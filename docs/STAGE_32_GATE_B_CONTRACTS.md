# STAGE 32 — GATE B: CANONICAL MANIFEST ENGINE & RELATIONAL CONTRACTS SPECIFICATION
## Immutable Dataset Versioning, Research Snapshots & Point-in-Time Data Provenance

**Project:** Quantitative Portfolio Optimization Engine  
**Stage:** 32 — Gate B (Manifest Engine & Relational Contracts)  
**Session:** 55  
**Date:** October 21, 2026  
**Roles:** Principal Quantitative Finance Architect, Database Architect, Backend Engineer, QA Lead  
**Approved Strategy:** Hybrid Relational Manifest & Virtual Snapshot Architecture (Option C)  
**Approved Snapshot Mode:** Dual Mode — Manual Tagging (`manual`) + Automatic Snapshotting on Execution (`auto_backtest`, `auto_experiment`)  

---

## 1. Executive Summary & Objective

In Session 55 Gate A ([`docs/STAGE_32_GATE_A_BASELINE_AUDIT.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/STAGE_32_GATE_A_BASELINE_AUDIT.md)), the architectural baseline established the critical need to bridge Stage 31 point-in-time market data with reproducible research runs. The Project Owner formally authorized Gate B with **Option C (Dual Mode)**:
1. **Manual Snapshotting:** Researchers can explicitly freeze and tag a dataset (e.g. `tag="baseline_2024_q1"`, `description="Q1 2024 Investment Committee Review Universe"`).
2. **Automatic Lightweight Snapshotting:** Every backtest or research experiment execution automatically captures and seals an immutable dataset snapshot if one was not explicitly supplied, ensuring 100% regulatory-grade auditability.

Gate B delivers the formal specification and concrete implementation of:
* The **Canonical Observation Manifest Engine** (`backend/app/market_data/manifest.py`).
* The **Relational Snapshot Persistence Model** (`dataset_snapshots` table in `backend/app/db/models.py`).
* The **Reversible Alembic Migration Script** (`backend/alembic/versions/d3e4f5a6b7c8_create_dataset_snapshots_table.py`).
* Foreign key linkages connecting `backtest_runs` and `research_experiment_runs` to `dataset_snapshots.id`.
* Comprehensive unit tests proving determinism, permutation invariance, and mutation sensitivity (`backend/tests/test_dataset_manifest.py`).

---

## 2. Canonical Manifest Engine Specification (`manifest.py`)

### 2.1 The Need for Canonical Manifests
Raw CSV file hashing is fragile: non-semantic differences (CRLF vs LF, column reordering, trailing whitespace, or shuffled row ordering) produce divergent SHA-256 digests despite identical financial data. Furthermore, raw CSV hashing completely ignores corporate-action ledgers.

The Canonical Manifest Engine solves this by enforcing:
1. **Lexicographical Row Normalization:**
   Observations are sorted deterministically by primary keys:
   $$\text{Price Bars Ordering} \equiv (\text{ticker ASC}, \text{market ASC}, \text{date ASC})$$
   $$\text{Corporate Actions Ordering} \equiv (\text{effective\_date ASC}, \text{ticker ASC}, \text{event\_id ASC})$$
2. **Deterministic Numeric Representation:**
   - Prices (`open`, `high`, `low`, `close`, `adj_close`) are formatted to 6 fixed decimal places (e.g. `"150.250000"`, `null` for missing).
   - Volumes are formatted to 2 fixed decimal places.
   - Text fields are trimmed and converted to uppercase (`AAPL`, `US`, `USD`).
   - Dates are standardized to ISO-8601 strings (`YYYY-MM-DD`).

### 2.2 Hierarchical Composite Hashing (Merkle Digest)
The manifest produces a composite cryptographic identity:
1. **Price Bars Digest ($\text{Hash}_{\text{bars}}$):**
   $$\text{Hash}_{\text{bars}} = \text{SHA-256}\left(\sum_{i=1}^N \text{canonical\_bar\_string}_i\right)$$
2. **Corporate Actions Digest ($\text{Hash}_{\text{actions}}$):**
   $$\text{Hash}_{\text{actions}} = \text{SHA-256}\left(\sum_{j=1}^M \text{canonical\_action\_string}_j\right)$$
3. **Composite Manifest Digest ($\text{Manifest}_{\text{sha256}}$):**
   $$\text{Manifest}_{\text{sha256}} = \text{SHA-256}\left(\text{"DATASET\_MANIFEST:v1:"} \,||\, \text{dataset\_id} \,||\, \text{Hash}_{\text{bars}} \,||\, \text{Hash}_{\text{actions}} \,||\, \text{calendar\_version} \,||\, \text{adjustment\_policy\_version} \,||\, \text{as\_of\_date} \,||\, \text{pit\_status}\right)$$

### 2.3 Mathematical Invariants & Guarantees
* **Permutation Invariance:** If two CSV files contain identical price observations in different row orders, their $\text{Hash}_{\text{bars}}$ and $\text{Manifest}_{\text{sha256}}$ **must be identical**.
* **Mutation Sensitivity:** If a single price bar's close changes by $\$0.000001$, or an active corporate action's dividend changes by $\$0.01$, $\text{Manifest}_{\text{sha256}}$ **must change**.
* **Policy Sealing:** Changing the exchange calendar version (e.g. from `US-NYSE-2026.1` to `US-NYSE-2026.2`) or adjustment policy version updates $\text{Manifest}_{\text{sha256}}$, preserving full lineage across policy updates.

---

## 3. Relational Database Schema (`dataset_snapshots`)

### 3.1 `dataset_snapshots` Table Definition
```sql
CREATE TABLE dataset_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    dataset_id VARCHAR(36) NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    tag VARCHAR(100),
    description TEXT,
    snapshot_type VARCHAR(30) NOT NULL DEFAULT 'manual', -- 'manual', 'auto_backtest', 'auto_experiment'
    manifest_sha256 VARCHAR(64) NOT NULL,
    manifest_json TEXT NOT NULL,
    as_of_date DATE,
    point_in_time_status VARCHAR(50) NOT NULL DEFAULT 'unverified_legacy',
    calendar_version VARCHAR(50),
    adjustment_policy_version VARCHAR(50),
    is_frozen BOOLEAN NOT NULL DEFAULT TRUE,
    total_bars_count INTEGER NOT NULL DEFAULT 0,
    total_actions_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_dataset_snapshots_dataset_id ON dataset_snapshots(dataset_id);
CREATE INDEX ix_dataset_snapshots_user_id ON dataset_snapshots(user_id);
CREATE INDEX ix_dataset_snapshots_manifest_sha256 ON dataset_snapshots(manifest_sha256);
CREATE INDEX ix_dataset_snapshots_dataset_tag ON dataset_snapshots(dataset_id, tag);
CREATE INDEX ix_dataset_snapshots_created_at ON dataset_snapshots(created_at);
```

### 3.2 Foreign Key Upgrades to Research & Simulation Models
To achieve end-to-end auditability without breaking existing consumers, nullable `snapshot_id` foreign keys are added to:
1. **`backtest_runs` Table:**
   - Add column: `snapshot_id VARCHAR(36) REFERENCES dataset_snapshots(id) ON DELETE SET NULL`.
   - Add index: `ix_backtest_runs_snapshot_id`.
2. **`research_experiment_runs` Table:**
   - Add column: `snapshot_id VARCHAR(36) REFERENCES dataset_snapshots(id) ON DELETE SET NULL`.
   - Add index: `ix_research_experiment_runs_snapshot_id`.

### 3.3 Alembic Migration Ancestry
* **Migration ID:** `d3e4f5a6b7c8`
* **Revises:** `c1d2e3f4a5b6` (`create_corporate_actions_table_and_pit_columns`)
* **Down Revision:** Linear rollback restoring prior schema cleanly.

---

## 4. API & Pydantic Data Contracts

### 4.1 Manifest DTO Contracts
```python
class CanonicalAssetSummary(BaseModel):
    asset_id: str
    ticker: str
    market: str
    currency: str
    start_date: str
    end_date: str
    observation_count: int

class DatasetManifestData(BaseModel):
    manifest_version: str = "1.0"
    dataset_id: str
    as_of_date: str | None = None
    calendar_version: str | None = None
    adjustment_policy_version: str | None = None
    point_in_time_status: str = "unverified_legacy"
    bars_digest: str
    actions_digest: str
    manifest_sha256: str
    total_bars: int
    total_actions: int
    assets: dict[str, CanonicalAssetSummary]
    action_event_ids: list[str] = []

class DatasetSnapshotCreate(BaseModel):
    tag: str | None = Field(None, max_length=100, description="Optional human-readable tag, e.g. baseline_2024_q1")
    description: str | None = Field(None, max_length=500, description="Optional researcher notes")
    as_of_date: date | None = Field(None, description="Point-in-time decision cutoff date")

class DatasetSnapshotResponse(BaseModel):
    id: str
    dataset_id: str
    user_id: str | None = None
    tag: str | None = None
    description: str | None = None
    snapshot_type: str
    manifest_sha256: str
    as_of_date: str | None = None
    point_in_time_status: str
    calendar_version: str | None = None
    adjustment_policy_version: str | None = None
    is_frozen: bool
    total_bars_count: int
    total_actions_count: int
    created_at: str
    manifest: DatasetManifestData | None = None
```

---

## 5. Security, Tenant Isolation & Governance Rules

1. **Strict Tenant Ownership:**
   - Every snapshot inherits the creating user's `user_id`.
   - Queries for snapshots are strictly filtered by `(snapshot.user_id == current_user.id) OR (current_user.is_admin) OR (snapshot.is_shared)`.
   - Unauthorized attempts to view or freeze snapshots for another user's dataset raise HTTP 403/404.
2. **Immutability Enforcement:**
   - Once a snapshot is persisted, `is_frozen = True`.
   - Modification of `manifest_sha256`, `manifest_json`, or observation data for an existing snapshot is prohibited at the repository layer.
3. **Audit Trail Preservation:**
   - Deleting a base dataset cascades to its snapshots, but deleting a snapshot that is currently referenced by completed backtests or research runs sets `snapshot_id = NULL` (preserving run history without foreign-key violation).

---

## 6. Gate B Verification Criteria

Gate B can pass only when:
1. `backend/app/market_data/manifest.py` is implemented with complete canonicalization and Merkle hashing.
2. `backend/app/db/models.py` defines `DatasetSnapshotModel` and updates `BacktestRunModel` and `ResearchExperimentRunModel`.
3. Alembic migration `d3e4f5a6b7c8` applies cleanly and downgrades reversibly without schema corruption.
4. Dedicated unit test suite `backend/tests/test_dataset_manifest.py` verifies determinism, row-shuffling invariance, and mutation sensitivity.
5. Full backend regression test suite passes with 0 failures.
