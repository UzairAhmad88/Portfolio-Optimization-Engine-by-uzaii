# SESSION 42 INDEPENDENT QUANTITATIVE AUDIT REPORT
## Audit of Stage 30: Transaction Cost Analysis (TCA) and Slippage Performance Attribution

**Document:** Independent Quantitative, Statistical, Architectural & Contractual Audit  
**Audit Target:** Stage 30 — Transaction Cost Analysis (TCA) & Slippage Attribution  
**Session:** 42  
**Audit Mode:** Strictly Read-Only  
**Audit Status:** Remediation Required (6 Defect Findings: 2 High, 2 Medium, 2 Low)  

---

### 1. Executive Summary & Audit Verdict

Following project-owner instructions for Session 42, an independent, evidence-based quantitative, statistical, mathematical, and contractual audit of **Stage 30: Transaction Cost Analysis (TCA) and Slippage Performance Attribution** was conducted.

The Session 41 completion report claimed that Stage 30 delivered a production-ready, mathematically reconciled, and causally sound TCA attribution layer with zero residual ($C_{\text{unattributed}} \equiv 0.0$), 464 passing backend tests, 42 passing frontend tests, and a clean frontend build.

While the mathematical formulation of signed slippage and single-tranche opportunity costs is theoretically sound, and the backtest engine does not contaminate portfolio equity or historical return cash flows with fictitious deductions, this independent audit has uncovered **six material defects**, including **two HIGH-severity architectural and contract defects** that will cause a client-side runtime `TypeError` crash in the frontend dashboard and distort multi-day execution reporting.

#### Audit Verdict: **REQUIRE REMEDIATION**
Stage 30 **must not be approved for production sign-off** in its current state. Remediation of the frontend-backend contract mismatch (DEF-42-01) and multi-day queue requested notional accounting (DEF-42-02) is mandatory before Stage 31 can be authorized.

---

### 2. Repository & Roadmap Preflight

- **Repository Root:** `d:\Quants\Projects\quant-portfolio-engine-starter`.
- **Git Status:** Uninitialized/unversioned workspace. No Git commands, remotes, or commit histories were altered.
- **Roadmap Alignment:** Inspected `docs/MASTER_PLAN.md`, `docs/SESSION_40_AUDIT.md`, `docs/SESSION_41_CONTRACTS.md`, and `docs/SESSION_41_REPORT.md`.
- **Dependency & Runtime Versions:**
  - Python: 3.11.16 (`backend/.venv`)
  - Pytest: 9.1.1
  - Node.js: v24.18.0
  - Vite: 8.3.4
  - Vitest: 5.0.5

---

### 3. Files & Functions Inspected

| File Inspected | Functions / Components Examined | Lines | Responsibility |
| :--- | :--- | :--- | :--- |
| `backend/app/quant/tca.py` | `TradeFill`, `calculate_trade_slippage`, `calculate_opportunity_cost`, `_aggregate_fills_subset`, `compute_transaction_cost_analysis`, `reconcile_tca_with_backtest_costs` | 1–384 | Core TCA mathematical engine, signed slippage, opportunity cost, and aggregation. |
| `backend/app/quant/vine_backtest.py` | `_execute_cash_financed_tranche`, `run_vine_tail_risk_parity_backtest` (rebalance and queue loop, fill population, and `tca_report` generation) | 490–1323 | Walk-forward simulation engine, tranche execution, fill recording, and backtest metrics. |
| `backend/app/quant/execution.py` | `compute_rebalance_market_impact`, `compute_multi_day_execution_schedule`, `compute_regime_aware_execution_parameters` | 234–420 | Non-linear market impact, half-spread, permanent impact, and commissions calculation. |
| `backend/app/copula/models.py` | `TCACostMetrics`, `TCAEventMetrics`, `TCAProvenance`, `TCAReport`, `VineBacktestResponse` | 294–383 | Pydantic response models and schema serialization. |
| `backend/app/copula/service.py` | `execute_vine_backtest` | 525–575 | Service orchestration layer plumbing `tca_report` into `VineBacktestResponse`. |
| `backend/tests/test_tca_engine.py` | Tests 1–7 (slippage signs, opportunity cost, decomposition, notional weighting, walk-forward reconciliation, mutation invariance, Pydantic schemas) | 1–464 | Stage 30 test suite. |
| `frontend/src/types/api.ts` | `TCACostMetrics`, `TCAEventMetrics`, `TCAProvenance`, `TCAReport`, `VineBacktestResponse` | 2139–2205 | TypeScript API data contracts. |
| `frontend/src/api/client.ts` | `apiClient.runVineBacktest` | 764–866 | Frontend client mapping and network response handling. |
| `frontend/src/components/pages/CopulaTailRiskPage.tsx` | Stage 30 TCA Dashboard Card, KPI Tiles, Tabbed Attribution Table, Provenance Footnote | 1993–2215 | React 19 UI presentation layer. |

