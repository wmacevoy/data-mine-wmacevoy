"""
Index Shakespeare chunks into Postgres with pgvector.

Flow:
- Load previously-fitted TF–IDF + SVD artifacts from `data/embeddings/`.
- Chunk each file with character-overlap windows.
- Transform chunks to dense, row-normalized vectors for cosine distance.
- Upsert into Postgres tables (`documents`, `chunks`).

Why normalize? pgvector's `vector_cosine_ops` expects normalized vectors for
true cosine similarity. We store `float32` vectors to save space.

Learn more:
- pgvector extension: https://github.com/pgvector/pgvector
- Cosine operator `<#>` in pgvector: https://github.com/pgvector/pgvector#querying
"""

from pathlib import Path
from typing import List

import numpy as np

from .chunk import chunk_text
from .db import upsert_document, upsert_chunk
from .embed import load_corpus, _load_embedding_config, openai_embed_texts
import joblib
from scipy.sparse import csr_matrix


def _load_artifacts():
    # Load pre-fitted vectorizer and SVD to transform new chunks idempotently
    from pathlib import Path
    import joblib

    vec_path = Path("data/embeddings/vectorizer.joblib")
    svd_path = Path("data/embeddings/svd.joblib")
    if not (vec_path.exists() and svd_path.exists()):
        return None, None
    vectorizer = joblib.load(vec_path)
    svd = joblib.load(svd_path)
    return vectorizer, svd


def transform_texts(texts: List[str]) -> np.ndarray:
    """
    Transform raw texts to dense, row-normalized vectors using the fitted
    vectorizer and SVD artifacts (see `embed.py`).
    """
    cfg = _load_embedding_config()
    method = (cfg.get("method") or "tfidf").lower()
    if method == "openai":
        emb = openai_embed_texts(texts, cfg.get("model"))
        if emb is None:
            raise RuntimeError("OpenAI embeddings unavailable; check OPENAI_API_KEY and model")
        return emb.astype(np.float32)
    vectorizer, svd = _load_artifacts()
    if vectorizer is None or svd is None:
        raise RuntimeError("Embedding artifacts not found. Run full build first.")
    X: csr_matrix = vectorizer.transform(texts)
    dense = svd.transform(X)
    # Normalize rows for cosine similarity in pgvector (cosine_ops expects normalized vectors)
    norms = np.linalg.norm(dense, axis=1, keepdims=True) + 1e-12
    dense = (dense / norms).astype(np.float32)
    return dense


def index_file(path: Path, max_chars: int = 1000, overlap: int = 100) -> int:
    """
    Chunk the file at `path`, embed each chunk, and upsert into Postgres.
    Returns the number of chunks inserted/updated.
    """
    document_id = upsert_document(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    parts = chunk_text(text, max_chars=max_chars, overlap=overlap)
    if not parts:
        return 0
    embeddings = transform_texts(parts)
    for i, (content, vec) in enumerate(zip(parts, embeddings)):
        upsert_chunk(document_id, i, content, vec)
    return len(parts)
