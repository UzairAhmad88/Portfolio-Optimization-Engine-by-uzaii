# STAGE 32 — GATE C: IMMUTABLE SNAPSHOT CREATION, REPLAY SERVICE & DETERMINISTIC VERIFICATION
## Research Reproducibility, Anti-Tamper Replay Engine & Point-in-Time Data Provenance

**Project:** Quantitative Portfolio Optimization Engine  
**Stage:** 32 — Gate C (Snapshot Creation, Replay & Mathematical Verification)  
**Session:** 56  
**Date:** October 21, 2026  
**Roles:** Principal Quantitative Finance Architect, Data Architecture Lead, Database Engineer, QA Lead  
**Approved Strategy:** Strategy A — Immutable Materialized Snapshot Payload with Merkle Canonical Manifests  
**Manifest Schema Version:** `1.1` (8-Decimal Financial Precision, backward compatible with `1.0`)  
**Database Migration:** `e5f6a7b8c9d0_add_frozen_payload_to_snapshots.py`  

---

## 1. Executive Summary & Gate Objective

In Stage 32 Gate B ([`docs/STAGE_32_GATE_B_CONTRACTS.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/STAGE_32_GATE_B_CONTRACTS.md)), the project established canonical manifest generation, relational snapshot metadata schemas, and nullable foreign-key links on backtest and research run entities.

Gate C addresses the core architectural mandate:
> **Core Requirement:** Once a snapshot is created successfully, later changes to operational datasets (price updates, bar insertions, corrections), corporate-action revisions, or current adjustment policies must **not** silently change the data resolved by that snapshot. A manifest hash alone does not freeze data unless the underlying inputs are immutably retained or retrieved and integrity-verified.

In Gate C, we:
1. Formally evaluated **Strategy A** (Immutable Materialized Snapshot Payload) vs **Strategy B** (Versioned Relational References) and selected **Strategy A** because the underlying operational tables (`price_bars`, `corporate_actions`) are mutable.
2. Upgraded the manifest engine to **Schema Version `1.1`** with **8-decimal financial precision** (`0.00000001`), supporting sub-penny pricing and fractional corporate action adjustments, while retaining full backwards-compatibility with version `1.0`.
3. Created and applied additive migration `e5f6a7b8c9d0_add_frozen_payload_to_snapshots.py` adding `frozen_payload_json` to `dataset_snapshots`.
4. Implemented `create_dataset_snapshot(...)` in `backend/app/market_data/snapshot_service.py` with transactional consistency, PIT cutoff filtering, Merkle manifest calculation, and idempotent deduplication.
5. Implemented `resolve_snapshot_price_panel(...)` in `backend/app/market_data/snapshot_service.py` to reconstruct the exact frozen panel strictly from the immutable payload, cryptographically verifying the Merkle digest and failing closed without ever falling back to mutable operational tables.
6. Integrated snapshot lifecycle into `execute_backtest` (`backend/app/backtesting/service.py`) and `ResearchExperimentService` (`backend/app/research/service.py`), supporting both explicit `snapshot_id` and automatic execution snapshots (`auto_snapshot`).
7. Mathematically demonstrated that mutating operational tables (modifying closing prices, appending new bars, inserting new corporate actions) produces **zero drift ($0.00000000$)** on subsequent snapshot replays.

---

## 2. Design Decision & Architectural Justification

### 2.1 Strategy A vs Strategy B Comparison

| Dimension | Strategy A: Immutable Materialized Snapshot Payload | Strategy B: Versioned References + Content Verification |
| :--- | :--- | :--- |
| **Operational Table Mutability** | Fully insulated against updates, deletes, re-imports, or ledger corrections. | Vulnerable: operational tables have mutable records; changes invalidate old hashes or fail replays. |
| **Storage Footprint** | Materialized JSON payload per snapshot (~100 KB–2 MB depending on universe size). | Zero duplicate payload storage; only metadata stored. |
| **Immutability Guarantee** | **Guaranteed:** Payload is sealed at creation time; even deleting the operational dataset allows snapshot replay. | **Fragile:** If operational records are updated or pruned, replay fails or silently diverges. |
| **Verification Mechanism** | Full Merkle integrity check: `manifest_sha256` computed from payload must match stored digest. | Relational query filtered by cutoff; fails if underlying rows were modified. |
| **Retention & Pruning Policy** | Snapshot payload is retained until explicit lifecycle retention expiration. | Coupled to operational table lifetime. |

### 2.2 Selected Architecture: Strategy A

Because PostgreSQL operational tables (`price_bars`, `corporate_actions`) in this platform permit operational data ingestion, correction of bad ticks, and ledger revisions, **Strategy A** is the only safe strategy that guarantees immutable research reproducibility. 

The snapshot payload is stored in the `frozen_payload_json` column of `dataset_snapshots`. The payload contains:
```json
{
  "dataset_id": "...",
  "as_of_date": "2024-01-31",
  "calendar_version": "US-NYSE-2026.1",
  "adjustment_policy_version": "CRSP-SPLIT-DIVIDEND-v1.0",
  "pit_status": "POINT_IN_TIME_CERTIFIED",
  "bars": [
    {"ticker": "AAPL", "market": "US", "date": "2024-01-15", "open": 185.50, "high": 186.20, "low": 184.80, "close": 185.92, "adj_close": null, "volume": 54000000.0, "currency": "USD"}
  ],
  "corporate_actions": [
    {"event_id": "...", "ticker": "AAPL", "action_type": "cash_dividend", "effective_date": "2024-01-19", ...}
  ]
}
```

---

## 3. Manifest Canonicalization Contract (Schema Version 1.1)

### 3.1 Financial Precision Strengthening
Gate B utilized 6-decimal float formatting (`{val:.6f}`). In Gate C, quantitative review determined that sub-penny equity quotes (Rule 612 under SEC Regulation NMS allows $\$0.0001$ increments for quotes under $\$1.00$) and high-precision split ratios (e.g. Berkshire Hathaway conversions or reverse splits) require at least 8 decimal places.

In `backend/app/market_data/manifest.py`:
- Schema version upgraded to `DEFAULT_MANIFEST_VERSION = "1.1"`.
- Price fields (`open`, `high`, `low`, `close`, `adj_close`) are formatted to 8 decimals:
  $$\text{format\_float}(v) \equiv f"{v:.8f}"$$
- Volume formatted to 2 decimals.
- Missing values formatted as `"null"`.
- Row-ordering invariants:
  - Price bars sorted by `(ticker ASC, market ASC, date ASC)`.
  - Corporate actions sorted by `(effective_date ASC, ticker ASC, event_id ASC)`.
- Backwards compatibility: manifests generated under version `1.0` (using `"DATASET_MANIFEST:v1:"` prefix) remain valid and parseable by the deserializer and verifier.

### 3.2 Merkle Composite Digest
The composite cryptographic digest is computed as:
$$\text{composite\_input} = \text{"DATASET\_MANIFEST:v1.1:"} \,||\, \text{dataset\_id} \,||\, \text{Hash}_{\text{bars}} \,||\, \text{Hash}_{\text{actions}} \,||\, \text{calendar\_version} \,||\, \text{adjustment\_policy\_version} \,||\, \text{as\_of\_date} \,||\, \text{pit\_status}$$
$$\text{manifest\_sha256} = \text{SHA-256}(\text{composite\_input})$$

---

## 4. Snapshot Services Implementation

### 4.1 Snapshot Creation Service (`create_dataset_snapshot`)
Implemented in `backend/app/market_data/snapshot_service.py`:
- **Dataset Authorization:** Validates that the requesting user owns the dataset.
- **Point-in-Time Cutoff:**
  - `price_bars` filtered by `bar.date <= as_of_date`.
  - `corporate_actions` filtered strictly by `ca.effective_date <= as_of_date` and `ca.announcement_date <= as_of_date` (strict anti-leakage).
- **Provenance Sealing:** If any corporate action has an unverified announcement date, `pit_status` is sealed as `LEGACY_UNVERIFIED`. If fully PIT compliant, sealed as `POINT_IN_TIME_CERTIFIED`.
- **Merkle Manifest Generation:** Calls `generate_dataset_manifest(...)` to produce `DatasetManifest`.
- **Idempotency:** Queries existing snapshots for `(dataset_id, manifest_sha256)`. If an exact identical snapshot exists, returns the existing record rather than duplicating storage.
- **Transactional Persistence:** Writes `DatasetSnapshotModel` with `frozen_payload_json` and commits atomically.

### 4.2 Snapshot Replay Service (`resolve_snapshot_price_panel`)
Reconstructs the frozen input panel with zero operational table lookups:
1. **Fetch & Deserialize:** Loads `DatasetSnapshotModel`. Raises `SnapshotNotFoundError` if absent.
2. **Fail-Closed on Missing Payload:** If `frozen_payload_json` is null, raises `SnapshotIntegrityError("Snapshot has no frozen payload; mutable table fallback prohibited")`.
3. **Cryptographic Verification:** Recomputes the Merkle manifest and verifies:
   $$\text{recomputed\_manifest\_sha256} == \text{snapshot.manifest\_sha256}$$
   $$\text{recomputed\_bars\_sha256} == \text{snapshot.bars\_sha256}$$
   $$\text{recomputed\_actions\_sha256} == \text{snapshot.actions\_sha256}$$
   If any digest fails to match, raises `SnapshotIntegrityError`.
4. **Currency Homogeneity Check:** Validates that all assets in the universe share a single currency (or raises `ValueError`).
5. **Corporate Action Adjustment:** Applies `adjust_ohlcv_series` using the frozen corporate actions and the recorded adjustment policy (e.g. `split_dividend`).
6. **Return Type Resolution:** Returns `total_return` or `price_return` according to `return_type` specification.
7. **Provenance Attachment:** Returns `(prices_df, provenance_dict)` providing cryptographic verification details to the caller.

---

## 5. Backtest & Research Engine Integration

### 5.1 Backtesting Engine Integration
In `backend/app/backtesting/service.py`:
- `BacktestRequest` supports:
  - `snapshot_id: Optional[str]`: Explicit replay of an immutable snapshot.
  - `auto_snapshot: bool = False`: Automatic capture and sealing of a snapshot prior to calculation.
- When `snapshot_id` or `auto_snapshot` is present, `execute_backtest` resolves prices via `resolve_snapshot_price_panel(...)`.
- Atomically records `backtest_record.snapshot_id = snapshot.id`.
- Returns `snapshot_id` and `snapshot_provenance` in `BacktestResponse`.
- Preserves 100% backwards compatibility for legacy runs where `snapshot_id is None`.

### 5.2 Research Engine Integration
In `backend/app/research/service.py`:
- `execute_experiment_run` propagates snapshot configuration to the underlying backtest execution.
- Automatically links `run_record.snapshot_id = snapshot_id`.
- Added `check_run_reproducibility(experiment_id, run_id, db)`:
  - Verifies whether the run is linked to an immutable snapshot.
  - Verifies cryptographic integrity of the frozen payload.
  - Labels runs without snapshots as `REPRODUCIBILITY_UNVERIFIED` and snapshotted runs as `REPRODUCIBLE_FROZEN`.

---

## 6. Migration Safety & Persistence

### 6.1 Migration `e5f6a7b8c9d0`
- **File:** `backend/alembic/versions/e5f6a7b8c9d0_add_frozen_payload_to_snapshots.py`
- **Parent:** `d3e4f5a6b7c8` (Gate B snapshot table creation).
- **Operation:** Additive column `frozen_payload_json = Column(Text, nullable=True)`.
- **Reversibility:** Fully reversible via `op.drop_column('dataset_snapshots', 'frozen_payload_json')`.
- **Safety:** Zero table drops, zero destructive alterations; legacy rows retain `NULL` payload.

---

## 7. Deterministic Verification & Immutability Evidence

### 7.1 Focused Gate C Suite (`backend/tests/test_dataset_snapshot_replay.py`)
12 targeted deterministic tests were authored and executed:

| Test Case | Description | Result |
| :--- | :--- | :--- |
| `test_manifest_financial_precision_and_sub_penny_sensitivity` | Verifies $0.00000001 sensitivity and v1.1 composite digest. | **PASSED** |
| `test_snapshot_creation_success` | Validates transaction, Merkle digest calculation, and payload serialization. | **PASSED** |
| `test_snapshot_creation_unauthorized_fails` | Rejects unauthorized cross-tenant snapshot creation with HTTP 403. | **PASSED** |
| `test_snapshot_creation_retries_idempotent` | Re-executing snapshot creation returns existing record with no state duplication. | **PASSED** |
| `test_snapshot_replay_success` | Replays frozen panel with 100% precision match against initial baseline. | **PASSED** |
| `test_immutability_under_operational_dataset_mutation` | **Mathematical Immutability:** Mutates operational prices (+50%), adds new price bars, and inserts new corporate actions. Proves replayed prices have **0.0 drift**. | **PASSED** |
| `test_corrupted_frozen_payload_fails_closed` | Tampering with a single character in `frozen_payload_json` raises `SnapshotIntegrityError`. | **PASSED** |
| `test_missing_frozen_payload_fails_closed_no_fallback` | Missing payload fails closed without falling back to operational table. | **PASSED** |
| `test_backtest_with_explicit_snapshot_id` | Backtest executes using explicit snapshot, records `snapshot_id`, and returns provenance. | **PASSED** |
| `test_backtest_auto_snapshot` | Automatic snapshot created prior to calculation and linked to backtest. | **PASSED** |
| `test_research_experiment_run_with_snapshot_linkage` | Research run links to snapshot; `check_run_reproducibility` reports verified. | **PASSED** |
| `test_snapshot_api_lifecycle` | Validates REST endpoints: create, list, get, and cryptographic verify. | **PASSED** |

### 7.2 Regression Verification Summary
- **Stage 32 Focused Suite:** 55 passed in 22.16s (`test_dataset_manifest.py`, `test_dataset_snapshot_replay.py`, `test_corporate_actions.py`, `test_pit_backtest_integration.py`, `test_point_in_time_leakage.py`, `test_backtesting_api.py`, `test_research_api.py`).
- **Full Backend Regression:** 530+ tests executed with 0 failures.
- **Frontend Verification:** 43 Vitest tests passed; production build clean.

---

## 8. Gate C Exit Verdict

**VERDICT: PASS**

The repository now possesses:
1. True immutability under operational table mutations.
2. 8-decimal precision financial manifest generation.
3. Cryptographic Merkle anti-tampering verification.
4. Seamless integration with backtesting and research workflows.
5. Strict fail-closed semantics with zero silent fallback to mutable tables.

Proceed to project owner review. Gate D (Auditing & User Verification UX) authorized upon owner sign-off.
