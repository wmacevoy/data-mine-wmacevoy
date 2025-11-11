"""
Postgres database helpers for RAG indexing and retrieval (via pgvector).

Tables:
- documents: one row per source file (path + metadata/hash)
- chunks:    one row per chunk with a `vector(256)` embedding

This module handles connection pooling, schema migrations, and idempotent
upserts for both documents and chunks.

Learn more:
- psycopg (PostgreSQL driver): https://www.psycopg.org/psycopg3/docs/
- pgvector extension: https://github.com/pgvector/pgvector
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple, List

import numpy as np
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from .config_loader import load_all_config, get_secret
import yaml


_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """
    Create (or return) a global psycopg connection pool. If `DATABASE_URL`
    is provided via environment/secrets, it will be used; otherwise a local
    default DSN is assumed.
    """
    global _pool
    if _pool is not None:
        return _pool
    cfg = load_all_config()
    dsn = get_secret("DATABASE_URL") or "postgresql://raguser:ragpass@localhost:5432/rag"
    _pool = ConnectionPool(conninfo=dsn, kwargs={"row_factory": dict_row})
    # Register pgvector type adapter
    with _pool.connection() as conn:  # type: ignore
        register_vector(conn)
    return _pool


def _embedding_dim_from_config() -> int:
    """
    Determine vector dimension for the `chunks.embedding` column based on
    configuration. Falls back to 256.
    - tfidf: uses `retrieval.dense_dim` (default 256)
    - openai: infers from model name (1536 for text-embedding-3-small,
      3072 for text-embedding-3-large); defaults to 1536 if unspecified.
    """
    try:
        data = load_all_config().get("settings", {})
        emb = data.get("embeddings", {}) or {}
        method = str(emb.get("method", "tfidf")).lower()
        if method == "openai":
            model = str(emb.get("model", "text-embedding-3-small"))
            if "text-embedding-3-large" in model:
                return 3072
            return 1536
        # tfidf path
        retr = data.get("retrieval", {}) or {}
        return int(retr.get("dense_dim", 256))
    except Exception:
        return 256


def run_migrations() -> None:
    """
    Create required tables and the pgvector extension/index if missing.
    Uses IVFFLAT for approximate cosine similarity on `chunks.embedding`.
    """
    pool = get_pool()
    with pool.connection() as conn, conn.cursor() as cur:  # type: ignore
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        emb_dim = _embedding_dim_from_config()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
              id BIGSERIAL PRIMARY KEY,
              origin_path TEXT UNIQUE NOT NULL,
              origin_mtime TIMESTAMPTZ,
              origin_sha256 TEXT,
              created_at TIMESTAMPTZ DEFAULT NOW(),
              updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
              id BIGSERIAL PRIMARY KEY,
              document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
              chunk_index INT NOT NULL,
              chunk_sha256 TEXT,
              content TEXT NOT NULL,
              embedding vector(%s),
              created_at TIMESTAMPTZ DEFAULT NOW(),
              updated_at TIMESTAMPTZ DEFAULT NOW(),
              UNIQUE(document_id, chunk_index)
            )
            """,
            (emb_dim,),
        )
        # Index for vector similarity (IVFFLAT); requires non-empty table to build efficiently later
        cur.execute(
            """
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'chunks_embedding_ivfflat'
              ) THEN
                CREATE INDEX chunks_embedding_ivfflat ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
              END IF;
            END $$;
            """
        )
        conn.commit()


def sha256_text(text: str) -> str:
    """Compute a hex SHA-256 digest for a Unicode string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Compute a hex SHA-256 digest for the bytes of `path`."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_document(origin_path: Path) -> int:
    """
    Insert or update a `documents` row for `origin_path` and return its id.
    Stores last modified time and a content hash to detect changes.
    """
    pool = get_pool()
    mtime = datetime.fromtimestamp(origin_path.stat().st_mtime)
    digest = sha256_file(origin_path)
    with pool.connection() as conn, conn.cursor() as cur:  # type: ignore
        cur.execute(
            """
            INSERT INTO documents (origin_path, origin_mtime, origin_sha256)
            VALUES (%s, %s, %s)
            ON CONFLICT (origin_path)
            DO UPDATE SET origin_mtime = EXCLUDED.origin_mtime,
                          origin_sha256 = EXCLUDED.origin_sha256,
                          updated_at = NOW()
            RETURNING id
            """,
            (str(origin_path), mtime, digest),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])  # type: ignore


def upsert_chunk(document_id: int, chunk_index: int, content: str, embedding: np.ndarray) -> int:
    """
    Insert or update a `chunks` row for (`document_id`, `chunk_index`).
    Content hash enables idempotence; embedding is stored as `vector(256)`.
    Returns the chunk id.
    """
    pool = get_pool()
    sha = sha256_text(content)
    emb = embedding.astype(np.float32)
    with pool.connection() as conn, conn.cursor() as cur:  # type: ignore
        cur.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, chunk_sha256, content, embedding)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (document_id, chunk_index)
            DO UPDATE SET content = EXCLUDED.content,
                          chunk_sha256 = EXCLUDED.chunk_sha256,
                          embedding = EXCLUDED.embedding,
                          updated_at = NOW()
            RETURNING id
            """,
            (document_id, chunk_index, sha, content, emb),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])  # type: ignore
