"""ML service: independent evidence checks survive missing damage checkpoints."""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from ml.tabular.graph import GraphModel
from ml.model_registry import status as model_status, assess_structured

from ml.detection.detector import DamageDetector
from ml.fraud.image_forensics import ImageForensics
from ml.fraud.consistency_checker import ConsistencyChecker
from ml.fraud.vehicle_classifier import VehicleMakeClassifier
from ml.fraud.plate_reader import check_plate_match
from ml.cost.estimator import CostEstimationEngine
from ml.pipeline import AssessmentPipeline

pipeline = None
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(app):
    global pipeline
    from ml.fraud.tamper_detector import TamperDetector
    retrieval = get_retrieval_engine()
    pipeline = AssessmentPipeline(
        DamageDetector(), ImageForensics(), CostEstimationEngine(),
        ConsistencyChecker(), VehicleMakeClassifier(), check_plate_match, TamperDetector(), retrieval)
    yield


app = FastAPI(title="IntelliClaim ML Service", version="0.3.0", lifespan=lifespan)


class TabularFields(BaseModel):
    fields: dict


@app.post("/tabular/assess")
async def structured_assessment(request: TabularFields):
    try:
        return await run_in_threadpool(assess_structured,request.fields)
    except (ValueError,TypeError,KeyError):
        raise HTTPException(422,"Unsupported structured fields")


@app.post("/tabular/graph")
async def graph_assessment(request: TabularFields):
    try:
        return await run_in_threadpool(GraphModel().assess, request.fields)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, "Unsupported structured claim fields")


class DetectionOut(BaseModel):
    label: str
    confidence: float
    bbox: list[float]


class AnalysisResponse(BaseModel):
    damage_analysis_available: bool
    damage_detected: Optional[bool]
    num_instances: int
    detections: list[DetectionOut]
    severity: Optional[str]
    severity_score: Optional[float]
    severity_reasoning: dict
    severity_method: Optional[str]
    primary_damage_type: Optional[str]
    cost_estimate_min: Optional[float]
    cost_estimate_max: Optional[float]
    cost_breakdown: dict
    cost_method: Optional[str]
    component_status: dict
    fraud_score: Optional[float] = None
    score_type: str = "not_estimated"
    fraud_flags: list[str]
    fraud_indicators: list[dict]
    review_required: bool
    checks_complete: bool


async def read_image(file):
    from ml.image_input import open_upload
    from PIL import Image, UnidentifiedImageError
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Images must be 10 MB or smaller")
    try:
        with open_upload(content) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported image format")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError):
        raise HTTPException(422, "Upload a valid JPEG, PNG or WebP image")
    return content


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...), vehicle_make: str = Form(default=""),
    vehicle_year: int = Form(default=2022), region: str = Form(default="default"),
    claim_id: str = Form(default=""), image_id: str = Form(default=""),
    description: str = Form(default=""), registration_number: str = Form(default=""),
):
    content = await read_image(file)
    return await run_in_threadpool(pipeline.analyze, content, claim_id=claim_id,
        image_id=image_id, vehicle_make=vehicle_make, vehicle_year=vehicle_year,
        region=region, description=description, registration_number=registration_number)


@app.post("/detect")
async def detect_only(file: UploadFile = File(...)):
    content = await read_image(file)
    if not pipeline.detector.trained:
        raise HTTPException(409, "A trained damage checkpoint is not available")
    result = await run_in_threadpool(pipeline.detector.detect, content)
    return Response(content=result["annotated_image"], media_type="image/png")


@app.post("/forensics")
async def run_forensics(file: UploadFile = File(...), claim_id: str = Form(default=""),
                        image_id: str = Form(default="")):
    content = await read_image(file)
    return await run_in_threadpool(pipeline.forensics.full_analysis,
        content, claim_id=claim_id, image_id=image_id)


@app.get("/health")
async def health():
    return {
        "status": "healthy" if pipeline and pipeline.detector.trained else "degraded",
        "service": "intelliclaim-ml", "version": "0.3.0",
        "model_trained": bool(pipeline and pipeline.detector.trained),
        "components": model_status(pipeline),
    }


@app.post("/saliency")
async def saliency(file: UploadFile = File(...)):
    import base64
    from ml.explainability.occlusion import occlusion_saliency
    content = await read_image(file)
    if not pipeline.detector.trained:
        raise HTTPException(409, "Damage checkpoint unavailable")
    result = await run_in_threadpool(occlusion_saliency, pipeline.detector, content)
    if result is None:
        return {"available": False, "reason": "No detection available to explain"}
    return {"available": True, **{k:v for k,v in result.items() if k != "image"},
            "image_data_url": "data:image/png;base64," + base64.b64encode(result["image"]).decode()}

# Standalone evidence retrieval. Gallery access remains server-controlled.
_retrieval_engine = None

def get_retrieval_engine():
    global _retrieval_engine
    if _retrieval_engine is None:
        import os
        from pathlib import Path
        from ml.retrieval.engine import RetrievalEngine
        root = Path(__file__).resolve().parents[1]
        generali = root / 'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
        default_gallery = generali if generali.exists() else root / 'data/raw/tqvcd'
        if os.environ.get('IMAGE_DATABASE_URL'):
            from ml.retrieval.postgres_engine import PostgresRetrievalEngine
            _retrieval_engine = PostgresRetrievalEngine(os.environ.get('RETRIEVAL_GALLERY','/tmp/retrieval-gallery'))
        else:
            _retrieval_engine = RetrievalEngine(os.environ.get('RETRIEVAL_GALLERY', str(default_gallery)))
    return _retrieval_engine


@app.post('/retrieval/search')
async def retrieve_evidence(file: UploadFile = File(...), k: int = Form(5)):
    content = await read_image(file)
    if not 1 <= k <= 20:
        raise HTTPException(422, 'k must be between 1 and 20')
    engine = get_retrieval_engine()
    try:
        return await run_in_threadpool(engine.search, content, k)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.post('/retrieval/gallery/add')
async def add_gallery_photo(file: UploadFile = File(...), image_id: Optional[str] = Form(None)):
    content = await read_image(file)
    engine = get_retrieval_engine()
    try:
        return await run_in_threadpool(engine.add_image, content, image_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.get('/retrieval/stats')
async def retrieval_gallery_stats():
    engine = get_retrieval_engine()
    try:
        return await run_in_threadpool(engine.stats)
    except Exception as exc:
        raise HTTPException(500, f"Failed to read retrieval stats: {exc}")


@app.post('/evidence/inspect')
async def inspect_photograph(file: UploadFile = File(...), vehicle_make: str = Form(''), registration_number: str = Form('')):
    content=await read_image(file)
    from ml.fraud.plate_reader import check_plate_match
    def inspect():
        return {'vehicle_make':pipeline.vehicle_classifier.verify_make(content,vehicle_make),
                'plate':check_plate_match(content,registration_number),
                'tamper':pipeline.tamper_detector.analyze(content),
                'historical_photographs':get_retrieval_engine().search(content,k=3)}
    return await run_in_threadpool(inspect)
