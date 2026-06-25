# Eko Recon — Audit & Industry Enhancement Roadmap (deepened)

> **Status:** research/advisory deliverable — **now partly delivered.** The whole Tier-1 quick-win set
> shipped in **v6.3 (2026-06-25)**: ✅ 1.1 config/entitlement change-audit, ✅ 1.2 audit-read gate,
> ✅ 1.3 saved + URL-synced views, ✅ 1.4 ingestion event ledger + Monitor, ✅ 1.5 ingestion sources catalog,
> ✅ 1.6 pre-ingest data-quality profiler — plus a recon-health watchdog and a 43-test characterization suite
> (the prerequisite for the riskier refactors). Tier 2 / Tier 3 below remain advisory/unbuilt. Every roadmap
> item is designed to be **100% additive** — new tables/columns (nullable, backfilled), new read-only
> endpoints/views, opt-in flags (default off / display-only), shadow/parallel computation that writes only to
> new tables. **No existing matching logic, ingestion/parsing, row classification, status transition,
> tolerance, match-ID scheme, post-ingest pass order, or stored-data semantic is changed. The live
> reconciliation team's screens, filters, workflows, and results are not touched, even slightly.**
>
> **How this was produced:** a read-only audit of all 9 subsystems (parallel agents) + an industry benchmark
> across 8 capability dimensions against the leading platforms (BlackLine, Trintech Cadency, SmartStream TLM,
> AutoRek, Oracle ARCS, Duco, Gresham, Osfin.ai, Modern Treasury, Numeric, Sigma, ReconArt, Nanonets), then a
> synthesis pass — **~50 risk-rated recommendations**, the overwhelming majority `none-additive`/`low`. The
> full per-subsystem audit detail lives in the workflow output (see the pointer at the end).

---

## Part 0 — Subsystem audit scorecard (at a glance)

Per subsystem: what's genuinely good (preserve), and the most material gaps. Full detail + risk ratings in
the raw audit; the latent correctness/control issues are consolidated in **Part C (Risk Register)**.

| Subsystem | Strengths (preserve) | Most material gaps |
|---|---|---|
| **Ingestion** | WLR/FREC wrong-file hard-blocks; 3-layer dup protection; robust header/PDF/encoding auto-detect; 16 declarative presets | Two ingest copies **drift** (watch-folder loses Levin prefix, QR net_amount, AS=SD checks); WLR/FREC/slot/hash guards **bypassed on watch-folder**; greedy bare-digit fallback; single opaque `skipped` counter |
| **Matching engine** | MAX+1 IDs; autoflush footgun defended + tested; clean priority ladder; type-segregated reversal; self-heal | **No DB-atomic sequence** (single-worker only, no unique constraint); first-match-wins, **no scoring/N-way**; amount only post-hoc (mismatch pairs still *consume* both rows); no per-pair rule provenance |
| **Product modules** | Deep domain modelling (BBPS lifecycle, AePS/QR formulas, SBI 4-priority); resilient E-Value parsers | QR/AePS have **no settlement↔ledger matcher**; arbitrary candidate selection; SBI `upload_date==today` coupling; **E-Value replace deletes human work**; inconsistent/non-atomic module IDs |
| **Exceptions/workflow** | Strong human-action audit + mandatory remarks; counterpart-integrity on breaks; "universal" Open Items; real maker-checker | `rematch`/`tag-adhoc`/`manual-interbank`/`resolve-mismatch` **bypass maker-checker**; `manual_match` **no precondition checks**; no SLA/lifecycle/comments; 3 divergent ageing defs; Partner=All materializes all module rows in Python |
| **Reporting/scheduling** | Exports mirror UI filters; fire-time date windows; durable subs; auditor-facing certificate PDF | **EOD digest is dead** (never registered + would crash on SQLAlchemy 2.x); reports **not reproducible** (no snapshot); unbounded full-table exports; date-range filters **silently drop `'auto'` rows** |
| **Auth/audit/admin** | API keys hashed + scoped + IP-allowlist; unified JWT/key auth; refuses boot w/o SECRET_KEY; append-only audit | **Config/entitlement changes NOT audited**; audit read open to **any authenticated user**; no JWT revocation; `require_permission('admin')` escalation footgun; static default admin pwd; no MFA/SSO |
| **Automation** | Durable DB-backed crons; transactional fail-safe ingest; per-job status; folder-path hardening | **No file-hash/idempotency on auto paths** (double-count risk); today-only detection, no catch-up; cron path **can't route SBI/BBPS/E-Value**; **no failure alerting** |
| **Data model** | Clean SQLite↔MySQL portability; idempotent boot; query-shaped indexes; first-class audit columns | No migration framework/versioning; **seeders double as string-keyed migrations**; no DB-level FK/CHECK/enum integrity; **every boot rewrites match-IDs**; no archival/partitioning |
| **Frontend/UI** | Centralized auth+UTC→IST interceptor; registry SSOT; tabular-num money hygiene; ErrorBoundary; mandatory-remark UX | **Zero accessibility** (no ARIA/focus-trap); no responsive/mobile; **client-side filter+select-all scoped to current page** (money-affecting trap); native `confirm/prompt`; no request cancellation (stale-response races) |

---

## Part A — Feature & Process Roadmap

*A board-ready synthesis of the platform audit and the 2024–2026 industry benchmark, scoped to be 100%
additive — the live reconciliation team's work and results are not touched, even slightly.*

### 1. Executive Summary

**Where we stand.** Eko's reconciliation platform is a **genuinely strong, purpose-built transaction-matching
engine** that already outperforms most homegrown fintech recon tooling on the things that matter for
correctness: reconciliation-grade input controls (WLR/FREC wrong-file hard-blocks), layered duplicate
protection born from a real production incident, deep domain modelling of Indian settlement edge cases (BBPS
refund lifecycle, AePS/QR settlement formulas, SBI Kiosk's four-process model, E-Value's 8-bank fuzzy
matcher), a disciplined timezone pact, append-only audit with before-snapshots, working maker-checker
dual-control, and a cohesive, branded operator console. The team has made many **deliberate, non-obvious,
correct engineering decisions** (MAX+1 match-ID sequencing, reversal-before-fee classification, `_build_key`
null-guards, per-engine tolerances) and documented them in a behavior contract — itself a sign of an
unusually mature codebase.

The platform is, however, **a generation behind the commercial frontier (BlackLine, Trintech Cadency, Duco,
SmartStream TLM, Osfin.ai, Numeric) on the "platform" dimensions rather than the "engine" dimension.** Deep
matching is now table stakes; the 2025–2026 differentiators are: confidence-scored/ML-assisted/N-way
matching, programmatic & native bank/rail connectivity (incl. RBI Account Aggregator), managed exception
case management with SLAs and root-cause analytics, SOX/RBI-grade controls (period-close immutability,
tamper-evident audit, config-change auditing, attestation workflows), real analytics (charts, executive
cockpits, predictive insight, GenAI narratives), close-orchestration/GL substantiation, and horizontal
scale/multi-tenancy/observability.

