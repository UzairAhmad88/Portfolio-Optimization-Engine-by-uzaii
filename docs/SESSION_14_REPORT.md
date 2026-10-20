# SESSION 14 REPORT — Monte Carlo Simulation, Probabilistic Risk Analysis, VaR & CVaR

## Executive Summary

Session 14 delivers a deterministic Monte Carlo simulation engine, multi-estimator Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR / Expected Shortfall) risk analytics, tenant-isolated relational persistence, authenticated REST APIs, and an interactive React 19 / TypeScript quantitative workspace (`MonteCarloPage.tsx`).

The module enables quantitative researchers to generate multi-period stochastic asset return trajectories, evaluate terminal wealth distributions, examine tail risk with empirical and parametric estimators, and compare simulated outcomes against parametric and historical benchmarks.

All simulated outcomes are strictly designated as hypothetical research models. They are not presented as guarantees of future profitability, forecasts of actual asset returns, or personalized investment advice.

---

## 1. Pre-Coding Repository Audit

Prior to implementation, a thorough audit was conducted and recorded in [docs/SESSION_14_AUDIT.md](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/SESSION_14_AUDIT.md):

- **Baseline Test Suite:** Verified 196 passing backend pytest tests and 12 passing frontend Vitest tests from Session 13.
- **Alembic Database State:** Migration head verified at `e4f5a6b7c8d9` (`create_scenario_runs_table`).
- **Reusable Core Modules:** Reused `backend/app/quant/covariance.py` for sample covariance, `backend/app/scenarios/stress.py` for PSD spectral clipping projection, and `backend/app/market_data/service.py` for verified dataset bar retrieval.
- **Identified Gaps:** Prior to Session 14, no stochastic path generator, Cholesky factorization, or empirical/parametric VaR/CVaR calculations existed.
- **Financial Risk Contract:** Formulated and approved in [docs/PROBABILISTIC_RISK_CONTRACTS.md](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/PROBABILISTIC_RISK_CONTRACTS.md) prior to writing implementation code.

---

## 2. Financial Risk Contracts & Mathematical Conventions

### 2.1 Return & Compounding Conventions
Simulations generate discrete simple arithmetic returns $r_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$. Individual asset values compound multiplicatively:
$$V_{i,t} = V_{i,t-1}(1 + r_{i,t})$$

Total portfolio wealth is the sum of asset holdings plus cash $C$:
$$V_t = C + \sum_{i=1}^N V_{i,t}$$

- **`buy_and_hold`:** Asset values drift according to realized returns without rebalancing.
- **`constant_weights`:** At the end of each simulation step $t$, total wealth $V_t$ is redistributed according to target weights $w_i$, resetting $V_{i,t} = w_i V_t$.

### 2.2 Loss Sign Convention & Tail Risk Formulations
Portfolio loss is defined as:
$$L = V_0 - V_T$$
Under this convention, **positive VaR and CVaR represent positive financial loss** (a decline in portfolio value).

- **Empirical Value at Risk ($\text{VaR}_q$):**
  For confidence level $q \in (0, 1)$, $\text{VaR}_q$ is the $q$-quantile of the simulated loss sample $\{L_1, \dots, L_P\}$ using linear interpolation:
  $$\text{VaR}_q = Q_q(L)$$
- **Empirical Conditional Value at Risk ($\text{CVaR}_q$ / Expected Shortfall):**
  The expected loss conditional on the loss equaling or exceeding the VaR threshold:
  $$\text{CVaR}_q = \frac{1}{|K|} \sum_{k \in K} L_k, \quad K = \{k : L_k \ge \text{VaR}_q\}$$
  In cases of small samples where $K$ is empty, $\text{CVaR}_q = \text{VaR}_q$.
- **Parametric VaR & CVaR (Normal Benchmark):**
  For portfolio loss mean $\mu_L$ and standard deviation $\sigma_L$:
  $$\text{VaR}_q^{\text{param}} = \mu_L + z_q \sigma_L$$
  $$\text{CVaR}_q^{\text{param}} = \mu_L + \frac{\phi(z_q)}{1 - q} \sigma_L$$
  where $z_q = \Phi^{-1}(q)$ and $\phi(z)$ is the standard normal probability density function.