---

### 4. Detailed Audit Findings by Dimension

#### 4.1 Audit A — Signed Slippage Mathematics
The reported formula is:
$$C_j^{\text{slip}} = s_j \cdot N_j \cdot \left(\frac{P_j^{\text{fill}} - P_j^{\text{arr}}}{P_j^{\text{arr}}}\right)$$
where $s_j = +1$ for buys and $-1$ for sells.

**Independent Verification:**
Let $q_j$ be share quantity and $P^{\text{arr}}_j$ be the decision-time arrival price. If executed notional is $N_j = q_j \cdot P_j^{\text{arr}}$:
$$C_j^{\text{slip}} = s_j \cdot (q_j P_j^{\text{arr}}) \cdot \frac{P_j^{\text{fill}} - P_j^{\text{arr}}}{P_j^{\text{arr}}} = s_j \cdot q_j \cdot (P_j^{\text{fill}} - P_j^{\text{arr}})$$
- **Buy Adverse Execution ($s_j = +1, P^{\text{fill}} > P^{\text{arr}}$):** $q_j(P^{\text{fill}} - P^{\text{arr}}) > 0$ (positive friction cost).
- **Buy Price Improvement ($s_j = +1, P^{\text{fill}} < P^{\text{arr}}$):** $q_j(P^{\text{fill}} - P^{\text{arr}}) < 0$ (negative cost / gain).
- **Sell Adverse Execution ($s_j = -1, P^{\text{fill}} < P^{\text{arr}}$):** $-q_j(P^{\text{fill}} - P^{\text{arr}}) = q_j(P^{\text{arr}} - P^{\text{fill}}) > 0$ (positive friction cost).
- **Sell Price Improvement ($s_j = -1, P^{\text{fill}} > P^{\text{arr}}$):** $-q_j(P^{\text{fill}} - P^{\text{arr}}) < 0$ (negative cost / gain).

**Critical Implementation Observation (DEF-42-04):**
While `calculate_trade_slippage()` is mathematically sound and passes unit tests in `test_tca_engine.py`, **it is never called anywhere inside `compute_transaction_cost_analysis()` or `_aggregate_fills_subset()`**.
In `backend/app/quant/vine_backtest.py` (lines 868–869, 1103–1104):
```python
arr_p = 100.0
fill_p = arr_p * (1.0 + dir_i * (tot_c / exec_n)) if exec_n > 0 else arr_p
```
The backtest engine reverse-engineers a synthetic `fill_p` from `tot_c`, but `tca.py` does not compute arrival slippage from `fill_p`; it simply sums `f.total_cost`.

---

#### 4.2 Audit B — Opportunity and Delay Cost
The reported formula is:
$$C_j^{\text{opp}} = s_j \cdot N_j^{\text{unexec}} \cdot R_{t, i}$$
where $N_j^{\text{unexec}} = \max(0, N_j^{\text{requested}} - N_j^{\text{executed}})$.

**Independent Numerical Verification:**
1. **Unexecuted Buy with Asset Rising:**
   - Requested: $100,000, Executed: $60,000, $N^{\text{unexec}} = $40,000.
   - Asset return: $R_{t, i} = +5\%$.
   - $C^{\text{opp}} = (+1) \times 40,000 \times (+0.05) = +$2,000 (positive opportunity cost = missed upside).
