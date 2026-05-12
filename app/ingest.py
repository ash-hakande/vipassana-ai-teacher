"""
Run once before starting the server (re-run after adding new documents):
    poetry run python -m app.ingest
"""
import os
import sys
from pathlib import Path
from typing import List

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import config


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, source: str, chunk_size: int, overlap: int) -> List[dict]:
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            stem = Path(source).stem
            chunks.append({
                "id": f"{stem}_{idx:04d}",
                "text": chunk,
                "source": source,
            })
            idx += 1
        start += chunk_size - overlap
    return chunks


def main():
    docs_dir = Path(config.DOCUMENTS_DIR)
    if not docs_dir.exists():
        print(f"Documents directory not found: {docs_dir}")
        sys.exit(1)

    files = list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.txt"))
    if not files:
        print(f"No .pdf or .txt files found in {docs_dir}")
        sys.exit(0)

    print(f"Found {len(files)} document(s). Loading and chunking...")

    all_chunks: List[dict] = []
    for f in files:
        text = load_text(f)
        chunks = chunk_text(text, f.name, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        print(f"  {f.name}: {len(chunks)} chunks")
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
    collection = client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(
        ids=[c["id"] for c in all_chunks],
        embeddings=[e.tolist() for e in embeddings],
        documents=texts,
        metadatas=[{"source": c["source"], "chunk_id": c["id"]} for c in all_chunks],
    )

    print(f"Done. {collection.count()} chunks now in collection '{config.COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
