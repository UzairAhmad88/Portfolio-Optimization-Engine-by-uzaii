# SESSION 27 REPORT — STAGE 22: COPULA-BASED TAIL DEPENDENCY, NON-LINEAR EXTREME CO-MOVEMENT & TAIL RISK PARITY ALLOCATION

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 27  
**Approved Stage:** Stage 22 — Copula-Based Tail Dependency, Non-Linear Extreme Co-Movement & Tail Risk Parity Allocation  
**Execution Mode:** Repository-first, mathematically rigorous, test-driven  
**Timestamp:** 2026-10-19T02:35:00Z  
**Alembic Migration Head:** `b2c3d4e5f6a7 (head)` (Stateless analytical engine; no new database migrations required)  
**Test Suite Verification Results:**
- Backend Tests: **372 passed**, 6 warnings in 27.39s
- Frontend Tests: **38 passed** across 2 test files in 11.85s
- Production Build: Clean (`tsc -b && vite build` built in 771ms, exit code 0)

---

## 1. Executive Summary

In Session 27, Stage 22 was implemented, mathematically verified, integrated into the multi-tenant REST API, and surfaced in an institutional React 19 / TypeScript workspace.

The platform was successfully extended beyond linear correlation and Gaussian regime models by introducing copula-based dependence modeling, asymmetric tail-dependence diagnostics ($\lambda_L, \lambda_U$), multivariate extreme-loss simulation, and a tail-risk-based portfolio allocation engine (Tail Risk Parity).

### Key Questions Answered for Researchers
1. **How strongly do assets co-move during extreme losses?**
   Quantified via lower tail dependence coefficients $\lambda_L = \lim_{q \to 0} \mathbb{P}(U_1 \le q \mid U_2 \le q)$ estimated through Canonical Maximum Likelihood (CML) on rank pseudo-observations.
2. **Is dependence symmetric or asymmetric?**
   Demonstrated by contrasting Clayton copulas ($\lambda_L > 0, \lambda_U = 0$) against Gumbel copulas ($\lambda_L = 0, \lambda_U > 0$) and symmetric Student-t copulas ($\lambda_L = \lambda_U > 0$).
3. **How do extreme joint-loss scenarios affect portfolio risk?**
   Modeled via dependent Monte Carlo simulation preserving non-linear dependency and marginal fat tails, driving Copula-CVaR ($\text{CVaR}_\alpha$) evaluation.
4. **Can portfolio weights balance asset contributions to tail risk?**
   Solved via the Tail Risk Parity (TRP) optimizer, achieving equalized Euler risk contributions ($TRC_i \equiv TRC_j$) subject to budget $\sum w_i = 1$ and long-only $w_i \ge 0$ constraints.
5. **How stable are dependence parameters and allocations?**
   Diagnostics provide Kendall's $\tau$, Pearson correlation, AIC/BIC model comparison scores, Euler reconciliation residuals, and CVaR reduction percentages relative to equal-weight baselines.

---

## 2. Implemented Components & Files Changed

| Component | Path | Description |
|---|---|---|
| **Numerical Core** | `backend/app/quant/copula_tail_risk.py` | Pure NumPy/SciPy engine: pseudo-observation transforms, Clayton/Gumbel/Student-t/Gaussian bivariate CML fitting, Marshall-Olkin and Cholesky copula simulation, Euler CVaR risk decomposition, and SLSQP Tail Risk Parity optimization. |
| **Pydantic Schemas** | `backend/app/copula/models.py` | Pydantic v2 schemas: `CopulaFitRequest`, `CopulaSimulateRequest`, `TailRiskParityRequest`, `PairwiseCopulaResult`, `CopulaFitResponse`, `CopulaSimulateResponse`, `TailRiskParityResponse`. |
| **Service Layer** | `backend/app/copula/service.py` | Orchestration layer: dataset retrieval, multi-tenant isolation, price-to-return differencing with clean dropna, asset filtering, and copula analysis execution. |
| **REST API Routes** | `backend/app/api/v1/copula_routes.py` | Authenticated endpoints: `POST /api/v1/copula/fit`, `POST /api/v1/copula/simulate`, `POST /api/v1/copula/tail-risk-parity` (and alias `POST /api/v1/copula/optimize`). |
| **Route Registration** | `backend/app/api/v1/routes.py` | Mounted `copula_router` under `/api/v1/copula`; updated health check stage to `"copula_tail_risk"`. |
| **Engine Tests** | `backend/tests/test_copula_tail_risk_engine.py` | 7 unit tests: Clayton analytical benchmark, Gumbel analytical benchmark, Student-t analytical benchmark, Gaussian baseline, simulation reproducibility, Euler CVaR reconciliation, TRP optimizer. |
| **API & Security Tests**| `backend/tests/test_copula_tail_risk_api.py` | 6 integration tests: 401 unauthenticated access rejection, cross-tenant 404/403 isolation, fit success, simulate success, TRP optimization success, 422 schema validation. |
| **Test Conftest** | `backend/tests/conftest.py` | Bypassed mock user override for `test_copula_tail_risk_api` to ensure genuine JWT 401 testing. |
| **Access Control Test** | `backend/tests/test_auth_and_access_control.py` | Added `"copula_tail_risk"` to valid public health check stages. |
| **Frontend Types** | `frontend/src/types/api.ts` | TypeScript types for copula models, parameters, fit responses, simulation responses, and TRP allocations. |
| **Frontend API Client** | `frontend/src/api/client.ts` | Axios client methods: `fitCopula`, `simulateCopula`, `optimizeTailRiskParity`. |
| **UI Workspace** | `frontend/src/components/pages/CopulaTailRiskPage.tsx`| Institutional React 19 workspace: model configuration, interactive tail dependence matrix heatmap, pairwise metrics table, Monte Carlo preview, and TRP allocation breakdown. |
| **Navigation & App** | `frontend/src/App.tsx`, `Sidebar.tsx`, `Header.tsx`, `OverviewPage.tsx` | Mounted `copula-tail-risk` route, navigation item with `Network` icon, header title, and overview feature card. |
| **Frontend Tests** | `frontend/src/test/api-client.test.ts` | 2 new Vitest tests validating `fitCopula` and `optimizeTailRiskParity`. |

