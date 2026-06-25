"""
core/ingestion_ledger.py

Append-only ingestion lineage ledger (roadmap 1.4 — additive).

`record_ingestion_event()` writes ONE IngestionEvent row in its OWN database
session/transaction and swallows every error, so logging can never block,
slow, or roll back an actual ingest. It is imported by BOTH ingest paths
(routes/upload.confirm_mapping and core/ingest_service.ingest_dataframe) so the
two divergent copies share one ledger.

This module reads counters the ingest pipeline already computes — it does NOT
touch classification, the regex ladder, tolerances, or pass order
(behavior-contract #2/#3/#4/#10).
"""
import json
import hashlib
import logging

logger = logging.getLogger("eko_recon")


def sha256_of_file(path, _chunk=1 << 20):
    """Streamed SHA-256 of a file. Returns None on any error (never raises)."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_chunk), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def record_ingestion_event(**fields):
    """
    Persist a single ingestion-ledger row in an isolated transaction.

    Accepts any IngestionEvent column as a kwarg. `skip_breakdown` and `detail`
    may be passed as a dict/list and are JSON-encoded here. ALL errors are
    swallowed — recording the ledger must never affect the caller's ingest.
    """
    try:
        from models.database import SessionLocal, IngestionEvent
        for k in ("skip_breakdown", "detail", "dq_profile"):
            v = fields.get(k)
            if v is not None and not isinstance(v, str):
                fields[k] = json.dumps(v, default=str)
        db = SessionLocal()
        try:
            db.add(IngestionEvent(**fields))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"ingestion_ledger: record failed (non-fatal): {e}")
