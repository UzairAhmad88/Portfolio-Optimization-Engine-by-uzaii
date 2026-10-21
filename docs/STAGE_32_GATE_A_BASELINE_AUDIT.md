# STAGE 32 — GATE A: ARCHITECTURE & BASELINE AUDIT
## Immutable Dataset Versioning, Research Snapshots & Point-in-Time Data Provenance Auditing

**Project:** Quantitative Portfolio Optimization Engine  
**Stage:** 32 — Gate A (Architecture & Baseline Audit)  
**Session:** 55  
**Date:** October 21, 2026  
**Roles:** Principal Quantitative Finance Architect, Data Governance Engineer, Database Architect, Independent QA Auditor  
**Repository:** `https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii.git`  
**Current Branch:** `main`  
**Verified Head Commit:** `9922cb171cced14f348b59b87b0f50c437608048`  
**Gate A Verdict:** **`PASS — ARCHITECTURAL BASELINE ESTABLISHED`**  

---

## 1. Executive Summary & Actual Repository State

In Session 54, the Project Owner formally accepted **Stage 31 (Point-in-Time Market Data Integrity & Corporate Actions)**. In accordance with Session 55 instructions, this audit establishes the architectural foundation and concrete baseline for **Stage 32: Immutable Dataset Versioning, Research Snapshots & Point-in-Time Data Provenance Auditing**.

### Repository State Verification
* **Git Branch:** `main` (clean working tree, zero unstaged/staged modifications).
* **Remote Tracking:** `origin/main` is fully synchronized with local `main`.
* **Head Commit:** `9922cb171cced14f348b59b87b0f50c437608048` (`docs: record Stage 31 formal owner acceptance and candidate Stage 32 roadmap`).
* **Clean Diff Quality:** `git diff --check` passed with 0 errors or whitespace warnings.
* **Database State:** Clean schema at migration head `c1d2e3f4a5b6` (corporate actions table and dataset PIT columns).
* **Codebase State:** 511 backend pytest tests passing, 43 frontend Vitest tests passing, Vite production build clean.

---

## 2. Verified Stage 31 Dependency Baseline

Stage 32 directly relies on the mathematical and architectural capabilities established in Stage 31:

1. **Exchange Calendars (`calendars.py`):**
   - Authoritative `USCalendar` (NYSE/NASDAQ, `version="US-NYSE-2026.1"`) with statutory holidays, weekend shifts, and historical exceptional closures.
   - Authoritative `PSXCalendar` (Pakistan Stock Exchange, `version="PSX-KHI-2026.1"`) with fixed statutory closures and gazetted Islamic lunar holiday tables for 2020–2026.
   - Session alignment (`align_cross_market_sessions`) and missing-bar detection (`detect_missing_sessions`).
2. **Canonical Corporate Actions (`corporate_actions.py`):**
   - `CorporateActionEvent` schema covering stock splits, reverse splits, cash dividends, symbol changes, and complex unsupported actions.
   - `CorporateActionLedger` providing deterministic event deduplication and revision supersession (`status="active" | "superseded" | "cancelled"`).
   - `SymbolMappingRegistry` tracking asset identity stability across ticker changes (e.g. `FB` $\to$ `META`).
3. **Deterministic Price Adjustments (`adjustments.py`):**
   - Unambiguous separation between raw prices, provider-adjusted prices, and system-derived adjusted prices.
   - Mathematical distinction between price return series ($r^{\text{price}}$) and dividend-inclusive total return series ($r^{\text{total}}$).
   - Versioned adjustment policy (`AdjustmentPolicy(version="2026.1")`).
4. **Point-in-Time Anti-Leakage (`point_in_time.py`):**
   - `PointInTimeCutoff` filtering actions strictly by `announcement_date <= as_of_date`.
   - Fail-closed semantics for unverified historical datasets lacking announcement provenance.
5. **Backtesting Dynamic Integration (`prepare_backtest_data`):**
   - Dynamic resolution of corporate actions at backtest decision cutoffs, preventing double-adjustment on provider pre-adjusted series.

---

## 3. Current Dataset and Price-Bar Lifecycle Audit (Workstream 32.1)

An in-depth inspection of `backend/app/market_data/` and `backend/app/db/models.py` reveals the current operational lifecycle:

### 3.1 Dataset Creation and Ingestion Path
1. **Upload Initiation (`routes.py::upload_csv`):**
   - Researcher uploads a CSV file via `POST /api/v1/market-data/uploads`.
   - File size is capped at 10 MB (`_read_upload`).