2. **Unexecuted Buy with Asset Falling:**
   - Asset return: $R_{t, i} = -5\%$.
   - $C^{\text{opp}} = (+1) \times 40,000 \times (-0.05) = -$2,000 (negative opportunity cost = avoided drawdown).
3. **Unexecuted Sell with Asset Falling:**
   - Requested: $100,000, Executed: $60,000, $N^{\text{unexec}} = $40,000.
   - Asset return: $R_{t, i} = -5\%$.
   - $C^{\text{opp}} = (-1) \times 40,000 \times (-0.05) = +$2,000 (positive opportunity cost = unliquidated holding depreciated).
4. **Unexecuted Sell with Asset Rising:**
   - Asset return: $R_{t, i} = +5\%$.
   - $C^{\text{opp}} = (-1) \times 40,000 \times (+0.05) = -$2,000 (negative opportunity cost = unliquidated holding appreciated).

**Critical Accounting Defect Discovered (DEF-42-02):**
In `backend/app/quant/vine_backtest.py` (lines 875 and 1110):
- On the rebalance day (Day 1 of a multi-day schedule), `requested_notional` is assigned as the **entire multi-day intended order** (`intended_notionals.get(tk)`).
- On subsequent queue days (Days 2 .. $D$), `requested_notional` is assigned as the **daily tranche notional** (`tranche_n`).
When `_aggregate_fills_subset()` sums `tot_req = sum(f.requested_notional)`:
For a $90,000 order sliced over 3 days into $30,000 daily tranches:
$$\text{tot\_req} = 90,000 + 30,000 + 30,000 = 150,000$$
$$\text{tot\_exec} = 30,000 + 30,000 + 30,000 = 90,000$$
$$\text{tot\_unexec} = 150,000 - 90,000 = 60,000$$
$$\text{fill\_rate\_pct} = 90,000 / 150,000 = 60.0\%$$
Even though the order was **100% executed over the scheduled horizon**, the TCA engine reports an artificial unexecuted notional of $60,000 and an erroneous fill rate of 60.0%. Furthermore, Day 1 calculates an opportunity cost on the remaining $60,000 that was never unexecuted, merely scheduled for subsequent days.
**Experimental Reproduction:** Verified via test script with 100k ADV and 5-day TWAP: reported requested notional was $186,731.62 vs executed $106,345.35, falsely reporting a 56.95% fill rate.

**Omission on Complete Rejections (DEF-42-05):**
In `vine_backtest.py` lines 830–844: when `rebal_rejected_today` is `True` (e.g. participation policy is `"reject"` and trade exceeds limit), no `TradeFill` is appended. As a result, completely rejected rebalances have zero fills in TCA, and their missed trade opportunity cost is omitted from the TCA report.

---

#### 4.3 Audit C — Cost Decomposition and Exact Reconciliation
The reported decomposition identity is:
$$C^{\text{total}} = C^{\text{spread}} + C^{\text{temp\_impact}} + C^{\text{perm\_impact}} + C^{\text{comm}} + C^{\text{unattributed}}$$
The completion report claimed:
$$C^{\text{unattributed}} \equiv 0.0 \quad (< 10^{-4})$$

**Analysis of the Reconciliation Identity (DEF-42-03):**
1. In `execution.py` line 364:
   $$\text{asset\_cost} = \text{cost\_spread} + \text{cost\_temp} + \text{cost\_perm} + \text{cost\_fee}$$
2. In `vine_backtest.py` lines 879–883, each `TradeFill` is constructed directly from these fields:
   `total_cost = tot_c`, `spread_cost = s_c`, `temp_impact_cost = t_c`, `perm_impact_cost = p_c`, `commission_cost = cm_c`.
3. In `tca.py` lines 229–230:
   `sum_components = tot_spread + tot_temp + tot_perm + tot_comm`
   `unattributed = float(tot_cost - sum_components)`
Because `tot_cost` was defined at creation time as the exact sum of those four numbers, `unattributed` is identically zero **by construction (tautology)**. It is not an empirical reconciliation against an independent market price or external fill report.
4. Furthermore, while the Session 41 report claimed permanent impact is "not modeled at daily resolution", `execution.py` lines 361 actually calculates `cost_perm = trade_exec * (c_perm * daily_vol * min(trade_exec / adv, 1.0))`. When $c_{\text{perm}} = 0.1$, `cost_perm` is non-zero and included in `TradeFill.perm_impact_cost`.

