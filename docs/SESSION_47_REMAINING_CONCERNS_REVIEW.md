# SESSION 47 FOCUSED QUANTITATIVE REVIEW
## Focused Read-Only Review of Remaining Stage 30 Quantitative Concerns

**Document:** Focused Read-Only Quantitative, Accounting, and Provenance Review  
**Audit Target:** Stage 30 — Transaction Cost Analysis (TCA) and Slippage Performance Attribution  
**Session:** 47  
**Audit Mode:** Strictly Read-Only (Zero persistent code, test, schema, config, or roadmap modifications)  
**Final Audit Verdict:** **BLOCKED — Confirmed Defects Require Remediation**  
**Evidence Baseline:** 468 Backend Tests Passing | 43 Frontend Tests Passing | Clean Vite Production Build  

---

### 1. Executive Verdict and Summary

In accordance with the Project Owner's instructions for Session 47, an exhaustive, focused, read-only quantitative review was conducted targeting four key areas:
1. Gross versus net performance metric conventions and UI reporting.
2. Zero-equity floor semantics and post-bankruptcy simulation dynamics.
3. Modeled versus empirical slippage terminology and provenance disclosures.
4. Opportunity-cost attribution horizons and multi-day order scope.

#### Final Audit Verdict: **BLOCKED — CONFIRMED DEFECTS REQUIRE REMEDIATION**

**Core Justification:**
The review identified a confirmed metric inconsistency in the performance reporting pipeline (**DEF-47-01**):
- In [`frontend/src/api/client.ts`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/api/client.ts) (lines 781–782), both `total_return_gross` and `total_return_net` are mapped to the identical backend field `raw.strategy_metrics.total_return`, which is strictly net of transaction costs.
- Consequently, in [`frontend/src/components/pages/CopulaTailRiskPage.tsx`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/components/pages/CopulaTailRiskPage.tsx) (lines 1941–1949), the prominent KPI card **"Gross vs Net Return Drag"** calculates `(total_return_gross - total_return_net) * 10000`, which **always displays `0.0 bps`** and identical percentages (`Gross: X.XX% | Net: X.XX%`).
- This directly contradicts the adjacent Stage 30 TCA card, which reports hundreds of dollars of execution friction and non-zero effective drag basis points (e.g. `8.37 bps`).
- Furthermore, in [`backend/app/quant/vine_backtest.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/vine_backtest.py), `sharpe_ratio` and `annualized_volatility` are computed on gross asset returns (`strat_daily_rets`), while `total_return` and `cagr` are computed on net equity (`strat_equity_series`). A quantitative demonstration proves that reporting a gross Sharpe ratio alongside net total returns overstates risk-adjusted performance by over 30% in high-turnover regimes.

---

### 2. Repository State and Files Inspected

- **Repository Root:** `D:\Quants\Projects\quant-portfolio-engine-starter`.
- **Git State:** Unversioned workspace (`fatal: not a git repository`). No remotes or VCS tracking states were altered.
- **Working-Tree Integrity:**
  - Zero application source files in `backend/app/` or `frontend/src/` were modified.
  - Zero test files in `backend/tests/` or `frontend/src/test/` were modified.
  - Zero configuration files, dependencies, or documentation files were changed.
  - `docs/SESSION_47_REMAINING_CONCERNS_REVIEW.md` is the sole deliverable created.
- **Roadmap Status:** In [`docs/MASTER_PLAN.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/MASTER_PLAN.md), Stage 30 remains unaccepted; Stage 31 remains strictly blocked.

#### Files and Call Paths Inspected:
1. [`backend/app/quant/vine_backtest.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/vine_backtest.py):
   - Lines 239–305: `_compute_strategy_kpis()`.
   - Lines 665–745: Multi-day queue cancellation on rebalance conflict.
   - Lines 950–970: Rebalance-day cost deduction (`strat_equity = max(0.0, strat_equity - cost_today)`).
   - Lines 1185–1205: Queue-day cost deduction and gross return realization.
   - Lines 1238–1248: Equity compounding and return history appending.
   - Lines 1320–1376: Strategy KPI aggregation and TCA report generation.
2. [`backend/app/quant/tca.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/tca.py):
   - Lines 85–129: `calculate_trade_slippage()`.
   - Lines 131–173: `calculate_opportunity_cost()`.
   - Lines 182–246: `_aggregate_fills_subset()`.
   - Lines 249–339: `compute_transaction_cost_analysis()`.
   - Lines 342–368: `reconcile_tca_with_backtest_costs()`.
3. [`frontend/src/api/client.ts`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/api/client.ts):
   - Lines 770–825: Backtest response adaptation mapping `total_return_gross` and `total_return_net`.
