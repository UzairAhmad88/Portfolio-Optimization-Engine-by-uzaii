# Session 16 Report: Portfolio Research Experiments, Strategy Comparison & Reproducible Research Runs

**Date:** 2026-10-18  
**Author:** Antigravity (Advanced Agentic AI Pair Programmer)  
**Status:** Complete & Fully Verified  
**Scope Boundaries Enforced:** Zero live trading or broker integration, zero new optimization algorithms, zero predictive models, zero automated parameter sweeps or grid searches, zero distributed job queues, zero unsupported FX conversions, zero universal strategy ranking scores, and zero synthetic benchmark data fabrication.

---

## 1. Executive Summary

Session 16 successfully elevated the Quant Portfolio Optimization Engine and Research Dashboard into a structured, reproducible **Portfolio Research Experiments & Strategy Comparison** platform. Prior to this session, the system provided sophisticated analytical engines—including mean-variance optimization, walk-forward backtesting, scenario shock analysis, Monte Carlo probabilistic risk modeling, and Menchero benchmark attribution—but each operated largely as an isolated, ad-hoc execution. 

Session 16 formalized the scientific research lifecycle:
1. **Decoupled Experiment Definitions from Execution Runs:** Formal separation between an experiment's immutable hypothesis/canonical configuration (`research_experiments` table) and its sequential, non-destructive execution runs (`research_experiment_runs` table). Re-executing an experiment produces a new sequential run ($1 \to 2 \to 3$) rather than overwriting historical results.
2. **Deterministic Canonical Fingerprinting:** SHA-256 fingerprint generation derived from recursive key sorting, 8-decimal float canonicalization (`f"{val:.8f}"`), and non-semantic field exclusion. Semantic modifications alter the fingerprint; whitespace, key ordering, and non-semantic labels preserve it.
3. **Cryptographic Provenance Verification:** Recording source dataset content SHA-256 hashes at configuration creation and verifying them against live dataset storage at execution time. Missing or modified datasets trigger explicit non-reproducible status flags and user-facing audit warnings.
4. **Cross-Strategy Multi-Run Comparison Engine:** Side-by-side evaluation across compatible completed runs, enforcing strict currency matching, period alignment, gross vs. net cost drag transparency, and explicit handling of unavailable metrics (no metric fabrication).
5. **Relational Persistence & Cascade Integrity:** Alembic migration `b2c3d4e5f6a7` adding `research_experiments` and `research_experiment_runs` tables with foreign keys and strict user-tenant isolation.
6. **Frontend Institutional Research Lab Workspace:** Integrated React 19 / TypeScript `ResearchLabPage` featuring an Experiment Library, Hypothesis Builder, Run History with provenance badges, and a Strategy Comparison matrix.
7. **Comprehensive Verification:** 17 new backend unit and security tests, 252/252 passing backend tests (100%), 19/19 passing frontend tests (100%), and 0-error production build.

---

## 2. Repository Audit & Baseline Findings

A rigorous pre-implementation audit was conducted and documented in `docs/SESSION_16_AUDIT.md`. Key findings included:
- **Reusable Domain Engines:** The existing services (`BacktestService`, `RiskSimulationService`, `PerformanceAttributionService`, and `OptimizationEngine`) are mathematically sound, pure Python/NumPy calculations that can be reused directly without code duplication.
- **Data Provenance Gaps:** Earlier backtests and scenarios recorded `dataset_id`, but did not assert whether the underlying dataset had been modified since creation. Session 16 introduced validation of `content_sha256` to detect data drift.
- **Tenant Isolation Standards:** User ownership (`user_id`) must be strictly enforced on all experiments and runs. Cross-tenant access, run execution on foreign datasets, or deleting other users' experiments must return HTTP 404/403.
- **Execution Model:** In-process synchronous execution wrapped in Starlette threadpools (`run_in_threadpool`) is sufficient and reliable for the current scale without requiring distributed task infrastructure (Celery/Redis).

---

