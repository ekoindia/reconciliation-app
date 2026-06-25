"""
Integration characterization tests for the ingest pipeline (D1.2).

These drive a real pandas DataFrame through core.ingest_service.ingest_dataframe
(the directly-callable watch-folder/auto copy of the ingest pipeline) against an
in-memory SQLite DB. They PIN behaviors that only emerge end-to-end:

  #10 Fino ACCOUNT_ACTION_ID == 118 rows are DROPPED at ingest, including the
      float-string form "118.0" (the deliberate `.split('.')` parse). The drop is
      byte-identical in BOTH ingest copies (routes/upload.confirm_mapping and
      core/ingest_service.ingest_dataframe); this exercises the latter.
  #4  Ingesting the internal side triggers the post-ingest auto-recon chain, so a
      freshly-ingested internal row matches a pre-existing bank counterpart.

Internal-side Fino ingest reads no files, so no on-disk fixture is needed.
"""
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, UploadSession, ReconStatus
from core.ingest_service import ingest_dataframe

DATE = "2026-04-15"
MAPPING = {"eko_tid": "eko_trxn_id", "tracking_number": "TrackingNumber",
           "amount": "Amount", "status": "Status"}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _session(db, partner="fino", side="internal", recon_date=DATE):
    sess = UploadSession(partner=partner, side=side, recon_date=recon_date,
                         original_filename="fino_dump.xlsx", column_mapping="{}")
    db.add(sess)
    db.commit()
    return sess


# ── #10 Fino ACCOUNT_ACTION_ID == 118 drop ────────────────────────────────────

def test_fino_action_118_dropped_including_float_string(db):
    df = pd.DataFrame([
        {"ACCOUNT_ACTION_ID": "118",   "eko_trxn_id": "T1", "TrackingNumber": "R1", "Amount": 100, "Status": "Success"},
        {"ACCOUNT_ACTION_ID": "10",    "eko_trxn_id": "T2", "TrackingNumber": "R2", "Amount": 200, "Status": "Success"},
        {"ACCOUNT_ACTION_ID": "118.0", "eko_trxn_id": "T3", "TrackingNumber": "R3", "Amount": 300, "Status": "Success"},
    ])
    sess = _session(db)
    out = ingest_dataframe(df, sess, MAPPING, db, "u1", "tester", do_auto_recon=False)
    # Only the action-id 10 row survives; both 118 and 118.0 are skipped.
    assert out["row_count"] == 1
    assert out["skipped"] >= 2
    kept = db.query(Transaction).filter_by(side="internal").all()
    assert [t.eko_tid for t in kept] == ["T2"]


def test_non_fino_action_118_is_kept(db):
    # The drop is Fino-only — an axis dump with action-id 118 keeps the row (#10).
    df = pd.DataFrame([
        {"ACCOUNT_ACTION_ID": "118", "eko_trxn_id": "A1", "TrackingNumber": "R1", "Amount": 100, "Status": "Success"},
    ])
    sess = _session(db, partner="axis")
    out = ingest_dataframe(df, sess, MAPPING, db, "u1", "tester", do_auto_recon=False)
    assert out["row_count"] == 1
    assert db.query(Transaction).filter_by(side="internal").count() == 1


# ── #4 ingest triggers the auto-recon chain ───────────────────────────────────

def test_ingesting_internal_auto_reconciles_against_existing_bank_row(db):
    # Pre-load an unmatched bank counterpart, then ingest the matching internal row.
    bank = Transaction(partner="fino", side="bank", recon_date=DATE, row_type="txn",
                       recon_status=ReconStatus.unmatched, eko_tid="TX",
                       tracking_number="RX", amount=500.0)
    db.add(bank)
    db.commit()

    df = pd.DataFrame([
        {"ACCOUNT_ACTION_ID": "10", "eko_trxn_id": "TX", "TrackingNumber": "RX", "Amount": 500, "Status": "Success"},
    ])
    sess = _session(db)
    ingest_dataframe(df, sess, MAPPING, db, "u1", "tester", do_auto_recon=True)

    db.refresh(bank)
    internal = db.query(Transaction).filter_by(side="internal", eko_tid="TX").one()
    # The post-ingest auto-recon pass ran and paired the two sides.
    assert bank.recon_status == ReconStatus.matched
    assert internal.recon_status == ReconStatus.matched
    assert bank.match_id == internal.match_id
