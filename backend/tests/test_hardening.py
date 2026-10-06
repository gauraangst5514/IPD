import os
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from PIL import Image
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.database import Base, get_db
from app.core.auth import get_current_user
from app.core.config import Settings
from app.models import User, Vehicle, Claim, ClaimImage
from app.models.claim import ClaimStatus, DamageType
from app.api.auth import RegisterRequest
from app.api import claims
from app.services.upload_validation import validate_upload
from app.services import claim_processor as processor
from ml.detection.detector import DamageDetector, ModelUnavailableError
from ml.detection.severity import SeverityEstimator, DamageInstance
from ml.cost.estimator import CostEstimationEngine

@pytest.mark.parametrize('role', ['admin', 'assessor'])
def test_public_privilege_rejected(role):
    with pytest.raises(ValidationError):
        RegisterRequest(email='user@example.com', password='password', full_name='User', role=role)


def image_bytes():
    out = io.BytesIO(); Image.new('RGB', (20, 20)).save(out, format='PNG'); return out.getvalue()

@pytest.mark.parametrize('content,mime,limits,code', [
    (b'bad', 'image/png', {}, 400),
    (image_bytes(), 'image/jpeg', {}, 415),
    (image_bytes(), 'text/plain', {}, 415),
    (image_bytes(), 'image/png', {'MAX_UPLOAD_BYTES': 4}, 413),
    (image_bytes(), 'image/png', {'MAX_IMAGE_PIXELS': 10}, 413),
])
def test_upload_rejections(content, mime, limits, code):
    with pytest.raises(HTTPException) as exc:
        validate_upload(content, mime, Settings(_env_file=None, **limits))
    assert exc.value.status_code == code


def test_valid_upload():
    assert validate_upload(image_bytes(), 'image/png', Settings(_env_file=None)) == (20, 20, '.png')


def test_missing_model_abstains(tmp_path):
    with pytest.raises(ModelUnavailableError):
        DamageDetector(str(tmp_path / 'missing.pt'))

@pytest.mark.parametrize('label', ['tire_flat', 'lamp_broken', 'glass_shatter'])
def test_damage_mapping_and_cost(label):
    primary = SeverityEstimator().primary_damage_type([DamageInstance(label, .8, (.5, .5, .2, .2))])
    assert primary == label
    assert processor.DAMAGE_TYPE_MAP[primary].value == label
    cost = CostEstimationEngine().estimate(damage_type=primary, severity='moderate', vehicle_make='tata', vehicle_year=2022)
    assert cost.max_cost > 0


def test_production_default_secrets_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="production", DEBUG=False)

@pytest.mark.asyncio
async def test_ownership_upload_limits_and_processing(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email='one@example.com', hashed_password='x', full_name='One')
        other = User(email='two@example.com', hashed_password='x', full_name='Two')
        db.add_all([user, other]); await db.flush()
        own = Vehicle(owner_id=user.id, registration_number='ONE', make='tata', model='x', year=2022)
        foreign = Vehicle(owner_id=other.id, registration_number='TWO', make='tata', model='x', year=2022)
        db.add_all([own, foreign]); await db.flush()
        auth = {'user_id': str(user.id), 'role': 'claimant'}
        for vehicle_id in (foreign.id, uuid.uuid4()):
            with pytest.raises(HTTPException) as exc:
                await claims.create_claim(claims.ClaimCreateRequest(vehicle_id=vehicle_id), db, auth)
            assert exc.value.status_code == 404
        created = await claims.create_claim(claims.ClaimCreateRequest(vehicle_id=own.id), db, auth)
        claim = await db.get(Claim, uuid.UUID(created['id']))
        await db.refresh(claim, ['images'])
        with pytest.raises(HTTPException):
            await claims.submit_claim(str(claim.id), db, auth)
        from starlette.datastructures import UploadFile, Headers
        monkeypatch.setattr(claims, 'get_settings', lambda: Settings(_env_file=None, MAX_IMAGES_PER_CLAIM=1))
        import app.services.storage as storage_module
        storage = SimpleNamespace(upload_image=lambda *args: {'key':'test.png', 'url':'url', 'file_hash':'hash'}, download_image=lambda key: b'image')
        monkeypatch.setattr(storage_module, 'get_storage_service', lambda: storage)
        def upload():
            return UploadFile(io.BytesIO(image_bytes()), filename='../../evil.png', headers=Headers({'content-type':'image/png'}))
        first = await claims.upload_claim_image(str(claim.id), upload(), db, auth)
        repeated = await claims.upload_claim_image(str(claim.id), upload(), db, auth)
        assert first["image_id"] == repeated["image_id"]
        alternate = io.BytesIO()
        Image.new("RGB", (20,20), "red").save(alternate, format="PNG")
        with pytest.raises(HTTPException) as exc:
            await claims.upload_claim_image(str(claim.id), UploadFile(io.BytesIO(alternate.getvalue()), filename="red.png", headers=Headers({"content-type":"image/png"})), db, auth)
        assert exc.value.status_code == 409
    await engine.dispose()


def test_registration_api_rejects_privileged_roles_before_db():
    from app.api import auth
    app = FastAPI(); app.include_router(auth.router)
    def forbidden_db():
        yield None
    app.dependency_overrides[get_db] = forbidden_db
    with TestClient(app) as client:
        for role in ('admin', 'assessor'):
            response = client.post('/register', json=dict(email='one@example.com', password='password', full_name='One', role=role))
            assert response.status_code == 422


def test_wrong_model_metadata_rejected(tmp_path, monkeypatch):
    import sys
    weights = tmp_path / 'generic.pt'; weights.write_bytes(b'test')
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=lambda path: SimpleNamespace(names={0: 'person'})))
    with pytest.raises(ModelUnavailableError, match='metadata'):
        DamageDetector(str(weights), device='cpu')
