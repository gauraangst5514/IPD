"""Private inference API: validated uploads, explicit abstention and check coverage."""
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.responses import Response, JSONResponse
from shared.contracts import AnalysisResult
from shared.image_validation import validate_upload
from shared.request_limits import RequestSizeLimit
from ml.config import get_settings
from ml.detection.detector import DamageDetector
from ml.cost.estimator import CostEstimationEngine
from ml.fraud.consistency_checker import ConsistencyChecker
from ml.fraud.vehicle_classifier import VehicleMakeClassifier
from ml.fraud.plate_reader import check_plate_match, EASYOCR_AVAILABLE
from ml.pipeline import analyze

logger = logging.getLogger(__name__)
settings = get_settings()
detector = None
forensics = None
cost_engine = CostEstimationEngine()
consistency_checker = ConsistencyChecker()
vehicle_classifier = VehicleMakeClassifier()


@asynccontextmanager
async def lifespan(app):
    global detector, forensics
    try:
        detector = DamageDetector()
    except Exception:
        logger.exception('Damage detector unavailable')
        detector = None
    try:
        from ml.fraud.image_forensics import ImageForensics
        forensics = ImageForensics()
    except ImportError:
        logger.warning('Optional forensics dependencies unavailable')
        forensics = None
    yield


app = FastAPI(title='IntelliClaim ML', version='0.3.0', lifespan=lifespan)
app.add_middleware(RequestSizeLimit, max_bytes=settings.MAX_UPLOAD_BYTES + 256 * 1024)


async def service_auth(x_service_key: str = Header(default='')):
    if settings.ML_API_KEY and not secrets.compare_digest(x_service_key, settings.ML_API_KEY):
        raise HTTPException(401, 'Invalid service credentials')
    if not settings.ML_API_KEY and settings.APP_ENV != 'development':
        raise HTTPException(503, 'Service credentials unavailable')


async def read_image(file):
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    await asyncio.to_thread(validate_upload, content, file.content_type, settings)
    return content


@app.post('/analyze', response_model=AnalysisResult, dependencies=[Depends(service_auth)])
async def analyze_image(
    file: UploadFile = File(...), vehicle_make: str = Form(default='hyundai'),
    vehicle_year: int = Form(default=2022), region: str = Form(default='default'),
    claim_id: str = Form(default=''), description: str = Form(default=''),
    registration_number: str = Form(default=''),
):
    if detector is None:
        raise HTTPException(503, 'Damage model unavailable')
    content = await read_image(file)
    return await asyncio.to_thread(
        analyze, content, detector=detector, forensics=forensics, cost_engine=cost_engine,
        consistency_checker=consistency_checker, vehicle_classifier=vehicle_classifier,
        plate_check=check_plate_match, vehicle_make=vehicle_make, vehicle_year=vehicle_year,
        region=region, claim_id=claim_id, description=description,
        registration_number=registration_number,
    )


@app.post('/detect', dependencies=[Depends(service_auth)])
async def detect_only(file: UploadFile = File(...)):
    if detector is None:
        raise HTTPException(503, 'Damage model unavailable')
    result = await asyncio.to_thread(detector.detect, await read_image(file))
    return Response(result['annotated_image'], media_type='image/png')


@app.post('/forensics', dependencies=[Depends(service_auth)])
async def run_forensics(file: UploadFile = File(...), claim_id: str = Form(default='')):
    if forensics is None:
        raise HTTPException(503, 'Forensics unavailable')
    return await asyncio.to_thread(forensics.full_analysis, await read_image(file), claim_id=claim_id)


@app.get('/health')
async def health():
    return {'status': 'healthy' if detector else 'model_unavailable',
            'detector_loaded': detector is not None,
            'model_provenance': detector.provenance if detector else None,
            'components': {'severity': 'heuristic', 'cost': 'provisional_heuristic',
                           'forensics': 'heuristic' if forensics else 'unavailable',
                           'vehicle_make': 'loaded' if vehicle_classifier.loaded else 'unavailable',
                           'plate': 'optional_ocr' if EASYOCR_AVAILABLE else 'unavailable'}}


@app.get('/ready')
async def readiness():
    return JSONResponse(await health(), status_code=200 if detector else 503)
