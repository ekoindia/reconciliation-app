# Eko Recon

**A full-stack bank reconciliation platform for fintech operations.**

Eko Recon ingests bank statements and internal transaction dumps (CSV / Excel / PDF / tab-separated text), auto-matches them with a priority-ordered rule engine, and gives finance teams a complete exception-management workflow: open items, manual matching, maker-checker approvals, ageing, scheduled reports, and a full audit trail.

Built by the finance operations team at Eko Bharat Ventures and battle-tested on live settlement volumes across 12+ product lines.

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](backend/requirements.txt)
[![React](https://img.shields.io/badge/React-18-61DAFB)](frontend/package.json)

---

## What it does

| Capability | Detail |
|---|---|
| **Multi-format ingestion** | CSV, XLSX/XLS, PDF (auto table extraction), tab-separated text. Auto header detection, format auto-recognition from column signatures, saveable column-mapping templates. |
| **Wrong-file protection** | FREC (file recognition check) and WLR (wrong-record detection) hard-block files uploaded under the wrong partner/format. Duplicate uploads blocked by slot guard + SHA-256 file hashing. |
| **Rule-based matching** | Priority-ordered match rules per partner (TID / tracking number / UTR / amount), editable in the UI Logic Builder. Amount tolerance flags `amount_mismatch` instead of silently matching. |
| **Special passes** | Reversal pairing, NEFT D+1 carry, internal Success+Refund contra, cross-bank interbank transfers, configurable D+N carry-forward. |
| **Product modules** | DMT (multi-partner), AePS settlement (T+ formula verification), PG net-settlement, QR settlement + chargebacks, wallet-load reconciliation across 8 banks (E-Value), BBPS refund lifecycle, SBI Kiosk P01–P04. |
| **Exception workflow** | Universal Open Items window across all modules, bulk SRC assignment, manual match, override with mandatory remarks, maker-checker approval queue, adhoc tagging. |
| **Reporting** | Summary, bank reconciliation statement, ageing, SRC analysis, matched-pairs export, EOD digest email, per-user scheduled report subscriptions, monthly reconciliation certificate PDF. |
| **Audit & access control** | Append-only audit log with before/after states, JWT + API-key auth (with IP allowlists), per-module permissions, per-product data scoping, session logging. |
| **Automation** | Watch-folder auto-upload with cron schedules (APScheduler), auto-recon after every ingest, startup self-healing migrations. |

## Quickstart

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |

### Run locally

```bash
# Backend (terminal 1)
cd backend
pip install -r requirements.txt
cp .env.example .env          # set SECRET_KEY — see comments inside
uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev                   # → http://localhost:3000
```

Windows users can run `start.bat` (or `start_backend.bat` for the backend alone).

A default admin user is created on first start — **change its password immediately** (Users → admin → reset password).

### Run with Docker

```bash
cp backend/.env.example backend/.env   # set SECRET_KEY
docker compose up --build              # → http://localhost:8000
```

The image builds the frontend and serves it from the backend, so one container is the whole app.

## Configuration

- **`backend/.env`** — secret key, database URL, CORS origins, SMTP for report emails, schedule times. See [backend/.env.example](backend/.env.example) for every option.
- **`backend/instance/seed_accounts.json`** — your bank-account registry (gitignored; real account numbers never belong in the repo). Copy [backend/instance/seed_accounts.example.json](backend/instance/seed_accounts.example.json) and fill in your accounts, or add them in the UI under **Configuration**.
- **Database** — SQLite out of the box (`backend/recon.db`, zero setup). Set `DATABASE_URL` for MySQL/PostgreSQL in production; `backend/migrate_to_mysql.py` helps move existing data.
- **Matching rules** — editable per partner in the UI (**Logic Builder**), no code changes needed.

## Architecture

```
frontend/  React 18 + Vite + Tailwind SPA
  src/pages/        one page per workflow (Upload, Open Items, Reports, …)
  src/components/   shared UI
  src/utils/api.js  axios instance: auth header, 401 redirect, UTC→IST display

backend/   FastAPI + SQLAlchemy
  routes/   HTTP endpoints (upload, recon, reports, product modules, admin)
  core/     engines: matching, E-Value, BBPS, ingestion, scheduler, auth
  models/   database.py — all models, idempotent migrations, seeders
  instance/ deployment-specific data (gitignored)
```

Deep dives: [docs/architecture.md](docs/architecture.md) · [docs/behavior-contract.md](docs/behavior-contract.md) · [docs/known-issues.md](docs/known-issues.md)

The API is self-documenting: `http://localhost:8000/docs` (Swagger) and `/redoc`.

## Contributing

PRs welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first, especially the rule about never changing reconciliation behavior silently: this codebase moves real money, and [docs/behavior-contract.md](docs/behavior-contract.md) lists the invariants reviewers will hold you to.

Security reports: see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Eko Bharat Ventures
