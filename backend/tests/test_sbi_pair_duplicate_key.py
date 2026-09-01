"""
Two business-identical KO rows must BOTH be pairable.

Manual pairs persist as a read-time overlay keyed on stable business content (never row ids)
so they survive a re-upload — behavior-contract #17. `_row_disc` is meant to keep two
business-identical rows apart, and for KO rows it uses txn_datetime. But in this feed that
timestamp is a BATCH stamp (one stamp covers ~5-9 rows), so a KO depositing the SAME amount
twice on the SAME day in one batch produces two rows with a BYTE-IDENTICAL key.

The write guard held `used_keys` as a SET, so once any pair consumed that key the second
physical row could never be paired — it failed with "already manually matched" even though
nothing had consumed it. That is the operator report: a Rs 49,500 KO Deposit that would not
match, reported only as ". 1 failed".

The read side (`_apply_pairs`) was always occurrence-aware — it consumes one (pair, leg) per
row, so a single pair can never flip both rows. These pin the write guard to the same rule.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (Base, User, SBIKOLimits, SBIBankTransaction,
                             SBIManualPair, generate_id)
from routes.sbi_kiosk import (create_manual_pairs, ManualPairBulkIn, ManualPairIn,
                              _data_descriptor, _key_capacity)

DATE = "2026-08-27"
STAMP = "27-08-2026 03:27:10 pm"          # one batch stamp shared by many rows
KO = "1A999012"                            # reserved test range — never a live KO id
USER = User(id="u1", username="raj", role="user", permissions='{"src_assign": true}')


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def _deposit(db, amount, stamp=STAMP, ko=KO, opening=None):
    r = SBIKOLimits(id=generate_id(), upload_date=DATE, txn_date=DATE, txn_datetime=stamp,
                    ko_id=ko, txn_type="KO Deposit", amount=amount, opening_limit=opening)
    db.add(r); db.commit()
    return r


def _bank(db, amount, balance):
    b = SBIBankTransaction(id=generate_id(), upload_date=DATE, txn_date=DATE,
                           description="CASH DEPOSIT-CASH DEPOSIT SELF--", ref_number="",
                           ko_id="", debit=0.0, credit=amount, balance=balance,
                           is_settlement=False)
    db.add(b); db.commit()
    return b


def _pair(db, bank_row, ko_row):
    return create_manual_pairs(
        ManualPairBulkIn(pairs=[ManualPairIn(bank_id=bank_row.id, data_id=ko_row.id,
                                             data_source="KO Deposit")],
                         remark="operator matched cash deposit"),
        db=db, current_user=USER)


def test_the_two_rows_really_do_share_one_key(db):
    """If this ever stops being true the rest of the file is testing nothing."""
    a = _deposit(db, 49500.0, opening=-24206.0)
    b = _deposit(db, 49500.0, opening=-73706.0)
    assert _data_descriptor(a, "KO Deposit")["key"] == _data_descriptor(b, "KO Deposit")["key"]


def test_second_identical_deposit_can_still_be_paired(db):
    """The regression: pairing the first row used to make the second permanently unpairable."""
    a = _deposit(db, 49500.0, opening=-24206.0)
    b = _deposit(db, 49500.0, opening=-73706.0)
    b1, b2 = _bank(db, 49500.0, 6467837.11), _bank(db, 49500.0, 5558662.11)

    assert _pair(db, b1, a)["paired"] == 1
    out = _pair(db, b2, b)
    assert out["paired"] == 1, out["results"]          # was 0 paired / 1 failed
    assert db.query(SBIManualPair).count() == 2


def test_a_third_pair_on_an_exhausted_key_is_still_rejected(db):
    """Occurrence-aware, not permissive: capacity is the number of physical rows."""
    a = _deposit(db, 49500.0, opening=-24206.0)
    b = _deposit(db, 49500.0, opening=-73706.0)
    banks = [_bank(db, 49500.0, 100.0 + i) for i in range(3)]
    assert _pair(db, banks[0], a)["paired"] == 1
    assert _pair(db, banks[1], b)["paired"] == 1

    out = _pair(db, banks[2], a)                       # both occurrences now consumed
    assert out["paired"] == 0 and out["errors"] == 1
    assert "already manually matched" in out["results"][0]["error"]


def test_the_failure_reason_names_the_duplicate_count(db):
    """The operator saw only '1 failed'; the reason must be actionable."""
    a = _deposit(db, 49500.0, opening=-24206.0)
    b = _deposit(db, 49500.0, opening=-73706.0)
    banks = [_bank(db, 49500.0, 100.0 + i) for i in range(3)]
    _pair(db, banks[0], a); _pair(db, banks[1], b)
    err = _pair(db, banks[2], a)["results"][0]["error"]
    assert "all 2 identical rows" in err


def test_a_unique_row_is_still_strictly_one_to_one(db):
    """Non-colliding rows must keep the original strict 1:1 guard."""
    solo = _deposit(db, 12345.0, stamp="27-08-2026 09:00:00 am", opening=-1.0)
    b1, b2 = _bank(db, 12345.0, 900.0), _bank(db, 12345.0, 901.0)
    assert _pair(db, b1, solo)["paired"] == 1
    out = _pair(db, b2, solo)
    assert out["paired"] == 0 and out["errors"] == 1
    assert "identical rows" not in out["results"][0]["error"]   # no duplicate-count suffix


def test_capacity_counts_only_genuinely_identical_rows(db):
    """Same amount+date but a DIFFERENT batch stamp is a different key -> capacity 1 each."""
    a = _deposit(db, 49500.0, stamp="27-08-2026 03:27:10 pm")
    b = _deposit(db, 49500.0, stamp="27-08-2026 03:32:07 pm")
    ka = _data_descriptor(a, "KO Deposit")["key"]
    assert ka != _data_descriptor(b, "KO Deposit")["key"]
    assert _key_capacity(db, "KO Deposit", ka, DATE, 49500.0) == 1


def test_bank_rows_keep_capacity_one(db):
    """Bank keys carry the running balance and had zero collisions in production."""
    bk = _bank(db, 49500.0, 6467837.11)
    from routes.sbi_kiosk import _bank_descriptor
    d = _bank_descriptor(bk)
    assert _key_capacity(db, d["source"], d["key"], d["date"], d["amount"]) == 1
