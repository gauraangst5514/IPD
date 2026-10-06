from typing import Literal
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from pydantic import BaseModel, Field, model_validator
from app.core.database import get_db
from app.core.auth import require_role
from app.models.claim import Claim, ClaimStatus, ClaimAssessment
from app.models.user import User
from app.services.notifications import send_claim_notification

router = APIRouter()


class AssessmentRequest(BaseModel):
    claim_id: uuid.UUID
    decision: Literal['approved', 'rejected', 'escalated']
    expected_version: int = Field(ge=0)
    approved_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode='after')
    def amount_matches_decision(self):
        if self.decision == 'approved' and self.approved_amount is None:
            raise ValueError('An approval requires an amount')
        if self.decision != 'approved' and self.approved_amount is not None:
            raise ValueError('Only an approval can contain an approved amount')
        return self


@router.post('')
async def submit_assessment(request: AssessmentRequest, db: AsyncSession = Depends(get_db),
                            current_user: dict = Depends(require_role(['assessor', 'admin']))):
    claim = await db.get(Claim, request.claim_id)
    if claim is None:
        raise HTTPException(404, 'Claim not found')
    reviewer_id = uuid.UUID(current_user['user_id'])
    if claim.claimant_id == reviewer_id:
        raise HTTPException(403, 'You cannot assess your own claim')
    predicates = [Claim.id == request.claim_id,
                  Claim.status.in_([ClaimStatus.AWAITING_REVIEW, ClaimStatus.FLAGGED]),
                  Claim.review_version == request.expected_version]
    if current_user['role'] != 'admin':
        predicates.append(or_(Claim.assigned_assessor_id.is_(None), Claim.assigned_assessor_id == reviewer_id))
    status_map = {'approved': ClaimStatus.APPROVED, 'rejected': ClaimStatus.REJECTED, 'escalated': ClaimStatus.FLAGGED}
    changed = await db.execute(update(Claim).where(*predicates).values(
        status=status_map[request.decision], reviewed_at=datetime.now(timezone.utc),
        assigned_assessor_id=reviewer_id, review_version=Claim.review_version + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, 'Claim changed or is assigned to another reviewer; refresh the queue')
    assessment = ClaimAssessment(claim_id=request.claim_id, assessor_id=reviewer_id,
                                 decision=request.decision, approved_amount=request.approved_amount, notes=request.notes)
    db.add(assessment)
    await db.flush()
    assessment_id = str(assessment.id)
    claimant = await db.get(User, claim.claimant_id)
    notification = None if claimant is None else {
        'email': claimant.email, 'claim_id': str(claim.id), 'status': status_map[request.decision].value,
        'details': {'severity': claim.severity.value if claim.severity else 'N/A',
                    'damage_summary': claim.damage_type.value if claim.damage_type else 'N/A',
                    'cost_estimate_min': claim.estimated_cost_min, 'cost_estimate_max': claim.estimated_cost_max,
                    'fraud_risk_score': claim.fraud_risk_score, 'notes': request.notes or ''},
    }
    await db.commit()  # Notify only after the decision is durable.
    if notification:
        try:
            await asyncio.to_thread(send_claim_notification, **notification)
        except Exception:
            pass  # Notification failures never roll back a committed assessment.
    return {'assessment_id': assessment_id, 'claim_id': str(request.claim_id), 'decision': request.decision}


@router.get('/queue')
async def get_review_queue(db: AsyncSession = Depends(get_db), current_user: dict = Depends(require_role(['assessor', 'admin']))):
    query = select(Claim).where(Claim.status.in_([ClaimStatus.AWAITING_REVIEW, ClaimStatus.FLAGGED]))
    if current_user['role'] != 'admin':
        query = query.where(or_(Claim.assigned_assessor_id.is_(None), Claim.assigned_assessor_id == uuid.UUID(current_user['user_id'])))
    claims = list(await db.scalars(query.order_by(Claim.fraud_risk_score.desc().nullslast(), Claim.created_at)))
    return [{'id': str(c.id), 'status': c.status.value, 'review_version': c.review_version,
             'damage_type': c.damage_type.value if c.damage_type else None,
             'severity': c.severity.value if c.severity else None,
             'estimated_cost_min': c.estimated_cost_min, 'estimated_cost_max': c.estimated_cost_max,
             'fraud_risk_score': c.fraud_risk_score, 'created_at': c.created_at} for c in claims]