4. [`frontend/src/components/pages/CopulaTailRiskPage.tsx`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/components/pages/CopulaTailRiskPage.tsx):
   - Lines 1931–1991: Trading Friction & Turnover Execution Diagnostics cards.
   - Lines 1993–2215: Stage 30 TCA cards, tables, and provenance badges.

---

### 3. Investigation A — Gross Versus Net Performance Metrics

#### 3.1 Trace of Returns and Equity in the Codebase

1. **Gross Return Calculation:**
   In [`backend/app/quant/vine_backtest.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/vine_backtest.py) (lines 1203–1205):
   ```python
   r_today = R_matrix[t, :]
   r_cash_today = float(risk_free_rate / annualization_factor)
   strat_gross_ret = float(np.dot(strat_drifted, r_today) + strat_cash_drifted * r_cash_today)
   ```
   `strat_gross_ret` represents the pure portfolio asset return before any trading friction.

2. **Deduction of Transaction Costs:**
   In `vine_backtest.py` (lines 953 and 1189):
   ```python
   strat_equity = max(0.0, strat_equity - cost_today)
   ```
   Costs are deducted from capital at the start of day $t$.
   Then at the end of day $t$ (line 1238):
   ```python
   strat_equity *= (1.0 + strat_gross_ret)
   strat_daily_rets.append(strat_gross_ret)
   strat_equity_series.append(strat_equity)
   ```
   Therefore:
   - `strat_equity_series` is compounded **net of costs**: $V_t = (V_{t-1} - C_t)(1 + r_t^{\text{gross}})$.
   - `strat_daily_rets` records **gross asset returns**: $r_t^{\text{gross}}$.

3. **Performance Metric Computation in `_compute_strategy_kpis()`:**
   In `vine_backtest.py` (lines 287–300):
   ```python
   ret_arr = np.array(daily_returns, dtype=np.float64)  # Contains strat_gross_ret
   final_equity = equity_values[-1] if equity_values else initial_capital  # Net of costs

   total_return = float(final_equity / initial_capital - 1.0)  # NET RETURN
   cagr = float((final_equity / initial_capital) ** (1.0 / years) - 1.0)  # NET CAGR

   vol_daily = float(np.std(ret_arr, ddof=1))  # GROSS VOLATILITY
   ann_vol = vol_daily * math.sqrt(annualization_factor)

   excess_ret = ret_arr - (risk_free_rate / annualization_factor)  # GROSS EXCESS RETURN
   sharpe = float(np.mean(excess_ret) / vol_daily * math.sqrt(annualization_factor))  # GROSS SHARPE
   ```

4. **Frontend Adaptation Mapping Collision:**
   In [`frontend/src/api/client.ts`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/api/client.ts) (lines 780–785):
   ```typescript
   dynamic_vine_trp: {
     total_return_gross: raw.strategy_metrics.total_return,  // MAPPED TO NET!
     total_return_net: raw.strategy_metrics.total_return,    // MAPPED TO NET!
     cagr_net: raw.strategy_metrics.cagr,
     annualized_volatility: raw.strategy_metrics.annualized_volatility,
     sharpe_ratio: raw.strategy_metrics.sharpe_ratio,
   }
   ```
   And in [`frontend/src/components/pages/CopulaTailRiskPage.tsx`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/components/pages/CopulaTailRiskPage.tsx) (lines 1941–1949):
   ```tsx
   <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Gross vs Net Return Drag</div>
   <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: '#EF4444', fontFamily: 'monospace' }}>
     {((backtestResult.strategies.dynamic_vine_trp.total_return_gross - backtestResult.strategies.dynamic_vine_trp.total_return_net) * 10000).toFixed(1)} bps
   </div>
   <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
     Gross: {(backtestResult.strategies.dynamic_vine_trp.total_return_gross * 100).toFixed(2)}% | Net: {(backtestResult.strategies.dynamic_vine_trp.total_return_net * 100).toFixed(2)}%
   </div>
   ```
   **Observed Behavior:** The card permanently displays `0.0 bps` and identical percentages, hiding the actual friction drag from the user.

#### 3.2 Synthetic Quantitative Demonstration

To illustrate the mathematical divergence between gross and net metrics, consider a hypothetical 3-day trading horizon with initial capital $V_0 = \$100,000$ and zero risk-free rate ($r_f = 0$):

- **Day 1 (Rebalance):**
  - Transaction cost incurred: $C_1 = \$500$ ($50$ bps of capital).
  - Capital after deduction: $V_1^{\text{post-cost}} = \$100,000 - \$500 = \$99,500$.
  - Asset return: $r_1^{\text{gross}} = +2.0\% (+0.02)$.
  - Ending equity: $V_1 = \$99,500 \times 1.02 = \$101,490.00$.
  - True net daily return: $r_1^{\text{net}} = \frac{101,490}{100,000} - 1 = \mathbf{+1.490\%}$.

- **Day 2 (No Trading):**
  - Cost incurred: $C_2 = \$0$.
  - Asset return: $r_2^{\text{gross}} = -1.0\% (-0.01)$.
  - Ending equity: $V_2 = \$101,490 \times 0.99 = \$100,475.10$.
  - True net daily return: $r_2^{\text{net}} = \frac{100,475.10}{101,490} - 1 = \mathbf{-1.000\%}$.

- **Day 3 (Rebalance):**
  - Transaction cost incurred: $C_3 = \$400$.
  - Capital after deduction: $V_3^{\text{post-cost}} = \$100,475.10 - \$400 = \$100,075.10$.
  - Asset return: $r_3^{\text{gross}} = +1.5\% (+0.015)$.
  - Ending equity: $V_3 = \$100,075.10 \times 1.015 = \$101,576.23$.
  - True net daily return: $r_3^{\text{net}} = \frac{101,576.23}{100,475.10} - 1 = \mathbf{+1.096\%}$.

#### Quantitative Comparison Table:

| Metric | Gross Formulation (Asset Returns) | Net Formulation (Equity Returns) | Discrepancy / Drag |
| :--- | :--- | :--- | :--- |
| **Cumulative Total Return** | $(1.02)(0.99)(1.015) - 1 = \mathbf{+2.495\%}$ | $\frac{101,576.23}{100,000} - 1 = \mathbf{+1.576\%}$ | **91.9 bps** |
| **Daily Return Series** | $[+2.00\%, -1.00\%, +1.50\%]$ | $[+1.490\%, -1.000\%, +1.096\%]$ | Average drag = $30.6$ bps/day |
| **Mean Daily Return** | $+0.8333\%$ | $+0.5287\%$ | $-30.46$ bps/day |
| **Daily Volatility ($\sigma_{\text{daily}}$)** | $1.6073\%$ | $1.3391\%$ | $-0.2682\%$ |
| **Annualized Volatility ($\times \sqrt{252}$)** | $\mathbf{25.52\%}$ | $\mathbf{21.26\%}$ | $-4.26\%$ |
| **Sharpe Ratio ($\frac{\bar{r}}{\sigma} \sqrt{252}$)** | $\mathbf{8.23}$ | $\mathbf{6.27}$ | **Overstated by +31.3%** |

#### Conclusion for Investigation A:
The current implementation represents a **confirmed inconsistency requiring remediation**.
- The backend computes a gross Sharpe ratio and a net total return without qualifying labels.
- The frontend adapter collides both gross and net total returns into the net value, rendering the "Gross vs Net Return Drag" tile inoperative ($0.0$ bps).

---

### 4. Investigation B — Zero-Equity Floor and Insolvency Semantics

#### 4.1 Numerical Safeguard vs Financial Outcome
In `vine_backtest.py` (lines 953 and 1189):
$$V_t^{\text{post-cost}} = \max(0.0, V_{t-1} - C_t)$$
- **Role as a Numerical Guard:** If $V_{t-1} < C_t$, flooring equity at $0.0$ avoids negative equity, which would cause CAGR calculation $(V_T / V_0)^{1/Y} - 1$ to raise a `ValueError` or return complex roots.
- **Financial Consequence:** The expression acts as an **unlimited liability shield / insolvency barrier**. If a portfolio with $\$500$ in equity incurs an $\$800$ execution fee, the $\$300$ deficit is absorbed by the floor (`0.0`). The cumulative cost ledger records `strat_total_costs += 800`, creating a ledger discrepancy against equity depletion ($\$800$ recorded cost vs $\$500$ equity loss).

#### 4.2 Post-Bankruptcy Simulation Dynamics
If $V_t$ drops to $0.0$:
1. On day $t+1$, intended orders $\Delta N_i = (w_i^* - w_i^{\text{drift}}) \cdot V_t$ evaluate to $0.0$.
2. However, the weight drifting vector $\mathbf{w}_t^{\text{drift}}$ continues to update on lines 1251–1255.
3. Market returns $\mathbf{r}_{t+1}$ continue to be dotted with $\mathbf{w}_{t+1}^{\text{drift}}$ to compute `strat_gross_ret`.
4. `strat_daily_rets.append(strat_gross_ret)` continues accumulating phantom returns after the fund has ceased to hold assets.
5. In `_compute_strategy_kpis()`, `sharpe_ratio` and `annualized_volatility` are computed on the entire return array, including the post-insolvency period.
- **Coverage Gap:** Existing tests in `test_vine_backtest_engine.py` and `test_tca_engine.py` do not test extreme insolvency or verify simulation termination upon capital exhaustion.

---

### 5. Investigation C — Modeled Versus Empirical Slippage

#### 5.1 Algebraic Determination in Daily-Bar Backtests
In `vine_backtest.py` (lines 725, 928, 1165):
$$P_i^{\text{fill}} = P_i^{\text{arr}} \cdot \left(1 + s_i \cdot \frac{C_i^{\text{total}}}{N_i^{\text{exec}}}\right)$$
where $C_i^{\text{total}} = C_i^{\text{spread}} + C_i^{\text{temp}} + C_i^{\text{perm}} + C_i^{\text{comm}}$.
In `tca.py` (lines 85–129), `calculate_trade_slippage()` evaluates:
$$C_i^{\text{slip}} = s_i \cdot N_i^{\text{exec}} \cdot \frac{P_i^{\text{fill}} - P_i^{\text{arr}}}{P_i^{\text{arr}}} = s_i \cdot N_i^{\text{exec}} \cdot \left(s_i \frac{C_i^{\text{total}}}{N_i^{\text{exec}}}\right) = s_i^2 C_i^{\text{total}} \equiv C_i^{\text{total}}$$
- **Finding:** In daily-bar simulation, arrival slippage is an algebraic identity that restates modeled friction in price space. It is not an independently measured market quantity.

#### 5.2 Terminology and UI Disclosures
- **Field Name:** Stored as `realized_slippage` and `realized_slippage_bps` on `TCACostMetrics`.
- **Potential Ambiguity:** In institutional trading, "realized slippage" implies reconciliation against actual broker execution fills (FIX drop-copy). Here, it is simulated implementation shortfall.
- **Mitigating Disclosures:** The provenance footer in `CopulaTailRiskPage.tsx` explicitly renders:
  `Decomposition: structural_modeled_identity`
  `Interval VWAP: unavailable_daily_bars`
- **Non-Additive Presentation:** `realized_slippage` is presented in a separate diagnostic tile and is **never** added to `total_cost` or debited from portfolio capital.

---

### 6. Investigation D — Opportunity Cost and Multi-Day Order Scope

#### 6.1 Return Benchmark and Measurement Horizon
- Formula: $C^{\text{opp}} = s \cdot N^{\text{unexec}} \cdot R_{t, i}$.
- Evaluated against close-to-close return $R_{t, i}$ on day $t$.
- Follows Perold's (1988) institutional sign conventions:
  - Unexecuted Buy: $R > 0 \implies C^{\text{opp}} > 0$ (missed upside); $R < 0 \implies C^{\text{opp}} < 0$ (avoided loss).
  - Unexecuted Sell: $R < 0 \implies C^{\text{opp}} > 0$ (adverse holding loss); $R > 0 \implies C^{\text{opp}} < 0$ (favorable retention).

#### 6.2 Attribution Timing & Overlapping Rebalances
- **Single-Day Attribution:** When an order is clipped by volume caps, cancelled by a rebalance conflict, or rejected by participation policy, a zero-fill record is emitted on day $t$. The opportunity cost is recorded for day $t$ and does not roll forward or compound as an open ghost order.
- **Interrupted Multi-Day Queues:** When a new rebalance interrupts an in-flight queue (lines 665–693), cancelled tranches emit zero-fills on day $t$. The new rebalance is computed from current drifted weights at day $t$, preventing overlapping attribution.
- **Ledger Impact:** $0.00$ deduction from cash or portfolio equity.

---

### 7. Evidence and Test Results

The following test suites were executed to verify the current baseline:

| Test Command | Runtime | Exit Code | Verified Outcome |
| :--- | :--- | :--- | :--- |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_tca_engine.py -v` | 7.59s | 0 | **11 passed (100%)** |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_multi_day_execution_scheduling.py -v` | 45.06s | 0 | **13 passed (100%)** |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -q` | 72.17s | 0 | **468 passed, 6 warnings (100%)** |
| `npm test -- --run` (in `frontend/`) | 9.41s | 0 | **43 passed across 2 files (100%)** |
| `npm run build` (in `frontend/`) | 1.69s | 0 | **Clean build (0 errors, 0 warnings)** |

