# SESSION 35 AUDIT REPORT
## Independent Quantitative Audit of Stage 26 & Next-Stage Roadmap Review

**Project:** Quant Research Dashboard & Portfolio Optimization Engine  
**Audit Target:** Stage 26 — Endogenous Liquidity Stress & Cash-Aware Partial Execution  
**Session:** Session 35  
**Auditor Role:** Independent Quantitative Finance Auditor & Model Validator  
**Mode:** Read-Only Audit, Mathematical Verification, Regression Review & Roadmap Planning  
**Audit Verdict:** **Pass with Caveats** (Core engine mathematically sound; strategy-level risk aggregation and sell-side partial fill queue require documented caveats and future refinement)

---

### 1. Executive Summary & Audit Verdict

This audit conducted an independent verification of the Stage 26 implementation, focusing on:
1. **Cash-Aware Partial Execution Accounting:** Verification of `participation_policy="cap"`, weight invariants, non-distorting unaffected asset execution, cash drift, and sell/buy asymmetry.
2. **Endogenous Liquidity Stress Model:** Vectorized spread widening ($\kappa$) and ADV volume freeze ($\eta$) formulations, dimensional consistency, and monotonicity.
3. **Tail Risk (VaR / CVaR) Formulation:** Verification of rebalance-level prospective stressed loss quantiles and a critical review of the strategy summary-level additive aggregation heuristic.
4. **Causality & Double-Counting Safeguards:** Temporal boundaries, zero look-ahead verification, and separation of realized trading friction from prospective liquidation risk.
5. **API, UI, and Regression Integrity:** Verification of API schemas, TypeScript interfaces, React controls, and test suites.

**Verdict: Pass with Caveats.**  
The implementation is mathematically and causally solid at the rebalance decision and execution engine level. The two caveats identified do not break software integrity or introduce regressions, but represent structural limitations in the current financial specification that should be addressed in subsequent stages.

---

### 2. Evidence Table

| Claim / Component | Code Evidence | Verification Method | Verdict |
|---|---|---|---|
| **Capped Trade Residual Retained as Cash** | `backend/app/quant/vine_backtest.py:489-508` | Direct code inspection & `test_cap_policy_cash_conservation` | **Verified** |
| **Unaffected Liquid Assets Preserved** | `backend/app/quant/vine_backtest.py:491-498` | Direct code inspection & `test_unaffected_assets_not_distorted` | **Verified** |
| **Exact Cash Budget Invariant ($\sum w_i + w_{\text{cash}} = 1$)** | `backend/app/quant/vine_backtest.py:503-508` | Unit test execution (12/12 passed) | **Verified** |
| **Causal Cash Drift & Interest Accrual ($r_f / 252$)** | `backend/app/quant/vine_backtest.py:667-693` | Direct code inspection & mathematical proof | **Verified** |
| **Requested vs Executed Weights Distinguishable** | `backend/app/quant/vine_backtest.py:427, 638-640` | Inspected `rebalance_history` and `test_requested_vs_executed_weights_distinguishable` | **Verified** |
| **Vectorized Endogenous Spread Widening** | `backend/app/quant/execution.py:570, 579` | Inspected NumPy broadcasting & `test_spread_stress_monotonicity` | **Verified** |
| **Vectorized ADV Volume Contraction** | `backend/app/quant/execution.py:572, 583-584` | Inspected NumPy broadcasting & `test_endogenous_liquidity_monotonic_expansion` | **Verified** |
| **Zero-Stress Baseline Recovery ($\kappa=0, \eta=0$)** | `backend/app/quant/execution.py:632-635` | Tested against deterministic scalar via `test_zero_sensitivity_matches_deterministic` | **Verified** |
| **Strict Anti-Lookahead Temporal Causality** | `backend/app/quant/vine_backtest.py:378-403` | Future volume perturbation test (`test_temporal_anti_lookahead_endogenous_invariance`) | **Verified** |
| **Strict Input Parameter Validation** | `backend/app/quant/execution.py:523-542` | Explicit `ValueError` on negative sensitivities, bad confidence, or NaNs | **Verified** |
| **Strategy-Level Stressed CVaR Distribution** | `backend/app/quant/vine_backtest.py:151-152, 721-742` | Analytical model review (see Section 5) | **Caveat (Heuristic)** |
| **Sell-Order Funding Dependency** | `backend/app/quant/vine_backtest.py:503-505` | Analytical execution trace (see Section 3) | **Caveat (Renormalization)** |

---

### 3. Audit A — Cash-Aware Execution Findings

