# IntelliClaim technical audit and implementation plan

This independent clone of https://github.com/gauraangst5514/IPD is the implementation project. The upstream repository is not modified or pushed.

## P0 security
- Public registration must create claimants only; privileged accounts need an authenticated administrative provisioning flow.
- Claim creation must validate vehicle ownership and UUID input.
- Validate image MIME, decoded format, byte size, dimensions/pixels, and image count before storage. Serialize concurrent uploads and prohibit uploads after submission.
- Reject development JWT/storage/DB/graph secrets in production; use environment or secret-manager injection. Deployment credentials and dependency security still require review.

## ML correctness
- Never load generic COCO YOLO weights as a damage model. Missing/incompatible damage weights must report model unavailable, with no fabricated assessment.
- Preserve tire_flat, lamp_broken and glass_shatter labels through detection, severity, pricing and persistence.
- Training scripts do not establish a trained/validated model. Require versioned weights, class metadata, dataset splits, evaluation metrics and provenance.
- Severity, cost and much fraud logic are heuristics. Vehicle classification requires its own verified artifact; generic OCR is not a trained insurance plate model.

## Reliability
- Explicit processing_failed and partial_processing states; no automatic review-ready state when inference fails.
- Replace process-memory duplicates with persisted cryptographic/perceptual hashes, indexed lookup, tenant/access controls and evidence records. A match is a signal, not proof of fraud.
- Introduce versioned migrations, focused API/processing regression tests and CI. Queue dispatch must occur after transaction commit; durable outbox and idempotent retry remain next steps.

## Differentiation roadmap
1. Guided multi-view capture: required angles, blur/lighting/coverage validation and retake guidance.
2. Vehicle damage digital twin: map damage to vehicle panels with evidence and history.
3. Cross-view deduplication: associate the same physical damage across photographs before adding repair costs.
4. Graph fraud: persist relationships between claims, vehicles, repairers and reused images with explainable signals.
5. Uncertainty-aware decisions: calibrated confidence, abstention, human review and out-of-distribution checks.
6. Segmentation: panel/damage masks with validated area estimation; compare against box-based baseline.

## Implementation order
Registration roles → ownership → bounded uploads → model availability → tire/lamp mapping → failed/partial states → focused tests.

## Validation and limits
Record actual tests and remaining work in IMPLEMENTATION_RESULTS.md. Full service integration requires PostgreSQL/Redis/storage and verified model weights. Do not represent static checks or mocked inference as model validation.

## Follow-up progress
Implemented owner-only failed/partial retry API and UI, per-image outcomes, stale-result cleanup, annotation failure isolation, owner-scoped persistent exact SHA-256 matching, worker redelivery guard, frozen baseline/0003 migration and CI checks. Perceptual matching, durable outbox/per-attempt tokens, live service integration and validated weights remain next steps. Latest focused suite: 18 passed.


## Latest implementation status

See IMPLEMENTATION_RESULTS.md for the 6 October follow-up fixes, 34 passing tests, changed-file inventory and remaining integration/model validation. The roadmap remains proposed work, not completed functionality.
