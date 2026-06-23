"""
Characterization tests for core.matching_engine.flag_same_side_duplicates.

Guards the conservative scoping that keeps it safe to run automatically after
every ingest: it flags ONLY still-'unmatched' txn-row duplicates, never a
matched row, never an operator-actioned row, and never a reversal/fee row
(which legitimately share tracking numbers — behaviour-contract #18).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, ReconStatus, generate_id
from core.matching_engine import flag_same_side_duplicates


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _t(tn, recon_status=ReconStatus.unmatched, row_type="txn", side="bank"):
    return Transaction(id=generate_id(), partner="qr", side=side, recon_date="2026-06-18",
                       tracking_number=tn, row_type=row_type,
                       recon_status=recon_status, amount=100.0)


def test_flags_unmatched_dupes_keeps_one(db):
    db.add_all([_t("AAA"), _t("AAA"), _t("AAA"), _t("BBB")])
    db.commit()
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 2
    aaa = db.query(Transaction).filter(Transaction.tracking_number == "AAA").all()
    assert [r.recon_status for r in aaa].count(ReconStatus.unmatched) == 1
    assert [r.recon_status for r in aaa].count(ReconStatus.duplicate) == 2
    # a unique tracking number is never touched
    bbb = db.query(Transaction).filter(Transaction.tracking_number == "BBB").one()
    assert bbb.recon_status == ReconStatus.unmatched


def test_keeps_the_matched_copy(db):
    db.add_all([_t("AAA", ReconStatus.unmatched),
                _t("AAA", ReconStatus.matched),
                _t("AAA", ReconStatus.unmatched)])
    db.commit()
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 2
    rows = db.query(Transaction).filter(Transaction.tracking_number == "AAA").all()
    assert sum(r.recon_status == ReconStatus.matched for r in rows) == 1
    assert sum(r.recon_status == ReconStatus.duplicate for r in rows) == 2


def test_never_flags_reversals(db):
    db.add_all([_t("AAA", row_type="reversal"), _t("AAA", row_type="reversal")])
    db.commit()
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 0
    assert all(r.recon_status == ReconStatus.unmatched for r in db.query(Transaction).all())


def test_never_flags_operator_actioned(db):
    db.add_all([_t("AAA", ReconStatus.src_assigned), _t("AAA", ReconStatus.src_assigned)])
    db.commit()
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 0


def test_idempotent(db):
    db.add_all([_t("AAA"), _t("AAA")])
    db.commit()
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 1
    assert flag_same_side_duplicates("qr", "bank", db)["duplicates_flagged"] == 0
