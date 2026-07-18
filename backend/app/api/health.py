import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "intelliclaim-api", "version": "0.1.0"}


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get claim statistics for the dashboard."""
    from sqlalchemy import func
    from app.models.claim import Claim, ClaimStatus

    user_id = uuid.UUID(current_user["user_id"])
    role = current_user["role"]

    # Base query — claimants see only their own, assessors/admins see all
    if role == "claimant":
        base = select(func.count()).select_from(Claim).where(Claim.claimant_id == user_id)
    else:
        base = select(func.count()).select_from(Claim)

    total = (await db.execute(base)).scalar() or 0
    pending = (await db.execute(
        base.where(Claim.status.in_([ClaimStatus.AWAITING_REVIEW, ClaimStatus.PROCESSING]))
    )).scalar() or 0
    approved = (await db.execute(
        base.where(Claim.status == ClaimStatus.APPROVED)
    )).scalar() or 0
    flagged = (await db.execute(
        base.where(Claim.status == ClaimStatus.FLAGGED)
    )).scalar() or 0

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "flagged": flagged,
    }
