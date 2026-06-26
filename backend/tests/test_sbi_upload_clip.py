"""
Regression test for the SBI upload "Data too long for column" failures.

A parsed cell can leak an over-long value into a VARCHAR column (the classic case:
a settlement narration leaking into ref_number VARCHAR(100)). MySQL (prod) rejects
"Data too long for column …" and fails the WHOLE upload; SQLite (dev) silently
accepts it — which is why these only ever broke on the server. The fix clips every
parsed string to its column width BEFORE insert, so uploads are robust on both DBs.

The bank-statement path was hardened first (dc35128); this suite also covers the
other five SBI upload endpoints (ko-limits, txn-report, csp-master, ko-cash-holding,
limit-failures) so none of them can 500 on an over-long cell.
"""
import io
import asyncio
import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import (
    Base, User, SBIBankTransaction,
    SBIKOLimits, SBITxnReport, SBICSPMaster, SBIKOCashHolding, SBILimitFailure,
)
from routes.sbi_kiosk import (
    _clip, upload_bank_statement,
    upload_ko_limits, upload_txn_report, upload_csp_master,
    upload_ko_cash_holding, upload_limit_failures,
)

USER = User(id="u1", username="raj", role="admin", permissions="{}")


class _UploadFileStub:
    def __init__(self, content: bytes, filename: str):
        self._c = content
        self.filename = filename

    async def read(self):
        return self._c


def _run(coro):
    return asyncio.run(coro)


def _xlsx(grid) -> bytes:
    """Build an .xlsx from a list-of-rows grid. The pandas-based uploads try
    engine='xlrd' first (which rejects xlsx on xlrd 2.x) then fall back to the
    default openpyxl reader — exactly the path a real .xlsx export takes."""
    wb = Workbook()
    ws = wb.active
    for r in grid:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


# ── _clip unit + bank-statement (the original fix) ────────────────────────────

def test_clip():
    assert _clip("X" * 130, 100) == "X" * 100
    assert _clip("short", 100) == "short"
    assert _clip(None, 10) == ""
    assert len(_clip("Y" * 999, 20)) == 20


def test_bank_statement_with_overlong_ref_uploads_and_clips(db):
    # A Ref-No value of 150 chars (no extractable ref in the description) would
    # overflow ref_number VARCHAR(100) and 500 on MySQL. With the fix the upload
    # succeeds and the stored value is clipped to 100.
    header = "Txn Date\tValue Date\tDescription\tRef No\tBranch\tDebit\tCredit\tBalance"
    long_ref = "X" * 150
    row = f"24/06/2026\t24/06/2026\tplain narration no reference here\t{long_ref}\t10521\t \t100.00\t3"
    content = ("metadata line\n" * 5 + header + "\n" + row).encode("utf-8")

    out = _run(upload_bank_statement(file=_UploadFileStub(content, "sbi.xls"),
                                     recon_date="", db=db, current_user=USER))
    assert out["inserted"] == 1
    bt = db.query(SBIBankTransaction).one()
    assert len(bt.ref_number) == 100        # clipped from 150 — would have crashed MySQL


def test_normal_statement_unaffected(db):
    header = "Txn Date\tValue Date\tDescription\tRef No\tBranch\tDebit\tCredit\tBalance"
    row = "24/06/2026\t24/06/2026\tBY TRANSFER-123 TXN@KO1A85058\tRRN12345\t10521\t \t500.00\t9"
    content = ("meta\n" * 5 + header + "\n" + row).encode("utf-8")
    out = _run(upload_bank_statement(file=_UploadFileStub(content, "sbi.xls"),
                                     recon_date="", db=db, current_user=USER))
    assert out["inserted"] == 1
    bt = db.query(SBIBankTransaction).one()
    assert bt.ref_number == "RRN12345"       # short value passes through unchanged


# ── The other five upload endpoints ───────────────────────────────────────────

