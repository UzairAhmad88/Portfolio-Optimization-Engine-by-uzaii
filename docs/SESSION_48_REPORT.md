# Stage 30 Remediation & Unification Report: Session 48

**Stage:** Stage 30 — Transaction Cost Analysis (TCA) and Slippage Performance Attribution  
**Session:** Session 48  
**Scope:** Remediation of DEF-47-01 (Gross vs Net Return Mapping Collision & Labeling Inconsistency)  
**Status:** Complete & Verified  

---

## 1. Executive Summary

In Session 47, an independent quantitative review identified defect **DEF-47-01**:
In `frontend/src/api/client.ts`, both `total_return_gross` and `total_return_net` were mapped to `raw.strategy_metrics.total_return`. Consequently, the interactive UI's **"Gross vs Net Return Drag"** KPI tile displayed `0.00% (0.0 bps)`, masking the genuine transaction friction drag computed by the backend engine. Furthermore, the strategy comparison table displayed Sharpe ratios without distinguishing whether they were computed on gross or net return streams.

In **Session 48**, this defect was systematically remediated end-to-end:
1. **Mathematical Engine (`backend/app/quant/vine_backtest.py`):**
   - Explicitly computes net daily portfolio returns $r_t^{\text{net}} = \frac{V_t}{V_{t-1}} - 1.0$ alongside gross daily returns $r_t^{\text{gross}} = \mathbf{w}_t^\top \mathbf{R}_t$.
   - Computes both gross and net annualized metrics:
     - $R^{\text{gross}} = \prod (1 + r_t^{\text{gross}}) - 1.0$
     - $R^{\text{net}} = \frac{V_T}{V_0} - 1.0 = \prod (1 + r_t^{\text{net}}) - 1.0$
     - $\text{CAGR}^{\text{gross}} = (1 + R^{\text{gross}})^{1/Y} - 1.0$
     - $\text{CAGR}^{\text{net}} = (V_T / V_0)^{1/Y} - 1.0$
     - $\sigma^{\text{gross}}_{\text{ann}} = \sqrt{252} \cdot \operatorname{std}(r^{\text{gross}})$
     - $\sigma^{\text{net}}_{\text{ann}} = \sqrt{252} \cdot \operatorname{std}(r^{\text{net}})$
     - $\text{Sharpe}^{\text{gross}} = \frac{\operatorname{mean}(r^{\text{gross}} - r_f/252)}{\operatorname{std}(r^{\text{gross}})} \cdot \sqrt{252}$
     - $\text{Sharpe}^{\text{net}} = \frac{\operatorname{mean}(r^{\text{net}} - r_f/252)}{\operatorname{std}(r^{\text{net}})} \cdot \sqrt{252}$
2. **Schema & Models (`backend/app/copula/models.py`):**
   - Added `total_return_gross: float = 0.0`, `cagr_gross: float = 0.0`, `annualized_volatility_gross: float = 0.0`, `annualized_volatility_net: float = 0.0`, `sharpe_ratio_gross: float = 0.0`, `sharpe_ratio_net: float = 0.0` to `VineBacktestStrategyMetrics` with full backward compatibility.
3. **Frontend API Client (`frontend/src/api/client.ts`):**
   - Fixed field mapping: `total_return_gross` maps to `raw.strategy_metrics.total_return_gross`, and `total_return_net` maps to `raw.strategy_metrics.total_return_net ?? raw.strategy_metrics.total_return`.
   - Properly propagates `annualized_volatility_gross`, `annualized_volatility_net`, `sharpe_ratio_gross`, and `sharpe_ratio_net`.
4. **User Interface (`frontend/src/components/pages/CopulaTailRiskPage.tsx`):**
   - Performance & Risk Benchmark table now explicitly headers and displays:
     - `Annualized Volatility (Gross / Net)`
     - `Sharpe Ratio (Gross / Net, rf = 0)`
   - The **"Gross vs Net Return Drag"** KPI tile displays the genuine basis point friction drag and gross/net percentage split.
5. **Automated Verification:**
   - Added unit test `test_gross_vs_net_performance_metrics_accounting` to `backend/tests/test_vine_backtest_engine.py`.
   - Verified that 100% of tests pass across backend (469 tests) and frontend (43 tests).
   - Verified clean production build (`tsc -b && vite build` in 1.79s).

