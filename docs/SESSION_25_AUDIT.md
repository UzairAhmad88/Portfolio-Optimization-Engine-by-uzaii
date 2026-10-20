# SESSION 25 REPOSITORY & MATHEMATICAL AUDIT REPORT

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 25  
**Audit Date:** 2026-10-19  
**Auditor:** Quantitative Systems Lead & Verification Agent (Antigravity)  
**Status:** AUDIT COMPLETE — GATE A ACTIVE (Awaiting User Scope Selection)  

---

## 1. Executive Summary & Working-Tree State

An exhaustive inspection of the working tree, database migration state, test suites, and quantitative mathematics in `backend/app/quant/regime_switching.py` was conducted.

### Working-Tree & Baseline Build Summary
- **Current Branch / Working Tree:** Clean; zero uncommitted or dangling temporary files.
- **Database Migration Head:** Alembic migration head is verified at `b2c3d4e5f6a7 (head)` on SQLite/PostgreSQL schema.
- **Full Backend Regression Suite:**
  - **Command:** `backend\.venv\Scripts\pytest.exe -q`
  - **Execution Time:** 90.24 seconds
  - **Pass Count:** **347 passed, 6 warnings, 0 failed** (100% pass rate).
- **Frontend Test Suite:**
  - **Command:** `npx vitest run --pool=threads` (in `frontend`)
  - **Execution Time:** 12.17 seconds
  - **Pass Count:** **34 passed across 2 test files (30 API client tests, 4 UI shell navigation tests)**.
- **Frontend Production Build:**
  - **Command:** `npm run build` (in `frontend`)
  - **Execution Time:** 1.55 seconds
  - **Result:** **Exit code 0**; TypeScript compilation (`tsc -b`) and Vite production bundle generated cleanly without errors.

---

## 2. Roadmap Milestone Audit (Gate A Gap Analysis)

### Formal Status of Previous Stages
1. **Stage 18 (Session 22):** Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging — *Complete & Verified*.
2. **Stage 19 (Session 23):** Non-Linear Execution Costs, Market Impact Modeling & Optimal Trade Scheduling (Almgren-Chriss Engine) — *Complete & Verified*.
3. **Stage 20 (Session 24):** Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting — *Complete & Verified*.

### Roadmap Status for Stage 21
Inspection of `docs/MASTER_PLAN.md` (lines 116–132) reveals that the roadmap formally concludes at Stage 20. There is **no documented Stage 21** or pre-authorized subsequent milestone.

Per **Non-Negotiable Rule 3 & 4** and **Gate A**:
> *"Do not assume Stage 21 exists or invent its requirements without approval. If the next stage is undefined or ambiguous, present up to three justified candidate scopes and obtain explicit user approval before implementation."*

Implementation cannot begin until the user has formally evaluated and selected the authorized scope for Stage 21.

---

## 3. Mandatory Stage 20 Mathematical Audit (HMM & Volatility Targeting)

A thorough mathematical, dimensional, and numerical safety audit of `backend/app/quant/regime_switching.py` was conducted.

### A. Gaussian Hidden Markov Model (HMM)
- **Model Equations:**
  $$P(s_t = j \mid s_{t-1} = i) = A_{ij}, \quad r_t \mid s_t = k \sim \mathcal{N}(\mu_k, \Sigma_k)$$
- **Stochastic Matrix Properties:**
  - The transition matrix $A$ is row-stochastic: $\sum_{j=1}^M A_{ij} = 1.0$ for all $i \in \{0, \dots, M-1\}$. Verified in code via normalization at line 217: `self.A_ = self.A_ / np.sum(self.A_, axis=1, keepdims=True)`.
  - Initial probabilities $\pi$ satisfy $\sum_{i=0}^{M-1} \pi_i = 1.0$.
  - Covariance matrices $\Sigma_k$ are symmetric and positive-definite: enforced at line 231 via $\Sigma_k \leftarrow \frac{1}{2}(\Sigma_k + \Sigma_k^\top) + 10^{-9} I_N$.
