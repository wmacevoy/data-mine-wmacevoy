import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_private_config() -> Dict[str, Any]:
    # Load .env from private (optional). We no longer use JSON config.
    env_path = Path("private/secrets.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    return {}


def load_settings() -> Dict[str, Any]:
    return _read_yaml(Path("config/settings.yaml"))


def get_secret(name: str, default: Optional[str] = None, private: Optional[Dict[str, Any]] = None) -> Optional[str]:
    # Precedence: environment > default
    if name in os.environ and os.environ[name]:
        return os.environ[name]
    return default


def load_all_config() -> Dict[str, Any]:
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


