"""
core/data_quality.py

Pre-ingest data-quality profiler (roadmap 1.6 — additive, read-only).

profile_dataframe() computes a per-file quality snapshot over an already-parsed
DataFrame: row count, per-mapped-column blank rate, parseable-amount rate +
control total, date-parse rate, duplicate-key rate, and a non-blocking list of
threshold breaches.

It READS ONLY. It never mutates the DataFrame, never calls or alters the ingest
classification / `_parse_description` / `_auto_detect_amount` / FAILED_STATUSES
logic, and cannot change which rows get ingested (behavior-contract #3/#9). The
result is stored on IngestionEvent.dq_profile and returned as a NEW Step-3 field
(`data_quality`, additive per #25) — purely observational.
"""
import re
from collections import Counter

# Non-blocking warning thresholds (display-only; tune freely).
_BLANK_RATE_WARN  = 0.20     # a mapped KEY column more than 20% blank
_AMOUNT_RATE_WARN = 0.95     # fewer than 95% of rows have a parseable amount
_DATE_RATE_WARN   = 0.95     # fewer than 95% parseable dates
_DUP_RATE_WARN    = 0.10     # more than 10% duplicate key values in-file

_KEY_FIELDS = ("eko_tid", "tracking_number", "utr_number")
_BLANK_TOKENS = ("", "nan", "none", "null", "na", "n/a", "-")


def _is_blank(v) -> bool:
    return str(v).strip().lower() in _BLANK_TOKENS if v is not None else True


def _parse_amount(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def _looks_like_date(v) -> bool:
    s = str(v).strip()
    if _is_blank(s):
        return False
    # Permissive: a 4-digit year plus a separator (2026-04-15, 18 Jun 2026), or a
    # dd/mm/yy(yy)-style group. Display metric only — not the real date parser.
    return (bool(re.search(r"\d{4}", s)) and bool(re.search(r"[-/.\s]", s))) \
        or bool(re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", s))


def profile_dataframe(df, mapping_dict=None) -> dict:
    """Return a read-only data-quality profile for an already-parsed DataFrame."""
    mapping_dict = mapping_dict or {}
    n = int(len(df))
    out = {"rows": n, "warnings": []}
    if n == 0:
        out["has_warnings"] = False
        return out

    cols = {str(c) for c in df.columns}

    # ── Per mapped-column blank rate ─────────────────────────────────────────
    colstats = {}
    for std, fcol in mapping_dict.items():
        if not fcol or str(fcol) not in cols:
            continue
        blanks = sum(1 for v in df[fcol] if _is_blank(v))
        rate = round(blanks / n, 4)
        colstats[std] = {"file_col": fcol, "blank_rate": rate}
        if std in _KEY_FIELDS and rate > _BLANK_RATE_WARN:
            out["warnings"].append(f"{std} ({fcol}) is {round(rate * 100)}% blank")
    out["columns_mapped"] = colstats

    # ── Parseable-amount rate + control total ────────────────────────────────
    amt_col = mapping_dict.get("amount")
    if amt_col and str(amt_col) in cols:
        parsed = [_parse_amount(v) for v in df[amt_col]]
        ok = [p for p in parsed if p is not None]
        rate = round(len(ok) / n, 4)
        out["amount"] = {"file_col": amt_col, "parse_rate": rate, "sum": round(sum(ok), 2)}
        if rate < _AMOUNT_RATE_WARN:
            out["warnings"].append(f"only {round(rate * 100)}% of amounts parse as numbers")

    # ── Date-parse rate ──────────────────────────────────────────────────────
    date_col = mapping_dict.get("transaction_date")
    if date_col and str(date_col) in cols:
        ok = sum(1 for v in df[date_col] if _looks_like_date(v))
        rate = round(ok / n, 4)
        out["date"] = {"file_col": date_col, "parse_rate": rate}
        if rate < _DATE_RATE_WARN:
            out["warnings"].append(f"only {round(rate * 100)}% of dates look parseable")

    # ── Duplicate-key rate (first available key field) ───────────────────────
    for kf in ("tracking_number", "eko_tid"):
        kcol = mapping_dict.get(kf)
        if not kcol or str(kcol) not in cols:
            continue
        vals = [str(v).strip() for v in df[kcol] if not _is_blank(v)]
        if vals:
            counts = Counter(vals)
            extras = sum(c - 1 for c in counts.values() if c > 1)   # rows beyond first per key
            dup_rate = round(extras / len(vals), 4)
            out["duplicate_key"] = {"field": kf, "file_col": kcol,
                                    "dup_rate": dup_rate, "extra_rows": extras}
            if dup_rate > _DUP_RATE_WARN:
                out["warnings"].append(f"{round(dup_rate * 100)}% duplicate {kf} values in-file")
        break

    out["has_warnings"] = bool(out["warnings"])
    return out
