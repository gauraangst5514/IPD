import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, update
from app.models import Claim, ClaimImage, User
from app.models.claim import ClaimStatus, DamageType
from app.models.processing import ProcessingAttempt, ImageEvidence
from app.models.fraud import FraudFlag
from app.api.claims import retry_claim
from app.services import claim_processor as processor
from app.services.processing_jobs import run_attempt, acquire, finish, reconcile, dispatch_due, now
from app.services.duplicates import duplicate_evidence
from helpers import seed, enqueue, analysis, image_bytes


def fake_services(monkeypatch, responses):
    client = SimpleNamespace(analyze_image=AsyncMock(side_effect=responses))
    storage = SimpleNamespace(download_image=lambda key: image_bytes(), upload_heatmap=lambda *args: 'preview.png')
    monkeypatch.setattr(processor, 'get_storage_service', lambda: storage)
    monkeypatch.setattr(processor, 'get_ml_client', lambda: client)
    return client, storage


@pytest.mark.asyncio
async def test_duplicate_scope_survives_new_session(factory):
    ids = await seed(factory)
    async with factory() as db:
        foreign = Claim(claimant_id=ids['stranger'], vehicle_id=ids['vehicle'])
        db.add(foreign); await db.flush()
        db.add(ClaimImage(claim_id=foreign.id, original_url='foreign.png', file_hash='hash-0'))
        await db.commit()
    async with factory() as db:
        image = await db.get(ClaimImage, ids['images'][0])
        assert (await duplicate_evidence(db, image, ids['owner']))['match_count'] == 0
        own = Claim(claimant_id=ids['owner'], vehicle_id=ids['vehicle'])
        db.add(own); await db.flush()
        db.add(ClaimImage(claim_id=own.id, original_url='own.png', file_hash='hash-0'))
        await db.commit()
    async with factory() as db:
        evidence = await duplicate_evidence(db, await db.get(ClaimImage, ids['images'][0]), ids['owner'])
        assert evidence['match_count'] == 1 and evidence['fraud_verdict'] is False


@pytest.mark.asyncio
async def test_failed_partial_retry_and_append_only_evidence(factory, monkeypatch):
    ids = await seed(factory)
    first = await enqueue(factory, ids['claim'])
    client, storage = fake_services(monkeypatch, [analysis(), RuntimeError('unavailable')])
    assert (await run_attempt(first, factory))['status'] == 'completed'
    async with factory() as db:
        claim = await db.get(Claim, ids['claim'])
        assert claim.status == ClaimStatus.PARTIAL_PROCESSING
        assert claim.detector_confidence == .9 and claim.severity_score == .1
        assert claim.confidence_score is None
        assert claim.damage_type == DamageType.TIRE_FLAT
        assert await db.scalar(select(func.count()).select_from(ImageEvidence)) == 2
        assert await db.scalar(select(func.count()).select_from(FraudFlag)) == 1
        with pytest.raises(HTTPException) as exc:
            await retry_claim(claim.id, db, {'user_id': str(ids['stranger'])})
        assert exc.value.status_code == 404
        retried = await retry_claim(claim.id, db, {'user_id': str(ids['owner'])})
        with pytest.raises(HTTPException) as exc:
            await retry_claim(claim.id, db, {'user_id': str(ids['owner'])})
        assert exc.value.status_code == 409
    client.analyze_image = AsyncMock(side_effect=RuntimeError('private internal error'))
    await run_attempt(retried['attempt_id'], factory)
    async with factory() as db:
        claim = await db.get(Claim, ids['claim'])
        assert claim.status == ClaimStatus.PROCESSING_FAILED
        assert claim.damage_type is None and claim.estimated_cost_max is None
        assert all(img.processing_error == 'analysis_unavailable' for img in claim.images)
        assert all(img.detector_confidence is None for img in claim.images)
        assert await db.scalar(select(func.count()).select_from(ImageEvidence)) == 4
        assert await db.scalar(select(func.count()).select_from(FraudFlag)) == 1  # History retained.


