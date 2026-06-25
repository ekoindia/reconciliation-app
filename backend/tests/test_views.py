"""
Tests for Saved Views (roadmap 1.3).

A saved view is a per-user stored filter dict. Owners manage their own views;
shared views are visible (read-only) to everyone for the same page. The route
functions are called directly with an explicit Session + User.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, User
from routes.views import list_views, create_view, update_view, delete_view, ViewIn


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


A = User(id="ua", username="alice", role="user", permissions="{}")
B = User(id="ub", username="bob", role="user", permissions="{}")


def test_create_and_list_own_view(db):
    v = create_view(ViewIn(name="My Fino", page="open-items",
                           query={"partner": "fino"}), db=db, user=A)
    assert v["owned"] is True and v["query"] == {"partner": "fino"}
    out = list_views(page="open-items", db=db, user=A)
    assert len(out["views"]) == 1
    assert out["views"][0]["name"] == "My Fino"


def test_private_view_hidden_from_others(db):
    create_view(ViewIn(name="Private", query={"x": 1}, is_shared=False), db=db, user=A)
    assert list_views(page=None, db=db, user=B)["views"] == []


def test_shared_view_visible_to_others_readonly(db):
    create_view(ViewIn(name="Team view", query={"side": "bank"}, is_shared=True), db=db, user=A)
    views = list_views(page=None, db=db, user=B)["views"]
    assert len(views) == 1
    assert views[0]["owned"] is False        # bob can see it but doesn't own it


def test_create_requires_name(db):
    with pytest.raises(HTTPException) as e:
        create_view(ViewIn(name="   "), db=db, user=A)
    assert e.value.status_code == 400


def test_update_and_delete_restricted_to_owner(db):
    v = create_view(ViewIn(name="X", query={}), db=db, user=A)
    vid = v["id"]
    # bob cannot update or delete alice's view
    with pytest.raises(HTTPException) as e1:
        update_view(vid, ViewIn(name="hacked"), db=db, user=B)
    assert e1.value.status_code == 403
    with pytest.raises(HTTPException) as e2:
        delete_view(vid, db=db, user=B)
    assert e2.value.status_code == 403
    # owner can
    assert update_view(vid, ViewIn(name="renamed", query={"a": 1}), db=db, user=A)["name"] == "renamed"
    assert delete_view(vid, db=db, user=A)["deleted"] == vid
    assert list_views(page=None, db=db, user=A)["views"] == []