2. **Validation & Hashing (`service.py::validate_csv`):**
   - The SHA-256 digest of the **raw uploaded bytes** is computed: `digest = sha256(raw).hexdigest()`.
   - CSV rows are parsed, validated for geometry (OHLC), dates, tickers, currencies, and non-negative volumes.
3. **Deduplication & Storage (`service.py::register_csv_dataset`):**
   - The database is queried: `repository.find_dataset_by_sha256(session, content_sha256, user_id=user_id)`.
   - If an identical raw file was already uploaded by that user, the existing `DatasetModel` is returned (idempotent raw byte deduplication).
   - If new, a UUID is generated (`dataset_id`), and records are inserted into:
     * `datasets`: stores `filename`, `content_sha256`, `rows_examined`, `valid_rows`, `rejected_rows`, `point_in_time_status`, `calendar_version`, `adjustment_policy_version`.
     * `dataset_assets`: aggregate summary per asset (`start_date`, `end_date`, `observation_count`).
     * `price_bars`: individual normalized bars with constraint `uq_dataset_ticker_market_date`.
4. **Critical Finding — Raw Bytes Discarded:**
   - The raw CSV file bytes are **not stored** on disk or in the database. Once parsed into `price_bars`, the raw input stream is gone. Only the SHA-256 hash of the upload is preserved.

### 3.2 Dataset Mutability and Identity Drift
* **Price Bar Immutability:** There is currently no API endpoint to edit, update, or patch individual `price_bars`. A dataset's price bars are effectively static once imported.
* **Corporate Action Mutability Risk:** Corporate actions can be ingested into `corporate_actions` at any time via `POST /api/v1/market-data/corporate-actions`, linked to `dataset_id`.
  - Adding, revising, or superseding corporate actions for a dataset **does not change `dataset.content_sha256`**!
  - Consequently, `dataset.content_sha256` reflects *only the raw CSV file uploaded on Day 1*, not the total market-data and corporate-action state.
* **Identity Instability:** If a dataset's corporate actions are updated, downstream consumers using `dataset_id` observe different adjusted prices over time while the dataset ID remains unchanged.

---

## 4. Research-Run and Backtest Input Lineage (Workstream 32.2)

Tracing the execution call paths across backtesting, scenarios, simulations, and research experiments reveals significant lineage gaps:

### 4.1 Backtesting Engine (`backend/app/backtesting/`)
* **Execution:** `prepare_backtest_data()` resolves prices from `price_bars` and `corporate_actions` based on `dataset_id`.
* **Persistence (`BacktestRunModel`):**
  - Stores: `dataset_id`, `strategy_type`, `strategy_config_json`, `summary_metrics_json`, `equity_curve_json`, `rebalance_events_json`.
  - **Missing Lineage:** Does **not** store `dataset_version_hash`, `snapshot_id`, `corporate_action_cutoff`, `point_in_time_metadata`, `calendar_version`, or `adjustment_policy_version`.
  - **Re-run Consequence:** If a user re-runs a backtest using its saved `strategy_config_json`, the backtesting engine queries the *current* state of the dataset and corporate action ledger, which may have evolved since the original run.

### 4.2 Research Lab Experiments (`backend/app/research/`)
* **Execution (`service.py::execute_experiment_run`):**
  - Reads `dataset_hash = dataset.content_sha256`.
  - Saves `ResearchExperimentRunModel(dataset_version_hash=dataset_hash, config_fingerprint=...)`.
  - Compares: `if dataset.content_sha256 != run.dataset_version_hash: warn(...)`.
* **Lineage Gap:** While Stage 12 added `dataset_version_hash`, this hash only tracks the raw CSV upload digest. If corporate actions are added or superseded, `dataset.content_sha256` does not change, meaning the Research Lab **falsely reports that the dataset has not evolved** when its corporate actions actually changed!

### 4.3 Other Quantitative Engines
* **Scenario Analysis (`ScenarioRunModel`):** Stores `dataset_id`; no content hash or version metadata.
* **Monte Carlo / VaR (`RiskSimulationRunModel`):** Stores `dataset_id`; no content hash or version metadata.
* **Performance Attribution (`PerformanceReportModel`):** Stores `dataset_id` and `backtest_id`; no content hash.

---

## 5. Content Identity and Integrity Assessment (Workstream 32.3)

### 5.1 Flaws of Raw File Hashing
The current system computes `content_sha256 = sha256(raw_bytes).hexdigest()`. Raw file hashing has severe limitations:
1. **Formatting Sensitivity:** Changing CSV line endings (`\r\n` vs `\n`), column ordering, trailing commas, or whitespace alters the hash completely, even if the financial data is identical.
2. **Row Order Sensitivity:** Two files containing the exact same price observations in different order produce different hashes.
3. **Omission of Corporate Actions:** Does not account for split/dividend events that govern price adjustments.

