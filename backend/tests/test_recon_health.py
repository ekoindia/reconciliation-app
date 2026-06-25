"""
Tests for the recon-health watchdog (D2).

compute_recon_health() is read-only and defensive — it aggregates failure
signals from the ingestion ledger, watch-folder status, DQ profiles, and recon
runs into one report, ranking severity critical > warn > ok and never raising.
"""
import json
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, IngestionEvent, WatchFolderConfig, ReconRun
from core.recon_health import compute_recon_health


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _by_key(report, key):
    return next(c for c in report["checks"] if c["key"] == key)


def test_empty_is_healthy(db):
    r = compute_recon_health(db)
    assert r["status"] == "ok"
    assert all(c["ok"] for c in r["checks"])


def test_failed_ingest_warns(db):
    db.add(IngestionEvent(channel="watch_folder", status="failed"))
    db.commit()
    r = compute_recon_health(db)
    assert _by_key(r, "failed_ingests")["severity"] == "warn"
    assert r["status"] in ("warn", "critical")


def test_watch_folder_error_is_critical(db):
    db.add(WatchFolderConfig(label="Fino Bank", partner="fino", side="bank",
                             last_trigger_status="error", last_trigger_message="boom"))
    db.commit()
    r = compute_recon_health(db)
    assert _by_key(r, "watch_folders")["severity"] == "critical"
    assert r["status"] == "critical"


def test_watch_folder_not_found_is_warn(db):
    db.add(WatchFolderConfig(label="Fino Bank", partner="fino", side="bank",
                             last_trigger_status="not_found"))
    db.commit()
    assert _by_key(compute_recon_health(db), "watch_folders")["severity"] == "warn"


def test_dq_warnings_counted(db):
    db.add(IngestionEvent(channel="upload", status="completed",
                          dq_profile=json.dumps({"has_warnings": True, "warnings": ["x"]})))
    db.add(IngestionEvent(channel="upload", status="completed",
                          dq_profile=json.dumps({"has_warnings": False})))
    db.commit()
    c = _by_key(compute_recon_health(db), "dq_warnings")
    assert c["severity"] == "warn"
    assert c["detail"]["count"] == 1


def test_low_match_rate_warns(db):
    # 10 bank + 10 internal but only 2 matched → 20% < 50% threshold.
    db.add(ReconRun(partner="fino", recon_date="2026-04-15",
                    total_bank=10, total_internal=10, matched=2))
    db.commit()
    c = _by_key(compute_recon_health(db), "match_rate")
    assert c["severity"] == "warn"
    assert c["detail"]["rate"] == 0.2


def test_healthy_match_rate_ok(db):
    db.add(ReconRun(partner="fino", recon_date="2026-04-15",
                    total_bank=10, total_internal=10, matched=9))
    db.commit()
    assert _by_key(compute_recon_health(db), "match_rate")["severity"] == "ok"


def test_old_events_outside_window_ignored(db):
    old = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    e = IngestionEvent(channel="watch_folder", status="failed")
    e.created_at = old
    db.add(e)
    db.commit()
    # Default 7-day window excludes the 30-day-old failure.
    assert _by_key(compute_recon_health(db, days=7), "failed_ingests")["severity"] == "ok"
