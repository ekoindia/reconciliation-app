"""
SQLite -> MySQL Migration Script
================================
Moves ALL existing data from the local SQLite database into MySQL.

Steps:
  1. Provision MySQL and create the database, e.g.:
       CREATE DATABASE eko_recon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  2. Set DATABASE_URL in backend/.env to the MySQL connection string, e.g.:
       DATABASE_URL=mysql+pymysql://user:password@localhost:3306/eko_recon
  3. Run:  python migrate_to_mysql.py  [path-to-source.db]
       (source defaults to ./recon.db)
  4. Verify the row-count report prints "ALL TABLES MATCH", then restart the backend.

Design notes:
  - Copies EVERY table defined in the models, in foreign-key-safe order
    (Base.metadata.sorted_tables), not just a hand-picked subset.
  - Reads through the ORM metadata so column types are marshalled correctly
    (SQLite ISO datetime strings -> real datetimes, 0/1 -> bool, etc.).
  - Idempotent: skips rows whose primary key already exists in MySQL, so it is
    safe to re-run after a partial load.
  - NON-DESTRUCTIVE: only ever INSERTs into MySQL; never touches the SQLite source.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import create_engine, select, func, text, inspect as sa_inspect
from models.database import Base

# ── Source: SQLite ────────────────────────────────────────────────────────────
SQLITE_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "recon.db")
if not os.path.exists(SQLITE_PATH):
    print(f"ERROR: source SQLite file not found: {SQLITE_PATH}")
    sys.exit(1)
SQLITE_URL = "sqlite:///" + SQLITE_PATH.replace("\\", "/")
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

# ── Target: MySQL (from .env) ─────────────────────────────────────────────────
MYSQL_URL = os.getenv("DATABASE_URL", "")
if not MYSQL_URL or "sqlite" in MYSQL_URL:
    print("ERROR: DATABASE_URL in backend/.env must point to MySQL, not SQLite.")
    print("  Example: mysql+pymysql://user:password@localhost:3306/eko_recon")
    sys.exit(1)
mysql_engine = create_engine(MYSQL_URL, pool_pre_ping=True)

BATCH = 1000


def _sqlite_has_table(name: str) -> bool:
    with sqlite_engine.connect() as c:
        r = c.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name})
        return r.fetchone() is not None


def _pk_cols(table):
    pk = list(table.primary_key.columns)
    return pk if pk else [table.c.id] if "id" in table.c else []


def migrate_table(table) -> tuple:
    """Copy one table SQLite -> MySQL. Returns (inserted, skipped, src_count)."""
    name = table.name
    if not _sqlite_has_table(name):
        print(f"  {name:32s}  (not in source — skipped)")
        return (0, 0, 0)

    pk_cols = _pk_cols(table)

    # Only copy columns present in BOTH the source DB and the model, so the
    # migration is robust to schema drift (a column the model added later but the
    # source predates, or vice-versa). Missing columns land as NULL/default.
    src_col_names = {c["name"] for c in sa_inspect(sqlite_engine).get_columns(name)}
    use_cols = [c for c in table.columns if c.name in src_col_names]
    skipped_cols = [c.name for c in table.columns if c.name not in src_col_names]
    if skipped_cols:
        print(f"  {name:32s}  (note: source lacks {skipped_cols} — will be NULL/default)")

    with sqlite_engine.connect() as src:
        rows = [dict(r) for r in src.execute(select(*use_cols)).mappings().all()]
    src_count = len(rows)
    if src_count == 0:
        print(f"  {name:32s}  0 rows")
        return (0, 0, 0)

    # Existing PKs already in MySQL (so re-runs are idempotent)
    with mysql_engine.connect() as dst:
        existing = set()
        if pk_cols:
            for r in dst.execute(select(*pk_cols)).all():
                existing.add(tuple(r))

    def pk_of(row):
        return tuple(row[c.name] for c in pk_cols) if pk_cols else None

    fresh = [r for r in rows if pk_of(r) not in existing] if pk_cols else rows
    skipped = src_count - len(fresh)

    inserted = 0
    with mysql_engine.begin() as dst:
        for i in range(0, len(fresh), BATCH):
            chunk = fresh[i:i + BATCH]
            if chunk:
                dst.execute(table.insert(), chunk)
                inserted += len(chunk)

    print(f"  {name:32s}  {inserted} inserted, {skipped} already existed  (source {src_count})")
    return (inserted, skipped, src_count)


def main():
    print(f"Source SQLite : {SQLITE_PATH}")
    print(f"Target MySQL  : {MYSQL_URL.split('@')[-1]}")   # host/db only, never the password
    print("\nCreating MySQL tables + indexes (widened String(36) UUID keys)...")
    Base.metadata.create_all(bind=mysql_engine)
    print("  tables ready")

    print("\nMigrating data (foreign-key-safe order)...")
    results = {}
    for table in Base.metadata.sorted_tables:
        try:
            results[table.name] = migrate_table(table)
        except Exception as e:
            print(f"  ERROR on {table.name}: {e}")
            results[table.name] = ("ERR", "ERR", "ERR")

    # ── Verification: compare row counts SQLite vs MySQL ──────────────────────
    print("\nVerifying row counts...")
    all_ok = True
    for table in Base.metadata.sorted_tables:
        name = table.name
        if not _sqlite_has_table(name):
            continue
        with sqlite_engine.connect() as s:
            sc = s.execute(select(func.count()).select_from(table)).scalar()
        with mysql_engine.connect() as m:
            mc = m.execute(select(func.count()).select_from(table)).scalar()
        flag = "OK " if sc == mc else "MISMATCH"
        if sc != mc:
            all_ok = False
        if sc or mc:
            print(f"  [{flag}] {name:32s} sqlite={sc}  mysql={mc}")

    print("\n" + ("ALL TABLES MATCH — migration complete." if all_ok
                  else "ROW-COUNT MISMATCH — review the table(s) flagged above before switching over."))


if __name__ == "__main__":
    main()
