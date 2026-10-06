import uuid
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.auth import create_access_token, get_current_user
from app.models import User
from app.models.claim import ClaimStatus
from app.api.assessments import AssessmentRequest, submit_assessment
from app.api.claims import get_image_content
from helpers import seed, image_bytes


@pytest.mark.asyncio
async def test_live_account_role_and_revocation(factory):
    ids = await seed(factory)
    token = create_access_token({'sub': str(ids['owner']), 'role': 'admin'})
    async with factory() as db:
        assert (await get_current_user(token, db))['role'] == 'claimant'
        user = await db.get(User, ids['owner'])
        user.token_version += 1
        await db.commit()
        with pytest.raises(HTTPException) as error:
            await get_current_user(token, db)
        assert error.value.status_code == 401
        user.token_version = 0
        user.is_active = False
        await db.commit()
        with pytest.raises(HTTPException):
            await get_current_user(token, db)


@pytest.mark.asyncio
async def test_images_are_private(factory, monkeypatch):
    ids = await seed(factory)
    payload = image_bytes()
    class Storage:
        def download_image(self, key):
            return payload
    monkeypatch.setattr('app.services.storage.get_storage_service', lambda: Storage())
    async with factory() as db:
        response = await get_image_content(ids['claim'], ids['images'][0], 'original', db,
            {'user_id': str(ids['owner']), 'role': 'claimant'})
        assert response.body == payload
        assert response.headers['cache-control'] == 'private, no-store'
        with pytest.raises(HTTPException) as error:
            await get_image_content(ids['claim'], ids['images'][0], 'original', db,
                {'user_id': str(ids['stranger']), 'role': 'claimant'})
        assert error.value.status_code == 404


@pytest.mark.parametrize('values', [
    {'decision':'anything'}, {'decision':'approved', 'approved_amount':-1},
    {'decision':'approved', 'approved_amount':float('nan')}, {'decision':'approved'},
    {'decision':'rejected', 'approved_amount':100},
])
def test_invalid_assessment(values):
    with pytest.raises(ValidationError):
        AssessmentRequest(claim_id=uuid.uuid4(), expected_version=0, **values)


@pytest.mark.asyncio
async def test_assessment_version_and_self_review(factory, monkeypatch):
    ids = await seed(factory, status=ClaimStatus.AWAITING_REVIEW)
    monkeypatch.setattr('app.api.assessments.send_claim_notification', lambda **kwargs: None)
    request = AssessmentRequest(claim_id=ids['claim'], decision='approved', approved_amount=100, expected_version=0)
    async with factory() as db:
        with pytest.raises(HTTPException) as error:
            await submit_assessment(request, db, {'user_id':str(ids['owner']), 'role':'admin'})
        assert error.value.status_code == 403
    async with factory() as db:
        assert (await submit_assessment(request, db, {'user_id':str(ids['reviewer']), 'role':'assessor'}))['decision'] == 'approved'
    async with factory() as db:
        with pytest.raises(HTTPException) as error:
            await submit_assessment(request, db, {'user_id':str(ids['reviewer']), 'role':'assessor'})
        assert error.value.status_code == 409
