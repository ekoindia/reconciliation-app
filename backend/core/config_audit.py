"""
core/config_audit.py  —  Additive config / entitlement change auditing.

Roadmap item 1.1. PURELY ADDITIVE: a SQLAlchemy ``before_flush`` listener that
writes an ``AuditLog`` row whenever a CONFIG / IDENTITY model is inserted,
updated, or deleted by a logged-in user. It only *observes* those tables and
only *adds* audit rows — it never changes any matching, ingestion, recon, or
status behaviour, and never blocks the underlying change (the whole handler is
wrapped so an auditing failure can never raise into the flush).

Why this closes a real gap: today ``admin.py``/``auth.py`` write ZERO audit
rows, so there is no record of who changed a matching rule, fee, partner, bank
account, user, permission, or API key — the single largest control gap in the
audit. This shim records actor + before/after for exactly those changes.

Design notes
------------
* **Actor** is carried on ``session.info`` (set in ``core.auth.get_current_user``
  via ``set_actor``), NOT a contextvar — FastAPI runs sync deps/endpoints in a
  threadpool where contextvars do not reliably propagate, but the SAME ``db``
  session is injected into the dependency and the endpoint, so ``session.info``
  is reliable.
* **Startup seeders / scheduler / watch-folder** use their own ``SessionLocal()``
  sessions with no actor set → they are skipped (only human, request-driven
  config changes are audited).
* **Atomic with the change**: the audit row is inserted in the same flush, so the
  audit exists iff the change commits (desirable for compliance). The handler
  body is guarded so a logic error degrades to "no audit", never a blocked save.
* **Gate**: env ``CONFIG_AUDIT_ENABLED`` (default on). When off, the handler is a
  cheap no-op.
* Sensitive columns (password/key hashes) are recorded as ``"***redacted***"`` —
  the field/event is audited, never the secret value.
"""
import os
import json
import datetime

from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.attributes import get_history

_ACTOR_KEY = "config_audit_actor"

# Columns whose *values* must never be written to the audit log.
_SENSITIVE = {
    "password_hash", "hashed_password", "password",
    "key_hash", "api_key", "secret", "token",
}
# If the ONLY columns that changed are these system timestamps, skip the audit
# (avoids noise from e.g. the API-key ``last_used_at`` touch on every request).
_IGNORE_ONLY = {
    "last_used_at", "updated_at", "last_run_at", "last_run_status", "last_run_message",
    "last_trigger_at", "last_trigger_status", "last_trigger_message", "last_trigger_filename",
}

_AUDITED = None  # resolved lazily to avoid import cycles


def set_actor(db, user):
    """Stamp the request's authenticated user onto the session so the flush
    listener can attribute config changes. Safe no-op on any error."""
    try:
        if db is not None and user is not None:
            db.info[_ACTOR_KEY] = {
                "id": getattr(user, "id", None),
                "username": getattr(user, "username", None),
            }
    except Exception:
        pass


def _enabled() -> bool:
    return os.getenv("CONFIG_AUDIT_ENABLED", "1").strip().lower() not in (
        "0", "false", "no", "off", ""
    )


def _audited_models():
    global _AUDITED
    if _AUDITED is None:
        from models.database import (
            PartnerConfig, MatchRule, FeeRule, BankFormatPreset, BankAccount,
            EvalueAccount, SettlementBankConfig, User, APIKey,
        )
        _AUDITED = {
            PartnerConfig, MatchRule, FeeRule, BankFormatPreset, BankAccount,
            EvalueAccount, SettlementBankConfig, User, APIKey,
        }
    return _AUDITED


def _json_safe(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _full_snapshot(obj) -> dict:
    """All auditable column values of ``obj`` (sensitive cols redacted)."""
    out = {}
    for col in sa_inspect(obj).mapper.column_attrs:
        name = col.key
        try:
            out[name] = "***redacted***" if name in _SENSITIVE else _json_safe(getattr(obj, name))
        except Exception:
            continue
    return out


def _db_old_values(session, obj) -> dict:
    """Pre-change DB row values via a direct Core SELECT. The pending UPDATE has
    not flushed yet, so the row still holds the OLD values — reliable even when
    the attribute was expired by a prior commit (autoflush=False → no recursion)."""
    try:
        from sqlalchemy import select
        insp = sa_inspect(obj)
        ident = insp.identity
        if not ident:
            return {}
        table = insp.mapper.local_table
        pk_col = list(table.primary_key.columns)[0]
        row = session.connection().execute(
            select(table).where(pk_col == ident[0])
        ).mappings().first()
        return dict(row) if row else {}
    except Exception:
        return {}


def _changed(session, obj):
    """Return (before, after) dicts of meaningfully-changed columns, or
    (None, None) if only system timestamps (or nothing) changed."""
    changed = []
    for col in sa_inspect(obj).mapper.column_attrs:
        name = col.key
        try:
            if get_history(obj, name).has_changes():
                changed.append(name)
        except Exception:
            continue
    meaningful = [c for c in changed if c not in _IGNORE_ONLY]
    if not meaningful:
        return None, None  # only system timestamps changed (or nothing)
    old = _db_old_values(session, obj)
    before, after = {}, {}
    for name in meaningful:
        if name in _SENSITIVE:
            before[name] = after[name] = "***redacted***"
        else:
            after[name] = _json_safe(getattr(obj, name))
            before[name] = _json_safe(old.get(name))
    return before, after


def _mk(actor, action, obj, detail, previous_state):
    from models.database import AuditLog
    return AuditLog(
        user_id=actor.get("id"),
        username=actor.get("username"),
        action=action,
        action_type="human",
        entity_type=getattr(obj, "__tablename__", obj.__class__.__name__),
        entity_id=getattr(obj, "id", None),
        detail=json.dumps(detail, default=str) if detail is not None else None,
        previous_state=json.dumps(previous_state, default=str) if previous_state is not None else None,
    )


def _before_flush(session, flush_context, instances):
    # MUST NOT raise into the flush — auditing never blocks a config change.
    try:
        if not _enabled():
            return
        actor = session.info.get(_ACTOR_KEY)
        if not actor:
            return  # no request actor (startup seeders / scheduler) — skip
        audited = _audited_models()
        rows = []
        for obj in list(session.new):
            if type(obj) in audited:
                rows.append(_mk(actor, "config_create", obj, _full_snapshot(obj), None))
        for obj in list(session.dirty):
            if type(obj) in audited and session.is_modified(obj, include_collections=False):
                before, after = _changed(session, obj)
                if after is None:
                    continue
                rows.append(_mk(actor, "config_update", obj, after, before))
        for obj in list(session.deleted):
            if type(obj) in audited:
                rows.append(_mk(actor, "config_delete", obj, None, _full_snapshot(obj)))
        for r in rows:
            session.add(r)
    except Exception:
        # Never let auditing break the actual operation.
        pass


_REGISTERED = False


def register(session_factory):
    """Attach the before_flush listener to a sessionmaker (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return
    event.listen(session_factory, "before_flush", _before_flush)
    _REGISTERED = True