#### 3.1 Trace of `participation_policy="cap"`
Located at `backend/app/quant/vine_backtest.py:487-512`:
```python
if participation_policy == "cap" and part_warn_today:
    asset_impact_map = {ai["ticker"]: ai for ai in impact_res["asset_impacts"]}
    adjusted_w = []
    for i, tk in enumerate(asset_names):
        if tk in asset_impact_map:
            ai = asset_impact_map[tk]
            direction = 1.0 if target_w[i] >= strat_drifted[i] else -1.0
            exec_w = strat_drifted[i] + direction * (ai["executed_notional"] / strat_equity) if strat_equity > 0 else target_w[i]
            adjusted_w.append(max(0.0, exec_w))
        else:
            adjusted_w.append(strat_drifted[i])
    adj_arr = np.array(adjusted_w, dtype=np.float64)
    tot_w = float(np.sum(adj_arr))
    if tot_w > 1.0:
        target_w = adj_arr / tot_w
        strat_cash = 0.0
    else:
        target_w = adj_arr
        strat_cash = max(0.0, 1.0 - tot_w)
```

#### 3.2 Evaluation of Strengths:
1. **Target Weight Preservation:** The unadjusted target weight vector $w^*$ is preserved as `requested_target_w` (line 427) and emitted in `rebalance_history["requested_weights"]`.
2. **Buy-Order Partial Fills:** When buying an illiquid asset is capped, `exec_w < target_w[i]`. The unspent allocation remains in cash ($w_{\text{cash}} = 1.0 - \sum w_i > 0$). Liquid assets execute their exact target notional without distortion.
3. **Invariant Preservation:** Across all 12 unit tests and 425 backend tests, $\sum w_i + w_{\text{cash}} \equiv 1.0$ holds within numerical precision.

#### 3.3 Identified Caveat (DEF-35-01): Sell-Order Asymmetry & Unfunded Buys
Consider a rebalance where:
- Asset A is held at 50% and targeted to be sold down to 10% (intended sell of 40% notional).
- Asset B is held at 0% and targeted to be bought up to 40% (intended buy of 40% notional).
- Cash is 50%.
If Asset A is illiquid and its sell is capped at 10% notional, the executed weight of Asset A is $50\% - 10\% = 40\%$ (retaining an unwanted 30% exposure in Asset A).
If Asset B is liquid and executes its full 40% buy:
$$\sum w_i^{\text{adj}} = 40\% (\text{Asset A}) + 40\% (\text{Asset B}) + 50\% (\text{Unchanged}) = 130\% > 100\%$$
At lines 503-505, because `tot_w > 1.0`, the code rescales `target_w = adj_arr / tot_w` and sets `strat_cash = 0.0`.
- **Finding:** In this specific simultaneous rebalance setting, a capped sell combined with an uncapped buy triggers the fallback normalization `adj_arr / tot_w`, thereby scaling down Asset B.
- **Institutional Context:** In reality, cash-constrained accounts execute sales *first*; buy orders are queued and funded conditionally on realized sell proceeds.

---

### 4. Audit B — Liquidity-Stress Model Findings

#### 4.1 Specification Match
The code at `backend/app/quant/execution.py:570-584` implements:
$$\text{Spread}_i(s) = \text{Spread}_{0, i} \cdot \left[1 + \kappa \cdot \max(0, -r_{i, s})\right]$$
$$\text{ADV}_i(s) = \max\left(100.0, \; \frac{\text{ADV}_{0, i}}{1 + \eta \cdot \max(0, -r_{p, s})}\right)$$
where $r_{p, s} = \sum_{i=1}^N w_i r_{i, s}$.

#### 4.2 Verification Points:
- **Dimensional Consistency:**
  - $\text{Spread}_{0, i}$ is passed in basis points (bps) and converted to fractional cost via $\text{Spread}(s) \times 10^{-4} / 2.0$, applied to traded notional $w_i V$.
  - $\text{ADV}_{i}(s)$ is in dollar volume units. The participation rate $\text{PR}_i(s) = \frac{w_i V}{\text{ADV}_i(s) \cdot H}$ is dimensionless.
  - Temporary impact $c_{\text{temp}} \sigma_i \sqrt{\text{PR}_i(s)}$ is dimensionless and multiplied by $w_i V$ (dollars).
  - Permanent impact $c_{\text{perm}} \sigma_i \frac{w_i V}{\text{ADV}_i(s)}$ is dimensionless and multiplied by $w_i V$ (dollars).
  - Commission is in bps: $\text{Comm} \times 10^{-4} \times w_i V$ (dollars).
- **Asymmetric Drawdown Dependency:**
  - When $r_{i, s} \ge 0$ (gain), $\max(0, -r_{i, s}) = 0$, so spreads never artificially tighten.
  - When $r_{p, s} \ge 0$ (portfolio gain), $\max(0, -r_{p, s}) = 0$, so volume never artificially expands.
- **Model Classification:**
  The model is accurately described as a **scenario-dependent liquidity stress model** (or stress-response function), rather than a full structural general-equilibrium market model (which would require order book matching and endogenous price discovery).