- **Emission Log-Likelihood:**
  - Computed via Cholesky decomposition of $\Sigma_k + 10^{-12} I_N$:
    $$\ln \mathcal{N}(x \mid \mu_k, \Sigma_k) = -\frac{1}{2}\left(N \ln(2\pi) + \ln|\Sigma_k| + (x - \mu_k)^\top \Sigma_k^{-1} (x - \mu_k)\right)$$
  - Cholesky factorization computes $\ln|\Sigma_k| = 2 \sum \ln(L_{ii})$ and solves $L y = x - \mu$ stably without explicit matrix inversion. A singular-matrix fallback uses pseudo-inverse and `slogdet`.

### B. Baum-Welch Expectation-Maximization (EM)
- **Forward-Backward Scaling:**
  - To prevent numerical underflow over long financial time series ($T > 250$), scaling factors $c_t = 1 / \sum_i \alpha_t(i)$ are computed at each step.
  - Forward variables: $\hat{\alpha}_t(j) = c_t \left[\sum_i \hat{\alpha}_{t-1}(i) A_{ij}\right] b_j(r_t)$.
  - Backward variables: $\hat{\beta}_t(i) = c_{t+1} \sum_j A_{ij} b_j(r_{t+1}) \hat{\beta}_{t+1}(j)$.
  - Total log-likelihood: $\ln P(R \mid \theta) = -\sum_{t=0}^{T-1} \ln(c_t)$.
- **Posterior State & Transition Probabilities:**
  - Smoothed state probability: $\gamma_t(i) = \frac{\hat{\alpha}_t(i) \hat{\beta}_t(i)}{\sum_j \hat{\alpha}_t(j) \hat{\beta}_t(j)}$.
  - Expected transitions: $\xi_t(i, j) = \frac{\hat{\alpha}_t(i) A_{ij} b_j(r_{t+1}) \hat{\beta}_{t+1}(j)}{\sum_{k,l} \hat{\alpha}_t(k) A_{kl} b_l(r_{t+1}) \hat{\beta}_{t+1}(l)}$.
  - Parameter updates for $\mu_k$ and $\Sigma_k$ use sample weights $\gamma_t(i)$ normalized by $\sum_{t} \gamma_t(i)$.
- **Convergence:** Monotonic non-decreasing log-likelihood is verified; iteration halts when $|\ln P(R \mid \theta)^{(m)} - \ln P(R \mid \theta)^{(m-1)}| < \text{tol}$.

### C. Deterministic Label-Switching Resolution
- **Permutation Ordering:**
  - Unsupervised HMMs suffer from the label-switching identification problem across different initialization seeds.
  - `GaussianHMM` solves this by computing total regime variance: $\operatorname{Tr}(\Sigma_k) = \sum_{n=1}^N \sigma_{k,n}^2$.
  - State indices are sorted monotonically: $\operatorname{Tr}(\Sigma_0) < \operatorname{Tr}(\Sigma_1) < \dots < \operatorname{Tr}(\Sigma_{M-1})$.
  - The permutation vector `order` is applied simultaneously to:
    $$\pi \leftarrow \pi[\text{order}], \quad A \leftarrow A[\text{order}][:, \text{order}], \quad \mu \leftarrow \mu[\text{order}], \quad \Sigma \leftarrow \Sigma[\text{order}]$$
  - State 0 consistently denotes the lowest-volatility regime.
  - *Economic Governance Note:* Low volatility is a mathematical variance ordering and naming convention, not a universal guarantee of low credit or geopolitical risk.

### D. Causal Filtering vs. Smoothing & Look-Ahead Bias Prevention
- **Causal Forward Filter:**
  $$\hat{\alpha}_t(k) = P(s_t = k \mid r_1, \dots, r_t)$$
  Only data available up to timestamp $t$ is incorporated.
- **Smoothed Posterior:**
  $$\gamma_t(k) = P(s_t = k \mid r_1, \dots, r_T)$$
  Incorporates future observations up to $T$.
