# SQLite → MySQL migration runbook

Eko Recon ships on SQLite and is **dual-database by design** — the same code runs on
MySQL by changing one environment variable. This runbook is the safe path to move an
existing deployment (with live data) onto MySQL.

> Status: the code is MySQL-ready and has been dress-rehearsed on MySQL 8 (schema
> builds, all tables migrate, 36-char UUID keys survive, FK joins intact, app starts
> and serves). What remains is provisioning MySQL and running the cutover below.

## Why move

SQLite is excellent for single-user/low-write workloads but has a single-writer lock
and (on synced folders like Dropbox/OneDrive) a real corruption risk. MySQL handles
larger data, concurrent writes, and backups/replication properly.

## Prerequisites

1. **MySQL 8** reachable from the app host (native install, Docker, or a separate DB
   host). Installing it on the RAG server needs root — that's a **tech-lead task**
   (`himanshu` is not a sudoer).
2. Create the database with utf8mb4:
   ```sql
   CREATE DATABASE eko_recon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'recon'@'%' IDENTIFIED BY '<strong-password>';
   GRANT ALL PRIVILEGES ON eko_recon.* TO 'recon'@'%';
   FLUSH PRIVILEGES;
   ```
3. The deployed code must include commit `de881cd` (widened UUID keys + complete
   migration tool). **Do not migrate on older code** — earlier revisions define 18
   primary keys as `VARCHAR(20)` while storing 36-char UUIDs; MySQL would truncate
   them and corrupt the data.

## Cutover (run on the app host)

```bash
cd /home/himanshu/reconciliation-app/backend

# 1. BACK UP the live SQLite DB first (always).
cp recon.db ~/backup-$(date +%F)/recon.db.pre-mysql

# 2. Point DATABASE_URL at MySQL in backend/.env:
#    DATABASE_URL=mysql+pymysql://recon:<password>@<host>:3306/eko_recon

# 3. Copy all data SQLite -> MySQL (creates tables, copies every table, verifies counts).
#    Reads recon.db by default; pass a path to use a different source.
./venv/bin/python migrate_to_mysql.py recon.db
#    --> must end with "ALL TABLES MATCH — migration complete."
#    If any table shows MISMATCH, STOP and investigate before serving traffic.

# 4. Restart the app (it now talks to MySQL).
bash ~/restart_all.sh

# 5. Verify.
curl -s localhost:8000/api/health     # {"status":"ok","db":"mysql",...}
```

Then spot-check in the UI: Open Items, a product recon screen, Reports export, and an
SBI P02 view (exercises the UUID foreign key).

## Rollback

The migration is **non-destructive** — it only ever inserts into MySQL and never
touches `recon.db`. To roll back, set `DATABASE_URL` back to SQLite (or comment it out)
in `backend/.env` and restart. Your data is exactly as it was.

## After cutover

- Keep nightly `mysqldump` backups of `eko_recon`.
- The old `recon.db` can be archived once MySQL is confirmed stable for a few days.

## ⚠️ Before running MULTIPLE app workers

Moving to MySQL lets you scale, but **do not run more than one uvicorn worker yet.**
Match-ID allocation (`core/matching_engine.py`) currently serialises with a
**process-local lock** plus a `MAX(seq)+1` query — safe within one process, but two
workers/processes can mint duplicate match IDs (see
[behavior-contract.md #1](behavior-contract.md) and [known-issues.md](known-issues.md)).
Running multiple workers requires first making match-ID allocation atomic at the DB
level (e.g. an `INSERT ... ON DUPLICATE KEY` sequence table, or `SELECT … FOR UPDATE`).
That is a **finance-sign-off change** because match IDs are audit references. Until then:
`uvicorn main:app --workers 1` (MySQL still gives you the bigger, safer database).
