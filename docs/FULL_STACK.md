# Full infrastructure mode

The core Docker claim workflow has now passed a real isolated PostgreSQL/Redis/Celery/MinIO/Neo4j smoke. The older checkout's running `intelliclaim-gauraang` stack was left unchanged. This supersedes the older statement that Docker access was blocked.

## Default stack

```bash
python3 scripts/dev.py start --full-stack
python3 scripts/dev.py status --full-stack
python3 scripts/dev.py stop --full-stack
```

Default frontend: http://localhost:5173. This uses the `intelliclaim-gauraang` Compose project name, so do not run it over another checkout using that same project. Stop preserves volumes. Generated credentials are in ignored `var/full-stack.env` and `var/full-stack-accounts.json`.

## Isolated verification stack used in this work

```bash
INTELLICLAIM_COMPOSE_PROJECT=intelliclaim-completion \
INTELLICLAIM_COMPOSE_OVERRIDE=docker-compose.verify.yml \
python3 scripts/dev.py start --full-stack
```

Open http://127.0.0.1:15173 . Published verification ports: backend 18000, ML 18001, PostgreSQL 15432, Redis 16379, MinIO 19000/19001, Neo4j 17474/17687. The verification override references the separately provisioned local gallery and Torch cache; those assets are not distributed with source. The launcher's generic success text may show the default 5173 URL; the override's published frontend is **15173**.

```bash
.venv/bin/python scripts/smoke_full_stack.py
```

The default smoke target is backend 18000 and `var/full-stack-accounts.json`. It submits synthetic claims, waits for Celery, checks real detector output and persistent reuse, downloads stored media and a PDF, reads Neo4j and records infrastructure probes. Evidence: `research/results/full_stack_verification.json`.

## Components

PostgreSQL stores application records and the Neo4j projection outbox. Redis is the Celery broker/result store. Workers run the same claim processor as inline mode. MinIO stores originals/overlays using separate browser/server endpoints. Neo4j derives actual claim/entity/photo relationships through idempotent parameterized writes. The ML service loads provisioned artifacts; frontend Nginx proxies the API. SQLite photo history persists on a named ML volume in this configuration.

The frontend health probe now uses `127.0.0.1` to avoid the observed localhost/IPv6 probe failure. Account seeding executes `python -m scripts.seed_demo` so the app package resolves inside the container.

This core-stack smoke preceded the later vehicle/OCR/TruFor additions; those were separately verified in the updated local launcher/browser. Rebuild and repeat the full stack before claiming every later model revision was verified inside Docker. No production security/load or insurer-accuracy claim follows from healthy containers.

Stop the isolated project without affecting the older stack:

```bash
INTELLICLAIM_COMPOSE_PROJECT=intelliclaim-completion \
INTELLICLAIM_COMPOSE_OVERRIDE=docker-compose.verify.yml \
python3 scripts/dev.py stop --full-stack
```
