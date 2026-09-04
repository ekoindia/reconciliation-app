"""
A FAILED transaction-report row must not read as "Matched" against a bank movement.

P02 matches a bank statement line to a transaction report line by 20-digit reference. It did
that regardless of whether the report row SUCCEEDED, so a failed transaction whose money still
left the bank came back as a clean "Matched" on both legs. Operator (Rajendra):
"data side ki koi bhi failed transaction bank statement ki transaction se match nhi hona chahiye."

He is right: the bank moved real money for a transaction that failed. That should have come back
as a reversal credit; when it didn't, the debit is an exception to chase, not a reconciliation.
Production carried 758 such rows worth ~Rs 70.9 lakh, of which 457 debits (~Rs 51.7 lakh net) had
no offsetting credit at all — all of it hidden inside the "Matched" bucket.

Read-time only (behavior-contract #17): P02 results are untouched, so analytics and the reported
match rate do not move. This is the "Option A" the user chose.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, User, SBIBankTransaction, SBITxnReport, SBIP02Result,
                             generate_id)
from routes.sbi_kiosk import (_unified_entries, _MATCHED_UNIFIED, _CLOSED_UNIFIED,
                              _FAILED_BANK_MOVED, manual_pair_open_items)

DATE = "2026-09-01"
REF = "62441243284900128110"          # shape only — not a live reference
KO = "1A999012"                        # reserved test range, never a live KO
USER = User(id="u1", username="raj", role="admin", permissions='{}')


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def _matched_pair(db, status, ref=REF, amount=2100.0, bank_type="DR"):
    """A P02 'Matched' result linking one bank line to one report row of the given status."""
    b = SBIBankTransaction(id=generate_id(), upload_date=DATE, txn_date=DATE,
                           description=f"TO TRANSFER-{ref}", ref_number=ref, ko_id=KO,
                           debit=amount if bank_type == "DR" else 0.0,
                           credit=amount if bank_type == "CR" else 0.0,
                           balance=5000.0, is_settlement=False)
    t = SBITxnReport(id=generate_id(), upload_date=DATE, txn_date=DATE, ko_id=KO,
                     reference_number=ref, amount=amount, status=status,
                     txn_type="Money Transfer", source_file="txn.xlsx")
    db.add_all([b, t]); db.commit()
    r = SBIP02Result(id=generate_id(), recon_date=DATE, bank_txn_id=b.id, txn_report_id=t.id,
                     reference_number=ref, bank_amount=amount, bank_type=bank_type,
                     report_amount=amount, report_txn_type="Money Transfer",
                     match_status="Matched", success_status=status)
    db.add(r); db.commit()
    return b, t, r


def _sides(db):
    ents = _unified_entries(db, DATE, include_deposits=True)
    return ({e["status"] for e in ents if e["side"] == "bank"},
            {e["status"] for e in ents if e["side"] == "data"})


def test_failed_txn_does_not_read_as_matched_on_either_leg(db):
    _matched_pair(db, "Failure")
    bank, data = _sides(db)
    assert bank == {_FAILED_BANK_MOVED}, bank      # the screenshot showed BOTH as Matched
    assert data == {_FAILED_BANK_MOVED}, data
    assert _FAILED_BANK_MOVED not in _MATCHED_UNIFIED


def test_a_successful_txn_is_untouched(db):
    """The 678k genuine matches must not move."""
    _matched_pair(db, "Success")
    bank, data = _sides(db)
    assert bank == {"Matched"} and data == {"Matched"}


def test_credit_side_failure_also_flips(db):
    """Money returned or not, the rule is the same: a failed txn never reads Matched."""
    _matched_pair(db, "Failure", bank_type="CR")
    bank, data = _sides(db)
    assert bank == {_FAILED_BANK_MOVED} and data == {_FAILED_BANK_MOVED}


@pytest.mark.parametrize("status", ["Failure", "T_EXP", "Failure/Timed Out", "FAILED"])
def test_every_non_success_status_flips(db, status):
    _matched_pair(db, status)
    bank, _ = _sides(db)
    assert bank == {_FAILED_BANK_MOVED}


def test_blank_status_is_left_alone(db):
    """_is_txn_failed deliberately ignores a blank status — don't reclassify unknowns."""
    _matched_pair(db, "")
    bank, data = _sides(db)
    assert bank == {"Matched"} and data == {"Matched"}


def test_it_stays_out_of_the_pair_picker(db):
    """The row IS already tied to a bank line; re-offering it would invite a double match."""
    _matched_pair(db, "Failure")
    assert _FAILED_BANK_MOVED in _CLOSED_UNIFIED
    data = manual_pair_open_items(side="data", date_from=DATE, date_to=DATE,
                                  db=db, current_user=USER)
    assert data["total"] == 0, data["items"]


def test_unmatched_failed_row_still_reads_Failed_closed(db):
    """The pre-existing Failed(closed) bucket must not be swallowed by the new one."""
    t = SBITxnReport(id=generate_id(), upload_date=DATE, txn_date=DATE, ko_id=KO,
                     reference_number="62441243284900199999", amount=500.0, status="Failure",
                     txn_type="Money Transfer", source_file="txn.xlsx")
    db.add(t); db.commit()
    data = [e for e in _unified_entries(db, DATE, include_deposits=True) if e["side"] == "data"]
    assert [e["status"] for e in data] == ["Failed"]


def test_p02_results_are_not_mutated(db):
    """Option A is read-time only — analytics and the match rate must not move."""
    _, _, r = _matched_pair(db, "Failure")
    _unified_entries(db, DATE, include_deposits=True)
    db.refresh(r)
    assert r.match_status == "Matched"      # stored result untouched
