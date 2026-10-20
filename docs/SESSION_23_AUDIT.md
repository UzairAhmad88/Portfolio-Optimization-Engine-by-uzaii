# SESSION 23 AUDIT & ROADMAP GATE REPORT

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 23  
**Auditor:** Senior Quantitative Finance Research Engineer, Systematic Portfolio Manager & Software Quality Auditor  
**Date:** 2026-10-18T19:48:00+05:00  
**Current Milestone Completed:** Stage 18 — Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging Engine  
**Next Milestone Status:** **ROADMAP GAP IDENTIFIED — AWAITING EXPLICIT SELECTION & APPROVAL (GATE A)**

---

## 1. Executive Summary & Repository Baseline

A comprehensive inspection of the workspace, repository state, database migrations, and automated test suites was conducted:

| Component | Verified Status | Evidence |
| :--- | :--- | :--- |
| **Workspace Directory** | `d:\Quants\Projects\quant-portfolio-engine-starter` | Verified clean tree; no extraneous artifacts |
| **Database Migrations** | `b2c3d4e5f6a7 (head)` | Verified via `.venv\Scripts\alembic.exe current` |
| **Backend Test Suite** | **324 passed**, 0 failed (57.81s) | Verified via `pytest -q` |
| **Frontend Test Suite** | **30 passed**, 0 failed (63.92s) | Verified via `vitest run --pool=threads` |
| **Frontend Production Build** | **Exit code 0** (2.19s, 1945 modules) | Verified via `npm run build` (`tsc -b && vite build`) |
| **Stage 18 Implementation** | Complete & passing | `multi_asset.py`, `service.py`, `MultiAssetPage.tsx` |
| **Documented Stage 19** | **MISSING** | `docs/MASTER_PLAN.md` concludes at Stage 18 |

---

## 2. Phase B — Comprehensive Stage 18 Quantitative Audit

Per Section 3 of the Session 23 Master Prompt, all Stage 18 mathematical formulations, numerical routines, and test fixtures were audited and re-derived from first principles.

### A. Local-to-Base Currency Conversion
- **Mathematical Specification:**
  For an asset priced in local currency $c$, where spot FX rate $S_t$ is quoted as base currency units per 1 foreign currency unit (e.g., USD per EUR), the base currency asset price is $P_t^{\text{base}} = P_t^{\text{loc}} \times S_t$.
  The exact 1-period simple return in base currency is:
  $$1 + R_{i,t}^{\text{base}} = \frac{P_{i,t}^{\text{base}}}{P_{i,t-1}^{\text{base}}} = \frac{P_{i,t}^{\text{loc}} S_t}{P_{i,t-1}^{\text{loc}} S_{t-1}} = (1 + R_{i,t}^{\text{loc}})(1 + R_{c(i),t}^{\text{fx}})$$
  Expanding the product:
  $$R_{i,t}^{\text{base}} = R_{i,t}^{\text{loc}} + R_{c(i),t}^{\text{fx}} + R_{i,t}^{\text{loc}} R_{c(i),t}^{\text{fx}}$$
- **Code Audit (`backend/app/quant/multi_asset.py:62-75`):**
  - Domestic assets where `curr.upper() == base_currency.upper()` correctly bypass FX conversion ($R^{\text{base}} = R^{\text{loc}}$).
  - Foreign assets compute `r_base_unhedged = (1.0 + r_loc) * (1.0 + r_fx) - 1.0`, retaining the exact multiplicative cross-term $R^{\text{loc}} R^{\text{fx}}$.
  - Tested across positive and negative local and FX return permutations; reconciled in `test_multi_asset_hand_calculated_analytical_benchmark` to $< 10^{-12}$.