### 5.2 Canonical Content Manifest Requirements
To achieve true content identity, Stage 32 must define a **Canonical Observation Manifest**:
* **Deterministic Normalization:**
  - Asset records sorted lexicographically: `(ticker ASC, market ASC, date ASC)`.
  - Normalized fields: `open`, `high`, `low`, `close`, `adj_close`, `volume` formatted to fixed decimal strings (e.g. 6 decimal places, nulls as `null`).
  - Standard timezone representation (`UTC` / ISO-8601).
* **Merkle / Composite Hashing:**
  $$\text{Manifest Hash} = \text{SHA256}(\text{PriceBarsHash} \,||\, \text{CorporateActionsHash} \,||\, \text{PolicyVersion} \,||\, \text{CalendarVersion})$$
* **Canonical JSON Utility:** Leverage the established `canonical_json_dumps` engine from `backend/app/research/fingerprint.py` (which sorts keys, rounds floats, and strips whitespace).

---

## 6. Point-in-Time Provenance Assessment (Workstream 32.4)

### 6.1 Requirements for Point-in-Time Research Snapshots
A research snapshot must freeze not only the data points, but the **information state available at the historical decision cutoff**:
1. **As-Of Cutoff Timestamp ($T_{\text{cutoff}}$):** The decision boundary.
2. **Corporate Action Ledger State:** Exactly which splits and dividends had `announcement_date <= T_{\text{cutoff}}`.
3. **Revision State:** Later corrections announced after $T_{\text{cutoff}}$ must be excluded from the snapshot view.
4. **Calendar and Quality Policies:** The exact versions of `USCalendar` / `PSXCalendar` (`2026.1`) and `QualityAuditPolicy` (`2026.1`) used.
5. **Legacy Data Qualification:** If a dataset originates from a CSV without announcement timestamps, creating a snapshot must **not** magically certify it as PIT-safe. The snapshot must inherit and seal the `point_in_time_status = "unverified_legacy"`.

### 6.2 Data Storage Strategy for Snapshots
* *Naive Full Duplication (Anti-Pattern):* Copying all `price_bars` rows for every snapshot would cause exponential database bloat ($10 \text{ snapshots of } 500{,}000 \text{ rows} = 5{,}000{,}000 \text{ duplicate rows}$).
* *Recommended Snapshot Strategy:* Manifest-based virtual snapshots referencing immutable base bar ranges plus temporal corporate-action cutoff filters, sealed with a cryptographic manifest digest.

---

## 7. Persistence, API, Security & Lifecycle Assessment (Workstream 32.5)

### 7.1 Relational Architecture & Migration Ancestry
The existing schema has 8 linear Alembic migrations:
```
0a14be571daa (market data) -> 7c4a4e92cae9 (users) -> 8993dbd79e8a (backtests) 
-> e4f5a6b7c8d9 (scenarios) -> f5a6b7c8d9e0 (simulations) -> a1b2c3d4e5f6 (performance) 
-> b2c3d4e5f6a7 (research lab) -> c1d2e3f4a5b6 (corporate actions & PIT)
```
Stage 32 can cleanly introduce migration `d3e4f5a6b7c8` descending from `c1d2e3f4a5b6` to create `dataset_snapshots` without breaking existing tables.

### 7.2 Multi-Tenant Security & Access Control
* Snapshots must enforce strict tenant ownership:
  $$\text{Snapshot Access Permitted} \iff (\text{snapshot.user\_id} == \text{current\_user.id}) \lor (\text{current\_user.is\_admin}) \lor (\text{snapshot.is\_shared})$$
* Cross-tenant read, write, or tagging of snapshots must be rejected with HTTP 403/404.

### 7.3 Snapshot Lifecycle & Deletion Protection
* **Retention Policy:** Snapshots referenced by completed `backtest_runs` or `research_experiment_runs` must be protected from accidental deletion via foreign key constraints (`ondelete="RESTRICT"` or soft-archival).

---

## 8. Gate A Gap Matrix

