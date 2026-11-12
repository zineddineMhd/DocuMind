"""Recherche hybride : vecteurs (ChromaDB) + BM25, fusion RRF, reranking optionnel, déduplication.

Les permissions sont vérifiées en base AVANT l'appel (cf. api/deps) ; ce module ne reçoit que des
identifiants de documents déjà autorisés et applique en plus le filtre vectoriel espace/documents.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentChunk
from app.services import vectorstore
from app.services.embedding import get_embedder

_STOP = set(
    "le la les l un une des du de d et ou a au aux en dans sur pour par avec sans ce cet cette ces que qui quoi dont "
    "ou est sont etre ete il elle ils elles on nous vous je tu se sa son ses leur leurs ne pas plus y the of and to in "
    "is are a an for on with by as at it this that be what which how quel quelle quels quelles comment".split()
)


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    section: str | None
    ordinal: int
    text: str
    score: float
    similarity: float | None = None


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in _STOP and len(t) > 1]


# --- cache BM25 par document (invalidé à la réindexation / suppression) -----------------------
_tok_cache: dict[str, list[tuple[str, list[str]]]] = {}
_tok_lock = threading.Lock()


def invalidate(document_id: str) -> None:
    with _tok_lock:
        _tok_cache.pop(document_id, None)


def _doc_tokens(db: Session, document_id: str) -> list[tuple[str, list[str]]]:
    with _tok_lock:
        cached = _tok_cache.get(document_id)
    if cached is None:
        rows = db.execute(
            select(DocumentChunk.id, DocumentChunk.text).where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.ordinal)
        ).all()
        cached = [(cid, tokenize(text)) for cid, text in rows]
        with _tok_lock:
            _tok_cache[document_id] = cached
    return cached


def _bm25(db: Session, query: str, document_ids: list[str], n: int) -> list[tuple[str, float]]:
    q = tokenize(query)
    if not q:
        return []
    ids: list[str] = []
    corpus: list[list[str]] = []
    for d in document_ids:
        for cid, toks in _doc_tokens(db, d):
            ids.append(cid)
            corpus.append(toks or ["_"])
    if not corpus:
        return []
    scores = BM25Okapi(corpus).get_scores(q)
    order = sorted(range(len(ids)), key=lambda i: -scores[i])[:n]
    return [(ids[i], float(scores[i])) for i in order if scores[i] > 0]


_reranker = None


def _rerank(query: str, hits: list[Hit]) -> list[Hit]:
    global _reranker
    name = get_settings().reranker_model
    if not name or len(hits) < 2:
        return hits
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(name, device="cpu", max_length=512)
    scores = _reranker.predict([(query, h.text) for h in hits], show_progress_bar=False)
    for h, s in zip(hits, scores):
        h.score = float(s)
    return sorted(hits, key=lambda h: -h.score)


def _load_hits(db: Session, scored: dict[str, float], sims: dict[str, float]) -> list[Hit]:
    if not scored:
        return []
    rows = db.execute(
        select(DocumentChunk, Document.filename).join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(list(scored)))
    ).all()
    hits = [
        Hit(chunk_id=c.id, document_id=c.document_id, filename=fn, page=c.page, section=c.section,
            ordinal=c.ordinal, text=c.text, score=scored[c.id], similarity=sims.get(c.id))
        for c, fn in rows
    ]
    return sorted(hits, key=lambda h: -h.score)


def _dedupe(hits: list[Hit], limit: int) -> list[Hit]:
    kept: list[Hit] = []
    seen: list[set[str]] = []
    for h in hits:
        toks = set(tokenize(h.text))
        if any(len(toks & s) / max(1, len(toks | s)) > 0.8 for s in seen):
            continue
        kept.append(h)
        seen.append(toks)
        if len(kept) >= limit:
            break
    return kept


def search(db: Session, query: str, workspace_id: str, document_ids: list[str], top_k: int | None = None,
           per_document: bool = False) -> tuple[list[Hit], dict]:
    """Recherche hybride. `per_document=True` garantit des extraits de chaque document (comparaisons)."""
    s = get_settings()
    top_k = top_k or s.top_k
    t0 = time.perf_counter()
    if not document_ids:
        return [], {"search_ms": 0, "candidates": 0}
    qvec = get_embedder().embed_query(query)

    def fused(doc_ids: list[str], n: int) -> tuple[dict[str, float], dict[str, float]]:
        vec = [(c, sim) for c, sim in vectorstore.query(qvec, workspace_id, doc_ids, n) if sim >= s.min_similarity]
        sims = dict(vec)
        scores: dict[str, float] = {}
        for rank, (cid, _) in enumerate(vec):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (60 + rank)
        if s.hybrid_search:
            for rank, (cid, _) in enumerate(_bm25(db, query, doc_ids, n)):
                scores[cid] = scores.get(cid, 0.0) + 0.7 / (60 + rank)
        return scores, sims

    if per_document and len(document_ids) > 1:
        per = max(2, (top_k + 2) // len(document_ids))
        groups = []
        for d in document_ids:
            sc, sm = fused([d], s.retrieval_candidates)
            groups.append(_dedupe(_rerank(query, _load_hits(db, sc, sm)), per))
        hits = [h for i in range(per) for g in groups if i < len(g) for h in [g[i]]]
        n_cand = sum(len(g) for g in groups)
    else:
        sc, sm = fused(document_ids, s.retrieval_candidates)
        cands = _rerank(query, _load_hits(db, sc, sm))
        n_cand = len(cands)
        hits = _dedupe(cands, top_k)
        # couverture multi-documents : meilleur extrait de chaque document sélectionné non représenté
        if 1 < len(document_ids) <= 6:
            present = {h.document_id for h in hits}
            for h in cands:
                if h.document_id not in present and len(hits) < top_k + 2:
                    hits.append(h)
                    present.add(h.document_id)
    return hits, {"search_ms": round((time.perf_counter() - t0) * 1000), "candidates": n_cand}


def coverage(db: Session, document_ids: list[str], budget: int = 24) -> list[Hit]:
    """Échantillonne des chunks répartis uniformément dans chaque document (résumés de corpus)."""
    hits: list[Hit] = []
    if not document_ids:
        return hits
    per = max(3, budget // len(document_ids))
    for d in document_ids:
        rows = db.execute(
            select(DocumentChunk, Document.filename).join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.document_id == d).order_by(DocumentChunk.ordinal)
        ).all()
        if not rows:
            continue
        if len(rows) > per:
            step = (len(rows) - 1) / (per - 1)
            rows = [rows[round(i * step)] for i in range(per)]
        hits += [Hit(chunk_id=c.id, document_id=c.document_id, filename=fn, page=c.page, section=c.section,
                     ordinal=c.ordinal, text=c.text, score=0.0) for c, fn in rows]
    return hits
