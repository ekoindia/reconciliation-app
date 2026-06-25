"""
Tests for roadmap item 1.4 — ingestion event ledger + lineage.

Covers the recorder contract that the additive design depends on:
  * record_ingestion_event() persists ONE row from the passed fields,
  * dict-valued `detail` / `skip_breakdown` are JSON-encoded,
  * the recorder NEVER raises — a logging failure cannot block an ingest,
  * sha256_of_file() hashes a real file and returns None for a missing one.

The recorder opens its own SessionLocal(), so we monkeypatch SessionLocal in
models.database to bind to an in-memory SQLite engine for the test.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models.database as db_mod
from models.database import Base, IngestionEvent
from core.ingestion_ledger import record_ingestion_event, sha256_of_file


@pytest.fixture
def patched_sessionlocal(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(db_mod, "SessionLocal", TestSession)
    return TestSession


def test_records_one_row_with_fields(patched_sessionlocal):
    record_ingestion_event(
        channel="upload", status="completed", partner="fino", side="bank",
        rows_read=10, rows_accepted=9, rows_skipped=1,
        skip_breakdown={"unknown_source": 1},
        detail={"note": "ok"},
    )
    s = patched_sessionlocal()
    try:
        rows = s.query(IngestionEvent).all()
        assert len(rows) == 1
        e = rows[0]
        assert e.channel == "upload" and e.status == "completed"
        assert e.partner == "fino" and e.rows_skipped == 1
        # dict fields are JSON-encoded
        assert json.loads(e.skip_breakdown) == {"unknown_source": 1}
        assert json.loads(e.detail) == {"note": "ok"}
    finally:
        s.close()


def test_recorder_never_raises_on_bad_field(patched_sessionlocal):
    # An unknown column would normally raise; the recorder must swallow it and
    # write nothing, never propagating to the caller (the ingest path).
    record_ingestion_event(not_a_real_column="boom", channel="upload")
    s = patched_sessionlocal()
    try:
        assert s.query(IngestionEvent).count() == 0
    finally:
        s.close()


def test_recorder_swallows_when_sessionlocal_broken(monkeypatch):
    def _broken():
        raise RuntimeError("db down")
    monkeypatch.setattr(db_mod, "SessionLocal", _broken)
    # Must not raise even when the DB is completely unavailable.
    record_ingestion_event(channel="watch_folder", status="failed")


def test_sha256_of_file(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_bytes(b"hello")
    import hashlib
    assert sha256_of_file(str(f)) == hashlib.sha256(b"hello").hexdigest()
    assert sha256_of_file(str(tmp_path / "missing.txt")) is None
