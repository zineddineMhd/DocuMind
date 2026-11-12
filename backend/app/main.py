"""DocuMind — API FastAPI. Documentation interactive : /docs."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import auth, chat, conversations, documents, search, workspaces
from app.core import errors
from app.core.config import BACKEND_DIR, get_settings
from app.db.session import Base, engine
from app.services.embedding import get_embedder
from app.workers import indexer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("documind")


def init_db() -> None:
    """Applique les migrations Alembic ; à défaut (tests), crée le schéma directement."""
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "db" / "migrations"))
        command.upgrade(cfg, "head")
    except Exception:  # noqa: BLE001
        log.exception("Migrations Alembic indisponibles : création directe du schéma")
        Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    init_db()
    if not s.indexing_sync:
        indexer.start()
        # préchargement du modèle d'embeddings hors du chemin critique des requêtes
        threading.Thread(target=get_embedder, name="embedder-warmup", daemon=True).start()
        n = indexer.resume_pending()
        if n:
            log.info("%s document(s) remis en file d'indexation", n)
    if s.environment != "development" and s.jwt_secret.startswith("dev-secret"):
        log.warning("JWT_SECRET par défaut : définissez une valeur aléatoire en production.")
    yield


app = FastAPI(title="DocuMind API", version="1.0.0", lifespan=lifespan,
              description="Assistant IA pour documents : RAG avec citations vérifiées (Gemini + ChromaDB).")
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "Content-Disposition"])

for r in (auth.router, workspaces.router, documents.router, chat.router, conversations.router, search.router):
    app.include_router(r)


@app.get("/health", tags=["système"], summary="Sonde de santé")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "gemini_configured": bool(get_settings().gemini_api_key)}


# En production « tout-en-un » : sert le frontend compilé (frontend/dist) s'il existe.
_dist = BACKEND_DIR.parent / "frontend" / "dist"
if (_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "health")):
            raise errors.AppError(404, "Ressource introuvable.")
        f = (_dist / path).resolve()
        if path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
