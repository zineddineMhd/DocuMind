"""Tests d'intégration : comptes, espaces, documents, recherche, chat, sécurité multi-comptes, suppression."""
from __future__ import annotations

import io
import json

from app.services import vectorstore
from tests.conftest import CUISINE_TEXT, TCP_TEXT


def make_pdf(pages: list[str]) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text, fontsize=11)
    return doc.tobytes()


def make_docx() -> bytes:
    import docx

    d = docx.Document()
    d.add_heading("Stratégie IA", level=1)
    d.add_paragraph("L'entreprise investit dans l'intelligence artificielle générative dès 2025.")
    d.add_heading("Budget", level=2)
    d.add_paragraph("Le budget alloué à la R&D est de 8,2 millions d'euros.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------------------- comptes
def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_register_login_profile(client, alice):
    assert client.get("/api/auth/me", headers=alice.headers).json()["email"] == alice.email
    r = client.post("/api/auth/register", json={"email": alice.email, "password": "motdepasse123"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    assert client.post("/api/auth/login", json={"email": alice.email, "password": "mauvais-mdp"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": alice.email, "password": "motdepasse123"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/register", json={"email": "pas-un-email", "password": "x"})
    assert r.status_code == 422 and r.json()["error"]["request_id"]


def test_workspace_crud(client, alice):
    r = client.post("/api/workspaces", headers=alice.headers, json={"name": "Réseaux"})
    assert r.status_code == 201
    wid = r.json()["id"]
    assert client.patch(f"/api/workspaces/{wid}", headers=alice.headers, json={"name": "Cours"}).json()["name"] == "Cours"
    assert len(client.get("/api/workspaces", headers=alice.headers).json()) == 2
    assert client.delete(f"/api/workspaces/{wid}", headers=alice.headers).status_code == 204
    assert len(client.get("/api/workspaces", headers=alice.headers).json()) == 1


# ----------------------------------------------------------------------------- documents
def test_upload_txt_pdf_docx(client, alice):
    txt = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode("utf-8"))
    assert txt["chunk_count"] >= 1 and len(txt["sha256"]) == 64
    pdf = alice.upload_ok("rapport.pdf", make_pdf(["Page un : croissance du chiffre d'affaires de 12 %.",
                                                    "Page deux : la marge nette atteint 18 %."]))
    assert pdf["page_count"] == 2
    chunks = client.get(f"/api/documents/{pdf['id']}/chunks", headers=alice.headers).json()
    assert [c["page"] for c in chunks] == [1, 2] and "marge nette" in chunks[1]["text"]
    docx_doc = alice.upload_ok("Stratégie.docx", make_docx())
    chunks = client.get(f"/api/documents/{docx_doc['id']}/chunks", headers=alice.headers).json()
    assert {c["section"] for c in chunks} == {"Stratégie IA", "Budget"}
    assert "8,2 millions" in " ".join(c["text"] for c in chunks)  # accents et chiffres conservés
    assert len(client.get(f"/api/documents?workspace_id={alice.workspace_id}", headers=alice.headers).json()) == 3
    r = client.get(f"/api/documents/{txt['id']}/file", headers=alice.headers)
    assert r.status_code == 200 and r.content == TCP_TEXT.encode("utf-8")


def test_upload_rejections(client, alice):
    assert alice.upload("virus.exe", b"MZ\x90\x00").status_code == 415
    assert alice.upload("faux.pdf", b"ceci n'est pas un pdf").status_code == 415
    assert alice.upload("faux.docx", b"PK\x03\x04 pas un vrai zip").status_code == 415
    r = alice.upload("gros.txt", b"a" * (1024 * 1024 + 10))
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    assert alice.upload("vide.txt", b"").status_code == 400
    alice.upload_ok("a.txt", TCP_TEXT.encode())
    r = alice.upload("copie.txt", TCP_TEXT.encode())  # même SHA-256 : pas de doublon
    assert r.status_code == 202 and r.json()["documents"] == [] and r.json()["rejected"][0]["code"] == "duplicate"


def test_scanned_pdf_fails_then_reindex_has_no_duplicates(client, alice):
    r = alice.upload("scan.pdf", make_pdf([""]))
    doc = client.get(f"/api/documents/{r.json()['documents'][0]['id']}", headers=alice.headers).json()
    assert doc["status"] == "failed" and "OCR" in doc["error"]
    ok = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    n = vectorstore.count_document(ok["id"])
    r = client.post(f"/api/documents/{ok['id']}/reindex", headers=alice.headers)
    assert r.status_code == 202
    assert vectorstore.count_document(ok["id"]) == n == ok["chunk_count"]


# ----------------------------------------------------------------------------- recherche
def test_search_filters_by_document(client, alice):
    tcp = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    cuisine = alice.upload_ok("Recettes.txt", CUISINE_TEXT.encode())
    body = {"workspace_id": alice.workspace_id, "query": "acquittements et retransmissions TCP"}
    res = client.post("/api/search", headers=alice.headers, json=body).json()["results"]
    assert res[0]["document_id"] == tcp["id"] and "acquitt" in res[0]["text"]
    res = client.post("/api/search", headers=alice.headers, json={**body, "document_ids": [cuisine["id"]]}).json()["results"]
    assert res and all(r["document_id"] == cuisine["id"] for r in res)


# ----------------------------------------------------------------------------- chat
def test_chat_citations_are_verified(client, alice, fake_gemini):
    doc = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    r = alice.chat("Comment TCP garantit-il la fiabilité ?", document_ids=[doc["id"]])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "answered"
    assert "S99" not in out["answer"] and "S77" not in out["answer"]  # identifiants inventés supprimés
    labels = [s["source_id"] for s in out["sources"]]
    assert labels and labels[0] == "S1" and all(f"[{lab}]" in out["answer"] for lab in labels)
    assert all(s["document_id"] == doc["id"] and s["filename"] == "Cours_TCP.txt" for s in out["sources"])
    # le contenu des documents est isolé dans <extraits>, jamais dans les instructions
    assert "<extraits>" in fake_gemini.prompts[-1] and "[SOURCE S1]" in fake_gemini.prompts[-1]

    # question de suivi : même conversation, reformulation utilisée pour la recherche
    r2 = alice.chat("et pour UDP ?", conversation_id=out["conversation_id"])
    assert r2.json()["conversation_id"] == out["conversation_id"]
    assert r2.json()["metrics"]["rewritten_question"].startswith("Comment UDP")
    conv = client.get(f"/api/conversations/{out['conversation_id']}", headers=alice.headers).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    assert conv["messages"][1]["sources"][0]["available"] is True
    md = client.get(f"/api/conversations/{out['conversation_id']}/export", headers=alice.headers)
    assert md.status_code == 200 and "Cours_TCP.txt" in md.text
    assert client.post(f"/api/messages/{out['message_id']}/feedback", headers=alice.headers, json={"value": 1}).status_code == 204


def test_chat_abstention_and_errors(client, alice, fake_gemini):
    assert alice.chat("Bonjour ?").status_code == 400  # aucun document prêt
    alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    out = alice.chat("Que dit le cours sur la licorne ?").json()
    assert out["status"] == "no_answer" and out["sources"] == [] and "[ABSTENTION]" not in out["answer"]
    fake_gemini.fail = True
    r = alice.chat("Comment TCP garantit-il la fiabilité ?")
    assert r.status_code == 503 and r.json()["error"]["code"] == "gemini_unavailable"


def test_chat_stream(client, alice, fake_gemini):
    alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    with client.stream("POST", "/api/chat/stream", headers=alice.headers,
                       json={"workspace_id": alice.workspace_id, "question": "Fiabilité de TCP ?"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "meta" and types[-1] == "final" and "token" in types
    assert events[-1]["status"] == "answered" and events[-1]["sources"]


def test_summary(client, alice, fake_gemini):
    doc = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    out = client.post(f"/api/documents/{doc['id']}/summary", headers=alice.headers).json()
    assert out["summary"].startswith("Résumé") and "tcp" in out["keywords"]
    assert client.get(f"/api/documents/{doc['id']}", headers=alice.headers).json()["keywords"] == ["tcp", "réseau"]


# ----------------------------------------------------------------------------- sécurité
def test_cross_account_isolation(client, alice, bob, fake_gemini):
    doc = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    conv_id = alice.chat("Fiabilité de TCP ?").json()["conversation_id"]
    bob.upload_ok("Recettes.txt", CUISINE_TEXT.encode())
    h = bob.headers
    assert client.get(f"/api/documents/{doc['id']}", headers=h).status_code == 404
    assert client.get(f"/api/documents/{doc['id']}/file", headers=h).status_code == 404
    assert client.get(f"/api/documents/{doc['id']}/chunks", headers=h).status_code == 404
    assert client.delete(f"/api/documents/{doc['id']}", headers=h).status_code == 404
    assert client.get(f"/api/documents?workspace_id={alice.workspace_id}", headers=h).status_code == 404
    assert client.get(f"/api/conversations/{conv_id}", headers=h).status_code == 404
    assert client.delete(f"/api/workspaces/{alice.workspace_id}", headers=h).status_code == 404
    assert bob.upload("x.txt", b"contenu", workspace_id=alice.workspace_id).status_code == 404
    # Bob tente d'interroger le document d'Alice depuis son propre espace
    assert bob.chat("Fiabilité de TCP ?", document_ids=[doc["id"]]).status_code == 403
    r = client.post("/api/search", headers=h, json={"workspace_id": bob.workspace_id, "query": "TCP",
                                                    "document_ids": [doc["id"]]})
    assert r.status_code == 403
    # et sa recherche globale ne voit que ses propres passages
    res = client.post("/api/search", headers=h, json={"workspace_id": bob.workspace_id,
                                                      "query": "acquittements retransmissions TCP"}).json()["results"]
    assert all(x["filename"] == "Recettes.txt" for x in res)
    assert client.get(f"/api/documents/{doc['id']}", headers=alice.headers).status_code == 200


def test_delete_document_purges_everything(client, alice, fake_gemini):
    import os

    from app.db.session import SessionLocal
    from app.models import Document

    doc = alice.upload_ok("Cours_TCP.txt", TCP_TEXT.encode())
    with SessionLocal() as db:
        path = db.get(Document, doc["id"]).storage_path
    out = alice.chat("Fiabilité de TCP ?").json()
    assert vectorstore.count_document(doc["id"]) > 0 and os.path.exists(path)
    assert client.delete(f"/api/documents/{doc['id']}", headers=alice.headers).status_code == 204
    assert vectorstore.count_document(doc["id"]) == 0 and not os.path.exists(path)
    assert client.get(f"/api/documents/{doc['id']}", headers=alice.headers).status_code == 404
    res = client.post("/api/search", headers=alice.headers, json={"workspace_id": alice.workspace_id, "query": "TCP"})
    assert res.json()["results"] == []
    # l'historique conserve la citation, signalée comme indisponible
    conv = client.get(f"/api/conversations/{out['conversation_id']}", headers=alice.headers).json()
    src = conv["messages"][1]["sources"][0]
    assert src["available"] is False and src["document_id"] is None and src["filename"] == "Cours_TCP.txt"


def test_delete_account(client, bob):
    doc = bob.upload_ok("Recettes.txt", CUISINE_TEXT.encode())
    assert client.delete("/api/auth/me", headers=bob.headers).status_code == 204
    assert client.get("/api/auth/me", headers=bob.headers).status_code == 401
    assert vectorstore.count_document(doc["id"]) == 0
