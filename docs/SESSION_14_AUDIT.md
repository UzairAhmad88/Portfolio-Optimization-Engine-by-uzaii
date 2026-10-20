# SESSION 14 AUDIT — Monte Carlo Simulation, Probabilistic Risk Analysis, VaR & CVaR

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-18  
**Author:** Quantitative Finance Platform Engineer & System Architect  
**Project:** Quant Portfolio Optimization Engine & Quant Research Dashboard  
**Status:** Pre-Implementation Architectural Baseline  

---

## 1. Executive Summary & Verification of Baseline

The platform has completed Sessions 01 through 13. The codebase features:
- Core financial mathematics: simple/log returns, annualization, sample/population variance, covariance, correlation, maximum drawdown, downside deviation, Sharpe, and Sortino ratios.
- Portfolio definitions: asset validation, long-only box constraints, sector caps, and feasibility checks.
- Numerical optimization: Global Minimum Variance (GMV), Maximum Sharpe Ratio (Tangency), Target Return, and Equal-Weight baselines via SciPy SLSQP.
- Efficient frontier generation and portfolio comparison analytics.
- Persistent market data: PostgreSQL / SQLite storage with SQLAlchemy 2.0 and Alembic migrations.
- Authentication & security: JWT access tokens, HttpOnly session cookies, brute-force rate-limiting, dataset tenant isolation, and RBAC (`researcher`, `admin`).
- Walk-forward backtesting: discrete simple compounding, weight drift, multi-frequency rebalancing, basis-point transaction costs and execution slippage, with Alembic migration `8993dbd79e8a`.
- Scenario analysis & stress testing: instantaneous asset shocks preserving unshocked cash, historical window replay without data fabrication, covariance stress with spectral positive semidefiniteness (PSD) projection, parametric sensitivity sweeps, and Alembic migration `e4f5a6b7c8d9`.
- Current test verification: **196 backend tests passed** (100%), **12 frontend Vitest tests passed** (100%), and **zero TypeScript build errors** (`tsc -b && vite build`).
- Current Alembic head revision: `e4f5a6b7c8d9` (`scenario_runs` table).

---

## 2. Reusable Functionality & Architectural Alignment

### 2.1 Domain Quantitative Core (`backend/app/quant/`)
- `returns.py`: Provides `simple_returns(prices_df)` and `periodic_mean_returns(returns_df)`.
- `covariance.py`: Provides `covariance_matrix(returns_df, ddof=1)` and `correlation_matrix(returns_df)`.
- `risk.py`: Provides `variance`, `volatility`, `annualized_volatility`, `downside_deviation`, `maximum_drawdown`, `annual_to_periodic_rate`.
- *Missing in domain risk:* Formal empirical and parametric Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR / Expected Shortfall) functions with explicit loss-sign conventions.

### 2.2 Market Data & Portfolio Services (`backend/app/market_data/`, `backend/app/portfolio/`)
- `get_dataset_rows(dataset_id)`: Fetches price bars from relational DB or in-memory fallback.
- `get_dataset_assets(dataset_id)`: Provides canonical asset identities (`TICKER:MARKET`) and currency metadata.
- Currency validation pattern from `backend/app/scenarios/service.py` (`prepare_scenario_data`): Verifies currency homogeneity across portfolio constituents and rejects mixed-currency portfolios (e.g. USD and PKR) with HTTP 422.

### 2.3 Persistence & Database Layer (`backend/app/db/`)
- SQLAlchemy 2.0 declarative models with `UserModel`, `DatasetModel`, `BacktestRunModel`, and `ScenarioRunModel`.
- Pattern for storing simulation metadata: foreign keys to `users.id` (with cascade delete) and `datasets.id`, JSON columns for configuration, results, and warnings.
- Migration head: `e4f5a6b7c8d9`. A new migration revision will be generated with `down_revision = 'e4f5a6b7c8d9'`.

