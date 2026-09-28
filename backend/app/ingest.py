"""
Run once before starting the server (re-run after adding new documents):
    ./dev.sh ingest

Each re-ingest rebuilds the collection from scratch so citations stay consistent.
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import config


# ── Source metadata ────────────────────────────────────────────────────────────

def _load_sources() -> dict:
    path = Path(config.SOURCES_FILE)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_note", None)
        return data
    except Exception as e:
        print(f"  [warn] Could not load {path}: {e}")
        return {}


def _resolve_chapter(page: int, chapters: list) -> str:
    """Return the chapter title for a given 1-indexed page number."""
    resolved = ""
    for ch in sorted(chapters, key=lambda c: c["page"]):
        if ch["page"] <= page:
            resolved = ch.get("title", "")
        else:
            break
    return resolved


def _build_citation(meta: dict, chapter: str, page: Optional[int]) -> str:
    """Build a human-readable citation string from source metadata."""
    parts = [meta.get("title", "Unknown")]
    if chapter:
        parts.append(chapter)
    if page is not None:
        parts.append(f"p. {page}")
    return ", ".join(parts)


# ── Chunking ───────────────────────────────────────────────────────────────────

def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_pdf(path: Path, source_meta: dict, chunk_size: int, overlap: int) -> List[dict]:
    reader = PdfReader(str(path))
    chunks, idx = [], 0
    stem = path.stem
    chapters = source_meta.get("chapters", [])
    url = source_meta.get("url", "")

    for page_num, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        chapter = _resolve_chapter(page_num, chapters)
        citation = _build_citation(source_meta, chapter, page_num)
        for chunk in _split_text(text, chunk_size, overlap):
            chunks.append({
                "id": f"{stem}_{idx:04d}",
                "text": chunk,
                "source": path.name,
                "page": page_num,
                "citation": citation,
                "url": url,
            })
            idx += 1
    return chunks


def chunk_txt(path: Path, source_meta: dict, chunk_size: int, overlap: int) -> List[dict]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    stem = path.stem
    url = source_meta.get("url", "")
    citation = source_meta.get("title", path.name)
    chunks = []
    for idx, chunk in enumerate(_split_text(text, chunk_size, overlap)):
        chunks.append({
            "id": f"{stem}_{idx:04d}",
            "text": chunk,
            "source": path.name,
            "page": None,
            "citation": citation,
            "url": url,
        })
    return chunks


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    docs_dir = Path(config.DOCUMENTS_DIR)
    if not docs_dir.exists():
        print(f"Documents directory not found: {docs_dir}")
        sys.exit(1)

    files = list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.txt"))
    if not files:
        print(f"No .pdf or .txt files found in {docs_dir}")
        sys.exit(0)

    sources = _load_sources()
    if sources:
        print(f"Loaded source metadata for {len(sources)} file(s) from sources.json")
    else:
        print("No sources.json found — citations will use raw filenames")

    print(f"Found {len(files)} document(s). Loading and chunking...")

    all_chunks: List[dict] = []
    for f in files:
        meta = sources.get(f.name, {"title": f.stem, "url": "", "chapters": []})
        if f.suffix.lower() == ".pdf":
            chunks = chunk_pdf(f, meta, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        else:
            chunks = chunk_txt(f, meta, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        print(f"  {f.name}: {len(chunks)} chunks  (title: {meta.get('title', f.stem)})")
        all_chunks.extend(chunks)

    if not all_chunks:
        print("No text extracted from documents.")
        sys.exit(0)

    print(f"Total chunks: {len(all_chunks)}. Embedding with {config.EMBEDDING_MODEL}...")
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    print(f"Storing in ChromaDB at {config.CHROMA_PERSIST_DIR}...")
    client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)

    # Delete and recreate so citations stay consistent after re-ingest
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.upsert(
        ids=[c["id"] for c in all_chunks],
        embeddings=[e.tolist() for e in embeddings],
        documents=texts,
        metadatas=[
            {
                "source": c["source"],
                "chunk_id": c["id"],
                "citation": c["citation"],
                "url": c["url"],
                "page": c["page"] if c["page"] is not None else -1,
            }
            for c in all_chunks
        ],
    )

    print(f"Done. {collection.count()} chunks in collection '{config.COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