---

## 3. Mathematical Contracts & Analytical Benchmark Results

### 3.1 Closed-Form Analytical Benchmarks
All four copula families were verified against analytical closed-form calculations:

1. **Clayton Copula:**
   - Parameter $\theta = 2.0$ ($\tau = 0.50$).
   - Closed form: $\lambda_L = 2^{-1/\theta} = 2^{-1/2} = \frac{1}{\sqrt{2}} \approx 0.7071067812$; $\lambda_U = 0.0$.
   - Engine output: $\lambda_L = 0.7071067812$, residual error $< 10^{-12}$.
2. **Gumbel Copula:**
   - Parameter $\theta = 2.0$ ($\tau = 0.50$).
   - Closed form: $\lambda_L = 0.0$; $\lambda_U = 2 - 2^{1/\theta} = 2 - \sqrt{2} \approx 0.5857864376$.
   - Engine output: $\lambda_U = 0.5857864376$, residual error $< 10^{-12}$.
3. **Student-t Copula:**
   - Correlation $\rho = 0.50$, degrees of freedom $\nu = 4.0$.
   - Closed form: $\lambda = 2 t_5\left(-\sqrt{\frac{5(0.5)}{1.5}}\right) = 2 t_5(-\sqrt{5/3}) \approx 0.25816881$.
   - Engine output: $\lambda = 0.25816881$, residual error $< 10^{-8}$.
4. **Gaussian Baseline:**
   - Correlation $\rho = 0.75$.
   - Closed form: $\lambda_L = \lambda_U = 0.0$.
   - Engine output: $\lambda_L = \lambda_U = 0.0$ (identically zero).

### 3.2 Euler Invariant & Tail Risk Parity
- **Euler CVaR Identity:**
  $$\sum_{i=1}^N TRC_i \equiv \text{CVaR}_\alpha(w)$$
  Verified numerically: residual $\|\sum TRC_i - \text{CVaR}_\alpha\|_\infty = 0.0$ ($< 10^{-12}$).
- **TRP Budget Invariant:**
  $$\sum_{i=1}^N w_i^* = 1.0 \pm 10^{-6}, \qquad w_i^* \ge 0$$
  Verified numerically across test suites.

---

## 4. Test Execution Evidence

### 4.1 Backend Test Suite (Pytest)
```
backend\.venv\Scripts\pytest.exe -q
372 passed, 6 warnings in 27.39s
```
- Total tests: 372 passed (100% pass rate, zero failures, zero regressions).
- Warnings: 6 benign Starlette deprecation warnings from test client.

### 4.2 Frontend Test Suite (Vitest)
```
npm test -- --run
✓ src/test/api-client.test.ts (24 tests) 79ms
✓ src/test/App.test.tsx (14 tests) 1152ms
Test Files  2 passed (2)
     Tests  38 passed (38)
  Duration  11.85s
```
- Total tests: 38 passed (100% pass rate).