### 2.3 Multivariate Return Generation
1. **Multivariate Normal Baseline:**
   $$\mathbf{r}_t = \boldsymbol{\mu} + \mathbf{L} \mathbf{z}_t, \quad \mathbf{z}_t \sim \mathcal{N}(\mathbf{0}, \mathbf{I})$$
   where $\mathbf{\Sigma} = \mathbf{L} \mathbf{L}^T$ is the Cholesky factorization of the positive semidefinite covariance matrix.
2. **Multivariate Student-t Extension:**
   $$\mathbf{r}_t = \boldsymbol{\mu} + \sqrt{\frac{\nu - 2}{W_t}} \mathbf{L} \mathbf{z}_t, \quad W_t \sim \text{Gamma}\left(\frac{\nu}{2}, \frac{\nu}{2}\right)$$
   The scaling factor $\sqrt{\frac{\nu-2}{W_t}}$ guarantees that for $\nu > 2$, the theoretical covariance of simulated returns $\operatorname{Cov}(\mathbf{r}_t) = \mathbf{\Sigma}$ exactly matches the input covariance matrix.
3. **Spectral Positive Semidefiniteness Projection:**
   If sample covariance $\mathbf{\Sigma}$ is ill-conditioned or rank-deficient ($N > T$), eigenvalues are floored at $\epsilon = 10^{-8}$:
   $$\mathbf{\Sigma}_{\text{psd}} = \mathbf{Q} \max(\mathbf{\Lambda}, 10^{-8} \mathbf{I}) \mathbf{Q}^T$$

---

## 3. Implementation Details

### 3.1 Core Quant & Risk Simulation Engine
- `backend/app/quant/var_cvar.py`: Pure functions for empirical VaR/CVaR, analytical parametric VaR/CVaR, and historical empirical estimation.
- `backend/app/risk_simulation/models.py`: Pydantic request/response models (`RiskSimulationRequest`, `RiskSimulationResponse`, `RiskSimulationSummary`, `VaRCVaREstimate`, `MultiEstimatorComparison`, `SimulationPathPoint`, `DistributionBin`, `RiskSimulationListItem`, `VaRCVaRStandaloneRequest`).
- `backend/app/risk_simulation/engine.py`: Pure mathematical routines for Cholesky factorization, PSD projection, Multivariate Normal and Student-t generation, multi-period wealth evolution, histogram binning, and trajectory downsampling.
- `backend/app/risk_simulation/service.py`: Service orchestrator verifying dataset access, preparing aligned price matrices, computing historical statistics, dispatching simulations, downsampling path envelopes, and persisting runs.
- `backend/app/risk_simulation/__init__.py`: Package initialization and exports.

### 3.2 Database Persistence & Alembic Migration
- `backend/app/db/models.py`: Added `RiskSimulationRunModel` with foreign key relationships to `UserModel` and `DatasetModel`, composite index on `(user_id, created_at)`, and cascading deletion on user/dataset removal.
- `backend/alembic/versions/f5a6b7c8d9e0_create_risk_simulation_runs_table.py`: Idempotent migration creating `risk_simulation_runs` table and indexes.
  - **Down revision:** `e4f5a6b7c8d9` (Session 13)
  - **Head revision:** `f5a6b7c8d9e0` (Session 14)

### 3.3 Authenticated REST API
Mounted under `/api/v1` in `backend/app/api/v1/risk_simulation_routes.py`:
- `POST /api/v1/risk-simulations` — Execute Monte Carlo simulation and persist summary run.
- `POST /api/v1/risk-simulations/var-cvar` — Compute standalone multi-estimator VaR and CVaR.
- `GET /api/v1/risk-simulations` — List authenticated user's saved runs.
- `GET /api/v1/risk-simulations/{run_id}` — Retrieve owned simulation run by ID.
- `DELETE /api/v1/risk-simulations/{run_id}` — Delete owned simulation run.

