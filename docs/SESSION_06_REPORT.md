# SESSION 06 REPORT — Portfolio Optimization Engine
**Document Version:** 1.0.0  
**Status:** Complete & Independently Verified  
**Date:** 2026-10-17  
**Author:** Quantitative Finance Software Engineering, Numerical Optimization & Architecture Team  

---

## 1. Executive Summary

In **Session 06**, we implemented the first production-grade, mathematically verified **Portfolio Optimization Engine** for the Quant Portfolio Optimization Engine.

Every returned portfolio is computed using actual numerical optimization via **SciPy's Sequential Least Squares Programming (SLSQP)** solver equipped with exact analytical gradients, rather than approximations or mock heuristics. The engine enforces typed input and output contracts, validates mathematical and constraint feasibility prior to optimization, independently verifies constraint satisfaction on returned weights, recalculates all return and risk metrics using the pure mathematical core, and returns comprehensive diagnostic information for independent verification.

---

## 2. Baseline Test Results Prior to Implementation

Before modifying code or adding optimization functionality, the existing test suite was executed against the repository:
- **Baseline Test Count:** 85 passed
- **Baseline Execution Time:** 7.18s
- **Baseline Suite Status:** 100% clean pass across market data ingestion, dataset registry, validation engine, API contracts, financial mathematics, and portfolio definition/constraint engines.

---

## 3. Solver Selection & Technical Rationale

### 3.1 Installed Environment Inspection
- **Python Version:** 3.11.16
- **NumPy Version:** 2.4.6
- **Pandas Version:** 3.0.6
- **SciPy Version:** 1.17.1
- **FastAPI Version:** 0.143.2
- **Pydantic Version:** 2.14.1

### 3.2 Solver Choice: SciPy SLSQP (`scipy.optimize.minimize(method="SLSQP")`)
We selected **SciPy SLSQP** as the sole optimization solver for the following architectural and mathematical reasons:
1. **Dependency Discipline:** SciPy 1.17.1 is already present in the active environment; CVXPY is not installed. Introducing CVXPY or OS-specific C solvers would require additional binary dependencies without functional necessity for the supported continuous problem class.
2. **Supported Problem Class:** SLSQP solves constrained minimization of smooth nonlinear/quadratic objective functions subject to linear equality constraints ($\sum w_i = W_{\text{target}}$), box bounds ($l_i \le w_i \le u_i$), and linear/nonlinear inequality constraints ($\sum |w_i| \le \text{Gross}_{\max}$).
3. **Exact Analytical Gradients:** Rather than relying on noisy finite-difference numerical approximations, our engine supplies exact analytical gradients:
   - For Minimum Variance:
     $$f(\mathbf{w}) = \frac{1}{2}\mathbf{w}^T \mathbf{\Sigma} \mathbf{w} \implies \nabla f(\mathbf{w}) = \mathbf{\Sigma} \mathbf{w}$$
   - For Maximum Sharpe Ratio:
     $$f(\mathbf{w}) = -\frac{\mathbf{w}^T \boldsymbol{\mu} - R_f}{\sigma_p(\mathbf{w})} \implies \nabla f(\mathbf{w}) = -\frac{\boldsymbol{\mu}}{\sigma_p(\mathbf{w})} + \frac{(\mu_p(\mathbf{w}) - R_f) \mathbf{\Sigma} \mathbf{w}}{\sigma_p(\mathbf{w})^3}$$
4. **Feasible Analytical Initialization:** Rather than using arbitrary or non-feasible initial points, our engine calculates a strictly feasible starting point $\mathbf{w}_0$ via analytical convex interpolation between lower and upper bounds:
   $$\alpha = \frac{W_{\text{target}} - \sum l_i}{\sum u_i - \sum l_i}, \quad \mathbf{w}_0 = (1 - \alpha)\mathbf{l} + \alpha \mathbf{u}$$
   This guarantees that $l_i \le w_{0,i} \le u_i$ and $\sum w_{0,i} = W_{\text{target}}$ on step 0, accelerating convergence and eliminating initialization-induced constraint violations.

---

## 4. Objectives Implemented