## 3. Data Contracts & Fingerprinting Engine

Formal contracts were authored in `docs/RESEARCH_EXPERIMENT_CONTRACTS.md`.

### 3.1 Separation of Experiment Definition vs. Run Execution
- **Experiment Definition:** Captures the researcher's hypothesis, metadata, strategy modality (`target_weights`, `min_variance`, `max_sharpe`, `risk_simulation`, `benchmark_attribution`), dataset ID, and the canonical configuration dictionary.
- **Experiment Run:** Captures a single discrete execution, containing `run_number`, status (`pending`, `running`, `succeeded`, `failed`), execution timestamps, execution latency in milliseconds, configuration fingerprint, live dataset hash verification, reproducibility flags (`is_reproducible`, `audit_notes`), typed summary metrics, and references to underlying domain records (`backtest_id`, `risk_sim_id`, `report_id`).

### 3.2 Canonical Fingerprinting Engine (`backend/app/research/fingerprint.py`)
To ensure zero drift across operating systems and serialization formats:
- **Recursive Key Sorting:** All dictionary keys at all nesting levels are sorted lexicographically.
- **Numeric Standardization:** Floating-point numbers are rounded to 8 decimal places using `f"{val:.8f}"`.
- **Exclusion of Non-Semantic Fields:** Display labels, execution timestamps, run numbers, and user IDs are excluded from the fingerprint payload.
- **SHA-256 Digest:** The canonical JSON string (`separators=(",", ":")`) is hashed with SHA-256.

```python
# Semantic fields included in fingerprint:
{
    "strategy_type": "target_weights",
    "dataset_id": "ds_123",
    "dataset_content_sha256": "abcdef...",
    "assets": ["AAPL", "MSFT"],
    "asset_weights": {"AAPL": 0.50000000, "MSFT": 0.50000000},
    "rebalance_frequency": "monthly",
    "cost_bps": 10.00000000,
    "slippage_bps": 5.00000000,
    "random_seed": 42
}
```

---

## 4. Database Schema & Persistence

### 4.1 Alembic Migration
- **Revision ID:** `b2c3d4e5f6a7`
- **Revises:** `a1b2c3d4e5f6` (Session 15 Performance Reports)
- **Path:** `backend/alembic/versions/b2c3d4e5f6a7_create_research_experiments_tables.py`
- **Upgrade Command:** `alembic upgrade head` (verified clean application)
- **Rollback Command:** `alembic downgrade -1`

### 4.2 Tables Implemented
1. `research_experiments`:
   - `id` (VARCHAR(36), PK, UUIDv4)
   - `user_id` (VARCHAR(36), FK `users.id`, Indexed)
   - `dataset_id` (VARCHAR(36), FK `datasets.id`, Indexed)
   - `name` (VARCHAR(150), Non-null)
   - `description` (TEXT, Nullable)
   - `strategy_type` (VARCHAR(50), Non-null)
   - `configuration_json` (TEXT, Non-null)
   - `configuration_fingerprint` (VARCHAR(64), Non-null, Indexed)
   - `created_at` (TIMESTAMP, Non-null)
   - `updated_at` (TIMESTAMP, Non-null)

2. `research_experiment_runs`:
   - `id` (VARCHAR(36), PK, UUIDv4)
   - `experiment_id` (VARCHAR(36), FK `research_experiments.id` ON DELETE CASCADE, Indexed)
   - `user_id` (VARCHAR(36), FK `users.id`, Indexed)
   - `run_number` (INTEGER, Non-null, 1-based sequential per experiment)
   - `status` (VARCHAR(30), Non-null: `pending`, `running`, `succeeded`, `failed`)
   - `configuration_fingerprint` (VARCHAR(64), Non-null)
   - `dataset_content_sha256` (VARCHAR(64), Nullable)
   - `is_reproducible` (BOOLEAN, Non-null, default True)
   - `audit_notes` (TEXT, Nullable)
   - `started_at` (TIMESTAMP, Non-null)
   - `completed_at` (TIMESTAMP, Nullable)
   - `execution_duration_ms` (FLOAT, Nullable)
   - `error_message` (TEXT, Nullable, sanitized)
   - `backtest_id` (VARCHAR(36), FK `backtest_runs.id` ON DELETE SET NULL, Nullable)
   - `risk_simulation_id` (VARCHAR(36), FK `risk_simulation_runs.id` ON DELETE SET NULL, Nullable)
   - `performance_report_id` (VARCHAR(36), FK `performance_reports.id` ON DELETE SET NULL, Nullable)
   - `result_summary_json` (TEXT, Nullable)

