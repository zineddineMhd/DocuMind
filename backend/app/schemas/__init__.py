"""Contrats JSON de l'API (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- comptes -------------------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: str
    email: str
    name: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user: UserOut


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


# --- espaces -------------------------------------------------------------------------------
class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceOut(ORM):
    id: str
    name: str
    created_at: datetime
    document_count: int = 0
    conversation_count: int = 0


# --- documents -----------------------------------------------------------------------------
class DocumentOut(ORM):
    id: str
    workspace_id: str
    filename: str
    content_type: str
    file_size: int
    sha256: str
    page_count: int | None
    chunk_count: int
    status: Literal["pending", "processing", "ready", "failed"]
    error: str | None
    summary: str | None
    keywords: list[str] | None
    created_at: datetime


class UploadOut(BaseModel):
    documents: list[DocumentOut]
    rejected: list[dict] = []


class ChunkOut(ORM):
    id: str
    page: int | None
    section: str | None
    ordinal: int
    text: str


class SummaryOut(BaseModel):
    document_id: str
    summary: str
    keywords: list[str]
    truncated: bool = False


# --- chat / recherche ----------------------------------------------------------------------
class ChatIn(BaseModel):
    workspace_id: str
    conversation_id: str | None = None
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] | None = None  # None ou [] = tous les documents prêts de l'espace
    mode: Literal["qa", "summary", "compare", "explain"] = "qa"


class SourceOut(BaseModel):
    source_id: str
    document_id: str | None
    filename: str
    page: int | None
    section: str | None = None
    chunk_id: str
    excerpt: str
    available: bool = True


class ChatOut(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[SourceOut]
    status: Literal["answered", "no_answer", "uncertain", "error"]
    metrics: dict = {}
    created_at: datetime | None = None


class SearchIn(BaseModel):
    workspace_id: str
    query: str = Field(min_length=1, max_length=1000)
    document_ids: list[str] | None = None
    top_k: int = Field(default=8, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    section: str | None
    text: str
    score: float
    similarity: float | None


class SearchOut(BaseModel):
    results: list[SearchResult]
    search_ms: int


# --- conversations -------------------------------------------------------------------------
class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    status: str | None
    feedback: int | None
    sources: list[SourceOut]
    metrics: dict | None = None
    created_at: datetime


class ConversationOut(ORM):
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class FeedbackIn(BaseModel):
    value: Literal[-1, 0, 1]
