"""Dépendances : authentification et contrôle d'appartenance (toujours vérifié en base)."""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Conversation, Document, Message, User, Workspace

_bearer = HTTPBearer(auto_error=False)


def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                 db: Session = Depends(get_db)) -> User:
    token = creds.credentials if creds else None
    user_id = decode_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise AppError(401, "Authentification requise.")
    return user


def owned_workspace(db: Session, user: User, workspace_id: str) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None or ws.user_id != user.id:
        raise AppError(404, "Espace introuvable.")  # 404 : on ne révèle pas l'existence
    return ws


def owned_document(db: Session, user: User, document_id: str) -> Document:
    doc = db.execute(
        select(Document).join(Workspace).where(Document.id == document_id, Workspace.user_id == user.id)
    ).scalar_one_or_none()
    if doc is None:
        raise AppError(404, "Document introuvable.")
    return doc


def owned_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    conv = db.execute(
        select(Conversation).join(Workspace).where(Conversation.id == conversation_id, Workspace.user_id == user.id)
    ).scalar_one_or_none()
    if conv is None:
        raise AppError(404, "Conversation introuvable.")
    return conv


def owned_message(db: Session, user: User, message_id: str) -> Message:
    msg = db.execute(
        select(Message).join(Conversation).join(Workspace)
        .where(Message.id == message_id, Workspace.user_id == user.id)
    ).scalar_one_or_none()
    if msg is None:
        raise AppError(404, "Message introuvable.")
    return msg
