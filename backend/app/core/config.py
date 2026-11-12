"""Configuration centralisée (variables d'environnement / fichier .env à la racine du dépôt)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
FINETUNED_MODEL_DIR = BACKEND_DIR / "models" / "documind-e5-small-ft"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "DocuMind"
    environment: str = "development"

    # --- Gemini (Google AI Studio) : utilisé uniquement côté serveur ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3.5-flash-lite"  # essayés si le principal est indisponible
    gemini_timeout_s: int = 40
    gemini_max_retries: int = 2
    gemini_max_output_tokens: int = 4096
    gemini_thinking_budget: int | None = None  # 0 = désactive la « réflexion » (plus rapide) sur 2.5-flash

    # --- Stockage ---
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'documind.db').as_posix()}"
    chroma_path: str = str(BACKEND_DIR / "data" / "chroma")
    upload_dir: str = str(BACKEND_DIR / "data" / "uploads")

    # --- Sécurité ---
    jwt_secret: str = "dev-secret-a-changer-en-production-0123456789"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_chat_per_min: int = 20
    rate_limit_auth_per_min: int = 15

    # --- Documents ---
    max_upload_mb: int = 20
    storage_quota_mb: int = 1024

    # --- RAG ---
    embedding_backend: str = "local"  # local | gemini | hash (tests)
    embedding_model: str = ""  # vide = modèle affiné s'il existe, sinon intfloat/multilingual-e5-small
    gemini_embedding_model: str = "gemini-embedding-001"
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 6
    retrieval_candidates: int = 24
    hybrid_search: bool = True
    reranker_model: str = ""  # ex. cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (optionnel, plus lent)
    min_similarity: float = 0.0  # seuil cosinus en dessous duquel un extrait est ignoré
    indexing_sync: bool = False  # True = indexation dans la requête (tests)
    indexing_max_attempts: int = 3

    @field_validator("gemini_thinking_budget", mode="before")
    @classmethod
    def _empty_none(cls, v):
        return None if v in ("", None) else v

    @property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model:
            return self.embedding_model
        if (FINETUNED_MODEL_DIR / "config.json").exists():
            return str(FINETUNED_MODEL_DIR)
        return "intfloat/multilingual-e5-small"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    Path(s.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(s.chroma_path).mkdir(parents=True, exist_ok=True)
    if s.database_url.startswith("sqlite:///"):
        Path(s.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return s
