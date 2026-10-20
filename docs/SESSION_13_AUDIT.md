# SESSION 13 AUDIT — Scenario Analysis, Portfolio Stress Testing & Sensitivity Analysis

**Project:** Quant Portfolio Optimization Engine & Research Dashboard  
**Date:** 2026-10-18  
**Author:** Quantitative Research Software Engineering  
**Scope:** Session 13 Repository Audit and Technical Feasibility Assessment  

---

## 1. Existing Reusable Functionality

An audit of the codebase confirms that Sessions 01 through 12 have established an institutional quantitative finance foundation:

1. **Pure Financial Mathematics (`backend/app/quant/`):**
   - `returns.py`: Arithmetic returns $r_t = (P_t - P_{t-1}) / P_{t-1}$, log returns, periodic compounding, and annualization factors.
   - `covariance.py`: Sample and population covariance matrices $\mathbf{\Sigma}$, Ledoit-Wolf shrinkage, symmetry enforcement ($\|\mathbf{\Sigma} - \mathbf{\Sigma}^T\| \le 10^{-12}$), and pairwise/listwise missing value handling.
   - `portfolio.py`: Weight validation, gross/net exposure computation, portfolio returns $R_p = \mathbf{w}^T \mathbf{r}$, portfolio variance $\sigma_p^2 = \mathbf{w}^T \mathbf{\Sigma} \mathbf{w}$, and volatility $\sigma_p$.
   - `risk.py`: Annualized volatility, historical downside deviation below MAR, Sortino ratio, Sharpe ratio, and peak-to-trough Maximum Drawdown.
   - `optimization.py`: SciPy SLSQP quadratic programming solver for minimum variance and maximum Sharpe allocations under linear constraints.

2. **Market Data & Persistence Layer (`backend/app/market_data/`, `backend/app/db/`):**
   - SQLAlchemy 2.0 relational models: `UserModel`, `DatasetModel`, `AssetModel`, `PriceBarModel`, `BacktestRunModel`.
   - Authoritative SQLite / PostgreSQL database managed via Alembic (current head revision: `8993dbd79e8a`).
   - In-memory dataset registry cache (`_DATASETS`) backed by relational persistence across server restarts.
   - `prepare_backtest_data` (`backend/app/backtesting/data.py`): Reusable pattern for synchronized price panels, adjusted-close prioritization, canonical composite asset resolution (`TICKER:MARKET`), and currency validation.

3. **Authentication & Multi-Tenant Security (`backend/app/auth/`):**
   - JWT token authentication via `Authorization: Bearer <token>` and `SameSite=Lax` HttpOnly cookies.
   - `check_dataset_access(session, dataset_id, user)`: Strict tenant isolation ensuring users can only query or run models on their owned or shared datasets.
   - Test framework integration via `conftest.py` with mock overrides for legacy suites and live auth verification.

4. **Frontend Architecture (`frontend/src/`):**
   - React 19, TypeScript, and Vite.
   - Institutional dark-theme design tokens, responsive sidebar navigation (`Sidebar.tsx`), contextual header (`Header.tsx`), and workflow overview cards (`OverviewPage.tsx`).
   - Typed API client (`frontend/src/api/client.ts`) with error details extraction.
   - High-performance native SVG charting (avoiding heavy external chart dependencies).

---

## 2. Existing Data & Currency Contracts

1. **Asset Identity Invariant:**
   - Assets are canonically identified by composite IDs `TICKER:MARKET` (e.g., `AAPL:US`, `LUCK:PSX`).
   - User inputs specifying plain tickers (e.g., `AAPL`) are resolved by matching against both canonical ID and ticker prefix if unambiguous.
2. **Homogeneous Currency Invariant:**
   - As documented in `docs/FINANCIAL_DATA_CONTRACTS.md` and enforced in `app/portfolio/service.py` and `app/backtesting/data.py`, portfolios must contain assets of a single currency (e.g., all `USD` or all `PKR`).
   - Cross-currency portfolios without explicit FX exchange rate series are rejected with a 422 Unprocessable Entity error.
