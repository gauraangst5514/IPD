from typing import Optional
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.models.claim import Claim, ClaimImage, ClaimStatus, SeverityLevel, DamageType
from app.models.vehicle import Vehicle
from app.core.config import get_settings
from app.core.claim_fields import StructuredFields

router = APIRouter()


class ClaimCreateRequest(BaseModel):
    vehicle_id: str
    description: Optional[str] = None
    incident_date: Optional[datetime] = None
    incident_location: Optional[str] = None
    structured_fields: Optional[StructuredFields] = None
    invoice_text: Optional[str] = None


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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_claim(
    request: ClaimCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new insurance claim."""
    vehicle = (await db.execute(select(Vehicle).where(
        Vehicle.id == uuid.UUID(request.vehicle_id),
        Vehicle.owner_id == uuid.UUID(current_user["user_id"]),
    ))).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
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

    if request.structured_fields or request.invoice_text:
        from app.models.intelligence import ClaimIntelligence
        from app.services.invoice import parse_invoice
        if request.invoice_text and len(request.invoice_text)>50000:
            raise HTTPException(422,"Invoice text must be at most 50000 characters")
        db.add(ClaimIntelligence(claim_id=claim.id,
            structured_fields=request.structured_fields.model_dump() if request.structured_fields else {},
            tabular_result={},
            invoice_result=parse_invoice(request.invoice_text) if request.invoice_text else {}))
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

    if claim.status != ClaimStatus.SUBMITTED:
        raise HTTPException(status_code=409, detail="Images can only be added before submission")

    # Read file content
    content = await file.read(get_settings().MAX_IMAGE_BYTES + 1)
    file_size = len(content)
    if file_size > get_settings().MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Images must be 10 MB or smaller")

    from PIL import Image as PILImage, UnidentifiedImageError
    import io as _io
    try:
        with PILImage.open(_io.BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported format")
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, PILImage.DecompressionBombError):
        raise HTTPException(status_code=422, detail="Upload a valid JPEG, PNG or WebP image")

    # Upload to MinIO storage
    from app.services.storage import get_storage_service
    storage = get_storage_service()
    upload_result = storage.upload_image(content, claim_id, file.filename)

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

    if not claim.images:
        raise HTTPException(status_code=400, detail="Upload at least one image before submission")

    claim.status = ClaimStatus.PROCESSING

    if get_settings().PROCESSING_MODE == "celery":
        # Workers need committed data before the task is dispatched.
        await db.commit()
        try:
            from app.worker.tasks import process_claim_task
            process_claim_task.apply_async(args=[claim_id], retry=False)
        except Exception:
            claim.status = ClaimStatus.SUBMITTED
            await db.commit()
            raise HTTPException(status_code=503, detail="Processing queue is unavailable; please retry")
    else:
        from app.services.claim_processor import process_claim
        try:
            await process_claim(claim_id, db)
            await db.commit()
            from app.services.graph_projection import synchronize_pending
            await synchronize_pending(db)
        except Exception as e:
            claim.status = ClaimStatus.AWAITING_REVIEW
            print(f"⚠️  ML processing failed: {e}")

    return {"id": str(claim.id), "status": claim.status.value, "message": "Claim submitted for AI assessment."}


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

    from app.services.storage import get_storage_service
    storage = get_storage_service()
    images = [
        {
            "id": str(img.id),
            "original_url": storage.get_presigned_url(img.original_url) if not img.original_url.startswith("http") else img.original_url,
            "heatmap_url": storage.get_presigned_url(img.heatmap_url) if img.heatmap_url and not img.heatmap_url.startswith("http") else img.heatmap_url,
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
        "detections": claim.detections or [],
        "images": images,
        "created_at": claim.created_at,
        "processed_at": claim.processed_at,
    }


@router.get("/{claim_id}/pdf")
async def download_claim_pdf(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download claim report as PDF."""
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
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
            "confidence": img.confidence,
            "is_manipulated": img.is_manipulated,
        }
        for img in (claim.images or [])
    ]

    claim_data = {
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
