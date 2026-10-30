# Publication inventory

The review branch publishes the implementation, architecture/component documentation, setup/deployment/provisioning scripts, deterministic tests, model provenance/licenses, portable structured-model JSON artifacts, pinned data manifests and numeric research/verification reports. Model inference remains separate from model accuracy claims.

## Included

- Backend/ML/frontend source, container/Compose/Vercel configuration and CI.
- The complete project documentation and guides under `docs/`.
- Upstream OSNet MIT license and TruFor source notices/nonprofit-use license/provenance.
- Research scripts, pinned manifests and completed numeric JSON reports, including negative findings.
- Small generated tabular/GraphSAGE JSON model artifacts needed by the research baseline tests; no original row/photograph pairing is asserted.
- Narration transcript, captions and a manifest describing the local edited walkthrough.

## Excluded from the public source

- `var/`: passwords, signing secrets, Vercel environment settings/OIDC material, databases, user uploads, logs and temporary probes.
- `.vercel/`, local connector/agent files, dependency links/caches, build outputs and bytecode.
- Downloaded model binaries/archives, raw Generali/TQVCD/CarDD/CDDM images, and cached embedding binaries.
- The teammate CSV and demo image while their redistribution terms remain unconfirmed. Provenance READMEs and source links remain available. The deterministic test suite uses fixed non-sensitive input fixtures rather than requiring that raw CSV.
- Local browser screenshots and the MP4 walkthrough that contain those research/demo photographs. They remain available in the working checkout; transcript/captions and the production/render scripts are published.

“Push everything” is implemented as a complete, reviewable source/documentation/results handoff, with private runtime material and separately licensed imagery kept out of a public repository. No credentials or claim data are required to understand or review the implementation.

## Verification snapshot

The provisioned local environment passed 72 tests and the production frontend build. The isolated publication checkout also passes all **72 tests** and the frontend build after raw fixtures and private assets are excluded. The source audit found no matches against 22 generated private credential values, and relative documentation links resolve. Core isolated Docker, Neon and Blob checks succeeded under the documented scope. Vercel built the staged containers, but hosted capability/claim verification failed. Successful cloud-flow verification reports are deliberately absent.

Historical research JSON files retain their original scope and dates. `release_verification.json` and `docs/INTEGRATION_HANDOFF.md` describe the latest state. The original older checkout's uncommitted files are not rewritten by publication.