---

## 5. Controlled Research Execution & Comparison Service

Implemented in `backend/app/research/service.py`:

### 5.1 Sequential Non-Destructive Execution
When a user triggers an experiment run (`POST /api/v1/research/experiments/{id}/runs`):
1. Loads the owned experiment and verifies the authenticated user owns it.
2. Resolves the linked dataset and verifies existence and access permissions.
3. Checks live dataset `content_sha256` against `expected_dataset_sha256`. If mismatched or missing, flags `is_reproducible = False` and attaches clear audit warnings.
4. Queries the maximum existing `run_number` for this experiment and assigns `next_run_number = max_run + 1`.
5. Creates the run record in `status="running"`.
6. Executes the corresponding domain service:
   - `target_weights`, `min_variance`, `max_sharpe`: executes `BacktestService.create_backtest`.
   - `risk_simulation`: executes `RiskSimulationService.create_simulation`.
   - `benchmark_attribution`: executes `PerformanceAttributionService.analyze_portfolio_performance`.
7. Formulates a typed `RunResultSummary` containing cumulative return, annualized return, volatility, max drawdown, Sharpe, Sortino, VaR, CVaR, tracking error, information ratio, turnover, and cost drag.
8. Persists the run in `status="succeeded"` with exact millisecond duration, or catches unexpected exceptions and records sanitized error diagnostics under `status="failed"`.

### 5.2 Multi-Run Strategy Comparison
Users select 2 or more completed runs for comparison (`POST /api/v1/research/comparisons`):
- **Currency Compatibility:** Verifies all compared runs operate in the same base currency. Mismatches return HTTP 422.
- **Evaluation Period Analysis:** Surfaces period start/end dates and observation bar counts across all runs.
- **Baseline Deltas:** Computes metric deltas ($\Delta \text{Cumulative Return}$, $\Delta \text{Annualized Volatility}$, $\Delta \text{Max Drawdown}$, $\Delta \text{Sharpe}$) relative to a user-selected or first-selected baseline run.
- **Metric Availability Transparency:** Only metrics supported by a run's underlying model are displayed; unsupported metrics return `None` rather than fabricated approximations.

---

## 6. REST API Endpoints

