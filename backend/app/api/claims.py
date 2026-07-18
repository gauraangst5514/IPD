from typing import Optional
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.models.claim import Claim, ClaimImage, ClaimStatus, SeverityLevel, DamageType

router = APIRouter()


class ClaimCreateRequest(BaseModel):
    vehicle_id: str
    description: Optional[str] = None
    incident_date: Optional[datetime] = None
    incident_location: Optional[str] = None


class ClaimResponse(BaseModel):
    id: str
    vehicle_id: str
    status: str
    description: Optional[str]
    damage_type: Optional[str]
    severity: Optional[str]
    confidence_score: Optional[float]
    estimated_cost_min: Optional[float]
    estimated_cost_max: Optional[float]
    cost_breakdown: Optional[dict]
    fraud_risk_score: Optional[float]
    fraud_flags: Optional[dict]
    created_at: datetime
    processed_at: Optional[datetime]
    image_count: int

    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_claim(
    request: ClaimCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new insurance claim."""
    claim = Claim(
        claimant_id=uuid.UUID(current_user["user_id"]),
        vehicle_id=uuid.UUID(request.vehicle_id),
        description=request.description,
        incident_date=request.incident_date,
        incident_location=request.incident_location,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    await db.flush()

    return {"id": str(claim.id), "status": claim.status.value, "message": "Claim created. Upload images next."}


@router.post("/{claim_id}/images")
async def upload_claim_image(
    claim_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload an image for a claim. Triggers async ML processing."""
    # Verify claim ownership
    result = await db.execute(
        select(Claim).where(
            Claim.id == uuid.UUID(claim_id),
            Claim.claimant_id == uuid.UUID(current_user["user_id"]),
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Upload to MinIO storage
    from app.services.storage import get_storage_service
    storage = get_storage_service()
    upload_result = storage.upload_image(content, claim_id, file.filename)

    # Extract image dimensions
    from PIL import Image as PILImage
    import io as _io
    try:
        img = PILImage.open(_io.BytesIO(content))
        width, height = img.size
    except Exception:
        width, height = None, None

    claim_image = ClaimImage(
        claim_id=uuid.UUID(claim_id),
        original_url=upload_result["key"],
        file_size_bytes=file_size,
        file_hash=upload_result["file_hash"],
        image_width=width,
        image_height=height,
    )
    db.add(claim_image)
    await db.flush()

    return {
        "image_id": str(claim_image.id),
        "url": upload_result["url"],
        "file_hash": upload_result["file_hash"],
        "message": "Image uploaded successfully.",
    }


@router.post("/{claim_id}/submit")
async def submit_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Submit claim for processing after all images are uploaded."""
    result = await db.execute(
        select(Claim).where(
            Claim.id == uuid.UUID(claim_id),
            Claim.claimant_id == uuid.UUID(current_user["user_id"]),
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status != ClaimStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Claim already submitted for processing")

    claim.status = ClaimStatus.PROCESSING

    # Try Celery first, fall back to direct processing if Redis isn't available
    try:
        from app.worker.tasks import process_claim_task
        process_claim_task.delay(claim_id)
    except Exception:
        # Direct processing (no Celery/Redis) — works for dev/demo
        from app.services.claim_processor import process_claim
        try:
            await process_claim(claim_id, db)
        except Exception as e:
            claim.status = ClaimStatus.AWAITING_REVIEW
            print(f"⚠️  ML processing failed: {e}")

    return {"id": str(claim.id), "status": claim.status.value, "message": "Claim submitted for AI assessment."}


@router.get("/", response_model=list[ClaimResponse])
async def list_claims(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List claims based on user role."""
    if current_user["role"] == "claimant":
        query = select(Claim).where(Claim.claimant_id == uuid.UUID(current_user["user_id"]))
    elif current_user["role"] in ("assessor", "admin"):
        query = select(Claim)
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")

    result = await db.execute(query.order_by(Claim.created_at.desc()))
    claims = result.scalars().all()

    return [
        ClaimResponse(
            id=str(c.id),
            vehicle_id=str(c.vehicle_id),
            status=c.status.value,
            description=c.description,
            damage_type=c.damage_type.value if c.damage_type else None,
            severity=c.severity.value if c.severity else None,
            confidence_score=c.confidence_score,
            estimated_cost_min=c.estimated_cost_min,
            estimated_cost_max=c.estimated_cost_max,
            cost_breakdown=c.cost_breakdown,
            fraud_risk_score=c.fraud_risk_score,
            fraud_flags=c.fraud_flags,
            created_at=c.created_at,
            processed_at=c.processed_at,
            image_count=len(c.images) if c.images else 0,
        )
        for c in claims
    ]


@router.get("/{claim_id}")
async def get_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get full claim details including ML results."""
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Check access
    if current_user["role"] == "claimant" and str(claim.claimant_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your claim")

    images = [
        {
            "id": str(img.id),
            "original_url": img.original_url,
            "heatmap_url": img.heatmap_url,
            "damage_detected": img.damage_detected,
            "damage_type": img.damage_type.value if img.damage_type else None,
            "severity": img.severity.value if img.severity else None,
            "confidence": img.confidence,
            "is_duplicate": img.is_duplicate,
            "is_manipulated": img.is_manipulated,
            "manipulation_score": img.manipulation_score,
        }
        for img in (claim.images or [])
    ]

    return {
        "id": str(claim.id),
        "status": claim.status.value,
        "description": claim.description,
        "incident_date": claim.incident_date,
        "incident_location": claim.incident_location,
        "damage_type": claim.damage_type.value if claim.damage_type else None,
        "severity": claim.severity.value if claim.severity else None,
        "confidence_score": claim.confidence_score,
        "estimated_cost_min": claim.estimated_cost_min,
        "estimated_cost_max": claim.estimated_cost_max,
        "cost_breakdown": claim.cost_breakdown,
        "fraud_risk_score": claim.fraud_risk_score,
        "fraud_flags": claim.fraud_flags,
        "images": images,
        "created_at": claim.created_at,
        "processed_at": claim.processed_at,
    }