- **Walk-Forward Verification:**
  - In `run_regime_switching_walk_forward_backtest`, at each rebalance date $t_k$, the training window is strictly slice $[t_k - W, t_k)$.
  - Allocation decisions condition strictly upon $\hat{\alpha}_{t_k - 1}$ (causal filtered probability).
  - Out-of-sample mutation tests confirmed that modifying returns at $t > t_k$ produces bitwise identical allocations and leverage scalars at $t_k$ ($< 10^{-12}$).

---

## 4. Volatility Targeting & Portfolio Accounting Audit

### A. Dynamic Leverage Multiplier
- **Formula:**
  $$k_t = \min\left(\text{Lev}_{\max}, \frac{\sigma_{\text{target}}}{\hat{\sigma}_{p,t}}\right)$$
  where $\hat{\sigma}_{p,t} = \sqrt{w^\top \mathbf{\Sigma}_{\text{blend}, t} w} \times \sqrt{252}$.
- **Boundary Handling:**
  - Estimated volatility is clamped above $10^{-6}$ to prevent division by zero.
  - Target volatility is constrained to $\sigma_{\text{target}} \in [0.01, 1.0]$.
  - Maximum leverage is constrained to $\text{Lev}_{\max} \in [1.0, 2.5]$.
  - Long-only portfolio weights $w$ scale to $k_t w$.

### B. Cash and Financing Accounting
- **Under-Leveraged Regime ($k_t < 1.0$):**
  - Risky assets receive weight $k_t w$. Unallocated capital $w_{\text{cash}} = 1 - k_t > 0$ is held in risk-free cash.
  - Daily cash return accrues at $w_{\text{cash}} \cdot \frac{r_f}{252} > 0$.
- **Leveraged Regime ($k_t > 1.0$):**
  - Risky assets receive weight $k_t w > 1.0$.
  - Cash balance becomes negative: $w_{\text{cash}} = 1 - k_t < 0$.
  - In code line 523: `cash_ret = current_cash_w * daily_rf`. When $w_{\text{cash}} < 0$, `cash_ret` is negative, accurately modeling borrowing/financing cost at the risk-free rate $r_f$.
- **Budget Invariant:** $\sum w_{\text{risky}} + w_{\text{cash}} = k_t + (1 - k_t) = 1.0$ holds identically.

### C. Frictional Wealth Compounding
- Daily asset returns drift weights: $w_{i, t+1}^{\text{drift}} = \frac{w_{i, t}(1 + R_{i, t})}{1 + R_{p, t}}$.
- At each rebalance epoch, 1-way turnover $\frac{1}{2}\sum |w_i^{\text{target}} - w_i^{\text{drift}}|$ is calculated.
- Transaction costs $\text{Fee} = \text{Equity} \times \text{Turnover} \times c_{\text{bps}} \times 10^{-4}$ are deducted exactly once from capital before reinvestment.

---

## 5. Candidate Scopes for Stage 21 (Gate A Presentation)

To advance the quantitative platform, three institutional candidate directions are proposed:

### Option 1: Multi-Asset Performance Attribution, Brinson-Fachler Decomposition & Systematic Factor Risk Attribution (Stage 21)
- **Business Purpose:** Provide institutional allocators and chief investment officers with audit-grade performance attribution explaining the exact sources of active portfolio return ($R_p - R_b$) relative to a strategic benchmark.
- **Quantitative Rationale:** Implements the Brinson-Fachler (1985) arithmetic and geometric attribution model:
  - **Allocation Effect:** $A_i = (w_{p,i} - w_{b,i})(R_{b,i} - R_b)$
  - **Selection Effect:** $S_i = w_{b,i}(R_{p,i} - R_{b,i})$
  - **Interaction Effect:** $I_i = (w_{p,i} - w_{b,i})(R_{p,i} - R_{b,i})$
  - **Multi-Period Linking:** Applies Cariño logarithmic smoothing factors to eliminate multi-period residual compounding errors such that $\sum_{t} \tilde{A}_t + \tilde{S}_t + \tilde{I}_t \equiv R_p^{\text{cum}} - R_b^{\text{cum}}$.
  - **Karnosky-Singer FX Decomposition:** Extends Stage 18 multi-currency returns into local asset selection, currency allocation, and forward carry contributions.
  - **Systematic Factor Attribution:** Integrates Stage 16 Barra multi-factor models to decompose active risk into factor tilts vs asset selection.