*Assessment:* The existing tests thoroughly verify the algebraic correctness and schema contracts of the current codebase. However, they pass because the test assertions reflect the current mapping collision (e.g. testing that `raw.strategy_metrics.total_return` passes through). Passing tests did not catch that `total_return_gross` and `total_return_net` are assigned identical values.

---

### 8. Findings Ranked by Severity

| ID | Severity | Location | Description & Financial Reasoning | Concrete Failure Scenario | Recommended Remediation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-47-01** | **Medium** | `frontend/src/api/client.ts`:781–782, `backend/app/quant/vine_backtest.py`:287–300 | **Gross vs Net Return Mapping Collision & Labeling Inconsistency:** `total_return_gross` is mapped to `total_return` (net), causing the UI "Gross vs Net Return Drag" tile to always display `0.0 bps`. Furthermore, `sharpe_ratio` is gross while `total_return` is net. | Strategy pays $1,500 in trading friction (150 bps), but dashboard reports "Gross vs Net Return Drag: 0.0 bps" and reports a gross Sharpe ratio of 1.45 instead of the net Sharpe ratio of 1.15. | 1. Compute `total_return_gross = \prod(1 + r_t^{\text{gross}}) - 1` in `_compute_strategy_kpis`.<br>2. Map `total_return_gross` accurately in `api/client.ts`.<br>3. Compute and expose both `sharpe_ratio_gross` and `sharpe_ratio_net`. |
| **OBS-47-01** | **Observation** | `backend/app/quant/vine_backtest.py`:953, 1189 | **Insolvency Floor Dynamics:** `max(0.0, strat_equity - cost_today)` acts as an insolvency barrier. In the event of bankruptcy, simulation continues with phantom weight drifting. | If capital reaches $0.0$, subsequent days continue recording daily returns of drifted weights into `strat_daily_rets`. | Add an early termination check if `strat_equity <= 0.0` to halt trading and set post-insolvency returns to 0.0. |
| **OBS-47-02** | **Observation** | `backend/app/quant/tca.py`:85–129, `backend/app/copula/models.py`:130 | **Modeled Slippage Terminology:** Arrival slippage is an algebraic restatement of modeled friction in daily simulation. Terminology `realized_slippage` may imply empirical broker execution. | Users may believe `realized_slippage` is derived from an actual broker FIX drop-copy tape. | Document simulated price construction in API docstrings and retain provenance badges. |
| **OBS-47-03** | **Observation** | `backend/app/quant/tca.py`:131–173 | **Opportunity Cost Scope:** Evaluated over day $t$ return ($R_{t, i}$) on the day of non-execution as an informative diagnostic with $0.00$ equity deduction. | N/A (Standard institutional implementation shortfall practice). | Maintain diagnostic status. |

