from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_workspace
from app.api.documents import used_bytes
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Conversation, Document, Message, User, Workspace
from app.schemas import SearchIn, SearchOut, SearchResult
from app.services import retrieval
from app.services.embedding import get_embedder

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchOut, summary="Recherche sémantique : passages retrouvés")
def search(body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = owned_workspace(db, user, body.workspace_id)
    ready = set(db.execute(select(Document.id).where(Document.workspace_id == ws.id, Document.status == "ready")).scalars())
    if body.document_ids:
        if set(body.document_ids) - ready:
            raise AppError(403, "Un ou plusieurs documents sélectionnés sont inaccessibles.", "document_not_allowed")
        ids = list(body.document_ids)
    else:
        ids = list(ready)
    hits, m = retrieval.search(db, body.query, ws.id, ids, top_k=body.top_k)
    return SearchOut(search_ms=m["search_ms"], results=[
        SearchResult(chunk_id=h.chunk_id, document_id=h.document_id, filename=h.filename, page=h.page,
                     section=h.section, text=h.text, score=round(h.score, 5),
                     similarity=round(h.similarity, 4) if h.similarity is not None else None) for h in hits])


@router.get("/stats", summary="Tableau de bord : compteurs, stockage, configuration serveur")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = get_settings()
    ws_ids = select(Workspace.id).where(Workspace.user_id == user.id)
    conv_ids = select(Conversation.id).where(Conversation.workspace_id.in_(ws_ids))
    by_status = dict(db.execute(select(Document.status, func.count()).where(Document.workspace_id.in_(ws_ids))
                                .group_by(Document.status)).all())
    answers = dict(db.execute(select(Message.status, func.count())
                              .where(Message.conversation_id.in_(conv_ids), Message.role == "assistant")
                              .group_by(Message.status)).all())
    total_answers = sum(answers.values())
    return {
        "workspaces": db.scalar(select(func.count()).select_from(Workspace).where(Workspace.user_id == user.id)),
        "documents": sum(by_status.values()),
        "documents_by_status": by_status,
        "conversations": db.scalar(select(func.count()).select_from(Conversation)
                                   .where(Conversation.workspace_id.in_(ws_ids))),
        "questions": total_answers,
        "abstention_rate": round(answers.get("no_answer", 0) / total_answers, 3) if total_answers else 0,
        "storage_used": used_bytes(db, user.id),
        "storage_quota": s.storage_quota_mb * 1024 * 1024,
        "config": {
            "gemini_model": s.gemini_model,
            "gemini_configured": bool(s.gemini_api_key),
            "embedding_version": get_embedder().version,
            "hybrid_search": s.hybrid_search,
            "reranker": s.reranker_model or None,
            "max_upload_mb": s.max_upload_mb,
            "top_k": s.top_k,
            "chunk_size": s.chunk_size,
            "rate_limit_chat_per_min": s.rate_limit_chat_per_min,
        },
    }