### 3.4 Frontend Workspace
- `frontend/src/types/api.ts`: Added TypeScript interfaces for risk simulation, distributions, trajectories, and estimators.
- `frontend/src/api/client.ts`: Added `executeRiskSimulation`, `calculateStandaloneVaRCVaR`, `listRiskSimulations`, `getRiskSimulation`, `deleteRiskSimulation`.
- `frontend/src/components/pages/MonteCarloPage.tsx`: Interactive quantitative workspace featuring:
  - Preset portfolio templates (Equal Weight, Tech Growth, Defensive/Balanced).
  - Configurable horizon, path count ($\le 5,000$), distribution model (Normal vs. Student-t), degrees of freedom ($\nu$), random seed, and loss threshold.
  - SVG Terminal Return Density Histogram with dashed markers for 95% VaR, 99% VaR, and 95% CVaR.
  - SVG Wealth Trajectory Fan Chart rendering 5th-95th percentile ribbon, median trajectory, and individual sample paths.
  - Multi-Estimator Risk Comparison Matrix benchmarking Monte Carlo vs. Parametric vs. Historical VaR and CVaR.
  - Saved Runs Drawer with run retrieval and deletion controls.
- `frontend/src/components/layout/Sidebar.tsx`: Added `'monte-carlo'` navigation item with `Dice5` icon.
- `frontend/src/components/layout/Header.tsx`: Added page title and subtitle for `'monte-carlo'`.
- `frontend/src/components/pages/OverviewPage.tsx`: Added Card 9 for Monte Carlo Risk Analysis.
- `frontend/src/App.tsx`: Wired `'monte-carlo'` route into the main workspace switcher.

---

## 4. Verification & Quality Gates

### 4.1 Backend Automated Tests (Pytest)
Command executed:
```bash
.\.venv\Scripts\pytest.exe -q
```
Result: **216 passed, 3 warnings in 14.53s** (100% pass rate).

Test suite breakdown:
- `backend/tests/test_risk_simulation_engine.py`: 12 passed tests covering hand-calculated small loss samples, tied quantiles, monetary vs. percentage reconciliation, normal benchmark comparison, moment convergence ($N=25,000$), Student-t fat tails, PSD spectral projection, compounding drift vs. constant weights, and histogram/trajectory downsampling.
- `backend/tests/test_risk_simulation_api.py`: 8 passed tests covering unauthenticated rejection (401), authenticated execution, Student-t execution, cross-tenant dataset isolation (404/403), resource limit enforcement ($P \le 10,000$, $T \le 252$), CRUD operations and tenant run isolation, and standalone VaR/CVaR endpoint.
- All 196 regression tests from Sessions 01 through 13 continue to pass without regression.

### 4.2 Frontend Automated Tests (Vitest)
Command executed:
```bash
npm test -- --run
```
Result: **14 passed across 2 test files in 2.68s** (100% pass rate).
- `frontend/src/test/api-client.test.ts`: 10 passed tests, including `executeRiskSimulation` and `calculateStandaloneVaRCVaR`.
- `frontend/src/test/App.test.tsx`: 4 passed tests, including authenticated rendering, sidebar navigation to `Monte Carlo Risk`, and switching across all research workspaces.

### 4.3 Frontend Production Build
Command executed:
```bash
npm run build
```
Result: **Exit code 0** (`tsc -b && vite build`). Clean TypeScript compilation with 0 type errors; bundle generated in 735ms.

---

## 5. Artifacts and Changed Files