---

#### 4.4 Audit D — Basis Points and Aggregation
The formula used is:
$$C_{\text{bps}} = 10^4 \cdot \frac{C_{\text{total}}}{N_{\text{traded}}}$$
- **Verification:** `_aggregate_fills_subset()` correctly uses the ratio of summed costs to summed executed notionals:
  `eff_bps = (tot_cost / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0`.
  It does not naively average per-trade basis points. Hand calculation confirmed: for a $10,000 trade at 1.0 bps ($1.00 cost) and a $90,000 trade at 10.0 bps ($90.00 cost), the notional-weighted average is $91 / 100,000 \times 10^4 = 9.1$ bps (whereas naive arithmetic average would be 5.5 bps).
- **Observation on Opportunity Bps:** In `tca.py` line 227:
  `opp_bps = (tot_opp / tot_unexec * 10000.0) if tot_unexec > 1e-6 else 0.0`.
  Notice that `opp_bps` uses `tot_unexec` as its denominator, while all other basis point metrics use `tot_exec`. This distinction was omitted from the contract documentation.

---

#### 4.5 Audit E — Fill Capture & Execution Lifecycle
- Single-day fixed-bps fills: captured at lines 699–719.
- Cash-financed rebalance day tranches: captured at lines 871–891.
- Multi-day queue tranches: captured at lines 1106–1126.
- Portfolio equity integrity: verified that `strat_equity` is debited by `cost_today` exactly as before Stage 30. The TCA layer does not alter portfolio cash balances, asset holdings, turnover, or strategy net returns.
- **Event Breakdown Multiplicity:** `compute_transaction_cost_analysis()` groups events by `f.date` (each trading day an execution tranche occurs). For a 5-day schedule, this produces 5 distinct entries in `by_event`. In `test_walk_forward_backtest_tca_integration_and_identity`, `len(by_event) == total_rebalances` passed only because in that test with high ADV, `scheduled_days` happened to be 1 for all rebalances. Under true multi-day scheduling, `len(by_event) > total_rebalances`.

---

