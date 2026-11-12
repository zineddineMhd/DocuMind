from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, owned_conversation, owned_message, owned_workspace
from app.db.session import get_db
from app.models import Conversation, Message, User
from app.schemas import (ConversationDetail, ConversationOut, ConversationPatch, FeedbackIn, MessageOut, SourceOut)

router = APIRouter(prefix="/api", tags=["conversations"])


def _message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id, role=m.role, content=m.content, status=m.status, feedback=m.feedback, metrics=m.metrics,
        created_at=m.created_at,
        sources=[SourceOut(source_id=s.source_label, document_id=s.document_id, filename=s.filename, page=s.page,
                           chunk_id=s.chunk_id, excerpt=s.excerpt, available=s.document_id is not None)
                 for s in m.sources],
    )


@router.get("/conversations", response_model=list[ConversationOut], summary="Historique d'un espace")
def list_conversations(workspace_id: str = Query(...), user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    ws = owned_workspace(db, user, workspace_id)
    rows = db.execute(
        select(Conversation, func.count(Message.id)).outerjoin(Message)
        .where(Conversation.workspace_id == ws.id).group_by(Conversation.id).order_by(Conversation.updated_at.desc())
    ).all()
    out = []
    for conv, n in rows:
        o = ConversationOut.model_validate(conv)
        o.message_count = n
        out.append(o)
    return out


def _load(db: Session, conversation_id: str) -> Conversation:
    return db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages).selectinload(Message.sources))
    ).scalar_one()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail, summary="Messages et sources")
def get_conversation(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _load(db, owned_conversation(db, user, conversation_id).id)
    return ConversationDetail(id=conv.id, workspace_id=conv.workspace_id, title=conv.title, created_at=conv.created_at,
                              updated_at=conv.updated_at, message_count=len(conv.messages),
                              messages=[_message_out(m) for m in conv.messages])


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut, summary="Renommer")
def rename_conversation(conversation_id: str, body: ConversationPatch, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    conv = owned_conversation(db, user, conversation_id)
    conv.title = body.title.strip()
    db.commit()
    return conv


@router.delete("/conversations/{conversation_id}", status_code=204, summary="Supprimer")
def delete_conversation(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_conversation(db, user, conversation_id))
    db.commit()
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}/export", response_class=PlainTextResponse,
            summary="Exporter en Markdown")
def export_conversation(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _load(db, owned_conversation(db, user, conversation_id).id)
    lines = [f"# {conv.title}", "", f"_Exporté depuis DocuMind — {conv.created_at:%d/%m/%Y}_", ""]
    for m in conv.messages:
        lines += [f"## {'Question' if m.role == 'user' else 'DocuMind'}", "", m.content, ""]
        if m.sources:
            lines.append("**Sources :**")
            for s in m.sources:
                page = f", p. {s.page}" if s.page else ""
                lines.append(f"- [{s.source_label}] {s.filename}{page} — « {s.excerpt[:200]} »")
            lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="conversation-{conv.id[:8]}.md"'})


@router.post("/messages/{message_id}/feedback", status_code=204, summary="Pouce haut / bas sur une réponse")
def feedback(message_id: str, body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    msg = owned_message(db, user, message_id)
    msg.feedback = body.value or None
    db.commit()
    return Response(status_code=204)