| Area / Capability | Actual Current State | Inspected Evidence | Identified Gap | Financial / Research Risk | Proposed Stage 32 Direction |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dataset Hashing** | SHA-256 of raw uploaded CSV bytes. | `validate_csv` in `service.py:160` | Formatting/order changes break hash; corporate actions omitted. | False drift warnings or missed data mutations. | Implement canonical observation manifest and composite hash. |
| **Raw Data Retention** | Raw CSV bytes discarded after parsing. | `register_csv_dataset` in `service.py:381` | Original source bytes cannot be inspected, exported, or re-verified. | Regulatory audit failure; inability to reconstruct raw uploads. | Retain optional raw byte archive or reproducible canonical export. |
| **Backtest Lineage** | `BacktestRunModel` only records `dataset_id`. | `models.py:259`, `backtesting/service.py:91` | No record of dataset hash, snapshot ID, or PIT cutoff metadata. | Re-running a backtest produces different results if data evolved. | Add `dataset_snapshot_id` and `dataset_version_hash` to backtest models. |
| **Research Lab Lineage** | Stores `dataset_version_hash = dataset.content_sha256`. | `research/service.py:300`, `models.py:637` | Blind to corporate action changes and price-bar updates. | False claim of dataset stability despite corporate action drift. | Bind experiment runs to immutable `snapshot_id` with composite hash. |
| **Snapshot Concept** | No snapshot entity exists in the schema. | `backend/app/db/models.py` | Datasets are open-ended mutable containers; no freeze point. | Inability to freeze a historical research dataset for institutional audit. | Create `dataset_snapshots` table with cryptographic manifests. |
| **Point-in-Time Sealing** | PIT metadata computed at runtime but discarded. | `prepare_backtest_data` in `backtesting/data.py` | Run results do not persist their PIT certification details. | Inability to prove to auditors that a historical backtest avoided lookahead. | Persist complete `PointInTimeAuditResult` in snapshot record. |
| **Dataset Versioning API** | Only `GET /datasets` and `POST /uploads` exist. | `backend/app/api/v1/routes.py` | No endpoints to freeze, tag, list, or inspect dataset snapshots. | Researchers cannot manage or select specific versions in the UI. | Expose `/market-data/datasets/{id}/snapshots` endpoints. |
| **Frontend UI Integration** | UI only lists active datasets. | `MarketDataPage.tsx`, `DatasetContext.tsx` | No UI to view snapshots, tags (`baseline_2024_q1`), or provenance badges. | Researchers cannot choose frozen snapshots for backtests/experiments. | Add Snapshot Management panel and snapshot selector in Backtesting & Research. |

---

## 9. Architecture Options Analysis

Three distinct architectural models were evaluated:

### Option A: Database-Native Full Observation Duplication
* **Mechanism:** Every snapshot copies all associated `price_bars` and `corporate_actions` into dedicated snapshot observation tables (`snapshot_price_bars`).
* **Pros:** Complete physical isolation; standard SQL queries without complex joins or filtering.
* **Cons:** Massive disk and memory bloat; unacceptable scaling for large institutional universes.
* **Rating:** Rejected due to excessive storage overhead.

### Option B: External Object Storage / Content-Addressed Blobs (CAS)
* **Mechanism:** Normalized observation panels and corporate actions are serialized to Parquet/Arrow blobs, stored in object storage (e.g. S3/GCS/MinIO), and referenced by relational metadata.
* **Pros:** Highly scalable, natural fit for massive enterprise data lakes.
* **Cons:** High operational complexity, requires external blob store infrastructure, violates existing modular monolith architecture.
* **Rating:** Unsuitable for current project architecture.

### Option C: Hybrid Relational Manifest & Virtual Snapshot Architecture (Recommended)
* **Mechanism:** 
  1. Base price bars remain in `price_bars` table.
  2. `dataset_snapshots` stores:
     - `id` (UUID), `dataset_id`, `user_id`, `tag` (e.g. `2024_Q1_PROD`).
     - `manifest_sha256`: Cryptographic digest of the canonical manifest.
     - `manifest_json`: Manifest containing asset lists, observation date ranges, count, and action IDs.
     - `point_in_time_cutoff_date`, `point_in_time_status`, `calendar_version`, `adjustment_policy_version`.
     - `is_frozen`: Boolean preventing modification.
  3. A dedicated **Snapshot Resolution Service** reconstructs the exact historical panel for any snapshot on demand, using base bars filtered by the snapshot's manifest and corporate-action cutoffs.
* **Pros:** Zero row duplication, minimal storage footprint, strict cryptographic reproducibility, full backward compatibility.
* **Rating:** **Recommended Direction.**

---

## 10. Recommended Candidate Design & Unresolved Decisions

