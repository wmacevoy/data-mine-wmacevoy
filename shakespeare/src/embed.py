"""
Embedding pipeline using classic IR features:

- TF–IDF for sparse bag-of-words vectors.
- TruncatedSVD (a.k.a. LSA/LSI) to derive dense semantic vectors.
- Row-normalization for cosine similarity.
- On-disk persistence of artifacts for reuse across sessions.

Why this approach? It is lightweight, offline-friendly, and transparent for
learning. You can later swap dense embeddings with transformer-based models
(`sentence-transformers`, OpenAI embeddings, etc.) keeping the retrieval API
the same.

Learn more:
- TF–IDF (scikit-learn): https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting
- TruncatedSVD & LSA: https://scikit-learn.org/stable/modules/decomposition.html#lsa
- Cosine similarity: https://scikit-learn.org/stable/modules/metrics.html#cosine-similarity
"""

from pathlib import Path
from typing import List, Tuple, Optional

import logging
from logging.handlers import RotatingFileHandler
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from scipy.sparse import save_npz, csr_matrix
import joblib
import yaml
from typing import Literal, Dict, Any

try:
    # OpenAI client is optional; only used if configured
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    OpenAI = None  # type: ignore


def _find_config_path() -> Optional[Path]:
    # Search upwards from CWD for config/settings.yaml so notebooks work
    cwd = Path.cwd()
    for base in [cwd, cwd.parent, cwd.parent.parent, cwd.parent.parent.parent]:
        cfg = base / "config" / "settings.yaml"
        if cfg.exists():
            return cfg
    # Fallback to project-local relative path if running from repo root
    cfg_local = Path("config/settings.yaml")
    return cfg_local if cfg_local.exists() else None


def _is_debug() -> bool:
    cfg_path = _find_config_path()
    if not cfg_path:
        return False
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return bool(data.get("debug", False))
    except Exception:
        return False


logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    if getattr(_setup_logging, "_configured", False):
        return
    cfg_path = _find_config_path()
    # Default locations if config not found
    base_dir = Path.cwd()
    if cfg_path:
        base_dir = cfg_path.parent.parent  # project root (.. from config/)
    log_dir = base_dir / "logs"
    log_file = "embedding.log"
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {} if cfg_path else {}
        log_cfg = data.get("logging", {}) or {}
        if "dir" in log_cfg and str(log_cfg.get("dir")):
            # If dir is relative, resolve under project root
            log_dir = (base_dir / str(log_cfg.get("dir"))).resolve()
        if "embed_file" in log_cfg:
            log_file = str(log_cfg.get("embed_file"))
    except Exception:
        pass
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if _is_debug() else logging.INFO
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Stream handler (console)
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)
    # Rotating file handler
    fh = RotatingFileHandler(str(log_dir / log_file), maxBytes=1_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # Avoid duplicate handlers
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        logger.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(sh)
    _setup_logging._configured = True  # type: ignore[attr-defined]
    # Emit a startup line so the log file is definitely non-empty
    try:
        logger.info("Logging initialized (dir=%s file=%s debug=%s)", str(log_dir), log_file, _is_debug())
    except Exception:
        pass


_setup_logging()


def load_corpus(processed_file: str = "data/processed/corpus.txt") -> List[str]:
    """
    Load the processed corpus (one document per line) into memory.
    Returns a list of non-empty lines.
    """
    path = Path(processed_file)
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if _is_debug():
        logger.debug("Loaded corpus: %d lines from %s", len(lines), processed_file)
    return lines


def fit_vectorizer(texts: List[str]) -> Tuple[TfidfVectorizer, csr_matrix]:
    """
    Fit a TF–IDF vectorizer on `texts` and return the fitted vectorizer
    plus the sparse document-term matrix.

    Notes:
    - `max_features` caps vocabulary size; adjust for data size.
    - `ngram_range=(1,2)` captures unigrams and bigrams.
    - English stop-words remove common words with little signal.
    """
    vectorizer = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    if _is_debug():
        logger.debug("TF-IDF: shape=%s nnz=%d vocab=%d", tuple(matrix.shape), matrix.nnz, len(vectorizer.vocabulary_))
        try:
            total_power = float(matrix.power(2).sum())
            logger.debug("TF-IDF: total_power=%.6f", total_power)
        except Exception:
            pass
    else:
        logger.info("TF-IDF built: shape=%s nnz=%d", tuple(matrix.shape), matrix.nnz)
    return vectorizer, matrix


class _PassthroughSVD:
    def __init__(self, n_components: int) -> None:
        self.n_components = int(max(1, n_components))

    def transform(self, X: csr_matrix) -> np.ndarray:
        import numpy as _np
        return _np.zeros((X.shape[0], self.n_components), dtype=_np.float32)

def _total_column_variance(X: csr_matrix) -> float:
    """
    Compute sum of per-column variances using sparse-friendly operations:
      Var(col) = E[X^2] - (E[X])^2
    Return sum over columns.
    """
    try:
        mean = np.asarray(X.mean(axis=0)).ravel()
        mean_sq = np.asarray(X.power(2).mean(axis=0)).ravel()
        var = mean_sq - np.square(mean)
        # Numerical floor at zero
        var[var < 0] = 0.0
        return float(var.sum())
    except Exception:
        # Fallback (may densify for tiny matrices)
        A = X.toarray()
        return float(np.var(A, axis=0).sum())

def fit_dense_projection(matrix: csr_matrix, n_components: int) -> Tuple[TruncatedSVD, np.ndarray]:
    """
    Fit TruncatedSVD on the TF–IDF matrix to obtain a dense LSA projection.
    Returns the fitted SVD object and row-normalized dense vectors.

    Guard rails:
    - Falls back to a zero embedding if the matrix is degenerate (e.g., no
      variance), which avoids numerical issues while keeping shapes consistent.
    """
    # Guard against degenerate inputs that cause division by zero inside scikit-learn
    num_rows, num_cols = matrix.shape
    if _is_debug():
        logger.debug("SVD input: rows=%d cols=%d nnz=%d requested_components=%d", num_rows, num_cols, matrix.nnz, n_components)
        try:
            total_power = float(matrix.power(2).sum())
            logger.debug("SVD input: total_power=%.6f", total_power)
        except Exception:
            pass
    # If clearly degenerate by structure, skip
    if num_rows < 2 or matrix.nnz == 0:
        if _is_debug():
            logger.debug("SVD degenerate path: returning zeros (rows<2 or nnz==0)")
        else:
            logger.info("SVD skipped: degenerate input (rows=%d nnz=%d)", num_rows, matrix.nnz)
        svd = _PassthroughSVD(n_components)
        dense = svd.transform(matrix)
        return svd, dense
    # If total variance across columns is ~0, skip to avoid scikit-learn warning
    var_sum = _total_column_variance(matrix)
    if var_sum <= 1e-12:
        if _is_debug():
            logger.debug("SVD skipped: near-zero total column variance (%.6e)", var_sum)
        else:
            logger.info("SVD skipped: near-zero total column variance")
        svd = _PassthroughSVD(n_components)
        dense = svd.transform(matrix)
        return svd, dense

    # Ensure n_components is valid for the data shape
    max_components = max(1, min(num_rows - 1, num_cols - 1))
    n_comp = max(1, min(n_components, max_components))
    if _is_debug() and n_comp != n_components:
        logger.debug("Adjusted n_components from %d to %d based on data shape", n_components, n_comp)

    svd = TruncatedSVD(n_components=n_comp, random_state=0)
    dense = svd.fit_transform(matrix)
    # Log variance stats to catch divide-by-zero conditions internally
    try:
        full_var = float(getattr(svd, "explained_variance_", np.array([])).sum())
        ratio = getattr(svd, "explained_variance_ratio_", np.array([]))
        nan_ratio = bool(np.isnan(ratio).any()) if isinstance(ratio, np.ndarray) else False
        if _is_debug():
            logger.debug("SVD: explained_variance_sum=%.6f n_components=%d nan_in_ratio=%s", full_var, n_comp, nan_ratio)
        else:
            logger.info("SVD fitted: components=%d var_sum=%.6f", n_comp, full_var)
    except Exception:
        pass
    dense = normalize(dense)  # row-normalize for cosine via dot
    return svd, dense


def persist(
    vectorizer: TfidfVectorizer,
    matrix: csr_matrix,
    svd: TruncatedSVD,
    dense: np.ndarray,
    out_dir: str = "data/embeddings",
) -> None:
    """
    Persist all learned artifacts so retrieval can run without re-fitting:
    - `vectorizer.joblib`: TF–IDF vectorizer
    - `tfidf.npz`: sparse document-term matrix
    - `svd.joblib`: TruncatedSVD model
    - `dense.npy`: normalized dense embeddings
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, out_path / "vectorizer.joblib")
    save_npz(out_path / "tfidf.npz", matrix)
    joblib.dump(svd, out_path / "svd.joblib")
    np.save(out_path / "dense.npy", dense)


def persist_dense_only(dense: np.ndarray, out_dir: str = "data/embeddings") -> None:
    """
    Persist only dense embeddings (used when `embeddings.method = openai`).
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    np.save(out_path / "dense.npy", dense)


def _load_dense_dim_from_config(default_dim: int = 256) -> int:
    """
    Read `retrieval.dense_dim` from `config/settings.yaml` if available, else
    return `default_dim`. This controls the SVD target dimensionality.
    """
    cfg_path = Path("config/settings.yaml")
    if not cfg_path.exists():
        return default_dim
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return int(data.get("retrieval", {}).get("dense_dim", default_dim))
    except Exception:
        return default_dim


def _load_embedding_config() -> Dict[str, Any]:
    """
    Read embedding configuration from `config/settings.yaml`.
    Returns dict with keys: method (str), model (str|None).
    """
    cfg_path = Path("config/settings.yaml")
    method = "tfidf"
    model = None
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            emb = data.get("embeddings", {}) or {}
            method = str(emb.get("method", method))
            if "model" in emb:
                model = str(emb.get("model"))
        except Exception:
            pass
    return {"method": method, "model": model}


def _openai_client() -> Optional["OpenAI"]:
    """Create an OpenAI client if the package is available and API key is set."""
    if OpenAI is None:
        logger.warning("openai package not installed; falling back to non-OpenAI path")
        return None
    try:
        client = OpenAI()
        return client
    except Exception:
        logger.warning("OpenAI client creation failed; check OPENAI_API_KEY")
        return None


def openai_embed_texts(texts: List[str], model: Optional[str]) -> Optional[np.ndarray]:
    """
    Embed texts with OpenAI embeddings API and return row-normalized vectors.
    Returns None if client/model unavailable.
    """
    client = _openai_client()
    if client is None:
        return None
    model_name = model or "text-embedding-3-small"
    try:
        # API returns list of data entries with embeddings
        resp = client.embeddings.create(model=model_name, input=texts)
        vectors = np.array([d.embedding for d in resp.data], dtype=np.float32)
        # Normalize rows for cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
        vectors = (vectors / norms).astype(np.float32)
        return vectors
    except Exception as e:
        logger.warning("OpenAI embeddings failed: %s", e)
        return None


def run_embedding(processed_file: str = "data/processed/corpus.txt", out_dir: str = "data/embeddings") -> None:
    """
    One-shot embedding pipeline controlled by `embeddings.method`:
    - tfidf: Fit TF–IDF + TruncatedSVD; persist vectorizer, tfidf, svd, dense.
    - openai: Call OpenAI embeddings; persist dense vectors only.
    """
    logger.info("Embedding start: processed_file=%s out_dir=%s", processed_file, out_dir)
    texts = load_corpus(processed_file)
    if not texts:
        logger.info("Embedding aborted: no texts loaded")
        return
    cfg = _load_embedding_config()
    method = (cfg.get("method") or "tfidf").lower()
    if method == "openai":
        emb = openai_embed_texts(texts, cfg.get("model"))
        if emb is None:
            logger.info("OpenAI embeddings unavailable; aborting (fallback to tfidf possible)")
            return
        persist_dense_only(emb, out_dir)
        logger.info("Embedding complete (openai): saved dense vectors to %s", out_dir)
        return
    # Default TF–IDF path
    vectorizer, matrix = fit_vectorizer(texts)
    dense_dim = _load_dense_dim_from_config()
    svd, dense = fit_dense_projection(matrix, n_components=dense_dim)
    persist(vectorizer, matrix, svd, dense, out_dir)
    logger.info("Embedding complete (tfidf): saved artifacts to %s", out_dir)


def build_embeddings(texts: List[str], out_dir: str = "data/embeddings") -> Dict[str, Any]:
    """
    Build embeddings for in-memory texts using configured method.
    Returns info dict with the chosen method and saved files.
    """
    info: Dict[str, Any] = {"out_dir": out_dir}
    cfg = _load_embedding_config()
    method = (cfg.get("method") or "tfidf").lower()
    info["method"] = method
    if method == "openai":
        emb = openai_embed_texts(texts, cfg.get("model"))
        if emb is None:
            return {**info, "status": "error", "message": "OpenAI embeddings unavailable"}
        persist_dense_only(emb, out_dir)
        return {**info, "status": "ok", "saved": ["dense.npy"]}
    # tfidf path
    vectorizer, matrix = fit_vectorizer(texts)
    dense_dim = _load_dense_dim_from_config()
    svd, dense = fit_dense_projection(matrix, n_components=dense_dim)
    persist(vectorizer, matrix, svd, dense, out_dir)
    return {**info, "status": "ok", "saved": ["vectorizer.joblib", "tfidf.npz", "svd.joblib", "dense.npy"]}

from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix


def train_tfidf(documents: List[str]) -> Tuple[TfidfVectorizer, csr_matrix]:
    """
    Lightweight helper for ad-hoc experimentation in notebooks.
    Trains a TF–IDF vectorizer with simple frequency cutoffs and bigrams.
    """
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_df=0.9,
        min_df=2,
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(documents)
    return vectorizer, matrix


def embed_query(query: str, vectorizer: TfidfVectorizer) -> csr_matrix:
    """
    Vectorize a user query with the trained TF–IDF vectorizer.
    Returns a `(1, D)` sparse row.
    """
    return vectorizer.transform([query])
