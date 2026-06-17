# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.1.0] - 2026-06-15

### Added
- **Bank-statement description / narration** surfaced for every bank-side transaction
  everywhere it appears (recon workbench, Open Items, Mismatches, manual-match, every
  product module, and all Excel exports). Searchable/filterable, read-only, and
  backfilled for already-uploaded statements. Purely additive — no existing column,
  label, order, value, or matching behaviour changes.
- **MySQL production support.** The database engine is selected entirely by
  `DATABASE_URL`; the same code runs on SQLite (development) and MySQL/PostgreSQL
  (production). Added `backend/migrate_to_mysql.py` (idempotent, column-intersection
  aware, row-count verified) and a SQLite→MySQL cutover runbook in
  [docs/mysql-migration.md](docs/mysql-migration.md).

### Changed
- **Schema made MySQL-ready** without any behaviour change: UUID string primary keys
  (and the SBI foreign keys referencing them) widened from `VARCHAR(20)` to
  `VARCHAR(36)` so MySQL does not truncate 36-char UUIDs (SQLite ignores the width).
  Money columns remain `DECIMAL(15,2)` for exact storage on MySQL.

### Security
- Replaced real bank account numbers in E-Value test-fixture file names with synthetic
  values.

## [6.0.0] - 2026-06-10

Initial open-source-ready release.

### Added
- Full reconciliation platform: a FastAPI backend (matching engine, ingestion pipeline,
  scheduler, audit) and a React 18 + Vite + Tailwind SPA.
- Product modules: DMT (Fino / Airtel / Axis / Levin), AePS settlement, PG net-settlement,
  QR settlement + chargebacks, E-Value wallet loads (8 banks), BBPS refund lifecycle, and
  SBI Kiosk (P01–P04).
- Exception workflow (Open Items, manual match, SRC assignment, override with mandatory
  remarks, maker-checker approvals), reporting/exports, watch-folder automation, and an
  append-only audit log with JWT + API-key auth.

### Security
- Externalised real bank-account seed data out of code into the gitignored
  `backend/instance/seed_accounts.json` (only `seed_accounts.example.json` is published).
- Hardened `.gitignore` to exclude secrets, databases, uploads, and internal documents;
  all configuration is read from environment variables / instance files.

[6.1.0]: https://github.com/ekoindia/reconciliation-app/compare/v6.0.0...v6.1.0
[6.0.0]: https://github.com/ekoindia/reconciliation-app/releases/tag/v6.0.0
