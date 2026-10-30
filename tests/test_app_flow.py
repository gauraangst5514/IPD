"""Real API routes, SQLite, image evidence and PDFs; no trained-model claims.

The backend-to-ML HTTP boundary uses in-process TestClients so these tests need
no remote services, model downloads, Redis, MinIO or trained checkpoints.
"""
from contextlib import ExitStack
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

HAS_STACK = all(importlib.util.find_spec(m) for m in
    ("fastapi", "httpx", "sqlalchemy", "aiosqlite", "pydantic_settings", "jose",
     "bcrypt", "email_validator", "multipart", "boto3", "reportlab", "PIL", "numpy", "imagehash", "exifread"))


@unittest.skipUnless(HAS_STACK, "Install tests/requirements.txt for API-flow tests")
class AppFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.environment = patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///" + str(cls.root / "claims.sqlite3"),
            "UPLOADS_DIR": str(cls.root / "uploads"), "STORAGE_BACKEND": "local",
            "PROCESSING_MODE": "inline", "DEBUG": "false", "SECRET_KEY": "integration-test-only",
            "IMAGE_HISTORY_PATH": str(cls.root / "history.sqlite3"),
            "DAMAGE_MODEL_PATH": str(cls.root / "missing.pt"),
        })
        cls.environment.start()
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from fastapi.testclient import TestClient
        from app.main import app
        from ml.serve import app as ml_app
        cls.stack = ExitStack()
        cls.ml = cls.stack.enter_context(TestClient(ml_app))

        class InProcessMLClient:
            async def analyze_image(self, image_bytes, **fields):
                response = cls.ml.post("/analyze", files={"file": ("fixture.jpg", image_bytes, "image/jpeg")},
                    data={k: str(v) for k, v in fields.items()})
                response.raise_for_status()
                return response.json()

            async def get_annotated_image(self, image_bytes):
                response = cls.ml.post("/detect", files={"file": ("fixture.jpg", image_bytes, "image/jpeg")})
                response.raise_for_status()
                return response.content

            async def health_check(self):
                return cls.ml.get("/health").json()

            async def assess_structured(self, fields):
                response=cls.ml.post("/tabular/assess",json={"fields":fields})
                response.raise_for_status()
                return response.json()

        client = InProcessMLClient()
        cls.stack.enter_context(patch("app.services.ml_client.get_ml_client", return_value=client))
        cls.stack.enter_context(patch("app.services.claim_processor.get_ml_client", return_value=client))
        cls.api = cls.stack.enter_context(TestClient(app))

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()
        cls.environment.stop()
        cls.tmp.cleanup()

    def test_public_registration_cannot_create_assessor(self):
        response = self.api.post("/api/v1/auth/register", json={"email": "elevated@example.com",
            "password": "test-only-password", "full_name": "Test", "role": "admin"})
        self.assertEqual(response.status_code, 422)

    def test_claim_upload_reuse_pdf_and_assessor_review(self):
        from PIL import Image
        response = self.api.post("/api/v1/auth/register", json={"email": "claimant@example.com",
            "password": "test-only-password", "full_name": "Claimant"})
        self.assertEqual(response.status_code, 201, response.text)
        auth = {"Authorization": "Bearer " + response.json()["access_token"]}
        vehicle = self.api.post("/api/v1/vehicles", headers=auth,
            json={"registration_number": "MH00TT1001", "make": "Hyundai", "model": "i20", "year": 2022})
        self.assertEqual(vehicle.status_code, 201, vehicle.text)
        image = Image.new("RGB", (64, 64), (20, 100, 160))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        claims = []
        for index in range(2):
            response = self.api.post("/api/v1/claims", headers=auth, json={
                "vehicle_id": vehicle.json()["id"], "description": "Door scratch",
                "structured_fields":{"incident_severity":"Minor Damage","incident_type":"Parked Car",
                  "insured_hobbies":"reading","total_claim_amount":6200,"vehicle_claim":4100,
                  "umbrella_limit":0,"policy_annual_premium":1120},
                "invoice_text":"Repair | 2 | 500\nInvoice total: 1000"})
            self.assertEqual(response.status_code, 201, response.text)
            claim_id = response.json()["id"]
            claims.append(claim_id)
            if index == 0:
                invalid = self.api.post(f"/api/v1/claims/{claim_id}/images", headers=auth,
                    files={"file": ("bad.jpg", b"not an image", "image/jpeg")})
                self.assertEqual(invalid.status_code, 422)
            response = self.api.post(f"/api/v1/claims/{claim_id}/images", headers=auth,
                files={"file": ("fixture.jpg", buffer.getvalue(), "image/jpeg")})
            self.assertEqual(response.status_code, 200, response.text)
            response = self.api.post(f"/api/v1/claims/{claim_id}/submit", headers=auth)
            self.assertEqual(response.status_code, 200, response.text)
        detail = self.api.get(f"/api/v1/claims/{claims[1]}", headers=auth).json()
        self.assertEqual(detail["status"], "flagged")
        self.assertIsNone(detail["fraud_risk_score"])
        self.assertIsNone(detail["severity"])
        self.assertIsNone(detail["estimated_cost_min"])
        reuse = next(i for i in detail["fraud_flags"]["_indicators"] if i["code"] == "duplicate_image")
        self.assertEqual(reuse["evidence"]["matches"][0]["claim_id"], claims[0])
        self.assertEqual(self.api.get(detail["images"][0]["original_url"]).status_code, 200)
        pdf = self.api.get(f"/api/v1/claims/{claims[1]}/pdf", headers=auth)
        self.assertEqual(pdf.status_code, 200, pdf.text[:100] if pdf.status_code != 200 else "")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        forbidden = self.api.post("/api/v1/assessments", headers=auth,
            json={"claim_id": claims[1], "decision": "approved"})
        self.assertEqual(forbidden.status_code, 403)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.models.user import User, UserRole
        from app.core.auth import create_access_token, hash_password
        assessor_id = uuid.uuid4()
        sync_engine = create_engine("sqlite:///" + str(self.root / "claims.sqlite3"))
        with Session(sync_engine) as db:
            db.add(User(id=assessor_id, email="assessor@example.com", full_name="Assessor",
                hashed_password=hash_password("test-only-password"), role=UserRole.ASSESSOR))
            db.commit()
        sync_engine.dispose()
        assessor = {"Authorization": "Bearer " + create_access_token({"sub": str(assessor_id), "role": "assessor"})}
        automatic=self.api.get(f"/api/v1/intelligence/claims/{claims[1]}",headers=assessor)
        self.assertTrue(automatic.json()["tabular"]["available"],automatic.text)
        self.assertTrue(automatic.json()["invoice"]["available"])
        infrastructure=self.api.get("/api/v1/infrastructure",headers=assessor)
        self.assertEqual(infrastructure.status_code,200,infrastructure.text)
        self.assertEqual(infrastructure.json()["services"]["database"]["status"],"healthy")
        self.assertEqual(infrastructure.json()["services"]["graph"]["backend"],"sql")
        self.assertEqual(self.api.get("/api/v1/infrastructure",headers=auth).status_code,403)
        self.assertEqual(self.api.get("/api/v1/intelligence/graph", headers=auth).status_code, 403)
        graph = self.api.get("/api/v1/intelligence/graph", headers=assessor)
        self.assertEqual(graph.status_code, 200, graph.text)
        self.assertTrue(any(e["relation"] == "exact_file" for e in graph.json()["edges"]))
        invoice = self.api.post(f"/api/v1/intelligence/claims/{claims[1]}/invoice", headers=assessor,
            json={"text": "Repair | 2 | 500\nInvoice total: 1200"})
        self.assertEqual(invoice.status_code, 200, invoice.text)
        self.assertEqual(invoice.json()["calculated_subtotal"], 1000)
        dossier = self.api.get(f"/api/v1/intelligence/claims/{claims[1]}", headers=assessor)
        self.assertEqual(dossier.json()["invoice"]["declared_total"], 1200)
        structured = {"incident_severity": "Minor Damage", "incident_type": "Single Vehicle Collision",
            "insured_hobbies": "reading", "total_claim_amount": 10000, "vehicle_claim": 7000,
            "umbrella_limit": 0, "policy_annual_premium": 1200}
        tabular = self.api.post(f"/api/v1/intelligence/claims/{claims[1]}/tabular",
            headers=assessor, json=structured)
        self.assertEqual(tabular.status_code, 200, tabular.text)
        self.assertTrue(tabular.json()["available"])
        self.assertTrue(tabular.json()["contributions"])
        bad = self.api.post(f"/api/v1/intelligence/claims/{claims[1]}/tabular",
            headers=assessor, json={**structured, "fraud_reported": "Y"})
        self.assertEqual(bad.status_code, 422)
        self.assertIsNone(self.api.get(f"/api/v1/claims/{claims[1]}", headers=auth).json()["fraud_risk_score"])
        approved = self.api.post("/api/v1/assessments", headers=assessor,
            json={"claim_id": claims[1], "decision": "approved", "approved_amount": 0, "notes": "Synthetic test: permitted resubmission"})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertNotEqual(approved.json()["assessment_id"], "None")
        self.assertEqual(self.api.get(f"/api/v1/claims/{claims[1]}", headers=auth).json()["status"], "approved")


if __name__ == "__main__":
    unittest.main()
