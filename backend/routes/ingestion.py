"""
routes/ingestion.py — Ingestion Monitor (roadmap 1.4, additive, read-only).

Surfaces the append-only IngestionEvent ledger written by BOTH ingest paths
(interactive upload + watch-folder/auto). Every endpoint here is read-only — it
never writes to or alters any ingestion/recon/stored data. Gated by the existing
'upload' permission (admins short-circuit), so no new permission/migration is
needed.
"""
import json
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.database import get_db, IngestionEvent, User
from core.auth import require_permission

router = APIRouter(prefix="/api/ingestion", tags=["ingestion-monitor"])


def _jload(v):
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return v


def _row(e: IngestionEvent) -> dict:
    return {
        "id": e.id,
        "created_at": str(e.created_at) if e.created_at else None,
        "channel": e.channel,
        "status": e.status,
        "partner": e.partner,
        "side": e.side,
        "recon_date": e.recon_date,
        "username": e.username,
        "filename": e.filename,
        "file_sha256": e.file_sha256,
        "file_size": e.file_size,
        "preset_detected": e.preset_detected,
        "rows_read": e.rows_read,
        "rows_accepted": e.rows_accepted,
        "rows_skipped": e.rows_skipped,
        "skip_breakdown": _jload(e.skip_breakdown),
        "wlr_frec": e.wlr_frec,
        "duration_ms": e.duration_ms,
        "upload_session_id": e.upload_session_id,
        "detail": _jload(e.detail),
        "dq_profile": _jload(e.dq_profile),
    }


@router.get("/events")
def list_events(
    channel: Optional[str] = None,
    status: Optional[str] = None,
    partner: Optional[str] = None,
    from_date: Optional[str] = None,   # YYYY-MM-DD, on created_at
    to_date: Optional[str] = None,     # YYYY-MM-DD, inclusive
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
):
    """Paginated ingestion-ledger feed, most recent first."""
    q = db.query(IngestionEvent)
    if channel:
        q = q.filter(IngestionEvent.channel == channel)
    if status:
        q = q.filter(IngestionEvent.status == status)
    if partner:
        q = q.filter(IngestionEvent.partner == partner)
    if from_date:
        try:
            q = q.filter(IngestionEvent.created_at >= datetime.datetime.strptime(from_date, "%Y-%m-%d"))
        except Exception:
            pass
    if to_date:
        try:
            q = q.filter(IngestionEvent.created_at <
                         datetime.datetime.strptime(to_date, "%Y-%m-%d") + datetime.timedelta(days=1))
        except Exception:
            pass
    total = q.count()
    rows = (q.order_by(IngestionEvent.created_at.desc())
              .offset((page - 1) * page_size).limit(page_size).all())
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_row(e) for e in rows]}


@router.get("/summary")
def summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
):
    """Lightweight rollup for the monitor header — counts by status/channel."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    rows = db.query(IngestionEvent).filter(IngestionEvent.created_at >= since).all()
    by_status: dict = {}
    by_channel: dict = {}
    rows_read = rows_accepted = rows_skipped = 0
    for e in rows:
        by_status[e.status or "?"] = by_status.get(e.status or "?", 0) + 1
        by_channel[e.channel or "?"] = by_channel.get(e.channel or "?", 0) + 1
        rows_read += e.rows_read or 0
        rows_accepted += e.rows_accepted or 0
        rows_skipped += e.rows_skipped or 0
    return {"days": days, "events": len(rows), "by_status": by_status,
            "by_channel": by_channel, "rows_read": rows_read,
            "rows_accepted": rows_accepted, "rows_skipped": rows_skipped}


@router.get("/sources")
def ingestion_sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
):
    """Read-only ingestion-sources catalog (1.5) — who delivered today vs stale."""
    from core.ingestion_sources import compute_sources
    return compute_sources(db)


@router.get("/health")
def recon_health(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
):
    """Read-only recon-health watchdog (D2) — failure signals in one report."""
    from core.recon_health import compute_recon_health
    return compute_recon_health(db, days=days)


@router.get("/events/{event_id}")
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
):
    e = db.query(IngestionEvent).filter(IngestionEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Ingestion event not found")
    return _row(e)