def test_ko_limits_clips_overlong_field(db):
    # 'Limit Configured By' -> String(20); a 40-char value must clip, not crash.
    grid = [
        ["meta"], ["meta"], ["meta"],
        ["Type of Transaction", "Date of Transaction", "Limit Configured By",
         "KO ID", "Opening Limit", "Amount", "Closing Limit"],
        ["KO Deposit", "24/06/2026", "U" * 40, "KO9", "100", "50", "150"],
    ]
    out = _run(upload_ko_limits(file=_UploadFileStub(_xlsx(grid), "ko_limits.xlsx"),
                                db=db, current_user=USER))
    assert out["inserted"] == 1
    row = db.query(SBIKOLimits).one()
    assert len(row.limit_configured_by) == 20
    assert row.ko_id == "KO9"               # short match key untouched


def test_txn_report_clips_overlong_reference(db):
    # 'Reference Number' -> String(100); the classic leak. 150 -> 100, upload survives.
    grid = [
        ["meta"], ["meta"], ["meta"],
        ["Sr. No", "KO ID", "Transaction Date & Time", "Reference Number",
         "Type of Transaction", "From Account", "To Account", "Amount",
         "Customer Charge", "Journal Number", "Status", "Reversal Status",
         "SETTELMENT_ACCOUNT_", "KO HOLDING"],
        ["1", "KO5", "24/06/2026 10:00", "R" * 150, "Money Transfer", "FROM1",
         "TO1", "500", "5", "J1", "Success", "", "BC", "0"],
    ]
    out = _run(upload_txn_report(file=_UploadFileStub(_xlsx(grid), "txn.xlsx"),
                                 db=db, current_user=USER))
    assert out["inserted"] == 1
    row = db.query(SBITxnReport).one()
    assert len(row.reference_number) == 100
    assert row.ko_id == "KO5"


def test_csp_master_clips_overlong_ref(db):
    # 'Ref Number' -> String(100); header is row 0 for this file.
    grid = [
        ["CSP Code", "Ref Number", "Mode"],
        ["CSP9", "R" * 150, "Cash"],
    ]
    out = _run(upload_csp_master(file=_UploadFileStub(_xlsx(grid), "csp.xlsx"),
                                 db=db, current_user=USER))
    assert out["inserted"] == 1
    row = db.query(SBICSPMaster).one()
    assert len(row.ref_number) == 100
    assert row.csp_code == "CSP9"


def test_ko_cash_holding_clips_overlong_ko_id(db):
    # 'KO ID' -> String(20); a 40-char id must clip, not crash.
    grid = [
        ["meta"], ["meta"], ["meta"],
        ["KO ID", "Limit", "Opening Balance", "Cash Receipts", "Cash Payments",
         "KO Deposit", "KO Withdrawal", "Closing Balance"],
        ["K" * 40, "100", "10", "0", "0", "0", "0", "110"],
    ]
    out = _run(upload_ko_cash_holding(file=_UploadFileStub(_xlsx(grid), "cash.xlsx"),
                                      report_date="", db=db, current_user=USER))
    assert out["inserted"] == 1
    row = db.query(SBIKOCashHolding).one()
    assert len(row.ko_id) == 20


def test_limit_failures_clips_overlong_fields(db, monkeypatch):
    # limit-failures parses with xlrd directly (no pandas fallback). xlwt isn't
    # installed to author a .xls, so stub the workbook xlrd returns. csp_code is
    # String(20), user is String(50) — both must clip.
    grid = [
        ["m"], ["m"], ["m"], ["Sr", "Date", "CSP", "BC", "Amount", "User"],
        ["1", "24/06/2026", "C" * 40, "BC1", "100", "U" * 80],
    ]

    class _FakeSheet:
        def __init__(self, g):
            self._g = g
            self.nrows = len(g)
            self.ncols = max(len(r) for r in g)

        def cell_value(self, r, c):
            row = self._g[r]
            return row[c] if c < len(row) else ""

    class _FakeBook:
        def sheet_by_index(self, i):
            return _FakeSheet(grid)

    import xlrd
    monkeypatch.setattr(xlrd, "open_workbook", lambda **kw: _FakeBook())

    out = _run(upload_limit_failures(file=_UploadFileStub(b"ignored", "lf.xls"),
                                     db=db, current_user=USER))
    assert out["inserted"] == 1
    row = db.query(SBILimitFailure).one()
    assert len(row.csp_code) == 20
    assert len(row.user) == 50
    assert row.bc_id == "BC1"               # short value untouched
