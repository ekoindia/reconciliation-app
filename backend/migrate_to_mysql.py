"""
SQLite → MySQL Migration Script
================================
Run this ONCE after setting up MySQL to move all existing data over.

Steps:
  1. Set DATABASE_URL in backend/.env to your MySQL connection string
  2. Make sure the MySQL database (eko_recon) exists:
       CREATE DATABASE eko_recon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  3. Run:  python migrate_to_mysql.py
  4. Restart the backend — it will now talk to MySQL

Safe to re-run: it only inserts rows that don't already exist in MySQL.
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Source: SQLite ────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_URL = "sqlite:///./recon.db"
sqlite_engine  = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SQLiteSession  = sessionmaker(bind=sqlite_engine)

# ── Target: MySQL (from .env) ─────────────────────────────────────────────────
MYSQL_URL = os.getenv("DATABASE_URL")
if not MYSQL_URL or "sqlite" in MYSQL_URL:
    print("ERROR: DATABASE_URL in .env must point to MySQL, not SQLite.")
    print("  Example: mysql+pymysql://root:password@localhost:3306/eko_recon")
    sys.exit(1)

mysql_engine  = create_engine(MYSQL_URL, pool_pre_ping=True)
MySQLSession  = sessionmaker(bind=mysql_engine)

# ── Create all tables + indexes in MySQL ──────────────────────────────────────
from models.database import Base, init_db

print("Creating MySQL tables and indexes...")
Base.metadata.create_all(bind=mysql_engine)
print("  ✓ Tables created")


# ── Helper: migrate a table row by row ────────────────────────────────────────
def migrate_table(table_name: str, pk_col: str = "id"):
    with sqlite_engine.connect() as src, mysql_engine.connect() as dst:
        rows = src.execute(text(f"SELECT * FROM {table_name}")).mappings().all()
        if not rows:
            print(f"  {table_name}: 0 rows (skipped)")
            return

        cols      = list(rows[0].keys())
        col_list  = ", ".join(f"`{c}`" for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)

        inserted = 0
        skipped  = 0
        for row in rows:
            row_dict = dict(row)
            # Check if already exists in MySQL
            exists = dst.execute(
                text(f"SELECT 1 FROM `{table_name}` WHERE `{pk_col}` = :{pk_col}"),
                {pk_col: row_dict[pk_col]}
            ).fetchone()

            if exists:
                skipped += 1
                continue

            # Clean None values from integer columns that MySQL won't accept as NULL strings
            dst.execute(
                text(f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})"),
                row_dict
            )
            inserted += 1

        dst.commit()
        print(f"  {table_name}: {inserted} inserted, {skipped} already existed")


# ── Run migrations in dependency order ────────────────────────────────────────
tables_in_order = [
    "users",
    "upload_sessions",
    "transactions",
    "recon_runs",
    "match_rules",
    "column_mapping_templates",
]

print("\nMigrating data...")
for table in tables_in_order:
    try:
        migrate_table(table)
    except Exception as e:
        print(f"  ERROR on {table}: {e}")

print("\nDone. Verify row counts in MySQL then update .env for production use.")
