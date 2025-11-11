"""
Ingestion utilities for building a text corpus.

What this module does (at a glance):
- Walks a directory (e.g., `data/raw/`) to find `.txt`/`.md` files.
- Applies light, reproducible cleaning to normalize whitespace and newlines.
- Optionally splits long documents into manageable chunks for retrieval.
- Writes the processed corpus to disk for downstream embedding.

Key ideas for students:
- File I/O with `pathlib.Path` and directory walking via `os.walk`.
- Text normalization (strip, replace, regex) to reduce noise.
- Simple chunking by character window with a heuristic for sentence boundaries.

Learn more:
- Pathlib (official docs): https://docs.python.org/3/library/pathlib.html
- Regular expressions in Python: https://docs.python.org/3/library/re.html
- Text feature extraction (scikit-learn):
  https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction
- Sentence tokenization (alternative to our heuristic):
  NLTK https://www.nltk.org/api/nltk.tokenize.html, spaCy https://spacy.io/usage/linguistic-features#sbd
"""

import os
from pathlib import Path
from typing import List


def read_text_files(input_dir: str) -> List[str]:
    """
    Recursively read all `.txt` and `.md` files under `input_dir` and return
    their content as a list of strings. Invalid encodings are skipped safely.

    Parameters
    - input_dir: directory containing raw text files (e.g., `data/raw`).

    Returns
    - List of raw document strings (one per file).
    """
    input_path = Path(input_dir)
    texts: List[str] = []
    if not input_path.exists():
        return texts
    for root, _dirs, files in os.walk(input_dir):
        for name in files:
            if name.lower().endswith((".txt", ".md")):
                file_path = Path(root) / name
                try:
                    texts.append(file_path.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    # If a file can't be decoded with UTF-8, ignore it.
                    continue
    return texts


def simple_clean(text: str) -> str:
    """
    Minimal text cleanup suitable for a baseline pipeline.
    - Replace newlines with spaces, collapse repeated whitespace, and strip.

    Tip: You can extend this for lowercasing, punctuation handling, etc.,
    depending on downstream needs.
    """
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def write_lines(lines: List[str], output_file: str) -> None:
    """
    Write each string in `lines` to `output_file`, one per line.
    Ensures the output directory exists.
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def run_ingestion(raw_dir: str = "data/raw", processed_file: str = "data/processed/corpus.txt") -> str:
    """
    End-to-end convenience function:
    - Read raw files from `raw_dir`.
    - Apply `simple_clean`.
    - Write the processed corpus to `processed_file` (one line per document).

    Returns the path to the processed corpus for downstream steps.
    """
    texts = read_text_files(raw_dir)
    cleaned_lines: List[str] = [simple_clean(t) for t in texts if t.strip()]
    write_lines(cleaned_lines, processed_file)
    return processed_file

import os
import re
from pathlib import Path
from typing import List


def _clean_text(text: str) -> str:
    """
    Normalize newlines to `\n` and collapse repeated whitespace using regex.
    This produces a single-line string per chunk/document for easy storage.
    """
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    """
    Split a long string into roughly sentence-aligned chunks no longer than
    `max_chars` characters.

    Heuristic: within each window, we try to split at the last period `.` to
    avoid cutting mid-sentence; if none is found, we split at the window end.

    Why chunk? Retrieval systems work better when indexing moderately sized
    passages rather than entire books. For more robust sentence segmentation,
    consider NLTK or spaCy (see links in the module docstring).
    """
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # Try to cut at a sentence boundary (very simple heuristic)
        period_idx = text.rfind(".", start, end)
        split_idx = period_idx + 1 if period_idx != -1 and period_idx > start else end
        chunks.append(text[start:split_idx].strip())
        start = split_idx
    return [c for c in chunks if c]


def load_raw_documents(raw_dir: str) -> List[str]:
    """
    Load and clean all `*.txt` files under `raw_dir` into a list of strings.
    """
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        return []
    documents: List[str] = []
    for path in raw_path.rglob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(errors="ignore")
        documents.append(_clean_text(text))
    return documents


def build_processed_corpus(raw_dir: str, processed_dir: str) -> List[str]:
    """
    Produce a folder of chunk files from raw documents:
    - Reads `raw_dir` via `load_raw_documents`.
    - Splits each document into chunks using `_chunk_text`.
    - Writes each chunk as `processed_dir/chunk_00000.txt` for inspection.

    Returns the in-memory list of chunk strings for immediate use.
    """
    os.makedirs(processed_dir, exist_ok=True)
    raw_documents = load_raw_documents(raw_dir)
    if not raw_documents:
        return []
    chunks: List[str] = []
    for doc in raw_documents:
        chunks.extend(_chunk_text(doc))
    # Optionally write chunks to disk for inspection
    for i, chunk in enumerate(chunks):
        Path(processed_dir, f"chunk_{i:05d}.txt").write_text(chunk, encoding="utf-8")
    return chunks
