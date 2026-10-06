"""Durable dispatch records and append-only per-run image evidence."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.types import GUID


def utcnow():
    return datetime.now(timezone.utc)


class ProcessingAttempt(Base):
    __tablename__ = 'processing_attempts'
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('claims.id'), index=True)
    state: Mapped[str] = mapped_column(String(24), default='queued', index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=True)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageEvidence(Base):
    __tablename__ = 'image_evidence'
    __table_args__ = (UniqueConstraint('attempt_id', 'lease_token', 'image_id', name='uq_evidence_attempt_run_image'),)
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('processing_attempts.id'), index=True)
    lease_token: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    image_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('claim_images.id'), index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
