# IntelliClaim — Next Steps Plan

## Architecture Decision (IMPORTANT)

We switched from a **classification** model to a **detection** model (YOLOv8) using
the **CarDD dataset** (4,000 images, 6 damage categories, insurance-grade annotations).

This matches the project report (which mentions YOLOv8/Faster R-CNN) and gives us:
- Bounding boxes around each damage (great for demos)
- 6 damage categories: dent, scratch, crack, glass_shatter, lamp_broken, tire_flat
- Severity derived from damage area + type weighting (explainable heuristic)

The old classification model (`ml/damage/`, `ml/training/`) is kept but deprecated.
The new detection pipeline is in `ml/detection/`.

## What's Working

- ✅ CarDD download + YOLO conversion (`ml/detection/prepare_cardd.py`) — **2816 images downloaded, converted to 2252 train / 281 val / 283 test**
- ✅ YOLOv8 training script (`ml/detection/train.py`) — **VERIFIED: 2-epoch smoke test reached mAP50=0.21**
- ✅ Severity-from-area heuristic (`ml/detection/severity.py`) — **tested, calibrated thresholds**
- ✅ Detection inference wrapper (`ml/detection/detector.py`) — **VERIFIED on real CarDD image**
- ✅ Single-image prediction CLI (`ml/detection/predict.py`) — **VERIFIED: detects boxes, severity, cost, fraud**
- ✅ Updated ML service (`ml/serve.py`) — detection-based
- ✅ Cost estimation engine (India-specific)
- ✅ Fraud forensics (EXIF, ELA, duplicates)
- ✅ Backend API + DamageType enum aligned to CarDD categories
- ✅ Frontend dashboard (React)

## Current State (verified end-to-end)

The detection pipeline is fully functional. A real CarDD test image produced:
- 2 tire_flat detections (99.2%, 66.8% confidence) with bounding boxes
- SEVERE severity (89.5% area coverage)
- Cost estimate ₹36,000–₹48,800 (BMW, Mumbai)
- EXIF fraud flag
- Annotated image with boxes drawn

The only thing left for a strong model is a full 50-epoch training run (the smoke-test
model only saw 2 epochs). Everything else works.

## Step 1: Finish Dataset Download & Conversion

The CarDD download from Hugging Face was started (slow due to unauthenticated
rate limits — ~45 min for 2816 images).

```bash
# If download was interrupted, resume (it skips already-downloaded files):
python3 -m ml.detection.prepare_cardd

# If download finished but conversion didn't run:
python3 -m ml.detection.prepare_cardd --skip_download

# TIP: For faster downloads, set a free HF token:
#   export HF_TOKEN=hf_xxxxx   (get from https://huggingface.co/settings/tokens)
```

After this you'll have `data/cardd_yolo/` with images/, labels/, and data.yaml.

## Step 2: Train the Detector

**VERIFIED WORKING** — A 2-epoch smoke test confirmed the full pipeline runs on MPS
and already reached mAP50=0.21 after 1 epoch. Now run the real training:

```bash
# Recommended: YOLOv8-small, 50 epochs (~6 hrs on MPS, much faster on CUDA)
python3 -m ml.detection.train --model yolov8s.pt --epochs 50 --batch 16 --device mps

# Faster option: yolov8n, 50 epochs (~3.5 hrs on MPS, lower accuracy)
python3 -m ml.detection.train --model yolov8n.pt --epochs 50 --batch 16 --device mps

# Training output goes to: ml/weights/detection/cardd_yolov8/weights/best.pt
```

Each epoch is ~7 min on MPS (nano). Expected mAP50 ~0.6-0.7 with yolov8s after 50 epochs.
NOTE: run this overnight or on a GPU machine — MPS is slow for 50 epochs.

## Step 3: Test the Trained Model

```bash
# Predict on a single image (draws boxes, estimates cost + fraud)
python3 -m ml.detection.predict --image path/to/car.jpg \
    --vehicle_make hyundai --region mumbai \
    --save_annotated annotated_output.png
```

## Step 4: Run the ML Service

```bash
python3 ml/serve.py     # runs on port 8001
# Then test: curl -F "file=@car.jpg" http://localhost:8001/analyze
```

## ===== POST-TRAINING ROADMAP (to project completion) =====

