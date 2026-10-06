from typing import Optional
import uuid
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from pydantic import BaseModel
from typing import Literal
from app.services.processing_jobs import request_attempt
from app.models.processing import ProcessingAttempt, ImageEvidence

from app.models.vehicle import Vehicle
from app.core.config import get_settings
from app.services.upload_validation import validate_upload
from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.models.claim import Claim, ClaimImage, ClaimStatus, SeverityLevel, DamageType

router = APIRouter()


class ClaimCreateRequest(BaseModel):
    vehicle_id: uuid.UUID
    description: Optional[str] = None
    incident_date: Optional[datetime] = None
    incident_location: Optional[str] = None


class ClaimResponse(BaseModel):
    id: str
    vehicle_id: uuid.UUID
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_claim(
    request: ClaimCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new insurance claim."""
    vehicle = (await db.execute(select(Vehicle).where(
        Vehicle.id == request.vehicle_id,
        Vehicle.owner_id == uuid.UUID(current_user["user_id"]),
    ))).scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    claim = Claim(
        claimant_id=uuid.UUID(current_user["user_id"]),
        vehicle_id=request.vehicle_id,
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
    claim_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload an image for a claim. Triggers async ML processing."""
    # Verify claim ownership
    result = await db.execute(
        select(Claim).where(
            Claim.id == uuid.UUID(str(claim_id)),
            Claim.claimant_id == uuid.UUID(current_user["user_id"]),
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    settings = get_settings()
    locked = await db.execute(update(Claim).where(
        Claim.id == claim.id, Claim.status == ClaimStatus.SUBMITTED,
    ).values(status=ClaimStatus.SUBMITTED))
    if locked.rowcount != 1:
        raise HTTPException(status_code=409, detail="Claim no longer accepts images")
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    width, height, extension = await asyncio.to_thread(validate_upload, content, file.content_type, settings)
    file_size = len(content)
    file_hash = hashlib.sha256(content).hexdigest()
    existing = (await db.execute(select(ClaimImage).where(
        ClaimImage.claim_id == claim.id, ClaimImage.file_hash == file_hash,
    ))).scalars().first()
    if existing:
        return {"image_id": str(existing.id), "url": image_url(claim.id, existing.id),
                "file_hash": file_hash, "message": "Image already uploaded"}
    count = await db.scalar(select(func.count()).select_from(ClaimImage).where(ClaimImage.claim_id == claim.id))
    if count >= settings.MAX_IMAGES_PER_CLAIM:
        raise HTTPException(409, "Maximum images per claim reached")

    # Upload to MinIO storage
    from app.services.storage import get_storage_service
    storage = await asyncio.to_thread(get_storage_service)
    upload_result = await asyncio.to_thread(storage.upload_image, content, str(claim.id), "image" + extension)

    claim_image = ClaimImage(
        claim_id=uuid.UUID(str(claim_id)),
        original_url=upload_result["key"],
        file_size_bytes=file_size,
        file_hash=file_hash,
        image_width=width,
        image_height=height,
    )
    db.add(claim_image)
    await db.flush()

    return {
        "image_id": str(claim_image.id),
        "url": image_url(claim.id, claim_image.id),
        "file_hash": file_hash,
        "message": "Image uploaded successfully.",
    }


@router.post("/{claim_id}/submit")
async def submit_claim(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Submit claim for processing after all images are uploaded."""
    result = await db.execute(
        select(Claim).where(
            Claim.id == uuid.UUID(str(claim_id)),
            Claim.claimant_id == uuid.UUID(current_user["user_id"]),
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status != ClaimStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Claim already submitted for processing")

    if not claim.images:
        raise HTTPException(status_code=400, detail="Upload at least one image before submission")
    attempt_id = await request_attempt(db, claim, [ClaimStatus.SUBMITTED])
    await db.commit()  # Claim state and durable job become visible together.
    return {"id": str(claim.id), "status": "processing", "attempt_id": str(attempt_id),
            "message": "Claim queued for assessment"}


@router.post("/{claim_id}/retry")
async def retry_claim(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Owner-only retry; conditional transition prevents duplicate dispatch."""
    claim = (await db.execute(select(Claim).where(
        Claim.id == claim_id,
        Claim.claimant_id == uuid.UUID(current_user["user_id"]),
    ))).scalar_one_or_none()
    if claim is None:
        raise HTTPException(404, "Claim not found")
    attempt_id = await request_attempt(db, claim, [ClaimStatus.PROCESSING_FAILED, ClaimStatus.PARTIAL_PROCESSING])
    await db.commit()
    return {"id": str(claim.id), "status": "processing", "attempt_id": str(attempt_id)}


def image_url(claim_id, image_id, variant="original"):
    return f"/api/v1/claims/{claim_id}/images/{image_id}/content?variant={variant}"


async def authorized_claim(claim_id, db, current_user):
    claim = await db.get(Claim, claim_id)
    if claim is None or (current_user["role"] == "claimant" and str(claim.claimant_id) != current_user["user_id"]):
        raise HTTPException(404, "Claim not found")
    if current_user["role"] not in ("claimant", "assessor", "admin"):
        raise HTTPException(403, "Unauthorized")
    return claim


@router.get("/{claim_id}/images/{image_id}/content")
async def get_image_content(
    claim_id: uuid.UUID, image_id: uuid.UUID, variant: Literal["original", "annotated"] = "original",
    db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user),
):
    await authorized_claim(claim_id, db, current_user)
    image = await db.get(ClaimImage, image_id)
    if image is None or image.claim_id != claim_id:
        raise HTTPException(404, "Image not found")
    key = image.original_url if variant == "original" else image.heatmap_url
    if not key:
        raise HTTPException(404, "Image not available")
    from app.services.storage import get_storage_service
    storage = await asyncio.to_thread(get_storage_service)
    try:
        content = await asyncio.to_thread(storage.download_image, key)
    except Exception:
        raise HTTPException(503, "Image storage unavailable")
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(Path(key).suffix.lower(), "application/octet-stream")
    return Response(content, media_type=mime, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{claim_id}/attempts")
async def attempt_history(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await authorized_claim(claim_id, db, current_user)
    attempts = list(await db.scalars(select(ProcessingAttempt).where(ProcessingAttempt.claim_id == claim_id).order_by(ProcessingAttempt.created_at)))
    return [{"id": str(a.id), "state": a.state, "run_count": a.run_count,
             "error_code": a.error_code, "created_at": a.created_at, "completed_at": a.completed_at} for a in attempts]


@router.get("/{claim_id}/attempts/{attempt_id}/evidence")
async def attempt_evidence(claim_id: uuid.UUID, attempt_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await authorized_claim(claim_id, db, current_user)
    attempt = await db.get(ProcessingAttempt, attempt_id)
    if attempt is None or attempt.claim_id != claim_id:
        raise HTTPException(404, "Attempt not found")
    rows = list(await db.scalars(select(ImageEvidence).where(ImageEvidence.attempt_id == attempt_id).order_by(ImageEvidence.created_at)))
    # Raw object keys are internal; authorized image access uses the content route.
    return [{"id": str(row.id), "created_at": row.created_at, "run_id": str(row.lease_token),
             "payload": {k: v for k, v in row.payload.items() if k != "heatmap_key"}} for row in rows]


@router.get("", response_model=list[ClaimResponse])
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
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get full claim details including ML results."""
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(str(claim_id))))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Check access
    if current_user["role"] == "claimant" and str(claim.claimant_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your claim")

    images = [
        {
            "id": str(img.id),
            "original_url": image_url(claim.id, img.id),
            "heatmap_url": image_url(claim.id, img.id, "annotated") if img.heatmap_url else None,
            "damage_detected": img.damage_detected,
            "damage_type": img.damage_type.value if img.damage_type else None,
            "severity": img.severity.value if img.severity else None,
            "confidence": None,
            "detector_confidence": img.detector_confidence,
            "severity_score": img.severity_score,
            "analysis_outcome": img.analysis_outcome,
            "checks": img.checks or [],
            "processing_status": img.processing_status,
            "processing_error": img.processing_error,
            "annotation_error": img.annotation_error,
            "duplicate_evidence": img.duplicate_evidence,
            "is_duplicate": img.is_duplicate,
            "is_manipulated": img.is_manipulated,
            "manipulation_score": img.manipulation_score,
        }
        for img in (claim.images or [])
    ]

    return {
        "id": str(claim.id),
        "status": claim.status.value,
        "claimant_id": str(claim.claimant_id),
        "description": claim.description,
        "incident_date": claim.incident_date,
        "incident_location": claim.incident_location,
        "damage_type": claim.damage_type.value if claim.damage_type else None,
        "severity": claim.severity.value if claim.severity else None,
        "confidence_score": None,
        "detector_confidence": claim.detector_confidence,
        "severity_score": claim.severity_score,
        "analysis_outcome": claim.analysis_outcome,
        "checks": claim.checks or [],
        "review_version": claim.review_version,
        "current_attempt_id": str(claim.current_attempt_id) if claim.current_attempt_id else None,
        "estimated_cost_min": claim.estimated_cost_min,
        "estimated_cost_max": claim.estimated_cost_max,
        "cost_breakdown": claim.cost_breakdown,
        "fraud_risk_score": claim.fraud_risk_score,
        "fraud_flags": claim.fraud_flags,
        "detections": claim.detections or [],
        "images": images,
        "created_at": claim.created_at,
        "processed_at": claim.processed_at,
    }


@router.get("/{claim_id}/pdf")
async def download_claim_pdf(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download claim report as PDF."""
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(str(claim_id))))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Check access
    if current_user["role"] == "claimant" and str(claim.claimant_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your claim")

    # Build claim dict for PDF generator
    images = [
        {
            "id": str(img.id),
            "damage_type": img.damage_type.value if img.damage_type else None,
            "severity": img.severity.value if img.severity else None,
            "confidence": None,
            "detector_confidence": img.detector_confidence,
            "severity_score": img.severity_score,
            "analysis_outcome": img.analysis_outcome,
            "checks": img.checks or [],
            "is_manipulated": img.is_manipulated,
        }
        for img in (claim.images or [])
    ]

    claim_data = {
        "id": str(claim.id),
        "status": claim.status.value,
        "claimant_id": str(claim.claimant_id),
        "description": claim.description,
        "incident_date": claim.incident_date,
        "incident_location": claim.incident_location,
        "damage_type": claim.damage_type.value if claim.damage_type else None,
        "severity": claim.severity.value if claim.severity else None,
        "confidence_score": None,
        "detector_confidence": claim.detector_confidence,
        "severity_score": claim.severity_score,
        "analysis_outcome": claim.analysis_outcome,
        "checks": claim.checks or [],
        "review_version": claim.review_version,
        "current_attempt_id": str(claim.current_attempt_id) if claim.current_attempt_id else None,
        "estimated_cost_min": claim.estimated_cost_min,
        "estimated_cost_max": claim.estimated_cost_max,
        "cost_breakdown": claim.cost_breakdown,
        "fraud_risk_score": claim.fraud_risk_score,
        "fraud_flags": claim.fraud_flags,
        "images": images,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "processed_at": claim.processed_at.isoformat() if claim.processed_at else None,
    }

    from app.services.pdf_report import generate_claim_pdf
    import io as _io

    pdf_bytes = generate_claim_pdf(claim_data)

    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=claim_{claim_id[:8]}_report.pdf"
        },
    )