**The size of the opportunity.** Critically, **almost every gap can be closed additively** — alongside the
live engine, never inside it. The benchmark surfaced ~50 concrete recommendations, the overwhelming majority
rated `risk: none-additive` or `low`, because they are new tables, new read-only endpoints, shadow/parallel
computations, and feature-flagged surfaces. We can move from "competent matcher" to "industry-leading
platform" **without a risky rewrite and without disturbing a single live reconciliation**:

- **Lift effective match rates and analyst throughput** (confidence scoring, ranked suggestions, GenAI
  assist, bulk-at-scale, case management) — competitors cite 97–99.9% auto-match and ">70% manual-work
  elimination."
- **Close the compliance/audit gap** that would currently fail an external SOX/RBI review (config-change
  auditing, tamper-evident audit, period-close, certification, regulatory packs) — the highest-risk finding.
- **Unlock connectivity** (push API, SFTP/AA feeds, OCR, quarantine/observability) so ingestion stops being a
  manual file-drop.
- **Make performance visible** (snapshot-backed analytics, executive dashboards, alerting).
- **Prepare for scale** (atomic sequencing, leader-elected scheduler, structured observability).

Visible wins inside 90 days, strategic capability inside 6 months, platform-grade transformation inside 12 —
each step independently shippable and reversible.

### 2. Current-State Strengths (must be preserved)

| Area | What is genuinely good |
|---|---|
| **Input controls** | WLR (`_check_wlr`, 422 `[WLR]`) and FREC (`_check_frec`, 422 `[FREC]`) hard-blocks stop wrong-account/wrong-format files from creating phantom open items — industry-correct and rare in homegrown tools. |
| **Duplicate defense-in-depth** | 409 slot hard-block (born from a real Jun-2026 double-count incident), SHA-256 `file_hash_guard`, and post-ingest `flag_same_side_duplicates` — three mechanisms for three failure modes. |
| **Match-ID design** | MAX+1 (not COUNT) sequencing means unmatch/delete never reissues an existing audit reference — thoughtful, non-obvious, correct, with a characterization test guarding the real NEFT/QR production incident. |
| **Domain depth** | BBPS `failed_pending_refund` vs `refunded_but_success`; AePS/QR settlement-formula verification; SBI P01–P04; E-Value reference-first fuzzy matcher across 8 banks. Edge cases a generic matcher cannot express. |
| **Money/time discipline** | Per-engine tolerances on purpose; naive-UTC-store → IST-display interceptor; tabular-nums INR formatting; zero-padded lexicographic business dates. |
| **Audit & dual-control** | Append-only `AuditLog` with `action_type` app/human split and `previous_state` before-snapshots; mandatory ≥10-char remarks; working maker-checker with self-approval block. |
| **Resilience** | Non-blocking auto-recon chain (each pass try/except-wrapped); transactional ingest with rollback; top-level `ErrorBoundary`; self-healing `_repair_orphaned_matches`. |
| **Config-as-data foundation** | 16 declarative `BANK_FORMAT_PRESETS`; admin-editable per-partner match rules (Logic Builder); `productRegistry.js`/`filterModel.js` SSOT on the frontend. |
| **Engineering hygiene** | A documented 25-item behavior contract, a known-issues catalogue of deliberate non-fixes, dual-DB-clean code (SQLite↔MySQL/Postgres), and an additive `recon_jobs.py` pattern the team already uses. |

### 🔒 GUARDRAILS — load-bearing logic that must NEVER be touched

**Every recommendation is constrained by these (sourced from `docs/behavior-contract.md`, cited by item).
Anything that would alter them is out of scope and reframed additive or deferred.**

| # | Guardrail | Why load-bearing |
|---|---|---|
| **1** | Match-ID scheme `{PREFIX}-{YYYYMMDD}-{NNNN}`, MAX+1 `_next_seq`, startup repair/backfill | Existing IDs are audit references (single-worker assumption — known-issues) |
| **2** | `_parse_description` regex ladder order | Digit-length bounds decide tracking vs TID vs UTR |
| **3** | `_classify_bank_row` precedence (reversal before fee) | A reversed fee would auto-close as `fee_matched` |
| **4** | Post-ingest pass order (reversal → counterpart-gated recon → NEFT D+1 → internal self-match → dup flag LAST) | Order changes silently change final ledger statuses |
| **5** | `_normalize` float canonicalization (`700.0 → '700'`) | Amount-keyed rules depend on the exact string |
| **6** | `_build_key` returns None on ANY empty field | Lets fallback rules fire; tolerating empties over-matches |
| **7** | Per-engine tolerances — ₹1 core/BBPS, exact E-Value, 0.01 SBI, 0.02 AePS, 0.05 QR | Equalizing reclassifies money |
| **8** | NEFT D+1 matches on UTR only (despite docstring) | Never change without sign-off |
| **9** | `FAILED_STATUSES`/status sets duplicated across ~7 files, `'0'`=failed | New code must **import**, not re-duplicate/unify |
| **10** | Two divergent ingest copies + Fino `ACCOUNT_ACTION_ID==118` drop in both | Mirror fixes, don't unify casually |
| **11** | Duplicate-upload protections — 409 slot guard (`recon_date != 'auto'`), non-committing SHA-256 hash guard | The exact controls a real incident hardened |
| **12** | Timezone pact — naive UTC store, IST interceptor, server-side Excel conversion | tz-aware/ISO+Z double-shifts every time |
| **13** | E-Value replace semantics + `reco_acc_no` quirks (BOI-0351/0352 swap, PNB suffix) | Cross-account pass + fuzzy regex + cash `score≥1` tuned to real narrations |
| **14** | Open-Items contracts — default unmatched+src_assigned, `_skip_row_type`, `match_id` bypass, `'all'`, `dmt` fan-out, offset-stitched pagination | External behavior the UI depends on |
| **15** | Startup seeders mutate live data, keyed on exact strings | Editing literals re-triggers/skips migrations |
| **16** | Maker-checker intercept placement & payload replay through CURRENT Pydantic models; dual response shape | Frontend parses the shape; replay frozen |
| **17** | SBI couplings — `upload_date == today`, tab-separated `.xls`, typo'd headers, `max_shift=2`, delete-and-recreate | Brittle by design |
| **18** | Reversal pairing — `zip()` drops surplus, originals across ALL dates, fee split | Tuned to IMPS fee rows sharing tracking |
| **19** | Three divergent ageing-bucket definitions (core SQL / module adapter / Excel) | New code must pick ONE and label it |
| **20** | Carry-forward writes plain `matched`; markers are `src_note` + `CFW-` ID | |
| **21** | Counting semantics — `row_count`=`txn` only; settlement_credit double-counted; EOD/pair views bank-side only | |
| **22** | Magic literals — `'mixed'`, `'auto'`/`'auto (multi-date)'`, `'system'`/`'auto-upload'`/`'openclaw-bot'`, `[WLR]`/`[FREC]` | String-matched contracts |
| **23** | Data-type pacts — `Numeric(15,2, asdecimal=False)` floats, lexicographic string dates, **no unique constraint on match keys**, String(20) PKs hold UUIDs | |
| **24** | `_extract_bank_account` heuristics — `'Account No - '` in first 25 lines, else 9–18 leading filename digits | Loosening creates bogus accounts |
| **25** | External contracts — Excel headers/sheet names, date-alias precedence (`date_from` wins), `/recon/run` shape, jobs dict shape, Step-3 result fields, unauthenticated `partners-public` | Consumed externally |