### B. Forward-Hedge Return & Covered Interest Parity (CIP)
- **Mathematical Derivation:**
  Under the convention that $S_t$ is base currency per 1 foreign currency, standard Covered Interest Parity dictates the forward exchange rate:
  $$F_{t, t+1} = S_t \frac{1 + r_{\text{base}}}{1 + r_{\text{foreign}}}$$
  A forward currency contract entered at time $t$ to sell foreign currency forward yields payoff at $t+1$:
  $$\text{Payoff} = h \cdot P_t^{\text{loc}} (F_{t, t+1} - S_{t+1})$$
  Relative to the initial base investment $P_t^{\text{base}} = P_t^{\text{loc}} S_t$, the forward return contribution is:
  $$R_{\text{forward}} = h \left( \frac{F_{t, t+1}}{S_t} - \frac{S_{t+1}}{S_t} \right) = h \left( \frac{1 + r_{\text{base}}}{1 + r_{\text{foreign}}} - (1 + R_t^{\text{fx}}) \right)$$
  Using the discrete carry differential $\text{Carry} = \frac{r_{\text{base}} - r_{\text{foreign}}}{1 + r_{\text{foreign}}} \approx r_{\text{base}} - r_{\text{foreign}}$:
  $$R_{\text{forward}} \approx - h (R_t^{\text{fx}} - \text{Carry})$$
  Adding the hedge overlay to the unhedged asset return:
  $$R_t^{\text{hedged}} = R_t^{\text{unhedged}} - h (R_t^{\text{fx}} - \text{Carry})$$
- **Code Audit (`backend/app/quant/multi_asset.py:77-87`):**
  - Code correctly clips $h \in [0.0, 1.0]$.
  - Daily carry is computed as $\text{daily\_carry} = \text{carry\_rate} / 252.0$.
  - When $h = 1.0$, $R_t^{\text{hedged}} = R_t^{\text{loc}} + \text{daily\_carry} + R_t^{\text{loc}} R_t^{\text{fx}}$.
  - The implementation accurately reflects the market reality that forward contracts hedge the beginning-of-period principal rather than the stochastic within-period capital gain.

### C. Cash Allocation & Cash Drag Modeling
- **Mathematical Formulation:**
  Let $w = [w_1, \dots, w_N]^\top$ be risky asset weights and $w_{\text{cash}}$ be the cash weight.
  Full budget invariant: $\sum_{i=1}^N w_i + w_{\text{cash}} = 1.0$.
  Cash earns risk-free interest: $R_{\text{cash}, t} = r_f^{\text{base}} / 252$.
  Portfolio return: $R_{p,t} = \sum_{i=1}^N w_i R_{i,t} + w_{\text{cash}} R_{\text{cash}, t}$.
  The fully invested risky allocation is $w_i^{\text{fully}} = w_i / (1 - w_{\text{cash}})$, with return $R_{\text{fully}, t} = \sum w_i^{\text{fully}} R_{i,t}$.
  Cash drag relative to the fully invested portfolio is:
  $$\text{Cash Drag}_t = R_{\text{fully}, t} - R_{p,t} = w_{\text{cash}} (R_{\text{fully}, t} - R_{\text{cash}, t})$$
- **Code Audit (`backend/app/quant/multi_asset.py:516-525`):**
  - Confirmed `cash_drag_today = drifted_cash_w * (fully_invested_ret - daily_rf)`.
  - When risky assets outperform cash ($R_{\text{fully}} > r_f$), cash drag is positive (drag on performance).
  - When risky assets underperform cash ($R_{\text{fully}} < r_f$), cash drag is negative (cash cushions portfolio losses).
  - Cash return is included exactly once in daily portfolio compounding.

### D. Multi-Asset & FX Risk Decomposition
- **Covariance Identity Verification:**
  Let local portfolio return be $L_t = \sum_i w_i R_{i,t}^{\text{loc}}$ and currency portfolio return be $F_t = \sum_i w_i R_{c(i),t}^{\text{fx}}$.
  The linear combination variance satisfies:
  $$\operatorname{Var}(L + F) = \operatorname{Var}(L) + \operatorname{Var}(F) + 2 \operatorname{Cov}(L, F)$$
  In matrix notation:
  $$\sigma_p^2 = w^\top \Sigma_{\text{loc}} w + w^\top \Sigma_{\text{fx}} w + 2 w^\top \Sigma_{\text{cross}} w$$
- **Code Audit (`backend/app/quant/multi_asset.py:109-145`):**
  - Local asset covariance `cov_loc`, FX covariance `cov_fx`, and cross-covariance `cov_cross` are annualized by the same factor (252).
  - Total unhedged variance is computed as `var_loc + var_fx + var_cross`.
  - Asset risk share ($\frac{\text{var\_loc}}{\text{total\_var}}$) and FX risk share ($\frac{\text{var\_fx} + \text{var\_cross}}{\text{total\_var}}$) sum to exactly $100\%$.
  - Volatilities are correctly computed via `math.sqrt(var)` rather than conflated with variances.

