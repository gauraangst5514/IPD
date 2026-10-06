"""Persistent exact-file reuse evidence. A match is not an automatic fraud verdict."""
from sqlalchemy import select, func
from app.models.claim import ClaimImage, Claim


async def duplicate_evidence(db, image, owner_id):
    if not image.file_hash:
        return {"method": "sha256_exact_v1", "match_count": 0, "available": False}
    # Never reveal another customer's claim/image identifiers.
    count = await db.scalar(select(func.count()).select_from(ClaimImage).join(
        Claim, Claim.id == ClaimImage.claim_id,
    ).where(
        ClaimImage.file_hash == image.file_hash,
        ClaimImage.id != image.id,
        Claim.claimant_id == owner_id,
    ))
    return {"method": "sha256_exact_v1", "match_count": count,
            "scope": "same_owner", "available": True, "fraud_verdict": False}
