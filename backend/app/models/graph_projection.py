"""Durable SQL outbox for retryable Neo4j projections."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import JSON, ForeignKey, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.types import GUID

class GraphProjection(Base):
    __tablename__="graph_projections"
    claim_id: Mapped[uuid.UUID] = mapped_column(GUID(),ForeignKey("claims.id"),primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON,nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    last_error: Mapped[str | None] = mapped_column(String(200),nullable=True)
