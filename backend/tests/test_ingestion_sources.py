"""
Tests for the Ingestion Sources catalog (roadmap 1.5).

compute_sources() is read-only and derives "who delivered today" purely from
existing tables (PartnerConfig, UploadSession joined through Transaction,
WatchFolderConfig). 'Today' is IST-aware.
"""
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, Transaction, UploadSession, WatchFolderConfig,
                             PartnerConfig, ReconStatus)
from core.ingestion_sources import compute_sources

NOW = datetime.datetime.utcnow()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _partner(db, slug, bank=True, internal=True):
    db.add(PartnerConfig(slug=slug, display_name=slug.title(), match_prefix=slug[:3].upper(),
                         is_active=True, has_bank_statement=bank, has_internal_dump=internal))
    db.commit()


def _delivery(db, session_partner, txn_partner, side, when):
    sess = UploadSession(partner=session_partner, side=side, upload_date=when,
                         original_filename="f.xlsx")
    db.add(sess); db.commit()
    db.add(Transaction(partner=txn_partner, side=side, recon_date="2026-04-15",
                       row_type="txn", recon_status=ReconStatus.unmatched,
                       upload_session_id=sess.id))
    db.commit()


def _src(report, partner, side):
    return next(s for s in report["sources"] if s["partner"] == partner and s["side"] == side)


def test_delivered_today(db):
    _partner(db, "fino")
    _delivery(db, "fino", "fino", "bank", NOW)
    r = compute_sources(db)
    s = _src(r, "fino", "bank")
    assert s["status"] == "delivered" and s["delivered_today"] is True


def test_stale_delivery(db):
    _partner(db, "fino")
    _delivery(db, "fino", "fino", "bank", NOW - datetime.timedelta(days=3))
    s = _src(compute_sources(db), "fino", "bank")
    assert s["status"] == "stale"
    assert s["days_since"] == 3


def test_core_partner_side_never_delivered(db):
    # Airtel is a core partner (delivered on internal) but its configured bank
    # side has never delivered → that side shows 'never', not absent.
    _partner(db, "airtel")
    _delivery(db, "airtel", "airtel", "internal", NOW)        # makes airtel a core partner
    db.add(WatchFolderConfig(label="Airtel Bank", partner="airtel", side="bank",
                             is_enabled=True))
    db.commit()
    s = _src(compute_sources(db), "airtel", "bank")
    assert s["status"] == "never"
    assert s["last_delivered_at"] is None


def test_module_partner_with_watch_but_no_transactions_excluded(db):
    # A module product (evalue) with a watch config but NO Transaction delivery must
    # NOT appear — it stores data elsewhere, so 'never' here would be misleading.
    _partner(db, "evalue")
    db.add(WatchFolderConfig(label="E-Value", partner="evalue", side="bank",
                             is_enabled=True))
    db.commit()
    r = compute_sources(db)
    assert all(s["partner"] != "evalue" for s in r["sources"])


def test_mixed_dump_credits_each_partner(db):
    # A 'mixed' upload session whose transactions are partner=fino must credit fino.
    _partner(db, "fino")
    _delivery(db, "mixed", "fino", "internal", NOW)
    s = _src(compute_sources(db), "fino", "internal")
    assert s["status"] == "delivered"


def test_watch_folder_status_surfaced(db):
    _partner(db, "fino")
    _delivery(db, "fino", "fino", "bank", NOW)        # fino is a core partner
    db.add(WatchFolderConfig(label="Fino Bank", partner="fino", side="bank",
                             is_enabled=True, last_trigger_status="not_found"))
    db.commit()
    s = _src(compute_sources(db), "fino", "bank")
    assert s["has_auto"] is True
    assert s["watch_status"] == "not_found"


def test_summary_counts(db):
    _partner(db, "fino")
    _delivery(db, "fino", "fino", "bank", NOW)            # delivered
    _delivery(db, "fino", "fino", "internal", NOW - datetime.timedelta(days=2))  # stale
    _delivery(db, "airtel", "airtel", "internal", NOW)   # airtel core (delivered)
    db.add(WatchFolderConfig(label="Airtel Bank", partner="airtel", side="bank",
                             is_enabled=True))            # core partner side, never delivered
    db.commit()
    r = compute_sources(db)
    assert r["summary"]["delivered_today"] >= 1
    assert r["summary"]["stale"] >= 1
    assert r["summary"]["never"] >= 1