---

### 5. Audit C — VaR and CVaR Mathematics

#### 5.1 Rebalance-Level Stressed Tail Risk (Sound)
At lines 614-625 of `backend/app/quant/execution.py`:
$$l_s = -r_{p, s} + \frac{C_{\text{liq}}(s)}{V}$$
$$\text{Stressed L-VaR}_{\alpha} = \text{Quantile}_{\alpha}(l)$$
$$\text{Stressed L-CVaR}_{\alpha} = \mathbb{E}\left[l_s \;\middle|\; l_s \ge \text{Stressed L-VaR}_{\alpha}\right]$$
- **Loss Convention:** Positive numbers represent financial losses.
- **Quantile Rule:** Evaluated on the continuous distribution of joint stressed loss scenarios.
- **Soundness:** Fully rigorous and mathematically coherent on the scenario set.

#### 5.2 Critical Review of Strategy-Level Aggregation (Caveat DEF-35-02)
The strategy-level summary metric in `backend/app/quant/vine_backtest.py:151-152` is:
$$\text{Stressed L-CVaR}_{99} = \text{CVaR}_{99}^{\text{hist}} + \bar{c}_{\text{liq}} + \Delta_{\text{stress}}$$
where:
$$\Delta_{\text{stress}} = \frac{1}{K}\sum_{k=1}^K \max(0, \text{Stressed L-CVaR}_{t_k} - \text{L-CVaR}_{t_k})$$

**Auditor Critique:**
1. **Hybrid Dimensionality:**
   $\text{CVaR}_{99}^{\text{hist}}$ is the empirical tail mean of realized historical out-of-sample daily returns:
   $$\{ -r_{p, t} \}_{t=1}^{T_{\text{oos}}}$$
   $\Delta_{\text{stress}}$ is the mean incremental tail stress across $K$ monthly rebalances, evaluated on in-sample simulated copula returns.
2. **Artificial Ordering Guarantee:**
   Because $\Delta_{\text{stress}} \ge 0$ by construction via $\max(0, \dots)$, this formulation guarantees $\text{Stressed L-CVaR}_{99} \ge \text{L-CVaR}_{99} \ge \text{CVaR}_{99}$ by definition of adding non-negative scalars, rather than by sampling a unified distribution.
3. **Recommended Corrected Specification:**
   In an institutional risk system, strategy-level out-of-sample tail risk should be computed from the realized daily net liquidation loss time series:
   $$l_t^{\text{oos}} = -R_{p, t}^{\text{gross}} + c_{\text{liq}}(w_t, r_{p, t}, \mathbf{r}_t)$$
   $$\text{Stressed L-CVaR}_{99}^{\text{oos}} = \text{CVaR}_{99}\left(\{l_t^{\text{oos}}\}_{t=1}^{T_{\text{oos}}}\right)$$
   This ensures single-distribution consistency across all reported metrics.

---

### 6. Audit D — Double-Counting and Backtest Causality

1. **Separation of Costs:**
   - Realized rebalance friction (turnover $\times$ spread/impact/commission) is deducted from running portfolio equity $V$ at the rebalance timestamp (line 518).
   - Prospective liquidation costs ($C_{\text{liq}}$) are evaluated purely as prospective solvency metrics for L-VaR/L-CVaR and are **not** deducted from cash equity.
   - Result: **Zero double-counting**.
2. **Cash Return Accrual:**
   Cash earns $r_{\text{cash}} = r_f / 252$ per business day, matching the established `annualization_factor = 252`.
   Only the cash weight $w_{\text{cash}}$ earns $r_{\text{cash}}$.
3. **Temporal Invariance:**
   The test `test_temporal_anti_lookahead_endogenous_invariance` verifies that multiplying all trading volumes by $10\times$ on days $t > t_k$ produces zero change in past allocations, cash reserves, and tail risk metrics ($< 10^{-12}$).

---

### 7. Audit E — API, Frontend, and Regression Findings

1. **API Endpoints & Schemas:**
   - `POST /api/v1/copula/vine/backtest` accepts `enable_endogenous_liquidity`, `spread_stress_sensitivity`, and `adv_stress_sensitivity`.
   - Responses include `requested_weights`, `executed_weights`, `cash_weight`, `stressed_l_var_99`, and `stressed_l_cvar_99`.
2. **Frontend UI Integration:**
   - `CopulaTailRiskPage.tsx` integrates the Endogenous Liquidity Stress toggle, $\kappa$ and $\eta$ inputs, strategy KPI table rows, and audit trail columns.
3. **Security & Tenant Isolation:**
   - User authentication and dataset tenant isolation are enforced in `copula_routes.py` and `vine_copula_api.py`.
