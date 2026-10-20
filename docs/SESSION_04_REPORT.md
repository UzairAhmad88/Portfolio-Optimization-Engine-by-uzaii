# SESSION 04 REPORT — Financial Mathematics Core
**Document Version:** 1.0.0  
**Status:** Complete & Verified  
**Date:** 2026-10-17  
**Author:** Quantitative Finance Software Engineering & Architecture Team  

---

## 1. Executive Summary

In **Session 04**, we designed, implemented, and verified the foundational **Financial Mathematics Core** (`app.quant`) for the Quant Portfolio Optimization Engine.

All financial mathematics are implemented as pure, deterministic, reproducible functions in NumPy and pandas, strictly decoupled from FastAPI web transport, route handlers, database persistence, and mutable global state. Calculations are verified by deterministic unit and numerical tests anchored to hand-calculated and analytically derived mathematical test oracles.

---

## 2. Baseline Test Results & Verification

Prior to modifying any code, the Session 03 baseline was executed against Python 3.11:
- **Baseline Test Count:** 40 passed
- **Baseline Execution Time:** 5.63s
- **Baseline Test Suite Status:** Clean baseline; 100% pass rate across `test_market_data.py`, `test_validation_engine.py`, `test_dataset_registry.py`, and `test_api_contracts.py`.

---

## 3. Files Created and Modified

| File Path | Action | Description |
|---|---|---|
| `backend/app/quant/__init__.py` | Created | Public package interface exposing financial mathematical functions and dataclasses. |
| `backend/app/quant/returns.py` | Created | Discrete simple returns, continuously compounded log returns, cumulative returns / wealth curves, and annualized returns (CAGR and arithmetic). |
| `backend/app/quant/risk.py` | Created | Sample and population variance, volatility, annualized volatility, running drawdown series, maximum drawdown with `DrawdownResult` (peak, trough, recovery dates), downside deviation, and effective periodic compounding conversion. |
| `backend/app/quant/covariance.py` | Created | Multi-asset sample and population covariance matrices with listwise/pairwise NA strategies, symmetry verification ($|\Sigma - \Sigma^T| \le 10^{-12}$), diagonal consistency, annualized covariance, and correlation matrix. |
| `backend/app/quant/portfolio.py` | Created | Portfolio periodic returns ($r_p = \mathbf{w}^T \mathbf{r}$), arithmetic expected return ($\mu_p = \mathbf{w}^T \boldsymbol{\mu}$), portfolio variance ($\sigma_p^2 = \mathbf{w}^T \mathbf{\Sigma} \mathbf{w}$), portfolio volatility, floating-point tolerance handling, weight validation, and `PortfolioWeightSummary`. |
| `backend/tests/test_quant_math.py` | Created | 26 deterministic unit and numerical tests validating calculations against analytical solutions and hand calculations. |
| `docs/FINANCIAL_DATA_CONTRACTS.md` | Modified | Updated Section 4 with mathematical formulas, indexing conventions, missing-data handling, degrees of freedom, drawdown definitions, numerical tolerances, and cross-market limits. |
| `docs/SESSION_04_REPORT.md` | Created | Complete audit report of Session 04 deliverables, formulas, tests, and recommendations. |

---

## 4. Implemented Formulas and Mathematical Conventions

### 4.1 Returns (`app.quant.returns`)
1. **Simple Discrete Returns:**
   $$r_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$$
   - First element $t=0$ is strictly `NaN`.
   - Datetime index and asset columns are preserved.
   - Non-positive prices ($P \le 0.0$) and non-finite values (`inf`) raise `ValueError`.
2. **Logarithmic (Continuously Compounded) Returns:**
   $$r_{\log, t} = \ln\left(\frac{P_t}{P_{t-1}}\right)$$
   - Linearly additive across time: $\sum r_t = \ln(P_T / P_0)$.
   - Explicitly documented as non-additive across portfolio assets.
3. **Cumulative Returns & Wealth Curve:**
   $$R_{\text{cum}}(t) = \prod_{\tau=1}^t (1 + r_\tau) - 1$$
   - Optional `as_wealth_index=True` yields $W_t = 1 + R_{\text{cum}}(t)$ with $W_0 = 1.0$.
   - Any discrete return $r_t < -1.0$ is rejected.
4. **Annualized Returns:**
   - **Geometric (CAGR):**
     $$\text{CAGR} = \left(\prod_{t=1}^N (1 + r_t)\right)^{\frac{\text{periods\_per\_year}}{N}} - 1$$
   - **Arithmetic Annualized Return:**
     $$R_{\text{arith, ann}} = \bar{r} \times \text{periods\_per\_year}$$
   - Annualization factors: US Equities ($252$), PSX Equities ($250$), Weekly ($52$), Monthly ($12$).

