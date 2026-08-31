"""
The BC "Deposit" report's date header is TRUNCATED — the cell reads "Transaction Date &" with no
"Time". `upload_txn_report` looked the column up by exact key ('transaction_date_&_time' or
'transaction_date'), so it matched neither, every row ingested with a BLANK txn_date, and the
rows became invisible to every date-scoped surface (the reconciliation report, the unified
ledger, all four P0x runs). To the operator the upload simply looked like it had not worked
(Rajendra, 2026-08-31: "not able to upload this file in kiosk recon").

The date column is now resolved by PREFIX, so any wording variant works. These pin that the
truncated header parses, the full header still parses, and a file with no date column at all
degrades to blank rather than crashing.
"""
import re
import pytest
from routes.sbi_kiosk import _clean


def _resolve(headers):
    """Mirror of the resolver in upload_txn_report (same _clean + normalisation)."""
    h = [_clean(c) for c in headers]
    col_map = {c.lower().replace(' ', '_').replace('/', '_'): c for c in h if c}
    return next((v for k, v in col_map.items()
                 if re.sub(r'_+', '_', k).startswith('transaction_date')), '')


def test_truncated_deposit_header_resolves():
    # the real BC Deposit report header row
    h = ['Sr. No', 'KO ID', 'Transaction Date &', 'Reference Number', 'Type of Transaction',
         'From Account', 'To Account', 'Amount', 'Customer Charge', 'Journal Number', 'Status']
    assert _resolve(h) == 'Transaction Date &'


def test_full_header_still_resolves():
    h = ['Sr. No', 'KO ID', 'Transaction Date & Time', 'Reference Number', 'Status']
    assert _resolve(h) == 'Transaction Date & Time'


@pytest.mark.parametrize("variant", ['Transaction Date', 'Transaction  Date & Time', 'transaction date'])
def test_other_wordings_resolve(variant):
    assert _resolve(['Sr. No', variant, 'Amount']) == variant


def test_missing_date_column_degrades_to_blank_not_crash():
    assert _resolve(['Sr. No', 'KO ID', 'Amount']) == ''
