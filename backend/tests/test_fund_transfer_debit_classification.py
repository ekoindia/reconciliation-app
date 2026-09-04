"""
"NEFT/" must not be mistaken for a fund transfer.

_classify_bank_row's fund-transfer branch auto-closes a row (row_type and recon_status both
'fund_transfer'), removing it from reconciliation entirely. Its pattern included an UNANCHORED
`FT\\s*/` — which also matches the tail of "NEF(T/)".

Axis DMT payouts are narrated "NEFT/AXISCN<ref>/<eko_tid>/<beneficiary>/<ifsc>", so every one of
them was classified as an own-account fund transfer and silently dropped from recon. Its internal
counterpart then sat Unmatched forever with no way to pair it: Manual Match lists only
unmatched/src_assigned, so the bank leg was unreachable — clearing its SRC changed nothing,
because it was never src_assigned.

Production held 341 such rows; 339 carried an Eko TID and 331 had an open internal twin on the
same partner+date, ~Rs 2.08 crore, growing ~25-44/day. All 339 narrations began with "NEFT", and
none match once the pattern is anchored.

Anchoring is deliberately preferred over gating the branch on DR/CR: a genuine OUTBOUND
own-account transfer is also a debit and must stay auto-closed.

routes/upload.py owns this function and core/ingest_service.py imports it, so this one change
fixes both the interactive and the watch-folder ingest path (contract #10, no mirror edit).
"""
import pytest

from routes.upload import _classify_bank_row

# Real Axis statement shape (see the axis_bank preset): the description column is "Particulars",
# which is not a desc/narr/remark name, so the classifier finds it via its IMPS|NEFT|... fallback.
AXIS_COLS = ["S.No", "Transaction Date (dd/mm/yyyy)", "Particulars", "Amount(INR)",
             "Debit/Credit", "Balance(INR)"]
FINO_COLS = ["Date", "Narration", "Debits", "Credits", "Balance"]


def _narr(narration, debit="100", credit="0"):
    """A statement whose description column IS found by name (Fino-style 'Narration').

    Axis names its column "Particulars", which the classifier does not recognise by name — it
    only finds that text through the IMPS|NEFT|RTGS|FEE CHG|FUND TRAN fallback scan. So a bare
    "FT/..." was never even visible to the fund-transfer branch on an Axis statement; what made
    it fire was "NEFT" putting the narration into `desc`, after which the unanchored FT/ matched
    the tail of "NEFT/". These cases therefore use a narration-bearing column set.
    """
    return ({"Date": "02-09-2026", "Narration": narration,
             "Debits": debit, "Credits": credit}, FINO_COLS)


def _axis(particulars, direction="DR"):
    return ({"S.No": "1", "Transaction Date (dd/mm/yyyy)": "02/09/2026",
             "Particulars": particulars, "Amount(INR)": "11,311.00",
             "Debit/Credit": direction, "Balance(INR)": "35,68,970.00"}, AXIS_COLS)


def test_neft_payout_is_a_transaction_not_a_fund_transfer():
    """The regression: an Axis NEFT DMT payout that went missing from recon."""
    row = _axis("NEFT/AXISCN1454736446/3575223755/BENE NAME/UTIB0000001")
    assert _classify_bank_row(*row) == ("txn", "unmatched")


def test_neft_out_variant_also_reads_as_a_transaction():
    """2 of the 339 production rows were narrated 'NEFT OUT NEFT/...'."""
    assert _classify_bank_row(*_axis("NEFT OUT NEFT/AXISCN999/123/BENE/UTIB0000001")) == ("txn", "unmatched")


def test_a_real_standalone_fund_transfer_is_still_auto_closed():
    """The anchor must not stop the branch doing its actual job."""
    for desc in ("FT/OWN ACCOUNT SWEEP", "FUND TRANSFER TO SELF",
                 "TRF TO POOL ACCOUNT", "TRANSFER TO NODAL"):
        assert _classify_bank_row(*_narr(desc)) == ("fund_transfer", "fund_transfer"), desc


def test_outbound_own_account_transfer_stays_closed_even_though_it_is_a_debit():
    """Why we anchored instead of gating on DR/CR — this debit must NOT reopen."""
    assert _classify_bank_row(*_narr("FT/SWEEP OUT", debit="100")) == ("fund_transfer", "fund_transfer")


def test_imps_payout_unchanged():
    """The other Axis payout format was never affected; pin it so it stays that way."""
    assert _classify_bank_row(*_axis("IMPS/P2A/123456789012/BENE/123/BANK/")) == ("txn", "unmatched")


# ── the surrounding ladder is order-sensitive; pin that it is untouched ───────

def test_reversal_still_beats_fee_and_fund_transfer():
    """Contract: the reversal check runs BEFORE fee_charge."""
    assert _classify_bank_row(*_axis("FEE CHG IMPS Charges/607410029036-Reversal")) == ("fee_reversal", "unmatched")
    assert _classify_bank_row(*_axis("REV IMPS-7297413813-CBIN-x")) == ("reversal", "unmatched")


def test_fee_charge_still_auto_closes():
    assert _classify_bank_row(*_axis("FEE CHG IMPS")) == ("fee_charge", "fee_matched")


def test_credit_only_row_still_settlement_credit():
    row = {"Date": "02-09-2026", "Narration": "NEFT INWARD", "Debits": "0", "Credits": "5000"}
    assert _classify_bank_row(row, FINO_COLS) == ("settlement_credit", "fund_transfer")


@pytest.mark.parametrize("desc,expected", [
    ("NEFT/AXISCN1/2/BENE/IFSC",  ("txn", "unmatched")),                 # payout — was broken
    ("FT/SOMETHING",              ("fund_transfer", "fund_transfer")),   # anchored at string start
    ("SOMETHING FT/X",            ("fund_transfer", "fund_transfer")),   # boundary after a space
    ("NEFT INWARD",               ("txn", "unmatched")),                 # no standalone FT/
    ("SWIFT/PAYMENT",             ("txn", "unmatched")),                 # must NOT match SWI(FT/)
])
def test_anchor_boundary_cases(desc, expected):
    assert _classify_bank_row(*_narr(desc)) == expected
