"""
Characterization tests for routes.upload._parse_recon_date.

Run from backend/:  pytest -q tests/test_parse_recon_date.py

Guards behaviour-contract-sensitive date parsing in the ingestion pipeline.
The QR Paypoint "ExportTransactionList" export dates each row as
"18 Jun 2026 11:59 PM" — a date whose own text contains spaces. A regression
here silently stores recon_date = NULL, making uploaded rows invisible in every
date-scoped view and unreconcilable (the original "QR uploads but isn't in the
data" bug). The same helper feeds the watch-folder path via
core.ingest_service, so both ingest copies depend on these cases.
"""
import pytest

from routes.upload import _parse_recon_date as p


@pytest.mark.parametrize("raw,expected", [
    # ── The QR Paypoint export format (the bug this test guards) ──────────────
    ("18 Jun 2026 11:59 PM", "2026-06-18"),
    ("18 Jun 2026 11:56 PM", "2026-06-18"),
    ("1 Jan 2026 12:00 AM",  "2026-01-01"),
    ("31 Dec 2025 09:36 PM", "2025-12-31"),
    # Space-delimited date with 24h / no time at all
    ("18 Jun 2026 23:59",    "2026-06-18"),
    ("18 Jun 2026 23:59:00", "2026-06-18"),
    ("18 Jun 2026",          "2026-06-18"),
    ("15 Apr 2026",          "2026-04-15"),
    # ── Existing formats must keep parsing exactly as before (no regression) ──
    ("2026-04-15",           "2026-04-15"),
    ("2026-04-15 06:06:36",  "2026-04-15"),   # timestamp — date has no spaces
    ("2026-04-15T06:06:36",  "2026-04-15"),   # ISO 'T' separator
    ("15-04-2026",           "2026-04-15"),   # day-first dashes
    ("15/04/2026",           "2026-04-15"),   # day-first slashes (NOT month-first)
    ("2026/04/15",           "2026-04-15"),
    ("15-Apr-2026",          "2026-04-15"),
])
def test_parse_recon_date_valid(raw, expected):
    assert p(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "garbage", "not a date", "18"])
def test_parse_recon_date_unparseable_returns_none(raw):
    assert p(raw) is None


def test_day_first_is_preserved():
    # 01/02/2026 must stay 1 Feb (day-first), never 2 Jan (month-first):
    # equalizing this would silently reclassify transactions onto wrong dates.
    assert p("01/02/2026") == "2026-02-01"
