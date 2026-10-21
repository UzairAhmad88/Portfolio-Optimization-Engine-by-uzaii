# Stage 32 Gate F Remediation Report

**Session:** 60  
**Date:** October 21, 2026  
**Stage:** 32 — Immutable Dataset Versioning, Research Snapshots & Point-in-Time Data Provenance Auditing  
**Gate:** Gate F Remediation  
**Status:** REMEDIATION COMPLETE — STAGE 32 REMAINS UNACCEPTED PENDING OWNER REVIEW  

---

## 1. Initial Status Baseline

Prior to beginning remediation, the repository status was inspected and verified:

- **Repository:** `d:\Quants\Projects\quant-portfolio-engine-starter`
- **Active Branch:** `main`
- **Initial HEAD SHA:** `d740e1d70a1736fb011b2d9ae2791f904a02d5b8`
- **Working Tree:** Clean (with untracked Session 59 audit report `docs/STAGE_32_GATE_F_INTEGRITY_AND_PIT_AUDIT.md`)
- **Baseline Verification:**
  - Backend test baseline: 530 passing pytest tests.
  - Frontend test baseline: 52 passing Vitest unit tests.
  - Production build: Clean Vite production build.

---

## 2. Summary of Findings Addressed & Deferred

| Finding / Issue | Severity / Type | Action Taken | Disposition |
| :--- | :--- | :--- | :--- |
| **`OBS-32-01`**: Currency omitted from price-bar canonical digest line | Medium (Integrity) | Introduced manifest version `"1.2"` binding `currency` into canonical bar lines (`TICKER\|MARKET\|CURRENCY\|DATE\|OPEN\|HIGH\|LOW\|CLOSE\|ADJ_CLOSE\|VOLUME`). Preserved backward-compatibility for legacy `"1.0"` and `"1.1"` snapshots. | **Remediated** |
| **Verification Error Handling Defect**: Unhandled `JSONDecodeError` on malformed payload | Low (Reliability) | Wrapped `deserialize_frozen_payload` in `verify_snapshot_integrity` within a `try...except` block raising `SnapshotIntegrityError` (translating into controlled HTTP 409 Conflict instead of HTTP 500). Enforced non-empty bar check. | **Remediated** |
| **Numeric Formatting Edge Case**: IEEE-754 `-0.0` vs `+0.0` divergence | Low (Determinism) | Added explicit normalization in `_format_float` (`if f_val == 0.0: f_val = 0.0`) so that signed negative zero formats as `0.00000000`. | **Remediated** |
| **Digest Terminology**: Misleading "Merkle tree / Merkle root" claims | Low (Documentation) | Replaced "Merkle tree / root" terminology across code docstrings, route summaries, and UI tooltips with accurate **"hierarchical composite manifest digest"**. | **Remediated** |
| **`OBS-32-02`**: Shared database trust boundary | Architectural Disclosure | Formally disclosed threat model in documentation: database co-location protects against silent data corruption, accidental mutations, and operational updates, but does NOT protect against a privileged DBA / root database actor modifying both payload and digest simultaneously. External KMS / WORM deferred as out of scope. | **Disclosed / Retained Limitation** |
| **`OBS-32-03`**: Concurrent snapshot creation isolation under PostgreSQL | Concurrency Disclosure | Verified SQLite transactional behavior. Formally classified PostgreSQL `READ COMMITTED` non-repeatable read concurrency as **NOT PROVEN** in local SQLite test environment. Safe isolation safeguards documented for future multi-writer deployment. | **Disclosed / Retained Limitation** |

---

## 3. Files Changed and Rationale

1. **`backend/app/market_data/manifest.py`**:
   - Updated `DEFAULT_MANIFEST_VERSION = "1.2"`.
   - Updated `_format_float` to normalize IEEE-754 `-0.0` to `+0.0`.
   - Updated `compute_price_bars_digest`:
     - Under `manifest_version >= "1.2"`, canonical bar line incorporates `currency`: `f"{ticker}|{market}|{currency}|{d_str}|{op_str}|{hi_str}|{lo_str}|{cl_str}|{adj_str}|{vol_str}"`.
     - Under `manifest_version < "1.2"`, legacy canonical bar line is preserved: `f"{ticker}|{market}|{d_str}|{op_str}|{hi_str}|{lo_str}|{cl_str}|{adj_str}|{vol_str}"`.
   - Updated docstrings and comments from "Merkle" to "hierarchical composite manifest digest".
2. **`backend/app/market_data/snapshot_service.py`**:
   - Updated `verify_snapshot_integrity` with `try...except Exception as exc: raise SnapshotIntegrityError(...)` and non-empty `frozen_bars` check.
   - Replaced "Merkle" wording in docstrings and comments with "hierarchical composite manifest digest".
