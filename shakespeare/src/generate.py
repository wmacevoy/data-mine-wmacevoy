"""
Answer generation utilities and a simple offline-friendly baseline.

What this module shows:
- How to assemble a prompt from retrieved context snippets (RAG pattern).
- A placeholder generator that returns a templated summary instead of calling
  an external LLM API (keeps the project runnable without network keys).

To plug in a real LLM later, replace `generate_answer` with a call to your
provider of choice and keep the prompt template stable.

Learn more:
- Retrieval-Augmented Generation (RAG): https://arxiv.org/abs/2005.11401
- Prompt engineering tips (vendor-agnostic concepts):
  https://platform.openai.com/docs/guides/prompt-engineering
"""

from typing import List, Dict
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import yaml
from typing import Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    OpenAI = None  # type: ignore


def _find_config_path():
    cwd = Path.cwd()
    for base in [cwd, cwd.parent, cwd.parent.parent, cwd.parent.parent.parent]:
        cfg = base / "config" / "settings.yaml"
        if cfg.exists():
            return cfg
    cfg_local = Path("config/settings.yaml")
    return cfg_local if cfg_local.exists() else None


def _is_debug() -> bool:
    cfg = _find_config_path()
    if not cfg:
        return False
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return bool(data.get("debug", False))
    except Exception:
        return False


logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    if getattr(_setup_logging, "_configured", False):
        return
    cfg = _find_config_path()
    base_dir = Path.cwd()
    if cfg:
        base_dir = cfg.parent.parent
    log_dir = base_dir / "logs"
    log_file = "generation.log"
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {} if cfg else {}
        log_cfg = data.get("logging", {}) or {}
        if "dir" in log_cfg and str(log_cfg.get("dir")):
            log_dir = (base_dir / str(log_cfg.get("dir"))).resolve()
        if "generate_file" in log_cfg and str(log_cfg.get("generate_file")):
            log_file = str(log_cfg.get("generate_file"))
    except Exception:
        pass
    log_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if _is_debug() else logging.INFO
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)
    fh = RotatingFileHandler(str(log_dir / log_file), maxBytes=1_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        logger.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(sh)
    _setup_logging._configured = True  # type: ignore[attr-defined]
    try:
        logger.info("Generation logging initialized (dir=%s file=%s debug=%s)", str(log_dir), log_file, _is_debug())
    except Exception:
        pass


_setup_logging()


PROMPT_TEMPLATE = (
    "System: You are a Shakespearean culture assistant.\n"
    "User: {query}\n"
    "Context:\n{context}\n"
    "Task: Answer the user using the context. Include dates and locations. Avoid speculation.\n"
)


def assemble_context(snippets: List[Dict]) -> str:
    """
    Join retrieved snippets into a delimiting block suitable for prompting.
    """
    return "\n---\n".join(s.get("text", "") for s in snippets)


def generate_answer(query: str, snippets: List[Dict]) -> str:
    """
    Baseline, offline-friendly generator. Formats a response using the prompt
    template and returns a short answer including the raw context.

    Swap this for a real LLM call to move from demo -> production.
    """
    # Decide model from config: generation.model = mock | openai-<model>
    model = _load_generation_model()
    context = assemble_context(snippets)
    if model and model.lower().startswith("openai"):
        model_name = model.split("openai-", 1)[-1] if "-" in model else model
        out = _generate_openai(query, context, model_name)
        if out:
            return out
        # Fallback to mock if OpenAI path fails
    # Offline-friendly dummy response using prompt template
    prompt = PROMPT_TEMPLATE.format(query=query, context=context)
    if not snippets:
        logger.info("generate_answer: no snippets; query=%s", query)
        return "I don't have enough indexed data yet. Please run ingestion/embedding."
    logger.info("generate_answer: query_len=%d snippets=%d context_len=%d", len(query), len(snippets), len(context))
    return f"Based on the context, here are relevant details for your query: {query}\n\n{context}"

from typing import List, Tuple


def assemble_prompt(user_query: str, contexts: List[str]) -> str:
    """
    Assemble a structured prompt by concatenating multiple context strings.
    Useful for simple experimentation in notebooks.
    """
    context_block = "\n\n".join(contexts)
    return (
        "System: You are a Shakespearean culture assistant.\n"
        f"User: {user_query}\n"
        "Context:\n"
        f"{context_block}\n"
        "Task: Answer the user using the context. Include dates and locations. Avoid speculation.\n"
    )


def simple_generate(user_query: str, top_contexts: List[Tuple[int, float, str]]) -> str:
    """
    Notebook-friendly formatter that prints top contexts as bullet points and
    invites the user to refine the query.
    """
    if not top_contexts:
        return (
            "I could not find relevant context yet. Please add Shakespeare texts to data/raw/ "
            "or provide more details in your question."
        )
    bullet_points = [f"- {text}" for (_i, _s, text) in top_contexts]
    joined = "\n".join(bullet_points[:5])
    return (
        "Here are the most relevant context snippets I found.\n" +
        joined +
        "\n\nBased on these, please refine your question if needed."
    )


def _load_generation_model() -> Optional[str]:
    cfg = _find_config_path()
    if not cfg:
        return None
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        gen = data.get("generation", {}) or {}
        m = gen.get("model")
        return str(m) if m else None
    except Exception:
        return None


def _openai_client() -> Optional["OpenAI"]:
    if OpenAI is None:
        logger.info("openai package not installed; using mock model")
        return None
    try:
        return OpenAI()
    except Exception:
        logger.info("OpenAI client creation failed; using mock model")
        return None


def _generate_openai(query: str, context: str, model_name: str) -> Optional[str]:
    client = _openai_client()
    if client is None:
        return None
    try:
        messages = [
            {"role": "system", "content": "You are a Shakespearean culture assistant."},
            {
                "role": "user",
                "content": (
                    f"{query}\n\nContext:\n{context}\n\n"
                    "Task: Answer the user using the context. Include dates and locations. Avoid speculation."
                ),
            },
        ]
        resp = client.chat.completions.create(model=model_name, messages=messages, temperature=0.2)
        if resp and resp.choices:
            return resp.choices[0].message.content or None
    except Exception as e:
        logger.info("OpenAI generation failed: %s", e)
    return None
