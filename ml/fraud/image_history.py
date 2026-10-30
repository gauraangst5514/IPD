"""Durable, process-safe image evidence index for a single-host deployment.

SQLite WAL shares history across ML workers. The transaction serializes lookup
and registration. Keep the file on a persistent local volume, not a network share.
"""
import os
import sqlite3
from contextlib import closing
from pathlib import Path


class ImageHistory:
    def __new__(cls, path=None, hamming_threshold=6):
        if cls is ImageHistory and os.environ.get('IMAGE_DATABASE_URL'):
            from ml.fraud.postgres_history import PostgresImageHistory
            return PostgresImageHistory(path,hamming_threshold)
        return super().__new__(cls)

    def __init__(self, path=None, hamming_threshold=6):
        default = Path(__file__).resolve().parents[1] / "evidence" / "image_history.sqlite3"
        self.path = Path(path or os.environ.get("IMAGE_HISTORY_PATH", default)).resolve()
        if not 0 <= hamming_threshold <= 64:
            raise ValueError("hamming_threshold must be between 0 and 64")
        self.hamming_threshold = hamming_threshold
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS image_history (
                claim_id TEXT NOT NULL, image_id TEXT NOT NULL,
                sha256 TEXT NOT NULL, phash TEXT NOT NULL, dhash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                PRIMARY KEY (claim_id, sha256)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_history_sha ON image_history(sha256)")
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def check_and_register(self, claim_id, image_id, sha256, phash, dhash):
        """Return matching evidence, never a fraud verdict.

        Anonymous requests cannot populate history. Same-claim retries are
        idempotent. Both hashes must be close for a near-match candidate.
        """
        if not claim_id or not claim_id.strip():
            return {"status": "unavailable", "reason": "claim_id_required", "matches": []}
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("Expected a SHA-256 hex digest")
        for value in (phash, dhash):
            if len(value) != 16 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Expected a 64-bit perceptual hash")
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            matches = []
            # Linear scan is suitable for this project-sized gallery. Move near
            # search to a dedicated retrieval index for a larger deployment.
            for row in db.execute("SELECT * FROM image_history WHERE claim_id != ?", (claim_id,)):
                pd = (int(phash, 16) ^ int(row["phash"], 16)).bit_count()
                dd = (int(dhash, 16) ^ int(row["dhash"], 16)).bit_count()
                exact = sha256 == row["sha256"]
                if exact or (pd <= self.hamming_threshold and dd <= self.hamming_threshold):
                    matches.append({
                        "claim_id": row["claim_id"], "image_id": row["image_id"],
                        "match_type": "exact_file" if exact else "perceptual_candidate",
                        "phash_distance": pd, "dhash_distance": dd,
                        "first_seen_at": row["created_at"],
                    })
            db.execute(
                "INSERT OR IGNORE INTO image_history (claim_id,image_id,sha256,phash,dhash) VALUES (?,?,?,?,?)",
                (claim_id, image_id or sha256, sha256, phash, dhash),
            )
            db.commit()
            matches.sort(key=lambda m: (m["match_type"] != "exact_file",
                m["phash_distance"] + m["dhash_distance"], m["claim_id"]))
            return {"status": "checked", "matches": matches}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