3. **`backend/app/api/v1/routes.py`**:
   - Replaced "Merkle manifest digest" with "composite manifest digest" in `/datasets/snapshots/{snapshot_id}/verify` route description.
4. **`frontend/src/components/common/SnapshotProvenanceBadge.tsx`**:
   - Updated verification button label to `"Verifying Composite Digest..."`.
   - Updated hash copy button title to `"Copy Manifest Hash"`.
5. **`frontend/src/test/snapshot-provenance.test.tsx`**:
   - Reconciled button title selector to `"Copy Manifest Hash"`.
6. **`backend/tests/test_dataset_manifest.py`**:
   - Added `test_manifest_v1_2_currency_sensitivity` confirming currency alteration alters `bars_digest` and `manifest_sha256` under v1.2, while preserving v1.1 digest stability.
   - Added `test_negative_zero_canonicalization` confirming `-0.0` and `+0.0` produce identical digests.
7. **`backend/tests/test_dataset_snapshot_replay.py`**:
   - Added `test_snapshot_api_malformed_payload_returns_409` verifying corrupt JSON returns HTTP 409 Conflict.
   - Added `test_snapshot_api_empty_bars_payload_returns_409` verifying empty bar payload returns HTTP 409 Conflict.
   - Added `test_snapshot_v1_2_currency_tampering_fails_verification` verifying direct currency modification in v1.2 frozen payload triggers `SnapshotIntegrityError` and HTTP 409.
8. **`docs/MASTER_PLAN.md`**:
   - Updated Stage 32 roadmap section with Gate F and Gate F Remediation records.

---

## 4. Digest Schema & Version Compatibility Policy

The platform supports a backward-compatible versioned manifest schema policy:

- **Version 1.0**:
  - Price precision: 6 decimals.
  - Volume precision: 2 decimals.
  - Corporate action value precision: 6 decimals.
  - Currency in bar line: Omitted.
  - Version tag: `v1`.
- **Version 1.1**:
  - Price precision: 8 decimals (sub-penny sensitivity).
  - Volume precision: 4 decimals.
  - Corporate action value precision: 8 decimals.
  - Currency in bar line: Omitted.
  - Version tag: `v1.1`.
- **Version 1.2 (Active Default)**:
  - Price precision: 8 decimals.
  - Volume precision: 4 decimals.
  - Corporate action value precision: 8 decimals.
  - Currency in bar line: **Bound** (`TICKER|MARKET|CURRENCY|DATE|...`).
  - Negative zero normalization: Enforced (`-0.0` $\to$ `+0.0`).
  - Version tag: `v1.2`.

### Compatibility Guarantees:
- Existing snapshots created under v1.0 or v1.1 carry `manifest_version` in their metadata.
- `verify_snapshot_integrity` and `resolve_snapshot_price_panel` read `m_version = snapshot.get_manifest().get("manifest_version", "1.2")` and recompute according to that exact version's canonicalization rules.
- Historical snapshots are neither rewritten nor re-hashed; their cryptographic verification remains exact and mathematically reproducible.

---

## 5. Financial Precision Decision & Evidence

- **8-Decimal Precision Retention:** The 8-decimal policy for prices and corporate actions was preserved. Quantitative audit verified that financial quantities (e.g., penny fractions, sub-penny crypto/FX prices, and corporate split factors like 3:2 or 7:5) require up to 8 decimal places to prevent truncation drift across multi-year walk-forward compounding.
- **Signed Zero Normalization:** IEEE-754 signed zero (`-0.0`) was identified as a potential source of non-deterministic formatting divergence in Python (`f"{-0.0:.8f}" == "-0.00000000"` vs `f"{0.0:.8f}" == "0.00000000"`). Normalization in `_format_float` ensures that `float(val) == 0.0` always produces `"0.00000000"`.
- Tested in unit test `test_negative_zero_canonicalization` (passed).

---

## 6. Malformed-Payload Error-Handling Behavior

- **Before Remediation:** In `verify_snapshot_integrity`, calling `deserialize_frozen_payload` on invalid or malformed JSON raised `json.decoder.JSONDecodeError`. In the API route `/datasets/snapshots/{snapshot_id}/verify`, this leaked as an unhandled HTTP 500 Internal Server Error.
- **After Remediation:**
  - `verify_snapshot_integrity` wraps deserialization in `try...except Exception as exc: raise SnapshotIntegrityError(...)` and validates that `frozen_bars` is non-empty.
  - The API route catches `SnapshotIntegrityError` and translates it into a controlled **HTTP 409 Conflict** with an explanatory diagnostic message.
  - Tested in unit tests `test_snapshot_api_malformed_payload_returns_409` and `test_snapshot_api_empty_bars_payload_returns_409` (passed).