### E. Walk-Forward Temporal Integrity & Transaction Friction
- **Temporal Boundaries (`backend/app/quant/multi_asset.py:445-455`):**
  - The historical estimation slice is `R_base_matrix[t - estimation_window : t, :]`.
  - In Python slice notation, index `t` is excluded. Therefore, decision at date $t$ utilizes observations strictly up to date $t-1$. Zero look-ahead bias is strictly maintained.
- **Weight Drift & Turnover:**
  - Asset weights drift daily: $w_{i,t} = \frac{w_{i,t-1}(1 + R_{i,t})}{1 + R_{p,t}}$.
  - One-way turnover is $T = \frac{1}{2} \sum |w_i^{\text{new}} - w_i^{\text{drift}}|$.
  - Traded notional is $2 T \times \text{Equity}$.
  - Frictional cost ($c_{\text{bps}} \times 10^{-4} \times \text{Traded Notional}$) is deducted exactly once on rebalance date.
- **Future Mutation Invariance:**
  - Verified by `test_multi_asset_walk_forward_simulation_and_lookahead_bias`: mutating out-of-sample data strictly after rebalance dates produces bitwise identical in-sample allocations to $< 10^{-12}$.

### F. Optimization, Feasibility & Security
- **Hierarchical Constraints:**
  - Group constraints $L_k \le \sum_{i \in \text{Class}_k} w_i \le U_k$ and cash bounds $w_{\text{cash}} \in [w_{\text{min}}, w_{\text{max}}]$ are solved via SLSQP with analytic Jacobian vectors.
  - Infeasible configurations gracefully fall back with structured messages and relaxed boundaries rather than raising unhandled exceptions.
- **Authentication & Multi-Tenant Security:**
  - Endpoints `POST /api/v1/multi-asset/optimize` and `POST /api/v1/multi-asset/backtest` enforce `get_current_active_user` and `check_dataset_access`.
  - Unauthenticated requests return HTTP 401; cross-tenant access returns HTTP 403/404.

---

## 3. Phase A — Roadmap Verification & Identification of Stage 19 Gap

Inspection of [docs/MASTER_PLAN.md](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/MASTER_PLAN.md) establishes that:
- Stages 1 through 18 are documented with explicit acceptance gates and completion records.
- Stage 18 (*Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging Engine*) is the last documented stage.
- **Stage 19 is undefined.** There is no pre-existing title, scope, or acceptance criteria.

Per Gate A rules:
> *"If Stage 19 is missing, ambiguous, or inconsistent with the documented architecture, create an audit document proposing up to three justified next-stage options, with their benefits, dependencies, risks, and acceptance criteria... Ask the user to select or approve a scope. Do not implement a proposed stage without approval."*

---

## 4. Proposed Stage 19 Candidate Scopes for User Approval

Based on the quantitative evolution of the platform (progressing from single-asset equities to robust Bayesian factor models and multi-asset currency overlays), three institutional-grade directions are proposed:

### Candidate Option 1: Non-Linear Execution Costs, Market Impact Modeling & Optimal Trade Scheduling (Almgren-Chriss Engine)
- **Quantitative Rationale:**
  Current backtesting modules (Stages 7, 13, 14, 15, 17, 18) assume linear transaction friction ($c_{\text{bps}} \times \text{Turnover}$). In real institutional trading, large rebalances move market prices non-linearly. The Almgren-Chriss (2000) framework models both permanent price impact (linear in trade size, driven by informational content) and temporary price impact (power-law function of trading rate relative to Average Daily Volume).
- **Core Features:**
  1. *Liquidity & Impact Estimation:* Estimating Average Daily Volume (ADV), percentage spread, and daily volatility from historical price bars.
  2. *Almgren-Chriss Optimal Trajectories:* Solving the dynamic optimization trade-off between market impact cost and price volatility risk across $M$ execution intervals:
     $$\min_{\tau} \mathbb{E}[\text{Cost}] + \lambda \operatorname{Var}[\text{Cost}]$$
  3. *Rebalance Trade Scheduler:* Generating institutional TWAP (Time-Weighted Average Price), VWAP (Volume-Weighted Average Price), and Almgren-Chriss Urgency execution schedules for portfolio rebalance orders.
  4. *Backtesting Integration:* Non-linear execution cost penalties incorporated directly into backtest transaction accounting.