- **Dependencies:** Stage 16 (Factor Model), Stage 18 (Multi-Asset Taxonomy & FX Hedging), Stage 20 (Backtesting Engine).
- **Implementation Risks:** Multi-period geometric linking edge cases when periodic returns approach $-100\%$.
- **Acceptance Criteria:**
  - Analytical 2-asset 2-period worked example matches exact mathematical decomposition to $< 10^{-12}$.
  - Cariño smoothed multi-period attribution reconciles to cumulative active return with zero unexplained residual.
  - Currency attribution reconciles to unhedged and hedged multi-asset returns.
  - Tenant-isolated REST API routes (`POST /api/v1/attribution/brinson`, `POST /api/v1/attribution/factor`).
  - Institutional React 19 / TypeScript workspace with interactive Brinson waterfall charts, allocation vs selection scatter plots, and time-series attribution tables.

### Option 2: Live Broker Order Execution, FIX Protocol Engine & Real-Time Paper Trading (Stage 21)
- **Business Purpose:** Bridge the gap between simulated execution trajectories (Stage 19 Almgren-Chriss) and live electronic order routing by providing a simulated broker gateway, continuous double-auction limit order book (LOB), FIX 4.2 / 4.4 message protocol engine, and real-time paper trading blotter.
- **Quantitative Rationale:** Translates Almgren-Chriss and TWAP/VWAP optimal schedules into discrete market/limit order slices. Models continuous limit order books with price-time priority, queue position, partial fills, non-linear slippage, cancel/replace latency, and maker/taker fee schedules.
- **Dependencies:** Stage 19 (Optimal Execution Engine).
- **Implementation Risks:** Concurrency, asynchronous order state machines, WebSocket connection management, and simulated exchange clock synchronization.
- **Acceptance Criteria:**
  - Deterministic order state machine (New, Partially Filled, Filled, Canceled, Rejected).
  - LOB matching engine accurately fills orders against bid-ask depth with price-time priority.
  - REST and WebSocket endpoints for paper trading and live order tracking.
  - Institutional React trading dashboard with real-time blotter, execution fill charts, and order book depth visualization.

### Option 3: Quantitative Machine Learning Alpha Forecasting & Non-Linear Ensemble Ranking (Stage 21)
- **Business Purpose:** Provide systematic quantitative researchers with non-linear machine learning alpha signal generation, cross-sectional stock ranking, and dynamic feature selection.
- **Quantitative Rationale:** Implements cross-sectional forecasting using Ridge/Lasso regularized regressions, Random Forest / Gradient Boosting decision trees, and Neural Multi-Layer Perceptrons on rolling financial features (momentum, value, volatility, liquidity). Formulates Information Coefficient (IC) and Rank IC (Spearman correlation between predicted scores and realized returns), decile spread returns (Q1 - Q5), and turnover-penalized long/short portfolio construction.
- **Dependencies:** Stage 16/17 (Factor Model & Dynamic Backtester).
- **Implementation Risks:** Overfitting on financial time series, look-ahead leakage in feature standardization/winsorization, and computational latency of rolling cross-validation.
- **Acceptance Criteria:**
  - Purged and embargoed cross-validation (López de Prado) preventing autocorrelation leakage.
  - Exact analytical verification of Spearman Rank IC and Pearson IC on synthetic data.
  - Decile monotonicity tear-sheet (Q1 > Q2 > ... > Q5) and decile long-short spread tracking.
  - Authenticated REST API (`POST /api/v1/ml-forecasting/train`, `POST /api/v1/ml-forecasting/predict`).
  - Institutional React workspace with feature importance bar charts, rolling IC time-series, and cumulative quantile return plots.

---

## 6. Stop Condition & Next Step

Phase A, Phase B, Phase C, and Gate A gap analyses are **COMPLETE**.

Per Non-Negotiable Rules 3, 4, and 10:
**No implementation of Stage 21 has been started.** The agent will now prompt the user via `ask_question` with the three candidate scopes and await explicit authorization.
