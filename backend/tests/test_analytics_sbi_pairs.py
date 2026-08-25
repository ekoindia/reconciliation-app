"""
The analytics dashboard must reflect operator SBI Kiosk manual PAIRS.

The dashboard reads the P0x result tables directly and never applies `_apply_pairs` — unlike
the unified SBI Kiosk page and the downloadable report. Without the `analytics_pair_deltas`
overlay, doing a manual pair never moves the dashboard's P02 unmatched count (operator report,
2026-08-13: "auto-match left 30 unmatched; manually matched them; still 30"). These pin:

1. a manual pair moves the pair-closed P02 row unmatched -> matched in BOTH the headline
   (by_group / totals) AND the expandable P01-P04 breakdown, with volume moved too;
2. no pairs -> byte-identical to before (the overlay is a strict no-op);
3. it never reduces unmatched below the real count (conservative min-guard).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, User, SBIBankTransaction, SBITxnReport,
                             SBIP02Result, generate_id)
from core.analytics import build_analytics, clear_analytics_cache
from routes.sbi_kiosk import create_manual_pairs, ManualPairIn, ManualPairBulkIn

DATE = "2026-07-01"
REMARK = "operator confirmed pair"
USER = User(id="u1", username="raj", role="user", permissions='{"src_assign": true}')


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    clear_analytics_cache()   # module-level cache is keyed by bind id, but be tidy
    s.close()


def _kiosk(a):
    return next(g for g in a["by_group"] if g["group"] == "kiosk")


def _p02(a):
    return next(p for p in a["kiosk_processes"] if p["process"].startswith("P02"))


def _unmatched_bank(db, ref, ko="KO1", amount=100.0):
    """A bank statement row with a P02 'Unmatched' result row (an open bank item)."""
    b = SBIBankTransaction(id=generate_id(), upload_date=DATE, txn_date=DATE,
                           description=f"row {ref}", ref_number=ref, ko_id=ko,
                           debit=amount, credit=0.0, is_settlement=False)
    db.add(b); db.commit()
    db.add(SBIP02Result(id=generate_id(), recon_date=DATE, bank_txn_id=b.id,
                        reference_number=ref, bank_amount=amount, bank_type="DR",
                        match_status="Unmatched"))
    db.commit()
    return b


def _report(db, ref, ko="KO1", amount=100.0):
    t = SBITxnReport(id=generate_id(), upload_date=DATE, txn_date=DATE,
                     source_file="AEPS_Withdrawal_Transaction_Report.xlsx", ko_id=ko,
                     reference_number=ref, amount=amount, txn_type="AEPS OFFUS Withdrawal",
                     status="Success")
    db.add(t); db.commit(); return t


def _pair(db, b, t):
    return create_manual_pairs(
        ManualPairBulkIn(pairs=[ManualPairIn(bank_id=b.id, data_id=t.id, data_source="Txn Report")],
                         remark=REMARK),
        db=db, current_user=USER)


def test_manual_pair_moves_p02_unmatched_to_matched(db):
    b = _unmatched_bank(db, "R1", amount=100.0)
    t = _report(db, "R2", amount=100.0)

    # before the pair: the dashboard shows 1 unmatched P02 bank row
    a0 = build_analytics(db, date_from=DATE, date_to=DATE)
    assert _kiosk(a0)["unmatched"] == 1 and _kiosk(a0)["matched"] == 0
    assert _p02(a0)["unmatched"] == 1 and _p02(a0)["matched"] == 0

    out = _pair(db, b, t)
    assert out["paired"] == 1
    clear_analytics_cache()   # a real recon/upload clears it; the pair endpoint is separate

    # after: the pair-closed row is matched in the headline AND the P02 breakdown, volume moved
    a1 = build_analytics(db, date_from=DATE, date_to=DATE)
    k = _kiosk(a1)
    assert k["unmatched"] == 0 and k["matched"] == 1
    assert k["open_volume"] == 0.0 and k["matched_volume"] == 100.0
    p = _p02(a1)
    assert p["unmatched"] == 0 and p["matched"] == 1
    assert p["match_rate"] == 100.0


def test_no_pairs_is_unchanged(db):
    _unmatched_bank(db, "R1", amount=100.0)
    a = build_analytics(db, date_from=DATE, date_to=DATE)
    assert _kiosk(a)["unmatched"] == 1 and _kiosk(a)["matched"] == 0
    assert _p02(a)["unmatched"] == 1 and _p02(a)["matched"] == 0
    assert _kiosk(a)["open_volume"] == 100.0


def test_pair_on_one_of_two_unmatched_leaves_the_other_open(db):
    # isolation: pairing exactly one open bank row must move exactly one row, never both.
    b1 = _unmatched_bank(db, "R1", amount=100.0)
    _unmatched_bank(db, "R9", amount=200.0)      # a second, unrelated open bank row
    t = _report(db, "R2", amount=100.0)
    assert _pair(db, b1, t)["paired"] == 1
    clear_analytics_cache()

    a = build_analytics(db, date_from=DATE, date_to=DATE)
    assert _kiosk(a)["matched"] == 1 and _kiosk(a)["unmatched"] == 1     # one moved, one stays
    assert _kiosk(a)["open_volume"] == 200.0                            # the ₹200 row remains open
    assert _p02(a)["unmatched"] == 1 and _p02(a)["matched"] == 1
