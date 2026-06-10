"""
file_hash_guard.py — central duplicate-file protection for the dedicated modules
(E-Value, BBPS, SBI…). The core engine already hard-blocks re-uploads via
UploadSession; the modules ingest directly, so this guard stores a SHA-256 of
every ingested file and rejects the exact same bytes a second time.
"""
import hashlib

from fastapi import HTTPException


def guard_duplicate_file(db, module: str, side: str, file_bytes: bytes,
                         filename: str, user=None) -> str:
    """
    Raise 409 if this exact file was already ingested for `module`.
    Otherwise record its hash (committed together with the caller's ingest)
    and return the hex digest.
    """
    from models.database import ModuleUploadHash

    sha = hashlib.sha256(file_bytes).hexdigest()
    existing = db.query(ModuleUploadHash).filter(
        ModuleUploadHash.module == module,
        ModuleUploadHash.sha256 == sha,
    ).first()
    if existing:
        when = existing.uploaded_at.strftime("%Y-%m-%d %H:%M UTC") if existing.uploaded_at else "earlier"
        raise HTTPException(
            status_code=409,
            detail=(f"[DUPLICATE] This exact file was already uploaded to {module} "
                    f"as '{existing.filename}' on {when}. "
                    f"If the source data changed, upload the corrected file (its content differs, so it will pass)."),
        )
    db.add(ModuleUploadHash(
        module=module, side=side, sha256=sha, filename=filename,
        uploaded_by=getattr(user, "username", None),
    ))
    return sha
