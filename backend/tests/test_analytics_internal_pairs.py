"""
An internal SELF-match must count as ONE transaction, not two.

`run_internal_match` pairs a Success row with its Refund/contra row — one transaction
recorded twice. Every other matched pair is deduped to a single headline transaction
(the bank leg), but BOTH legs of an internal self-match carry side='internal', so the
"drop the internal leg" rule cannot dedup it: it was exempted from the skip purely so
the bucket wouldn't zero out, and the pair was then counted TWICE. On production that
inflated matched by 10,479 transactions and ~11.4 crore of matched volume.

The dedup keys on `matched_with_id` (mutually set by all three pair passes), NOT on
`match_id`, because `run_internal_match` pass 3 (digikhata "net position") stamps ONE
shared match_id on N residual rows that are each a distinct wallet movement — keying
on match_id would collapse those N rows to 1.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, generate_id
from core.analytics import build_analytics, clear_analytics_cache

DATE = "2026-08-30"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    clear_analytics_cache()
    yield s
    s.close()
    clear_analytics_cache()


def _row(db, partner, side, status, amount, rid=None, mwid=None, mid=None):
    r = Transaction(id=rid or generate_id(), partner=partner, side=side, row_type="txn",
                    recon_date=DATE, recon_status=status, amount=amount,
                    matched_with_id=mwid, match_id=mid)
    db.add(r)
    return r


def _self_match(db, partner, amount, a="a", b="b", mid="M1"):
    """A Success + its contra, linked mutually — exactly what run_internal_match writes."""
    _row(db, partner, "internal", "internal_matched", amount, rid=a, mwid=b, mid=mid)
    _row(db, partner, "internal", "internal_matched", amount, rid=b, mwid=a, mid=mid)
    db.commit()


def test_internal_self_match_counts_once(db):
    _self_match(db, "axis", 50900.0)
    t = build_analytics(db, DATE, DATE)["totals"]
    assert t["matched"] == 1                       # was 2 — the pair was double-counted
    assert t["matched_volume"] == 50900.0          # and so was its volume
    assert t["transactions"] == 1


def test_both_legs_still_visible_in_the_per_side_breakdown(db):
    """The dedup is a headline-count rule; the bank-vs-internal split is explicitly
    documented as showing BOTH legs pre-dedup. It must not shrink."""
    _self_match(db, "axis", 100.0)
    a = build_analytics(db, DATE, DATE)
    assert a["totals"]["internal_transactions"] == 2
    assert a["totals"]["matched"] == 1


def test_unlinked_net_position_rows_are_not_collapsed(db):
    """digikhata pass 3 gives N residual rows ONE match_id and no matched_with_id.
    They are distinct movements — deduping by match_id would wrongly fold them to 1."""
    for i in range(4):
        _row(db, "digikhata", "internal", "internal_matched", 10.0 + i,
             rid=f"d{i}", mwid=None, mid="NETPOS1")
    db.commit()
    t = build_analytics(db, DATE, DATE)["totals"]
    assert t["matched"] == 4
    assert t["matched_volume"] == pytest.approx(46.0)


def test_mixed_pairs_and_net_position(db):
    _self_match(db, "axis", 500.0, a="p1", b="p2", mid="M1")
    _self_match(db, "axis", 700.0, a="p3", b="p4", mid="M2")
    _row(db, "digikhata", "internal", "internal_matched", 9.0, rid="n1", mid="NP")
    db.commit()
    t = build_analytics(db, DATE, DATE)["totals"]
    assert t["matched"] == 3                       # 2 pairs + 1 unlinked row (not 5)
    assert t["matched_volume"] == pytest.approx(1209.0)


def test_unequal_leg_amounts_take_the_canonical_leg_only(db):
    """85 production pairs differ by up to Rs 0.75 between legs (rounding crumbs inside
    the +/-Rs 1 tolerance). Volume must follow ONE leg, never half the sum of both."""
    _row(db, "axis", "internal", "internal_matched", 100.00, rid="a", mwid="b", mid="M")
    _row(db, "axis", "internal", "internal_matched", 100.75, rid="b", mwid="a", mid="M")
    db.commit()
    t = build_analytics(db, DATE, DATE)["totals"]
    assert t["matched"] == 1
    assert t["matched_volume"] == 100.00           # the lower-id leg, deterministically


def test_bank_internal_pairs_are_unaffected(db):
    """Regression guard: the ordinary cross-side dedup must behave exactly as before."""
    _row(db, "axis", "bank", "matched", 250.0)
    _row(db, "axis", "internal", "matched", 250.0)
    _row(db, "axis", "bank", "unmatched", 30.0)
    _row(db, "axis", "internal", "unmatched", 40.0)
    db.commit()
    t = build_analytics(db, DATE, DATE)["totals"]
    assert t["matched"] == 1                       # pair counted once (bank leg)
    assert t["matched_volume"] == 250.0
    assert t["unmatched"] == 2                     # orphans keep both sides