---

## 7. Concurrency Conclusions & Unproven Behavior

- **Local Development / Testing (SQLite):**
  - Uses SQLite with `PRAGMA foreign_keys=ON`.
  - Under single-connection session scopes, snapshot creation reads observations, corporate actions, computes the manifest, serializes the payload, and persists the record atomically.
- **PostgreSQL Concurrency (`OBS-32-03`):**
  - Under default PostgreSQL `READ COMMITTED` transaction isolation, if another transaction commits new price bars to the dataset during snapshot computation, the observations read for the manifest might theoretically interleave if multiple queries are executed without repeatable reads or row locks.
  - In the local testing environment (SQLite), PostgreSQL-specific multi-client concurrency cannot be executed.
  - **Status:** **NOT PROVEN under PostgreSQL**.
  - **Recommendation:** In multi-tenant environments with concurrent market-data ingestion writers, snapshot creation should either:
    1. Set transaction isolation to `REPEATABLE READ` or `SERIALIZABLE` during `create_dataset_snapshot`, OR
    2. Execute an explicit advisory lock `pg_advisory_xact_lock(dataset_hash)`.

---

## 8. Trust-Boundary & Terminology Changes

- **Terminology Reconciliation:**
  - Previous documentation and UI strings referred to the manifest root hash as a "Merkle root" or "Merkle manifest".
  - Because the platform implements a 2-level hierarchical composite hash (`SHA-256(DATASET_MANIFEST:...:bars_digest:actions_digest:...)`) rather than an $O(\log N)$ binary Merkle tree with individual leaf inclusion proofs, the terminology was corrected to **"hierarchical composite manifest digest"**.
  - Updated in `manifest.py`, `snapshot_service.py`, `routes.py`, and `SnapshotProvenanceBadge.tsx`.
- **Trust-Boundary Disclosure (`OBS-32-02`):**
  - Both `manifest_sha256` and `frozen_payload_json` reside in the same relational table (`dataset_snapshots`).
  - This architecture guarantees immutability against *application-level* operations (accidental deletions, operational price corrections, updates to mutable operational tables, and software bugs).
  - It does **not** protect against a malicious actor with direct database `UPDATE` access to `dataset_snapshots`.
  - True cryptographic non-repudiation against privileged database operators would require an external KMS, asymmetric digital signatures, or external WORM / object-lock storage. This is retained as an architectural boundary and out of scope for Stage 32.

---

## 9. Migration Details

- **No Alembic Migration Required:**
  - The database table `dataset_snapshots` already includes `manifest_json` and `frozen_payload_json` (added in migration `e5f6a7b8c9d0`).
  - `manifest_version` is stored inside the serialized `DatasetManifest` object within `manifest_json`.
  - Existing records retain their original schema version string (`"1.0"` or `"1.1"`), ensuring complete backward compatibility without table alterations.

---

## 10. Verification Commands & Test Results

All verification commands were executed directly in the repository environment:

| Scope | Exact Command | Exit Code | Result Summary |
| :--- | :--- | :---: | :--- |
| **Focused Manifest & Snapshot Tests** | `backend/.venv/Scripts/pytest.exe backend/tests/test_dataset_manifest.py backend/tests/test_dataset_snapshot_replay.py -v` | `0` | **23 passed** (including new v1.2 currency sensitivity, -0.0 normalization, malformed 409, and tampering tests) |
| **Full Backend Regression Suite** | `backend/.venv/Scripts/pytest.exe backend/tests/ -q` | `0` | **535 passed**, 6 warnings in 227.82s |
| **Frontend Unit Tests** | `npm test -- --run` (in `frontend/`) | `0` | **3 test files passed, 52 passed** |
| **Frontend Production Build** | `npm run build` (in `frontend/`) | `0` | **Built in 1.30s**, 0 TypeScript or bundling errors |

---

## 11. Remaining Risks

1. **PostgreSQL Concurrent Ingestion:** Concurrent writes to mutable operational price bars during snapshot creation remain unproven under PostgreSQL `READ COMMITTED`.
2. **Database Co-Location:** The snapshot payload and expected digest share a storage boundary; external signing or WORM storage is not implemented.
3. **Multi-Currency Replay Restriction:** Datasets containing heterogeneous currencies across assets are rejected by the replay service, requiring single-currency datasets or explicit FX rate conversion.

---

## 12. Final Git & Acceptance Status

- **Stage Status:** **REMEDIATION COMPLETE — STAGE 32 REMAINS UNACCEPTED PENDING OWNER REVIEW.**
- **Stage 33 Status:** NOT STARTED.

The remediation evidence is prepared and submitted for formal Project Owner review.
