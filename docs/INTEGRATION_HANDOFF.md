# Current integration handoff — 30 October 2026

This file supersedes the older 29 October handoff. The complete explanation is in [COMPONENT_GUIDE.md](COMPONENT_GUIDE.md) and [the project documentation](../IntelliClaim_Complete_Project_Documentation.md).

## Verified implementation

- React/TypeScript claimant and assessor workflows, authenticated backend and ML service.
- Damage detection, persistent exact/perceptual photo reuse, separate structured baselines, invoice arithmetic, graph, saliency, PDF and explicit human review.
- OSNet historical retrieval, candidate thumbnails/counts, SIFT/LightGlue evidence, SVG correspondence overlay and damage masking.
- Dynamic gallery ingestion with duplicate detection, safe filenames and restart persistence.
- Four formerly unavailable checks now execute locally: nine-make ViT vehicle suggestions, offline English plate OCR, official TruFor forensic diagnostics, and historical damage-photo candidate retrieval.
- Per-photo assessor inspector renders actual suggestions/inconclusive states, plate candidates, forensic score/map and historical candidates.
- PostgreSQL-backed shared ML history/gallery and private Vercel Blob storage with key-scoped expiring image URLs.

## Verification and its limits

| Evidence | Actual outcome |
|---|---|
| Automated source/integration suite | 72 passed in the provisioned local Python 3.11 environment |
| TypeScript + Vite production build | Passed |
| Local browser | Retrieval, correspondence toggles, four capability cards and per-photo evidence inspector verified |
| Local real-model claim smoke | Passed, including damage, persisted reuse, PDF and graph |
| Isolated Docker stack | Real PostgreSQL/Redis/Celery/MinIO/Neo4j core claim smoke passed; separate project/ports protected the older stack |
| Neon persistence | Shared photograph history and gallery tested across separate instances; synthetic test rows removed |
| Private Blob | Actual put/get passed; temporary object removed; signed-key isolation covered by tests |
| LightGlue experiment | All 390 pairs complete; selected zero weight, no improvement |
| Narrated demo | 102.6-second edited walkthrough of captured browser screens, synthesized Aman voice and captions; not a continuous live screen recording |
| Vercel build | READY for staged deployment `dpl_AsBwuxtHyTczjN9EkruqBw5KwAzx` |
| Hosted application flow | **Failed verification:** capability response lacked `damage_detection`; synthetic claim request timed out |

Do not describe the cloud deployment as working end to end or the public project alias as a verified release. No successful production claim/capability verification reports were generated. Successful cloud database/storage checks are narrower than complete application verification.

## Last deployment state and next investigation

- Team/project: `gst8/intelliclaim`.
- Staged URL: https://intelliclaim-jl3a0zow6-gst8.vercel.app . The login page rendered; assessor authentication was exercised by the verification script.
- Frontend: Vite service. Backend and private ML: CPU container services, linked through `ML_SERVICE_URL`.
- Built containers: backend approximately 122.82 MB; ML approximately 1.31 GB. CPU-only PyTorch avoids unused CUDA libraries.
- Provisioned backing services: Neon database `intelliclaim-db` and private Blob store `intelliclaim-uploads`.
- The failed capability assertion is a missing component key, not a measured detector/model accuracy failure. Check the backend health client's returned ML error, service-binding URL/path and private routing, ML container startup/resource logs and cold-start timeout before changing model logic. Root cause has not been established.
- A shell runtime-log query hit the automatic approval review deadline; the fallback MCP error-only query returned no logs, and a wider query hit the plan's retention constraint. Do not interpret these as proof the deployed services were healthy. Retry a narrowly scoped recent log window.
- Work switched to documentation/publication at the user's request; no further production promotion is claimed.

## Operate and reproduce

```bash
python3 scripts/dev.py doctor
python3 scripts/dev.py start
```

Local ports: 5183 / 8010 / 8011. Secrets/accounts, databases, uploads and logs are under ignored `var/`. Dependencies in this copy are links to the earlier checkout; a fresh machine needs setup and explicit model/data provisioning.

```bash
.venv/bin/python -m unittest discover -s tests -v
npm run build --prefix frontend
.venv/bin/python scripts/smoke_full_flow.py
.venv/bin/python scripts/smoke_retrieval.py
```

The first two commands validate source/build. The smoke scripts additionally require provisioned model weights and the separately obtained local demo photograph. [FULL_STACK.md](FULL_STACK.md) documents the isolated Docker command. [VERCEL_RELEASE.md](VERCEL_RELEASE.md) documents cloud verification and promotion; do not promote until hosted checks pass.

## Files and local artifacts

- `research/results/release_verification.json`: current machine-readable handoff.
- `research/results/*evaluation.json`: completed research results and limitations.
- `research/results/full_stack_verification.json`, `postgres_persistence_verification.json`, `blob_storage_verification.json`: successful bounded integration evidence.
- `research/results/enabled_checks_verified.png`, `photo_inspection_verified.png`: local visual evidence, not distributed with public source pending imagery terms.
- `submission/IntelliClaim_Narrated_Walkthrough.mp4`: local narrated walkthrough; transcript/captions/manifest are documented in the publication inventory.
- `var/demo_accounts.json`, `var/full-stack-accounts.json`, `var/production_accounts.json`: private synthetic credentials, never publish.

## Remaining research/release requirements

Independent licensed same-damage data, audited identity/pretraining overlap, detector and insurer outcome validation, useful reliably validated abstention, calibrated severity/cost, production inference capacity/security testing and the hosted backend-to-ML repair. None can be replaced by renaming an unavailable check or quoting a published paper's performance.
