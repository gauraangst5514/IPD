"""Gauraang app: real model/API integration using temporary local stores.

This does not open sockets and does not verify external Docker services.
"""
import base64
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"backend"),str(ROOT)]
os.environ.setdefault("YOLO_CONFIG_DIR",str(ROOT/"var/yolo"))
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/"var/matplotlib"))

def main():
    from fastapi.testclient import TestClient
    with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ,{
            "DATABASE_URL":"sqlite+aiosqlite:///"+temp+"/claims.sqlite3",
            "UPLOADS_DIR":temp+"/uploads","IMAGE_HISTORY_PATH":temp+"/history.sqlite3",
            "SECRET_KEY":"real-flow-test-only","DEBUG":"false","STORAGE_BACKEND":"local",
            "PROCESSING_MODE":"inline","GRAPH_BACKEND":"sql"}))
        from ml.serve import app as ml_app
        from app.main import app
        ml=stack.enter_context(TestClient(ml_app))
        assert ml.get("/health").json()["model_trained"]
        class Transport:
            async def health_check(self):return ml.get("/health").json()
            async def analyze_image(self,image_bytes,**fields):
                r=ml.post("/analyze",files={"file":("sample.jpg",image_bytes,"image/jpeg")},
                          data={k:str(v) for k,v in fields.items()})
                r.raise_for_status();return r.json()
            async def get_annotated_image(self,image_bytes):
                r=ml.post("/detect",files={"file":("sample.jpg",image_bytes,"image/jpeg")})
                r.raise_for_status();return r.content
            async def assess_structured(self,fields):
                r=ml.post("/tabular/assess",json={"fields":fields})
                r.raise_for_status();return r.json()
            async def explain_image(self,image_bytes):
                r=ml.post("/saliency",files={"file":("sample.jpg",image_bytes,"image/jpeg")})
                r.raise_for_status();return r.json()
        transport=Transport()
        stack.enter_context(patch("app.services.ml_client.get_ml_client",return_value=transport))
        stack.enter_context(patch("app.services.claim_processor.get_ml_client",return_value=transport))
        api=stack.enter_context(TestClient(app))
        registered=api.post("/api/v1/auth/register",json={
            "email":"smoke@example.com","password":"test-only-strong-password","full_name":"Synthetic smoke claimant"})
        registered.raise_for_status()
        auth={"Authorization":"Bearer "+registered.json()["access_token"]}
        vehicle=api.post("/api/v1/vehicles",headers=auth,json={
            "registration_number":"MH00TT1001","make":"Toyota","model":"Corolla","year":2022})
        vehicle.raise_for_status()
        fields={"incident_severity":"Minor Damage","incident_type":"Parked Car","insured_hobbies":"reading",
                "total_claim_amount":6200,"vehicle_claim":4100,"umbrella_limit":0,"policy_annual_premium":1120}
        sample=(ROOT/"data/demo/repository_sample_scratch.jpg").read_bytes()
        claims=[]
        for _ in range(2):
            r=api.post("/api/v1/claims",headers=auth,json={
                "vehicle_id":vehicle.json()["id"],"description":"Front bumper scratch",
                "structured_fields":fields,"invoice_text":"Repair | 2 | 1500\nPaint | 1 | 2000\nInvoice total: 5000"})
            r.raise_for_status();cid=r.json()["id"];claims.append(cid)
            uploaded=api.post("/api/v1/claims/"+cid+"/images",headers=auth,
                files={"file":("repository-sample.jpg",sample,"image/jpeg")})
            uploaded.raise_for_status()
            submitted=api.post("/api/v1/claims/"+cid+"/submit",headers=auth);submitted.raise_for_status()
        detail=api.get("/api/v1/claims/"+claims[1],headers=auth).json()
        assert detail["damage_type"]=="scratch",detail
        assert detail["fraud_risk_score"] is None
        duplicate=next(i for i in detail["fraud_flags"]["_indicators"] if i["code"]=="duplicate_image")
        assert duplicate["evidence"]["matches"][0]["claim_id"]==claims[0]
        # Internal fixture account creation; public role escalation remains forbidden.
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.models.user import User,UserRole
        from app.core.auth import create_access_token,hash_password
        assessor_id=uuid.uuid4()
        engine=create_engine("sqlite:///"+temp+"/claims.sqlite3")
        with Session(engine) as db:
            db.add(User(id=assessor_id,email="assessor-smoke@example.com",full_name="Synthetic assessor",
                        hashed_password=hash_password("test-only-password"),role=UserRole.ASSESSOR))
            db.commit()
        engine.dispose()
        assessor={"Authorization":"Bearer "+create_access_token({"sub":str(assessor_id),"role":"assessor"})}
        dossier=api.get("/api/v1/intelligence/claims/"+claims[1],headers=assessor).json()
        assert dossier["tabular"]["available"]
        assert dossier["tabular"]["graph_baseline"]["available"]
        assert dossier["invoice"]["available"]
        saliency=api.post("/api/v1/intelligence/images/"+detail["images"][0]["id"]+"/saliency",headers=assessor)
        saliency.raise_for_status();assert saliency.json()["available"]
        decoded=base64.b64decode(saliency.json()["image_data_url"].split(",",1)[1])
        assert decoded.startswith(b"\x89PNG")
        (ROOT/"var/gauraang_saliency.png").write_bytes(decoded)
        graph=api.get("/api/v1/intelligence/graph",headers=assessor);graph.raise_for_status()
        infrastructure=api.get("/api/v1/infrastructure",headers=assessor);infrastructure.raise_for_status()
        pdf=api.get("/api/v1/claims/"+claims[1]+"/pdf",headers=auth);pdf.raise_for_status()
        assert pdf.content.startswith(b"%PDF")
        decision=api.post("/api/v1/assessments",headers=assessor,
            json={"claim_id":claims[1],"decision":"escalated","notes":"Synthetic fixture: verify reuse context"})
        decision.raise_for_status()
        report={"real_yolo_inference":True,"detected_damage":detail["damage_type"],
                "raw_detection_confidence":detail["confidence_score"],
                "automatic_tabular_inference":True,"automatic_graphsage_inference":True,
                "invoice_parsing":True,"persistent_photograph_match":True,"actual_saliency_overlay":True,
                "claim_graph":True,"pdf":True,"assessor_decision":True,
                "stores_tested":["SQLite","local files","SQLite image history"],
                "external_docker_services_tested":False,"live_browser_tested":False,
                "detector_or_fraud_accuracy_evaluated":False}
        (ROOT/"var/gauraang_real_flow.json").write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))

if __name__=="__main__":main()
