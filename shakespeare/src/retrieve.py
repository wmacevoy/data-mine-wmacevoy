"""
Retrieval utilities for both hybrid and sparse-only search.

Two retrieval paths are provided:
- Hybrid (default): weighted sum of sparse TF–IDF cosine and dense LSA cosine.
- Sparse-only helpers for simple experiments.

Why hybrid? Sparse (exact lexical) matches excel at keyword precision, while
dense (semantic) vectors capture paraphrases and related concepts. Combining
them often improves recall and robustness.

Learn more:
- Cosine similarity (scikit-learn): https://scikit-learn.org/stable/modules/metrics.html#cosine-similarity
- Hybrid search overview: https://www.pinecone.io/learn/hybrid-search/
"""

from pathlib import Path
from typing import List, Tuple, Dict, Any

import numpy as np
from scipy.sparse import load_npz
from sklearn.metrics.pairwise import cosine_similarity
import joblib
import yaml
from .embed import openai_embed_texts


def load_artifacts(
    embeddings_dir: str = "data/embeddings",
    processed_file: str = "data/processed/corpus.txt",
):
    """
    Load persisted vectorizer, TF–IDF matrix, optional SVD+dense vectors, and
    the processed corpus texts.
    """
    vec_path = Path(embeddings_dir) / "vectorizer.joblib"
    mat_path = Path(embeddings_dir) / "tfidf.npz"
    svd_path = Path(embeddings_dir) / "svd.joblib"
    dense_path = Path(embeddings_dir) / "dense.npy"
    corpus_path = Path(processed_file)
    # Support both tfidf (requires vec + tfidf) and openai (dense + corpus)
    vectorizer = joblib.load(vec_path) if vec_path.exists() else None
    matrix = load_npz(mat_path) if mat_path.exists() else None
    svd = joblib.load(svd_path) if svd_path.exists() else None
    dense = np.load(dense_path) if dense_path.exists() else None
    corpus = []
    if corpus_path.exists():
        corpus = [line.strip() for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # If nothing exists, return minimal triple for caller to handle
    return vectorizer, matrix, corpus, svd, dense


def _load_embedding_method(default: str = "tfidf") -> str:
    cfg_path = Path("config/settings.yaml")
    if not cfg_path.exists():
        return default
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return str(data.get("embeddings", {}).get("method", default)).lower()
    except Exception:
        return default


def _load_weights_from_config(default_sparse: float = 0.5, default_dense: float = 0.5) -> Tuple[float, float]:
    """
    Read retrieval weights from `config/settings.yaml` under
    `retrieval.weights.sparse` and `retrieval.weights.dense`.
    Returns weights normalized to sum to 1.
    """
    cfg_path = Path("config/settings.yaml")
    if not cfg_path.exists():
        return default_sparse, default_dense
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        w = data.get("retrieval", {}).get("weights", {})
        a = float(w.get("sparse", default_sparse))
        b = float(w.get("dense", default_dense))
        s = a + b
        if s <= 0:
            return default_sparse, default_dense
        return a / s, b / s
    except Exception:
        return default_sparse, default_dense


def cosine_top_k_sparse(query_vec, matrix, k: int = 5) -> np.ndarray:
    """
    Return indices of the top-k documents by TF–IDF cosine similarity.
    Uses sklearn's optimized routines for sparse matrices.
    """
    sims = cosine_similarity(matrix, query_vec).ravel()  # (N,)
    order = np.argsort(-sims)
    return order[:k]


def retrieve(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: rank the corpus using a weighted sum of
    - Sparse TF–IDF cosine scores, and
    - Dense LSA (SVD) cosine scores.

    Returns a list of dicts with the top-k texts and score components.
    """
    vectorizer, matrix, corpus, svd, dense = load_artifacts()
    if not corpus:
        return []

    method = _load_embedding_method()
    # Dense-only path for OpenAI embeddings
    if method == "openai":
        if dense is None:
            return []
        # Load model name from config if available
        cfg_path = Path("config/settings.yaml")
        model_name = None
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            model_name = (data.get("embeddings", {}) or {}).get("model")
        except Exception:
            pass
        q_vecs = openai_embed_texts([query], model=model_name)
        if q_vecs is None:
            return []
        q = q_vecs[0]
        scores = dense @ q  # cosine via dot on normalized vectors
        order = np.argsort(-scores)[:k]
        results: List[Dict[str, Any]] = []
        for i in order:
            if 0 <= int(i) < len(corpus):
                results.append({
                    "text": corpus[int(i)],
                    "index": int(i),
                    "score": float(scores[int(i)]),
                    "components": {"sparse": 0.0, "dense": float(scores[int(i)])},
                })
        return results

    if vectorizer is None or matrix is None:
        return []

    q_sparse = vectorizer.transform([query])  # (1, D)

    # Sparse similarity (TF-IDF cosine)
    sparse_scores = cosine_similarity(matrix, q_sparse).ravel()

    # Dense similarity (SVD/LSA cosine)
    if svd is not None and dense is not None:
        q_dense = svd.transform(q_sparse)
        q_dense = q_dense / (np.linalg.norm(q_dense) + 1e-12)
        dense_scores = dense @ q_dense.ravel()
    else:
        dense_scores = np.zeros_like(sparse_scores)

    w_sparse, w_dense = _load_weights_from_config()
    scores = w_sparse * sparse_scores + w_dense * dense_scores

    order = np.argsort(-scores)[:k]
    results: List[Dict[str, Any]] = []
    for i in order:
        if 0 <= int(i) < len(corpus):
            results.append({
                "text": corpus[int(i)],
                "index": int(i),
                "score": float(scores[int(i)]),
                "components": {
                    "sparse": float(sparse_scores[int(i)]),
                    "dense": float(dense_scores[int(i)]),
                },
            })
    return results

from typing import List, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity


def retrieve_top_k(
    query_vector: csr_matrix,
    document_matrix: csr_matrix,
    documents: List[str],
    top_k: int = 5,
) -> List[Tuple[int, float, str]]:
    """
    Simpler sparse-only retrieval: given a query vector and document matrix,
    compute cosine similarities and return the top-k results as
    (index, score, text) tuples.
    """
    if document_matrix.shape[0] == 0:
        return []
    sims = cosine_similarity(query_vector, document_matrix)[0]
    if sims.size == 0:
        return []
    top_k = max(1, min(top_k, sims.size))
    top_indices = np.argpartition(-sims, top_k - 1)[:top_k]
    # sort those indices by score descending
    top_indices = top_indices[np.argsort(-sims[top_indices])]
    results: List[Tuple[int, float, str]] = []
    for idx in top_indices:
        score = float(sims[idx])
        results.append((int(idx), score, documents[idx]))
    return results