- **Dependencies:** Extends existing backtest data structures; requires trading volume data from ingested datasets.
- **Risks:** Datasets lacking historical volume require fallback to parametric liquidity models.
- **Acceptance Gate:** Reconciles against independent closed-form Almgren-Chriss analytical trajectories; higher risk aversion $\lambda$ produces faster execution; backtest verifies non-linear cost scaling.

---

### Candidate Option 2: Regime-Switching Dynamic Asset Allocation & Hidden Markov Models (HMM)
- **Quantitative Rationale:**
  Financial asset returns and correlations are non-stationary and exhibit discrete structural regimes (e.g., Low-Vol Bull, High-Vol Bear, Crisis). Static or fixed-rolling windows fail to adapt quickly during sudden regime shifts. Hidden Markov Models infer latent market regimes from returns and volatility, allowing allocations to adapt dynamically.
- **Core Features:**
  1. *Hamilton Regime-Switching / Gaussian HMM:* Multi-state (2-state Bull/Bear or 3-state Bull/Bear/Crisis) latent state filtering.
  2. *Strict Temporal Filtering:* Evaluates forward filter probabilities $P(S_t | \mathcal{F}_t)$ with zero look-ahead bias (strictly prohibiting backward smoothing $P(S_t | \mathcal{F}_T)$ during backtesting).
  3. *Regime-Conditional Parameters:* Estimating state-dependent expected returns $\mu(S_t)$ and covariance matrices $\Sigma(S_t)$.
  4. *Dynamic Regime-Switching Rebalancer:* Dynamic allocation shifting between risk-seeking equity tilts in Regime 1 and defensive fixed-income/cash/hedged overlays in Regime 2/3.
  5. *Institutional Workspace:* Interactive regime probability timelines, transition matrices, and regime-conditional equity curves.
- **Dependencies:** SciPy optimization or pure NumPy Baum-Welch EM estimation.
- **Risks:** EM algorithm convergence sensitivity; requires robust numerical guards against local optima.
- **Acceptance Gate:** Filter probabilities sum to 1.0 at each date; zero look-ahead bias verified under future data mutations; transition matrix row stochasticity ($\sum_j P_{ij} = 1$).

---

### Candidate Option 3: Institutional ESG & Carbon Intensity Portfolio Optimization (Climate Risk Constraints)
- **Quantitative Rationale:**
  Modern institutional allocators (Pensions, Sovereign Wealth Funds, UCITS) face regulatory mandates (SFDR, Net Zero Asset Owner Alliance) requiring portfolios to satisfy carbon intensity constraints (Scope 1, 2, 3 emissions per million revenue) and ESG minimum ratings alongside financial risk-return objectives.
- **Core Features:**
  1. *Asset Sustainability Taxonomy:* Integrating ESG ratings and Weighted Average Carbon Intensity (WACI: $\sum w_i C_i$) metrics into asset metadata.
  2. *Carbon-Constrained Mean-Variance Solver:*
     $$\min_w \frac{1}{2} w^\top \Sigma w - \lambda w^\top \mu \quad \text{s.t.} \quad w^\top \mathbf{C} \le \text{Target}, \quad \text{ESG}(w) \ge \text{Target}, \quad \text{TE}(w, w_b) \le \text{TE}_{\max}$$
  3. *Decarbonization Pathway Backtester:* Walk-forward simulation enforcing multi-year decarbonization glide paths (e.g., 7% year-on-year reduction per EU Paris-Aligned Benchmark standards).
  4. *ESG-Efficient Frontier:* Interactive 3D/2D frontier showing the trade-off between Sharpe Ratio, Tracking Error, and Carbon Reduction.
- **Dependencies:** Asset metadata schemas and multi-objective SLSQP solver.
- **Risks:** Non-financial datasets require clear synthetic or mock benchmark proxies when third-party provider feeds (e.g., MSCI, Sustainalytics) are absent.
- **Acceptance Gate:** Portfolio carbon intensity strictly satisfies target thresholds; zero look-ahead bias in annual decarbonization targets.

---

## 5. Mandatory Stop Condition & Action Required

Per Master Prompt Section 1.5, Section 2 (Gate A), and Section 8:
- The roadmap gap has been identified and documented.
- Candidate directions have been formally formulated with quantitative rigor.
- Antigravity is now stopping before implementing any new stage and requesting explicit user selection.