---

### 9. Recommended Next Actions (Ordered by Importance)

1. **Remediate DEF-47-01 in a Dedicated Session (Session 48):**
   - In [`backend/app/quant/vine_backtest.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/vine_backtest.py):
     - Compute `total_return_gross = float(np.prod(1.0 + ret_arr) - 1.0)`.
     - Compute net daily returns: $r_t^{\text{net}} = \frac{V_t}{V_{t-1}} - 1.0$.
     - Compute `sharpe_ratio_net` from $r_t^{\text{net}}$ alongside `sharpe_ratio_gross`.
   - In [`backend/app/copula/models.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/copula/models.py):
     - Expose `total_return_gross: float` on `BacktestStrategyMetrics`.
     - Expose `sharpe_ratio_net: float` and `sharpe_ratio_gross: float`.
   - In [`frontend/src/api/client.ts`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/api/client.ts):
     - Correctly map `total_return_gross: raw.strategy_metrics.total_return_gross`.
     - Correctly map `total_return_net: raw.strategy_metrics.total_return`.
   - In [`frontend/src/components/pages/CopulaTailRiskPage.tsx`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/components/pages/CopulaTailRiskPage.tsx):
     - Label Sharpe ratio clearly as Net or Gross.
     - The "Gross vs Net Return Drag" tile will now display the true non-zero friction drag (e.g. `8.37 bps`).

2. **Insolvency Hardening (Future Refinement):**
   - Add an early-exit check in `vine_backtest.py` if `strat_equity <= 0.0`.

---

### 10. Final Governance Statement

#### Final Determination: **BLOCKED — Confirmed Defects Require Remediation**

Stage 30 TCA and Slippage Performance Attribution cannot be accepted in its current state because the frontend/client performance reporting layer contains a confirmed defect (**DEF-47-01**) that masks execution friction by reporting identical gross and net returns (`0.0 bps drag`), directly conflicting with Stage 30's primary mission of transparent transaction cost attribution.

**Stage 30 remains unaccepted. Stage 31 remains strictly blocked.**
Remediation of DEF-47-01 should be scheduled for the next implementation session.
