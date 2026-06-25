"""
core/recon_health.py

Recon-health watchdog (D2 — additive, read-only).

compute_recon_health() aggregates failure signals the dead EOD digest never
surfaced into one structured health report:
  * failed ingests          (1.4 ingestion ledger, status='failed')
  * blocked re-uploads      (1.4 ledger, status='blocked' — the double-count guard)
  * watch-folder errors     (WatchFolderConfig.last_trigger_status error/not_found)
  * data-quality warnings   (1.6 dq_profile.has_warnings)
  * low recon match rate     (recent ReconRun aggregates)

READ ONLY — it never writes, never runs reconciliation, and every individual
check is wrapped so one failing query can never break the report or raise into a
caller. Severity ranks: critical > warn > ok; 'unknown' marks a check that errored.
"""
import json
import datetime

_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}

# Tunable thresholds (display-only).
_MATCH_RATE_WARN = 0.50      # recent aggregate match rate below this → warn


def _check(key, label, fn):
    """Run one check fn() -> (severity, message, detail); never raises."""
    try:
        severity, message, detail = fn()
    except Exception as e:
        severity, message, detail = "unknown", f"check failed: {e}", None
    return {"key": key, "label": label, "severity": severity,
            "ok": severity == "ok", "message": message, "detail": detail}


def compute_recon_health(db, days: int = 7) -> dict:
    """Return a structured, read-only recon-health report over the last `days`."""
    from models.database import IngestionEvent, WatchFolderConfig
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    def _failed_ingests():
        n = db.query(IngestionEvent).filter(
            IngestionEvent.created_at >= since,
            IngestionEvent.status == "failed").count()
        if n == 0:
            return "ok", "No failed ingests", {"count": 0}
        return "warn", f"{n} failed ingest(s) in {days}d", {"count": n}

    def _blocked_ingests():
        n = db.query(IngestionEvent).filter(
            IngestionEvent.created_at >= since,
            IngestionEvent.status == "blocked").count()
        if n == 0:
            return "ok", "No blocked re-uploads", {"count": 0}
        # Blocked = the duplicate-slot guard fired; informational, not a failure.
        return "warn", f"{n} blocked re-upload attempt(s) in {days}d", {"count": n}

    def _watch_folders():
        rows = db.query(WatchFolderConfig).all()
        bad = [{"label": w.label, "status": w.last_trigger_status,
                "message": w.last_trigger_message}
               for w in rows if (w.last_trigger_status or "") in ("error", "not_found")]
        if not bad:
            return "ok", "Watch folders healthy", {"errors": 0}
        sev = "critical" if any(b["status"] == "error" for b in bad) else "warn"
        return sev, f"{len(bad)} watch folder(s) in error/not_found", {"folders": bad}

    def _dq_warnings():
        rows = db.query(IngestionEvent).filter(
            IngestionEvent.created_at >= since,
            IngestionEvent.dq_profile.isnot(None)).all()
        n = 0
        for e in rows:
            try:
                if json.loads(e.dq_profile).get("has_warnings"):
                    n += 1
            except Exception:
                continue
        if n == 0:
            return "ok", "No data-quality warnings", {"count": 0}
        return "warn", f"{n} ingest(s) with data-quality warnings in {days}d", {"count": n}

    def _match_rate():
        # Compute over the CURRENT state of recently-dated txn rows, NOT ReconRun
        # logs: ReconRun only records same-date run_reconciliation, so D+1 (QR),
        # reversal, and internal-self matches it never sees read as 0% and would
        # false-warn. Open = the Open-Items default {unmatched, src_assigned}
        # (behavior-contract #14); everything else (matched / reversal_matched /
        # fee_matched / duplicate / …) counts as resolved.
        from models.database import Transaction, ReconStatus
        cutoff = (datetime.datetime.utcnow().date()
                  - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        base = db.query(Transaction).filter(
            Transaction.row_type == "txn",
            Transaction.recon_date.like("____-__-__"),   # real dates only, skip 'auto'
            Transaction.recon_date >= cutoff,
        )
        total = base.count()
        if total < 50:   # volume guard — don't warn on a handful of rows
            return "ok", f"Too few recent txns to assess ({total})", {"total": total}
        open_n = base.filter(Transaction.recon_status.in_(
            [ReconStatus.unmatched, ReconStatus.src_assigned])).count()
        rate = round((total - open_n) / total, 4)
        detail = {"total": total, "open": open_n, "resolved": total - open_n, "rate": rate}
        if rate < _MATCH_RATE_WARN:
            return "warn", f"Only {round(rate * 100)}% of recent txns reconciled ({open_n} open)", detail
        return "ok", f"{round(rate * 100)}% of recent txns reconciled", detail

    checks = [
        _check("failed_ingests",  "Failed ingests",       _failed_ingests),
        _check("blocked_ingests", "Blocked re-uploads",   _blocked_ingests),
        _check("watch_folders",   "Watch folders",        _watch_folders),
        _check("dq_warnings",     "Data-quality warnings", _dq_warnings),
        _check("match_rate",      "Reconciliation rate",  _match_rate),
    ]
    status = max((c["severity"] for c in checks), key=lambda s: _RANK.get(s, 0))
    return {"status": status, "window_days": days, "checks": checks}
