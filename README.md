# IntelliClaim

AI-powered vehicle damage assessment and fraud detection platform for insurance claims — built for the Indian market.

## What It Does

1. Claimant uploads photos of damaged vehicle
2. AI detects damage type, location, and severity (YOLOv8m, multi-scale inference)
3. Estimates repair cost based on damage area, vehicle make, age, and region
4. Checks for fraud (7-layer pipeline):
   - Image manipulation (ELA + EXIF forensics)
   - Duplicate image detection (perceptual hashing)
   - Vehicle make verification (EfficientNet-B0, 49 makes, 93% accuracy)
   - Description vs damage consistency (NLP keyword matching)
   - Severity mismatch detection
   - License plate OCR cross-reference (EasyOCR, optional)
   - Damage count consistency
5. Shows interactive before/after comparison slider (original vs AI detection)
6. Animated fraud risk timeline showing each check result
7. Detailed damage breakdown with per-type confidence and coverage
8. Assessor approves/rejects with full audit trail
9. PDF report download for each claim
10. Email notifications on status changes

## Screenshots

The claim detail page features:
- **Before/After Slider** — drag to compare original photo with AI detection overlay
- **Damage Breakdown** — per-type cards with confidence bars and area coverage
- **Fraud Timeline** — animated sequential check results
- **Cost Estimate** — parts/labour/paint breakdown with India-specific pricing

## Architecture

```
intelliclaim/
├── backend/            # FastAPI backend API
│   ├── app/
│   │   ├── api/        # Route handlers (auth, claims, vehicles, assessments, stats)
│   │   ├── models/     # SQLAlchemy models (User, Claim, Vehicle, FraudFlag)
│   │   ├── services/   # Business logic (claim_processor, ml_client, storage, notifications, pdf_report)
│   │   └── core/       # Config, auth (JWT + bcrypt), database
│   └── requirements.txt
├── frontend/           # React 18 + TypeScript dashboard
│   └── src/
│       ├── components/ # Layout, ImageCompareSlider, FraudTimeline, VehicleDamageMap
│       ├── pages/      # Dashboard, Claims, NewClaim, ClaimDetail, ReviewQueue, Login
│       ├── store/      # Zustand auth state (persisted to localStorage)
│       └── lib/        # Axios API client with auth interceptor
├── ml/                 # ML models & inference
│   ├── detection/      # YOLOv8m damage detector (6 classes, multi-scale inference)
│   ├── fraud/          # Image forensics + vehicle classifier + plate reader + consistency checker
│   ├── cost/           # Damage-to-cost estimation engine v2 (area-aware, India-specific)
│   └── weights/        # Trained model weights
├── data/               # CarDD dataset (YOLO format)
├── notebooks/          # Kaggle training notebooks
└── docker-compose.yml  # Full production deployment
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI, SQLite (dev) / PostgreSQL (prod) |
| Frontend | React 18, TypeScript, TailwindCSS, React Query, Zustand |
| ML - Damage | YOLOv8m (ultralytics), multi-scale inference (800+1024px) |
| ML - Vehicle ID | EfficientNet-B0 (timm), 49 makes, 93.2% accuracy |
| ML - Fraud | ELA, EXIF, perceptual hashing, NLP consistency |
| ML - OCR | EasyOCR (optional, for license plates) |
| Storage | Local filesystem (dev) / MinIO S3-compatible (prod) |
| Queue | Celery + Redis (optional, falls back to sync) |
| Email | SMTP (optional, falls back to console logging) |
| PDF | ReportLab |

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- pip

### 1. Install Backend

```bash
cd backend
pip install -r requirements.txt
pip install aiosqlite bcrypt email-validator boto3 reportlab
```

### 2. Install ML Dependencies

```bash
pip install ultralytics timm imagehash exifread opencv-python
```

### 3. Install Frontend

```bash
cd frontend
npm install
```

### 4. Start All Services (3 terminals)

```bash
# Terminal 1 — Backend API
cd backend
python3 -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — ML Service
python3 -m uvicorn ml.serve:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3 — Frontend
cd frontend
npx vite --port 5173
```

### 5. Create Demo Users

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@intelliclaim.com","password":"admin123","full_name":"Admin User","role":"admin"}'

curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"assessor@intelliclaim.com","password":"assessor123","full_name":"Rahul Sharma","role":"assessor"}'

curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"claimant@intelliclaim.com","password":"claimant123","full_name":"Priya Patel","role":"claimant"}'
```

### 6. Open the App

Go to **http://localhost:5173** and log in.

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@intelliclaim.com | admin123 |
| Assessor | assessor@intelliclaim.com | assessor123 |
| Claimant | claimant@intelliclaim.com | claimant123 |

## ML Models

### Damage Detection (YOLOv8m)

- **Dataset:** CarDD (2252 train / 281 val / 283 test images)
- **Classes:** dent, scratch, crack, glass_shatter, lamp_broken, tire_flat
- **Inference:** Multi-scale (800px + 1024px) with cross-scale confidence boosting
- **Performance:** mAP@50 ~0.68, mAP@50-95 ~0.49
- **Weights:** `ml/weights/detection/cardd_yolov8/weights/best.pt`

### Vehicle Make Classifier (EfficientNet-B0)