Mounted under `/api/v1/research` in `backend/app/api/v1/research_routes.py`:

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/research/experiments` | Create experiment definition & canonical fingerprint | Yes |
| `GET` | `/api/v1/research/experiments` | List authenticated user's experiments with last run status | Yes |
| `GET` | `/api/v1/research/experiments/{id}` | Retrieve experiment details and configuration | Yes |
| `PATCH` | `/api/v1/research/experiments/{id}` | Update metadata or configuration (increments version) | Yes |
| `DELETE` | `/api/v1/research/experiments/{id}` | Delete experiment (cascades to all execution runs) | Yes |
| `POST` | `/api/v1/research/experiments/{id}/runs` | Execute non-destructive sequential research run ($1 \to 2$) | Yes |
| `GET` | `/api/v1/research/experiments/{id}/runs` | List all historical execution runs for an experiment | Yes |
| `GET` | `/api/v1/research/runs/{run_id}` | Retrieve run execution details, provenance, and results | Yes |
| `POST` | `/api/v1/research/comparisons` | Multi-run cross-strategy comparative analytics | Yes |

---

## 7. Frontend Research Lab Workspace

Integrated in `frontend/src/components/pages/ResearchLabPage.tsx`:
- **Experiment Library:** Card grid displaying active hypotheses, strategy modalities, dataset bindings, run counts, last execution badges, and quick-action buttons.
- **New Hypothesis Builder:** Configurator for selecting datasets, strategies, rebalancing schedules, transaction friction (cost bps, slippage bps), Monte Carlo parameters, and benchmark assets.
- **Run History & Detail Inspector:** Drill-down into sequential runs showing execution latency, configuration fingerprints, cryptographic dataset provenance audit badges, and typed performance metrics.
- **Strategy Comparison Workspace:** Multi-select matrix comparing cumulative return, annualized return/volatility, drawdown, Sharpe, Sortino, VaR/CVaR, and cost drag with baseline deltas and warnings for mismatched periods.

---

## 8. Verification & Quality Gates

### 8.1 Backend Test Suites
Executed via `.venv/Scripts/python -m pytest`:
- **`backend/tests/test_research_engine.py` (8/8 passed):**
  - Canonical JSON key ordering stability.
  - Non-semantic whitespace and label perturbation immunity.
  - Semantic field sensitivity (modifying weights, seeds, or costs changes hash).
  - Validation rules (invalid rebalance frequencies, negative costs, weight normalization).
- **`backend/tests/test_research_api.py` (9/9 passed):**
  - Unauthenticated access rejection (HTTP 401).
  - Cross-tenant experiment isolation (User B cannot access User A's experiment).
  - Non-destructive sequential rerun ($1 \to 2$).
  - Target weights backtest execution and persistence.
  - Benchmark attribution run execution and persistence.
  - Risk simulation run execution and persistence.
  - Cross-strategy multi-run comparison.
  - Foreign key cascade deletion on experiment removal.
- **Full Backend Regression Suite:** **252 passed in 16.14s** with zero regressions across Market Data, Mathematics, Portfolio Constraints, Optimization, Efficient Frontier, Risk Analytics, Comparison, Backtesting, Scenarios, Monte Carlo, Performance Attribution, and Authentication.

### 8.2 Frontend Test Suites & Build
- **Vitest Unit & Component Tests:** `npm test -- --run` $\to$ **19 passed** across `api-client.test.ts` and `App.test.tsx`.
- **Production Build:** `npm run build` (`tsc -b && vite build`) $\to$ **0 errors**, built `dist/index.html` (0.80 kB) and `dist/assets/index-DVAwkHs5.js` (483.50 kB).

---

## 9. Reproducibility Guarantees & Limitations

### 9.1 Guarantees
1. **Deterministic Fingerprints:** Identical configuration dictionaries yield identical SHA-256 fingerprints across platforms.
2. **Non-Destructive Reruns:** Executing an existing experiment never overwrites previous runs. Historical records retain their original timestamps, duration, and output summaries.
3. **Data Provenance Alerts:** If a dataset is deleted or modified after experiment definition, the system alerts the user and marks `is_reproducible = false`.
4. **Seed Fidelity:** Stochastic Monte Carlo experiments strictly record and reuse the configured random seed.

### 9.2 Limitations
1. **Machine & Library Floating-Point Variations:** Minor variations ($\le 10^{-14}$) can occur across different CPU architectures (x86-64 vs ARM64) or BLAS/LAPACK implementations. Bit-for-bit identical floating-point values are guaranteed only within identical execution environments.
2. **Deleted Datasets:** If an underlying dataset is deleted from the database, rerunning the experiment is impossible. The system flags this condition rather than synthesizing missing data.
3. **No Automatic Strategy Discovery:** The system does not perform genetic algorithm parameter searches or black-box strategy mining. All configurations must be explicitly formulated by the researcher.

---

## 10. Conclusion & Handoff

Session 16 is complete in its entirety. The Quant Portfolio Engine now provides a fully reproducible, audited, and tenant-isolated research experiment platform.

**Ready for user review. No work has begun on Session 17.**