### 2.4 Transport Layer & Security (`backend/app/api/v1/`, `backend/app/auth/`)
- `get_current_active_user` enforces authentication on all analytical endpoints.
- `check_dataset_access(session, dataset_id, user)` enforces tenant isolation on datasets.
- Route responses adhere to sanitized JSON structures without exposing stack traces.

---

## 3. Financial Assumptions & Mathematical Scope for Session 14

### 3.1 Return Convention & Distributional Models
1. **Periodic Return Convention:** Discrete simple returns $r_t = \frac{P_t - P_{t-1}}{P_{t-1}}$.
2. **Multivariate Normal Baseline:**
   $$r_t = \mu + L z_t, \quad z_t \sim \mathcal{N}(0, \mathbf{I})$$
   where $\mathbf{\Sigma} = L L^T$ via Cholesky factorization. If $\mathbf{\Sigma}$ has numerical rounding issues, spectral positive semidefiniteness (PSD) projection will be applied.
3. **Multivariate Student-t Model:**
   For heavy-tailed financial returns, support multivariate Student-t with degrees of freedom $\nu > 2$:
   $$r_t = \mu + \sqrt{\frac{\nu}{W_t}} L z_t, \quad W_t \sim \chi^2_\nu, \quad z_t \sim \mathcal{N}(0, \mathbf{I})$$
   where the scale matrix is calibrated such that $\text{Cov}(r_t) = \mathbf{\Sigma}$ (by scaling factor $\sqrt{\frac{\nu - 2}{\nu}}$).
4. **Reproducibility:** Seeded pseudo-random number generator using NumPy's modern Generator API (`np.random.default_rng(seed)`).

### 3.2 Portfolio Evolution & Cash Treatment
1. **Buy-and-Hold Compounding (Default):**
   $$V_{i,t} = V_{i,t-1}(1 + r_{i,t})$$
   $$V_t = C + \sum_{i=1}^n V_{i,t}$$
   Natural weight drift is preserved; no rebalancing friction.
2. **Periodic Rebalanced Portfolio:**
   $$V_t = V_{t-1}(1 + \mathbf{w}^T \mathbf{r}_t)$$
   Simulates target weights being re-established at each period $t$.
3. **Terminal Loss Definition & Sign Convention:**
   $$\text{Loss } L = V_0 - V_T \quad (\text{monetary})$$
   $$L_{\%} = -\frac{V_T - V_0}{V_0} \quad (\text{fractional})$$
   **Positive VaR and CVaR represent positive losses.** A 95% 1-year VaR of $150,000 means there is a 5% probability of losing \$150,000 or more.

### 3.3 VaR and CVaR Quantile Conventions
1. **Empirical VaR:** For sample losses $\{L_1, \dots, L_M\}$ sorted in ascending order, $\operatorname{VaR}_q = Q_q(L)$. The quantile method will use standard linear interpolation (`numpy.quantile(losses, q, method='linear')`).
2. **Empirical CVaR:** Expected loss conditional on exceeding or equaling VaR:
   $$\operatorname{CVaR}_q = \mathbb{E}[L \mid L \ge \operatorname{VaR}_q]$$
   For finite discrete samples, calculated as the mean of all losses $\ge \operatorname{VaR}_q$.
3. **Parametric & Historical Benchmarks:**
   - Parametric VaR: $\operatorname{VaR}_q^{\text{param}} = V_0 \cdot \left(- \mu_p \cdot T + z_q \cdot \sigma_p \sqrt{T}\right)$
   - Historical VaR: Empirical quantile of historical rolling/periodic losses from actual dataset observations.

### 3.4 Resource & Simulation Bounds
- Maximum paths $M$: 10,000 paths (prevents memory explosion and CPU denial-of-service). Default: 1,000.
- Maximum horizon $T$: 252 trading days (1 year). Default: 21 days (1 trading month).
- Maximum sample paths sent to frontend for visualization: 50 paths (plus median, 5th, and 95th percentile curves).

---

