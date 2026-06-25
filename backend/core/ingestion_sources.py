"""
core/ingestion_sources.py

Ingestion Sources catalog (roadmap 1.5 — additive, read-only).

compute_sources() answers "which partner hasn't delivered today" by aggregating
EXISTING data only — no new table, no migration, no change to upload/ingest/
scheduler:
  * expected sources   ← PartnerConfig (active partners × the sides they carry)
  * actual last delivery ← max(UploadSession.upload_date) joined through
                            Transaction (so a 'mixed' dump still credits each
                            partner it fans out to)
  * auto channel status ← WatchFolderConfig.last_trigger_* / is_enabled

READ ONLY. "Today" is evaluated in IST (UTC+5:30) to match the app's display
timezone pact, since timestamps are stored as naive UTC.
"""
import datetime

_IST = datetime.timedelta(hours=5, minutes=30)


def _ist_date(dt):
    return (dt + _IST).date() if dt else None


def compute_sources(db) -> dict:
    from sqlalchemy import func
    from models.database import (Transaction, UploadSession, WatchFolderConfig,
                                 PartnerConfig)

    today = _ist_date(datetime.datetime.utcnow())

    # last delivery per (partner, side), crediting mixed-dump fan-out via the join
    last_by_key = {}
    try:
        rows = (db.query(Transaction.partner, Transaction.side,
                         func.max(UploadSession.upload_date))
                  .join(UploadSession, Transaction.upload_session_id == UploadSession.id)
                  .group_by(Transaction.partner, Transaction.side).all())
        for partner, side, last in rows:
            if partner and side:
                last_by_key[(partner, side)] = last
    except Exception:
        pass

    # auto-channel watch folders
    watch_by_key = {}
    try:
        for w in db.query(WatchFolderConfig).all():
            watch_by_key[(w.partner, w.side)] = w
    except Exception:
        pass

    # A partner belongs to the core Transaction pipeline only if it has delivered
    # through it at least once. Module products (E-Value, BBPS, SBI, PG, AePS/QR
    # settlement) store data in their OWN tables, never touch Transaction — and some
    # of them ALSO have watch-folder configs — so a watch config alone is not proof.
    # Restricting to partners seen in the Transaction join keeps module products
    # (which would otherwise show a misleading "never delivered") out of this view;
    # their watch-config sides are then included so an un-delivered side of a real
    # core partner still shows. PartnerConfig is used only for labels.
    core_partners = {p for (p, _s) in last_by_key}
    keys = set(last_by_key) | {k for k in watch_by_key if k[0] in core_partners}
    labels = {}
    try:
        for p in db.query(PartnerConfig).all():
            labels[p.slug] = p.display_name
    except Exception:
        pass

    sources = []
    for (partner, side) in keys:
        last_upload = last_by_key.get((partner, side))
        w = watch_by_key.get((partner, side))
        watch_at = getattr(w, "last_triggered_at", None) if w else None
        last_activity = max([d for d in (last_upload, watch_at) if d], default=None)

        last_ist = _ist_date(last_activity)
        if last_ist is None:
            status, days_ago = "never", None
        elif last_ist == today:
            status, days_ago = "delivered", 0
        else:
            status, days_ago = "stale", (today - last_ist).days

        sources.append({
            "partner": partner,
            "side": side,
            "label": labels.get(partner) or partner,
            "has_auto": bool(w),
            "auto_enabled": bool(getattr(w, "is_enabled", False)) if w else False,
            "watch_status": getattr(w, "last_trigger_status", None) if w else None,
            "last_delivered_at": str(last_activity) if last_activity else None,
            "delivered_today": status == "delivered",
            "status": status,
            "days_since": days_ago,
        })

    # problems first: never, then most-stale, then delivered; stable by name
    order = {"never": 0, "stale": 1, "delivered": 2}
    sources.sort(key=lambda s: (order.get(s["status"], 3),
                                -(s["days_since"] or 0),
                                s["partner"], s["side"]))

    summary = {
        "total": len(sources),
        "delivered_today": sum(1 for s in sources if s["status"] == "delivered"),
        "stale": sum(1 for s in sources if s["status"] == "stale"),
        "never": sum(1 for s in sources if s["status"] == "never"),
    }
    return {"as_of_ist": str(today), "summary": summary, "sources": sources}
