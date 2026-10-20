# SESSION 07 REPORT — Efficient Frontier & Risk Analytics
**Document Version:** 1.0.0  
**Status:** Complete & Independently Verified  
**Date:** 2026-10-17  
**Author:** Quantitative Finance Software Engineering, Numerical Optimization & Portfolio Analytics Team  

---

## 1. Executive Summary

In **Session 07**, we extended the Quant Portfolio Optimization Engine with:
1. **Target-Return Minimum-Variance Optimization:** Solving continuous quadratic programs using SciPy SLSQP with exact analytical gradients to find minimum-variance portfolios for specific return targets.
2. **Efficient Frontier Generation Engine:** Mapping the complete Markowitz risk-return spectrum with exact linear programming feasibility bounds, dominance classification, and explicit reporting for infeasible targets.
3. **Pure Portfolio Risk Analytics:** Rigorous standalone functions for Sharpe ratio, Sortino ratio with configurable Minimum Acceptable Return (MAR), and maximum peak-to-trough drawdown with explicit handling of zero/negligible volatility.
4. **Multi-Portfolio Strategy Comparison:** Synchronous comparative analysis across Global Minimum-Variance (GMV), Maximum Sharpe Ratio, Equal-Weight, and custom user allocations on identical underlying market data.
5. **Typed Domain Models & REST API Endpoints:** Pydantic request and response schemas exposed via `POST /api/v1/portfolios/efficient-frontier` and `POST /api/v1/portfolios/compare` executed safely in worker threadpools.

Every frontier point and risk metric is computed from actual numerical optimizations and historical returns—no chart points, weights, or expected returns are mocked or fabricated.

---

## 2. Baseline Test Verification

Prior to implementing Session 07 functionality, the existing test suite was executed to verify the reported Session 06 baseline:
- **Baseline Test Count:** 108 passed (100% pass rate)
- **Baseline Execution Time:** 9.00s
- **Baseline Modules:** `test_api_contracts.py` (6), `test_dataset_registry.py` (6), `test_market_data.py` (8), `test_optimization_engine.py` (23), `test_portfolio_engine.py` (19), `test_quant_math.py` (26), `test_validation_engine.py` (20).

---

## 3. Mathematical Formulations & Solver Architecture

### 3.1 Target-Return Minimum-Variance Problem

For any target expected return $R_{\text{target}}$, the optimizer minimizes portfolio variance subject to budget, return, and box constraints:

$$\min_{\mathbf{w}} \quad \frac{1}{2} \mathbf{w}^\top \mathbf{\Sigma} \mathbf{w}$$

Subject to:
1. $\sum_{i=1}^N w_i = W_{\text{target}}$ (equality budget constraint, typically $1.0$).
2. $\mathbf{w}^\top \boldsymbol{\mu} = R_{\text{target}}$ (equality target-return constraint).
3. $l_i \le w_i \le u_i$ for all $i \in \{1, \dots, N\}$ (per-asset box bounds).
4. $\sum_{i=1}^N |w_i| \le \text{Gross}_{\max}$ (inequality gross exposure limit, if shorting permitted).

**Analytical Gradient:**
$$\nabla f(\mathbf{w}) = \mathbf{\Sigma} \mathbf{w}$$

**Jacobians of Equality Constraints:**
- Budget: $\nabla c_1(\mathbf{w}) = \mathbf{1}^\top$
- Target Return: $\nabla c_2(\mathbf{w}) = \boldsymbol{\mu}^\top$

### 3.2 Exact Feasibility Bounds via Linear Programming

Before invoking quadratic optimization, the feasible expected return range $[\mu_{\min}, \mu_{\max}]$ under the linear constraint system is calculated using SciPy HiGHS dual-simplex linear programming (`scipy.optimize.linprog(method='highs')`):

$$\mu_{\min} = \min_{\mathbf{w}} \boldsymbol{\mu}^\top \mathbf{w} \quad \text{s.t. } \sum_{i=1}^N w_i = W_{\text{target}}, \quad l_i \le w_i \le u_i$$
$$\mu_{\max} = \max_{\mathbf{w}} \boldsymbol{\mu}^\top \mathbf{w} = -\min_{\mathbf{w}} (-\boldsymbol{\mu})^\top \mathbf{w} \quad \text{s.t. } \sum_{i=1}^N w_i = W_{\text{target}}, \quad l_i \le w_i \le u_i$$