#### 4.6 Audit F — Causality and Anti-Lookahead
- Lookback window $[t - \text{estimation\_window} : t]$ strictly terminates at $t-1$ (the close prior to today's decision).
- Point-in-time regime filtering: Gaussian HMM is fitted on historical returns only; forward-filtered probabilities are causal.
- Point-in-time ADVs: estimated over the causal estimation window.
- Mutation invariance: Verified that introducing a 10x return/volume shock 5 days after the first rebalance left the first rebalance's TCA metrics strictly identical ($< 10^{-12}$).
- **Unused Future Lookahead Field (DEF-42-06):** `TradeFill` records `post_trade_returns = [R_{t+1}, ..., R_{t+5}]`. While these forward-looking returns are recorded on the fill dataclass, they are never referenced by `tca.py`.

---

#### 4.7 Audit G — API, Frontend, and Security
**CRITICAL DEFECT: Backend Schema vs Frontend Contract Mismatch (DEF-42-01):**

| Data Concept | Backend Model (`models.py`) | Backend Runtime Dict (`tca.py`) | Frontend Type (`api.ts`) | Frontend JSX Access (`CopulaTailRiskPage.tsx`) |
| :--- | :--- | :--- | :--- | :--- |
| Portfolio Summary | `summary: TCACostMetrics` | `"summary"` | `portfolio_summary: TCACostMetrics` | `backtestResult.tca_report.portfolio_summary.total_cost` |
| Total Cost Bps | `effective_bps: float` | `"effective_bps"` | `total_cost_bps: number` | `...portfolio_summary.total_cost_bps` |
| Traded Notional | `total_executed_notional` | `"total_executed_notional"` | `total_traded_notional` | `...portfolio_summary.total_traded_notional` |
| Spread Bps | `spread_bps: float` | `"spread_bps"` | `spread_cost_bps: number` | `...portfolio_summary.spread_cost_bps` |
| Temp Impact Bps | `temporary_impact_bps: float`| `"temporary_impact_bps"` | `temporary_impact_cost_bps` | `...portfolio_summary.temporary_impact_cost_bps`|
| Perm Impact Bps | `permanent_impact_bps: float`| `"permanent_impact_bps"` | `permanent_impact_cost_bps` | `...portfolio_summary.permanent_impact_cost_bps`|
| Opportunity Bps | `opportunity_bps: float` | `"opportunity_bps"` | `opportunity_cost_bps` | `...portfolio_summary.opportunity_cost_bps` |
| Unattributed Cost | `unattributed_cost: float` | `"unattributed_cost"` | `unattributed_residual` | `...portfolio_summary.unattributed_residual` |
| Fill / Trade Count| `fill_count: int` | `"fill_count"` | `trade_count: number` | `metrics.trade_count` |
| Reconciliation Flag| Not present in `TCAReport` | Not present | `reconciled_with_backtest` | `...tca_report.reconciled_with_backtest` |

**Impact:**
Because `backtestResult.tca_report` contains `"summary"` and NOT `"portfolio_summary"`, `backtestResult.tca_report.portfolio_summary` evaluates to `undefined` in the browser. When React attempts to render:
```tsx
${backtestResult.tca_report.portfolio_summary.total_cost.toFixed(2)}
```
it throws an unhandled:
```
TypeError: Cannot read properties of undefined (reading 'total_cost')
```
which unmounts the page and presents a white screen.
The build (`tsc -b`) passed only because `frontend/src/types/api.ts` was written to match `CopulaTailRiskPage.tsx`, but neither was verified against the actual JSON emitted by the backend.

- **Security & Multi-Tenant Isolation:** Verified that `/copula/vine/backtest` requires JWT authentication, enforces tenant dataset ownership, and validates permissions. Multi-tenant isolation is intact.

---

### 5. Test Execution Evidence

All test suites were executed independently during Session 42.

#### 5.1 Targeted TCA Test Suite
```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_tca_engine.py -v
```
**Result:** 7 passed in 4.82s (0 failed).

#### 5.2 Execution & Walk-Forward Regression Suites
```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_multi_day_execution_scheduling.py backend/tests/test_regime_aware_execution.py backend/tests/test_queue_execution_and_oos_loss.py backend/tests/test_liquidity_backtest_engine.py backend/tests/test_vine_backtest_engine.py -q
```
**Result:** 50 passed in 86.52s (0 failed).

#### 5.3 Full Backend Pytest Suite
```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -q
```
**Result:** 464 passed, 6 warnings in 200.91s (0 failed).

#### 5.4 Frontend Vitest Suite
```bash
npm test -- --run  # in frontend/
```
**Result:** 2 test files passed, 42 tests passed in 11.74s (0 failed).

#### 5.5 Frontend Production Build
```bash
npm run build      # in frontend/
```
**Result:** `tsc -b && vite build` built cleanly in 1.51s (dist/ generated, 0 TypeScript compile errors).

---

### 6. Defect Register

| Defect ID | Severity | File / Component | Description | Recommended Correction |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-42-01** | **HIGH** | `frontend/src/types/api.ts`, `CopulaTailRiskPage.tsx`, `backend/app/copula/models.py` | **Frontend-Backend Contract Mismatch & Runtime TypeError Crash:** Frontend expects `portfolio_summary`, `total_cost_bps`, `total_traded_notional`, `reconciled_with_backtest`, etc., while backend emits `summary`, `effective_bps`, `total_executed_notional`, etc. When `tca_report` renders in the browser, `portfolio_summary.total_cost` throws `TypeError: Cannot read properties of undefined (reading 'total_cost')`. | Align frontend `types/api.ts` and `CopulaTailRiskPage.tsx` with backend `models.py` (or align `models.py`/`tca.py` with the contractual names). Use optional chaining `backtestResult.tca_report?.summary?.total_cost`. |
| **DEF-42-02** | **HIGH** | `backend/app/quant/vine_backtest.py` (lines 875, 1110) | **Multi-Day Queue Requested Notional Double-Counting:** On Day 1, `requested_notional` is set to the full multi-day order ($90k), and on Days 2..D it is set to the tranche ($30k). Summing `requested_notional` across fills yields $150k for a $90k order, artificially depressing the reported fill rate (e.g. to 60%) and recording spurious unexecuted notionals. | For multi-day schedules, record `requested_notional = tranche_n` on Day 1 (or track multi-day orders at the parent order level rather than conflating tranche requested notional with parent order notional). |
| **DEF-42-03** | **MEDIUM** | `backend/app/quant/tca.py` (lines 229–230) | **Tautological Cost Reconciliation:** `unattributed_cost` is calculated as `tot_cost - (spread + temp + perm + comm)`, where `tot_cost` was originally created by summing those exact four values. Claiming an "exact verified empirical reconciliation" is misleading because the residual is zero by construction. | Disclose in documentation and provenance that component decomposition is an exact structural identity of modeled components, rather than an empirical reconciliation against an independent market tape. |
| **DEF-42-04** | **MEDIUM** | `backend/app/quant/tca.py` (line 83), `backend/app/quant/vine_backtest.py` | **Unconnected Signed Slippage Function:** `calculate_trade_slippage()` is implemented and tested as an isolated utility, but is never called inside `compute_transaction_cost_analysis()`. The engine reports `f.total_cost` rather than computing arrival slippage from `arrival_price` and `fill_price`. | Integrate `calculate_trade_slippage()` into `_aggregate_fills_subset()` or explicitly clarify that in daily bar backtesting without intraday quotes, total friction serves as modeled arrival slippage. |
| **DEF-42-05** | **LOW** | `backend/app/quant/vine_backtest.py` (lines 830–844) | **Omission of Canceled/Rejected Rebalances in TCA:** When a rebalance is completely rejected by the participation policy (`rebal_rejected_today = True`), no `TradeFill` is created, omitting the opportunity cost of the rejected trade from TCA. | When a rebalance is rejected, emit zero-fill `TradeFill` records (`executed_notional = 0.0`) to capture the opportunity cost of rejected rebalances. |
| **DEF-42-06** | **LOW** | `backend/app/quant/tca.py` (line 80), `backend/app/quant/vine_backtest.py` (line 870) | **Unused Future Returns on TradeFill:** `TradeFill` stores `post_trade_returns = [R_{t+1}, ..., R_{t+5}]`, which looks into future returns. While not used by `tca.py` (hence no lookahead leakage in reported metrics), storing forward-looking data on an execution fill violates clean causal data encapsulation. | Remove `post_trade_returns` or encapsulate post-trade drift analysis in a distinct post-backtest reporting step. |

---

### 7. Known Limitations

1. **Daily Bar Microstructure Absence:** Without intraday trade-and-quote (TAQ) or order book depth, interval VWAP, bid-ask spread bounces, and permanent post-trade drift cannot be directly observed and are modeled parametrically.
2. **Synthetic Reference Prices:** In return-space backtesting without nominal share prices, `arrival_price` is normalized to 100.0 and `fill_price` is synthesized from modeled friction.
3. **Queue Attribution Event Granularity:** Event-level TCA attribution groups by calendar execution day rather than rebalance parent order ID, causing multi-day scheduled executions to appear as multiple separate events in `by_event`.

---

### 8. Final Audit Recommendation

**Verdict: REQUIRE REMEDIATION BEFORE STAGE 31**

1. **Remediation Priority 1 (DEF-42-01):** Fix the schema contract between `backend/app/copula/models.py`, `backend/app/quant/tca.py`, `frontend/src/types/api.ts`, and `CopulaTailRiskPage.tsx` to eliminate the browser runtime `TypeError`.
2. **Remediation Priority 2 (DEF-42-02):** Fix multi-day tranche requested notional accounting in `vine_backtest.py` so that multi-day orders report correct 100% fill rates and unexecuted notionals.
3. **Remediation Priority 3 (DEF-42-03 & DEF-42-04):** Update `docs/SESSION_41_CONTRACTS.md` and provenance metadata to accurately describe modeled structural reconciliation vs empirical market tape reconciliation.

**Strict Stop:** In compliance with Session 42 instructions, no production code, tests, or documentation files have been modified. The auditor will now stop and await explicit project-owner instructions.
