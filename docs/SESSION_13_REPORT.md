# SESSION 13 REPORT — Scenario Analysis, Portfolio Stress Testing & Sensitivity Analysis

**Project:** Quant Portfolio Optimization Engine & Quant Research Dashboard  
**Session:** 13 — Scenario Analysis, Stress Testing & Sensitivity Analysis  
**Date:** 2026-10-18  
**Status:** Complete & Fully Verified  
**Current Engine Baseline:** 196 backend unit & integration tests passing (100%), 12 frontend tests passing (100%), zero TypeScript build errors (`tsc -b && vite build` passed).

---

## 1. Executive Summary

Session 13 delivered an institutional-grade, mathematically reliable Scenario Analysis, Portfolio Stress Testing, and Sensitivity Analysis module. The implementation adheres strictly to the financial data contracts of the platform:
1. **Instantaneous Shocks:** Instantaneous asset repricing preserving unshocked cash ($V_{\text{after}} = \sum V_i(1+s_i) + C$), exact additive attribution reconciliation ($\sum \Delta V_i = \Delta V$), with zero look-ahead bias and clear non-predictive disclaimers.
2. **Historical Stress Window Replay:** Pure extraction of cumulative empirical returns over requested historical date ranges using only verified observations without synthetic forward-filling or data fabrication.
3. **Covariance & Correlation Stress:** Mathematical perturbation of covariance matrices with spectral eigenvalue verification and Higham-style spectral clipping projection ($M_{\text{psd}} = Q \max(\Lambda, 0) Q^T$) to guarantee positive semi-definiteness.
4. **Parametric Sensitivity Sweeps:** Deterministic 1-factor and 2-factor parametric shock grids with strict bounds ($\le 441$ grid points) to prevent computational exhaustion.
5. **Relational Persistence & Tenant Isolation:** Alembic migration `e4f5a6b7c8d9` creating the `scenario_runs` table with foreign key linkage to `users` and `datasets` and full tenant isolation.
6. **Institutional React Workspace:** Interactive `ScenarioAnalysisPage` featuring preset templates, asset shock inputs, waterfall contribution visualization, parametric sensitivity curves, and past run management.

---

## 2. Inventory of Changes

### 2.1 Backend Modules Created
- `backend/app/scenarios/`: Dedicated scenario package
  - `models.py`: Pydantic request and response schemas (`ScenarioRequest`, `ScenarioResponse`, `AssetShockContribution`, `ScenarioSummaryMetrics`, `SensitivityRequest`, `SensitivityResponse`, `ScenarioListItem`).
  - `shocks.py`: Pure mathematical calculation functions for instantaneous shocks and asset attribution.
  - `stress.py`: Pure functions for historical price extraction and covariance stress with eigenvalue decomposition.
  - `sensitivity.py`: Pure functions for 1-factor and 2-factor parametric sensitivity sweeps.
  - `service.py`: Orchestrator enforcing dataset ownership, currency homogeneity, composite asset resolution (`TICKER:MARKET`), solver invocation, and relational persistence.
  - `__init__.py`: Package export declarations.
- `backend/app/api/v1/scenario_routes.py`: FastAPI endpoints for scenario runs, stress tests, sensitivity sweeps, and scenario run CRUD.
- `backend/alembic/versions/e4f5a6b7c8d9_create_scenario_runs_table.py`: Database migration for `scenario_runs` table and indexes.
- `backend/tests/test_scenario_engine.py`: 9 deterministic mathematical tests covering zero shocks, cash preservation, attribution conservation, historical replay, covariance stress, and PSD projection.
- `backend/tests/test_scenario_api.py`: 8 end-to-end API integration tests verifying authentication, tenant isolation, cross-tenant blocking, sensitivity grid limits, and CRUD.

### 2.2 Backend Files Modified
- `backend/app/db/models.py`: Added `ScenarioRunModel` with relationships to `UserModel` and `DatasetModel`.
- `backend/app/api/v1/routes.py`: Mounted `scenario_router` and updated health check stage to `scenario-analysis`.
- `backend/tests/conftest.py`: Added `test_scenario_api` to security test exemption list to verify 401 unauthenticated rejections.
- `backend/tests/test_auth_and_access_control.py`: Updated health stage check tuple to accept `scenario-analysis`.

