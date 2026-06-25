# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.3.0] - 2026-06-25

A governance & observability release. Every item is **100% additive** — new tables
(nullable), new read-only endpoints, and new opt-in surfaces. No matching, ingestion,
classification, tolerance, match-ID, or stored-data behaviour changes (see
[docs/behavior-contract.md](docs/behavior-contract.md)).

### Added
- **Config / entitlement change auditing.** Every admin/auth mutation (partner, match
  rule, fee rule, format preset, bank account, user, API key, permission/password change)
  now writes an append-only `AuditLog` row with actor and before-snapshot, via a
  SQLAlchemy `before_flush` listener (`core/config_audit.py`). Closes the largest control
  gap — config changes previously left no trail. Gated by `CONFIG_AUDIT_ENABLED` (default on).
- **Ingestion event ledger + Ingestion Monitor.** A new append-only `IngestionEvent`
  table records every ingestion attempt across all channels (interactive upload and
  watch-folder/auto) — file SHA-256, size, detected preset, rows read/accepted/skipped,
  WLR/FREC outcome, duration, and the resulting upload session. Surfaced read-only at
  `/api/ingestion/events` and a new **Ingestion Monitor** page. Recorded in its own
  transaction so logging can never block or roll back an ingest.
- **Pre-ingest data-quality profiler.** At ingest time a read-only per-file profile is
  computed (per-column blank rate, parseable-amount rate + control total, date-parse rate,
  duplicate-key rate) and a non-blocking warning banner is shown on threshold breach.
  Stored on the ingestion ledger and returned as a new Step-3 result field.
- **Ingestion Sources catalog** — "which partner hasn't delivered today." A read-only
  delivery-status view (`/api/ingestion/sources`) derived from existing data: last delivery
  per partner/side (crediting mixed-dump fan-out), watch-folder status, IST-aware
  delivered / stale / never.
- **Recon-health watchdog** (`/api/ingestion/health`) — one read-only report aggregating
  failed/blocked ingests, watch-folder errors, data-quality warnings, and current
  reconciliation rate, the safety-net signals the EOD digest never surfaced.
- **Saved & shareable views.** Open Items filters are now reflected two-way in the URL
  (bookmarkable / shareable links), plus a per-user `SavedView` store (`/api/views`) with
  optional team sharing. A saved view is a stored filter set replayed through the unchanged
  list endpoint.

### Changed
- **Audit log read is now permission-gated.** `/api/audit/*` requires the `audit_read`
  permission (admins short-circuit); a one-time grandfather grants it to every existing
  user so no one loses access. New users default without it.

### Fixed
- **Clear / delete permission wiring.** The universal `/api/upload/clear` endpoint honoured
  only admin role, ignoring the `clear_data` permission ("Clear / Delete Data") that the
  Users screen and user model already expose — so a non-admin granted that permission still
  got 403. It now gates on `clear_data` (admins still short-circuit).
- **Modal clipping.** The `fade-in` animation left a persistent CSS `transform` on the page
  wrapper, making it the containing block for `position:fixed` and clipping modals to the
  content area. Made the animation opacity-only — fixes every modal at the root.

### Tests
- Added a **characterization test suite** (43 tests) pinning the load-bearing matching and
  ingestion behaviour — match-ID MAX+1 sequencing, `_normalize`/`_build_key`, ±₹1 tolerance,
  NEFT D+1 UTR-only matching, reversal pairing, the `_parse_description` regex ladder order,
  `_classify_bank_row` reversal-before-fee precedence, and the Fino action-id-118 drop — so
  future changes that perturb them fail CI.

## [6.2.0] - 2026-06-19

### Added
- **CSP (retailer) code & name** surfaced for every internal-side transaction everywhere
  it appears (recon workbench, Open Items, Mismatches, manual-match, every product
  module, and all Excel exports). Read from the internal dump's `CSPCode` / `MerchantName`
  columns, searchable/filterable, read-only, and backfilled for already-uploaded data.
  Blank when the source has no CSP column. Purely additive — no existing column, label,
  order, value, or matching behaviour changes.

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

[6.3.0]: https://github.com/ekoindia/reconciliation-app/compare/v6.2.0...v6.3.0
[6.2.0]: https://github.com/ekoindia/reconciliation-app/compare/v6.1.0...v6.2.0
[6.1.0]: https://github.com/ekoindia/reconciliation-app/compare/v6.0.0...v6.1.0
[6.0.0]: https://github.com/ekoindia/reconciliation-app/releases/tag/v6.0.0
