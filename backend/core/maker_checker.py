"""
maker_checker.py — Tier 1 dual-control for manual recon actions.

When the system setting `maker_checker_enabled` is "true", manual matches /
overrides / SRC assignments made by NON-admin users are not executed directly:
they are queued as ApprovalRequest rows and only run when a different user
(with the right permission) approves them in the Workflow page.

Admins always execute directly (they are the checkers).
"""
import json
import datetime


def is_enabled(db) -> bool:
    from models.database import SystemSetting
    row = db.query(SystemSetting).filter(SystemSetting.key == "maker_checker_enabled").first()
    return bool(row and str(row.value).lower() in ("true", "1", "yes", "on"))


def set_enabled(db, enabled: bool, username: str = None):
    from models.database import SystemSetting
    row = db.query(SystemSetting).filter(SystemSetting.key == "maker_checker_enabled").first()
    if not row:
        row = SystemSetting(key="maker_checker_enabled")
        db.add(row)
    row.value = "true" if enabled else "false"
    row.updated_by = username
    db.commit()


def intercept(db, user, action_type: str, payload: dict, summary: str, partner: str = None):
    """
    Returns None when the action should execute directly (feature off, or the
    user is an admin/checker). Otherwise queues an ApprovalRequest and returns
    the response payload the route should hand back to the caller.
    """
    if getattr(user, "role", "") == "admin":
        return None
    if not is_enabled(db):
        return None

    from models.database import ApprovalRequest
    req = ApprovalRequest(
        action_type=action_type,
        payload=json.dumps(payload),
        summary=summary[:400],
        partner=partner,
        requested_by=getattr(user, "username", "unknown"),
        requested_at=datetime.datetime.utcnow(),
        status="pending",
    )
    db.add(req)
    db.commit()
    return {
        "queued": True,
        "approval_id": req.id,
        "message": "Maker-checker is on — this action is pending approval by another user.",
    }
