"""ChromaDB persistant : une collection par version d'embedding, filtres stricts espace/documents."""
from __future__ import annotations

import re
import threading

import chromadb

from app.core.config import get_settings
from app.services.embedding import get_embedder

_client = None
_lock = threading.Lock()


def _collection():
    global _client
    with _lock:
        if _client is None:
            _client = chromadb.PersistentClient(path=get_settings().chroma_path)
    name = "chunks_" + re.sub(r"[^a-zA-Z0-9_-]", "_", get_embedder().version)[-50:].strip("_-")
    return _client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def upsert(ids: list[str], embeddings: list[list[float]], metadatas: list[dict], documents: list[str]) -> None:
    col = _collection()
    for i in range(0, len(ids), 500):
        col.upsert(ids=ids[i:i + 500], embeddings=embeddings[i:i + 500],
                   metadatas=metadatas[i:i + 500], documents=documents[i:i + 500])


def delete_document(document_id: str) -> None:
    _collection().delete(where={"document_id": document_id})


def count_document(document_id: str) -> int:
    return len(_collection().get(where={"document_id": document_id}, include=[])["ids"])


def query(embedding: list[float], workspace_id: str, document_ids: list[str], n: int) -> list[tuple[str, float]]:
    """Retourne [(chunk_id, similarité cosinus)]. Le filtre est toujours appliqué côté serveur."""
    if not document_ids:
        return []
    where = {"$and": [{"workspace_id": workspace_id}, {"document_id": {"$in": list(document_ids)}}]}
    res = _collection().query(query_embeddings=[embedding], n_results=n, where=where, include=["distances"])
    return [(cid, 1.0 - float(d)) for cid, d in zip(res["ids"][0], res["distances"][0])]