3. **Price Priority Policy:**
   - Adjusted close (`adjusted_close`) is prioritized over unadjusted `close` to account for stock splits and dividend distributions.
4. **Zero Silent Imputation:**
   - The engine strictly forbids fabricating missing dates or synthesizing prices. If observations are missing, listwise alignment or structured errors are emitted.

---

## 3. Current Authentication & Ownership Boundaries

- All scenario and stress-testing endpoints must require authentication via `get_current_active_user`.
- Datasets must be verified using `check_dataset_access(session, dataset_id, user)`.
- If scenario runs are persisted in relational storage (`scenario_runs` table), they must be linked to `user_id` with `ondelete="CASCADE"` and indexed for tenant isolation. User B must never be able to view, execute against, or delete User A's scenario runs.

---

## 4. Missing Functionality & Integration Risks

1. **Absence of Scenario & Stress Testing Domain:**
   - The system currently lacks a dedicated `backend/app/scenarios/` module.
   - No data models exist for custom asset shocks, historical event shocks, volatility scaling, correlation stress, or sensitivity matrices.
2. **Covariance Matrix Stress Mathematical Risks:**
   - Arbitrarily altering correlation coefficients or volatilities can violate positive semi-definiteness (PSD), resulting in negative eigenvalues and imaginary portfolio volatilities.
   - **Mitigation:** Implement strict PSD validation ($\lambda_{\min} \ge -10^{-8}$) and documented eigenvalue floor clipping (Higham projection / spectral reconstruction) when correlation stress is applied.
3. **Distinction Between Instantaneous Shock vs. Path Simulation:**
   - Instantaneous shock analysis evaluates $V_{\text{after}} = \sum V_i(1 + s_i) + C$ at a single static instant. It does not generate a return time series.
   - **Mitigation:** Do not compute Sharpe, Sortino, or CAGR for instantaneous shocks. Clearly delineate instantaneous valuation shocks from multi-period historical window replays.
4. **Computational Explosion in Sensitivity Grids:**
   - Multi-factor grid evaluation can experience combinatorial explosion ($M^K$ evaluations).
   - **Mitigation:** Cap 1-factor sensitivity grids to at most 101 points (e.g., $-50\%$ to $+50\%$ in $1\%$ steps), and cap 2-factor grids to at most $21 \times 21 = 441$ points. Reject grids with $> 500$ points.

---

## 5. Precise Session 13 Implementation Plan

1. **Contract Definition (`docs/SCENARIO_ANALYSIS_CONTRACTS.md`):**
   - Document formal mathematical equations, units (decimal vs. percentage), base currency constraints, cash handling, and output schemas.
2. **Domain Core (`backend/app/scenarios/`):**
   - `models.py`: Typed Pydantic schemas for requests, responses, asset shock contributions, sensitivity matrices, and risk metrics.
   - `shocks.py`: Pure functions for instantaneous asset price shocks, portfolio value changes, percentage changes, and asset contributions.
   - `stress.py`: Pure functions for historical window return extraction and covariance matrix stress (volatility scaling and correlation contraction/expansion with PSD verification).
   - `sensitivity.py`: Bounded 1D and 2D grid sweep engines.
   - `service.py`: Orchestration layer enforcing dataset authorization, currency homogeneity, execution, and persistence.
3. **Relational Persistence & Migration:**
   - Define `ScenarioRunModel` in `backend/app/db/models.py`.
   - Author Alembic migration `e4f5a6b7c8d9_create_scenario_runs_table.py` downstream of `8993dbd79e8a`.
4. **FastAPI Endpoints (`backend/app/api/v1/scenario_routes.py`):**
   - `POST /api/v1/scenarios`: Run instantaneous asset shock or stress scenario.
   - `POST /api/v1/scenarios/sensitivity`: Run 1D or 2D parameter sweep.
   - `POST /api/v1/scenarios/stress-test`: Run historical window or covariance stress test.
   - `GET /api/v1/scenarios`: List saved scenario runs for authenticated user.
   - `GET /api/v1/scenarios/{id}`: Retrieve saved scenario details.
   - `DELETE /api/v1/scenarios/{id}`: Delete saved scenario run.
   - Mount router into `backend/app/api/v1/routes.py` and update health stage to `scenario-analysis`.
