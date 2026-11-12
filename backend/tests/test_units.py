"""Tests unitaires : découpage, nettoyage, vérification des citations."""
from __future__ import annotations

import pytest

from app.services.chunk import chunk_document, split_text
from app.services.extract import Extracted, ExtractionError, Segment, clean_text, extract, sniff
from app.services.rag import build_context, verify_citations
from app.services.retrieval import Hit, tokenize


def test_split_respects_size_and_overlap():
    text = " ".join(f"Phrase numéro {i} qui parle du protocole réseau." for i in range(120))
    chunks = split_text(text, size=900, overlap=150)
    assert len(chunks) > 4
    assert all(len(c) <= 900 + 150 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        assert a[-40:] in b or b[:40] in a  # recouvrement entre chunks consécutifs
    assert "Phrase numéro 0 " in chunks[0] and "Phrase numéro 119 " in chunks[-1]


def test_split_long_text_without_punctuation():
    chunks = split_text("mot " * 2000, size=500, overlap=50)
    assert all(len(c) <= 560 for c in chunks) and len(chunks) >= 15


def test_chunks_keep_page_and_ordinal():
    ex = Extracted(segments=[Segment("Texte de la page un.", page=1), Segment("Texte de la page deux.", page=2)], page_count=2)
    chunks = chunk_document(ex)
    assert [(c.ordinal, c.page) for c in chunks] == [(0, 1), (1, 2)]


def test_clean_text_and_txt_encodings():
    assert clean_text("infor-\nmation  utile\n\n\n\nsuite") == "information utile\n\nsuite"
    assert "é" in extract("a.txt", "évaluation".encode("cp1252")).segments[0].text
    with pytest.raises(ExtractionError):
        extract("vide.txt", b"   \n ")
    with pytest.raises(ValueError):
        sniff("image.png", b"\x89PNG")


def test_tokenize_strips_accents_and_stopwords():
    assert tokenize("Les Protocoles réseaux de l'Élève") == ["protocoles", "reseaux", "eleve"]


def _hit(i: int) -> Hit:
    return Hit(chunk_id=f"d:{i}", document_id="d", filename="f.pdf", page=i, section=None, ordinal=i, text=f"texte {i}", score=1.0)


def test_verify_citations_drops_invented_and_renumbers():
    _, labels = build_context([_hit(1), _hit(2), _hit(3)])
    answer, cited = verify_citations("A [S3]. B [S1, S9]. C [S42]. D [S3][S1].", labels)
    assert answer == "A [S1]. B [S2]. C. D [S1][S2]."
    assert [(lab, h.page) for lab, h in cited] == [("S1", 3), ("S2", 1)]


def test_context_format():
    ctx, labels = build_context([_hit(12)])
    assert ctx.startswith("[SOURCE S1]\nDocument: f.pdf | Page: 12") and list(labels) == ["S1"]


def test_gemini_bascule_et_retrait_du_thinking(monkeypatch):
    """Un modèle en panne est mis à l'écart ; un 400 dû à thinking_config est réessayé sans ce paramètre."""
    from app.core.config import get_settings
    from app.services import gemini

    class Err(Exception):
        def __init__(self, code):
            self.code = code

    s = get_settings()
    monkeypatch.setattr(s, "gemini_model", "principal")
    monkeypatch.setattr(s, "gemini_fallback_models", "secours")
    monkeypatch.setattr(s, "gemini_thinking_budget", 0)
    monkeypatch.setattr(s, "gemini_max_retries", 1)
    monkeypatch.setattr(gemini, "_no_thinking", set())
    monkeypatch.setattr(gemini, "_down_until", {})
    calls = []

    def call(model, thinking):
        calls.append((model, thinking))
        if model == "principal":
            raise Err(504)
        if thinking:
            raise Err(400)
        return "ok"

    assert gemini._with_fallback(call) == ("ok", "secours")
    assert calls == [("principal", True), ("secours", True), ("secours", False)]
    calls.clear()
    # deuxième appel : le modèle en panne passe en dernier, le refus du thinking est mémorisé
    assert gemini._with_fallback(call) == ("ok", "secours")
    assert calls == [("secours", False)]