@pytest.mark.asyncio
async def test_empty_detection_has_no_damage_or_estimate(factory, monkeypatch):
    ids = await seed(factory, images=1)
    attempt = await enqueue(factory, ids['claim'])
    fake_services(monkeypatch, [analysis(False)])
    await run_attempt(attempt, factory)
    async with factory() as db:
        claim = await db.get(Claim, ids['claim'])
        assert claim.status == ClaimStatus.AWAITING_REVIEW
        assert claim.analysis_outcome == 'no_visible_damage'
        assert claim.damage_type is None and claim.estimated_cost_max is None
        assert claim.detector_confidence is None


@pytest.mark.asyncio
async def test_annotation_failure_preserves_analysis(factory, monkeypatch):
    import base64
    ids = await seed(factory, images=1)
    attempt = await enqueue(factory, ids['claim'])
    result = analysis(); result['annotated_image_base64'] = base64.b64encode(image_bytes()).decode()
    client, storage = fake_services(monkeypatch, [result])
    def fail(*args):
        raise RuntimeError('storage unavailable')
    storage.upload_heatmap = fail
    await run_attempt(attempt, factory)
    async with factory() as db:
        claim = await db.get(Claim, ids['claim'])
        assert claim.status == ClaimStatus.AWAITING_REVIEW
        assert claim.images[0].annotation_error == 'annotation_unavailable'
        assert claim.images[0].processing_error is None


@pytest.mark.asyncio
async def test_duplicate_delivery_and_database_not_locked_during_inference(factory, monkeypatch):
    ids = await seed(factory, images=1)
    attempt = await enqueue(factory, ids['claim'])
    started, release = asyncio.Event(), asyncio.Event()
    async def delayed(**kwargs):
        started.set(); await release.wait(); return analysis()
    client, storage = fake_services(monkeypatch, None)
    client.analyze_image.side_effect = delayed
    task = asyncio.create_task(run_attempt(attempt, factory))
    await asyncio.wait_for(started.wait(), 3)
    assert (await run_attempt(attempt, factory))['status'] == 'skipped'
    async with factory() as db:
        await asyncio.wait_for(db.execute(update(User).where(User.id == ids['owner']).values(full_name='Updated')), 2)
        await db.commit()
    release.set()
    await task
    assert (await run_attempt(attempt, factory))['status'] == 'skipped'
    assert client.analyze_image.await_count == 1


@pytest.mark.asyncio
async def test_expired_lease_recovery_fences_stale_worker(factory):
    ids = await seed(factory)
    attempt = await enqueue(factory, ids['claim'])
    old = await acquire(factory, attempt)
    async with factory() as db:
        await db.execute(update(ProcessingAttempt).where(ProcessingAttempt.id == attempt).values(lease_until=now()-timedelta(seconds=1)))
        await db.commit()
    await reconcile(factory)
    new = await acquire(factory, attempt)
    assert old != new
    assert await finish(factory, attempt, old, []) is False
    async with factory() as db:
        assert (await db.get(Claim, ids['claim'])).status == ClaimStatus.PROCESSING
        assert (await db.get(ProcessingAttempt, attempt)).lease_token == new


@pytest.mark.asyncio
async def test_exhausted_crashed_job_is_retryable_failure(factory):
    ids = await seed(factory)
    attempt = await enqueue(factory, ids['claim'])
    await acquire(factory, attempt)
    async with factory() as db:
        await db.execute(update(ProcessingAttempt).where(ProcessingAttempt.id == attempt).values(run_count=3, lease_until=now()-timedelta(seconds=1)))
        await db.commit()
    await reconcile(factory)
    async with factory() as db:
        assert (await db.get(Claim, ids['claim'])).status == ClaimStatus.PROCESSING_FAILED
        assert (await db.get(ProcessingAttempt, attempt)).state == 'failed'


@pytest.mark.asyncio
async def test_broker_outage_keeps_durable_job(factory):
    ids = await seed(factory)
    attempt = await enqueue(factory, ids['claim'])
    def unavailable(attempt_id):
        raise RuntimeError('offline')
    await dispatch_due(factory, unavailable)
    async with factory() as db:
        job = await db.get(ProcessingAttempt, attempt)
        assert job.state == 'queued'
        assert (await db.get(Claim, ids['claim'])).current_attempt_id == attempt
        job.last_dispatched_at = now() - timedelta(seconds=31)
        await db.commit()
    published = []
    await dispatch_due(factory, published.append)
    assert published == [str(attempt)]