### 4.2 Risk Metrics (`app.quant.risk`)
1. **Variance & Volatility:**
   - Sample Variance ($ddof=1$): $s^2 = \frac{1}{N-1} \sum_{i=1}^N (r_i - \bar{r})^2$, requiring $N \ge 2$.
   - Population Variance ($ddof=0$): $\sigma^2 = \frac{1}{N} \sum_{i=1}^N (r_i - \bar{r})^2$, requiring $N \ge 1$.
   - Periodic Volatility: $\sigma = \sqrt{\sigma^2}$.
   - Annualized Volatility: $\sigma_{\text{ann}} = \sigma \times \sqrt{\text{periods\_per\_year}}$.
2. **Maximum Drawdown (`DrawdownResult`):**
   - Wealth Index: $W_t = \prod_{\tau=1}^t (1 + r_\tau)$.
   - Running Peak: $M_t = \max_{0 \le \tau \le t} W_\tau$.
   - Drawdown Series: $DD_t = (W_t - M_t) / M_t \le 0.0$.
   - Max Drawdown: $\text{MDD} = \min DD_t \le 0.0$.
   - Identifies exact `peak_date`, `trough_date`, and subsequent `recovery_date` (or `None`).
   - Monotonically increasing wealth returns an exact $\text{MDD} = 0.0$.
3. **Downside Deviation (Semi-Deviation):**
   $$\delta_{\text{downside}} = \sqrt{\frac{1}{N - ddof} \sum_{t=1}^N \min(r_t - \tau, 0.0)^2}$$
   - Threshold $\tau$ is the periodic Minimum Acceptable Return (MAR, default 0.0).
   - Uses total sample size $N$ in denominator per Sortino & Price (1994) standard.
   - Default $ddof=0$ (literature standard for downside deviation); $ddof=1$ supported.
4. **Risk-Free Rate Conversion:**
   $$r_p = (1 + r_a)^{\frac{1}{m}} - 1$$
   - Exact compound interest equivalence for annual effective rate $r_a$ across $m$ periods per year.

### 4.3 Covariance & Correlation (`app.quant.covariance`)
1. **Sample & Population Covariance:**
   $$\mathbf{\Sigma}_{i,j} = \frac{1}{N - ddof} \sum_{t=1}^N (r_{i,t} - \bar{r}_i)(r_{j,t} - \bar{r}_j)$$
   - Supports `"drop_any"` (listwise deletion, default) to ensure synchronized time intervals and positive semi-definiteness.
   - Symmetry validation: $|\Sigma_{i,j} - \Sigma_{j,i}| \le 10^{-12}$.
   - Diagonal consistency: $\Sigma_{i,i} = \operatorname{Var}(r_i)$.
   - Annualized Covariance: $\mathbf{\Sigma}_{\text{ann}} = \mathbf{\Sigma} \times \text{periods\_per\_year}$.
2. **Correlation Matrix:**
   $$\mathbf{R}_{i,j} = \frac{\Sigma_{i,j}}{\sigma_i \sigma_j}$$
   - Exact $1.0$ on the main diagonal; bounded in $[-1.0, 1.0]$.
   - Zero-variance assets (constant prices) are detected and rejected.

### 4.4 Portfolio Return and Risk (`app.quant.portfolio`)
1. **Portfolio Periodic Return:** $r_{p,t} = \mathbf{w}^T \mathbf{r}_t$.
2. **Portfolio Expected Return:** $\mu_p = \mathbf{w}^T \boldsymbol{\mu}$.
3. **Portfolio Variance & Volatility:**
   $$\sigma_p^2 = \mathbf{w}^T \mathbf{\Sigma} \mathbf{w}, \quad \sigma_p = \sqrt{\sigma_p^2}$$
   - Floating-Point Tolerance: Tiny negative values in $[-10^{-12}, 0.0)$ resulting from numerical rounding are clamped to $0.0$.
   - Materially negative values ($< -10^{-12}$) raise `ValueError`.
4. **Portfolio Weight Validation & Summaries:**
   - Supports long-only ($w_i \ge 0$) and long-short ($w_i \in \mathbb{R}$) weight vectors.
   - `PortfolioWeightSummary` computes gross exposure, net exposure, fully invested check ($|\sum w - 1| \le 10^{-6}$), and short position detection.
   - Renormalization is strictly explicit via `normalize_weights()`; mathematical calculation functions **never silently renormalize weights**.

---

## 5. Test Coverage by Category

A total of 26 new deterministic tests were created in `backend/tests/test_quant_math.py`:

