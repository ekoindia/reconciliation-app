"""
routes/settlement_bank.py

Settlement Bank Configuration — two-stage SEV (Settlement Verification).

Industry reconciliation suites call this SEV: after PI transactions (PayU/AePS) are
matched against internal records, the net settlement due is verified against
the actual bank credit in the settlement account.

Step 1 already handled: PI txns matched against Simplibank dump.
Step 2 (this module): net settlement record matched against bank credit narration keyword.

The settlement bank account (where PayU/AePS credits land) is configurable:
  - Partner (pg, aeps, qr...)
  - Bank name + account number
  - Narration keyword (e.g. "GATEWAY SETTLEMENT", "AEPS") identifies the PI's credit
  - Settlement period (T+1, T+2 etc.)

If no config → SEV is skipped and a notice is surfaced on upload.
"""

import json
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import (
    get_db, SettlementBankConfig, PIIntegrityCheck,
    generate_id, AuditLog
)
from core.auth import get_current_user, require_permission

router = APIRouter(prefix="/api/settlement-bank", tags=["settlement-bank"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SettlementBankIn(BaseModel):
    partner:           str          # 'pg', 'aeps', 'qr', etc.
    partner_label:     str          # e.g. "PayU (Accept Payment)"
    bank_name:         str          # e.g. "Axis Bank"
    account_number:    str          # e.g. "000011112222333"
    narration_keyword: str          # e.g. "GATEWAY SETTLEMENT"
    settlement_period: str = "T+2"  # e.g. "T+1", "T+2"
    is_active:         bool = True
    notes:             str = ""


def _to_dict(cfg: SettlementBankConfig) -> dict:
    return {
        "id":                cfg.id,
        "partner":           cfg.partner,
        "partner_label":     cfg.partner_label,
        "bank_name":         cfg.bank_name,
        "account_number":    cfg.account_number,
        "narration_keyword": cfg.narration_keyword,
        "settlement_period": cfg.settlement_period,
        "is_active":         cfg.is_active,
        "notes":             cfg.notes,
        "created_at":        str(cfg.created_at),
        "updated_at":        str(cfg.updated_at),
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/configs")
def list_configs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List all settlement bank configurations."""
    configs = db.query(SettlementBankConfig).order_by(SettlementBankConfig.partner).all()
    return {"configs": [_to_dict(c) for c in configs]}


@router.post("/configs")
def create_config(
    body: SettlementBankIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("upload")),
):
    """Create a settlement bank configuration for a partner."""
    existing = db.query(SettlementBankConfig).filter(
        SettlementBankConfig.partner == body.partner
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Settlement bank config for partner '{body.partner}' already exists. Use PUT to update."
        )
    cfg = SettlementBankConfig(
        id                = generate_id(),
        partner           = body.partner,
        partner_label     = body.partner_label,
        bank_name         = body.bank_name,
        account_number    = body.account_number,
        narration_keyword = body.narration_keyword,
        settlement_period = body.settlement_period,
        is_active         = body.is_active,
        notes             = body.notes,
    )
    db.add(cfg)
    db.commit()
    _audit(db, current_user, "create_settlement_bank_config", body.partner)
    return {"id": cfg.id, "message": f"Settlement bank configured for {body.partner_label}"}


@router.put("/configs/{cfg_id}")
def update_config(
    cfg_id: str,
    body: SettlementBankIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("upload")),
):
    """Update a settlement bank configuration. All fields editable since bank accounts change."""
    cfg = db.query(SettlementBankConfig).filter(SettlementBankConfig.id == cfg_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    for field, val in body.dict().items():
        setattr(cfg, field, val)
    cfg.updated_at = datetime.datetime.utcnow()
    db.commit()
    _audit(db, current_user, "update_settlement_bank_config", body.partner)
    return {"message": "Updated"}


@router.delete("/configs/{cfg_id}")
def delete_config(
    cfg_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("upload")),
):
    cfg = db.query(SettlementBankConfig).filter(SettlementBankConfig.id == cfg_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    partner = cfg.partner
    db.delete(cfg)
    db.commit()
    _audit(db, current_user, "delete_settlement_bank_config", partner)
    return {"message": "Deleted"}


# ── SEV Status ────────────────────────────────────────────────────────────────

@router.get("/sev-status")
def sev_status(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Return SEV (Settlement Verification) configuration status for all PI partners.
    Shows which partners have settlement banks configured and which are awaiting setup.
    """
    PI_PARTNERS = [
        {"partner": "pg",        "label": "PayU (Accept Payment)"},
        {"partner": "aeps",      "label": "AePS Cashout (Fingpay)"},
        {"partner": "qr",        "label": "QR Collection (Paypoint)"},
    ]

    configs = {c.partner: c for c in db.query(SettlementBankConfig).all()}
    rows = []

    for pi in PI_PARTNERS:
        partner = pi["partner"]
        cfg = configs.get(partner)
        rows.append({
            "partner":     partner,
            "label":       pi["label"],
            "configured":  cfg is not None and cfg.is_active,
            "bank_name":   cfg.bank_name        if cfg else None,
            "account_number": cfg.account_number if cfg else None,
            "narration_keyword": cfg.narration_keyword if cfg else None,
            "settlement_period": cfg.settlement_period if cfg else None,
            "sev_note": (
                None if (cfg and cfg.is_active) else
                f"Settlement bank not configured for '{partner}' — SEV skipped. "
                f"Configure a bank account and narration keyword to enable two-stage settlement matching."
            ),
        })

    return {
        "rows": rows,
        "all_configured": all(r["configured"] for r in rows),
    }


# ── Audit helper ──────────────────────────────────────────────────────────────

def _audit(db: Session, user, action: str, partner: str):
    try:
        db.add(AuditLog(
            user_id=user.id, username=user.username,
            action=action, entity_type="settlement_bank_config", entity_id=None,
            detail=json.dumps({"partner": partner}),
        ))
        db.commit()
    except Exception:
        db.rollback()
