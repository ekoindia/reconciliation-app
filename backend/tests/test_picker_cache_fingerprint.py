"""
The pair-picker's report-open cache must not survive a manual-pair change.

The Manual Match picker keeps only bank rows the reconciliation report calls open, which means
calling core.sbi_reports.reconcile(db, d) per date — expensive, so its bank-open id set is
memoised behind a data fingerprint (_picker_open_fingerprint) in a module-level dict.

reconcile() ALSO overlays SBIManualPair onto its bank rows, so a pair created or DELETED changes
the very "Match Status" the cache filters on. SBIManualPair was NOT part of the fingerprint and
nothing invalidated the cache on pair writes, so after an unpair the picker kept filtering
against a stale set: the row was open again in All Entries but missing from Manual Match — the
operator's "All Entries shows 2 open bank entries, Manual Match shows 1" for the same date.

Unpairing is the direction that shows FEWER; pairing can show more. Both are covered here.

Note the fingerprint is deliberately GLOBAL over pairs, not per-date: a pair's two legs may sit
on different dates, so a pair written for one date can change reconcile() for another.
"""
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, SBIManualPair, SBIBankTransaction, generate_id)
from routes.sbi_kiosk import _picker_open_fingerprint

D = "2026-08-20"
OTHER = "2026-08-21"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    # a bank row so the date isn't the trivial zero-bank shortcut
    s.add(SBIBankTransaction(id=generate_id(), upload_date=D, txn_date=D, description="CASH DEPOSIT",
                             ref_number="", ko_id="", debit=0.0, credit=49500.0, balance=100.0,
                             is_settlement=False))
    s.commit()
    yield s
    s.close()


def _pair(db, bank_date=D, data_date=D, at=None):
    p = SBIManualPair(id=generate_id(), bank_date=bank_date, data_date=data_date,
                      bank_key=f"bank|||{bank_date}|CR|49500.00|d=100.0",
                      data_key=f"kod|1A999012||{data_date}|49500.00|d=x",
                      bank_source="Bank Statement", data_source="KO Deposit",
                      bank_amount=49500.0, data_amount=49500.0, remark="operator match",
                      created_at=at or datetime.datetime(2026, 8, 31, 12, 0, 0))
    db.add(p); db.commit()
    return p


def test_creating_a_pair_moves_the_fingerprint(db):
    before = _picker_open_fingerprint(db, D)
    _pair(db)
    assert _picker_open_fingerprint(db, D) != before


def test_deleting_a_pair_moves_the_fingerprint(db):
    """The regression that produced 'All Entries 2, Manual Match 1' — unpairing reopens the row
    everywhere except the cached set."""
    p = _pair(db)
    warm = _picker_open_fingerprint(db, D)
    db.delete(p); db.commit()
    assert _picker_open_fingerprint(db, D) != warm


def test_a_pair_on_a_DIFFERENT_date_still_moves_this_date_fingerprint(db):
    """Legs may straddle dates, so pair state is fingerprinted globally, not per-date."""
    before = _picker_open_fingerprint(db, D)
    _pair(db, bank_date=OTHER, data_date=OTHER)
    assert _picker_open_fingerprint(db, D) != before


def test_replacing_a_pair_moves_the_fingerprint(db):
    """Count alone would be unchanged; max(created_at) has to carry the difference."""
    p = _pair(db, at=datetime.datetime(2026, 8, 31, 12, 0, 0))
    warm = _picker_open_fingerprint(db, D)
    db.delete(p); db.commit()
    _pair(db, at=datetime.datetime(2026, 8, 31, 13, 0, 0))
    assert _picker_open_fingerprint(db, D) != warm


def test_fingerprint_is_stable_when_nothing_changes(db):
    """It must still CACHE — a fingerprint that never repeats would recompute reconcile()
    on every request and hand back the ~6s/date cost the cache exists to avoid."""
    _pair(db)
    a = _picker_open_fingerprint(db, D)
    b = _picker_open_fingerprint(db, D)
    assert a == b