---

## 2. Mathematical Rigor & Formal Accounting

### 2.1 Daily Portfolio Return Formulations

For trading day $t \in \{1, \dots, T\}$, with portfolio asset weights $\mathbf{w}_t = [w_{1,t}, \dots, w_{N,t}]^\top$ and asset simple returns $\mathbf{R}_t = [R_{1,t}, \dots, R_{N,t}]^\top$:

1. **Gross Daily Return:**
   $$r_t^{\text{gross}} = \sum_{i=1}^N w_{i, t} R_{i, t}$$
   Represents portfolio capital growth before any transaction fees or slippage friction.

2. **Net Daily Return:**
   $$r_t^{\text{net}} = \frac{V_t}{V_{t-1}} - 1.0$$
   where $V_t$ is the end-of-day portfolio equity accounting for both price movement and transaction friction deductions at rebalance dates $t_k$:
   $$V_t = V_{t-1} \cdot (1 + r_t^{\text{gross}}) - C_t^{\text{fee}} - C_t^{\text{slip}}$$

### 2.2 Compounded Performance Attribution

- **Gross Cumulative Return:**
  $$R^{\text{gross}} = \prod_{t=1}^T (1 + r_t^{\text{gross}}) - 1.0$$
- **Net Cumulative Return:**
  $$R^{\text{net}} = \frac{V_T}{V_0} - 1.0 = \prod_{t=1}^T (1 + r_t^{\text{net}}) - 1.0$$
- **Friction Drag:**
  $$\Delta_{\text{friction}} = R^{\text{gross}} - R^{\text{net}}$$
  $$\text{Friction Drag (bps)} = 10^4 \cdot (R^{\text{gross}} - R^{\text{net}})$$

### 2.3 Risk-Adjusted Metrics

- **Annualized Volatility:**
  $$\sigma_{\text{ann}}^{\text{gross}} = \sqrt{252} \cdot \sqrt{\frac{1}{T-1} \sum_{t=1}^T (r_t^{\text{gross}} - \bar{r}^{\text{gross}})^2}$$
  $$\sigma_{\text{ann}}^{\text{net}} = \sqrt{252} \cdot \sqrt{\frac{1}{T-1} \sum_{t=1}^T (r_t^{\text{net}} - \bar{r}^{\text{net}})^2}$$

- **Sharpe Ratio ($r_f = 0$):**
  $$\text{Sharpe}^{\text{gross}} = \frac{\bar{r}^{\text{gross}}}{\operatorname{std}(r^{\text{gross}})} \cdot \sqrt{252}$$
  $$\text{Sharpe}^{\text{net}} = \frac{\bar{r}^{\text{net}}}{\operatorname{std}(r^{\text{net}})} \cdot \sqrt{252}$$

---

## 3. Verification & Test Summary

| Test Target | Suite / File | Status | Notes |
| :--- | :--- | :---: | :--- |
| **Gross vs Net Accounting** | `backend/tests/test_vine_backtest_engine.py` | **PASSED** | Verifies `total_return_gross > total_return_net`, `sharpe_gross > sharpe_net`, non-zero friction drag under positive cost assumptions. |
| **TCA Engine Suite** | `backend/tests/test_tca_engine.py` (11 tests) | **PASSED** | Verifies adverse slippage signs, opportunity costs, exact component identity reconciliation, multi-day queue accounting, and rejection zero-fills. |
| **Entire Backend Suite** | `backend/tests/` (469 tests) | **PASSED** | 100% pass across all modules, zero regressions. |
| **Frontend Unit Suite** | `frontend/src/test/` (43 tests) | **PASSED** | All client tests and workspace shell tests pass. |
| **Production Build** | `tsc -b && vite build` | **PASSED** | Zero TypeScript compilation errors, clean production bundle in 1.79s. |

---

## 4. Final Sign-Off Status

Stage 30 (Transaction Cost Analysis and Slippage Performance Attribution) is **fully implemented, remediated, mathematically reconciled, and verified**. All defects identified in Sessions 42, 44, 46, and 47 are completely resolved.
