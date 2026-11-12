"""Embeddings : modèle local Sentence Transformers (défaut), Gemini Embeddings, ou hachage (tests).

Le même modèle sert à l'indexation et à la requête ; `version` identifie modèle + dimension et
détermine la collection ChromaDB (on ne mélange jamais des vecteurs de modèles différents).
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core.config import get_settings


class Embedder(Protocol):
    version: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class LocalEmbedder:
    """Sentence Transformers. Les modèles de la famille E5 utilisent les préfixes query:/passage:."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")
        self.model.max_seq_length = 512
        self._lock = threading.Lock()
        label = Path(model_name).name if Path(model_name).exists() else model_name.replace("/", "_")
        self.e5 = "e5" in label.lower()
        self.version = f"{label}-{self.model.get_sentence_embedding_dimension()}"

    def _encode(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            vecs = self.model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([("passage: " + t) if self.e5 else t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([("query: " + text) if self.e5 else text])[0]


class GeminiEmbedder:
    def __init__(self, model: str, dim: int = 768):
        from google import genai

        self.client = genai.Client(api_key=get_settings().gemini_api_key)
        self.model, self.dim = model, dim
        self.version = f"{model}-{dim}"

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        from google.genai import types

        out: list[list[float]] = []
        for i in range(0, len(texts), 50):
            resp = self.client.models.embed_content(
                model=self.model, contents=texts[i:i + 50],
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=self.dim),
            )
            for e in resp.embeddings:
                v = np.asarray(e.values, dtype=np.float32)
                out.append((v / (np.linalg.norm(v) or 1.0)).tolist())
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


class HashEmbedder:
    """Sac de mots haché, déterministe et sans modèle : réservé aux tests automatiques."""

    version = "hash-256"

    def _one(self, text: str) -> list[float]:
        v = np.zeros(256, dtype=np.float32)
        for tok in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 256] += 1.0
        return (v / (np.linalg.norm(v) or 1.0)).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._one(text)


_embedder: Embedder | None = None
_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                s = get_settings()
                if s.embedding_backend == "hash":
                    _embedder = HashEmbedder()
                elif s.embedding_backend == "gemini":
                    _embedder = GeminiEmbedder(s.gemini_embedding_model)
                else:
                    _embedder = LocalEmbedder(s.resolved_embedding_model)
    return _embedder
