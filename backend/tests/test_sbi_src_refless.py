"""
SRC-tagging a REF-LESS SBI P02 bank row (cash deposits — "CSH DEP (CDM)…" — have no reference
number in the statement). Before the fix, `_src_key('p02', row)` returned None for these, so
Assign SRC failed with 400 "Row has no stable key to tag" (and, before the interceptor fix, that
422/400 blanked the whole app). The fallback keys such rows on `bank_txn_id` (unique per row,
stable across recon re-runs). These pin: the assign succeeds, the tag shows in the unified view,
it does NOT fan out across two identical same-amount deposits, and ref-based rows are unchanged.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, User, SBIBankTransaction, SBIP02Result,
                             SBISrcAssignment, generate_id)
from routes.sbi_kiosk import assign_src, get_unified, _src_key, SBISRCIn

DATE = "2026-08-26"
USER = User(id="u1", username="raj", role="user", permissions='{"src_assign": true}')


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def _cash_deposit(db, desc, amount, balance):
    """A ref-less cash-deposit bank credit + its Unmatched P02 result row."""
    b = SBIBankTransaction(id=generate_id(), upload_date=DATE, txn_date=DATE, description=desc,
                           ref_number="", ko_id="", debit=0.0, credit=amount, balance=balance,
                           is_settlement=False)
    db.add(b); db.commit()
    r = SBIP02Result(id=generate_id(), recon_date=DATE, bank_txn_id=b.id, reference_number="",
                     bank_amount=amount, bank_type="CR", match_status="Unmatched")
    db.add(r); db.commit()
    return b, r


def _assign(db, result_id, code="OTHER"):
    return assign_src(SBISRCIn(process="p02", result_id=result_id, src_code=code, src_note=None),
                      db=db, current_user=USER)


def test_refless_row_has_a_bank_txn_key():
    assert _src_key("p02", {"reference_number": "", "bank_txn_id": "B9"}) == "btxn|B9"
    assert _src_key("p02", {"reference_number": None, "bank_txn_id": "B9"}) == "btxn|B9"
    # ref present → unchanged; nothing to key on → None
    assert _src_key("p02", {"reference_number": "R1", "bank_type": "DR"}) == "R1|DR"
    assert _src_key("p02", {"reference_number": "", "bank_txn_id": None}) is None


def test_assign_src_on_refless_row_succeeds_and_shows_in_unified(db):
    b, r = _cash_deposit(db, "CSH DEP (CDM)-1234500000 2664--", 48000.0, 100000.0)
    out = _assign(db, r.id)                      # no more "Row has no stable key to tag"
    assert out["src_code"] == "OTHER" and out["match_key"] == f"btxn|{b.id}"
    assert db.query(SBISrcAssignment).count() == 1

    rows = get_unified(recon_date=DATE, page=1, page_size=100, db=db, current_user=USER)["rows"]
    tagged = [x for x in rows if x["side"] == "bank" and x.get("src_code")]
    assert len(tagged) == 1 and tagged[0]["src_code"] == "OTHER"


def test_tag_does_not_fan_out_across_identical_deposits(db):
    # two business-identical cash deposits (same amount/date/desc) but DISTINCT bank rows/balances
    b1, r1 = _cash_deposit(db, "CASH DEPOSIT-CASH DEPOSIT SELF--", 60000.0, 200000.0)
    b2, r2 = _cash_deposit(db, "CASH DEPOSIT-CASH DEPOSIT SELF--", 60000.0, 260000.0)
    _assign(db, r1.id)                           # tag ONLY the first
    rows = get_unified(recon_date=DATE, page=1, page_size=100, db=db, current_user=USER)["rows"]
    tagged = [x for x in rows if x["side"] == "bank" and x.get("src_code")]
    assert len(tagged) == 1                       # exactly one flips — never both