| Objective | Mathematical Formulation | Solver & Method | Description |
|---|---|---|---|
| **Minimum Variance** | $\min_{\mathbf{w}} \frac{1}{2} \mathbf{w}^T \mathbf{\Sigma} \mathbf{w}$ | SciPy SLSQP (Exact $\nabla$) | Global minimum variance portfolio on the Markowitz efficient frontier. Fully convex quadratic program. |
| **Maximum Sharpe Ratio** | $\max_{\mathbf{w}} \frac{\mathbf{w}^T \boldsymbol{\mu} - R_f}{\sqrt{\mathbf{w}^T \mathbf{\Sigma} \mathbf{w}}}$ | SciPy SLSQP (Exact $\nabla$, multi-start) | Tangency portfolio maximizing risk-adjusted excess return per unit of annualized volatility. |
| **Equal-Weight Baseline** | $w_i = \frac{W_{\text{target}}}{N}$ | Deterministic Closed-Form | Benchmark allocation for comparison; verified against constraints. Not an optimization result. |

---

## 5. Supported & Unsupported Constraints

### 5.1 Supported Constraints
- **Per-Asset Weight Bounds:** $l_i \le w_i \le u_i$ for all assets $i \in \{1, \dots, N\}$.
- **Total Target Weight:** $\sum_{i=1}^N w_i = W_{\text{target}}$ (e.g. fully invested $1.0$, cash-buffered $< 1.0$, or leveraged $> 1.0$).
- **Long-Only Allocations:** $w_i \ge 0, \sum w_i = 1.0$.
- **Long-Short Allocations:** $w_i \in \mathbb{R}$ when `allow_short=True`.
- **Gross Exposure Limits:** $\sum |w_i| \le \text{Gross}_{\max}$.
- **Inclusion / Exclusion Rules:** Enforced directly via resolved bounds ($l_i = u_i = 0$ for excluded, $l_i \ge 10^{-4}$ for included).

### 5.2 Explicitly Unsupported in this Session
- **Mixed-Integer Constraints:** Cardinality constraints (e.g. "hold at most $K$ assets") or minimum trade sizes are not supported by continuous SLSQP and fail with an explicit validation error.
- **Turnover / Transaction Costs:** Deferred to Stage 7 Backtesting engine.
- **Factor Constraints / Group Constraints:** Sector/industry group constraints deferred to Stage 5.

---

## 6. Financial Conventions & Calculation Standards

1. **Discrete Simple Returns:** Historical asset returns are calculated using discrete arithmetic percentage returns:
   $$r_{t,i} = \frac{P_{t,i}}{P_{t-1,i}} - 1$$
2. **Authoritative Price Selection:** Backward split-adjusted close (`adjusted_close`) is used when present; if unadjusted `close` is used, an explicit warning is attached to the result.
3. **Synchronized Observation Invariant:** Only common trading observation dates across all selected assets are retained via listwise inner join (`dropna(how="any")`). At least 2 common dates are required.
4. **Annualization Conventions:**
   - Arithmetic Expected Return: $\hat{\mu}_{\text{ann}} = m \hat{\mu}_{\text{periodic}}$
   - Covariance Matrix: $\mathbf{\Sigma}_{\text{ann}} = m \mathbf{\Sigma}_{\text{periodic}}$
   - Where $m$ is the trading period scale factor (252 for US, 250 for PSX).
   - These arithmetic annualization conventions are explicitly decoupled from geometric CAGR.
5. **Risk-Free Rate Handling:**
   - When `annualized=True`, $R_f$ is interpreted as an annual effective rate matching annualized return and annualized volatility.
   - When `annualized=False`, $R_f$ is converted to periodic effective rate using exact compounding:
     $$r_p = (1 + R_f)^{1/m} - 1$$
6. **Non-Positive Excess Return Safeguard:**
   If $\max_i \mu_i \le R_f$, Sharpe ratio maximization is economically invalid (it creates a perverse incentive to increase volatility to make a negative ratio closer to zero). The engine terminates immediately with status `NON_POSITIVE_EXCESS_RETURNS` without claiming an optimum.

---

## 7. Numerical Validation Strategy & Invariants

