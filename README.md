# IntelliClaim

AI-powered vehicle damage assessment and fraud detection platform for insurance claims — built for the Indian market.

## What It Does

1. Claimant uploads photos of damaged vehicle
2. AI detects damage type, location, and severity
3. Estimates repair cost based on vehicle model + region
4. Checks for fraud (fake images, duplicate claims, fraud rings)
5. Shows explainable heatmaps to human assessors
6. Produces a unified risk score
7. Assessor approves/rejects with full audit trail

## Architecture

```
intelliclaim/
├── backend/            # FastAPI backend API
│   ├── app/
│   │   ├── api/        # Route handlers
│   │   ├── models/     # SQLAlchemy / Pydantic models
│   │   ├── services/   # Business logic
│   │   └── core/       # Config, auth, dependencies
│   └── requirements.txt
├── frontend/           # React 18 + TypeScript dashboard
│   └── src/
├── ml/                 # ML models & inference
│   ├── damage/         # Damage detection & severity
│   ├── explainability/ # Grad-CAM heatmaps
│   ├── fraud/          # Image forensics + graph fraud
│   └── cost/           # Damage-to-cost estimation engine
├── data/               # Dataset scripts & sample data
└── docker-compose.yml  # Full local dev environment
```

## Moats

1. **Damage-to-Cost Mapping** — "Moderate dent on rear bumper of 2022 Hyundai Creta → ₹8,000–₹12,000"
2. **Fraud Graph** — Neo4j knowledge graph connecting claims, claimants, garages, agents
3. **India-Specific** — Indian plates, regional language docs, Indian vehicle pricing

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, PostgreSQL, Redis |
| Frontend | React 18, TypeScript, TailwindCSS |
| ML | PyTorch, OpenCV, torchvision |
| Explainability | Grad-CAM (pytorch-grad-cam), SHAP |
| Graph DB | Neo4j |
| OCR | PaddleOCR |
| Storage | MinIO (S3-compatible, for images) |
| Queue | Celery + Redis (async ML inference) |

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# ML inference server
cd ml && pip install -r requirements.txt && python serve.py
```