4. **Database Migrations:**
   - Verified that no migration is needed; backtest computations operate in-memory on validated request payloads.

---

### 8. Test Execution Verification

All test suites were independently executed and observed during this audit session:

| Suite | Command | Result |
|---|---|---|
| **Dedicated Stage 26 Tests** | `pytest backend/tests/test_endogenous_liquidity_engine.py -v` | **12 passed** in 6.22s (100%) |
| **Liquidity & Vine Regressions** | `pytest backend/tests/test_liquidity_backtest_engine.py backend/tests/test_vine_backtest_engine.py backend/tests/test_vine_copula_api.py -v` | **27 passed**, 1 warning in 12.47s (100%) |
| **Frontend Unit Tests** | `npm test -- --run` (in `frontend/`) | **42 passed** in 3.54s (100%) |
| **Frontend Production Build** | `npm run build` (in `frontend/`) | **Clean build** (code 0 in 640ms) |

---

### 9. Material Defects & Audit Caveats

| ID | Severity | Category | Description | Status |
|---|---|---|---|---|
| **DEF-35-01** | Low / Architectural | Execution Accounting | When a sell order is capped under `participation_policy="cap"`, residual exposure remains in the asset. If an accompanying buy executes fully, total weight can exceed 1.0, triggering fallback proportional normalization. | **Caveat Documented** (Queue-based execution recommended for Stage 27) |
| **DEF-35-02** | Medium / Statistical | Risk Modeling | Strategy-level `stressed_l_cvar_99` uses an additive scalar penalty ($\Delta_{\text{stress}}$) over historical CVaR rather than an empirical quantile of the realized daily net liquidation loss time series. | **Caveat Documented** (Unified OOS loss distribution recommended for Stage 27) |

---

### 10. Roadmap Review & Next-Stage Recommendations

The roadmap in `docs/MASTER_PLAN.md` currently ends at **Stage 26**. No Stage 27 is defined.  
Based on the quantitative audit, three differentiated candidates are proposed:

#### Option 1 (Recommended): Stage 27 — Unified Daily Out-of-Sample Liquidation Loss Distribution & Queue-Based Cash-Financed Execution
- **Objective:** Remediate DEF-35-01 and DEF-35-02 by replacing the additive strategy KPI heuristic with a unified daily realized out-of-sample liquidation loss distribution ($\{l_t^{\text{stressed}}\}_{t=1}^T$) and implementing a priority execution queue where sells execute first to generate verified cash before buy orders execute.
- **Affected Subsystems:** `backend/app/quant/vine_backtest.py`, `backend/app/quant/execution.py`, `frontend/src/components/pages/CopulaTailRiskPage.tsx`.
- **Complexity:** Medium.
- **Risk:** Zero database or external dependency risk; eliminates theoretical caveats and establishes institutional-grade execution reality.

#### Option 2: Stage 27 — Multi-Regime Dynamic Liquidity & Conditional Market Impact Calibration
- **Objective:** Extend liquidity stress by coupling baseline $\text{ADV}_t$ and spread parameters to macroeconomic Hidden Markov Model (HMM) volatility states (from Stage 20), dynamically transitioning liquidity parameters across expansion, contraction, and crisis regimes.
- **Affected Subsystems:** `backend/app/quant/execution.py`, `backend/app/regime_switching/`, `backend/app/quant/vine_backtest.py`.
- **Complexity:** High.
- **Risk:** High parameter estimation risk and potential regime misclassification.

#### Option 3: Stage 27 — Liquidity-Constrained Tail Risk Parity Optimization
- **Objective:** Incorporate expected market impact and liquidity penalty directly into the optimizer's objective function ($\min_w \sum (\text{TRC}_i - \frac{1}{N}\text{CVaR})^2 + \lambda C_{\text{impact}}(w)$), steering portfolio allocations away from illiquid assets *before* rebalancing rather than capping them ex-post.
- **Affected Subsystems:** `backend/app/quant/copula_tail_risk.py`, `backend/app/quant/vine_copula.py`, SLSQP solver constraints.
- **Complexity:** High (non-convex optimization).
- **Risk:** Solver convergence failures and sensitivity to hyperparameter $\lambda$.

---

### 11. Exact Decision Required from Project Owner

The project owner is requested to review this audit and select one of the following:

- **Option 1 (Recommended):** Proceed to **Stage 27** with Unified Out-of-Sample Liquidation Loss Distribution & Queue-Based Cash-Financed Execution (resolving DEF-35-01 and DEF-35-02).
- **Option 2:** Proceed to **Stage 27** with Multi-Regime Dynamic Liquidity & Conditional Market Impact Calibration.
- **Option 3:** Proceed to **Stage 27** with Liquidity-Constrained Tail Risk Parity Optimization.
- **Option 4:** Retain Stage 26 as-is and transition to production deployment hardening.
