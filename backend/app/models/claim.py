import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from sqlalchemy import Enum as SAEnum

from app.core.database import Base
from app.core.types import GUID


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    PROCESSING_FAILED = "processing_failed"
    PARTIAL_PROCESSING = "partial_processing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    CLOSED = "closed"


class SeverityLevel(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class DamageType(str, enum.Enum):
    DENT = "dent"
    SCRATCH = "scratch"
    CRACK = "crack"
    GLASS_SHATTER = "glass_shatter"
    LAMP_BROKEN = "lamp_broken"
    TIRE_FLAT = "tire_flat"
    MULTIPLE = "multiple"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    claimant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("vehicles.id"), nullable=False)
    current_attempt_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=True, index=True)
    review_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    assigned_assessor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=True)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    incident_location: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(SAEnum(ClaimStatus), default=ClaimStatus.SUBMITTED)

    analysis_outcome: Mapped[str] = mapped_column(String(32), nullable=True)
    detector_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    severity_score: Mapped[float] = mapped_column(Float, nullable=True)
    checks: Mapped[list] = mapped_column(JSON, nullable=True)
    damage_type: Mapped[DamageType] = mapped_column(SAEnum(DamageType), nullable=True)
    severity: Mapped[SeverityLevel] = mapped_column(SAEnum(SeverityLevel), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=True)

    estimated_cost_min: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_cost_max: Mapped[float] = mapped_column(Float, nullable=True)
    cost_breakdown: Mapped[dict] = mapped_column(JSON, nullable=True)

    fraud_risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    fraud_flags: Mapped[dict] = mapped_column(JSON, nullable=True)
    detections: Mapped[dict] = mapped_column(JSON, nullable=True)  # Raw detection results for damage map

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    images: Mapped[list["ClaimImage"]] = relationship(back_populates="claim", lazy="selectin")


class ClaimImage(Base):
    __tablename__ = "claim_images"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("claims.id"), nullable=False)

    original_url: Mapped[str] = mapped_column(String(500), nullable=False)
    heatmap_url: Mapped[str] = mapped_column(String(500), nullable=True)

    file_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    processing_error: Mapped[str] = mapped_column(String(80), nullable=True)
    annotation_error: Mapped[str] = mapped_column(String(80), nullable=True)
    duplicate_evidence: Mapped[dict] = mapped_column(JSON, nullable=True)
    exif_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    image_width: Mapped[int] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int] = mapped_column(Integer, nullable=True)

    damage_detected: Mapped[bool] = mapped_column(nullable=True)
    analysis_outcome: Mapped[str] = mapped_column(String(32), nullable=True)
    detector_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    severity_score: Mapped[float] = mapped_column(Float, nullable=True)
    checks: Mapped[list] = mapped_column(JSON, nullable=True)
    damage_type: Mapped[DamageType] = mapped_column(SAEnum(DamageType), nullable=True)
    severity: Mapped[SeverityLevel] = mapped_column(SAEnum(SeverityLevel), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    is_duplicate: Mapped[bool] = mapped_column(nullable=True)
    is_manipulated: Mapped[bool] = mapped_column(nullable=True)
    manipulation_score: Mapped[float] = mapped_column(Float, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    claim: Mapped["Claim"] = relationship(back_populates="images")


class ClaimAssessment(Base):
    __tablename__ = "claim_assessments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("claims.id"), nullable=False)
    assessor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_amount: Mapped[float] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
