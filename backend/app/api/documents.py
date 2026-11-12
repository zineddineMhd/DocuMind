from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_document, owned_workspace
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Document, DocumentChunk, User, Workspace
from app.schemas import ChunkOut, DocumentOut, SummaryOut, UploadOut
from app.services import rag
from app.services.extract import extension, sniff
from app.workers import indexer

router = APIRouter(prefix="/api/documents", tags=["documents"])


def used_bytes(db: Session, user_id: str) -> int:
    return db.scalar(select(func.coalesce(func.sum(Document.file_size), 0)).join(Workspace)
                     .where(Workspace.user_id == user_id)) or 0


@router.post("/upload", response_model=UploadOut, status_code=202, summary="Envoyer un ou plusieurs fichiers")
async def upload(workspace_id: str = Form(...), files: list[UploadFile] = File(...),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = get_settings()
    ws = owned_workspace(db, user, workspace_id)
    max_bytes = s.max_upload_mb * 1024 * 1024
    quota = s.storage_quota_mb * 1024 * 1024
    used = used_bytes(db, user.id)
    accepted: list[Document] = []
    rejected: list[dict] = []
    errors: list[AppError] = []

    for f in files:
        name = Path(f.filename or "document").name[:255]
        data = await f.read(max_bytes + 1)
        err: AppError | None = None
        if len(data) > max_bytes:
            err = AppError(413, f"« {name} » dépasse la limite de {s.max_upload_mb} Mo.")
        elif len(data) == 0:
            err = AppError(400, f"« {name} » est vide.", "empty_file")
        elif used + len(data) > quota:
            err = AppError(413, "Espace de stockage insuffisant.", "quota_exceeded")
        else:
            try:
                mime = sniff(name, data)
            except ValueError as e:
                err = AppError(415, f"« {name} » : {e}")
        if err:
            errors.append(err)
            rejected.append({"filename": name, "code": err.code, "message": err.message})
            continue
        sha = hashlib.sha256(data).hexdigest()
        dup = db.execute(select(Document).where(Document.workspace_id == ws.id, Document.sha256 == sha)).scalars().first()
        if dup:
            rejected.append({"filename": name, "code": "duplicate",
                             "message": f"« {name} » est déjà présent dans cet espace ({dup.filename})."})
            continue
        doc_id = str(uuid.uuid4())
        folder = Path(s.upload_dir) / user.id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{doc_id}{extension(name)}"  # nom serveur : jamais le nom fourni par le client
        path.write_bytes(data)
        doc = Document(id=doc_id, workspace_id=ws.id, filename=name, content_type=mime, storage_path=str(path),
                       file_size=len(data), sha256=sha, status="pending")
        db.add(doc)
        db.commit()
        used += len(data)
        accepted.append(doc)

    if not accepted and len(files) == 1 and errors:
        raise errors[0]
    if not accepted and errors:
        raise AppError(errors[0].status, "Aucun fichier accepté : " + " ".join(e.message for e in errors), errors[0].code)
    for doc in accepted:
        indexer.enqueue(doc.id)
    for doc in accepted:
        db.refresh(doc)
    return UploadOut(documents=[DocumentOut.model_validate(d) for d in accepted], rejected=rejected)


@router.get("", response_model=list[DocumentOut], summary="Lister les documents d'un espace")
def list_documents(workspace_id: str = Query(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = owned_workspace(db, user, workspace_id)
    return db.execute(select(Document).where(Document.workspace_id == ws.id)
                      .order_by(Document.created_at.desc())).scalars().all()


@router.get("/{document_id}", response_model=DocumentOut, summary="État et métadonnées")
def get_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return owned_document(db, user, document_id)


@router.get("/{document_id}/file", summary="Télécharger le fichier original")
def get_file(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    if not Path(doc.storage_path).exists():
        raise AppError(404, "Fichier introuvable.")
    return FileResponse(doc.storage_path, media_type=doc.content_type, filename=doc.filename,
                        content_disposition_type="inline")


@router.get("/{document_id}/chunks", response_model=list[ChunkOut], summary="Passages indexés (lecteur de sources)")
def get_chunks(document_id: str, page: int | None = None, around: str | None = None,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    q = select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.ordinal)
    if page is not None:
        q = q.where(DocumentChunk.page == page)
    if around:
        center = db.get(DocumentChunk, around)
        if center is not None and center.document_id == doc.id:
            q = q.where(DocumentChunk.ordinal.between(center.ordinal - 2, center.ordinal + 2))
    return db.execute(q.limit(400)).scalars().all()


@router.delete("/{document_id}", status_code=204, summary="Supprimer et purger (fichier, chunks, vecteurs)")
def delete_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    indexer.purge_vectors(doc.id)
    Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return Response(status_code=204)


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=202, summary="Relancer l'indexation")
def reindex(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    if doc.status == "processing":
        raise AppError(409, "Indexation déjà en cours.")
    doc.status, doc.error = "pending", None
    db.commit()
    indexer.enqueue(doc.id)
    db.refresh(doc)
    return doc


@router.post("/{document_id}/summary", response_model=SummaryOut, summary="Résumé Gemini du document")
def summary(document_id: str, refresh: bool = False, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    if doc.status != "ready":
        raise AppError(409, "Le document n'est pas encore indexé.", "document_not_ready")
    if doc.summary and not refresh:
        return SummaryOut(document_id=doc.id, summary=doc.summary, keywords=doc.keywords or [])
    out = rag.summarize_document(db, doc)
    return SummaryOut(**{k: out[k] for k in ("document_id", "summary", "keywords", "truncated")})
