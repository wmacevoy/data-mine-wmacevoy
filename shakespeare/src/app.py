from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from . import ingest as ingest_mod
from . import embed as embed_mod
from . import retrieve as retrieve_mod
from . import generate as generate_mod
from .config_loader import load_all_config


app = FastAPI(title="Shakespeare Festival Assistant")


@app.on_event("startup")
def _startup_load_config() -> None:
    cfg = load_all_config()
    app.state.config = cfg


class AskRequest(BaseModel):
    query: str
    k: Optional[int] = 5


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest) -> dict:
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
    processed = ingest_mod.run_ingestion()
    embed_mod.run_embedding(processed)
    return {"status": "built", "processed": processed}


@app.get("/config")
def get_config() -> dict:
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
    return {"status": "ok"}


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
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

