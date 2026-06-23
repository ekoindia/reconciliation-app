"""
Characterization tests for core.config_audit (roadmap 1.1).

Verifies the additive config/entitlement audit shim:
  * create/update/delete of a config/identity model by a logged-in actor writes
    an AuditLog row (action_type='human') with before/after snapshots;
  * actor-less sessions (startup seeders / scheduler) write NOTHING;
  * sensitive columns (password/key hashes) are redacted, never logged;
  * pure system-timestamp churn (e.g. APIKey.last_used_at) is not audited;
  * non-config models (Transaction) are never audited by this shim.
Uses an in-memory SQLite session with autoflush=False (matches production).
"""
import json
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, AuditLog, PartnerConfig, User, APIKey, Transaction, generate_id
from core import config_audit


class _Actor:
    def __init__(self, id, username):
        self.id, self.username = id, username


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    config_audit._REGISTERED = False        # allow (re)attach to this test sessionmaker
    config_audit.register(Session)
    s = Session()
    yield s
    s.close()


def _audits(db, action=None):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.all()


def test_create_update_delete_are_audited(db):
    config_audit.set_actor(db, _Actor("u1", "alice"))

    p = PartnerConfig(slug="testp", display_name="Test P", match_prefix="TST")
    db.add(p); db.commit()
    creates = _audits(db, "config_create")
    assert len(creates) == 1
    a = creates[0]
    assert a.entity_type == "partner_configs"
    assert a.username == "alice" and a.user_id == "u1"
    assert a.action_type == "human"
    assert json.loads(a.detail)["slug"] == "testp"
    assert a.previous_state is None

    p.display_name = "Renamed P"
    db.commit()
    updates = _audits(db, "config_update")
    assert len(updates) == 1
    after = json.loads(updates[0].detail)
    before = json.loads(updates[0].previous_state)
    assert after["display_name"] == "Renamed P"
    assert before["display_name"] == "Test P"
    assert "match_prefix" not in after        # unchanged fields excluded from the diff

    db.delete(p); db.commit()
    deletes = _audits(db, "config_delete")
    assert len(deletes) == 1
    assert json.loads(deletes[0].previous_state)["slug"] == "testp"


def test_no_actor_no_audit(db):
    # No set_actor → simulates startup seeders / scheduler sessions.
    db.add(PartnerConfig(slug="seed", display_name="Seed", match_prefix="SD"))
    db.commit()
    assert _audits(db) == []


def test_sensitive_fields_redacted(db):
    config_audit.set_actor(db, _Actor("u1", "alice"))
    db.add(User(username="bob", hashed_password="super-secret-hash"))
    db.commit()
    a = _audits(db, "config_create")
    assert len(a) == 1
    assert json.loads(a[0].detail)["hashed_password"] == "***redacted***"
    assert "super-secret-hash" not in (a[0].detail or "")


def test_timestamp_only_update_skipped(db):
    config_audit.set_actor(db, _Actor("u1", "alice"))
    k = APIKey(name="agent", key_hash="h" * 64, key_prefix="eko_1234")
    db.add(k); db.commit()
    assert len(_audits(db, "config_create")) == 1
    k.last_used_at = datetime.datetime(2026, 6, 23, 10, 0, 0)   # the per-request touch
    db.commit()
    assert _audits(db, "config_update") == []


def test_non_config_model_not_audited(db):
    config_audit.set_actor(db, _Actor("u1", "alice"))
    db.add(Transaction(id=generate_id(), partner="qr", side="bank"))
    db.commit()
    assert _audits(db) == []
