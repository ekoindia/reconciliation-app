"""
Regression + characterization tests for the Open Items "Export Excel" button.

THE BUG: the export (routes/reports.export_open_items) queried ONLY the core
Transaction table. Module products (E-Value, BBPS) live in their own tables, so
exporting with partner=evalue produced an Excel with headers but ZERO rows — even
though the on-screen list (recon.get_open_items) showed hundreds, because the list
dispatches module partners through the _module_rows adapter.

The fix makes the export mirror the list's dispatch exactly:
  • module partner (evalue/bbps) → that module's rows
  • Partner = All (no partner)   → core ledger + every module product
  • core partner (fino/dmt/…)    → core ledger only

These tests pin every combination so the export can never silently diverge from
the screen again (behavior contract #14).
"""
import io
import asyncio
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (
    Base, User, Transaction, EvalueBankTxn, EvalueWalletLoad,
    BbpsBankTxn, BbpsInternal,
)
from routes.reports import export_open_items

USER = User(id="u1", username="admin", role="admin", permissions="{}")
RD = "2026-06-25"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def _read_excel(resp) -> pd.DataFrame:
    """Drain the StreamingResponse and parse the .xlsx back into a DataFrame."""
    async def _collect():
        chunks = []
        async for c in resp.body_iterator:
            chunks.append(c if isinstance(c, bytes) else c.encode())
        return b"".join(chunks)
    data = asyncio.run(_collect())
    return pd.read_excel(io.BytesIO(data))


def _seed_evalue(db):
    # one bank-side txn + one internal wallet-load, both open
    db.add(EvalueBankTxn(id="eb1", reco_acc_no="ACC1", txn_date=RD, utr="UTRBANK1",
                         amount=5000.0, dr_cr="CR", recon_status="unmatched_bank",
                         description="NEFT CR EKO"))
    db.add(EvalueWalletLoad(id="el1", reco_acc_no="ACC1", transaction_date=RD,
                            eko_trxn_id="EKO123", utr_number="UTRLOAD1", amount=100.0,
                            status="SUCCESS", recon_status="unmatched_load",
                            csp_code="CSP9", merchant_name="STAR COMM"))
    db.commit()


def _seed_core(db):
    db.add(Transaction(id="t1", partner="fino", side="bank", recon_date=RD,
                       transaction_date=RD, amount=2000.0, dr_cr="CR",
                       recon_status="unmatched", row_type="txn", utr_number="COREUTR1"))
    db.commit()


# ── THE BUG: evalue export must not be empty ───────────────────────────────────

def test_evalue_export_all_status_is_not_empty(db):
    _seed_evalue(db)
    resp = export_open_items(partner="evalue", recon_status="all", db=db, current_user=USER)
    df = _read_excel(resp)
    assert len(df) == 2                                  # was 0 before the fix
    assert set(df["Partner"]) == {"evalue"}
    # the two identifying values made it into the sheet
    assert "UTRBANK1" in set(df["UTR Number"].astype(str))
    assert "EKO123" in set(df["Eko TID"].astype(str))


def test_evalue_export_default_open_status(db):
    _seed_evalue(db)
    # no recon_status → module "open" set (unmatched_bank/unmatched_load are open)
    resp = export_open_items(partner="evalue", db=db, current_user=USER)
    df = _read_excel(resp)
    assert len(df) == 2
    assert set(df["Recon Status"]) == {"unmatched_bank", "unmatched_load"}


def test_bbps_export_uses_module_dispatch(db):
    # proves the module dispatch is not E-Value-specific
    db.add(BbpsBankTxn(id="bb1", client_ref="EKOB1", operator_ref="OPREF1",
                       transaction_date=RD, amount=300.0, status="Success",
                       recon_status="unmatched_bank"))
    db.add(BbpsInternal(id="bi1", eko_trxn_id="EKOB1", tracking_number="TRK1",
                        transaction_date=RD, amount=300.0, status="Success",
                        recon_status="unmatched_internal", csp_code="CSP1",
                        merchant_name="BBPS MERCHANT"))
    db.commit()
    resp = export_open_items(partner="bbps", recon_status="all", db=db, current_user=USER)
    df = _read_excel(resp)
    assert len(df) == 2
    assert set(df["Partner"]) == {"bbps"}
    assert "EKOB1" in set(df["Eko TID"].astype(str))


# ── Partner = All unions core ledger + modules ─────────────────────────────────

def test_all_partner_includes_core_and_modules(db):
    _seed_core(db)
    _seed_evalue(db)
    resp = export_open_items(partner=None, recon_status="all", db=db, current_user=USER)
    df = _read_excel(resp)
    partners = set(df["Partner"])
    assert "fino" in partners and "evalue" in partners
    assert len(df) == 3                                  # 1 core + 2 evalue


# ── Core partner stays core-only (no module bleed-in) ──────────────────────────

def test_core_partner_excludes_modules(db):
    _seed_core(db)
    _seed_evalue(db)
    resp = export_open_items(partner="fino", recon_status="all", db=db, current_user=USER)
    df = _read_excel(resp)
    assert set(df["Partner"]) == {"fino"}
    assert len(df) == 1


# ── New filters the export used to silently ignore ─────────────────────────────

def test_amount_min_filter_applies_to_modules(db):
    _seed_evalue(db)                                     # amounts 5000 (bank) and 100 (load)
    resp = export_open_items(partner="evalue", recon_status="all",
                             amount_min=1000.0, db=db, current_user=USER)
    df = _read_excel(resp)
    assert len(df) == 1
    assert float(df.iloc[0]["Amount"]) == 5000.0


def test_csp_name_filter_on_modules(db):
    _seed_evalue(db)
    resp = export_open_items(partner="evalue", recon_status="all",
                             csp_name="star", db=db, current_user=USER)
    df = _read_excel(resp)
    # only the internal load row carries a CSP name
    assert len(df) == 1
    assert df.iloc[0]["CSP Name"] == "STAR COMM"


def test_empty_result_still_valid_excel(db):
    # no data → headers-only sheet, but a valid file (not a crash)
    resp = export_open_items(partner="evalue", recon_status="all", db=db, current_user=USER)
    df = _read_excel(resp)
    assert len(df) == 0
    assert "Partner" in df.columns and "CSP Name" in df.columns
