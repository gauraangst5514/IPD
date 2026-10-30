"""Persist new ML evidence through the real claim-processing service and DB."""
import importlib.util
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

HAS_BACKEND = all(importlib.util.find_spec(m) for m in
    ("sqlalchemy", "aiosqlite", "pydantic_settings", "httpx", "boto3"))


@unittest.skipUnless(HAS_BACKEND, "Install tests/requirements.txt for backend integration tests")
class ClaimEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        os.environ["DEBUG"] = "false"
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.core.database import Base
        from app.models import User, Vehicle, Claim, ClaimImage
        from app.models.claim import ClaimStatus
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()
        user = User(id=uuid.uuid4(), email="test@example.com", full_name="Test", hashed_password="test")
        vehicle = Vehicle(id=uuid.uuid4(), owner_id=user.id, registration_number="MH01AB1234", make="Hyundai", model="i20", year=2022)
        self.claim = Claim(id=uuid.uuid4(), claimant_id=user.id, vehicle_id=vehicle.id,
            status=ClaimStatus.PROCESSING, description="door scratch", fraud_risk_score=0.7)
        self.image = ClaimImage(id=uuid.uuid4(), original_url="test.jpg", is_manipulated=True, manipulation_score=0.7)
        self.claim.images = [self.image]
        self.db.add_all([user, vehicle, self.claim])
        await self.db.flush()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def process(self, evidence, fail=False):
        from app.services.claim_processor import process_claim
        storage = MagicMock()
        storage.download_image.return_value = b"image"
        storage.upload_heatmap.return_value = "annotated.png"
        client = MagicMock()
        client.get_annotated_image = AsyncMock(return_value=b"annotated")
        client.analyze_image = AsyncMock(return_value={
            "damage_detected": True, "severity": "minor", "severity_score": 0.2,
            "primary_damage_type": "scratch", "detections": [],
            "cost_estimate_min": 1000, "cost_estimate_max": 2000,
            "fraud_score": None, "fraud_indicators": evidence,
        })
        if fail:
            client.analyze_image.side_effect = RuntimeError("test outage")
        with patch("app.services.claim_processor.get_storage_service", return_value=storage), \
             patch("app.services.claim_processor.get_ml_client", return_value=client), \
             patch("app.services.claim_processor.send_claim_notification"):
            await process_claim(str(self.claim.id), self.db)
        await self.db.commit()
        await self.db.refresh(self.claim)
        return client

    async def test_missing_exif_does_not_flag_claim_or_keep_old_score(self):
        from app.models.claim import ClaimStatus
        client = await self.process([{"code": "image_metadata", "status": "unavailable", "detail": "Absent", "evidence": {}}])
        self.assertIsNone(self.claim.fraud_risk_score)
        self.assertIsNone(self.image.manipulation_score)
        self.assertIsNone(self.image.is_manipulated)
        self.assertEqual(self.claim.status, ClaimStatus.AWAITING_REVIEW)
        self.assertFalse(self.claim.fraud_flags["_checks_complete"])
        self.assertEqual(client.analyze_image.call_args.kwargs["image_id"], str(self.image.id))

    async def test_duplicate_evidence_is_saved_and_routes_to_review(self):
        from app.models.claim import ClaimStatus
        await self.process([{"code": "duplicate_image", "status": "review", "detail": "Match",
            "evidence": {"matches": [{"claim_id": "previous", "image_id": "old"}]}}])
        self.assertEqual(self.claim.status, ClaimStatus.FLAGGED)
        self.assertTrue(self.image.is_duplicate)
        self.assertEqual(self.claim.fraud_flags["_indicators"][0]["evidence"]["matches"][0]["claim_id"], "previous")
        self.assertIsNone(self.claim.fraud_risk_score)

    async def test_failure_is_saved_as_unavailable(self):
        await self.process([], fail=True)
        self.assertFalse(self.claim.fraud_flags["_checks_complete"])
        self.assertEqual(self.claim.fraud_flags["_indicators"][0]["status"], "unavailable")
        self.assertIsNone(self.claim.fraud_risk_score)

    async def test_reprocessing_replaces_old_evidence(self):
        self.claim.fraud_flags = {"duplicate_image": True, "_indicators": [{"code": "old"}]}
        await self.process([{"code": "duplicate_image", "status": "not_observed", "detail": "No match", "evidence": {}}])
        self.assertNotIn("duplicate_image", self.claim.fraud_flags)
        self.assertEqual(len(self.claim.fraud_flags["_indicators"]), 1)


if __name__ == "__main__":
    unittest.main()