| File Path | Description |
|---|---|
| `docs/SESSION_14_AUDIT.md` | Pre-implementation audit recording existing code, migration head, and architectural plan. |
| `docs/PROBABILISTIC_RISK_CONTRACTS.md` | Comprehensive mathematical contracts for Monte Carlo simulations, loss-sign conventions, and VaR/CVaR. |
| `backend/app/quant/var_cvar.py` | Pure calculation functions for empirical, parametric, and historical VaR/CVaR. |
| `backend/app/quant/__init__.py` | Exported VaR/CVaR symbols. |
| `backend/app/risk_simulation/models.py` | Pydantic request/response models for simulation and VaR/CVaR. |
| `backend/app/risk_simulation/engine.py` | Pure mathematical routines for multivariate return generation, PSD projection, and compounding. |
| `backend/app/risk_simulation/service.py` | Multi-tenant orchestrator and persistence manager. |
| `backend/app/risk_simulation/__init__.py` | Package entrypoint. |
| `backend/app/api/v1/risk_simulation_routes.py` | Authenticated FastAPI routes for simulation and run management. |
| `backend/app/api/v1/routes.py` | Mounted `risk_simulation_router` and updated health stage to `probabilistic-risk`. |
| `backend/app/db/models.py` | Added `RiskSimulationRunModel` SQLAlchemy model. |
| `backend/alembic/versions/f5a6b7c8d9e0_create_risk_simulation_runs_table.py` | Database migration for `risk_simulation_runs` table. |
| `backend/tests/test_risk_simulation_engine.py` | Pure mathematical tests for VaR/CVaR and simulation engine. |
| `backend/tests/test_risk_simulation_api.py` | API integration and tenant isolation tests. |
| `backend/tests/test_auth_and_access_control.py` | Updated health stage test assertion. |
| `backend/tests/conftest.py` | Added risk simulation test module to unmocked security suite. |
| `frontend/src/types/api.ts` | Added TypeScript interfaces for risk simulation domain. |
| `frontend/src/api/client.ts` | Added API methods for simulation, VaR/CVaR, and run CRUD. |
| `frontend/src/components/pages/MonteCarloPage.tsx` | Interactive React 19 quantitative workspace. |
| `frontend/src/components/layout/Sidebar.tsx` | Added `'monte-carlo'` navigation item. |
| `frontend/src/components/layout/Header.tsx` | Added `'monte-carlo'` page header mapping. |
| `frontend/src/components/pages/OverviewPage.tsx` | Added Card 9 for Monte Carlo Risk Analysis. |
| `frontend/src/App.tsx` | Wired `'monte-carlo'` workspace switch. |
| `frontend/src/test/api-client.test.ts` | Added tests for simulation API client methods. |
| `frontend/src/test/App.test.tsx` | Added test for Monte Carlo navigation and rendering. |
| `docs/MASTER_PLAN.md` | Updated roadmap with Stage 10 milestone. |
| `docs/SYSTEM_ARCHITECTURE.md` | Added Section 3.6 module responsibility and ADR-11. |
| `docs/REQUIREMENTS_SPEC.md` | Added Section 3.10 (FR-073 to FR-080). |
| `docs/TEST_STRATEGY.md` | Added Section 4.8 verification suite details. |
| `docs/SESSION_14_REPORT.md` | Session 14 completion report. |

---

## 6. Assumptions and Limitations

1. **Non-Predictive Disclaimer:** All simulated outcomes are hypothetical probabilistic models based on historical parameters. They do not forecast actual returns or guarantee future performance.
2. **Stationary Historical Covariance:** Baseline simulations assume return distributions are stationary over the simulation horizon. Regime changes and structural breaks are not modeled.
3. **Bounded Computation:** Maximum paths are limited to $10,000$ and horizon to $252$ trading days to prevent server memory exhaustion.
4. **No Options / Non-Linear Derivatives:** Asset return compounding applies to linear cash equity holdings; options pricing and Greeks are out of scope.
5. **No Cross-Currency FX Modeling:** Portfolios must consist of homogeneous currency assets; cross-currency FX conversion is deferred.

---

## 7. Quality Gate Confirmation

- [x] Pre-coding repository audit and financial contracts documented.
- [x] Pure deterministic Monte Carlo simulation engine implemented.
- [x] Empirical and parametric VaR and CVaR implemented with strict loss-sign convention ($L = V_0 - V_T$).
- [x] Multivariate Student-t distribution extension implemented with calibrated covariance.
- [x] Spectral positive semidefiniteness covariance projection verified.
- [x] Relational persistence with Alembic migration `f5a6b7c8d9e0` verified.
- [x] Authenticated REST API with tenant isolation verified.
- [x] Institutional React 19 / TypeScript `MonteCarloPage.tsx` integrated.
- [x] 100% backend test pass rate (216 passed, 0 failed).
- [x] 100% frontend test pass rate (14 passed, 0 failed).
- [x] Frontend production build succeeded (`tsc -b && vite build`).
- [x] Master Plan, Architecture, Requirements, and Test Strategy updated.