### 2.3 Frontend Files Created / Modified
- `frontend/src/types/api.ts`: Added TypeScript interfaces for `ScenarioRequest`, `ScenarioResponse`, `AssetShockContribution`, `ScenarioSummaryMetrics`, `SensitivityRequest`, `SensitivityResponse`, `ScenarioListItem`.
- `frontend/src/api/client.ts`: Added methods `executeScenario`, `executeStressTest`, `executeSensitivity`, `listScenarios`, `getScenario`, `deleteScenario`.
- `frontend/src/components/pages/ScenarioAnalysisPage.tsx`: Institutional React 19 workspace with presets, waterfall SVG contribution chart, sensitivity SVG curve, and saved run selector.
- `frontend/src/components/layout/Sidebar.tsx`: Added `'scenario-analysis'` navigation item with `Zap` icon.
- `frontend/src/components/layout/Header.tsx`: Added page title and description for scenario analysis.
- `frontend/src/components/pages/OverviewPage.tsx`: Added Overview Card 8 for Scenario Analysis & Stress Testing.
- `frontend/src/App.tsx`: Wired `ScenarioAnalysisPage` into navigation switch.
- `frontend/src/test/api-client.test.ts`: Added unit tests for `executeScenario` and `executeSensitivity`.
- `frontend/src/test/App.test.tsx`: Added scenario mock handling and navigation test for Scenario & Stress workspace.

### 2.4 Documentation Created / Modified
- `docs/SESSION_13_AUDIT.md`: Pre-coding audit of existing capabilities, database schema, Alembic head, and implementation plan.
- `docs/SCENARIO_ANALYSIS_CONTRACTS.md`: Financial contract covering instantaneous shocks, attribution conservation, covariance eigenvalues, and non-prediction disclaimers.
- `docs/MASTER_PLAN.md`: Updated Stage 9 with Session 13 deliverables and acceptance gate.
- `docs/SYSTEM_ARCHITECTURE.md`: Documented `app/scenarios/` architecture, persistence models, and data flows.
- `docs/REQUIREMENTS_SPEC.md`: Added FR-065 through FR-072.
- `docs/TEST_STRATEGY.md`: Added Section 4.7 for Scenario Analysis test suite.
- `docs/SESSION_13_REPORT.md`: This comprehensive completion report.

---

## 3. Mathematical Conventions & Contracts

### 3.1 Instantaneous Shocks & Cash Preservation
Given initial asset values $V_i = w_i \cdot V_{\text{pre}}$ and cash $C = V_{\text{pre}}(1 - \sum w_i)$, the shocked portfolio value is:
$$V_{\text{after}} = \sum_{i=1}^n V_i(1 + s_i) + C$$
Absolute portfolio change:
$$\Delta V = V_{\text{after}} - V_{\text{pre}} = \sum_{i=1}^n V_i \cdot s_i$$
Percentage portfolio return:
$$\% \Delta V = \frac{\Delta V}{V_{\text{pre}}}$$

### 3.2 Exact Attribution Reconciliation
Asset dollar contribution:
$$\text{ContributionDollar}_i = V_i \cdot s_i = \Delta V_i$$
Conservation identity:
$$\sum_{i=1}^n \text{ContributionDollar}_i \equiv \Delta V$$
Asset return contribution:
$$\text{ContributionReturn}_i = w_i \cdot s_i$$
When $C = 0$:
$$\sum_{i=1}^n \text{ContributionReturn}_i \equiv \% \Delta V$$

### 3.3 Covariance & Correlation Perturbation
Given baseline covariance $\mathbf{\Sigma}_0 = \mathbf{D}_0 \mathbf{R}_0 \mathbf{D}_0$:
1. Volatility stress: $\sigma_{i, \text{stressed}} = \sigma_i \cdot \alpha_i$
2. Correlation stress: $R_{ij, \text{stressed}} = \text{clip}(R_{ij} \cdot \beta, -0.999, 0.999)$ for $i \ne j$, $R_{ii} = 1.0$.
3. Positive semi-definiteness (PSD) check: $\lambda_{\min}(\mathbf{\Sigma}_{\text{stressed}}) \ge -10^{-8}$.
4. Spectral projection (when requested): $\mathbf{R}_{\text{proj}} = \sum_{k=1}^n \max(\lambda_k, 10^{-8}) \mathbf{v}_k \mathbf{v}_k^T$ followed by diagonal normalization.

### 3.4 Currency Invariants
- Portfolios must have homogeneous currency denomination across assets.
- Cross-currency portfolios (e.g., mixing USD and PKR) are strictly rejected with HTTP 422 until a formal FX conversion framework is implemented.

---

## 4. API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/scenarios` | Execute instantaneous or historical scenario | Yes |
| `POST` | `/api/v1/scenarios/stress-test` | Execute volatility / correlation stress test | Yes |
| `POST` | `/api/v1/scenarios/sensitivity` | Execute 1D or 2D parametric sensitivity sweep | Yes |
| `GET` | `/api/v1/scenarios` | List saved scenario runs for authenticated user | Yes |
| `GET` | `/api/v1/scenarios/{scenario_id}` | Retrieve specific scenario run by ID | Yes |
| `DELETE` | `/api/v1/scenarios/{scenario_id}` | Delete owned scenario run | Yes |

