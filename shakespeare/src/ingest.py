import os
from pathlib import Path
from typing import List


def read_text_files(input_dir: str) -> List[str]:
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
                    continue
    return texts


def simple_clean(text: str) -> str:
    # Minimal cleanup; expand as needed (lowercasing, strip, collapse ws)
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def write_lines(lines: List[str], output_file: str) -> None:
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def run_ingestion(raw_dir: str = "data/raw", processed_file: str = "data/processed/corpus.txt") -> str:
    texts = read_text_files(raw_dir)
    cleaned_lines: List[str] = [simple_clean(t) for t in texts if t.strip()]
    write_lines(cleaned_lines, processed_file)
    return processed_file

import os
import re
from pathlib import Path
from typing import List


def _clean_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # try to cut at a sentence boundary
        period_idx = text.rfind(".", start, end)
        split_idx = period_idx + 1 if period_idx != -1 and period_idx > start else end
        chunks.append(text[start:split_idx].strip())
        start = split_idx
    return [c for c in chunks if c]


def load_raw_documents(raw_dir: str) -> List[str]:
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

