"""
Characterization test for core.matching_engine.run_neft_d1_match match-ID
sequencing (behavior contract #1).

The D+1 pass must mint a UNIQUE sequential match_id per matched pair. The bug
this guards: SessionLocal uses autoflush=False, so allocating the sequence with
_next_seq() *inside* the match loop re-reads the same un-flushed MAX(seq) and
stamps ONE duplicate match_id on every pair in the run — which collapsed 2,484
QR pairs onto 8 IDs in production. The matching itself stays UTR-only (#8).

Uses an in-memory SQLite session with autoflush=False to reproduce production.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, ReconStatus, generate_id
from core.matching_engine import run_neft_d1_match


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _txn(side, recon_date, utr, amount):
    return Transaction(
        id=generate_id(), partner="qr", side=side, recon_date=recon_date,
        utr_number=utr, amount=amount, row_type="txn",
        recon_status=ReconStatus.unmatched,
    )


def test_neft_d1_mints_unique_match_ids(db):
    # 4 QR pairs: bank on D-1 (06-04), internal on D (06-05), matched by UTR.
    pairs = [("100000000001", 1000.0), ("100000000002", 2000.0),
             ("100000000003", 1500.0), ("100000000004", 9500.0)]
    for utr, amt in pairs:
        db.add(_txn("bank", "2026-06-04", utr, amt))
        db.add(_txn("internal", "2026-06-05", utr, amt))
    db.commit()

    res = run_neft_d1_match("qr", "2026-06-05", db, user_id=None)
    assert res["neft_d1_matched"] == 4
    assert res["prev_date"] == "2026-06-04"

    matched = db.query(Transaction).filter(
        Transaction.recon_status == ReconStatus.matched).all()
    assert len(matched) == 8  # 4 pairs × 2 sides

    bank_ids = [t.match_id for t in matched if t.side == "bank"]
    assert all(bank_ids), "every matched bank row must carry a match_id"
    # The core assertion: one UNIQUE match_id per pair (the bug stamped all '-0001')
    assert len(set(bank_ids)) == 4, f"match_ids must be unique, got {sorted(bank_ids)}"
    # Format + series stay intact (contract #1): QRC-20260605-000N
    for mid in bank_ids:
        assert mid.startswith("QRC-20260605-")

    # Each pair shares its id across the two sides, and pairing is correct.
    for b in [t for t in matched if t.side == "bank"]:
        i = db.query(Transaction).filter(Transaction.id == b.matched_with_id).first()
        assert i is not None and i.match_id == b.match_id
        assert abs((b.amount or 0) - (i.amount or 0)) <= 0.05


def test_neft_d1_single_pair_is_first_in_series(db):
    # The common NEFT case (1 pair) is unchanged: first id in the date series.
    db.add(_txn("bank", "2026-06-04", "111122223333", 500.0))
    db.add(_txn("internal", "2026-06-05", "111122223333", 500.0))
    db.commit()
    res = run_neft_d1_match("qr", "2026-06-05", db, user_id=None)
    assert res["neft_d1_matched"] == 1
    b = db.query(Transaction).filter(Transaction.side == "bank").first()
    assert b.match_id == "QRC-20260605-0001"
