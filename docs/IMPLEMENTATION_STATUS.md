# Implementation status — 30 October 2026

| Component | Implementation | Verification/limit |
|---|---|---|
| Claim/account/vehicle/review APIs | Implemented | Local tests/browser; real isolated database/worker stack smoke |
| Damage detection | Supplied six-class YOLO checkpoint | Real inference; no independent detector accuracy claim |
| Severity/cost | Area/rule estimates | Not calibrated repair quotations |
| Vehicle verification | Published nine-make ViT | Real local inference; unsupported/low-score photos inconclusive |
| Plate OCR | Offline EasyOCR + registration parsing | Positive synthetic fixture; real-photo no-read remains inconclusive |
| Photograph forensics | Official pretrained TruFor | Real score/map; nonprofit research license; not insurance authenticity calibration |
| Photo reuse | SHA-256 + pHash/dHash | Durable local and shared PostgreSQL implementations tested |
| Historical matching | OSNet + correspondence diagnostics | Actual browser retrieval; candidates, not proven physical identity |
| Dynamic ingestion | Incremental embedding + duplicate checks | Restart/cross-instance persistence verified |
| Claim photo inspector | Vehicle/plate/TruFor/history panel | Real local browser interaction verified |
| Narrative | Keyword baseline | No learned deception model |
| Logistic/GraphSAGE | Separate public-data research baselines | Single split; no authentic pairing with images/collusion claims |
| Invoice | Structured arithmetic | No invoice authenticity/pricing verification |
| Evidence graph | SQL / Neo4j with outbox | Live isolated Neo4j core smoke |
| Saliency/PDF | Occlusion sensitivity / report export | Local real-model claim smoke |
| Cloud persistence | Neon + private Blob | Separate real-service checks pass |
| Vercel deployment | Three-service build READY | Hosted ML capability/claim verification failed; not a verified release |
| Narrated walkthrough | Local MP4 + captions + transcript | 102.6 seconds; edited screen captures and synthesized voice |
| Test/build | 72 local tests and production frontend build pass | Research/model smoke provisioning is separate from CI |

See [COMPONENT_GUIDE.md](COMPONENT_GUIDE.md) for source, inputs/outputs and limits, and [INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md) for the exact deployment blocker.
