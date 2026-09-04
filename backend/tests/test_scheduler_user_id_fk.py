"""
The auto-upload job must not stamp writes with a user_id that does not exist.

core/scheduler.py handed ingest_dataframe the literal string "system" as user_id. That value is
propagated into audit_logs.user_id and recon_runs.user_id, both of which are FOREIGN KEYs to
users.id — and there is no user whose id is "system". Every such write therefore raised
IntegrityError(1452) on MySQL.

Because the post-ingest chain deliberately swallows its exceptions (behavior-contract #4: a
matching error must never fail the upload), a watch-folder ingest would land its rows and then
SILENTLY fail to reconcile them, reporting success either way. It never bit production only
because no watch folder has ever actually run — all 27 are configured but unscheduled.

Found while re-reconciling the NEFT backfill: run_reconciliation(p, d, db, "system") blew up on
the first date and the poisoned session cascaded that failure across all 31 remaining dates.

Both columns are nullable, so None is the correct value. The audit-source classification keys on
USERNAME ("auto-upload"), not user_id, so tagging is unaffected.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User, ReconRun, AuditLog


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def test_there_is_no_user_called_system(db):
    """The premise: nothing in the schema or seeds creates a user with id/username 'system'."""
    assert db.query(User).filter(User.id == "system").first() is None
    assert db.query(User).filter(User.username == "system").first() is None


def test_the_fk_columns_are_nullable():
    """Which is why None is the correct value to pass, rather than inventing a user."""
    assert ReconRun.__table__.c.user_id.nullable is True
    assert AuditLog.__table__.c.user_id.nullable is True


def test_scheduler_does_not_pass_a_literal_system_user_id():
    """Guard the exact regression: the auto-upload job must hand down a NULL user_id.

    Asserted against the source because reproducing it needs a live FK, and SQLite does not
    enforce foreign keys by default — the very reason this survived the test suite and only
    surfaced against MySQL in production.
    """
    import inspect
    import core.scheduler as sched
    src = inspect.getsource(sched)
    assert 'user_id="system"' not in src, 'scheduler must not stamp writes with a non-existent user id'
    assert "user_id=None" in src, "the auto-upload ingest should pass user_id=None"


def test_username_still_marks_the_run_as_automated():
    """Audit-source classification keys on username, so it must stay 'auto-upload'."""
    import inspect
    import core.scheduler as sched
    assert 'username="auto-upload"' in inspect.getsource(sched)
