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
    rejected = (await db.execute(
        base.where(Claim.status == ClaimStatus.REJECTED)
    )).scalar() or 0

    # Average fraud score (for assessors/admins)
    avg_fraud = None
    if role in ("assessor", "admin"):
        result = await db.execute(
            select(func.avg(Claim.fraud_risk_score)).where(Claim.fraud_risk_score.isnot(None))
        )
        avg_fraud = result.scalar()
        avg_fraud = round(avg_fraud, 3) if avg_fraud else 0.0

    # Recent claims (last 5)
    if role == "claimant":
        recent_query = select(Claim).where(Claim.claimant_id == user_id).order_by(Claim.created_at.desc()).limit(5)
    else:
        recent_query = select(Claim).order_by(Claim.created_at.desc()).limit(5)

    recent_result = await db.execute(recent_query)
    recent_claims = [
        {
            "id": str(c.id),
            "status": c.status.value,
            "damage_type": c.damage_type.value if c.damage_type else None,
            "fraud_risk_score": c.fraud_risk_score,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in recent_result.scalars().all()
    ]

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "flagged": flagged,
        "rejected": rejected,
        "avg_fraud_score": avg_fraud,
        "recent_claims": recent_claims,
    }