### Candidate Design Overview
1. **Model:** Introduce `DatasetSnapshotModel` in `backend/app/db/models.py`.
2. **Canonical Manifest Generator:** Pure Python module in `backend/app/market_data/manifest.py` generating deterministic manifests and SHA-256 digests.
3. **Integration:** Update `BacktestRunModel` and `ResearchExperimentRunModel` to optionally reference `snapshot_id`.
4. **Replay Service:** `resolve_snapshot_price_panel(snapshot_id, ...)` returning deterministic, frozen data.

### Unresolved Architectural Decisions for Project Owner Review
1. **Raw Byte Retention Policy:** Should raw uploaded CSV files be archived to an encrypted local directory / database blob, or is the canonical observation manifest sufficient for reproducibility?
2. **Snapshot Creation Trigger:** Should snapshots be created manually by researchers (e.g. "Freeze Snapshot"), or automatically on every backtest / experiment execution?
3. **Snapshot Immutability Enforcement:** Should snapshot deletion be strictly forbidden if any backtest references it, or should it support soft-archival?

---

## 11. Proposed Stage 32 Workstreams & Acceptance Gates

* **Workstream 32.1:** Canonical Manifest Engine & Hashing (`manifest.py`).
* **Workstream 32.2:** Database Relational Persistence & Migration (`dataset_snapshots` table).
* **Workstream 32.3:** Snapshot Replay & Point-in-Time Data Provider Service.
* **Workstream 32.4:** Backtesting & Research Lab Integration.
* **Workstream 32.5:** REST API Endpoints & Security Authorization.
* **Workstream 32.6:** Frontend Workspace UI (Snapshot Manager & Selectors).

### Acceptance Gates
* **Gate A (Architecture & Baseline Audit):** *Current Gate — Completed.*
* **Gate B (Manifest Engine & Relational Contracts):** Mathematical manifest tests, Alembic migration, schema contracts.
* **Gate C (Snapshot Replay & PIT Sealing):** Replay service, deterministic verification fixtures, anti-tamper proofs.
* **Gate D (Engine Integration):** Backtest and Research Lab integration, regression verification.
* **Gate E (API, Frontend & Quality Assurance):** REST routes, React 19 UI, full regression suites.
* **Gate F (Independent Audit & Release):** Read-only quantitative audit, owner acceptance review, GitHub release.

---

## 12. Migration and Backward-Compatibility Risks

1. **Non-Destructive Schema Evolution:**
   - Migration `d3e4f5a6b7c8` will create `dataset_snapshots` and add nullable foreign keys `snapshot_id` to `backtest_runs` and `research_experiment_runs`.
   - Existing backtests and datasets continue operating seamlessly without disruption (`snapshot_id=None` fallback).
2. **Zero Invalidation of Historical Results:**
   - Legacy runs without snapshots remain intact and labeled as `legacy_unversioned`.

---

## 13. Required Tests and Audit Evidence

Future test suites for Stage 32 will require:
1. **Manifest Determinism:** Identical data in different row order produces the exact same manifest hash.
2. **Mutation Detection:** Perturbing a single price observation or corporate action alters the manifest hash.
3. **Historical Freezing Proof:** Modifying the base dataset after snapshot creation does not change the snapshot's resolved price panel.
4. **Tenant Isolation:** Tenant B cannot view or reference Tenant A's snapshots.
5. **Reversible Migration:** `alembic upgrade head -> downgrade -1 -> upgrade head` verified clean.

---

## 14. Explicit Scope Exclusions

The following areas are explicitly excluded from Stage 32:
* Real-time streaming WebSocket data feeds.
* External vendor API scraping or paid market-data licensing integrations.
* Destructive refactoring of existing Stage 1–31 calculation engines.
* Redesign of existing portfolio optimization algorithms.

---

## 15. Gate A Verdict

**VERDICT: `PASS — ARCHITECTURAL BASELINE ESTABLISHED`**

*Rationale:* The actual repository state, Stage 31 dependencies, dataset lifecycles, and research lineages have been thoroughly inspected. All architectural gaps, risks, and options have been documented. The roadmap is grounded in evidence without modifying application code or schemas.

---

## 16. Exact Project Owner Decision Required

To proceed with Stage 32, the Project Owner is requested to confirm:

1. **Gate A Acceptance:** Do you approve the **Gate A Baseline Audit** and the proposed **Hybrid Relational Manifest & Virtual Snapshot Architecture (Option C)**?
2. **Authorization to Proceed to Gate B:** Do you authorize commencing **Gate B (Manifest Engine & Relational Contracts Specification)**?
3. **Direction on Unresolved Decisions:** Do you prefer manual snapshot creation, automatic snapshot on backtest, or both?