| Category | Tests | Key Test Oracles |
|---|---|---|
| **Returns** | 7 tests | Hand-calculated price sequence $[100, 105, 99.75, 104.7375] \implies [+5\%, -5\%, +5\%]$; log returns $[100, 110, 121] \implies \ln(1.21)$; wealth growth $[0.10, -0.10, 0.20] \implies +18.8\%$; 2-period CAGR vs arithmetic annualization; non-positive and non-finite rejection. |
| **Risk Metrics** | 7 tests | Analytical sample ($ddof=1, s^2=0.00025$) & population ($ddof=0, \sigma^2=0.00020$) variance; US (252) vs PSX (250) annualized volatility; 6-period hand-calculated drawdown $[100, 120, 90, 80, 110, 130]$ verifying peak at Day 1, trough at Day 3 ($\text{MDD} = -33.33\%$), and recovery at Day 5; monotonic zero-drawdown verification; hand-calculated downside deviation ($2.0\%$ Sortino); compound rate conversion ($(1+r_p)^{12}-1 = 0.10$). |
| **Covariance & Correlation** | 5 tests | 2-asset analytical covariance with exact $2\times$ linear relationship ($\rho = 1.0, \Sigma_{AB} = 0.0002$); random matrix symmetry and diagonal consistency check; missing data listwise alignment; insufficient observations ($< ddof + 1$) rejection; zero-variance asset rejection. |
| **Portfolio Math** | 7 tests | Analytical 2-asset portfolio returns ($w=[0.6, 0.4] \implies r_{p,1}=7.0\%, r_{p,2}=0.4\%$); analytical portfolio variance ($w=[0.5, 0.5], \Sigma \implies \sigma_p^2 = 0.0385$); long-short portfolio handling; floating-point tolerance clamping ($-5\times 10^{-13} \to 0.0$); materially negative variance rejection ($< -10^{-12}$); asset-weight mismatch detection; invalid weight values rejection. |

---

## 6. Final Test Suite Results

```text
============================= test session starts =============================
platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Quants\Projects\quant-portfolio-engine-starter\backend
configfile: pyproject.toml
testpaths: tests
collected 66 items

tests/test_api_contracts.py ......................... [ 9%]
tests/test_dataset_registry.py ....................... [ 18%]
tests/test_market_data.py ........................... [ 30%]
tests/test_quant_math.py ............................ [ 69%] (26 new tests)
tests/test_validation_engine.py ..................... [100%]

======================== 66 passed, 1 warning in 1.95s ========================
```

### Static Analysis & Verification Checks
- **Pytest:** 66 passed, 0 failed, 0 regressions.
- **Ruff Linting (`uv tool run ruff check app tests`):** All checks passed.
- **Ruff Formatting (`uv tool run ruff format --check app tests`):** 18 files formatted, 0 violations.
- **Python Bytecode Compilation (`python -m compileall app tests`):** 100% clean compilation.

---

## 7. Numerical Limitations & Operational Boundaries

1. **Floating-Point Clamping Tolerance:**
   Sample covariance matrices evaluated near boundary conditions can yield tiny negative portfolio variances due to floating-point truncation. Variances in $[-10^{-12}, 0.0)$ are clamped to $0.0$; variances below $-10^{-12}$ trigger an explicit `ValueError`.
2. **Cross-Market Multi-Currency Limitation:**
   Asset returns are calculated independently in each asset's native trading currency (USD for US equities, PKR for PSX equities). Directly aggregating assets from different currencies without an FX rate series introduces unhedged currency distortion. Multi-currency portfolio optimization requires a formal base-currency selection and daily FX exchange rate series.
3. **No External Dependencies / Framework Decoupling:**
   `app.quant` imports only standard Python libraries (`dataclasses`, `typing`, `collections.abc`), `numpy`, and `pandas`. There is zero import of FastAPI, Starlette, or Pydantic in the math calculation layer.

---

## 8. Deferred Decisions

- **Sharpe and Sortino Ratios:** Deferred to Session 05 (Risk Analytics & Performance Attribution). This preserves unambiguous input contracts for excess returns, risk-free rate compounding conventions, and user-specified MAR thresholds.
- **Portfolio Optimization & Efficient Frontier Solvers:** SciPy / CVXPY numerical optimization solvers, quadratic programming formulations, and portfolio constraints (e.g., minimum variance, max Sharpe, target return, weight bounds) belong to Stage 4 (Session 06).
- **Backtesting & Transaction Costs:** Historical rebalancing, slippage, and performance attribution belong to Stage 5.

---

## 9. Recommended Next Session

**SESSION 05: Risk Analytics, Performance Attribution & Financial Reporting Contracts**
- Implement portfolio Sharpe Ratio, Sortino Ratio, Calmar Ratio, and Information Ratio built cleanly on the verified Session 04 mathematics core.
- Implement benchmark-relative metrics (Beta, Alpha, Tracking Error).
- Design typed Pydantic calculation request and response schemas for quant analytical API endpoints.
