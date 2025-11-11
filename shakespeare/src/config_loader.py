"""
Lightweight configuration loading for settings and secrets.

- Project settings live in `config/settings.yaml` (YAML is easy to diff/read).
- Secrets are loaded from `private/secrets.env` via `python-dotenv` if present.

This module intentionally avoids creating network clients; it only reads and
exposes configuration to the app.

Useful links:
- PyYAML: https://pyyaml.org/wiki/PyYAMLDocumentation
- python-dotenv: https://saurabh-kumar.com/python-dotenv/
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


def _read_yaml(path: Path) -> Dict[str, Any]:
    """Safely read YAML from `path` or return an empty dict on failure."""
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_private_config() -> Dict[str, Any]:
    """
    Load environment variables from `private/secrets.env` if it exists.
    Returns an empty dict (we rely on environment variables directly).
    """
    # Load .env from private (optional). We no longer use JSON config.
    env_path = Path("private/secrets.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    return {}


def load_settings() -> Dict[str, Any]:
    """Load `config/settings.yaml` into a dictionary (empty if missing)."""
    return _read_yaml(Path("config/settings.yaml"))


def get_secret(name: str, default: Optional[str] = None, private: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve a secret by name (environment takes precedence)."""
    # Precedence: environment > default
    if name in os.environ and os.environ[name]:
        return os.environ[name]
    return default


def load_all_config() -> Dict[str, Any]:
    """
    Aggregate settings and environment-backed secrets in a single dict.
    Only presence of secrets is exposed to the HTTP API, not values.
    """
    base = load_settings()
    private = load_private_config()
    # Expose resolved secrets commonly used; no network clients instantiated here
    secrets = {
        "OPENAI_API_KEY": get_secret("OPENAI_API_KEY"),
        "EVENTBRITE_API_KEY": get_secret("EVENTBRITE_API_KEY"),
        "ARTS_GOV_API_KEY": get_secret("ARTS_GOV_API_KEY"),
    }
    return {
        "settings": base,
        "private": private,
        "secrets": secrets,
    }

