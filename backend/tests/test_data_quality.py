"""
Tests for the pre-ingest data-quality profiler (roadmap 1.6).

profile_dataframe() is pure and read-only — it computes blank/amount/date parse
rates, a duplicate-key rate, a control total, and a non-blocking warnings list
over an already-parsed DataFrame, without ever mutating it or affecting ingest.
"""
import pandas as pd

from core.data_quality import profile_dataframe

MAPPING = {"eko_tid": "TID", "tracking_number": "RRN",
           "amount": "Amount", "transaction_date": "TxnDate"}


def _clean_df():
    return pd.DataFrame([
        {"TID": "T1", "RRN": "610508020080", "Amount": "100.50", "TxnDate": "2026-04-15"},
        {"TID": "T2", "RRN": "610508020081", "Amount": "1,200",   "TxnDate": "15/04/2026"},
        {"TID": "T3", "RRN": "610508020082", "Amount": "50",      "TxnDate": "18 Jun 2026"},
    ])


def test_clean_file_has_no_warnings_and_correct_totals():
    p = profile_dataframe(_clean_df(), MAPPING)
    assert p["rows"] == 3
    assert p["has_warnings"] is False
    assert p["amount"]["parse_rate"] == 1.0
    assert p["amount"]["sum"] == 1350.5            # 100.50 + 1200 + 50 (commas stripped)
    assert p["date"]["parse_rate"] == 1.0
    assert p["columns_mapped"]["eko_tid"]["blank_rate"] == 0.0


def test_blank_key_column_warns():
    df = pd.DataFrame([
        {"TID": "", "RRN": "610508020080", "Amount": "100", "TxnDate": "2026-04-15"},
        {"TID": "", "RRN": "610508020081", "Amount": "100", "TxnDate": "2026-04-15"},
        {"TID": "T3", "RRN": "610508020082", "Amount": "100", "TxnDate": "2026-04-15"},
    ])
    p = profile_dataframe(df, MAPPING)
    assert p["columns_mapped"]["eko_tid"]["blank_rate"] == round(2 / 3, 4)
    assert p["has_warnings"] is True
    assert any("eko_tid" in w for w in p["warnings"])


def test_unparseable_amount_warns():
    df = pd.DataFrame([
        {"TID": "T1", "RRN": "R1", "Amount": "ABC",  "TxnDate": "2026-04-15"},
        {"TID": "T2", "RRN": "R2", "Amount": "100",  "TxnDate": "2026-04-15"},
    ])
    p = profile_dataframe(df, MAPPING)
    assert p["amount"]["parse_rate"] == 0.5
    assert p["amount"]["sum"] == 100.0
    assert any("amounts parse" in w for w in p["warnings"])


def test_duplicate_key_rate_and_warning():
    df = pd.DataFrame([
        {"TID": "T1", "RRN": "DUP", "Amount": "100", "TxnDate": "2026-04-15"},
        {"TID": "T2", "RRN": "DUP", "Amount": "100", "TxnDate": "2026-04-15"},
        {"TID": "T3", "RRN": "DUP", "Amount": "100", "TxnDate": "2026-04-15"},
        {"TID": "T4", "RRN": "UNIQUE", "Amount": "100", "TxnDate": "2026-04-15"},
    ])
    p = profile_dataframe(df, MAPPING)
    # 3 'DUP' rows → 2 extras out of 4 non-blank keys = 0.5
    assert p["duplicate_key"]["extra_rows"] == 2
    assert p["duplicate_key"]["dup_rate"] == 0.5
    assert any("duplicate tracking_number" in w for w in p["warnings"])


def test_empty_frame_is_safe():
    p = profile_dataframe(pd.DataFrame(), MAPPING)
    assert p["rows"] == 0
    assert p["has_warnings"] is False


def test_unmapped_columns_are_ignored():
    # A mapping pointing at a column not in the file must not crash or warn.
    df = pd.DataFrame([{"TID": "T1"}])
    p = profile_dataframe(df, {"amount": "NotThere", "eko_tid": "TID"})
    assert "amount" not in p
    assert p["columns_mapped"]["eko_tid"]["blank_rate"] == 0.0
