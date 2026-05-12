from typing import List

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import config


def _format_chunks(results: dict) -> List[dict]:
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "chunk_id": meta.get("chunk_id", ""),
            "distance": dist,
        })
    return chunks


class RetrieverAgent:
    def __init__(self):
        self._model = SentenceTransformer(config.EMBEDDING_MODEL)
        self._client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
        self._collection = self._client.get_or_create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def retrieve(self, query: str, top_k: int = config.TOP_K_CHUNKS) -> List[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        n = min(top_k, count)
        embedding = self._model.encode([query])[0].tolist()
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        return _format_chunks(results)
