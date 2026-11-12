from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_workspace
from app.db.session import get_db
from app.models import Conversation, Document, User, Workspace
from app.schemas import WorkspaceIn, WorkspaceOut
from app.workers import indexer

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _out(db: Session, ws: Workspace) -> WorkspaceOut:
    out = WorkspaceOut.model_validate(ws)
    out.document_count = db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == ws.id))
    out.conversation_count = db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.workspace_id == ws.id))
    return out


@router.get("", response_model=list[WorkspaceOut], summary="Lister ses espaces")
def list_workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Workspace).where(Workspace.user_id == user.id).order_by(Workspace.created_at)).scalars()
    return [_out(db, w) for w in rows]


@router.post("", response_model=WorkspaceOut, status_code=201, summary="Créer un espace")
def create_workspace(body: WorkspaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = Workspace(user_id=user.id, name=body.name.strip())
    db.add(ws)
    db.commit()
    return _out(db, ws)


@router.patch("/{workspace_id}", response_model=WorkspaceOut, summary="Renommer un espace")
def rename_workspace(workspace_id: str, body: WorkspaceIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    ws = owned_workspace(db, user, workspace_id)
    ws.name = body.name.strip()
    db.commit()
    return _out(db, ws)


@router.delete("/{workspace_id}", status_code=204, summary="Supprimer un espace et son contenu")
def delete_workspace(workspace_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = owned_workspace(db, user, workspace_id)
    for d in ws.documents:
        indexer.purge_vectors(d.id)
        Path(d.storage_path).unlink(missing_ok=True)
    db.delete(ws)
    db.commit()
    return Response(status_code=204)