## 4. Integration Risks & Mitigations

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| Non-positive-semidefinite covariance matrix | Cholesky factorization failure (`LinAlgError`) | Detect non-PSD via eigenvalue decomposition; apply spectral projection or fallback to SVD/eigen-decomposition factor $L = Q \sqrt{\Lambda^+}$. |
| Severe cumulative loss ($V_{i,t} \le 0$) | Negative asset prices or runaway compounding | Enforce limited liability: asset prices floor at 0.0 ($r_{i,t} \ge -1.0$). Report warnings if bankruptcies occur in simulated paths. |
| Memory bloat from dense $M \times T \times N$ arrays | Server Out-of-Memory on large runs | Compute terminal portfolio values and aggregate distributions in memory; store only summarized distributions and downsampled sample paths ($K \le 50$) in persistence. |
| Mixed currency portfolio input | Invalid financial valuation across USD / PKR | Re-use strict currency validation from Session 13; reject heterogeneous currencies with HTTP 422. |
| Unreproducible test failures | Flaky statistical tests | Fix random seeds explicitly in tests; use statistically wide tolerance intervals based on Central Limit Theorem standard errors ($\pm 3 \times \sigma / \sqrt{M}$). |

---

## 5. Session 14 Implementation Plan

1. **Financial Risk Contracts:** Write `docs/PROBABILISTIC_RISK_CONTRACTS.md` defining all conventions, equations, distribution choices, and disclaimers.
2. **Domain Mathematical Engine (`backend/app/quant/var_cvar.py` & `backend/app/risk_simulation/`):**
   - Pure VaR and CVaR functions (empirical, parametric, historical).
   - Pure Monte Carlo path generator with multivariate normal and Student-t models.
   - Deterministic seed control and numerical diagnostics.
3. **Relational Persistence & Migration:**
   - Define `RiskSimulationRunModel` in `backend/app/db/models.py`.
   - Create Alembic revision `f5a6b7c8d9e0_create_risk_simulation_runs_table.py`.
   - Apply migration to local SQLite test database.
4. **Service & API Layer (`backend/app/risk_simulation/` & `backend/app/api/v1/`):**
   - `models.py`: Pydantic request/response schemas.
   - `service.py`: Dataset authorization, covariance estimation, simulation dispatch, and run persistence.
   - `risk_simulation_routes.py`: Endpoints for `/api/v1/risk-simulations`, `/var-cvar`, and run CRUD.
   - Wire router into `backend/app/api/v1/routes.py`.
5. **Backend Automated Tests:**
   - `backend/tests/test_risk_simulation_engine.py`: Pure mathematical tests (hand-calculated VaR/CVaR, moment convergence, seed reproducibility, Student-t).
   - `backend/tests/test_risk_simulation_api.py`: API integration, tenant isolation, and validation limits.
6. **Frontend Integration (`frontend/`):**
   - `types/api.ts`: Add risk simulation and VaR/CVaR interfaces.
   - `api/client.ts`: Add simulation API methods.
   - `components/pages/MonteCarloPage.tsx`: Interactive workspace with distribution histogram, fan chart, estimator comparison, and run history.
   - Sidebar, Header, App.tsx, OverviewPage.tsx integration.
   - Vitest unit tests in `api-client.test.ts` and `App.test.tsx`.
7. **Documentation & Quality Gates:**
   - Update `MASTER_PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `REQUIREMENTS_SPEC.md`, `TEST_STRATEGY.md`.
   - Create `docs/SESSION_14_REPORT.md`.
   - Run pytest, vitest, and `npm run build`.

---

## 6. Acceptance Criteria

1. Mathematical tests confirm empirical VaR and CVaR match independent hand-calculated benchmarks.
2. Monte Carlo paths are 100% deterministic given identical inputs and random seed.
3. Both Multivariate Normal and Multivariate Student-t distributions are mathematically verified.
4. Multi-estimator comparison provides Monte Carlo, Parametric, and Historical VaR/CVaR side by side.
5. All database operations are tenant-isolated; User B cannot retrieve or delete User A's runs.
6. The frontend renders actual simulation distributions, loss histograms, and fan charts with zero decorative mock data.
7. 100% passing backend tests, 100% passing frontend tests, and clean production build.
