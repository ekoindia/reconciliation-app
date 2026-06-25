"""
Characterization tests for the core matching engine (D1).

These PIN current behavior — they are not aspirational. Each asserts a
load-bearing invariant from docs/behavior-contract.md so that any future change
which silently reclassifies money, breaks match-ID audit references, or
double-counts funds fails CI. Cited by contract item number.

Covered:
  #1  match-ID format + MAX+1 (_next_seq) sequencing
  #5  _normalize float canonicalization (700.0 -> "700")
  #6  _build_key returns None when ANY field is empty
  #7  ±₹1 tolerance: within → matched, over → amount_mismatch (rows still consumed)
  #8  NEFT D+1 matches on UTR ONLY (amount is NOT checked, despite the docstring)
  #4  flag_same_side_duplicates re-labels only still-unmatched txn re-ingestions

Uses an in-memory SQLite session (autoflush=False, matching production).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, ReconStatus
from core.matching_engine import (
    _normalize, _build_key, _make_match_id, _next_seq,
    run_reconciliation, run_neft_d1_match, flag_same_side_duplicates,
    run_reversal_match,
)

DATE = "2026-04-15"
PREV = "2026-04-14"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def mk(db, side, partner="fino", recon_date=DATE, row_type="txn",
       recon_status=ReconStatus.unmatched, **kw):
    t = Transaction(partner=partner, side=side, recon_date=recon_date,
                    row_type=row_type, recon_status=recon_status, **kw)
    db.add(t)
    return t


# ── #5 _normalize ─────────────────────────────────────────────────────────────

def test_normalize_float_canonicalization():
    # Whole floats lose the decimal; fractional floats keep 2 places.
    assert _normalize(700.0) == "700"
    assert _normalize(25800.0) == "25800"
    assert _normalize(12.5) == "12.50"
    # None → empty (this is what lets _build_key short-circuit, #6)
    assert _normalize(None) == ""
    # strings are lower-cased, stripped, spaces removed
    assert _normalize("  Ab C ") == "abc"
    assert _normalize(700) == "700"


# ── #6 _build_key ─────────────────────────────────────────────────────────────

def test_build_key_joins_present_fields():
    t = Transaction(eko_tid="T1", tracking_number="R1")
    assert _build_key(t, ["eko_tid", "tracking_number"]) == "t1||r1"


def test_build_key_none_when_any_field_empty():
    # Missing utr_number → whole key is None so a lower-priority fallback can fire.
    t = Transaction(eko_tid="T1", tracking_number="R1", utr_number=None)
    assert _build_key(t, ["eko_tid", "tracking_number", "utr_number"]) is None


# ── #1 match-ID format + sequencing ───────────────────────────────────────────

def test_make_match_id_format():
    assert _make_match_id("fino", DATE, 1) == "FNO-20260415-0001"
    assert _make_match_id("fino", DATE, 43) == "FNO-20260415-0043"


def test_next_seq_is_max_plus_one_not_count(db):
    # Two ids with a GAP (0001, 0003). MAX+1 → 4; a COUNT-based impl would say 3.
    mk(db, "bank", eko_tid="A", match_id="FNO-20260415-0001",
       recon_status=ReconStatus.matched)
    mk(db, "bank", eko_tid="B", match_id="FNO-20260415-0003",
       recon_status=ReconStatus.matched)
    db.commit()
    assert _next_seq("fino", DATE, db) == 4


def test_next_seq_empty_series_starts_at_one(db):
    assert _next_seq("fino", DATE, db) == 1


# ── #7 tolerance ──────────────────────────────────────────────────────────────

def test_exact_match_pairs_both_sides_with_shared_id(db):
    b = mk(db, "bank", eko_tid="T1", tracking_number="R1", amount=100.0)
    i = mk(db, "internal", eko_tid="T1", tracking_number="R1", amount=100.0)
    db.commit()
    out = run_reconciliation("fino", DATE, db, "u1")
    assert out["matched"] == 1
    assert b.recon_status == ReconStatus.matched
    assert i.recon_status == ReconStatus.matched
    assert b.match_id == i.match_id and b.match_id.startswith("FNO-20260415-")
    assert b.matched_with_id == i.id and i.matched_with_id == b.id


def test_within_one_rupee_is_matched(db):
    mk(db, "bank", eko_tid="T1", tracking_number="R1", amount=100.0)
    mk(db, "internal", eko_tid="T1", tracking_number="R1", amount=100.5)  # diff 0.5 ≤ ₹1
    db.commit()
    out = run_reconciliation("fino", DATE, db, "u1")
    assert out["matched"] == 1
    b = db.query(Transaction).filter_by(side="bank").one()
    assert b.recon_status == ReconStatus.matched


def test_over_one_rupee_is_amount_mismatch_but_still_consumes_rows(db):
    # diff ₹5 → amount_mismatch; the pair is STILL consumed (both get a match_id).
    b = mk(db, "bank", eko_tid="T1", tracking_number="R1", amount=100.0)
    i = mk(db, "internal", eko_tid="T1", tracking_number="R1", amount=105.0)
    db.commit()
    out = run_reconciliation("fino", DATE, db, "u1")
    assert out["matched"] == 1                      # counted as a "match" attempt
    assert b.recon_status == ReconStatus.amount_mismatch
    assert i.recon_status == ReconStatus.amount_mismatch
    assert b.match_id == i.match_id and b.matched_with_id == i.id


def test_no_match_leaves_both_unmatched(db):
    b = mk(db, "bank", eko_tid="T1", tracking_number="R1", amount=100.0)
    i = mk(db, "internal", eko_tid="T2", tracking_number="R2", amount=100.0)
    db.commit()
    out = run_reconciliation("fino", DATE, db, "u1")
    assert out["matched"] == 0
    assert b.recon_status == ReconStatus.unmatched
    assert i.recon_status == ReconStatus.unmatched


def test_first_match_wins_extra_internal_flagged_duplicate(db):
    # One bank row, two identical internal rows → one matches, the other is duplicate.
    mk(db, "bank", eko_tid="T1", tracking_number="R1", amount=100.0)
    mk(db, "internal", eko_tid="T1", tracking_number="R1", amount=100.0)
    mk(db, "internal", eko_tid="T1", tracking_number="R1", amount=100.0)
    db.commit()
    out = run_reconciliation("fino", DATE, db, "u1")
    assert out["matched"] == 1
    statuses = sorted(t.recon_status for t in db.query(Transaction).filter_by(side="internal"))
    assert ReconStatus.matched in statuses
    assert ReconStatus.duplicate in statuses


# ── #8 NEFT D+1 matches on UTR ONLY ───────────────────────────────────────────

def test_neft_d1_matches_on_utr_ignoring_amount(db):
    # Yesterday's unmatched bank row + today's internal row, same UTR but WILDLY
    # different amounts → STILL matched. Proves amount is not part of the key (#8).
    b = mk(db, "bank", recon_date=PREV, utr_number="UTR123", amount=100.0)
    i = mk(db, "internal", recon_date=DATE, utr_number="UTR123", amount=999999.0)
    db.commit()
    out = run_neft_d1_match("fino", DATE, db, "u1")
    assert out["neft_d1_matched"] == 1
    assert b.recon_status == ReconStatus.matched
    assert i.recon_status == ReconStatus.matched
    assert b.match_id == i.match_id


def test_neft_d1_no_match_on_different_utr(db):
    mk(db, "bank", recon_date=PREV, utr_number="UTR123", amount=100.0)
    mk(db, "internal", recon_date=DATE, utr_number="UTR999", amount=100.0)
    db.commit()
    out = run_neft_d1_match("fino", DATE, db, "u1")
    assert out["neft_d1_matched"] == 0


# ── #4 flag_same_side_duplicates ──────────────────────────────────────────────

def test_flag_same_side_duplicates_keeps_one_flags_extras(db):
    mk(db, "bank", tracking_number="R9", eko_tid="A")
    mk(db, "bank", tracking_number="R9", eko_tid="A")   # re-ingested duplicate
    db.commit()
    out = flag_same_side_duplicates("fino", "bank", db)
    db.commit()
    rows = db.query(Transaction).filter_by(side="bank").all()
    statuses = sorted(r.recon_status for r in rows)
    assert out["duplicates_flagged"] == 1
    assert statuses.count(ReconStatus.duplicate) == 1   # exactly one survivor kept
    assert statuses.count(ReconStatus.unmatched) == 1


def test_flag_same_side_duplicates_ignores_non_txn_rows(db):
    # Reversal/fee rows legitimately share the original's tracking (#18) — never flagged.
    mk(db, "bank", tracking_number="R9", row_type="reversal")
    mk(db, "bank", tracking_number="R9", row_type="fee_charge")
    db.commit()
    out = flag_same_side_duplicates("fino", "bank", db)
    db.commit()
    assert out["duplicates_flagged"] == 0
    assert all(r.recon_status != ReconStatus.duplicate
               for r in db.query(Transaction).filter_by(side="bank"))


# ── #18 run_reversal_match (bank-to-bank pairing) ─────────────────────────────
# NOTE: tracking numbers here are all-DIGIT on purpose. run_reversal_match looks
# up originals with a SQL `IN` over _normalize()d reversal keys (which lower-cases),
# so it only pairs when the stored value equals its normalized form — true for the
# real digit RRNs/UTRs this code handles. Alphabetic test ids would silently miss.

def test_reversal_pairs_with_txn_original_across_dates(db):
    # Original sits on an EARLIER date; reversal on the upload date. The originals
    # query has NO date filter, so they still pair (#18 "across ALL dates").
    orig = mk(db, "bank", recon_date="2026-04-10", tracking_number="610508020080", row_type="txn")
    rev  = mk(db, "bank", recon_date=DATE, tracking_number="610508020080", row_type="reversal")
    db.commit()
    out = run_reversal_match("fino", DATE, db, "u1")
    assert out["reversal_matched"] == 1
    assert orig.recon_status == ReconStatus.reversal_matched
    assert rev.recon_status == ReconStatus.reversal_matched
    assert orig.match_id == rev.match_id


def test_fee_reversal_pairs_with_fee_charge_not_txn(db):
    # Type-aware: a fee_reversal must pair with a fee_charge, NOT a txn that happens
    # to share the same tracking number (IMPS fee shares the original's RRN, #18).
    fee  = mk(db, "bank", recon_date="2026-04-10", tracking_number="607410029036", row_type="fee_charge")
    txn  = mk(db, "bank", recon_date="2026-04-10", tracking_number="607410029036", row_type="txn")
    frev = mk(db, "bank", recon_date=DATE, tracking_number="607410029036", row_type="fee_reversal")
    db.commit()
    out = run_reversal_match("fino", DATE, db, "u1")
    assert out["reversal_matched"] == 1
    assert fee.recon_status == ReconStatus.reversal_matched
    assert frev.recon_status == ReconStatus.reversal_matched
    assert txn.recon_status == ReconStatus.unmatched        # the txn is left alone


def test_zip_drops_surplus_reversals(db):
    # 2 reversals but only 1 original for the same tracking → zip() pairs exactly 1
    # and silently drops the surplus reversal (#18).
    mk(db, "bank", recon_date="2026-04-10", tracking_number="606008009831", row_type="txn")
    mk(db, "bank", recon_date=DATE, tracking_number="606008009831", row_type="reversal")
    mk(db, "bank", recon_date=DATE, tracking_number="606008009831", row_type="reversal")
    db.commit()
    out = run_reversal_match("fino", DATE, db, "u1")
    assert out["reversal_matched"] == 1
    revs = db.query(Transaction).filter_by(row_type="reversal").all()
    statuses = sorted(r.recon_status for r in revs)
    assert statuses.count(ReconStatus.reversal_matched) == 1
    assert statuses.count(ReconStatus.unmatched) == 1


def test_airtel_style_reversal_pairs_on_original_utr(db):
    # Airtel: the reversal's tracking_number equals the original's utr_number
    # (APB_TXN_id), not its tracking_number — still pairs (#18).
    orig = mk(db, "bank", recon_date="2026-04-10", tracking_number="999999999999",
              utr_number="7297413813", row_type="txn")
    rev  = mk(db, "bank", recon_date=DATE, tracking_number="7297413813", row_type="reversal")
    db.commit()
    out = run_reversal_match("fino", DATE, db, "u1")
    assert out["reversal_matched"] == 1
    assert orig.recon_status == ReconStatus.reversal_matched
    assert rev.recon_status == ReconStatus.reversal_matched