**Additive design rules enforced throughout:** new tables (nullable, backfilled, no FK cascades onto live
tables); new read-only endpoints/views; opt-in flags defaulting OFF or display-only; shadow/parallel
computation writing only to new tables; reuse (import, never re-duplicate) the existing status-set literals
and the existing maker-checker/audit helpers; **no edits to matching, ingestion/parsing, classification,
status transitions, tolerances, match-ID logic, pass order, or stored-data semantics.**

### 3. Industry Gap Analysis

**3.1 Matching & AI/ML.** Industry (BlackLine/Trintech/Duco/SmartStream): layered exact→fuzzy→ML cascade,
**confidence score on every pair**, fuzzy/probabilistic on refs/names/dates, N-way (1:many, many:1,
split/consolidated, netting), global/optimal assignment, auto-learning rules + tolerance optimization, GenAI
assist, per-pair explainability. **Us:** deterministic 1:1 exact composite keys, binary
`matched`/`amount_mismatch`, no score, fuzzy only in E-Value, first-match-wins with arbitrary tie-break, no
ML/GenAI, only aggregate "rule X: N matches." **Gap:** no confidence scoring anywhere; no core fuzzy; no
group/split matching; non-deterministic among same-key candidates; auditors can't see *why* a pair matched.

**3.2 Ingestion & connectivity.** Industry: native bank/rail feeds (MT940/BAI2/ISO 20022 camt; UPI/IMPS/NEFT;
**RBI Account Aggregator**), 170+ pre-built connectors, schema-agnostic normalization, REST/webhook push with
idempotency, OCR/document-AI, SFTP automation with fingerprinting/catch-up/retry/alerts, data-quality
gates + quarantine, lineage. **Us:** file-only; 16 hardcoded presets; column-presence-only detection; pull-only;
scanned PDFs rejected; today-only watch folder with the weakest controls; single opaque `skipped`. **Gap:**
biggest India-specific gap (re-keying bank exports); renamed/superset columns mis-map; no OCR; least-supervised
channel highest-risk; a broken folder silently halts a partner for days.

**3.3 Exception & case management.** Industry: case lifecycle distinct from match status, SLA/due-dates/breach
clocks, smart routing + SoD, collaboration (threads/@mentions/attachments/reassignment history), root-cause
taxonomy + trend analytics, formal write-off with approval tiers + journal, bulk over full result set,
maker-checker on ALL dispositions. **Us:** bare `recon_status` + nullable owner/reason, three divergent aging
defs, manual assignment, one-shot remark, two flat code lists, generic override, bulk scoped to loaded page,
several dispositions bypass intercept. **Gap:** no case entity/lifecycle/SLA/routing/collaboration/root-cause;
money-affecting select-all trap; incomplete four-eyes.

**3.4 Controls, compliance & audit.** Industry: period close + lock + reproducible certified results,
preparer→reviewer→certifier + SoD + e-signature, tamper-evident audit (hash-chain/WORM), **every
config/entitlement change audited**, risk scoring, regulatory packs (RBI nodal/escrow), retention/lineage.
**Us:** everything re-runs over the live table; certificate has empty sign-off lines; append-only **by
convention only**; `admin.py`/`auth.py` write **zero** AuditLog rows; audit read open to any principal;
stateless 8h JWT, no MFA, static default admin. **Gap:** the single largest control gap (can't prove who
changed a rule/fee/account/user/key); not reproducible; would fail an external SOX/RBI review.

**3.5 Analytics, dashboards & reporting.** Industry: real-time KPI dashboards with charts, role-based exec
cockpit, trend/variance/flux, anomaly/risk scoring surfaced, predictive insight, GenAI narratives, self-service
builder, snapshot reproducibility. **Us:** **zero charting library** (hand-rolled `RateBar` divs);
one Dashboard for everyone; `/trend` pulls all rows into Python; EOD digest **never registered and crashes on
SQLAlchemy 2.x**; 12 hardcoded tabs; point-in-time recompute. **Gap:** no time-series/distribution/waterfall;
no exec view; no forecasting; reports differ across days.

**3.6 Close orchestration & GL.** Industry: period-close task orchestration (checklist/dependencies/rollup %),
account certification, balance-level vs transaction-level split, journal/GL auto-posting, multi-entity &
intercompany. **Us:** none — month-end is an implicit set of `recon_date` strings; 100% transaction matching;
no journal entity/GL dimension; single entity. **Gap:** the biggest category-expansion opportunity.

**3.7 Platform, scale, security & extensibility.** Industry: stateless N-worker tier, DB-atomic sequencing,
idempotency keys, optimistic locking, leader-elected/shared-jobstore scheduler, multi-tenancy, SSO/SAML/OIDC +
SCIM + MFA + revocation, Vault/KMS + field-level encryption, OTel observability, outbound webhooks, DR/HA.
**Us:** **single-worker by construction** (process-local `_RECON_LOCK`, no DB sequence/unique constraint),
one in-process APScheduler, single shared schema, local JWT/API-key only, `.env` on disk with clear account
numbers, plain-text logs + pervasive `except: pass`, pull-only, single node. **Gap:** the hardest scale
blocker; multiple identity gaps; minimal observability; no push integration; no DR.

### 4. The Additive Enhancement Roadmap

Risk: `none-additive` (new tables/read-only endpoints/UI only), `low` (additive but touches a contract
endpoint/auth path — needs a characterization test), `medium` (gated strictly behind an off-by-default flag;
could alter an outcome only when explicitly enabled). **No item is rated high.** Effort: S (≤1 wk), M (1–3
wk), L (3–8 wk), XL (multi-month).