All endpoints enforce tenant isolation: attempting to access another user's scenario run returns HTTP 404 (preventing ID enumeration).

---

## 5. Database Schema & Migration

### Alembic Revision: `e4f5a6b7c8d9`
- **Down Revision:** `8993dbd79e8a` (from Session 12 backtesting migration)
- **Table Created:** `scenario_runs`
  - `id`: String(36), Primary Key (UUIDv4)
  - `user_id`: String(36), Foreign Key to `users.id`, nullable=True, ondelete='CASCADE'
  - `dataset_id`: String(36), Foreign Key to `datasets.id`, nullable=False, ondelete='CASCADE'
  - `name`: String(120), nullable=False
  - `scenario_type`: String(50), nullable=False
  - `status`: String(20), nullable=False
  - `parameters`: JSON, nullable=False
  - `results`: JSON, nullable=False
  - `created_at`: DateTime(timezone=True), server_default=func.now()
- **Indexes:**
  - `ix_scenario_runs_user_id` on (`user_id`)
  - `ix_scenario_runs_dataset_id` on (`dataset_id`)

---

## 6. Verification & Test Execution Results

### 6.1 Backend Test Results
```text
Command: .venv\Scripts\pytest
Result: 196 passed, 3 warnings in 13.25s (100% pass rate)

Breakdown:
- tests/test_scenario_engine.py: 9 passed
- tests/test_scenario_api.py: 8 passed
- tests/test_backtesting_engine.py: 9 passed
- tests/test_backtesting_api.py: 7 passed
- tests/test_auth_and_access_control.py: 20 passed
- tests/test_optimization_engine.py: 23 passed
- tests/test_quant_math.py: 26 passed
- tests/test_risk_and_frontier.py: 20 passed
- tests/test_portfolio_engine.py: 19 passed
- tests/test_validation_engine.py: 20 passed
- tests/test_persistence_and_database.py: 8 passed
- tests/test_integration_and_reliability.py: 7 passed
- tests/test_market_data.py: 8 passed
- tests/test_dataset_registry.py: 6 passed
- tests/test_api_contracts.py: 6 passed
```

### 6.2 Frontend Test Results
```text
Command: npm test -- --run
Result: 12 passed in 2 files (100% pass rate)

Breakdown:
- src/test/api-client.test.ts: 8 passed
- src/test/App.test.tsx: 4 passed
```

### 6.3 Frontend Production Build
```text
Command: npm run build
Result: Code exited with code 0.
Vite bundle generated in 554ms with 0 type errors.
- dist/index.html: 0.80 kB
- dist/assets/index-DtJMXJ5u.css: 10.61 kB
- dist/assets/index-C39xi2FZ.js: 381.77 kB
```

---

## 7. Known Issues & Scope Boundaries

### Handled Cleanly in Session 13:
- Denominator safety when baseline portfolio value is zero.
- Non-PSD correlation matrix detection with optional spectral eigenvalue clipping.
- Grid computation ceilings preventing resource exhaustion ($\le 441$ points for 2D, $\le 101$ for 1D).
- Automatic preservation of unshocked cash reserves.
- Strict isolation of user scenario runs.

### Explicitly Deferred to Future Sessions (Out of Scope for Session 13):
- Live trading or order management system (OMS/EMS).
- Options Greeks, Black-Scholes pricing, or non-linear derivatives stress.
- FX conversion between cross-currency asset classes.
- Continuous-time Monte Carlo path generators.
- Automated regulatory report submission (CCAR/FRTB).

---

## 8. Definition of Done Confirmation

- [x] Pre-coding repository audit documented in `docs/SESSION_13_AUDIT.md`.
- [x] Financial contract documented in `docs/SCENARIO_ANALYSIS_CONTRACTS.md`.
- [x] Pure deterministic scenario engine built under `backend/app/scenarios/`.
- [x] Alembic migration `e4f5a6b7c8d9` created and applied.
- [x] Authenticated REST API endpoints implemented and secured.
- [x] React 19 institutional Scenario Analysis workspace built and tested.
- [x] All 196 backend tests passed.
- [x] All 12 frontend tests passed.
- [x] Frontend production build (`tsc -b && vite build`) passed with zero errors.
- [x] Project documentation updated (`MASTER_PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `REQUIREMENTS_SPEC.md`, `TEST_STRATEGY.md`, `SESSION_13_REPORT.md`).
- [x] Strictly stopped at Session 13 completion boundary without initiating Session 14.
