"""
core/jobs.py

Lightweight in-process background job runner for long-running operations
(e.g. running reconciliation over a month of data) so the HTTP request
thread is not blocked and the UI does not time out.

A single ThreadPoolExecutor runs jobs; status/result are kept in memory.
Jobs are ephemeral (cleared on restart) — they are progress handles, not
durable records (the work itself writes to the DB and audit log).
"""
import uuid
import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("eko_recon.jobs")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="reconjob")
_JOBS: dict = {}
_LOCK = threading.Lock()
_MAX_KEEP = 200


def _now():
    return datetime.datetime.utcnow().isoformat()


def submit(kind: str, fn, *args, label: str = "", **kwargs) -> str:
    """Submit a callable to run in the background. Returns a job_id immediately."""
    job_id = str(uuid.uuid4())
    with _LOCK:
        _JOBS[job_id] = {"id": job_id, "kind": kind, "label": label,
                         "status": "queued", "result": None, "error": None,
                         "submitted_at": _now(), "started_at": None, "finished_at": None}
        # bound memory
        if len(_JOBS) > _MAX_KEEP:
            for k in sorted(_JOBS, key=lambda k: _JOBS[k]["submitted_at"])[:len(_JOBS) - _MAX_KEEP]:
                if _JOBS[k]["status"] in ("done", "error"):
                    _JOBS.pop(k, None)

    def _run():
        with _LOCK:
            _JOBS[job_id]["status"] = "running"
            _JOBS[job_id]["started_at"] = _now()
        try:
            res = fn(*args, **kwargs)
            with _LOCK:
                _JOBS[job_id].update(status="done", result=res, finished_at=_now())
        except Exception as e:
            logger.error(f"[jobs] {kind} job {job_id} failed: {e}")
            with _LOCK:
                _JOBS[job_id].update(status="error", error=str(e)[:1000], finished_at=_now())

    _executor.submit(_run)
    return job_id


def get(job_id: str):
    with _LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None


def recent(limit: int = 50):
    with _LOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j["submitted_at"], reverse=True)
        return [dict(j) for j in jobs[:limit]]
