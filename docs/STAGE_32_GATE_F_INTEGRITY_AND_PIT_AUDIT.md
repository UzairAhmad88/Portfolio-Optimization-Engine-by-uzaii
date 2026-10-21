# STAGE 32 — GATE F: SNAPSHOT INTEGRITY, FINANCIAL PRECISION, PIT CONSISTENCY & VERIFICATION-CLAIM AUDIT
## Independent Technical Audit Report & Owner Acceptance Assessment

**Project:** Quantitative Portfolio Optimization Engine  
**Repository:** `UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Expected Branch:** `main`  
**Actual Checked-Out Branch:** `main`  
**Audited Commit:** `d740e1d70a1736fb011b2d9ae2791f904a02d5b8`  
**Parent Commit:** `c2df0d17d615b11f0682d1c5a592020f2ac7173a`  
**Date:** October 21, 2026  
**Roles:** Principal Quantitative Finance Engineer, Senior Backend Auditor, Data Integrity Specialist, Application Security Reviewer, Independent QA Lead  
**Audit Mode:** Strictly Read-Only (0 application or test files modified)  
**Overall Verdict:** `CONDITIONAL PASS — READY FOR FINAL OWNER ACCEPTANCE REVIEW`

---

## 1. Executive Summary & Verdict

This report presents the independent, read-only technical audit of **Stage 32 (Immutable Dataset Versioning, Research Snapshots & Point-in-Time Data Provenance Auditing)** across Gates A through E.

The audit verified the following core technical capabilities:
1. **Mathematical Immutability:** Replayed price panels exhibit exact $0.00000000$ drift when operational database tables are subjected to corruptive price updates, row additions, and unverified corporate action insertions (`test_immutability_under_operational_dataset_mutation`).
2. **Deterministic Replay:** Synchronized price matrices and corporate action adjustments are reconstructed purely from `frozen_payload_json` with complete decoupling from operational tables.
3. **Point-in-Time Anti-Leakage:** Corporate actions announced after the historical `as_of_date` cutoff are strictly excluded in strict PIT mode (`test_point_in_time_leakage.py`).
4. **Relational Traceability:** Backtests and research experiment runs atomically bind `snapshot_id` and provenance metadata into relational storage.
5. **Institutional UX:** The frontend delivers dedicated verification badges (`SnapshotProvenanceBadge.tsx`), copyable 64-character SHA-256 digests, and live on-demand browser integrity verification.

### Audit Verdict: `CONDITIONAL PASS`
The platform's snapshotting, replay, and anti-leakage engines meet their documented functional contracts. A **CONDITIONAL PASS** is recommended because four material architectural limitations require explicit Project Owner acknowledgement before formal acceptance:
1. **`OBS-32-01` (Currency in Price Bar Hashing):** Price bar currency is not cryptographically bound into `bars_digest` or `manifest_sha256`. Mutating the currency string inside `frozen_payload_json` does not trigger a digest mismatch.
2. **`OBS-32-02` (Co-located Storage Trust Boundary):** `frozen_payload_json` and `manifest_sha256` reside in the same relational table (`dataset_snapshots`). A privileged actor with direct database write permissions can update both simultaneously to bypass verification.
3. **`OBS-32-03` (Concurrency Isolation):** Snapshot creation executes sequential SELECT queries without explicit `REPEATABLE READ` transaction isolation, leaving concurrent ingestion consistency unproven under high-concurrency workloads.
4. **Digest Terminology Precision:** The hashing mechanism is a 2-level hierarchical composite hash (streaming bars SHA-256 + streaming actions SHA-256 + metadata digest), not a binary Merkle tree with logarithmic inclusion proofs.

---

## 2. Baseline & Evidence Matrix

### 2.1 Repository Baseline
| Audit Baseline Item | Command / Source | Verified State | Match Expected? |
| :--- | :--- | :--- | :--- |
| **Repository Root** | `Get-Location` | `D:\Quants\Projects\quant-portfolio-engine-starter` | YES |
| **Git Branch** | `git status` | `main` (synchronized with `origin/main`) | YES |
| **HEAD Commit** | `git log -n 1 --format="%H"` | `d740e1d70a1736fb011b2d9ae2791f904a02d5b8` | YES (`d740e1d`) |
| **Parent Commit** | `git log -n 1 --format="%P"` | `c2df0d17d615b11f0682d1c5a592020f2ac7173a` | YES (`c2df0d1`) |
| **Commit Author** | `git log -n 1 --format="%an <%ae>"` | `UzairAhmad88 <imuzairahamd8@gmail.com>` | YES |
| **Working Tree** | `git status` | Clean (0 modified, 0 staged, untracked test scratch files cleaned) | YES |
| **Database Migration Head**| `.venv/Scripts/alembic.exe heads` | `e5f6a7b8c9d0 (head)` | YES |
| **Master Plan Status** | `docs/MASTER_PLAN.md` (lines 204–211) | Stage 32 Gates A through E complete; Pending Owner Acceptance | YES |

---

## 3. Audit B — Digest and Canonicalization Correctness

### 3.1 Trace of Hashed Fields

#### 1. Price Observations (`compute_price_bars_digest` in `manifest.py`)
- **Canonical Line Format:** `f"{ticker}|{market}|{d_str}|{op_str}|{hi_str}|{lo_str}|{cl_str}|{adj_str}|{vol_str}"`
- **Fields Hashed:** `ticker`, `market`, `date`, `open`, `high`, `low`, `close`, `adj_close` (or `adjusted_close`), `volume`.
- **Fields Omitted from Line:** `currency`, `asset_id`, `dataset_id`, row primary key.
- **Precision:** 8 decimal places for price (`f"{float(val):.8f}"`), 4 decimal places for volume (`f"{float(val):.4f}"`) under manifest version `1.1`.
- **Ordering:** Deterministically sorted by `(ticker ASC, market ASC, date ASC)`. Permutation-invariant.
- **Digest Computation:** Streaming SHA-256 over newline-delimited canonical lines.

#### 2. Corporate Actions (`compute_corporate_actions_digest` in `manifest.py`)
- **Canonical Line Format:** `f"{eff_d}|{t}|{m}|{ev_id}|{ev_type}|{ann_d}|{v_str}|{curr}|{st}|{rev}"`
- **Fields Hashed:** `effective_date`, `ticker`, `market`, `event_id`, `event_type`, `announcement_date`, `value`, `currency`, `status`, `revision_id`.
- **Precision:** 8 decimal places for `value` under manifest version `1.1`.
- **Ordering:** Deterministically sorted by `(effective_date ASC, ticker ASC, event_id ASC)`.
- **Digest Computation:** Streaming SHA-256 over newline-delimited canonical lines.

#### 3. Composite Manifest Digest (`build_dataset_manifest` in `manifest.py`)
- **Composite Payload:**
  ```python
  composite_payload = (
      f"DATASET_MANIFEST:{version_tag}:{dataset_id}:{bars_digest}:{actions_digest}:"
      f"{cal_v}:{adj_v}:{as_of_str}:{pit_st}"
  )
  manifest_sha256 = hashlib.sha256(composite_payload.encode("utf-8")).hexdigest()
  ```
- **Fields Hashed:** `version_tag`, `dataset_id`, `bars_digest`, `actions_digest`, `calendar_version`, `adjustment_policy_version`, `as_of_date`, `point_in_time_status`.
- **Fields Omitted:** `manifest.assets` dictionary (including asset-level `currency`).

### 3.2 Canonicalization Edge Cases Verified

| Test Case | Inputs Evaluated | Observed Result | Pass / Finding |
| :--- | :--- | :--- | :--- |
| **8th Decimal Sensitivity** | `close = 150.12345678` vs `150.12345679` | `d1 != d2` (`True`) | **PASS:** Sub-penny differences detected |
| **9th Decimal Truncation** | `close = 150.123456781` vs `150.123456789` | `d1 == d2` (`True`) | **PASS:** Controlled truncation at 8 decimal places |
| **Zero vs 1e-8 Price** | `close = 0.0` vs `close = 1e-8` | `d1 != d2` (`True`) | **PASS:** Distinguishes near-zero asset prices |
| **Null vs Missing Fields** | `open = None` vs omitted `open` key | `d1 == d2` (`True`) | **PASS:** Normalized to string `"null"` |
| **Permutation Invariance** | Shuffled records vs pre-sorted records | `d_shuffled == d_sorted` (`True`) | **PASS:** Lexicographical sorting guarantees determinism |
| **Duplicate Records** | 1 record vs 2 identical records | `d_single != d_dupe` (`count=2`) | **PASS:** Duplicate rows alter stream digest |
| **Negative Zero (-0.0)** | `close = 0.0` vs `close = -0.0` | `d1 != d2` (Yields `"-0.00000000"`) | **FINDING:** IEEE-754 `-0.0` formats with negative sign |
| **Currency Tampering in Bars** | `currency = "USD"` vs `currency = "PKR"` | `d_usd == d_pkr` (`True`), `m_usd == m_pkr` (`True`) | **FINDING (`OBS-32-01`):** Currency omitted from `bar_line` |
| **CA Currency Tampering** | `currency = "USD"` vs `currency = "EUR"` | `d_ca1 != d_ca2` (`True`) | **PASS:** CA currency is cryptographically bound |
| **CA Revision Tampering** | `revision_id = None` vs `revision_id = "rev_2"` | `d_ca1 != d_ca2` (`True`) | **PASS:** CA revision history is cryptographically bound |

---

## 4. Audit C — Integrity Verification and Trust Boundaries

The integrity verification engine was audited across seven specific failure modes using isolated scratch executions:

| # | Condition Tested | Mechanism / Code Path | Observed Result | Evaluation |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Untouched Snapshot** | `verify_snapshot_integrity(snap_id)` | Returns `True` | **PASS** |
| **2** | **Payload Tampered Without Digest** | Modify price in `frozen_payload_json` | Raises `SnapshotIntegrityError` | **PASS:** Fail-closed |
| **3** | **Sub-Component Digest Tampered** | Corrupt `bars_digest` in `manifest_json` | Raises `SnapshotIntegrityError` in replay | **PASS:** Sub-component validation catches mismatch |
| **4** | **Malformed / Truncated Payload** | `frozen_payload_json = "{"` | Replay raises `SnapshotIntegrityError` | **PASS in Replay** (See Finding 3 for verify route) |
| **5** | **Missing Payload (None)** | `frozen_payload_json = None` | Raises `SnapshotIntegrityError` | **PASS:** Explicitly rejects fallback to operational data |
| **6** | **Missing Snapshot Record** | `resolve_snapshot_price_panel("missing")` | Raises `SnapshotNotFoundError` | **PASS:** Fails closed |
| **7** | **Privileged DB Modification** | Attacker updates payload AND manifest digest | `verify_snapshot_integrity` returns `True` | **CONFIRMED LIMITATION (`OBS-32-02`):** Co-located storage |

### 4.1 Threat Model and Trust Boundary Analysis
- **Protection Scope:** Cryptographic hashing guarantees dataset immutability against application-level regressions, operational price updates, corporate action revisions, bad tick cleanups, and silent operational database drift.
- **Trust Boundary:** Because `frozen_payload_json` and `manifest_sha256` are stored in the same relational database row, the system **does not protect against an internal actor with direct database write access** who updates both the payload and the hash.
- **Recommendation:** Document this boundary clearly (implemented in Gate E). If non-repudiation against DBAs is required in the future, integrate external KMS HMAC or WORM object storage (e.g., AWS S3 Object Lock / GCP Bucket Lock).

---

## 5. Audit D — Point-in-Time Semantics and Concurrency Consistency

### 5.1 Point-in-Time Lifecycle & Anti-Leakage
The lifecycle distinguishes five temporal markers:
1. **Economic Effective Date (`effective_date`):** When the distribution or split economically took effect.
2. **Announcement Date (`announcement_date`):** When the event was gazetted or filed.
3. **Ingestion Timestamp (`created_at`):** When the row entered the database.
4. **Historical Cutoff (`as_of_date`):** The quantitative decision boundary.
5. **Snapshot Creation Timestamp:** When the dataset view was frozen.

Under `filter_point_in_time_actions` with `strict=True`:
- Events with `announcement_date > as_of_date` are strictly excluded (`excluded_future_actions_count > 0`), preventing look-ahead bias.
- Events lacking `announcement_date` fail closed with `PointInTimeStatus.FAILED_CLOSED` and cannot be certified PIT-safe.
- If multiple revisions exist for the same economic event, the engine selects the latest revision announced on or before the cutoff date.

### 5.2 Concurrency Analysis during Snapshot Creation (`OBS-32-03`)
In `create_dataset_snapshot` (`snapshot_service.py`):
```python
# Step 3:
bars_stmt = select(PriceBarModel).where(PriceBarModel.dataset_id == dataset_id)...
bars_models = list(session.scalars(bars_stmt).all())
# Step 4:
ca_stmt = select(CorporateActionModel)...
ca_models = list(session.scalars(ca_stmt).all())
```
- **Transaction Isolation:** The function accepts an external SQLAlchemy `session: Session` and executes two separate `SELECT` statements without explicit `REPEATABLE READ` or row-level locking.
- **Concurrency Verdict:** In PostgreSQL under default `READ COMMITTED`, if a concurrent transaction commits new observations between Step 3 and Step 4, the snapshot could record non-synchronized bars and actions.
- **Status:** **NOT PROVEN** to be race-free under concurrent writes. In current production operation, datasets are static once uploaded (`status: completed`), mitigating real-world risk.
- **Remediation Plan:** When concurrent streaming ingestion is implemented, wrap snapshot creation in an explicit `REPEATABLE READ` transaction:
  ```python
  session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
  ```

---

## 6. Audit E — Currency, Markets, and Dataset Completeness

### 6.1 Multi-Market Support
- The platform supports both US (`US-NYSE-2026.1`, 252 periods/year) and PSX (`PK-PSX-2026.1`, 250 periods/year) calendars.
- In `resolve_snapshot_price_panel`, line 370 deterministically resolves trading periods:
  ```python
  periods_per_year = 250 if "PSX" in markets else 252
  ```

### 6.2 Currency Homogeneity & Omission Findings
- **Replay Protection:** Line 365 of `snapshot_service.py` inspects all currencies in `frozen_bars` and explicitly enforces:
  ```python
  if len(currencies) > 1:
      raise SnapshotValidationError(f"Multi-currency observations detected in snapshot '{snapshot_id}': {sorted(currencies)}.")
  ```
- **Finding:** While multi-currency mixing within a snapshot is prevented at replay, changing the currency of all rows (e.g., from `USD` to `PKR`) in `frozen_payload_json` is not detected by `verify_snapshot_integrity` because currency is omitted from `bar_line` (Finding 1).

---

## 7. Audit F — Frontend Verification Labels and API Contracts

Inspection of `frontend/src/components/common/SnapshotProvenanceBadge.tsx` and related pages confirmed:

| UI Badge / Label | Trigger Condition | Backed by Cryptographic Proof? | Audit Assessment |
| :--- | :--- | :--- | :--- |
| **`Verified Frozen`** | `isFrozen === true` | YES (Replay exhibits $0.00000000$ drift) | **Accurate** (Tooltip discloses operational table decoupling) |
| **`Point-in-Time Certified`**| `point_in_time_status === 'verified_point_in_time'` | YES (`strict_pit=True` & announcement dates verified) | **Accurate** (Certification matches backend audit) |
| **`Legacy Unverified`** | `point_in_time_status === 'unverified_legacy'` | N/A (Clear warning) | **Accurate** (Warns researcher of uncertified look-ahead) |
| **`Operational Market Data`** | `snapshot_id === null` | N/A (Clear warning) | **Accurate** (Warns researcher that simulation is mutable) |
| **`Verify Integrity Now`** | Live button click | YES (Calls `/verify` which recomputes digest) | **Accurate** (Displays live backend result) |
| **"Verifying Merkle Root..."** | Loading spinner text | Partial (2-level composite hash, not binary Merkle tree) | **Terminology Minor Finding** |

---

## 8. Audit G — Test Evidence and Command Logs

The following test suites were executed independently during Session 59:

| Test Suite | Command Executed | Exit Code | Observed Output Summary |
| :--- | :--- | :---: | :--- |
| **Snapshot Replay Suite** | `pytest backend/tests/test_dataset_snapshot_replay.py -v` | `0` | **12 passed, 1 warning in 2.06s** |
| **Manifest Suite** | `pytest backend/tests/test_dataset_manifest.py -v` | `0` | **6 passed in 0.11s** |
| **Focused PIT & Snapshot**| `pytest backend/tests/test_dataset_snapshot_replay.py backend/tests/test_dataset_manifest.py backend/tests/test_pit_backtest_integration.py backend/tests/test_point_in_time_leakage.py backend/tests/test_corporate_actions.py backend/tests/test_corporate_actions_api.py -q` | `0` | **42 passed, 1 warning in 7.82s** |
| **Full Backend Regression**| `pytest backend/tests/ -q` | `0` | **530 passed, 6 warnings in 147.22s** |
| **Frontend Vitest Suite** | `npm test -- --run` (in `frontend/`) | `0` | **52 passed across 3 test files in 4.09s** |
| **Frontend Production Build**| `npm run build` (in `frontend/`) | `0` | **Vite build clean in 905ms** |

---

## 9. Comprehensive Findings & Classification

### Finding 1: Price Bar Currency Omission in Hashing (`OBS-32-01`)
- **Severity:** Medium (Confirmed Limitation)
- **Description:** `bar_line` in `manifest.py` line 123 omits `currency`. Modifying the currency in `frozen_payload_json` does not alter `manifest_sha256`.
- **Mitigating Factor:** Currency homogeneity is verified at replay (`len(currencies) > 1` raises `SnapshotValidationError`).
- **Remediation Recommendation:** In schema version 1.2, update `bar_line` to:  
  `f"{ticker}|{market}|{curr}|{d_str}|{op_str}|{hi_str}|{lo_str}|{cl_str}|{adj_str}|{vol_str}"`.

### Finding 2: Co-located Payload and Digest Storage (`OBS-32-02`)
- **Severity:** Medium (Threat Model Boundary)
- **Description:** `frozen_payload_json` and `manifest_sha256` are stored in the same relational row. A database administrator with direct SQL update permissions can alter both simultaneously to defeat verification.
- **Mitigating Factor:** The UI explicitly discloses: *"Confirms immutability against operational table mutations; does not constitute external regulatory notarization."*
- **Remediation Recommendation:** Maintain as a documented limitation for Stage 32. Evaluate external KMS HMAC signing in enterprise compliance stages.

### Finding 3: Deserialization Exception Handling Asymmetry
- **Severity:** Low (Defect)
- **Description:** `verify_snapshot_integrity` does not wrap `deserialize_frozen_payload` in a `try...except` block, whereas `resolve_snapshot_price_panel` does. If `frozen_payload_json` contains malformed JSON, `verify_snapshot_integrity` raises an unhandled `json.decoder.JSONDecodeError` resulting in HTTP 500 rather than `SnapshotIntegrityError` (HTTP 409).
- **Remediation Recommendation:** Add `try...except Exception as exc: raise SnapshotIntegrityError(...)` around `deserialize_frozen_payload` in `verify_snapshot_integrity`.

### Finding 4: Concurrency Isolation during Snapshot Creation (`OBS-32-03`)
- **Severity:** Low (Theoretical Concurrency Race)
- **Description:** `create_dataset_snapshot` runs across multiple SELECT queries without `REPEATABLE READ` transaction isolation.
- **Mitigating Factor:** Datasets are immutable and static once uploaded (`status: completed`).
- **Remediation Recommendation:** Add `REPEATABLE READ` execution options when real-time ingestion pipelines are added.

### Finding 5: Digest Structure Terminology
- **Severity:** Informational
- **Description:** The documentation and UI use "Merkle root" and "Merkle manifest" to describe a 2-level composite streaming digest.
- **Remediation Recommendation:** Relabel in documentation as "Composite Observation Digest" or "Hierarchical Manifest Hash".

---

## 10. Gate F Recommendation

### Overall Gate F Verdict: `CONDITIONAL PASS`

Stage 32 has achieved its primary quantitative mission:
- **Zero Drift Immutability:** Historical research and backtests are mathematically insulated from operational table mutations ($0.00000000$ drift).
- **Point-in-Time Anti-Leakage:** Corporate actions are certified against explicit announcement cutoffs.
- **Full Test Coverage:** 530 backend tests passing, 52 frontend tests passing, clean production build.
- **Honest Institutional UX:** Researchers are provided copyable hashes, live browser integrity checks, and transparent disclosures.

**Condition for Acceptance:** The Project Owner must review and explicitly accept the four documented architectural limitations (`OBS-32-01` through `OBS-32-03` and terminology precision) before formally signing off on Stage 32.
