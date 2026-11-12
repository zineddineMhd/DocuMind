"""Modèle relationnel (cahier des charges §07)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


ID = String(36)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped[User] = relationship(back_populates="workspaces")
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('pending','processing','ready','failed')", name="ck_documents_status"),
        CheckConstraint("file_size >= 0", name="ck_documents_size"),
    )
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True)
    jobs: Mapped[list["IndexingJob"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_doc_ordinal", "document_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # déterministe : <document_id>:<ordinal>
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    vector_id: Mapped[str] = mapped_column(String(64))
    embedding_version: Mapped[str] = mapped_column(String(200))
    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    workspace: Mapped[Workspace] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # answered | no_answer | uncertain | error
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 / -1
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="MessageSource.position"
    )


class MessageSource(Base):
    __tablename__ = "message_sources"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    # SET NULL : l'historique conserve la citation, signalée comme indisponible après suppression du document.
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(64))
    source_label: Mapped[str] = mapped_column(String(8))  # S1, S2…
    position: Mapped[int] = mapped_column(Integer, default=0)
    filename: Mapped[str] = mapped_column(String(255))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text)
    message: Mapped[Message] = relationship(back_populates="sources")


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | done | failed
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document: Mapped[Document] = relationship(back_populates="jobs")
