"""
SRC-tagging a KO DEPOSIT row ('kod' namespace).

Deposits are open items in the unified view (they're the counterpart operators pair against) but
have NO P01–P04 result row, so the SRC write path — hard-wired to the four result tables — 404'd
and the UI showed no actions at all ("no option of selection, neither SRC nor match"). The 'kod'
namespace tags the SOURCE row (SBIKOLimits) directly, keyed on stable CONTENT
(ko|amount|date|datetime) so the tag survives a recon re-run AND a file re-upload — strictly
better than a surrogate id. Note SBIKOLimits has no `recon_date` column: the overlay's business
date comes from txn_date (a naive row.recon_date would AttributeError).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User, SBIKOLimits, SBISrcAssignment, SrcCode, generate_id
from routes.sbi_kiosk import (assign_src, remove_src, get_unified, _src_key,
                              SBISRCIn, SBISRCRemoveIn)

DATE = "2026-08-25"
USER = User(id="u1", username="raj", role="user", permissions='{"src_assign": true}')


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    s.add(SrcCode(id=generate_id(), code="OTHER", is_active=True))   # catalog must know the code
    s.commit()
    yield s
    s.close()


def _dep(db, amount=100.0, ko="1A999004", dt="2026-08-25 10:00:00"):
    w = SBIKOLimits(id=generate_id(), upload_date=DATE, txn_date=DATE, txn_datetime=dt,
                    ko_id=ko, txn_type="KO Deposit", amount=amount)
    db.add(w); db.commit(); return w


def _rows(db):
    return get_unified(recon_date=DATE, page=1, page_size=200, db=db, current_user=USER)["rows"]


def _assign(db, dep_id, code="OTHER"):
    return assign_src(SBISRCIn(process="kod", result_id=dep_id, src_code=code, src_note=None),
                      db=db, current_user=USER)


# ── the key itself ────────────────────────────────────────────────────────────
def test_kod_key_is_content_based_and_distinguishes_duplicates():
    a = _src_key("kod", {"ko_id": "K1", "amount": 100.0, "txn_date": DATE, "txn_datetime": "t1"})
    b = _src_key("kod", {"ko_id": "K1", "amount": 100.0, "txn_date": DATE, "txn_datetime": "t2"})
    assert a and b and a != b          # same ko/amount/date, different datetime → distinct keys
    # identical content → identical key (this is what survives a re-upload)
    assert a == _src_key("kod", {"ko_id": "K1", "amount": 100.0, "txn_date": DATE, "txn_datetime": "t1"})


# ── end to end ────────────────────────────────────────────────────────────────
def test_deposit_is_actionable_and_taggable(db):
    w = _dep(db)
    row = next(r for r in _rows(db) if r["source"] == "KO Deposit")
    # the row now carries what the UI needs to render its actions
    assert row["status"] == "Unmatched"
    assert row["result_process"] == "kod" and row["result_id"] == w.id

    out = _assign(db, w.id)                      # no more 404 / "no stable key"
    assert out["src_code"] == "OTHER"
    assert db.query(SBISrcAssignment).count() == 1
    sa = db.query(SBISrcAssignment).first()
    assert sa.process == "kod" and sa.recon_date == DATE   # business date from txn_date, not recon_date

    tagged = next(r for r in _rows(db) if r["source"] == "KO Deposit")
    assert tagged["src_code"] == "OTHER"          # overlay shows on the unified row


def test_deposit_src_survives_reupload(db):
    # The whole point of a CONTENT key: delete + recreate the deposit with a NEW id but identical
    # content (what a file re-upload does) — the tag must still apply.
    w = _dep(db)
    _assign(db, w.id)
    db.delete(w); db.commit()
    _dep(db)                                      # new id, same ko/amount/date/datetime
    again = next(r for r in _rows(db) if r["source"] == "KO Deposit")
    assert again["src_code"] == "OTHER"


def test_tag_does_not_fan_out_across_two_same_amount_deposits(db):
    w1 = _dep(db, amount=100.0, dt="2026-08-25 10:00:00")
    _dep(db, amount=100.0, dt="2026-08-25 16:30:00")   # same ko+amount+date, different time
    _assign(db, w1.id)
    deps = [r for r in _rows(db) if r["source"] == "KO Deposit"]
    assert len(deps) == 2
    assert sum(1 for r in deps if r["src_code"]) == 1   # exactly one tagged, never both


def test_remove_src_on_deposit(db):
    w = _dep(db)
    _assign(db, w.id)
    remove_src(SBISRCRemoveIn(process="kod", result_id=w.id), db=db, current_user=USER)
    assert db.query(SBISrcAssignment).count() == 0
    assert next(r for r in _rows(db) if r["source"] == "KO Deposit")["src_code"] is None
