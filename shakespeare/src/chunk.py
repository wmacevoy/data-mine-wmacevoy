"""
Chunking helper for splitting long texts into overlapping windows.

Why overlap? Overlap helps preserve context at chunk boundaries so that
retrievers and LLMs can see sentences that straddle two windows.

Typical defaults:
- `max_chars` ~ 500–1500 chars per chunk (tune for your data/LLM context).
- `overlap` ~ 10–20% of the window size.

Further reading:
- Text splitting in RAG systems (concepts): https://www.pinecone.io/learn/chunking-strategies/
"""

from typing import List


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> List[str]:
    """
    Split `text` into character windows of length up to `max_chars` with
    an overlap of `overlap` characters between consecutive windows.

    This simple splitter is token-agnostic and works for quick baselines.
    For token-aware splitting (e.g., by words or sentences), consider
    implementing a tokenizer-based approach.
    """
    chunks: List[str] = []
    if max_chars <= 0:
        return [text]
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks

