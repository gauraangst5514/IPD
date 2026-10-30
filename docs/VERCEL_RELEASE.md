# Vercel release architecture

**Current status:** staged container build READY at https://intelliclaim-jl3a0zow6-gst8.vercel.app, but hosted capabilities and claim inference failed verification. This is not an end-to-end verified public release; see [the handoff](INTEGRATION_HANDOFF.md).

The public application uses a single Vercel project, `gst8/intelliclaim`, with three Services (Vercel Services and Container Runtime are beta products):

- **frontend**: Vite static build, SPA deep-link rewrites.
- **backend**: Python/FastAPI container, public `/api/*` routes, existing claimant/assessor/admin authentication. Inline claim processing and the existing SQL graph mode are explicit cloud settings.
- **ml**: CPU Python container with published damage, vehicle, OCR, TruFor and embedding models. There is no public ingress rewrite. The backend calls it through the deployment-aware `ML_SERVICE_URL` service binding.

Neon Postgres stores claims, accounts, assessments and graph records. Shared ML photograph hashes and gallery vectors/photos use PostgreSQL tables (`ml_image_history`, `ml_retrieval_gallery`). Files and vectors in an instance's `/tmp` directory are only caches; a new instance reloads persistent gallery vectors without re-embedding. Adding gallery photographs does not mutate the offline research corpus.

Original claim photographs and overlays use a **private Vercel Blob store**. Browser URLs carry a key-scoped, expiring application signature, and the backend reads the private object. A photo URL cannot be repurposed for another key. Login tokens do not act as unscoped image signatures. Tests cover both cases. Secrets and account passwords stay under ignored `var/` files and Vercel secret settings; no raw dataset is shipped in the source deployment.

The ML image uses CPU-only PyTorch, avoiding unused CUDA libraries. Model provisioning runs at container build time and is cached independently of normal source edits. Runtime upload requests never install packages or download model weights. TruFor remains restricted to informational/nonprofit research use; this public release is a research prototype, not a commercial insurance service.

## Deploy and verify

```bash
npx vercel@65.8.0 project inspect --non-interactive
npx vercel@65.8.0 deploy --prod --skip-domain --scope gst8
.venv/bin/python scripts/verify_deployment.py https://<staged-deployment>.vercel.app
BACKEND_URL=https://<staged-deployment>.vercel.app ACCOUNTS_FILE=var/production_accounts.json EXPECTED_GRAPH_BACKEND=sql SMOKE_REPORT_PATH=research/results/production_claim_verification.json .venv/bin/python scripts/smoke_full_stack.py
npx vercel@65.8.0 promote https://<tested-production-deployment>.vercel.app --scope gst8
```

`--skip-domain` stages a production build. Promote the tested production build rather than rebuilding a preview. Verify the final alias afterward. A URL or completed frontend build alone does not establish successful backend/ML operation.

Vercel Functions have a 4.5 MB request-body limit. Keep hosted uploads below 4 MB to leave room for multipart overhead; the local development endpoint's separate 10 MB limit does not override Vercel's ingress limit. Cloud gallery initialization is intentionally separate from the local downloaded research gallery. Index approved claim photographs with assessor access.

## Verification evidence

- `research/results/full_stack_verification.json`: real isolated PostgreSQL, Celery, Redis, MinIO and Neo4j claim flow; the older user's Docker stack was left alone.
- `research/results/postgres_persistence_verification.json`: shared evidence and gallery across separate instances against the newly provisioned Neon database.
- `research/results/blob_storage_verification.json`: actual private Blob put/get, with temporary synthetic object removal.
- `research/results/deployment_verification.json`: created only by successful live deployed checks; includes auth, capabilities and a small health-endpoint concurrency probe.
- `research/results/production_claim_verification.json`: created only after successful real cloud claim processing.

A 20-request health probe does not establish peak ML inference capacity. Local integration checks and published pretrained weights do not establish insurer outcome accuracy, a full production security audit, or reliable abstention.

Private production demonstration account credentials are in `var/production_accounts.json`; do not put them in a public source archive or public demo video.