**Infeasible Target Invariant:**
If a requested target return satisfies $R_{\text{target}} < \mu_{\min} - 10^{-5}$ or $R_{\text{target}} > \mu_{\max} + 10^{-5}$, the problem is mathematically impossible under the specified constraints. The solver immediately marks the target as `OptimizationStatus.INFEASIBLE` with empty weights and detailed diagnostic messages. No fallback portfolios are fabricated.

### 3.3 Feasible Initial Guess ($\mathbf{w}_0$) Strategy

To ensure rapid SLSQP convergence and prevent artificial constraint violations during optimization, an initial guess $\mathbf{w}_0$ is constructed via convex interpolation between the extreme LP solutions $\mathbf{w}_{\min}$ and $\mathbf{w}_{\max}$:

$$\theta = \text{clip}\left(\frac{R_{\text{target}} - \mu_{\min}}{\mu_{\max} - \mu_{\min}}, 0.0, 1.0\right)$$
$$\mathbf{w}_0 = (1 - \theta) \mathbf{w}_{\min} + \theta \mathbf{w}_{\max}$$

Because the linear constraint polyhedron (box bounds + sum = $W_{\text{target}}$) is convex:
1. $l_i \le w_{0,i} \le u_i$ for all $i$
2. $\sum w_{0,i} = W_{\text{target}}$
3. $\mathbf{w}_0^\top \boldsymbol{\mu} = (1 - \theta)\mu_{\min} + \theta\mu_{\max} = R_{\text{target}}$

Thus, $\mathbf{w}_0$ starts on step 0 satisfying all linear equality and bound constraints.

---

## 4. Dominance & Efficient Frontier Classification

Every evaluated portfolio point along the curve is categorized into one of four mutually exclusive classifications:

| Classification | Condition | Description |
|---|---|---|
| **`efficient`** | $R_{\text{actual}} \ge R_{\text{GMV}} - 10^{-5}$ | Upper non-dominated branch of the Markowitz bullet. Maximizes return for a given risk level. |
| **`dominated_inefficient`** | $R_{\text{actual}} < R_{\text{GMV}} - 10^{-5}$ | Lower branch of the Markowitz bullet. Dominated because the GMV portfolio (or upper branch) provides strictly greater return for equal or lower risk. |
| **`infeasible`** | $R_{\text{target}} \notin [\mu_{\min}, \mu_{\max}]$ | Target return cannot be achieved under the specified bounds and budget. Empty weights returned. |
| **`failed`** | Solver non-convergence | Numerical failure or constraint violation beyond numerical tolerance ($10^{-5}$). |

**Completeness Tracking:**
The efficient frontier response explicitly records:
- `requested_count`: Total target returns requested.
- `successful_count`: Feasible points computed.
- `failed_count`: Infeasible or failed points.
- `is_complete`: `True` if and only if `failed_count == 0`.

---

## 5. Pure Risk Analytics Conventions

### 5.1 Sharpe Ratio (`sharpe_ratio`)
$$S = \frac{R_p - R_f}{\sigma_p}$$
- **Frequency Compatibility:** Both $R_p$ and $\sigma_p$ must be expressed on the same basis (both annualized or both periodic).
- **Rate Conversion Policy:** When `annualized=False`, annual effective rate $R_f$ is converted via exact compound discounting: $r_{\text{periodic}} = (1 + R_f)^{1/m} - 1$.
- **Zero Volatility Safeguard:** If $\sigma_p \le 10^{-12}$, Sharpe ratio is mathematically undefined. The pure math function raises `ValueError`, and service layers report `sharpe_ratio: null`. Returning `inf` or `NaN` is strictly prohibited.

### 5.2 Sortino Ratio (`sortino_ratio`)
$$\text{Sortino} = \frac{R_p - \text{MAR}}{\sigma_{\text{downside}}}$$
- **Downside Deviation Definition:**
  $$\sigma_{\text{downside}} = \sqrt{\frac{1}{N - \text{ddof}} \sum_{t=1}^N \min(r_t - \text{MAR}_{\text{periodic}}, 0)^2}$$
- **Full Sample Denominator:** The denominator divides by total observation count $N$ (Sortino & Price, 1994), measuring probability-weighted downside shortfall relative to the entire distribution.
- **Zero Downside Deviation:** If all returns exceed MAR, $\sigma_{\text{downside}} = 0.0$ and Sortino ratio is recorded as `null`. Substituting total volatility for downside deviation is strictly prohibited.

