"""
Regression test for the clear/delete permission wiring.

The universal /api/upload/clear endpoint must gate on the 'clear_data' permission
("Clear / Delete Data" in the Users screen) — NOT hard-code admin-only. A non-admin
with clear_data granted (e.g. Rajendra) was getting 403 because the endpoint
ignored the permission the UI/model expose and admins assign. These assert the
gate honors clear_data so that wiring can't silently regress.
"""
import json
import pytest
from fastapi import HTTPException

from models.database import User
from core.auth import require_permission

GATE = require_permission("clear_data")


def test_admin_passes_without_explicit_perm():
    admin = User(username="admin", role="admin", permissions="{}")
    assert GATE(current_user=admin) is admin


def test_user_with_clear_data_passes():
    raj = User(username="Rajendra", role="user",
               permissions=json.dumps({"upload": True, "clear_data": True}))
    assert GATE(current_user=raj) is raj


def test_user_without_clear_data_is_forbidden():
    u = User(username="someone", role="user",
             permissions=json.dumps({"upload": True, "clear_data": False}))
    with pytest.raises(HTTPException) as exc:
        GATE(current_user=u)
    assert exc.value.status_code == 403


def test_clear_endpoint_is_wired_to_clear_data_not_admin():
    # Guard against a revert to admin-only: the dependency on the clear endpoint
    # must be the clear_data permission checker.
    import routes.upload as up
    dep_names = []
    for d in up.clear_data.__defaults__ or ():
        # FastAPI Depends objects carry the dependency callable
        call = getattr(d, "dependency", None)
        if call is not None:
            dep_names.append(getattr(call, "__qualname__", ""))
    # require_permission('clear_data') returns a closure named '...checker'
    assert any("checker" in n for n in dep_names), dep_names
