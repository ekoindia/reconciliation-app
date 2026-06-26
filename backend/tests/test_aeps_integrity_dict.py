"""
Regression test for the AePS integrity-checks 500.

_aeps_integrity_dict built all four status messages in a dict literal, so they were
all evaluated eagerly. A PENDING record has cw_amount / tplus_amount = None, so the
unused 'passed'/'failed' f-strings still ran `{None:,.2f}` and crashed the endpoint —
500-ing the AePS page. The fix computes only the selected message, None-safely.
"""
from routes.upload import _aeps_integrity_dict
from models.database import PIIntegrityCheck


def test_pending_tplus_record_does_not_crash():
    r = PIIntegrityCheck(partner="aeps", recon_date="2026-06-24", status="pending_tplus",
                         cw_amount=None, tplus_amount=None, difference=None)
    d = _aeps_integrity_dict(r)
    assert d["status"] == "pending_tplus"
    assert "Waiting for T Plus" in d["message"]


def test_pending_cw_record_does_not_crash():
    r = PIIntegrityCheck(partner="aeps", recon_date="2026-06-24", status="pending_cw",
                         cw_amount=None, tplus_amount=None, difference=None)
    assert "Waiting for AePS Fingpay" in _aeps_integrity_dict(r)["message"]


def test_passed_record_formats_amounts():
    r = PIIntegrityCheck(partner="aeps", recon_date="2026-06-24", status="passed",
                         cw_amount=150000.0, tplus_amount=150000.0, difference=0.0)
    m = _aeps_integrity_dict(r)["message"]
    assert "PASSED" in m and "150,000.00" in m and "0.00" in m


def test_failed_with_none_field_is_safe():
    # Even a 'failed' record with a missing value must render, not crash.
    r = PIIntegrityCheck(partner="aeps", recon_date="2026-06-24", status="failed",
                         cw_amount=100.0, tplus_amount=90.0, difference=None)
    m = _aeps_integrity_dict(r)["message"]
    assert "FAILED" in m and "—" in m       # None difference renders as an em dash
