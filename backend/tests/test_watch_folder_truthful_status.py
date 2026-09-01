"""
The watch-folder must not report a half-done run as a success.

`ingest_dataframe` deliberately never raises on a post-ingest failure — a matching
error must not fail the upload (contract #4). The watch-folder copy also had NO
logging at all, so when auto-recon / NEFT D+1 / the internal self-match blew up, the
exception was swallowed with a bare `pass`, the scheduler saw a normal return and
wrote last_trigger_status='success', and core/recon_health then reported the folder
"healthy". A file could ingest with the entire recon chain broken and every surface
in the app said it was fine.

These pin the reporting contract, NOT the swallow: the chain must still complete and
the ingest must still succeed. Only the truthfulness of what is reported changes.
"""
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, Transaction, UploadSession, WatchFolderConfig,
                             UploadSchedule, generate_id)
from core.ingest_service import ingest_dataframe
import core.matching_engine as me

DATE = "2026-04-15"
MAPPING = {"eko_tid": "eko_trxn_id", "tracking_number": "TrackingNumber",
           "amount": "Amount", "status": "Status"}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def _session(db, partner="fino", side="internal"):
    sess = UploadSession(partner=partner, side=side, recon_date=DATE,
                         original_filename="dump.xlsx", column_mapping="{}")
    db.add(sess)
    db.commit()
    return sess


def _df():
    return pd.DataFrame([
        {"eko_trxn_id": "T1", "TrackingNumber": "R1", "Amount": 100, "Status": "Success"},
    ])


def test_clean_run_reports_no_post_errors(db):
    out = ingest_dataframe(_df(), _session(db), MAPPING, db, "u1", "tester",
                           do_auto_recon=True)
    assert out["row_count"] == 1
    assert out["post_errors"] == []


def test_failing_recon_step_is_recorded_but_never_fails_the_ingest(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("recon exploded")
    monkeypatch.setattr(me, "run_reconciliation", boom)

    out = ingest_dataframe(_df(), _session(db), MAPPING, db, "u1", "tester",
                           do_auto_recon=True)
    # Contract #4: the rows still land and the caller still gets a normal result.
    assert out["row_count"] == 1
    assert db.query(Transaction).filter(Transaction.row_type == "txn").count() == 1
    # …but the failure is no longer invisible.
    assert any("recon exploded" in e for e in out["post_errors"])


def test_a_failing_step_does_not_abort_the_rest_of_the_chain(db, monkeypatch):
    """The internal self-match runs after NEFT D+1; a NEFT failure must not skip it."""
    def boom(*a, **k):
        raise RuntimeError("neft exploded")
    calls = []
    real_internal = me.run_internal_match
    monkeypatch.setattr(me, "run_neft_d1_match", boom)
    monkeypatch.setattr(me, "run_internal_match",
                        lambda *a, **k: (calls.append(1), real_internal(*a, **k))[1])

    out = ingest_dataframe(_df(), _session(db), MAPPING, db, "u1", "tester",
                           do_auto_recon=True)
    assert any("neft exploded" in e for e in out["post_errors"])
    assert calls, "internal self-match was skipped because NEFT D+1 failed"


def test_ingest_service_logs_post_ingest_failures(db, monkeypatch, caplog):
    """It had no logging import at all — the whole point of the silent failure."""
    monkeypatch.setattr(me, "run_reconciliation",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaboom")))
    with caplog.at_level("WARNING", logger="eko_recon"):
        ingest_dataframe(_df(), _session(db), MAPPING, db, "u1", "tester",
                         do_auto_recon=True)
    assert any("kaboom" in r.message for r in caplog.records)


# ── recon_health must stop calling a half-failed folder healthy ───────────────

def _health_watch_folders(db):
    from core.recon_health import compute_recon_health
    for c in compute_recon_health(db).get("checks", []):
        if "watch" in (c.get("key", "") + c.get("label", "")).lower():
            return c
    return None


def _folder(db, status, scheduled=True, label="axis daily"):
    w = WatchFolderConfig(id=generate_id(), label=label, folder_path="/tmp/x",
                          partner="axis", side="bank", last_trigger_status=status,
                          last_trigger_message="m")
    db.add(w)
    if scheduled:
        db.add(UploadSchedule(id=generate_id(), watch_folder_id=w.id,
                              is_enabled=True, hour=20, minute=0))
    db.commit()
    return w


@pytest.mark.parametrize("status,expect_ok", [
    ("success", True),
    ("partial", False),
    ("error",   False),
])
def test_health_reflects_watch_folder_status(db, status, expect_ok):
    _folder(db, status)
    c = _health_watch_folders(db)
    assert c is not None, "watch-folder health check not found"
    assert c["ok"] is expect_ok, f"{status} -> {c['severity']}"


def test_a_folder_that_has_never_run_is_not_reported_healthy(db):
    """Production had 27 folders configured and ZERO enabled schedules, so not one had
    ever fired — last_trigger_status stayed NULL and health said "Watch folders healthy"."""
    _folder(db, None, scheduled=False)
    c = _health_watch_folders(db)
    assert c["ok"] is False
    assert "not scheduled" in c["message"]
    assert c["detail"]["unscheduled"] == ["axis daily"]


def test_a_scheduled_folder_that_has_not_run_yet_is_fine(db):
    """Scheduled but not yet fired today is normal — don't cry wolf."""
    _folder(db, None, scheduled=True)
    assert _health_watch_folders(db)["ok"] is True
