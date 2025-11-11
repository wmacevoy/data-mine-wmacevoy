"""
Utilities to programmatically update config/settings.yaml.

Usage examples (from a notebook or shell):

Python API
- from src.config_tools import set_generation_model, set_embeddings
- set_generation_model("mock")
- set_generation_model("openai-gpt-4o-mini")
- set_embeddings(method="tfidf")
- set_embeddings(method="openai", model="text-embedding-3-small")

CLI
- python -m src.config_tools --generation-model mock
- python -m src.config_tools --generation-model openai-gpt-4o-mini \
    --embeddings-method openai --embeddings-model text-embedding-3-small

Notes
- This modifies config/settings.yaml in-place. It creates the file if missing.
- Keys are created as needed; unrelated settings are preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import sys
import argparse
import yaml


SETTINGS_PATH = Path("config/settings.yaml")


def _load_settings() -> Dict[str, Any]:
    if SETTINGS_PATH.exists():
        try:
            return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}


def _save_settings(data: Dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _ensure_path(data: Dict[str, Any], path: list[str]) -> Dict[str, Any]:
    cur: Dict[str, Any] = data
    for key in path:
        if key not in cur or not isinstance(cur.get(key), dict):
            cur[key] = {}
        cur = cur[key]  # type: ignore[assignment]
    return cur


def set_generation_model(model: str) -> Dict[str, Any]:
    """Set generation.model to the given value (e.g., "mock" or "openai-gpt-4o-mini")."""
    cfg = _load_settings()
    gen = _ensure_path(cfg, ["generation"])
    gen["model"] = str(model)
    _save_settings(cfg)
    return cfg


def set_embeddings(method: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Set embeddings.method and (optionally) embeddings.model.
    - method: "tfidf" or "openai"
    - model: required when method=="openai" (e.g., "text-embedding-3-small")
    """
    cfg = _load_settings()
    emb = _ensure_path(cfg, ["embeddings"])
    emb["method"] = str(method)
    if method.lower() == "openai":
        if not model:
            raise ValueError("embeddings.method=openai requires embeddings.model")
        emb["model"] = str(model)
    elif model is not None:
        # Keep explicit model only when using OpenAI; remove otherwise to avoid confusion
        emb.pop("model", None)
    _save_settings(cfg)
    return cfg


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update config/settings.yaml")
    p.add_argument("--generation-model", dest="gen_model", help='e.g., "mock" or "openai-gpt-4o-mini"')
    p.add_argument("--embeddings-method", dest="emb_method", choices=["tfidf", "openai"], help='"tfidf" or "openai"')
    p.add_argument("--embeddings-model", dest="emb_model", help='OpenAI embedding model, e.g., "text-embedding-3-small"')
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    cfg = _load_settings()
    changed = False
    if args.gen_model:
        cfg = set_generation_model(args.gen_model)
        changed = True
    if args.emb_method:
        cfg = set_embeddings(args.emb_method, args.emb_model)
        changed = True
    if not changed:
        print("No changes requested. Use --help for options.")
        return 0
    print("Updated settings.yaml:")
    print(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

