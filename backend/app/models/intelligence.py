import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.types import GUID

class ClaimIntelligence(Base):
    __tablename__ = "claim_intelligence"
    claim_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("claims.id"), primary_key=True)
    structured_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    tabular_result: Mapped[dict] = mapped_column(JSON, default=dict)
    invoice_result: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