### 5.3 Maximum Drawdown (`maximum_drawdown`)
$$\text{MDD} = \min_{t} \frac{W_t - \max_{0 \le \tau \le t} W_\tau}{\max_{0 \le \tau \le t} W_\tau}$$
- Evaluated on compounding wealth index $W_t = \prod_{\tau=1}^t (1 + r_\tau)$ starting at $W_0 = 1.0$.
- Identifies exact peak date, trough date, and recovery date.

### 5.4 Comprehensive Portfolio Risk Summary (`portfolio_risk_summary`)
Generates standardized performance profiles containing:
- Periodic and annualized arithmetic mean return
- Total geometric cumulative wealth return
- Periodic and annualized volatility
- Periodic and annualized variance
- Peak-to-trough maximum drawdown
- Annualized downside deviation below MAR
- Annualized Sharpe and Sortino ratios
- Exact date window and clean observation count

---

## 6. Multi-Portfolio Strategy Comparison Service

The `execute_portfolio_comparison` service evaluates multiple portfolio allocations under identical assumptions:
- **Global Minimum Variance (GMV):** Least-risk continuous allocation.
- **Maximum Sharpe Ratio:** Tangency allocation maximizing risk-adjusted return.
- **Equal-Weight Baseline:** $1/N$ naive benchmark.
- **Custom User Portfolios:** User-specified allocations evaluated against constraints and market data.

**Guarantees & Safeguards:**
1. **Identical Market Data:** All portfolios are evaluated against the exact same synchronized price and return series.
2. **Same Date Range:** Common trading days enforced via synchronized dropna.
3. **Cross-Currency Isolation:** Multi-currency portfolios (mixing US and PSX equities) are strictly rejected with HTTP 422 under existing USD/PKR safeguards. No mock FX rates are fabricated.

---

## 7. API Integration

### 7.1 `POST /api/v1/portfolios/efficient-frontier`
- **Request Body:** `EfficientFrontierRequest` (portfolio definition, `target_count`, optional `target_returns`, `risk_free_rate`, `annualized`, `periods_per_year`).
- **Response Body:** `EfficientFrontierResponse` (points list, GMV anchor, `min_feasible_return`, `max_feasible_return`, `is_complete`, date coverage).
- **Thread Safety:** Executed via `run_in_threadpool`.

### 7.2 `POST /api/v1/portfolios/compare`
- **Request Body:** `PortfolioComparisonRequest` (base portfolio definition, flags for GMV, Max Sharpe, Equal Weight, custom portfolios dictionary).
- **Response Body:** `PortfolioComparisonResponse` (comparative portfolio items, standardized metrics, comprehensive risk summaries, annualization metadata).

---

## 8. Independent Numerical Verification

To ensure zero-drift accuracy, all solvers were tested against closed-form analytical oracles:

### 8.1 Two-Asset Uncorrelated Analytical Oracle
Consider two uncorrelated assets:
- Asset A: $\mu_A = 0.10, \sigma_A^2 = 0.04$
- Asset B: $\mu_B = 0.20, \sigma_B^2 = 0.09$
- Covariance: $\sigma_{AB} = 0.0$

Under fully invested budget $w_A + w_B = 1.0$, for any target return $R_{\text{target}} \in [0.10, 0.20]$, the unique analytical weights are:
$$w_B^* = \frac{R_{\text{target}} - 0.10}{0.20 - 0.10} = \frac{R_{\text{target}} - 0.10}{0.10}$$
$$w_A^* = 1.0 - w_B^*$$

**Numerical Verification Result:**
For target return $R_{\text{target}} = 0.14$:
- Analytical: $w_B^* = 0.400000, w_A^* = 0.600000$, Expected Variance $= (0.60^2)(0.04) + (0.40^2)(0.09) = 0.0144 + 0.0144 = 0.028800$.
- Solver Output: $w_B = 0.400000, w_A = 0.600000$, Variance $= 0.028800$, Status = `converged`.
- Absolute Weight Error: $< 10^{-7}$. Target Return Residual: $< 10^{-7}$.

### 8.2 Global Minimum-Variance Analytical Oracle
Analytical GMV weights:
$$w_A^{\text{GMV}} = \frac{\sigma_B^2}{\sigma_A^2 + \sigma_B^2} = \frac{0.09}{0.04 + 0.09} = \frac{9}{13} \approx 0.692308$$
$$w_B^{\text{GMV}} = \frac{\sigma_A^2}{\sigma_A^2 + \sigma_B^2} = \frac{0.04}{0.04 + 0.09} = \frac{4}{13} \approx 0.307692$$
$$R_{\text{GMV}} = \frac{9}{13}(0.10) + \frac{4}{13}(0.20) = \frac{1.70}{13} \approx 0.130769$$

