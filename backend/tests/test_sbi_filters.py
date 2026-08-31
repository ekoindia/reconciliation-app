"""
Tests for the SBI Kiosk result-view filters (display-time, additive).

These filter what is SHOWN from already-computed results; they do not change the
reconciliation run (#17 untouched). Dates are stored YYYY-MM-DD (same as the
HTML date picker), so the date filter matches.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User, SBIP01Result, SBIP02Result, SBIP03Result, SBIP04Result
from routes.sbi_kiosk import get_p01_results, get_p02_results, get_p03_results, get_p04_results

USER = User(id="u1", username="raj", role="user", permissions="{}")
RD = "2026-06-25"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def test_p01_transaction_date_filter(db):
    db.add(SBIP01Result(recon_date=RD, ko_id="KOA", bank_txn_date="2026-06-24", status="CREDITED"))
    db.add(SBIP01Result(recon_date=RD, ko_id="KOB", bank_txn_date="2026-06-23", status="PENDING"))
    db.add(SBIP01Result(recon_date=RD, ko_id="KOC", bank_txn_date="", deduct_date="2026-06-24", status="PENDING"))
    db.commit()
    out = get_p01_results(recon_date=RD, txn_date="2026-06-24", db=db, current_user=USER)
    # matches bank_txn_date OR deduct_date == 24th
    assert {r["ko_id"] for r in out["rows"]} == {"KOA", "KOC"}


def test_p01_ko_search(db):
    db.add(SBIP01Result(recon_date=RD, ko_id="1A999001", status="CREDITED"))
    db.add(SBIP01Result(recon_date=RD, ko_id="1A999002", status="PARTIAL"))
    db.commit()
    out = get_p01_results(recon_date=RD, ko_id="9001", db=db, current_user=USER)   # partial-KO search
    assert [r["ko_id"] for r in out["rows"]] == ["1A999001"]


def test_p02_reference_and_summary_reflects_filter(db):
    db.add(SBIP02Result(recon_date=RD, reference_number="REFAAA", match_status="Matched", bank_type="DR"))
    db.add(SBIP02Result(recon_date=RD, reference_number="REFBBB", match_status="Unmatched_Bank", bank_type="CR"))
    db.commit()
    out = get_p02_results(recon_date=RD, reference="AAA", db=db, current_user=USER)
    assert out["total"] == 1
    assert [r["reference_number"] for r in out["rows"]] == ["REFAAA"]
    # summary reflects the reference filter (only the Matched row remains)
    assert out["summary"] == {"Matched": 1}


def test_p03_csp_and_date(db):
    db.add(SBIP03Result(recon_date=RD, csp_code="CSP1", txn_date="2026-06-24", match_status="Matched"))
    db.add(SBIP03Result(recon_date=RD, csp_code="CSP2", txn_date="2026-06-23", match_status="Unmatched_Bank"))
    db.commit()
    out = get_p03_results(recon_date=RD, txn_date="2026-06-24", db=db, current_user=USER)
    assert [r["csp_code"] for r in out["rows"]] == ["CSP1"]
    out2 = get_p03_results(recon_date=RD, csp_code="CSP2", db=db, current_user=USER)
    assert [r["csp_code"] for r in out2["rows"]] == ["CSP2"]


def test_p04_csp_search(db):
    db.add(SBIP04Result(recon_date=RD, csp_code="CSPX", action_required="DEPOSIT"))
    db.add(SBIP04Result(recon_date=RD, csp_code="CSPY", action_required="NONE"))
    db.commit()
    out = get_p04_results(recon_date=RD, csp_code="CSPX", db=db, current_user=USER)
    assert [r["csp_code"] for r in out["rows"]] == ["CSPX"]