| Invariant / Check | Enforcement Mechanism | Failure Action |
|---|---|---|
| **Matrix Symmetry** | $\max \|\mathbf{\Sigma} - \mathbf{\Sigma}^T\| \le 10^{-10}$ | Reject with `OptimizationError` |
| **Positive Semi-Definiteness** | Eigenvalues $\lambda_i \ge -10^{-8}$ via `np.linalg.eigvalsh` | Reject with `OptimizationError` |
| **Matrix Conditioning** | Condition number $\kappa = \lambda_{\max} / \max(\lambda_{\min}, 10^{-16})$ | Warning if $\kappa > 10^{10}$ or $\lambda_{\min} \le 10^{-12}$ |
| **Pre-Optimization Feasibility** | $\sum l_i \le W_{\text{target}} \le \sum u_i$ | Terminate with `INFEASIBLE` status |
| **Independent Weight Verification** | `validate_weights_against_constraints(weights, assets, constraints, tol=1e-5)` | Flag violation; mark `is_feasible=False` |
| **Independent Metric Recalculation** | Recompute variance, volatility, return, and Sharpe from weights via Session 04 core | Guaranteed reconcile with pure math |
| **Near-Zero Volatility** | If $\sigma_p \le 10^{-8}$ | Sharpe ratio set to `None` with explicit warning |

---

## 8. API Integration

We introduced the typed endpoint:
```
POST /api/v1/portfolios/optimize
```
- **Execution:** CPU-bound solver logic runs in worker threadpool via `run_in_threadpool`, ensuring the async event loop is never blocked.
- **Request Model:** `OptimizationRequest` (wrapping `PortfolioDefinition`, `objective`, `risk_free_rate`, `annualized`, `periods_per_year`).
- **Response Model:** `OptimizationResponse` (optimal weights, verified metrics, solver diagnostics, constraint violations, warnings, errors).
- **HTTP Status Codes:**
  - `200 OK`: Successful optimization with feasible weights.
  - `404 Not Found`: Dataset ID missing from registry.
  - `422 Unprocessable Entity`: Contradictory constraints, cross-currency portfolios, non-positive excess returns, or solver divergence, returning a structured diagnostic payload.

---

## 9. Deterministic Tests Added & Independent Numerical Verification

A comprehensive test suite of **23 deterministic and analytical tests** was implemented in `backend/tests/test_optimization_engine.py`:

### 9.1 Independent Analytical Verification Cases
1. **Single-Asset Minimum Variance:**
   - 1 asset with $\sigma = 0.20 \implies w^* = 1.0, \sigma_p = 0.20, \sigma_p^2 = 0.04$. Verified to machine precision.
2. **Two-Asset Uncorrelated Minimum Variance:**
   - Analytical solution: $w_1^* = \frac{\sigma_2^2}{\sigma_1^2 + \sigma_2^2} = \frac{0.04}{0.05} = 0.80$, $w_2^* = 0.20$.
   - Solver result: $w_1 = 0.800000, w_2 = 0.200000$. Matches analytical formula within $10^{-6}$.
3. **Two-Asset Correlated Minimum Variance:**
   - $\sigma_1 = 0.15, \sigma_2 = 0.25, \rho = 0.50 \implies w_1^* = \frac{35}{38} \approx 0.921053, w_2^* = \frac{3}{38} \approx 0.078947$.
   - Solver result: matches analytical solution within $10^{-5}$.
4. **Three-Asset Uncorrelated Equal Variance:**
   - $\sigma_1 = \sigma_2 = \sigma_3 = 0.20 \implies w_i^* = 1/3 \approx 0.333333$. Verified within $10^{-5}$.
5. **Two-Asset Maximum Sharpe Tangency Portfolio:**
   - $\boldsymbol{\mu} = [0.12, 0.08]^T, \mathbf{\Sigma} = \operatorname{diag}(0.04, 0.01), R_f = 0.02$.
   - Tangency weights: $\tilde{\mathbf{w}} = \mathbf{\Sigma}^{-1}(\boldsymbol{\mu} - R_f \mathbf{1}) = [2.5, 6.0]^T \implies \mathbf{w}^* = [5/17, 12/17]^T \approx [0.294118, 0.705882]^T$.
   - Solver result: matches analytical solution within $10^{-4}$.
   - Independent recalculation of Sharpe ratio matches returned metric.
6. **Active Per-Asset Bounds:**
   - Upper bound $w_1 \le 0.50$ forces redistribution to $w = [0.50, 0.50]$.
7. **Negative Excess Returns Handling:**
   - When $\max \mu_i \le R_f$, solver terminates with `NON_POSITIVE_EXCESS_RETURNS` without claiming an optimum.
8. **Near-Zero Volatility:**
   - Handled gracefully without division by zero.
