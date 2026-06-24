"""
Characterization tests for roadmap item 1.2 — admin-gate audit READ.

Covers the two halves of the change:
  * ``require_permission('audit_read')`` — the gate now on /api/audit/*:
      - admin role passes WITHOUT an explicit perm (short-circuit),
      - a non-admin WITH ``audit_read`` passes,
      - a non-admin WITHOUT it gets HTTP 403.
  * ``seed_audit_read_grandfather`` — preserves today's open access:
      - grants ``audit_read`` to every user that exists at first run,
      - is idempotent (SystemSetting marker), and
      - does NOT grant it to users created after the marker is set
        (the lock-down for new principals).
Uses an in-memory SQLite session (autoflush=False, matching production).
"""
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User, SystemSetting, seed_audit_read_grandfather
from core.auth import require_permission

GATE = require_permission("audit_read")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


# ── the gate ──────────────────────────────────────────────────────────────────

def test_admin_passes_without_explicit_perm():
    admin = User(username="admin", role="admin", permissions="{}")
    assert GATE(current_user=admin) is admin


def test_user_with_audit_read_passes():
    u = User(username="ravi", role="user", permissions=json.dumps({"audit_read": True}))
    assert GATE(current_user=u) is u


def test_user_without_audit_read_is_forbidden():
    u = User(username="ravi", role="user", permissions=json.dumps({"reports": True}))
    with pytest.raises(HTTPException) as ei:
        GATE(current_user=u)
    assert ei.value.status_code == 403


# ── the grandfather seeder ────────────────────────────────────────────────────

def test_grandfather_grants_existing_users_once(db):
    db.add(User(username="admin", role="admin",
                hashed_password="x", permissions="{}"))
    db.add(User(username="ravi", role="user",
                hashed_password="x", permissions=json.dumps({"reports": True})))
    db.commit()

    seed_audit_read_grandfather(db)

    for name in ("admin", "ravi"):
        u = db.query(User).filter(User.username == name).first()
        assert json.loads(u.permissions).get("audit_read") is True
    # ravi keeps his other perms untouched
    ravi = db.query(User).filter(User.username == "ravi").first()
    assert json.loads(ravi.permissions).get("reports") is True
    # marker recorded so it never runs again
    assert db.query(SystemSetting).filter(
        SystemSetting.key == "audit_read_grandfathered_v1").first() is not None


def test_grandfather_is_idempotent_and_excludes_new_users(db):
    db.add(User(username="ravi", role="user",
                hashed_password="x", permissions=json.dumps({"reports": True})))
    db.commit()
    seed_audit_read_grandfather(db)          # first run: grandfathers ravi + sets marker

    # a user created AFTER the marker must NOT be grandfathered on a later run
    db.add(User(username="newbie", role="user",
                hashed_password="x", permissions=json.dumps({"reports": True})))
    db.commit()
    seed_audit_read_grandfather(db)          # second run: no-op (marker present)

    newbie = db.query(User).filter(User.username == "newbie").first()
    assert "audit_read" not in json.loads(newbie.permissions)