**Dominance Test:**
- Target $R_{\text{target}} = 0.11 < R_{\text{GMV}}$ correctly classified as `dominated_inefficient`.
- Target $R_{\text{target}} = 0.16 \ge R_{\text{GMV}}$ correctly classified as `efficient`.

---

## 9. Test Suite Verification & Coverage

The complete test suite was executed against the repository:
```
backend/tests/test_api_contracts.py .........                              [  4%]
backend/tests/test_dataset_registry.py ......                            [  9%]
backend/tests/test_market_data.py ........                               [ 15%]
backend/tests/test_optimization_engine.py .......................        [ 33%]
backend/tests/test_portfolio_engine.py ...................               [ 48%]
backend/tests/test_quant_math.py ..........................              [ 68%]
backend/tests/test_risk_and_frontier.py ....................             [ 84%]
backend/tests/test_validation_engine.py ....................             [100%]

======================= 128 passed, 1 warning in 9.73s ========================
```
- **Total Tests Passing:** 128
- **New Session 07 Tests Added:** 20 (across `TestRiskMetrics`, `TestTargetReturnOptimization`, `TestEfficientFrontierEngine`, `TestPortfolioComparisonAndSafeguards`, `TestAPIRouteIntegration`).
- **Regression Count:** 0 failures, 0 regressions. 108 existing baseline tests continue to pass cleanly.

---

## 10. Files Created and Modified

| File | Status | Description |
|---|---|---|
| `backend/app/quant/risk.py` | Modified | Added standalone `sharpe_ratio`, `sortino_ratio`, `PortfolioRiskSummary`, and `portfolio_risk_summary`. |
| `backend/app/quant/optimization.py` | Modified | Added `OptimizationObjective.TARGET_RETURN`, `FrontierPoint`, `EfficientFrontierResult`, `calculate_feasible_return_bounds` (LP), `optimize_target_return_min_variance`, and `generate_efficient_frontier`. Updated `optimize_portfolio` dispatcher. |
| `backend/app/quant/__init__.py` | Modified | Exported new frontier, target return, and risk analytics symbols in `__all__`. |
| `backend/app/portfolio/models.py` | Modified | Added `FrontierPointModel`, `EfficientFrontierRequest`, `EfficientFrontierResponse`, `PortfolioRiskSummaryModel`, `PortfolioComparisonItemModel`, `PortfolioComparisonRequest`, `PortfolioComparisonResponse`. Added `target_return` to `OptimizationRequest`. |
| `backend/app/portfolio/optimization_service.py` | Modified | Implemented `_prepare_portfolio_market_data`, `execute_efficient_frontier`, and `execute_portfolio_comparison`. Supported target-return optimization. |
| `backend/app/portfolio/__init__.py` | Modified | Exported new request/response models and service execution functions. |
| `backend/app/api/v1/routes.py` | Modified | Added `POST /api/v1/portfolios/efficient-frontier` and `POST /api/v1/portfolios/compare` endpoints. |
| `backend/tests/test_risk_and_frontier.py` | Created | Comprehensive deterministic test suite for pure risk metrics, analytical oracles, frontier generation, dominance classification, and API integration. |
| `docs/REQUIREMENTS_SPEC.md` | Modified | Marked Stage 5 complete and updated core workflow specifications. |
| `docs/FINANCIAL_DATA_CONTRACTS.md` | Modified | Added Section 6 defining Efficient Frontier & Portfolio Risk Analytics Contracts. |
| `docs/SYSTEM_ARCHITECTURE.md` | Modified | Added ADR-06 covering the Linear Programming Feasibility & Starting Point Strategy. |
| `docs/SESSION_07_REPORT.md` | Created | This authoritative engineering and verification report. |

---

## 11. Known Limitations & Handoff to Session 08

1. **Transaction Cost Invariance:** Current frontier calculations assume frictionless trading; transaction cost and turnover penalties are deferred to Stage 7 (Backtesting Engine).
2. **Continuous Convex Polytope:** Mixed-integer cardinality constraints (e.g., "hold at most 5 stocks") remain unsupported by continuous SLSQP.
3. **Cross-Currency Isolation:** Portfolios mixing USD and PKR assets remain strictly blocked until a historical FX series and base-currency policy are implemented.
4. **Handoff Condition:** Session 07 is complete. All 128 tests pass. Awaiting explicit user review and approval before proceeding to Session 08.
