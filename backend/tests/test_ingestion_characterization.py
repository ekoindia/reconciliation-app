"""
Characterization tests for the ingestion pure helpers (D1).

PIN current behavior of the parsing/classification functions in routes/upload.py
so a future edit that reassigns identifiers or reclassifies rows for live bank
formats fails CI. Cited by docs/behavior-contract.md item number.

Covered:
  #2  _parse_description regex ladder order (reversal-strip → two-segment IMPS →
      Charges/ → single IMPS → NEFT/RTGS → generic → bare digits)
  #3  _classify_bank_row precedence — reversal MUST be detected before fee_charge
  #24 _extract_bank_account 9–18 digit guard (header, else leading filename digits)

These are pure functions — no DB needed.
"""
from routes.upload import _parse_description, _classify_bank_row, _extract_bank_account


# ── #2 _parse_description ladder ──────────────────────────────────────────────

def test_two_segment_imps_extracts_tracking_and_tid():
    r = _parse_description("IMPS OUT IMPS/610508020080/3555907135")
    assert r["tracking_number"] == "610508020080"
    assert r["eko_tid"] == "3555907135"
    assert r["utr_number"] == "610508020080"


def test_single_segment_imps_tracking_only():
    r = _parse_description("IMPS OUT IMPS/606008009831")
    assert r["tracking_number"] == "606008009831"
    assert r["eko_tid"] is None


def test_fee_charge_description_tracking_only():
    r = _parse_description("FEE CHG IMPS Charges/607410029036")
    assert r["tracking_number"] == "607410029036"
    assert r["eko_tid"] is None


def test_reversal_suffix_stripped_before_extraction():
    # The -Reversal suffix is stripped so the reversal row gets the SAME tracking
    # as its original, enabling bank-to-bank pairing (#2 note).
    r = _parse_description("FEE CHG IMPS Charges/607410029036-Reversal")
    assert r["tracking_number"] == "607410029036"


def test_airtel_rev_imps_prefix_sets_tracking_and_utr_no_tid():
    r = _parse_description("REV IMPS-7297413813-CBIN-IMPS Return")
    assert r["tracking_number"] == "7297413813"
    assert r["utr_number"] == "7297413813"
    assert r["eko_tid"] is None


def test_neft_rtgs_alnum_utr_plus_numeric_tid():
    r = _parse_description("NEFT/UTR12345678901/3555907135")
    assert r["utr_number"] == "UTR12345678901"
    assert r["eko_tid"] == "3555907135"


def test_two_segment_wins_over_single_segment_ladder_order():
    # A string matching BOTH the two-segment and single-segment rules must yield
    # the TWO-segment result (tid populated) — proving ladder order, not greediness.
    r = _parse_description("IMPS/123456789012/3555907135")
    assert r["eko_tid"] == "3555907135"      # two-segment ran first


def test_bare_digits_last_resort():
    r = _parse_description("SOME TXN 123456789 done")
    assert r["tracking_number"] == "123456789"


def test_empty_or_nonstring_returns_all_none():
    for bad in ("", None, 12345):
        r = _parse_description(bad)
        assert r == {"eko_tid": None, "tracking_number": None, "utr_number": None}


# ── #3 _classify_bank_row precedence ──────────────────────────────────────────

DESC = ["Description"]


def test_reversed_fee_is_fee_reversal_not_fee_matched():
    # The critical precedence: a reversed FEE CHG must NOT auto-close as fee_matched.
    rt, status = _classify_bank_row(
        {"Description": "FEE CHG IMPS Charges/607410029036-Reversal"}, DESC)
    assert (rt, status) == ("fee_reversal", "unmatched")


def test_airtel_rev_imps_is_reversal():
    rt, status = _classify_bank_row(
        {"Description": "REV IMPS-7297413813-CBIN-IMPS Return"}, DESC)
    assert (rt, status) == ("reversal", "unmatched")


def test_plain_fee_charge_is_fee_matched():
    rt, status = _classify_bank_row(
        {"Description": "FEE CHG IMPS Charges/607410029036"}, DESC)
    assert (rt, status) == ("fee_charge", "fee_matched")


def test_customer_registration_is_fee_matched():
    rt, status = _classify_bank_row(
        {"Description": "Customer Registration for DMT"}, DESC)
    assert (rt, status) == ("fee_charge", "fee_matched")


def test_fund_transfer_classified():
    rt, status = _classify_bank_row({"Description": "FUND TRANSFER to nodal"}, DESC)
    assert (rt, status) == ("fund_transfer", "fund_transfer")


def test_credit_only_via_debit_credit_columns_is_settlement_credit():
    cols = ["Description", "Debits", "Credits"]
    row = {"Description": "IMPS inward", "Debits": "0", "Credits": "5000"}
    assert _classify_bank_row(row, cols) == ("settlement_credit", "fund_transfer")


def test_debit_row_falls_through_to_txn():
    cols = ["Description", "Debits", "Credits"]
    row = {"Description": "IMPS/606008009831", "Debits": "5000", "Credits": "0"}
    assert _classify_bank_row(row, cols) == ("txn", "unmatched")


def test_dr_cr_indicator_credit_is_settlement_credit():
    cols = ["Description", "DR_CR"]
    assert _classify_bank_row({"Description": "x", "DR_CR": "CR"}, cols) \
        == ("settlement_credit", "fund_transfer")


def test_plain_imps_debit_is_txn():
    assert _classify_bank_row({"Description": "IMPS OUT IMPS/606008009831"}, DESC) \
        == ("txn", "unmatched")


# ── #24 _extract_bank_account digit guard ─────────────────────────────────────

def test_account_from_leading_filename_digits():
    assert _extract_bank_account("912020012345678_statement.xlsx") == "912020012345678"


def test_date_prefixed_filename_yields_no_account():
    # SMB_RED_BK_<date>… must NOT produce a bogus account; name doesn't start with
    # a 9–18 digit run.
    assert _extract_bank_account("SMB_RED_BK_20260101_dump.xlsx") is None


def test_short_digit_run_rejected():
    # 8 leading digits is below the 9-digit floor → None.
    assert _extract_bank_account("12345678_file.xlsx") is None
