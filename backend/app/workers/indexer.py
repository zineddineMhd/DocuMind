"""Worker d'indexation : file en mémoire + thread, suivi dans indexing_jobs, reprise au démarrage.

Idempotent : les IDs de chunks sont déterministes (<document_id>:<ordinal>) et tout l'existant du
document est purgé avant réindexation -> pas de doublons après un échec partiel.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentChunk, IndexingJob, Workspace
from app.services import retrieval, vectorstore
from app.services.chunk import chunk_document
from app.services.embedding import get_embedder
from app.services.extract import ExtractionError, extract

log = logging.getLogger("documind.indexer")
_queue: "queue.Queue[str]" = queue.Queue()
_thread: threading.Thread | None = None


def purge_vectors(document_id: str) -> None:
    vectorstore.delete_document(document_id)
    retrieval.invalidate(document_id)


def index_document(document_id: str) -> None:
    """Extraction -> chunks -> embeddings -> ChromaDB ; met à jour statuts et métriques."""
    s = get_settings()
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        ws = db.get(Workspace, doc.workspace_id)
        attempt = (db.execute(select(IndexingJob.attempt).where(IndexingJob.document_id == document_id)
                              .order_by(IndexingJob.attempt.desc())).scalars().first() or 0) + 1
        job = IndexingJob(document_id=document_id, state="running", attempt=attempt,
                          started_at=datetime.now(timezone.utc))
        db.add(job)
        doc.status, doc.error = "processing", None
        db.commit()
        t0 = time.perf_counter()
        try:
            data = Path(doc.storage_path).read_bytes()
            extracted = extract(doc.filename, data)
            t_extract = time.perf_counter()
            chunks = chunk_document(extracted, s.chunk_size, s.chunk_overlap)
            if not chunks:
                raise ExtractionError("Aucun contenu exploitable dans ce document.")
            embedder = get_embedder()
            vectors = embedder.embed_documents(
                [(f"{c.section}\n{c.text}" if c.section and not c.text.startswith(c.section) else c.text)
                 for c in chunks])
            t_embed = time.perf_counter()

            # purge préalable (SQL + vecteurs) puis insertion
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            purge_vectors(document_id)
            ids = [f"{document_id}:{c.ordinal}" for c in chunks]
            db.add_all(DocumentChunk(id=i, document_id=document_id, page=c.page, section=c.section,
                                     ordinal=c.ordinal, text=c.text, vector_id=i,
                                     embedding_version=embedder.version) for i, c in zip(ids, chunks))
            db.flush()
            vectorstore.upsert(
                ids, vectors,
                [{"chunk_id": i, "document_id": document_id, "workspace_id": doc.workspace_id,
                  "user_id": ws.user_id, "page": c.page or 0, "ordinal": c.ordinal,
                  "embedding_version": embedder.version} for i, c in zip(ids, chunks)],
                [c.text for c in chunks],
            )
            doc.page_count = extracted.page_count
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            job.state = "done"
            job.metrics = {"extract_ms": round((t_extract - t0) * 1000), "embed_ms": round((t_embed - t_extract) * 1000),
                           "total_ms": round((time.perf_counter() - t0) * 1000), "chunks": len(chunks),
                           "chars": extracted.char_count}
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            log.info("Document %s indexé : %s chunks en %s ms", document_id, len(chunks), job.metrics["total_ms"])
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            message = str(exc) if isinstance(exc, ExtractionError) else "Erreur technique pendant l'indexation."
            if not isinstance(exc, ExtractionError):
                log.exception("Échec d'indexation du document %s", document_id)
            try:
                purge_vectors(document_id)
            except Exception:  # noqa: BLE001
                log.exception("Purge vectorielle impossible pour %s", document_id)
            doc = db.get(Document, document_id)
            if doc is not None:
                db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
                doc.status, doc.error, doc.chunk_count = "failed", message, 0
                job = db.get(IndexingJob, job.id)
                if job is not None:
                    job.state, job.error, job.finished_at = "failed", message, datetime.now(timezone.utc)
                db.commit()


def _run() -> None:
    while True:
        document_id = _queue.get()
        try:
            index_document(document_id)
        except Exception:  # noqa: BLE001
            log.exception("Erreur inattendue du worker")
        finally:
            _queue.task_done()


def start() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_run, name="documind-indexer", daemon=True)
        _thread.start()


def enqueue(document_id: str) -> None:
    if get_settings().indexing_sync:
        index_document(document_id)
    else:
        start()
        _queue.put(document_id)


def resume_pending() -> int:
    """Au démarrage : remet en file les documents restés en pending/processing (arrêt brutal)."""
    with SessionLocal() as db:
        ids = db.execute(select(Document.id).where(Document.status.in_(("pending", "processing")))).scalars().all()
    for i in ids:
        enqueue(i)
    return len(ids)
