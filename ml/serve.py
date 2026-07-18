"""
ML Inference Server

Separate FastAPI service that handles all ML inference.
The main backend calls this service for:
- Damage detection & localization (YOLOv8 on CarDD)
- Severity estimation (area-based heuristic)
- Cost estimation
- Fraud forensics
- Grad-CAM heatmaps (optional, for classification explainability)
"""

import io
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from ml.detection.detector import DamageDetector
from ml.fraud.image_forensics import ImageForensics
from ml.cost.estimator import CostEstimationEngine


# Global state
detector: Optional[DamageDetector] = None
forensics: Optional[ImageForensics] = None
cost_engine: Optional[CostEstimationEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global detector, forensics, cost_engine

    print("🔧 Loading models...")
    detector = DamageDetector()  # auto-detects device, falls back if untrained
    forensics = ImageForensics()
    cost_engine = CostEstimationEngine()
    print("✅ All models loaded")
    yield
    print("👋 Shutting down ML service")


app = FastAPI(title="IntelliClaim ML Service", version="0.2.0", lifespan=lifespan)


class DetectionOut(BaseModel):
    label: str
    confidence: float
    bbox: list[float]


class AnalysisResponse(BaseModel):
    damage_detected: bool
    num_instances: int
    detections: list[DetectionOut]
    severity: str
    severity_score: float
    severity_reasoning: dict
    primary_damage_type: str
    cost_estimate_min: float
    cost_estimate_max: float
    cost_breakdown: dict
    fraud_score: float
    fraud_flags: list[str]


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    vehicle_make: str = Form(default="hyundai"),
    vehicle_year: int = Form(default=2022),
    region: str = Form(default="mumbai"),
    claim_id: str = Form(default=""),
):
    """
    Full analysis pipeline for a single image:
    detection -> severity -> cost -> fraud.
    """
    image_bytes = await file.read()

    # 1. Damage detection + severity
    detection_result = detector.detect(image_bytes)

    # 2. Cost estimation (driven by primary damage type + severity)
    cost_result = cost_engine.estimate(
        damage_type=detection_result["primary_damage_type"],
        severity=detection_result["severity"],
        vehicle_make=vehicle_make,
        vehicle_year=vehicle_year,
        region=region,
    )

    # 3. Fraud analysis
    fraud_result = forensics.full_analysis(image_bytes, claim_id=claim_id)

    return AnalysisResponse(
        damage_detected=detection_result["damage_detected"],
        num_instances=detection_result["num_instances"],
        detections=detection_result["detections"],
        severity=detection_result["severity"],
        severity_score=detection_result["severity_score"],
        severity_reasoning=detection_result["severity_reasoning"],
        primary_damage_type=detection_result["primary_damage_type"],
        cost_estimate_min=cost_result.min_cost,
        cost_estimate_max=cost_result.max_cost,
        cost_breakdown=cost_result.breakdown,
        fraud_score=fraud_result["overall_manipulation_score"],
        fraud_flags=fraud_result["metadata_flags"],
    )


@app.post("/detect")
async def detect_only(
    file: UploadFile = File(...),
):
    """Run detection only and return the annotated image with boxes drawn."""
    image_bytes = await file.read()
    result = detector.detect(image_bytes)
    return Response(content=result["annotated_image"], media_type="image/png")


@app.post("/forensics")
async def run_forensics(
    file: UploadFile = File(...),
    claim_id: str = Form(default=""),
):
    """Run image forensics analysis only."""
    image_bytes = await file.read()
    result = forensics.full_analysis(image_bytes, claim_id=claim_id)
    return result


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "detector_loaded": detector is not None,
        "model_trained": detector.trained if detector else False,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ml.serve:app", host="0.0.0.0", port=8001, reload=True)