5. **Frontend Workspace (`frontend/src/components/pages/ScenarioAnalysisPage.tsx`):**
   - Scenario type tabs: **Custom Asset Shocks**, **Historical Stress Window**, **Volatility & Correlation Stress**, and **Sensitivity Analysis**.
   - Interactive shock inputs with presets (e.g., Tech Selloff, Market Correction, Flight to Quality).
   - Vector SVG visualizations:
     - Waterfall / Bar chart for asset-level dollar and percentage contribution to portfolio change.
     - 1D sensitivity curve / 2D contour grid.
     - Baseline vs. Stressed volatility comparison.
   - Saved scenarios selector with live retrieval and deletion.
   - Navigation wiring in `Sidebar.tsx`, `Header.tsx`, `App.tsx`, and `OverviewPage.tsx`.
6. **Comprehensive Automated Testing:**
   - `backend/tests/test_scenario_engine.py`: 10+ deterministic mathematical tests.
   - `backend/tests/test_scenario_api.py`: 8+ API integration, tenant isolation, and validation boundary tests.
   - `frontend/src/test/`: Vitest client and component navigation tests.
   - Verify full regression pass (179+ backend tests, 10+ frontend tests, clean production build).
7. **Documentation Updates:**
   - `docs/MASTER_PLAN.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/REQUIREMENTS_SPEC.md`, `docs/TEST_STRATEGY.md`, and `docs/SESSION_13_REPORT.md`.

---

## 6. Acceptance Criteria & Expected File Modifications

- **Mathematical Correctness:** Zero shock yields $\Delta V = 0$. Sum of asset dollar contributions equals total portfolio dollar change ($\sum \Delta V_i = \Delta V_p \pm 10^{-6}$).
- **Security & Multi-Tenancy:** Unauthenticated requests rejected with 401; cross-tenant access returns 404/403.
- **Determinism:** Zero randomness; exact reproducible floating-point calculations.
- **Full Test Suite:** 100% green pass on all backend and frontend suites.

**Expected Files Created / Modified:**
- `docs/SESSION_13_AUDIT.md` (Created)
- `docs/SCENARIO_ANALYSIS_CONTRACTS.md` (Created)
- `backend/app/scenarios/` (New directory with `__init__.py`, `models.py`, `shocks.py`, `stress.py`, `sensitivity.py`, `service.py`)
- `backend/app/db/models.py` (Add `ScenarioRunModel`)
- `backend/alembic/versions/e4f5a6b7c8d9_create_scenario_runs_table.py` (New migration)
- `backend/app/api/v1/scenario_routes.py` (New router)
- `backend/app/api/v1/routes.py` (Mount router, update health stage)
- `backend/tests/conftest.py` (Exempt `test_scenario_api` from ambient auth mock)
- `backend/tests/test_scenario_engine.py` (New unit tests)
- `backend/tests/test_scenario_api.py` (New API integration tests)
- `frontend/src/types/api.ts` (Add scenario interfaces)
- `frontend/src/api/client.ts` (Add scenario API methods)
- `frontend/src/components/pages/ScenarioAnalysisPage.tsx` (New workspace component)
- `frontend/src/components/layout/Sidebar.tsx` (Add navigation item)
- `frontend/src/components/layout/Header.tsx` (Add page title)
- `frontend/src/App.tsx` (Wire routing)
- `frontend/src/components/pages/OverviewPage.tsx` (Add Card 8)
- `frontend/src/test/api-client.test.ts` (Add scenario client tests)
- `frontend/src/test/App.test.tsx` (Add scenario navigation tests)
- `docs/MASTER_PLAN.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/REQUIREMENTS_SPEC.md`, `docs/TEST_STRATEGY.md`, `docs/SESSION_13_REPORT.md` (Updated/Created)