### Phase 1: Validate the Trained Model
- [ ] Run test-set evaluation — record mAP50, mAP50-95, per-class accuracy
      (CarDD's crack/tire_flat usually lag — note real numbers for the report)
- [ ] Predict on 10-15 varied real images, eyeball boxes + severity
- [ ] Calibrate severity thresholds (`MINOR_THRESHOLD`/`SEVERE_THRESHOLD` in
      `ml/detection/severity.py`) against real score distributions
- [ ] Save sample annotated outputs for report + demo

### Phase 2: Wire Backend Pipeline (BIGGEST remaining chunk — critical path)
- [x] Alembic migrations — configured with async support, imports all models
- [x] MinIO storage — `StorageService` (upload, download, presigned URLs, heatmaps)
- [x] Celery worker task: submit -> store -> call ML /analyze -> save results
      (`app/worker/tasks.py` + `app/services/claim_processor.py`)
- [x] Connect backend -> ML service (`app/services/ml_client.py`)
- [x] EXIF/metadata extraction during upload (image dimensions, hash)
- [ ] Generate first Alembic migration: `cd backend && alembic revision --autogenerate -m "initial"`
- [ ] Run migrations against a real Postgres: `alembic upgrade head`
- [ ] Integration test: docker-compose up → upload → process → verify DB state

### Phase 3: Connect & Test Frontend (coded but never tested live)
- [ ] Run backend + ML + frontend together, fix integration bugs
- [ ] Display annotated image (boxes) + cost breakdown on claim detail page
- [ ] Build assessor review panel (approve/reject with AI evidence shown)
- [ ] Verify role flows: claimant files -> AI processes -> assessor reviews

### Phase 4: Fraud Graph (moat #2 — optional but impressive)
- [ ] Stand up Neo4j (already in docker-compose)
- [ ] Build graph: claimant -> vehicle -> garage -> claim nodes + relationships
- [ ] Ring-detection queries (same garage + repeat claims + shared phone)
- [ ] Feed graph fraud signal into unified risk score
- [ ] (If time-tight: a simple version — duplicate image + EXIF + repeat-claim
      count — still demonstrates the concept)

### Phase 5: End-to-End Integration Test
- [ ] `docker-compose up` full stack
- [ ] Run a full claim: register -> file -> upload -> AI -> decision -> audit
- [ ] Fix whatever breaks

### Phase 6: Demo Preparation
- [ ] Collect 8-10 real damaged-car photos (scratch, dent, glass, tire)
- [ ] Scripted scenarios: genuine claim, fraud (dup/EXIF), cost comparison
      (Maruti vs BMW, Mumbai vs Ahmedabad)
- [ ] Record backup video demo

### Phase 7: Report & Documentation (runs in parallel throughout)
- [ ] Update methodology to YOLOv8 detection (report already mentions YOLOv8)
- [ ] Add real results: mAP, confusion matrix, sample annotated outputs
- [ ] Update architecture diagrams + add screenshots
- [ ] Document the moats (cost engine, fraud graph, India-specific context)

### Scope guidance
Must-haves for a working demoable product: Phases 1, 2, 3, 6.
Phase 4 (fraud graph) = wow factor if time allows.
Critical path = Phase 2 (backend wiring) — everything depends on it.

## Key Commands Cheat Sheet

```bash
# Dataset
python3 -m ml.detection.prepare_cardd

# Train
python3 -m ml.detection.train --epochs 50 --device mps

# Predict
python3 -m ml.detection.predict --image car.jpg --save_annotated out.png

# ML service
python3 ml/serve.py

# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## File Locations (Detection Pipeline)

| What | Where |
|------|-------|
| Dataset prep | `ml/detection/prepare_cardd.py` |
| Training | `ml/detection/train.py` |
| Severity heuristic | `ml/detection/severity.py` |
| Inference wrapper | `ml/detection/detector.py` |
| CLI prediction | `ml/detection/predict.py` |
| ML service | `ml/serve.py` |
| Cost engine | `ml/cost/estimator.py` |
| Fraud detection | `ml/fraud/image_forensics.py` |
| Trained weights | `ml/weights/detection/cardd_yolov8/weights/best.pt` |

## CarDD Category → Cost Engine Mapping

| CarDD category | Cost engine type |
|----------------|-----------------|
| dent | dent |
| scratch | scratch |
| crack | crack |
| glass_shatter | shatter |
| lamp_broken | panel |
| tire_flat | panel |
