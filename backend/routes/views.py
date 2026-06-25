"""
routes/views.py — Saved Views (roadmap 1.3, additive).

Per-user saved filter sets for list screens (Open Items, product recon pages). A
saved view is a stored query (filter dict) replayed through the UNCHANGED list
endpoint — these endpoints never touch Open-Items query semantics, buckets, or
vocabulary (#14). A user sees their own views plus any shared ones for the page;
mutations are restricted to the owner.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.database import get_db, SavedView, User
from core.auth import get_current_user

router = APIRouter(prefix="/api/views", tags=["saved-views"])


class ViewIn(BaseModel):
    name: str
    page: str = "open-items"
    query: dict = {}
    is_shared: bool = False


def _row(v: SavedView, current_user_id: str) -> dict:
    try:
        query = json.loads(v.query or "{}")
    except Exception:
        query = {}
    return {
        "id": v.id, "name": v.name, "page": v.page, "query": query,
        "is_shared": bool(v.is_shared), "username": v.username,
        "owned": v.user_id == current_user_id,
        "created_at": str(v.created_at) if v.created_at else None,
    }


@router.get("")
def list_views(
    page: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Own views + shared views, optionally scoped to a page."""
    q = db.query(SavedView).filter(
        or_(SavedView.user_id == user.id, SavedView.is_shared == True))
    if page:
        q = q.filter(SavedView.page == page)
    rows = q.order_by(SavedView.name).all()
    return {"views": [_row(v, user.id) for v in rows]}


@router.post("")
def create_view(
    body: ViewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    v = SavedView(
        user_id=user.id, username=user.username, name=name[:120],
        page=body.page or "open-items", query=json.dumps(body.query or {}),
        is_shared=bool(body.is_shared),
    )
    db.add(v)
    db.commit()
    return _row(v, user.id)


@router.put("/{view_id}")
def update_view(
    view_id: str,
    body: ViewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = db.query(SavedView).filter(SavedView.id == view_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="View not found")
    if v.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your view")
    if body.name is not None:
        v.name = (body.name or v.name).strip()[:120]
    if body.query is not None:
        v.query = json.dumps(body.query or {})
    v.is_shared = bool(body.is_shared)
    db.commit()
    return _row(v, user.id)


@router.delete("/{view_id}")
def delete_view(
    view_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = db.query(SavedView).filter(SavedView.id == view_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="View not found")
    if v.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your view")
    db.delete(v)
    db.commit()
    return {"deleted": view_id}