#### TIER 1 — Quick Wins (S/M, high value, zero/low risk)

**1.1 — Config/entitlement change-audit shim** `[M · low]` — **✅ SHIPPED (v6.3).** Make every admin/auth mutation (partner,
match-rule, fee-rule, format-preset, bank-account CRUD; user create/disable/delete; permission/password
change; API-key create/revoke) write an `AuditLog` row with actor, entity, and before-snapshot. *Closes the
single largest control gap.* Additive: a router-level dependency or SQLAlchemy `after_*` event listener on
`admin.py`/`auth.py` models, reusing the existing `AuditLog` table + `_log` helper, actor from a contextvar
set in `get_current_user`; gate behind `SystemSetting 'config_audit_enabled'` (default on). Append-only
preserved (insert only); no recon/ingest path touched.

**1.2 — Lock down & admin-gate audit READ** `[S · medium]` — **✅ SHIPPED (v6.3).** Require `audit_read` (or `require_admin`) on
`/api/audit/logs|actions|logs/export`; exclude scoped API keys. Swap dependency `get_current_user →
require_permission('audit_read')`; add to admin seed (admins short-circuit, so no migration). `medium` only
because it could 403 a non-admin relying on open access — default the perm true for admin-role + announce. No
schema/content change.

**1.3 — URL-synced, saveable, shareable views** `[M · none-additive]` — **✅ SHIPPED (v6.3).** Reflect every Open
Items/ProductReconPage filter set in the URL (two-way) + a per-user Saved Views store. Frontend
`setSearchParams` on filter change (filters already exist) + new `saved_views` table + new `/api/views`
endpoints. Open-Items query semantics/buckets/vocabulary unchanged (#14) — a saved view is a stored query
string replayed through the unchanged endpoint.

**1.4 — Ingestion event ledger + lineage** `[M · low]` — **✅ SHIPPED (v6.3).** Append-only `IngestionEvent` + `ingestion_rejects`
capturing source, channel, file SHA-256/name/size, detected preset, mapping version, rows
read/accepted/**skipped-with-per-reason-breakdown**, WLR/FREC outcome, duration, resulting `UploadSession` id
→ a read-only "Ingestion Monitor." A thin wrapper records BEFORE/AFTER metrics around the **existing**
confirm-mapping/`ingest_dataframe` calls (which already return skip counts + `integrity_warnings`), in a
separate transaction so a logging failure can't block ingest. Must not alter classification/ladder/tolerances/
pass order (#2,#3,#4,#10) — reads counters the code already computes.

**1.5 — Connector Registry + "Ingestion Sources" catalog** `[M · none-additive]` — **✅ SHIPPED (v6.3)** (delivery-status view; the editable owner/SLA registry table is deferred). A descriptive
`ConnectorSource` registry (DB + read UI) cataloguing every source — upload, watch-folder, future SFTP/API/feed
— with type, owner, expected cadence/SLA, preset link, last-seen status; surfaces "which partner hasn't
delivered today." New table seeded read-only from `WatchFolderConfig` + distinct partners; read-only
`/api/ingestion/sources` aggregating `UploadSession`/`WatchFolderConfig.last_trigger_*` + `Transaction
max(created_at)`. Zero changes to upload/ingest/scheduler.

**1.6 — Pre-ingest data-quality profiler (read-only, no gating)** `[M · none-additive]` — **✅ SHIPPED (v6.3).** At parse time
compute & store per-file profile: row count, per-mapped-column null/blank rate, parseable-amount rate,
date-parse rate, duplicate-key rate, control-total/checksum vs `sum(amount)`; non-blocking warning banner on
threshold breach. Pure read-only over the already-parsed DataFrame; stored on `ingestion_events`, returned as
a **new** Step-3 result field (additive, #25). Does not touch
`_classify_bank_row`/`_parse_description`/`_auto_detect_amount`/`FAILED_STATUSES` (#3,#9).

**1.7 — Match-confidence shadow scorer (display-only)** `[M · none-additive]` — `core/match_scoring.py`
computes a 0–100 confidence for (a) each matched pair and (b) the best candidate for each open item via a
transparent additive feature model (exact-amount, tolerance-band consumed, date proximity, identifier
equality vs fuzzy similarity, which rule fired). Writes **only** to a new `MatchScore` table; surfaced via
read-only endpoint + optional non-filtering confidence column. Nightly cron behind `MATCH_SCORING_ENABLED`
(off = zero code path). Produces the labelled feature set for later ML. No status/key/tolerance/pass-order
change (#1–#8).

**1.8 — Request cancellation + session-expiry UX** `[S · none-additive]` — `AbortController` on Open
Items/ProductReconPage load (newer filter cancels in-flight older) + a client-side JWT-`exp` idle warning that
stashes unsaved modal input to `sessionStorage` before the existing 401 redirect. Frontend-only; 401 behavior
unchanged (#12 untouched).

#### TIER 2 — Strategic Capabilities (M/L)

**2.1 — Additive exception-case layer + Case Cockpit** `[L · none-additive]` — A new `exception_case` table
keyed by `transaction_id` (+`module_ref`) holding a workflow lifecycle
(open/in_progress/pending_external/escalated/resolved/closed/written_off), assignee, priority, due_date,
root_cause_code — **without touching `recon_status`** (the sole matching authority). Lazily created on first
assign/comment/categorise. New "Case Cockpit" reads cases joined to live Transaction data. New table only
(nullable FK, no cascade — mirrors `matched_with_id`, #23); lifecycle never maps onto `ReconStatus` (#9
preserved); all endpoints new under `/api/cases`.

**2.2 — Canonical SLA/aging engine + smart routing** `[M×2 · low]` — (a) A read-only SLA service computing
**one** canonical case-age, configurable due-dates (partner/product/reason/amount-band), time-in-state,
at-risk/breached flags. (b) Rule-based routing config + a scheduled job that *suggests* assignees and
auto-escalates priority on SLA breach (suggest-only first). Computation over `recon_date`/`opened_at` + new
`sla_policy`/`routing_rule` tables; writes only to `exception_case`. **#19:** a **new, separately-labelled**
"case age" — the legacy three aging buckets stay byte-for-byte intact (not unified).

**2.3 — Case collaboration + root-cause taxonomy/analytics** `[M×2 · none-additive/low]` — (a)
`case_comment`/`case_attachment` → threaded discussion, evidence files, @mentions, reassignment/state-change
timeline. (b) A hierarchical `root_cause` taxonomy that **maps** (not renames) the existing 8 `exception_reason`
+ 9 `src_code` literals into a unified tree, + a read-only analytics dashboard (top causes, ₹ exposure by
cause/partner, recurring counterparties, MTTR by cause). New tables linked by `case_id`; **append** new
AuditLog action types (never mutate existing rows). Existing code literals not edited (#22) — overlay via a
`legacy_code → taxonomy_node` map.

**2.4 — True full-result-set bulk actions + maker-checker extension** `[M · low/medium]` — (a) New bulk
endpoints operating over an entire **filter** (not a page of IDs) — assign/categorise/set-priority/resolve/
write-off — each returning a per-row success/skip/fail manifest, with a "select all N matching" UI. (b) Wire
`maker_checker.intercept` into the currently-bypassing `rematch`/`tag_adhoc`/`manual_interbank`/`resolve_mismatch`/
bulk-match. New bulk endpoints reuse the **existing** per-row resolution functions in a loop, honour the
existing intercept, add a manifest — no change to action semantics/tolerances/match-ID. Intercept extension is
byte-identical when the maker-checker flag is OFF (the live default); `medium` only because it touches live
route entry points — mitigate with characterization tests asserting identical off-flag behavior (#16 preserved).

**2.5 — Inbound ingestion REST/webhook API (idempotent)** `[L · low]` — `POST /api/ingest/push` accepting a
structured payload or file plus a mandatory **idempotency key**, authed by the existing X-API-Key with a new
`ingest_push` scope; internally builds a DataFrame and calls the **same** existing
confirm-mapping/`ingest_dataframe` plumbing. New `routes/ingest_api.py` + an idempotency table integrating with
`file_hash_guard`. Calls existing ingest logic unchanged (#2,#3,#4,#7); existing endpoints untouched.

**2.6 — SFTP/cloud-bucket auto-pull + watch-folder control parity** `[L+M · low/medium]` — (a) A real
SFTP/S3/GCS connector that *deposits* remote files into the existing watch-folder mechanism, with a
`processed_files` fingerprint store (exactly-once), late-file catch-up, retry/backoff, per-source SLA/failure
alerting. (b) Run the same WLR/FREC/hash pre-checks on the watch-folder path behind a per-config flag,
initially **WARN/quarantine-only**. New `core/connectors/sftp_pull.py` only **deposits** files; the current
pickup runs unchanged. Control parity reuses `_check_wlr`/`_check_frec`/`guard_duplicate_file` read-only;
enforcement gated behind `WatchFolderConfig.enforce_checks` **default FALSE** (live behavior byte-identical
until opted in). `medium` isolated to enforce mode — ship WARN-only first. **#11 strengthened, never weakened.**

**2.7 — Suggested-match candidate ranking + GenAI exception narrator** `[L+L · low]` — (a)
`GET /api/recon/suggested-matches-v2`: partner-aware top-N counterpart candidates with score, "why" feature
list, fuzzy-reference similarity, **and one-to-many candidate groups** (internal rows summing to one bank row
within tolerance) — suggestions the operator confirms via the existing manual-match path. (b) An optional
GenAI narrator producing plain-language "likely unmatched because…" + suggested next action, optionally
pre-filling the (still human-edited) override remark. New read-only endpoints + UI panels; matcher core not
modified; suggestions never auto-applied; precondition checks live in the **new** endpoint only (legacy
`manual_match` untouched). GenAI flagged (`GENAI_NARRATOR_ENABLED`), PII-minimised, degrades silently with no
key — *confirm current Claude model IDs/params via the `claude-api` skill before wiring.* (#1–#8 untouched.)

**2.8 — Charting layer + Executive Dashboard + snapshot store** `[M+L · none-additive/low]` — (a) A nightly
read-only `recon_daily_snapshot` table written by a job that runs the **existing** dashboard-summary
aggregation. (b) A charting library + new `/executive` page: time-series match-rate, ageing distribution,
exposure (₹ at risk) trend, top-exposure partners, SLA breach counters — a controller/CFO cockpit distinct
from the operational Dashboard, every chart click-through to Open Items. New table (nullable, no FKs); extract
the dashboard-summary query into a pure helper both the live endpoint and the snapshotter call (no endpoint
behavior change); idempotent UPSERT on `(snapshot_date)`. New page gated by `analytics` permission; existing
Dashboard untouched; one additive charting dependency. **#9,#19:** analytics defines **its own** canonical
ageing/status constants, documented as analytics-only.

**2.9 — Tamper-evident audit hash-chain (shadow) + period-close snapshot** `[M+L · low]` — (a) A shadow
`audit_chain` table (`seq_no`, `prev_hash`, `entry_hash = H(prev_hash || canonical_json)`, HMAC) derived from
existing logs + a read-only `/api/audit/verify-chain`; optionally anchor the latest hash to WORM. (b) A
`ReconPeriodSnapshot`: an admin can "close" a (partner, period), freezing match results + balances into new
snapshot tables; certificates/exports can then generate against the **frozen** snapshot. Hash-chain derives
from existing append-only logs into a new table (never mutates `AuditLog`); computed, not enforced on the
write path. Period close is **copy-on-close** into new tables — never touches the live Transaction table,
never blocks recon, never alters replace/delete-and-recreate semantics (#13,#17). Certificate generator gets a
**new optional** `source=snapshot` branch; live path stays default (#25).

#### TIER 3 — Transformational / Platform Bets (L/XL)

**3.1 — Shadow atomic match-ID sequence (de-risk multi-worker)** `[L · low]` — A new `match_id_sequence` table +
`next_seq_atomic()` (DB-atomic). Behind `MATCHID_ATOMIC_SEQ=off`, run in **shadow**: on every real `_next_seq`,
also compute the atomic value and log a comparison — proving agreement over weeks **without changing a single
minted ID**. Removes the single hardest scale blocker (`_RECON_LOCK`) via an evidence-backed, finance-signed
switch. New table + function + shadow log only; live paths untouched while off; cutover is a separate gated
step (#1,#23 unchanged until cutover).

**3.2 — Certification & e-signature workflow with SoD** `[L · low]` — An account/period certification state
machine: preparer "reconciled" → a **different** reviewer → a certifier e-attests, capturing user, UTC
timestamp, statement, snapshot id + chain hash; SoD enforced (certifier ≠ preparer); blocked unless the period
snapshot exists. New tables + endpoints; reuses the maker-checker self-approval guard pattern; references the
period snapshot (2.9); writes AuditLog via the existing helper. New page; existing pages untouched;
feature-flagged.

**3.3 — Offline ML-suggested-match model (shadow inference, gated)** `[XL · low]` — Train an offline model on
the existing `AuditLog` manual_match/override history + `MatchProvenance` to predict P(correct match). Shadow:
a nightly batch scores open items into a new `MlSuggestion` table; ops see a labelled "AI suggestions (beta)"
panel and accept via the existing manual-match path. **Never auto-posts.** Adds auto-rule-proposal (recurring
high-confidence patterns draft a candidate `MatchRule` for admin review via the existing Logic Builder).
Entirely offline + read-only at inference; cron writes to a **new** table; nothing mutates Transaction or rules
automatically. *(Prerequisite: a `MatchProvenance` side-log — opt-in, flag-guarded, byte-identical when off.)*
Feature-flagged (`ML_SUGGESTIONS_ENABLED`); ships dark (#1–#8 preserved).

**3.4 — Shadow GL/Trial-Balance reconciliation + draft Journal register** `[XL · low]` — An optional
balance-substantiation layer: a `GLBalance` upload (reusing the existing loader read-only), a
`BalanceSubstantiation` endpoint tying a GL balance to the sum of matched + open reconciling items in
Transaction, and a `DraftJournalEntry` register to **propose** adjusting JEs and **export** them in a standard
template (draft/export only — **not** an ERP poster). New tables + router; substantiation only **reads**
aggregates; JE register stores drafts + exports a file. Only existing-table touch is an **additive nullable**
`PartnerConfig.gl_account_code` (or a standalone `GlAccountMap`). True ERP auto-posting deferred.

**3.5 — Close orchestration: Period + Checklist + Status dashboard** `[L · none-additive]` — New
`ClosePeriod`/`CloseTask`/`CloseTaskNote` tables + a `routes/close.py`: CRUD, dependency-aware completion, a
completion % rollup, a status board, a scheduled close-readiness digest. Tasks auto-seed from `PartnerConfig`.
All-new tables + new router gated by `close_manage`. Completion/dependency logic reads recon stats via existing
read queries; **never** calls `run_reconciliation`, **never** writes Transaction/`recon_status`/`match_id`
(#1,#4). The digest is a new subscription type on a new scheduler job id (does **not** revive the broken EOD
path).

**3.6 — RBI/escrow regulatory-reporting pack** `[L · low]` — Read-only generators for the India PPI/PA control
set: daily nodal/escrow balance reconciliation per settlement account; a day-end "escrow ≥ outstanding PPI
float + acquirer dues" pass/fail; monthly RBI transaction-statistics export; quarterly auditor/escrow-bank
certification pack — generated against frozen period snapshots, each writing an AuditLog `report_generated`.
New generators that **read** existing tables (+ snapshots); reuses openpyxl/reportlab + the report-subscription
scheduler. Entirely read-only; per-report flags.

**3.7 — Platform hardening bundle (each independently shippable, all gated):** leader-elected/shared-jobstore
scheduler `[M·med]`; structured logging + OpenTelemetry + Sentry + a "recon-health" watchdog `[M·low]` (incl. a
counter/log at each existing `except: pass`, and a watchdog alerting on watch-folder `not_found`/`error`/low
match rate/failed subscriptions — the safety-net the dead EOD digest never delivered); JWT revocation list +
login lockout + forced default-admin rotation + trusted-proxy XFF `[M·med]`; idempotency-key + optimistic
`row_version` shadow-validated `[L·med]`; outbound HMAC-signed webhooks `[L·low]`; secrets→vault/KMS +
field-level encryption for account numbers `[L·med]`; tenant/entity scoping foundation `[XL]` (a **nullable**
`tenant_id` backfilled to a single default tenant, enforced **only in new code paths**, enforcement on live
queries deferred). Every item env-gated and **default-off/inert**, observing rather than altering control flow.

### 5. Suggested Sequencing

**90 days — "close the compliance gap, make ingestion observable, give ops fast wins."** 1.1 config-audit
shim → 1.2 lock audit READ → 1.4 ingestion ledger + 1.6 DQ profiler → 1.5 connector registry + 1.3 URL/saved
views → 1.7 confidence scorer + 1.8 cancellation/session UX → **kick off 3.1 (shadow atomic sequence)** to
start accumulating agreement evidence early. *Outcome:* meaningfully more audit-defensible, observable
ingestion, ops have confidence scores + saveable views, multi-worker de-risking clock started.

**6 months — "managed exception layer, real analytics, programmatic ingestion, reproducible compliance."** 2.1
case layer + cockpit → 2.2 SLA/routing → 2.3 collaboration + root-cause → 2.4 bulk-at-scale + maker-checker
extension; 2.8 snapshot + charts + Executive Dashboard; 2.9 tamper-evident audit + period-close; 2.5 ingestion
API + 2.6 SFTP auto-pull (WARN mode); 2.7 ranked suggestions + GenAI narrator; begin 3.7 structured
logging/OTel + recon-health watchdog (delivers the alerting safety-net early).

**12 months — "platform-grade."** 3.1 atomic-sequence cutover (after evidence) → 3.7 leader-elected scheduler +
idempotency/version + webhooks (unblock multi-worker/HA); 3.2 certification + e-sign with SoD; 3.5 close
orchestration + 3.6 RBI/escrow pack; 3.3 offline ML model (after the `MatchProvenance` corpus matures); 3.4
shadow GL/TB + draft JE register; 3.7 secrets-to-vault + field-level encryption + tenant scoping foundation.
*Outcome:* a horizontally-scalable, multi-tenant-ready, ML-assisted, SOX/RBI-grade reconciliation platform with
close orchestration, GL substantiation, certification, regulatory reporting, and enterprise security — **having
never altered a single live reconciliation, match ID, tolerance, or stored-data semantic.**

---

## Part B — UI/UX Modernization Assessment & Roadmap

> Scope: **only** the operator console (`frontend/src`). Every recommendation is purely additive — new pages,
> widgets, opt-in toggles, read-only endpoints, nullable tables. **Nothing changes the recon team's existing
> screens, flows, filters, or results.**

### 1. Honest assessment — where we stand

The console is a **competent, cohesive back-office app**, on visual polish ahead of several incumbents
(Cadency/BlackLine are routinely called "old school" by their own users), with real architectural discipline.
But it sits **one generation behind the modern-SaaS bar** (Numeric, Modern Treasury, Sigma, Duco's Sept-2025
exceptions UI, Linear-grade interaction) on the three axes that matter most for a tool used 8h/day:
**power-user throughput, accessibility, and large-table behavior.**

**Strengths (verified in code — keep and build on):** centralized cross-cutting concerns (one axios instance
owns the Bearer header, 401 redirect, and the recursive UTC→IST interceptor — pages carry zero token/timezone
logic, honoring #12); SSOT registries (`productRegistry.js` + `filterModel.js`); a real branded design system
as a stated contract (`index.css` primitives + a load-bearing petrol-teal/amber palette, `focus-visible`,
`prefers-reduced-motion`); strong financial-table hygiene (`tabular-nums` + `toLocaleString('en-IN')`);
defensive resilience (top-level `ErrorBoundary`, per-fetch `.catch` fallbacks); mature exceptions affordances
(mandatory-remark modals, aging badges, Recon-ID drill-down, two-step interbank pairing, sticky bulk bar);
consistent permission-aware rendering (with the correct assumption that the backend is the enforcement
boundary).

**Pain points (verified by grep — the modernization targets):**

| # | Gap | Evidence | Why it matters |
|---|---|---|---|
| P1 | **Accessibility effectively absent** | `grep aria-*/role=/sr-only/htmlFor/alt=` → **0**; even branded `ActionModal` has no `role="dialog"`/`aria-modal`/focus-trap/Escape; icon-only buttons carry `title` only | WCAG 2.1/2.2 AA + VPAT is a hard procurement & EAA/ADA gate; would fail a basic screen-reader audit — real audit/legal exposure |
| P2 | **No saved/shareable/bookmarkable views** | `setSearchParams` **never called**; OpenItems reads seed params but never writes back | Can't bookmark/share/refresh-survive a filtered set |
| P3 | **Bulk actions & column filters scoped to loaded page** | OpenItems `page_size:50`; ProductReconPage `rows.filter(...)` (line 559) + `toggleAll` over loaded page | **Money-affecting trap:** bulk action after a filter silently hits one page; "No rows match" hides other-page rows |
| P4 | **No command palette / keyboard-first** | no `cmdk`/`useHotkeys`; mouse-driven | Numeric/Sigma set this bar; triage repeated hundreds×/day |
| P5 | **No virtualization, no column control** | every grid in `overflow-x-auto` (~50 refs); 17/11 cols; no hide/pin/reorder/density | AG Grid/TanStack virtualize tens of thousands of rows |
| P6 | **No request cancellation** | `grep AbortController/cancelToken/signal:` → **0**; `load()` fires on every change | Last-response-wins not guaranteed → stale rows under a newer filter |
| P7 | **Destructive actions use native `confirm`/`prompt`** | **17 sites across 11 files**; F2 migration half-done | Unbranded, Enter-dismissible, no recap |
| P8 | **Dashboard is a reporting view, not "do-the-work"** | identical for every user, scoped only by `allowed_products`; no personal queue | Osfin/Numeric lead on the personalized work-queue home |
| P9 | **No charts; `.skeleton` unused** | **no charting lib** in `package.json`; hand-rolled `RateBar` divs; plain `Loading…` | most visible dashboard gap vs every named tool |
| P10 | **No responsive/reviewer layout** | no mobile drawer, no breakpoints below `sm` | approvers can't review on a tablet |
| P11 | **Thin session UX; 401 destroys in-progress work** | localStorage Bearer; no idle timeout; interceptor hard-redirects, wiping a half-written remark | re-work risk on financial overrides |
| P12 | **Status/badge maps duplicated across pages** | `STATUS_BADGE` vs `statusColors.js` vs `filterModel` — must stay lockstep with backend #9 | a backend-added status renders gray and mis-filters with no error |

The throughline: deep matching is table stakes and we have it; the 2025–2026 differentiator is **analyst
throughput and auditor confidence delivered through UX** — exactly where the gaps cluster.

### 2. Prioritized, additive UI roadmap

**Tier 1 — Quick wins.** **T1.1 URL-synced + saveable + shareable views** `M/high/none-additive` (closes P2;
extend the existing `useSearchParams` seeding to also write, + a `saved_views` table + `/api/views`; no change
to `/api/recon/open-items` semantics, #14). **T1.2 Command palette (Cmd/Ctrl-K)** `M/high/none-additive`
(generated from the existing route table + registry + saved views; navigates only, bypasses no permission
gate). **T1.3 Accessibility to WCAG 2.1 AA + shared accessible `<Modal>`** `L/high/none-additive` (ARIA,
accessible names, focus-trapped dialogs, `axe-core` in CI, VPAT; one shared `<Modal>` that `ActionModal`/
`RemarkModal` adopt — the vehicle that also lets the 17 native dialogs migrate). **T1.4 Role-based "My Work"
home** `M/high/none-additive` (a `/home` opening to the operator's actionable queue; new read-only aggregate
endpoints over existing `assigned_to`/`exception_reason`/aging; tiles deep-link to existing Open Items; keep
the current Dashboard, make `/home` default only behind a per-user pref). **T1.5 Request cancellation +
last-write-wins guard** `S/medium/none-additive` (`AbortController` on load paths). **T1.6 Skeleton/empty-state
+ dark mode + density** `M/none-additive` (use the already-defined `.skeleton`; CSS-variable theme; current
palette becomes the "light" default). **T1.7 Finish the branded-dialog migration** `S/medium/none-additive`
(migrate the 17 native sites to the shared `<Modal>` with typed confirmation + item recap, in front of the
same existing handlers — gates/remarks/audit unchanged).

**Tier 2 — Strategic.** **T2.1 Explicit bulk-action scope ("all N matching" vs "this page") + progress + undo**
`L/high/low` (fixes the money-affecting trap P3; read side extends `/api/recon/open-items` with the
column-filter params + a `total` count — backward-compatible, needs a characterization test, #14/#25; write
side composes the **same existing** bulk endpoint over the full filtered ID set in batches — semantics
unchanged). **T2.2 Virtualized data grid + column show/hide/pin/reorder + density** `L/medium/low` (headless
TanStack Table + virtualizer behind a per-user "beta grid" flag; same row data + same `.table-th/.table-td`;
the existing table stays default). **T2.3 Real-time progress for long operations** `M/medium/none-additive`
(reuse the existing job pool; a read-only `GET /api/jobs/{id}/progress` reporting counters the steps already
produce; pass order/logic untouched, #4). **T2.4 In-app analytics (charting + Executive cockpit)**
`L/high/low` (new `/analytics` page + one charting dep — recharts; Dashboard untouched; *prefer* feeding from
the snapshot read model so charts are reproducible and never load live recon; analytics defines its own
canonical buckets, #9/#19). **T2.5 Session-expiry UX: idle warning + draft preservation** `M/medium/none-additive`
(decode JWT `exp` client-side; stash modal input to `sessionStorage` before the existing 401 redirect; backend
auth/token lifetime/401 behavior unchanged).

**Tier 3 — Transformational.** **T3.1 Unified exceptions cockpit** `L/high/low` (fuse virtualized grid +
saved views + full-result bulk + a side-panel inspector with the audit timeline + inline suggested matches +
keyboard nav j/k/x + copy-to-Excel/email of a filtered set; composed from additive Tier-1/2 pieces over the
**unchanged** read/action endpoints; behind the beta flag). **T3.2 Self-service saved-views/report builder**
`L/medium/low` (pick product/partner/date/status/group-by/columns, preview, save, optionally schedule;
new table + read-only compose/preview/run endpoints over the snapshot read model; reuses the
`report_subscriptions` pattern as an additive subscription type; never alters existing `/reports`, #25).
**T3.3 Guided onboarding & in-product help** `M/medium/none-additive` (first-run tour, contextual empty-states,
inline validation, searchable help drawer tied to the palette).

**Dependency-aware sequencing.** Wave 1 (foundations): T1.5 → T1.3 a11y+shared `<Modal>` → T1.1 URL-sync+saved
views → T1.7 dialog migration. Wave 2 (throughput): T1.2 palette → T1.4 My-Work home → T1.6 skeleton/dark/
density. Wave 3 (scale & trust): T2.1 bulk scope (+char. test) → T2.3 progress → T2.2 virtualized grid → T2.5
session UX. Wave 4 (analytics): snapshot read model → T2.4 charts + exec cockpit. Wave 5: T3.1 cockpit → T3.2
report builder → T3.3 onboarding. (`T1.3`'s shared `<Modal>` unblocks `T1.7`; `T1.1`'s store backs column
prefs in `T2.2` and theme/density in `T1.6`; the snapshot read model backs `T2.4`/`T3.2`.)

### 3. Design-system, component-library & foundations

**Extend, don't replace.** (1) Promote `index.css` primitives into a small documented component set (`Button`,
`Card`, `Input`, `Select`, `Badge`, `Table`, `Modal`, `Skeleton`) that *wrap* the existing classes — no
renames, no look change; this is the seam through which a11y, dark-mode variables, and density land once. (2)
A single shared accessible `<Modal>` (focus trap, `role="dialog"`, `aria-modal`, Escape) is the highest-leverage
primitive — carries T1.3 + T1.7 together. (3) Centralize the duplicated status/badge maps (P12) so a
backend-added status can't silently render gray and mis-filter (a pure consolidation; keeps lockstep with #9
without touching the backend sets).

**Component-library choice (additive, headless).** Stay React 18 + Vite + Tailwind; add only **headless**
libs so the design system stays authoritative: `cmdk` (palette), `@tanstack/react-table` + `react-virtual`
(grid), `recharts` (charts). Each a single additive dependency behind a flag.

**Performance foundations.** Eliminate the silent-stale-data class with `AbortController` (cheapest correctness
win); virtualize the 11–17-col grids; **serve analytics from a snapshot read model** (never full-table scans on
the live ledger — keeps dashboards sub-second *and* keeps the single-worker recon path uncontended, #1/#23);
code-split the new heavy routes via `React.lazy`.

**Accessibility foundations.** Adopt WCAG 2.1/2.2 AA, wire `axe-core` into CI (warn → block), ship a VPAT 2.5.
The shared `<Modal>` + component-set wrappers make AA reachable as an additive attribute/markup pass, not a
rewrite.

**Bottom line.** Well-architected and visually ahead of several incumbents, but trailing the modern bar on
throughput, accessibility, and large-table behavior — with one genuine money-affecting UX trap (page-scoped
bulk actions, P3). Every fix is deliverable additively; the recon team's screens, filters, workflows, and
results are never altered, with the lone behavior-contract-adjacent item (T2.1's optional read-side query
param) explicitly flagged `low` and gated behind a characterization test.

---

## Part C — Risk Register (latent issues found by the audit; NOT changed; need sign-off)

These are genuine correctness/control issues. Because fixing them **changes behavior**, they are **out of scope
for the additive roadmap** and listed for your decision. Most can be **detected** additively now (via Tier-1
items) while the underlying fix is scheduled with characterization tests + sign-off.

| ID | Severity | Issue | Detect additively now? |
|---|---|---|---|
| R1 | **High** | **Dual ingest-copy drift** — watch-folder path omits Levin EKOI-prefix strip, QR `net_amount`, AS=SD integrity, Levin DR default → *different rows* than the interactive path for the same file | Yes — shadow-parse + diff (1.4/1.6) |
| R2 | **High** | **Auto-upload bypasses WLR/FREC/slot/hash guards** + `recon_date='auto'` defeats the slot guard → silent double-count on the least-supervised channel | Yes — 2.6 WARN-mode + duplicate detector |
| R3 | **High** | **Match-ID allocation single-worker-only** (process-local lock, no DB sequence/unique constraint) — multi-worker mints duplicate audit IDs | Yes — 3.1 shadow allocator + monitor |
| R4 | **High** | **Config/entitlement changes unaudited** + audit log not tamper-evident + audit read open to any user | Yes — 1.1 + 1.2 + 2.9 (all additive) |
| R5 | **High** | **EOD digest email is dead** (never registered; would also crash on SQLAlchemy 2.x `db.execute(str)`) | Yes — 3.7 recon-health watchdog (new notifier) |
| R6 | **Med-High** | **`amount_mismatch` pairs consume both rows** — the true counterpart can no longer match; can mask real shortfalls/overages | Yes — exposure report on mismatch pairs |
| R7 | **Med-High** | **Manual match / rematch / interbank lack precondition checks**; several **bypass maker-checker** | Yes — 2.4 closes additively (opt-in) |
| R8 | **Med** | **Float money + lexicographic dates**; date-range reports **silently drop `'auto'`-dated rows** from certificates/exports | Yes — "rows excluded by date sentinel" warning |
| R9 | **Med** | **E-Value bank re-upload deletes prior human work** (matches/overrides/recovery) with no archive | Yes — snapshot before replace (2.9) |
| R10 | **Med** | **SBI `upload_date==today` coupling** → D+1 settlement invisible unless re-uploaded; spurious PENDING | Detection/report only |
| R11 | **Med** | **Scheduled SBI/BBPS/E-Value mis-ingest** — cron path can't route them to specialised handlers | Yes — guard/alert if such a config is scheduled |
| R12 | **Low-Med** | **Startup rewrites match-IDs every boot**; silent `try/except: pass` migrations can mask schema drift | Yes — schema_version + boot health surface |

**Recommended handling:** adopt the **detect-additively-now** column immediately (all Tier-1-safe), and
schedule R1–R5 as **separately-approved, test-guarded fixes** (each behind a characterization test that
captures *current* behavior first). None is touched without explicit go-ahead.

---

## Appendix — provenance

- **Audit (9 subsystems, full per-subsystem detail incl. processes/strengths/gaps/risks):** workflow run
  `wf_14fc126f-5a0`, raw output under the session's `tasks/` directory.
- **Benchmark (8 capability dimensions, ~50 risk-rated recommendations) + synthesis:** same run, resumed
  2026-06-23 after the rate-limit reset.
- **Grounding:** `docs/behavior-contract.md` (25 invariants), `docs/known-issues.md`, `docs/architecture.md`,
  `CLAUDE.md`.
