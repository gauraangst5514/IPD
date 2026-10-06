import io
from PIL import Image
from app.models import User, Vehicle, Claim, ClaimImage
from app.models.user import UserRole
from app.models.claim import ClaimStatus
from app.services.processing_jobs import request_attempt


def image_bytes(color='white'):
    out = io.BytesIO()
    Image.new('RGB', (20, 20), color).save(out, format='PNG')
    return out.getvalue()


def analysis(damaged=True):
    return dict(schema_version='2', outcome='damage_detected' if damaged else 'no_visible_damage',
        damage_detected=damaged,
        detections=[dict(label='tire_flat', confidence=.9, bbox=[.5,.5,.2,.2])] if damaged else [],
        severity='moderate' if damaged else None, severity_score=.1 if damaged else None,
        detector_confidence=.9 if damaged else None, primary_damage_type='tire_flat' if damaged else None,
        cost_estimate_min=100 if damaged else None, cost_estimate_max=200 if damaged else None,
        cost_breakdown={}, severity_reasoning={}, fraud_score=.2, manipulation_score=None,
        fraud_flags=['test_signal'], checks=[dict(id='vehicle_make', status='unavailable', detail='No weights', method='classifier')],
        model_provenance={'sha256':'test-only-artifact', 'validation':'synthetic fixture'}, annotated_image_base64=None)


async def seed(factory, images=2, status=ClaimStatus.SUBMITTED):
    async with factory() as db:
        owner = User(email='owner@example.com', full_name='Owner', hashed_password='unused')
        stranger = User(email='stranger@example.com', full_name='Stranger', hashed_password='unused')
        reviewer = User(email='reviewer@example.com', full_name='Reviewer', hashed_password='unused', role=UserRole.ASSESSOR)
        db.add_all([owner, stranger, reviewer]); await db.flush()
        vehicle = Vehicle(owner_id=owner.id, registration_number='AUDIT01', make='hyundai', model='test', year=2022)
        db.add(vehicle); await db.flush()
        claim = Claim(claimant_id=owner.id, vehicle_id=vehicle.id, status=status)
        db.add(claim); await db.flush()
        image_ids = []
        for i in range(images):
            image = ClaimImage(claim_id=claim.id, original_url=f'photo-{i}.png', file_hash=f'hash-{i}')
            db.add(image); await db.flush(); image_ids.append(image.id)
        await db.commit()
        return dict(owner=owner.id, stranger=stranger.id, reviewer=reviewer.id,
                    vehicle=vehicle.id, claim=claim.id, images=image_ids)


async def enqueue(factory, claim_id):
    async with factory() as db:
        claim = await db.get(Claim, claim_id)
        attempt_id = await request_attempt(db, claim, [ClaimStatus.SUBMITTED, ClaimStatus.PROCESSING_FAILED, ClaimStatus.PARTIAL_PROCESSING])
        await db.commit()
        return attempt_id