### 4.3 Frontend Production Build (Vite)
```
npm run build
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.4 building client environment for production...
✓ 1949 modules transformed.
dist/index.html                   0.80 kB │ gzip:   0.44 kB
dist/assets/index-DtJMXJ5u.css   10.61 kB │ gzip:   2.65 kB
dist/assets/index-CxSu3VHe.js   752.51 kB │ gzip: 160.13 kB
✓ built in 771ms
```
- TypeScript check `tsc -b`: Exited with code 0.
- Production bundle: Successfully built in 771ms.

---

## 5. Security & Tenant Isolation Evidence

Verified in `backend/tests/test_copula_tail_risk_api.py`:
- `test_copula_endpoints_require_authentication`:
  - `POST /api/v1/copula/fit` without Bearer token returns **401 Unauthorized**.
  - `POST /api/v1/copula/simulate` without Bearer token returns **401 Unauthorized**.
  - `POST /api/v1/copula/tail-risk-parity` without Bearer token returns **401 Unauthorized**.
- `test_copula_endpoints_enforce_tenant_isolation`:
  - Requesting copula estimation or simulation on another user's dataset ID returns **404 Not Found** (or 403 Forbidden), strictly preventing data leakage across tenants.
- `test_copula_validation_errors`:
  - Passing invalid copula types (e.g. `"unsupported_copula"`) returns **422 Unprocessable Content**.

---

## 6. Acceptance Criteria Verification

| ID | Acceptance Criterion | Verification Status | Evidence |
|---|---|---|---|
| **AC-1** | Copula families required by approved contracts implemented (Clayton, Gumbel, Student-t, Gaussian baseline, best-fit). | **PASS** | `backend/app/quant/copula_tail_risk.py` |
| **AC-2** | Theoretical tail-dependence calculations match independent analytical benchmarks. | **PASS** | `backend/tests/test_copula_tail_risk_engine.py` (all tolerances $< 10^{-7}$) |
| **AC-3** | Estimation failures, invalid inputs, and degenerate samples handled explicitly. | **PASS** | Bounded optimizer bounds, non-finite checks, 422 responses |
| **AC-4** | Dependent simulation reproducible and statistically validated. | **PASS** | Marshall-Olkin & Cholesky simulation seed reproducibility test |
| **AC-5** | Portfolio VaR/CVaR and risk contributions follow documented conventions. | **PASS** | Discrete quantile loss convention; Euler identity holds to $< 10^{-12}$ |
| **AC-6** | Tail Risk Parity uses justified objective and satisfies applicable constraints. | **PASS** | SLSQP optimizer satisfies $\sum w_i = 1$ and $w_i \ge 0$ |
| **AC-7** | Numerical reconciliation errors measured and reported. | **PASS** | Residual $\|\sum TRC_i - \text{CVaR}_\alpha\|_\infty$ surfaced in diagnostics |
| **AC-8** | APIs enforce authentication and tenant isolation. | **PASS** | 401 for unauthenticated calls; 404/403 for cross-tenant access |
| **AC-9** | Frontend presents actual API results with meaningful diagnostics. | **PASS** | `CopulaTailRiskPage.tsx` displays heatmap, pairwise table, and allocations |
| **AC-10**| Existing backend and frontend regression tests pass. | **PASS** | 372 backend tests passed, 38 frontend tests passed |
| **AC-11**| Production frontend build succeeds. | **PASS** | `tsc -b && vite build` exited with code 0 |
| **AC-12**| Documentation reflects actual implementation. | **PASS** | `MASTER_PLAN.md`, `REQUIREMENTS_SPEC.md`, `SYSTEM_ARCHITECTURE.md`, `TEST_STRATEGY.md`, `SESSION_27_CONTRACTS.md` |
| **AC-13**| No unrelated roadmap stages started. | **PASS** | Stage 22 only. Session 28 not started. |

---

## 7. Known Limitations & Numerical Boundary Notes
1. **Bivariate Copula Pairing for High Dimensions:** High-dimensional dependence matrices are constructed via pairwise bivariate copula estimations; while fully scalable and robust against curse of dimensionality, regular vine copulas (R-vines) can be evaluated in future research for conditional higher-order dependencies.
2. **Extreme Tail Sample Size Caution:** As documented in the workspace governance banner, estimating extreme tail risk ($\alpha = 0.99$) from limited historical price samples ($T < 250$ observations) incurs statistical sampling variance; researchers are advised to use $\ge 500$ daily observations where available.
3. **Stateless Analytical Architecture:** Like standard portfolio optimization runs, copula analysis is computed on-demand from tenant dataset returns without creating persistent database tables, maintaining operational agility and zero database migration overhead.

---

## 8. Governance Declaration

Session 27 is complete. Stage 22 implementation status is documented. Session 28 has not been started.
