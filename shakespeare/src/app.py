"""
FastAPI service exposing the Shakespeare RAG pipeline.

Endpoints (high level):
- `GET /health`: basic health check.
- `POST /ask`: retrieve relevant snippets and generate an answer.
- `POST /build`: run ingestion + embedding; optionally index into Postgres.
- `POST /rebuild`: incremental (DB-only) re-index.
- `GET /config`: show non-sensitive settings and which secrets are present.

Architecture notes for students:
- Retrieval defaults to a hybrid TF–IDF + LSA similarity unless `DATABASE_URL`
  is present, in which case Postgres + pgvector retrieval is attempted first.
- All long-running steps (ingest/embed/index) are kept simple for clarity.
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response, Request
from pydantic import BaseModel

from . import ingest as ingest_mod
from . import embed as embed_mod
from . import retrieve as retrieve_mod
from . import generate as generate_mod
from .config_loader import load_all_config
from .db import run_migrations
from .index_pg import index_file
from .retrieve_pg import retrieve as pg_retrieve
from .embed import load_corpus, fit_vectorizer, fit_dense_projection, persist
from pathlib import Path
import os


app = FastAPI(title="Shakespeare Festival Assistant")
# CORS for local static server (and general local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ensure_cors_headers(request: Request, call_next):
    # Fallback CORS headers in case upstream middleware is bypassed
    origin = request.headers.get("origin", "*")
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": request.headers.get("Access-Control-Request-Method", "*"),
            "Access-Control-Allow-Headers": request.headers.get("Access-Control-Request-Headers", "*"),
            "Access-Control-Allow-Credentials": "true",
        }
        return Response(status_code=204, headers=headers)
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers.setdefault("Access-Control-Allow-Methods", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "*")
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.on_event("startup")
def _startup_load_config() -> None:
    cfg = load_all_config()
    app.state.config = cfg
    # Initialize DB schema if DATABASE_URL is present
    try:
        if cfg.get("secrets", {}).get("DATABASE_URL"):
            run_migrations()
    except Exception:
        pass
    # CORS middleware is configured above at app creation


class AskRequest(BaseModel):
    query: str
    k: Optional[int] = 5


@app.get("/health")
def health() -> dict:
    """Return a lightweight health status payload for uptime checks."""
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    """
    Answer a user query using retrieval-augmented generation.

    Flow:
    - Try DB-backed retrieval (pgvector) if configured; otherwise use local artifacts.
    - If no results, instruct the user to build the index.
    - Format an answer with the simple generator in `generate.py`.
    """
    # Prefer Postgres vector retrieval if DB is configured; fallback to local
    use_db = bool(getattr(app.state, "config", {}).get("secrets", {}).get("DATABASE_URL"))
    if use_db:
        try:
            results = pg_retrieve(req.query, k=req.k or 5)
        except Exception:
            results = retrieve_mod.retrieve(req.query, k=req.k or 5)
    else:
        results = retrieve_mod.retrieve(req.query, k=req.k or 5)
    if not results:
        return {
            "answer": "Index not ready. Run ingestion and embedding first.",
            "results": [],
        }
    answer = generate_mod.generate_answer(req.query, results)
    return {"answer": answer, "results": results}


@app.post("/build")
def build_pipeline() -> dict:
    """
    Run a full local build:
    - Ingest and clean raw files into `data/processed/corpus.txt`.
    - Fit embeddings and persist artifacts.
    - If a DB is configured, (re)index all raw files into Postgres.
    """
    processed = ingest_mod.run_ingestion()
    # Full rebuild of artifacts based on configured embeddings method
    texts = embed_mod.load_corpus(processed)
    if not texts:
        return {"status": "no_data"}
    build_info = embed_mod.build_embeddings(texts)

    # If DB configured, (re)index all raw files idempotently
    cfg = getattr(app.state, "config", {})
    if cfg.get("secrets", {}).get("DATABASE_URL"):
        raw_dir = Path("data/raw")
        count = 0
        for p in raw_dir.rglob("*.txt"):
            try:
                count += index_file(p)
            except Exception:
                continue
        return {"status": "built", "processed": processed, "chunks_indexed": count, "embedding": build_info}
    return {"status": "built", "processed": processed, "embedding": build_info}


@app.post("/rebuild")
def rebuild_incremental() -> dict:
    """
    Incremental DB re-index of raw files using existing embedding artifacts.
    Requires `DATABASE_URL` to be configured.
    """
    # Incremental: assume artifacts exist; process new/modified raw files only
    cfg = getattr(app.state, "config", {})
    if not cfg.get("secrets", {}).get("DATABASE_URL"):
        return {"status": "db_not_configured"}
    raw_dir = Path("data/raw")
    count = 0
    for p in raw_dir.rglob("*.txt"):
        try:
            count += index_file(p)
        except Exception:
            continue
    return {"status": "rebuild_complete", "chunks_indexed": count}


@app.get("/config")
def get_config() -> dict:
    """
    Return non-sensitive settings and which secrets are present (boolean only).
    Useful for debugging environment configuration without leaking values.
    """
    # Expose non-sensitive structure and whether secrets are present (not their values)
    cfg = getattr(app.state, "config", {})
    secrets = cfg.get("secrets", {})
    present = {k: bool(v) for k, v in secrets.items()}
    return {
        "settings": cfg.get("settings", {}),
        "secrets_present": present,
    }

import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from .ingest import build_processed_corpus, load_raw_documents
from .embed import train_tfidf, embed_query
from .retrieve import retrieve_top_k
from .generate import simple_generate


class AskRequest(BaseModel):
    query: str
    k: int | None = None


def _load_settings() -> Dict[str, Any]:
    settings_path = Path("config/settings.yaml")
    if settings_path.exists():
        return yaml.safe_load(settings_path.read_text()) or {}
    return {}


def _get_setting(settings: Dict[str, Any], path: List[str], default: Any) -> Any:
    cur: Any = settings
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


app = FastAPI(title="Shakespeare Festival Assistant")


# Lazy in-memory state
STATE: Dict[str, Any] = {
    "documents": [],
    "vectorizer": None,
    "doc_matrix": None,
    "settings": {},
}


@app.on_event("startup")
def startup() -> None:
    # Load env first (encrypted via git-crypt in private/ when configured)
    load_dotenv(dotenv_path=Path("private/secrets.env"), override=False)

    settings = _load_settings()
    STATE["settings"] = settings

    raw_dir = _get_setting(settings, ["data", "raw_dir"], "data/raw")
    processed_dir = _get_setting(settings, ["data", "processed_dir"], "data/processed")

    # Build documents corpus
    documents = build_processed_corpus(raw_dir, processed_dir)
    if not documents:
        # fallback to raw docs without chunking if none processed
        documents = load_raw_documents(raw_dir)
    STATE["documents"] = documents

    if documents:
        vectorizer, doc_matrix = train_tfidf(documents)
        STATE["vectorizer"] = vectorizer
        STATE["doc_matrix"] = doc_matrix


@app.get("/health")
def health() -> Dict[str, str]:
    """(Alternate app instance) Basic health check."""
    return {"status": "ok"}


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
    """
    (Alternate app instance) Retrieve contexts with sparse TF–IDF and format a
    simple answer suitable for notebook demos.
    """
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    if STATE["vectorizer"] is None or STATE["doc_matrix"] is None:
        # service can still run; inform caller to add data
        top_contexts: List[Tuple[int, float, str]] = []
        answer = simple_generate(payload.query, top_contexts)
        return {
            "answer": answer,
            "contexts": [],
            "k": 0,
            "info": "No corpus available yet. Add .txt files to data/raw/",
        }

    start = time.time()
    vector = embed_query(payload.query, STATE["vectorizer"])
    k_default = _get_setting(STATE["settings"], ["retrieval", "top_k"], 5)
    k = payload.k or k_default
    results = retrieve_top_k(vector, STATE["doc_matrix"], STATE["documents"], top_k=k)
    elapsed_ms = int((time.time() - start) * 1000)

    answer = simple_generate(payload.query, results)

    return {
        "answer": answer,
        "contexts": [
            {"index": i, "score": s, "text": t[:5000]} for (i, s, t) in results
        ],
        "k": k,
        "latency_ms": elapsed_ms,
    }
