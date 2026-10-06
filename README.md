# IntelliClaim — separate hardening copy

Vehicle insurance claim prototype: React UI, FastAPI claims API, private ML API,
SQLAlchemy database, object storage, and durable processing attempts.

This copy improves security, failure recovery and evidence reporting. It does not
establish model accuracy or production readiness. Detector and vehicle classifier
weights and reproducible evaluation metrics are not supplied with this checkout.
Severity, repair pricing and most fraud signals are heuristics. Detector scores
are uncalibrated; missing evidence is explicitly unavailable or inconclusive.

## Local development

Use Python 3.12 for the API and Node 22+ for the frontend. From repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env
mkdir -p work
export APP_ENV=development
export PYTHONPATH=backend:.
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal with the same environment, run the durable local dispatcher:

```sh
python -m app.worker.dispatcher --local
```

Start the UI with `npm --prefix frontend ci` and `npm --prefix frontend run dev`.
The API can run without model weights; processing then reports a failure rather
than inventing detections. The local dispatcher still needs a running inference
service for successful analysis. Local file storage fallback is development-only.

For inference use a separate Python 3.11 environment, install `ml/requirements.txt`,
then run `APP_ENV=development uvicorn ml.serve:app --host 127.0.0.1 --port 8001`
from the root. Supply a matching ML_API_KEY in both services when configured.
Place approved six-class CarDD detector weights at the paths in
`ml/detection/detector.py`. Generic YOLO weights are rejected. `/ready` returns
503 until a detector loads. Loading an artifact does not validate its accuracy.

Create privileged accounts locally (password entered interactively):

```sh
python -m app.manage create-user --email reviewer@example.com --name Reviewer --role assessor
python -m app.manage revoke-sessions --email reviewer@example.com
```

Public registration only creates claimants. Authentication rechecks account
activity, current role and token version on every request.

## Production and migrations

`docker-compose.yml` requires explicit production secrets, runs migrations before
API/workers, uses a separate database dispatcher, and exposes only the frontend on
loopback. Set SECRET_KEY, ML_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD,
S3_ACCESS_KEY and S3_SECRET_KEY in a private environment. Do not reuse development
credentials. Configure TLS, backups and operational monitoring before deployment.
`docker-compose.dev.yml` supplies optional development infrastructure only.

Existing databases must be backed up and compared with the frozen baseline before
stamping migrations. Never blindly stamp an existing schema. Migration 0004
retains audit evidence and deliberately refuses downgrade. It moves legacy
confidence values into severity scores and marks orphaned processing claims failed.

Processing attempts are written in the same transaction as claim submission.
Dispatcher publication is retryable. Workers use expiring leases, heartbeat renewal
and fenced completion; a stale worker cannot overwrite a newer attempt. Evidence
is retained per attempt. Manual attempts are capped; per-attempt execution retries
are bounded. Failed and partial claims require an explicit retry before review.

## Checks

```sh
PYTHONPATH=backend:. pytest backend/tests -q
npm --prefix frontend run build
```

Tests use isolated SQLite databases by default. Set TEST_DATABASE_URL to a
PostgreSQL asyncpg URL to run the shared fixtures in isolated PostgreSQL schemas.
The test account needs permission to create/drop those schemas.

See TECHNICAL_AUDIT_AND_CHANGES.md and IMPLEMENTATION_RESULTS.md for scope,
validation and remaining work. No model performance or fraud accuracy claim should
be made until an artifact manifest, held-out evaluation and calibration report exist.
