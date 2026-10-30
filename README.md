# IntelliClaim

IntelliClaim is a vehicle-damage evidence review prototype for claimants and insurance investigators. It combines claim management, published pretrained vision models, historical-photograph retrieval, persistent reuse evidence, structured-data research baselines, and human assessment. It does not calculate a validated claim-fraud probability or automatically approve/reject claims.

**Status — 30 October 2026:** 72 local automated tests pass and the TypeScript/Vite production build passes. Browser retrieval and the four photograph-evidence checks run locally. A real isolated PostgreSQL/Redis/Celery/MinIO/Neo4j claim smoke passed. Cloud persistence checks passed against Neon and private Vercel Blob. The staged Vercel build is READY, but hosted ML capabilities and claim inference failed verification; the cloud application is **not an end-to-end verified release**.

## Documentation

- [Completed project report (PDF)](docs/IntelliClaim_Completed_Project_Report.pdf) and [editable Word version](docs/IntelliClaim_Completed_Project_Report.docx): submitted-style report covering the system, models, data, methods, results and limitations.
- [Complete project documentation](IntelliClaim_Complete_Project_Documentation.md): implementation, measured results, verification and remaining work.
- [Component-by-component guide](docs/COMPONENT_GUIDE.md): what every component does, inputs/outputs, source files and limitations.
- [Current handoff](docs/INTEGRATION_HANDOFF.md): operating instructions, artifacts and the exact deployment blocker.
- [Evidence models](docs/EVIDENCE_MODELS.md): vehicle classifier, OCR, TruFor and OSNet provenance and scope.
- [Research results](docs/RESEARCH_RESULTS.md): protocols, results and uncertainty.
- [Vercel release](docs/VERCEL_RELEASE.md): cloud architecture, staging and verification commands.
- [External data access](docs/DATA_ACCESS_AND_VALIDATION.md): official access requirements and completed external-source stress test.
- [Publication inventory](docs/PUBLICATION.md): included source/results and private/local artifacts.

## Run locally

Use Python 3.11 and Node.js 20 or newer. This development copy currently links dependencies from an older checkout; those links are not portable.

```bash
python3 scripts/dev.py setup --with-vision
python3 scripts/provision_retrieval.py --generali --lightglue
python3 scripts/provision_evidence_models.py
python3 scripts/dev.py doctor
python3 scripts/dev.py start
```

The local launcher uses frontend **5183**, backend **8010**, and ML **8011**. Open [the local application](http://127.0.0.1:5183). It generates private synthetic accounts in `var/demo_accounts.json`, a signing secret, local SQLite stores and logs. Trained damage and OSNet checkpoint provisioning, archive extraction/conversion and dataset access are described in the complete documentation. Downloads are explicit setup steps; inference requests do not install packages or download models.

To use the configured full infrastructure, start Docker Desktop and see [FULL_STACK.md](docs/FULL_STACK.md). Use the isolated verification project/override to avoid colliding with another running checkout.

## Main workflows

A claimant registers a vehicle, creates a claim, uploads photographs and submits it. Damage inference, photograph reuse, vehicle/plate suggestions, forensic diagnostics and historical candidates generate evidence. An assessor inspects the claim, optional invoice/structured results, visual diagnostics and related claims, then records a human decision and exports a PDF.

An assessor can also search the historical photograph gallery directly, inspect correspondence lines and damage masking, and add approved claim photos to the index. Similarity and model confidence values are not fraud probabilities. A model can be available while an individual image remains inconclusive.

## Checks and research

```bash
.venv/bin/python -m unittest discover -s tests -v
npm run build --prefix frontend
.venv/bin/python scripts/smoke_full_flow.py
.venv/bin/python scripts/smoke_retrieval.py
.venv/bin/python research/scripts/benchmark_fixed_gallery_abstention.py
.venv/bin/python research/scripts/benchmark_external_stress.py
```

Smoke/research commands require separately provisioned weights and licensed/local images. CI runs deterministic source-level tests without downloading research corpora. Large weights, original datasets, credentials, user databases and claim uploads are excluded from the public source.

On 420 downloaded Generali images under our leave-one-out protocol, frozen OSNet-AIN measured 95.24% Recall@1 and 74.82% mAP, versus 90.48% and 58.67% for ResNet18. SIFT and completed LightGlue reranking did not demonstrate improvement. Reliable open-set abstention and independent insurer validation remain unestablished. See [the research report](docs/RESEARCH_RESULTS.md) before comparing metrics.
