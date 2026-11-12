from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_conversation, owned_workspace
from app.core import ratelimit
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal, get_db
from app.models import Document, User
from app.schemas import ChatIn, ChatOut
from app.services import rag

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _prepare(db: Session, user: User, body: ChatIn):
    """Contrôles d'accès en base : espace, conversation et documents sélectionnés (prêts uniquement)."""
    ratelimit.check(f"chat:{user.id}", get_settings().rate_limit_chat_per_min)
    ws = owned_workspace(db, user, body.workspace_id)
    conv = None
    if body.conversation_id:
        conv = owned_conversation(db, user, body.conversation_id)
        if conv.workspace_id != ws.id:
            raise AppError(404, "Conversation introuvable.")
    ready = db.execute(select(Document.id).where(Document.workspace_id == ws.id, Document.status == "ready")).scalars().all()
    if body.document_ids:
        unknown = set(body.document_ids) - set(ready)
        if unknown:
            raise AppError(403, "Un ou plusieurs documents sélectionnés sont inaccessibles ou non indexés.",
                           "document_not_allowed")
        doc_ids = list(dict.fromkeys(body.document_ids))
    else:
        doc_ids = list(ready)
    if not doc_ids:
        raise AppError(400, "Aucun document prêt dans cet espace. Importez un document et attendez son indexation.",
                       "no_ready_document")
    return ws, conv, doc_ids


@router.post("", response_model=ChatOut, summary="Question RAG (réponse complète)")
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws, conv, doc_ids = _prepare(db, user, body)
    final = None
    for ev in rag.chat_events(db, ws.id, conv, body.question.strip(), doc_ids, body.mode):
        if ev["type"] == "final":
            final = ev
    return ChatOut(**{k: v for k, v in final.items() if k != "type"})


@router.post("/stream", summary="Question RAG en streaming (Server-Sent Events)")
def chat_stream(body: ChatIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws, conv, doc_ids = _prepare(db, user, body)
    ws_id, conv_id, rid = ws.id, (conv.id if conv else None), request.state.request_id

    def gen():
        from app.models import Conversation

        with SessionLocal() as sdb:  # session propre au flux (la dépendance peut être fermée avant la fin)
            try:
                c = sdb.get(Conversation, conv_id) if conv_id else None
                for ev in rag.chat_events(sdb, ws_id, c, body.question.strip(), doc_ids, body.mode):
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except AppError as exc:
                err = {"type": "error", "status": exc.status, "code": exc.code, "message": exc.message, "request_id": rid}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
            except Exception:  # noqa: BLE001
                err = {"type": "error", "status": 500, "code": "internal_error",
                       "message": "Erreur interne du serveur.", "request_id": rid}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