- **Dataset:** Stanford Cars (8144 train / 8041 test) → grouped into 49 makes
- **Makes:** BMW, Rolls Royce, Hyundai, Mercedes-Benz, Audi, Toyota, Honda, etc.
- **Indian makes:** Maruti/Suzuki equivalence, Tata/Mahindra graceful handling
- **Performance:** 93.2% accuracy at make level
- **Weights:** `ml/weights/vehicle_make/vehicle_make_classifier.pt`

## Fraud Detection Pipeline

Each uploaded image goes through 7 checks:

| # | Check | Method | Flag |
|---|-------|--------|------|
| 1 | Image manipulation | Error Level Analysis (ELA) | `high_ela_score` |
| 2 | Missing/edited metadata | EXIF parsing | `exif_inconsistency` |
| 3 | Reused image | Perceptual hashing (pHash + dHash) | `duplicate_image` |
| 4 | Wrong vehicle | EfficientNet make classifier (93% acc) | `vehicle_make_mismatch` |
| 5 | Description mismatch | Keyword NLP vs detected damage type | `description_mismatch` |
| 6 | Severity mismatch | Claimed severity vs AI severity | `severity_mismatch` |
| 7 | License plate | EasyOCR + Indian plate regex | `plate_number_mismatch` |

Combined fraud score determines claim routing:
- Score > 0.7 → Claim **FLAGGED** (requires manual review)
- Score ≤ 0.7 → Claim goes to **AWAITING_REVIEW**

## Cost Estimation Engine v2

Factors used for repair cost calculation:
- **Damage type + severity** (base pricing from Indian workshops)
- **Damage area coverage** (from YOLO bounding box sizes)
- **Number of instances** (multi-panel = more expensive)
- **Vehicle make segment** (Maruti 1.0× → BMW 2.8× → Rolls Royce 5.0×)
- **Vehicle age** (depreciation: new 1.0× → 8+ years 0.6×)
- **Regional labour rates** (Mumbai 1.35× → Tier 3 city 0.95×)
- **Variance range** (±12% minor, ±15% moderate, ±20% severe)

## Frontend Features

- **Split-screen login** with branding panel and feature list
- **Dark sidebar** with role-based navigation
- **Dashboard** with stats cards, avg fraud score, recent claims
- **Before/After comparison slider** — drag to reveal AI detection overlay
- **Animated fraud timeline** — checks appear sequentially with pass/fail icons
- **Damage breakdown cards** — per-type confidence bars and coverage stats
- **PDF download** — full claim report with assessment, cost, and fraud analysis
- **Responsive design** with Inter font, refined colour palette, hover states

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register new user |
| POST | /api/v1/auth/login | Login (returns JWT) |
| GET | /api/v1/stats | Dashboard statistics |
| GET | /api/v1/claims | List claims (filtered by role) |
| POST | /api/v1/claims | Create a new claim |
| POST | /api/v1/claims/:id/images | Upload damage image |
| POST | /api/v1/claims/:id/submit | Submit for AI processing |
| GET | /api/v1/claims/:id | Get claim details + AI results |
| GET | /api/v1/claims/:id/pdf | Download claim report as PDF |
| GET | /api/v1/vehicles | List user's vehicles |
| POST | /api/v1/vehicles | Register a vehicle |
| POST | /api/v1/assessments | Submit assessor decision |
| GET | /api/v1/assessments/queue | Review queue (sorted by fraud risk) |

## Retraining Models

Kaggle notebooks (free GPU T4) are in `notebooks/`:

- `train_cardd_kaggle.ipynb` — Retrain damage detector (YOLOv8m, ~1.5hr)
- `train_vehicle_classifier_kaggle.ipynb` — Retrain vehicle make classifier (EfficientNet-B0, ~30min)

See `notebooks/TRAINING_IMPROVEMENTS.md` for hyperparameter details.

## Production Deployment

```bash
# Generate secret key
export SECRET_KEY=$(openssl rand -hex 32)

# Build and start all services
docker-compose up --build -d

# Services: frontend(80), backend(8000), ml(8001), postgres(5432), redis(6379), neo4j(7474), minio(9000)
```

## Project Status

### Implemented
- ✅ Full-stack claim submission and review workflow
- ✅ YOLOv8m damage detection (6 classes, multi-scale inference)
- ✅ Vehicle make verification (49 makes, 93% accuracy)
- ✅ 7-layer fraud detection pipeline
- ✅ Area-aware cost estimation (India-specific, 35+ makes, 20+ cities)
- ✅ Before/After image comparison slider
- ✅ Animated fraud risk timeline
- ✅ Damage breakdown visualization
- ✅ PDF claim report download
- ✅ Email notifications (SMTP, optional)
- ✅ OCR license plate reading (EasyOCR, optional)
- ✅ Indian vehicle make support (Maruti, Tata, Mahindra, etc.)
- ✅ JWT auth with role-based access (claimant/assessor/admin)
- ✅ Dashboard with stats, fraud metrics, recent claims
- ✅ Production Docker Compose (8 services)
- ✅ Kaggle training notebooks

### Not Yet Implemented
- ❌ Neo4j fraud graph (fraud rings, repeat claimants)
- ❌ Real-time WebSocket progress updates during processing
