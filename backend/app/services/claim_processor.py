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
from app.models.fraud import FraudFlag
from app.models.user import User
from app.services.storage import get_storage_service
from app.services.ml_client import get_ml_client
from app.services.graph_fraud import sync_claim_to_graph, check_fraud_rings


# Map ML primary_damage_type string -> DamageType enum
DAMAGE_TYPE_MAP = {
    "dent": DamageType.DENT,
    "scratch": DamageType.SCRATCH,
    "crack": DamageType.CRACK,
    "shatter": DamageType.GLASS_SHATTER,
    "panel": DamageType.LAMP_BROKEN,
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

    # Load claimant (User) info (for fraud graph)
    claimant_result = await db.execute(select(User).where(User.id == claim.claimant_id))
    claimant = claimant_result.scalar_one_or_none()

    vehicle_make = vehicle.make if vehicle else "hyundai"
    vehicle_year = vehicle.year if vehicle else 2022
    # Derive region from incident location (simplified)
    region = _extract_region(claim.incident_location)

    # Process each image
    all_results = []
    max_fraud_score = 0.0
    all_fraud_flags = {}

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
            )

            # Get annotated image and store it
            annotated_bytes = await ml_client.get_annotated_image(image_bytes)
            heatmap_key = storage.upload_heatmap(annotated_bytes, claim_id, str(img.id))

            # Update image record
            img.damage_detected = analysis["damage_detected"]
            img.confidence = analysis.get("severity_score", 0.0)
            img.heatmap_url = heatmap_key
            img.is_manipulated = analysis["fraud_score"] > 0.5
            img.manipulation_score = analysis["fraud_score"]

            # Map damage type
            primary_type = analysis.get("primary_damage_type", "dent")
            if primary_type in DAMAGE_TYPE_MAP:
                img.damage_type = DAMAGE_TYPE_MAP[primary_type]

            # Map severity
            severity_str = analysis.get("severity", "moderate")
            if severity_str in SEVERITY_MAP:
                img.severity = SEVERITY_MAP[severity_str]

            all_results.append(analysis)

            # Track fraud
            if analysis["fraud_score"] > max_fraud_score:
                max_fraud_score = analysis["fraud_score"]
            for flag in analysis.get("fraud_flags", []):
                all_fraud_flags[flag] = True

            # Create fraud flag records
            for flag in analysis.get("fraud_flags", []):
                fraud_record = FraudFlag(
                    claim_id=uuid.UUID(claim_id),
                    flag_type=flag,
                    severity="high" if analysis["fraud_score"] > 0.7 else "medium",
                    confidence=analysis["fraud_score"],
                    description=f"Image {img.id}: {flag}",
                )
                db.add(fraud_record)

        except Exception as e:
            print(f"⚠️  Failed to process image {img.id}: {e}")
            continue

    # Aggregate results across all images
    if all_results:
        # Use the worst severity and highest cost across images
        severities = [r["severity"] for r in all_results]
        severity_order = {"severe": 3, "moderate": 2, "minor": 1}
        worst_severity = max(severities, key=lambda s: severity_order.get(s, 0))

        # Use the highest cost estimate
        max_cost_min = max(r["cost_estimate_min"] for r in all_results)
        max_cost_max = max(r["cost_estimate_max"] for r in all_results)

        # Use the most common damage type
        from collections import Counter
        type_counts = Counter(r["primary_damage_type"] for r in all_results)
        primary_type = type_counts.most_common(1)[0][0]

        # Confidence is average severity score
        avg_confidence = sum(r["severity_score"] for r in all_results) / len(all_results)

        # Cost breakdown from the highest-cost image
        best_result = max(all_results, key=lambda r: r["cost_estimate_max"])

        # Integrate Neo4j Graph Fraud Analysis
        try:
            if claimant and vehicle:
                await sync_claim_to_graph(claim, claimant, vehicle)
                graph_fraud = await check_fraud_rings(claim.id)
                
                # Add graph fraud score to the max image fraud score
                max_fraud_score = min(max_fraud_score + graph_fraud["score"], 1.0)
                
                # Add graph flags
                for flag in graph_fraud["flags"]:
                    all_fraud_flags[flag] = True
                    fraud_record = FraudFlag(
                        claim_id=claim.id,
                        flag_type="graph_fraud",
                        severity="high",
                        confidence=1.0,
                        description=flag,
                    )
                    db.add(fraud_record)
        except Exception as e:
            print(f"⚠️  Graph fraud analysis failed: {e}")

        # Update claim
        claim.severity = SEVERITY_MAP.get(worst_severity, SeverityLevel.MODERATE)
        claim.damage_type = DAMAGE_TYPE_MAP.get(primary_type, DamageType.DENT)
        claim.confidence_score = avg_confidence
        claim.estimated_cost_min = max_cost_min
        claim.estimated_cost_max = max_cost_max
        claim.cost_breakdown = best_result.get("cost_breakdown")
        claim.fraud_risk_score = max_fraud_score
        claim.fraud_flags = all_fraud_flags
        claim.processed_at = datetime.now(timezone.utc)

        # Set status based on fraud score
        if max_fraud_score > 0.7:
            claim.status = ClaimStatus.FLAGGED
        else:
            claim.status = ClaimStatus.AWAITING_REVIEW
    else:
        # No images could be processed
        claim.status = ClaimStatus.AWAITING_REVIEW
        claim.processed_at = datetime.now(timezone.utc)

    await db.flush()
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
