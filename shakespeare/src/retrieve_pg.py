"""
Database-backed retrieval using Postgres + pgvector.

Flow:
- Embed the query with the same TF–IDF + SVD pipeline.
- Normalize to unit length for cosine.
- Rank `chunks.embedding` by cosine distance using the `<#>` operator.

Links:
- pgvector querying: https://github.com/pgvector/pgvector#querying
"""

from typing import List, Dict, Any

import numpy as np
from psycopg.rows import dict_row

from .db import get_pool
from .embed import _load_embedding_config, openai_embed_texts
import joblib


def _load_query_artifacts():
    from pathlib import Path
    vec_path = Path("data/embeddings/vectorizer.joblib")
    svd_path = Path("data/embeddings/svd.joblib")
    if not (vec_path.exists() and svd_path.exists()):
        return None, None
    vectorizer = joblib.load(vec_path)
    svd = joblib.load(svd_path)
    return vectorizer, svd


def _embed_query(query: str) -> np.ndarray:
    """
    Convert the user query to a normalized dense vector, using the configured
    embeddings method (OpenAI or TF–IDF+SVD).
    """
    cfg = _load_embedding_config()
    method = (cfg.get("method") or "tfidf").lower()
    if method == "openai":
        emb = openai_embed_texts([query], cfg.get("model"))
        if emb is None:
            raise RuntimeError("OpenAI embeddings unavailable; check OPENAI_API_KEY and model")
        return emb.astype(np.float32).ravel()
    vectorizer, svd = _load_query_artifacts()
    if vectorizer is None or svd is None:
        raise RuntimeError("Embedding artifacts not found. Run full build first.")
    q_sparse = vectorizer.transform([query])
    q_dense = svd.transform(q_sparse)
    q_dense = q_dense / (np.linalg.norm(q_dense) + 1e-12)
    return q_dense.astype(np.float32).ravel()


def retrieve(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve top-`k` chunks by cosine similarity directly from Postgres.
    Returns a list of dicts with chunk text, file origin, and score.
    """
    q = _embed_query(query)
    pool = get_pool()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:  # type: ignore
        # cosine distance operator <#>
        cur.execute(
            """
            SELECT c.id, d.origin_path, c.chunk_index, c.content,
                   1 - (c.embedding <#> %s::vector) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            ORDER BY c.embedding <#> %s::vector ASC
            LIMIT %s
            """,
            (q, q, k),
        )
        rows = cur.fetchall()
    results: List[Dict[str, Any]] = []
    for r in rows:
        results.append({
            "index": int(r["chunk_index"]),
            "text": r["content"],
            "origin": r["origin_path"],
            "score": float(r["score"]),
        })
    return results
