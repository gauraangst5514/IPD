"""
Claim Processing Service

Orchestrates the full pipeline when a claim is submitted:
1. Fetch each uploaded image from storage
2. Call ML service for analysis
3. Store annotated images (with boxes)
4. Aggregate results across all images
5. Update the claim with final damage/severity/cost/fraud scores
6. Set claim status to awaiting_review

This can be called synchronously (for small claims) or dispatched
via Celery for async processing.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.claim import Claim, ClaimImage, ClaimStatus, SeverityLevel, DamageType
from app.models.vehicle import Vehicle
from app.models.user import User
from app.services.storage import get_storage_service
from app.services.ml_client import get_ml_client
from app.services.notifications import send_claim_notification
from app.services.assessment_results import aggregate_damage


# Map ML primary_damage_type string -> DamageType enum
DAMAGE_TYPE_MAP = {
    "dent": DamageType.DENT,
    "scratch": DamageType.SCRATCH,
    "crack": DamageType.CRACK,
    "glass_shatter": DamageType.GLASS_SHATTER,
    "lamp_broken": DamageType.LAMP_BROKEN,
    "tire_flat": DamageType.TIRE_FLAT,
}

SEVERITY_MAP = {
    "minor": SeverityLevel.MINOR,
    "moderate": SeverityLevel.MODERATE,
    "severe": SeverityLevel.SEVERE,
}


async def process_claim(claim_id: str, db: AsyncSession):
    """
    Run the full ML pipeline on a submitted claim.

    This is the main orchestration function.
    """
    storage = get_storage_service()
    ml_client = get_ml_client()

    # Load claim with images
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise ValueError(f"Claim {claim_id} not found")

    # Load vehicle info (for cost estimation)
    vehicle_result = await db.execute(select(Vehicle).where(Vehicle.id == claim.vehicle_id))
    vehicle = vehicle_result.scalar_one_or_none()

    vehicle_make = vehicle.make if vehicle else "hyundai"
    vehicle_year = vehicle.year if vehicle else 2022
    registration_number = vehicle.registration_number if vehicle else ""
    # Derive region from incident location (simplified)
    region = _extract_region(claim.incident_location)

    # Process each image
    all_results = []
    all_fraud_flags = {}
    indicators = []
    # Reprocessing replaces legacy heuristic scores and evidence.
    claim.fraud_risk_score = None
    claim.fraud_flags = {}
    # Preserve existing FraudFlag rows as historical records; new evidence is
    # kept in the claim JSON without inventing a confidence value.

    for img in claim.images:
        try:
            # Download from storage
            image_bytes = storage.download_image(img.original_url)

            # Call ML service
            analysis = await ml_client.analyze_image(
                image_bytes=image_bytes,
                vehicle_make=vehicle_make,
                vehicle_year=vehicle_year,
                region=region,
                claim_id=claim_id,
                image_id=str(img.id),
                description=claim.description or "",
                registration_number=registration_number,
            )

            # Evidence must survive a failed optional annotation request.
            heatmap_key = None
            if analysis.get("damage_analysis_available", True) and analysis.get("detections"):
                try:
                    annotated_bytes = await ml_client.get_annotated_image(image_bytes)
                    heatmap_key = storage.upload_heatmap(annotated_bytes, claim_id, str(img.id))
                except Exception:
                    indicators.append({"code": "damage_annotation", "status": "unavailable",
                        "detail": "Damage overlay could not be generated; other evidence is retained.",
                        "image_id": str(img.id), "evidence": {}})

            # Update image record
            img.damage_detected = analysis["damage_detected"]
            img.confidence = max((d["confidence"] for d in analysis.get("detections", [])), default=None)
            img.heatmap_url = heatmap_key
            img.is_manipulated = None
            img.manipulation_score = None
            image_indicators = analysis.get("fraud_indicators")
            if not isinstance(image_indicators, list):
                raise ValueError("ML service must return evidence indicators; deploy both services together")
            indicators.extend({**item, "image_id": str(img.id)} for item in image_indicators)
            duplicate = next((item for item in image_indicators if item["code"] == "duplicate_image"), None)
            img.is_duplicate = (duplicate["status"] == "review") if duplicate and duplicate["status"] != "unavailable" else None

            # Map damage type
            primary_type = analysis.get("primary_damage_type", "dent")
            img.damage_type = DAMAGE_TYPE_MAP.get(primary_type)

            # Map severity
            severity_str = analysis.get("severity", "moderate")
            img.severity = SEVERITY_MAP.get(severity_str)

            all_results.append(analysis)

            # Keep evidence in the existing JSON column. The legacy FraudFlag
            # table requires confidence, so do not invent one to write a row.
            for item in image_indicators:
                if item["status"] == "review":
                    all_fraud_flags[item["code"]] = True

        except Exception as e:
            print(f"⚠️  Failed to process image {img.id}: {e}")
            img.is_manipulated = None
            img.manipulation_score = None
            img.is_duplicate = None
            indicators.append({"code": "image_analysis", "status": "unavailable",
                "detail": "Image analysis failed; manual review is required.",
                "image_id": str(img.id), "evidence": {}})
            continue

    summary = aggregate_damage(all_results)
    claim.severity = SEVERITY_MAP.get(summary["severity"])
    claim.damage_type = DAMAGE_TYPE_MAP.get(summary["primary_damage_type"])
    claim.confidence_score = summary["confidence"]
    claim.estimated_cost_min = summary["cost_min"]
    claim.estimated_cost_max = summary["cost_max"]
    claim.cost_breakdown = summary["cost_breakdown"]
    claim.detections = summary["detections"]
    claim.processed_at = datetime.now(timezone.utc)
    claim.status = (ClaimStatus.FLAGGED if any(item["status"] == "review" for item in indicators)
                    else ClaimStatus.AWAITING_REVIEW)

    claim.fraud_flags = {
        **all_fraud_flags,
        "_indicators": indicators,
        "_checks_complete": bool(all_results) and not any(item["status"] == "unavailable" for item in indicators),
    }
    # Structured models are independent of image availability and run in ML.
    from app.models.intelligence import ClaimIntelligence
    from app.services.structured_assessment import assess_record
    record=await db.get(ClaimIntelligence,claim.id)
    if record:
        if record.structured_fields:
            await assess_record(record)
        invoice_indicators=record.invoice_result.get("indicators",[]) if record.invoice_result else []
        if invoice_indicators:
            indicators.extend(invoice_indicators)
            claim.fraud_flags={**claim.fraud_flags,"_indicators":indicators}
            if any(i["status"]=="review" for i in invoice_indicators):
                claim.status=ClaimStatus.FLAGGED
    from app.services.graph_projection import enqueue_claim
    await enqueue_claim(claim,db)
    await db.flush()

    # Send email notification (non-blocking, won't fail the processing)
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
            }
            send_claim_notification(
                email=claimant.email,
                claim_id=claim_id,
                status=claim.status.value,
                details=notification_details,
            )
    except Exception as e:
        print(f"⚠️  Failed to send notification for claim {claim_id}: {e}")

    return {
        "claim_id": claim_id,
        "status": claim.status.value,
        "images_processed": len(all_results),
    }


def _extract_region(location: Optional[str]) -> str:
    """
    Extract a city/region from the incident location string.
    Falls back to 'default' if not recognized.
    """
    if not location:
        return "default"

    location_lower = location.lower()
    known_cities = [
        "mumbai", "delhi", "bangalore", "bengaluru", "chennai",
        "pune", "hyderabad", "kolkata", "ahmedabad", "jaipur",
        "lucknow", "surat", "indore", "nagpur", "thane",
    ]
    for city in known_cities:
        if city in location_lower:
            return city

    return "default"
