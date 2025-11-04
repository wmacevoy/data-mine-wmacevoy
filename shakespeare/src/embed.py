from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from scipy.sparse import save_npz, csr_matrix
import joblib
import yaml


def load_corpus(processed_file: str = "data/processed/corpus.txt") -> List[str]:
    path = Path(processed_file)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fit_vectorizer(texts: List[str]) -> Tuple[TfidfVectorizer, csr_matrix]:
    vectorizer = TfidfVectorizer(max_features=50000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def fit_dense_projection(matrix: csr_matrix, n_components: int) -> Tuple[TruncatedSVD, np.ndarray]:
    svd = TruncatedSVD(n_components=n_components, random_state=0)
    dense = svd.fit_transform(matrix)
    dense = normalize(dense)  # row-normalize for cosine via dot
    return svd, dense


def persist(
    vectorizer: TfidfVectorizer,
    matrix: csr_matrix,
    svd: TruncatedSVD,
    dense: np.ndarray,
    out_dir: str = "data/embeddings",
) -> None:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, out_path / "vectorizer.joblib")
    save_npz(out_path / "tfidf.npz", matrix)
    joblib.dump(svd, out_path / "svd.joblib")
    np.save(out_path / "dense.npy", dense)


def _load_dense_dim_from_config(default_dim: int = 256) -> int:
    cfg_path = Path("config/settings.yaml")
    if not cfg_path.exists():
        return default_dim
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return int(data.get("retrieval", {}).get("dense_dim", default_dim))
    except Exception:
        return default_dim


def run_embedding(processed_file: str = "data/processed/corpus.txt", out_dir: str = "data/embeddings") -> None:
    texts = load_corpus(processed_file)
    if not texts:
        return
    vectorizer, matrix = fit_vectorizer(texts)
    dense_dim = _load_dense_dim_from_config()
    svd, dense = fit_dense_projection(matrix, n_components=dense_dim)
    persist(vectorizer, matrix, svd, dense, out_dir)

from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix


def train_tfidf(documents: List[str]) -> Tuple[TfidfVectorizer, csr_matrix]:
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_df=0.9,
        min_df=2,
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(documents)
    return vectorizer, matrix


def embed_query(query: str, vectorizer: TfidfVectorizer) -> csr_matrix:
    return vectorizer.transform([query])

