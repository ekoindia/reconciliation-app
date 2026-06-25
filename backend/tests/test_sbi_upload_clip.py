"""
Regression test for the SBI bank-statement upload failure.

A settlement row can leak an over-long value into ref_number (VARCHAR(100)).
MySQL (prod) rejects "Data too long for column …" and fails the whole upload;
SQLite (dev) silently accepts it — which is why it only broke on the server.
The fix clips parsed string values to their column widths BEFORE insert, so it's
robust on both databases.
"""
import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User, SBIBankTransaction
from routes.sbi_kiosk import upload_bank_statement, _clip

USER = User(id="u1", username="raj", role="admin", permissions="{}")


class _UploadFileStub:
    def __init__(self, content: bytes, filename: str):
        self._c = content
        self.filename = filename

    async def read(self):
        return self._c


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


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
