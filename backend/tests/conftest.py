"""Tests : base SQLite + Chroma temporaires, embeddings par hachage, Gemini simulé (aucun appel réseau)."""
from __future__ import annotations

import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp(prefix="documind-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db".replace("\\", "/"),
    "CHROMA_PATH": os.path.join(_tmp, "chroma"),
    "UPLOAD_DIR": os.path.join(_tmp, "uploads"),
    "EMBEDDING_BACKEND": "hash",
    "INDEXING_SYNC": "true",
    "GEMINI_API_KEY": "",
    "RERANKER_MODEL": "",
    "MAX_UPLOAD_MB": "1",
    "RATE_LIMIT_CHAT_PER_MIN": "1000",
    "RATE_LIMIT_AUTH_PER_MIN": "1000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.errors import AppError  # noqa: E402
from app.main import app  # noqa: E402
from app.services import gemini  # noqa: E402

TCP_TEXT = (
    "Cours de réseaux : le protocole TCP.\n\n"
    "TCP garantit la fiabilité grâce aux acquittements, aux numéros de séquence et aux retransmissions. "
    "Chaque segment envoyé doit être acquitté par le destinataire ; sans acquittement, il est retransmis.\n\n"
    "Le contrôle de congestion de TCP repose sur une fenêtre de congestion et l'algorithme slow start.\n\n"
    "UDP, à l'inverse, est un protocole sans connexion qui n'offre aucune garantie de livraison."
)
CUISINE_TEXT = (
    "Recettes de cuisine.\n\nLa ratatouille est un plat provençal à base de courgettes, d'aubergines, "
    "de poivrons et de tomates mijotés dans l'huile d'olive.\n\nLa pâte à crêpes se prépare avec de la farine, "
    "des œufs, du lait et une pincée de sel."
)


class FakeGemini:
    """Répond en citant S1 et une source inventée S99 ; s'abstient si la question contient « licorne »."""

    def __init__(self):
        self.fail = False
        self.prompts: list[str] = []

    def _answer(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise AppError(503, "Le service Gemini est momentanément indisponible.", "gemini_unavailable")
        question = prompt.split("[QUESTION]")[-1]
        if "licorne" in question:
            return "[ABSTENTION] Les extraits ne mentionnent pas ce sujet [S1]."
        return "D'après le document, voici la réponse [S1][S99]. Complément [S2, S77]."

    def generate(self, prompt, system=None, temperature=0.2, max_tokens=None, json_schema=None):
        if json_schema:
            self.prompts.append(prompt)
            return '{"summary": "Résumé du document.", "key_points": ["Point A"], "keywords": ["tcp", "réseau"]}', gemini.Usage()
        if "Question autonome" in prompt:
            return "Comment UDP gère-t-il la fiabilité ?", gemini.Usage()
        return self._answer(prompt), gemini.Usage()

    def stream(self, prompt, usage, system=None, temperature=0.2):
        text = self._answer(prompt)
        for i in range(0, len(text), 7):
            yield text[i:i + 7]


@pytest.fixture()
def fake_gemini(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(gemini, "generate", fake.generate)
    monkeypatch.setattr(gemini, "stream", fake.stream)
    return fake


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


class Account:
    def __init__(self, client: TestClient):
        self.client = client
        self.email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        r = client.post("/api/auth/register", json={"email": self.email, "password": "motdepasse123", "name": "Test"})
        assert r.status_code == 201, r.text
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.user_id = r.json()["user_id"]
        self.workspace_id = client.get("/api/workspaces", headers=self.headers).json()[0]["id"]

    def upload(self, name: str, data: bytes, workspace_id: str | None = None):
        return self.client.post("/api/documents/upload", headers=self.headers,
                                data={"workspace_id": workspace_id or self.workspace_id},
                                files=[("files", (name, data))])

    def upload_ok(self, name: str, data: bytes) -> dict:
        r = self.upload(name, data)
        assert r.status_code == 202, r.text
        doc = self.client.get(f"/api/documents/{r.json()['documents'][0]['id']}", headers=self.headers).json()
        assert doc["status"] == "ready", doc
        return doc

    def chat(self, question: str, **kw):
        return self.client.post("/api/chat", headers=self.headers,
                                json={"workspace_id": self.workspace_id, "question": question, **kw})


@pytest.fixture()
def alice(client):
    return Account(client)


@pytest.fixture()
def bob(client):
    return Account(client)
