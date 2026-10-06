"""Durable database queue with expiring leases and conditional completion.

Queue records commit alongside the claim transition. Broker delivery is only a
wakeup hint; a dispatcher redelivers queued work and recovers expired leases.
"""
import asyncio
import contextlib
import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, func, or_
from fastapi import HTTPException
from app.core.config import get_settings
from app.models.claim import Claim, ClaimImage, ClaimStatus
from app.models.vehicle import Vehicle
from app.models.processing import ProcessingAttempt, ImageEvidence
from app.models.fraud import FraudFlag
from app.services.duplicates import duplicate_evidence
from app.services import claim_processor

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc)


async def request_attempt(db, claim, allowed_states):
    settings = get_settings()
    count = await db.scalar(select(func.count()).select_from(ProcessingAttempt).where(ProcessingAttempt.claim_id == claim.id))
    if count >= settings.MAX_CLAIM_ATTEMPTS:
        raise HTTPException(409, 'Retry limit reached; contact support')
    attempt_id = uuid.uuid4()
    changed = await db.execute(update(Claim).where(
        Claim.id == claim.id, Claim.status.in_(allowed_states),
        Claim.current_attempt_id == claim.current_attempt_id,
    ).values(status=ClaimStatus.PROCESSING, current_attempt_id=attempt_id,
             review_version=Claim.review_version + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, 'Claim state changed; refresh before retrying')
    db.add(ProcessingAttempt(id=attempt_id, claim_id=claim.id))
    await db.flush()
    return attempt_id


def lease_filter(attempt_id, token):
    return (ProcessingAttempt.id == attempt_id, ProcessingAttempt.state == 'running',
            ProcessingAttempt.lease_token == token, ProcessingAttempt.lease_until > now())


async def acquire(factory, attempt_id):
    token = uuid.uuid4()
    settings = get_settings()
    async with factory() as db:
        changed = await db.execute(update(ProcessingAttempt).where(
            ProcessingAttempt.id == attempt_id, ProcessingAttempt.state == 'queued',
            ProcessingAttempt.next_run_at <= now(), ProcessingAttempt.run_count < settings.PROCESSING_MAX_RUNS,
        ).values(state='running', lease_token=token,
                 lease_until=now() + timedelta(seconds=settings.PROCESSING_LEASE_SECONDS),
                 run_count=ProcessingAttempt.run_count + 1, error_code=None))
        if changed.rowcount != 1:
            await db.rollback()
            return None
        attempt = await db.get(ProcessingAttempt, attempt_id)
        claim = await db.get(Claim, attempt.claim_id)
        if claim is None or claim.current_attempt_id != attempt_id or claim.status != ClaimStatus.PROCESSING:
            attempt.state = 'superseded'
            await db.commit()
            return None
        await db.commit()
    return token


async def heartbeat(factory, attempt_id, token):
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.PROCESSING_LEASE_SECONDS / 3)
        async with factory() as db:
            changed = await db.execute(update(ProcessingAttempt).where(*lease_filter(attempt_id, token)).values(
                lease_until=now() + timedelta(seconds=settings.PROCESSING_LEASE_SECONDS)))
            await db.commit()
            if changed.rowcount != 1:
                return


async def load_snapshot(factory, attempt_id):
    async with factory() as db:
        attempt = await db.get(ProcessingAttempt, attempt_id)
        claim = await db.get(Claim, attempt.claim_id)
        vehicle = await db.get(Vehicle, claim.vehicle_id)
        if vehicle is None:
            raise ValueError('Vehicle missing')
        snapshot = {'id': str(claim.id), 'make': vehicle.make, 'year': vehicle.year,
                    'registration': vehicle.registration_number, 'location': claim.incident_location,
                    'description': claim.description}
        images = []
        for image in sorted(claim.images, key=lambda value: str(value.id)):
            images.append({'id': str(image.id), 'key': image.original_url,
                           'duplicate_evidence': await duplicate_evidence(db, image, claim.claimant_id)})
        return snapshot, images


async def save_evidence(factory, attempt_id, token, outcome):
    async with factory() as db:
        fenced = await db.execute(update(ProcessingAttempt).where(*lease_filter(attempt_id, token)).values(
            lease_until=now() + timedelta(seconds=get_settings().PROCESSING_LEASE_SECONDS)))
        if fenced.rowcount != 1:
            await db.rollback()
            return False
        db.add(ImageEvidence(attempt_id=attempt_id, lease_token=token,
                             image_id=uuid.UUID(outcome['image_id']), payload=outcome))
        await db.commit()
        return True


async def finish(factory, attempt_id, token, outcomes):
    async with factory() as db:
        changed = await db.execute(update(ProcessingAttempt).where(*lease_filter(attempt_id, token)).values(
            state='completed', completed_at=now(), lease_until=None))
        if changed.rowcount != 1:
            await db.rollback()
            return False
        attempt = await db.get(ProcessingAttempt, attempt_id)
        fenced = await db.execute(update(Claim).where(
            Claim.id == attempt.claim_id, Claim.current_attempt_id == attempt_id,
            Claim.status == ClaimStatus.PROCESSING,
        ).values(review_version=Claim.review_version + 1))
        if fenced.rowcount != 1:
            await db.rollback()
            return False
        claim = await db.get(Claim, attempt.claim_id)
        claim_processor.project(claim, {str(img.id): img for img in claim.images}, outcomes)
        claim.processed_at = now()
        for outcome in outcomes:
            result = outcome['result']
            if result:
                for flag in result['fraud_flags']:
                    db.add(FraudFlag(claim_id=claim.id, attempt_id=attempt_id, flag_type=flag,
                                     severity='high' if result['fraud_score'] > .7 else 'medium',
                                     confidence=result['fraud_score'],
                                     description=f"Image {outcome['image_id']}: {flag}",
                                     evidence={'image_id': outcome['image_id'], 'model': result['model_provenance']}))
        await db.commit()
    return True


