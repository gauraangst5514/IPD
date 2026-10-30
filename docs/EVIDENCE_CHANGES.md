> Historical design/change record. For the current 30 October implementation, model availability and deployment failure, use [COMPONENT_GUIDE.md](COMPONENT_GUIDE.md) and [INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md).

# Durable image evidence and honest review indicators

## Behavior

- Image history lives in an SQLite database, shared across workers on one host.
- Exact file reuse is distinguished from a candidate perceptual match. Both
  pHash and dHash Hamming distances must be within 6 bits for a candidate.
  This retrieval threshold needs validation and is not a fraud probability.
- A match returns all matching claim/image IDs, distances and first-seen times.
- Lookup and insertion are one serialized transaction; retries within the same
  claim are idempotent and do not create cross-claim alerts.
- Missing/invalid EXIF is unavailable evidence. Software tags are informational.
- ELA is a raw JPEG recompression diagnostic, without a manipulation threshold.
- Unavailable checks remain visible; absence of a flag does not mean a pass.
- The ML API returns fraud_score=null, score_type=not_estimated, structured
  fraud_indicators, review_required and checks_complete.
- The backend stores image-specific evidence in the existing fraud_flags JSON
  column, clears legacy image manipulation/claim risk scores on reprocessing,
  and routes explicit discrepancies to human review. No schema migration is
  required. Legacy FraudFlag rows are retained as history; new ones are not
  populated with invented confidence.
- Dashboard, review queue, claim detail, CLI and PDF no longer present heuristic
  scores as probabilities. Existing claims require reprocessing for new evidence.

## Deployment

Deploy backend, ML service and frontend together; an old ML response cannot
populate the new evidence contract. Docker Compose mounts image_history_data at
/app/ml/evidence. The local default is ml/evidence/image_history.sqlite3, resolved
relative to the source location, independent of the working directory. Override
with IMAGE_HISTORY_PATH. Do not use :memory: or ephemeral container storage.

Use one ML service instance for this Compose setup. SQLite WAL supports multiple
processes sharing a local disk. Separate hosts or replicas need a shared service
and an appropriately indexed store (e.g. PostgreSQL plus a retrieval index), not
SQLite on a network filesystem. Near search is a full scan: measure latency and
migrate before growing beyond the tested gallery size. No large-gallery or
multi-host performance has been demonstrated.

History creation failure prevents startup; runtime lookup failure is reported as
unavailable, not silently replaced with an empty gallery. Keep the index private
like claim data and back it up with SQLite's backup API, or stop the service
before copying it; copying the main file alone during WAL writes is unsafe.

Previously lost in-memory history cannot be recovered directly. Seed the new
index from existing uploaded images:

```bash
python3 scripts/dev.py backfill
```

This uses the configured database, storage and running ML service. It is
idempotent and does not rewrite claim decisions. Backfilled first-seen values
are indexing timestamps, not original upload timestamps. It can return matches
against already indexed records irrespective of original claim chronology;
do not use this operational index for a temporal research evaluation.

## Verification

```bash
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q ml backend/app
cd frontend && npm ci && npm run build
```

Tests cover restart persistence, concurrent processes, same-claim retries,
multiple prior owners, near matches, anonymous inputs, metadata absence/parsing,
real JPEGs, history failures, and database persistence/routing with null scores.
The unit suite skips dependency-specific tests when dependencies are absent;
the GitHub workflow installs them. These tests do not establish model accuracy.

## Research boundary

The implemented matcher detects identical/visually similar files. It does not
recognize the same physical damage photographed from a new viewpoint. That
requires a separately trained/evaluated damage re-identification model. Neither
kind of match establishes intent, policy coverage, or a fraudulent claim.