9. **Singular & Collinear Covariance:**
   - Perfect collinearity ($\rho = 1.0$) detected; condition number warning emitted without crashing.
10. **Non-PSD & Asymmetric Covariance Rejection:**
    - Confirmed immediate rejection with `OptimizationError`.
11. **Equal-Weight Baseline:**
    - Confirmed $w_i = 1/N$; confirmed `INVALID_FOR_CONSTRAINTS` when $1/N > u_i$.
12. **End-to-End API Integration:**
    - Tested Minimum-Variance, Maximum-Sharpe, and Equal-Weight endpoints via FastAPI TestClient.
    - Verified HTTP 404 on missing dataset and HTTP 422 on infeasible constraints.

---

## 10. Final Full-Suite Test Execution Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Quants\Projects\quant-portfolio-engine-starter
plugins: anyio-4.15.1
collected 108 items

backend\tests\test_api_contracts.py ......                               [  5%]
backend\tests\test_dataset_registry.py ......                            [ 11%]
backend\tests\test_market_data.py ........                               [ 18%]
backend\tests\test_optimization_engine.py .......................        [ 39%]
backend\tests\test_portfolio_engine.py ...................               [ 57%]
backend\tests\test_quant_math.py ..........................              [ 81%]
backend\tests\test_validation_engine.py ....................             [100%]

======================= 108 passed, 1 warning in 7.61s ========================
```

---

## 11. Modified and Created Files

| File | Change | Description |
|---|---|---|
| `backend/app/quant/optimization.py` | Created | Pure quantitative optimization engine (Min-Variance, Max-Sharpe, Equal-Weight, SLSQP). |
| `backend/app/quant/__init__.py` | Modified | Exported optimization solvers, models, and validation routines. |
| `backend/app/portfolio/optimization_service.py` | Created | Service layer for price extraction, return alignment, and solver orchestration. |
| `backend/app/portfolio/models.py` | Modified | Added `OptimizationRequest`, `OptimizationResponse`, `PortfolioMetricsModel`, `SolverDiagnosticsModel`. |
| `backend/app/portfolio/__init__.py` | Modified | Exported optimization service and models. |
| `backend/app/api/v1/routes.py` | Modified | Added `POST /api/v1/portfolios/optimize` endpoint with threadpool scheduling. |
| `backend/tests/test_optimization_engine.py` | Created | 23 analytical and deterministic tests. |
| `docs/FINANCIAL_DATA_CONTRACTS.md` | Modified | Added Section 4.7 (Portfolio Optimization Engine Contracts). |
| `docs/REQUIREMENTS_SPEC.md` | Modified | Updated Stage 4 status and workflow contracts. |
| `docs/SYSTEM_ARCHITECTURE.md` | Modified | Updated ADR-03 to reflect SciPy SLSQP with analytical gradients. |
| `docs/SESSION_06_REPORT.md` | Created | This session verification audit report. |

---

## 12. Known Limitations & Scope Boundaries

1. **Continuous Solver Scope:** SciPy SLSQP optimizes smooth continuous functions. Discrete lot sizes or cardinality constraints are out of scope.
2. **Local vs. Global Optimality in Max Sharpe:** While Minimum Variance is strictly convex (global optimum guaranteed), Maximum Sharpe is quasi-convex under long-only constraints. Multi-start initialization is employed to ensure global convergence for typical investment geometries, but mathematical claims of global optimality for general non-convex spaces are explicitly avoided.
3. **Cross-Currency Limitation:** Multi-currency portfolios (combining USD and PKR assets) remain blocked until an explicit FX conversion series is implemented.
4. **No Covariance Shrinkage:** Sample covariance is used with listwise deletion. Shrinkage estimators (e.g. Ledoit-Wolf) are deferred to Stage 5.

---

## 13. Recommended Next Session (Session 07)

**Stage 5: Efficient Frontier Generation & Multi-Portfolio Risk Comparison Analytics**
1. Implement parametric trace of the Markowitz Efficient Frontier curve (varying target returns / risk-aversion parameters).
2. Generate efficient frontier coordinate sets $(\sigma_k, \mu_k)$ with corresponding weight allocations.
3. Implement portfolio comparison analytics (Equal-Weight vs. Minimum Variance vs. Maximum Sharpe).
4. Add diversification ratio and marginal risk contribution metrics.