async def release_failed(factory, attempt_id, token, error_code='processing_error'):
    async with factory() as db:
        attempt = await db.get(ProcessingAttempt, attempt_id)
        if attempt is None:
            return
        exhausted = attempt.run_count >= get_settings().PROCESSING_MAX_RUNS
        changed = await db.execute(update(ProcessingAttempt).where(*lease_filter(attempt_id, token)).values(
            state='failed' if exhausted else 'queued', lease_until=None, lease_token=None,
            error_code=error_code, next_run_at=now() + timedelta(seconds=30 * attempt.run_count),
            last_dispatched_at=None))
        if changed.rowcount and exhausted:
            await db.execute(update(Claim).where(Claim.id == attempt.claim_id,
                Claim.current_attempt_id == attempt_id, Claim.status == ClaimStatus.PROCESSING,
            ).values(status=ClaimStatus.PROCESSING_FAILED))
        await db.commit()


async def run_attempt(attempt_id, factory=None):
    if factory is None:
        from app.core.database import async_session
        factory = async_session
    attempt_id = uuid.UUID(str(attempt_id))
    token = await acquire(factory, attempt_id)
    if token is None:
        return {'status': 'skipped'}
    pulse = asyncio.create_task(heartbeat(factory, attempt_id, token))
    try:
        claim, images = await load_snapshot(factory, attempt_id)
        storage = await asyncio.to_thread(claim_processor.get_storage_service)
        client = claim_processor.get_ml_client()
        outcomes = []
        for image in images:
            try:
                outcome = await asyncio.wait_for(claim_processor.analyze_image(
                    image, claim, storage=storage, client=client,
                    artifact_suffix=f'{attempt_id}-{token}',
                ), timeout=150)
            except TimeoutError:
                outcome = {'image_id': image['id'], 'result': None, 'error': 'analysis_timeout',
                           'annotation_error': None, 'heatmap_key': None,
                           'duplicate_evidence': image['duplicate_evidence']}
            if not await save_evidence(factory, attempt_id, token, outcome):
                return {'status': 'superseded'}
            outcomes.append(outcome)
        committed = await finish(factory, attempt_id, token, outcomes)
        return {'status': 'completed' if committed else 'superseded'}
    except Exception:
        logger.exception('Processing attempt failed: %s', attempt_id)
        await release_failed(factory, attempt_id, token)
        return {'status': 'retry_scheduled'}
    finally:
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pulse


async def reconcile(factory):
    """Recover crashed workers without allowing an old lease to complete later."""
    async with factory() as db:
        expired = (await db.scalars(select(ProcessingAttempt).where(
            ProcessingAttempt.state == 'running', ProcessingAttempt.lease_until <= now(),
        ).limit(100))).all()
        for attempt in expired:
            exhausted = attempt.run_count >= get_settings().PROCESSING_MAX_RUNS
            changed = await db.execute(update(ProcessingAttempt).where(
                ProcessingAttempt.id == attempt.id, ProcessingAttempt.state == 'running',
                ProcessingAttempt.lease_token == attempt.lease_token, ProcessingAttempt.lease_until <= now(),
            ).values(state='failed' if exhausted else 'queued', lease_token=None, lease_until=None,
                     next_run_at=now(), last_dispatched_at=None, error_code='lease_expired').execution_options(synchronize_session=False))
            if changed.rowcount and exhausted:
                await db.execute(update(Claim).where(Claim.id == attempt.claim_id,
                    Claim.current_attempt_id == attempt.id, Claim.status == ClaimStatus.PROCESSING,
                ).values(status=ClaimStatus.PROCESSING_FAILED))
        await db.commit()


async def dispatch_due(factory, publish):
    await reconcile(factory)
    async with factory() as db:
        ids = list(await db.scalars(select(ProcessingAttempt.id).where(
            ProcessingAttempt.state == 'queued', ProcessingAttempt.next_run_at <= now(),
            or_(ProcessingAttempt.last_dispatched_at.is_(None),
                ProcessingAttempt.last_dispatched_at < now() - timedelta(seconds=30)),
        ).order_by(ProcessingAttempt.created_at).limit(100)))
    for attempt_id in ids:
        async with factory() as db:
            changed = await db.execute(update(ProcessingAttempt).where(
                ProcessingAttempt.id == attempt_id, ProcessingAttempt.state == 'queued',
                or_(ProcessingAttempt.last_dispatched_at.is_(None),
                    ProcessingAttempt.last_dispatched_at < now() - timedelta(seconds=30)),
            ).values(last_dispatched_at=now()))
            await db.commit()
        if not changed.rowcount:
            continue
        try:
            await asyncio.to_thread(publish, str(attempt_id))
        except Exception:
            logger.warning('Broker unavailable; attempt %s remains durable and queued', attempt_id)
