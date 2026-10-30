from typing import Optional, Literal
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import require_role
from app.models.claim import Claim, ClaimStatus, ClaimAssessment
from app.models.user import User
from app.services.notifications import send_claim_notification

router = APIRouter()


class AssessmentRequest(BaseModel):
    claim_id: str
    decision: Literal["approved", "rejected", "escalated"]
    approved_amount: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


@router.post("")
async def submit_assessment(
    request: AssessmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(["assessor", "admin"])),
):
    """Assessor submits their decision on a claim."""
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(request.claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status not in (ClaimStatus.AWAITING_REVIEW, ClaimStatus.FLAGGED):
        raise HTTPException(status_code=400, detail=f"Claim is in '{claim.status.value}' state, cannot review")

    # Record assessment
    assessment = ClaimAssessment(
        claim_id=uuid.UUID(request.claim_id),
        assessor_id=uuid.UUID(current_user["user_id"]),
        decision=request.decision,
        approved_amount=request.approved_amount,
        notes=request.notes,
    )
    db.add(assessment)

    # Update claim status
    status_map = {
        "approved": ClaimStatus.APPROVED,
        "rejected": ClaimStatus.REJECTED,
        "escalated": ClaimStatus.FLAGGED,
    }
    claim.status = status_map.get(request.decision, ClaimStatus.AWAITING_REVIEW)
    claim.reviewed_at = datetime.now(timezone.utc)
    from app.services.graph_projection import enqueue_claim
    await enqueue_claim(claim,db)

    # Send email notification to claimant (non-blocking)
    try:
        user_result = await db.execute(select(User).where(User.id == claim.claimant_id))
        claimant = user_result.scalar_one_or_none()
        if claimant and claimant.email:
            notification_details = {
                "damage_summary": claim.damage_type.value if claim.damage_type else "N/A",
                "severity": claim.severity.value if claim.severity else "N/A",
                "cost_estimate_min": claim.estimated_cost_min,
                "cost_estimate_max": claim.estimated_cost_max,
                "fraud_risk_score": claim.fraud_risk_score,
                "notes": request.notes or "",
            }
            send_claim_notification(
                email=claimant.email,
                claim_id=request.claim_id,
                status=claim.status.value,
                details=notification_details,
            )
    except Exception as e:
        print(f"⚠️  Failed to send assessment notification: {e}")

    await db.flush()
    return {
        "assessment_id": str(assessment.id),
        "claim_id": request.claim_id,
        "decision": request.decision,
        "message": f"Claim {request.decision} successfully.",
    }


@router.get("/queue")
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(["assessor", "admin"])),
):
    """Get claims awaiting assessor review, with flagged claims first, then oldest submissions."""
    result = await db.execute(
        select(Claim)
        .where(Claim.status.in_([ClaimStatus.AWAITING_REVIEW, ClaimStatus.FLAGGED]))
        .order_by(case((Claim.status == ClaimStatus.FLAGGED, 0), else_=1), Claim.created_at.asc())
    )
    claims = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "status": c.status.value,
            "damage_type": c.damage_type.value if c.damage_type else None,
            "severity": c.severity.value if c.severity else None,
            "estimated_cost_min": c.estimated_cost_min,
            "estimated_cost_max": c.estimated_cost_max,
            "fraud_risk_score": c.fraud_risk_score,
            "created_at": c.created_at,
        }
        for c in claims
    ]
