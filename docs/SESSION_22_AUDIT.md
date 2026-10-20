# SESSION 22 AUDIT — Roadmap Gap Verification, Stage 17 Audit & Stage 18 Scope Candidates

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 22  
**Audit Timestamp:** 2026-10-18T18:42:00+05:00  
**Governing Rule:** Master Prompt Section 3: *"If Stage 18 is missing, ambiguous, or inconsistent with other project documents, do not invent its objective. Present the roadmap gap and relevant options, then stop and request explicit approval. Do not silently choose a new quantitative-finance feature merely because it would be useful."*

---

## 1. Executive Summary & Repository Baseline State

A rigorous pre-implementation audit was conducted across the codebase, test suites, database migrations, and architectural documentation:

1. **Current Test Suite Execution Status:**
   - **Backend pytest:** **314 passed**, 0 failed, 5 warnings in 63.66s.
     - 304 baseline regression tests passed.
     - 5 dynamic factor numerical engine tests (`test_dynamic_factor_backtest.py`) passed.
     - 5 dynamic factor API & security tests (`test_factor_api.py`) passed.
     - Zero regressions across all historical modules (Markowitz, Black-Litterman, HRP, ERC, Monte Carlo, Scenarios).
   - **Frontend vitest:** **28 passed**, 0 failed across 2 test files in 10.87s (`api-client.test.ts` and `App.test.tsx`).
   - **Frontend production build:** `npm run build` (`tsc -b && vite build`) executes cleanly with **Exit Code 0**, transforming 1,944 modules and producing minified production bundles in `dist/`.
   - **Database Migration State:** SQLite Alembic migration is synchronized at `b2c3d4e5f6a7 (head)` (`research_experiments` and `research_experiment_runs`).
2. **Roadmap State (`docs/MASTER_PLAN.md`):**
   - Stages 1 through 17 are formally documented and marked `Complete`:
     - Stage 1: Market Data Ingestion & CSV Validation
     - Stage 2: Financial Mathematics & Statistical Conventions
     - Stage 3: Portfolio Definition & Constraints
     - Stage 4: Optimization Engine (SLSQP Mean-Variance, Min Variance, Max Sharpe)
     - Stage 5: Efficient Frontier Spectrum & Risk Analytics
     - Stage 6: Research Dashboard UI (React 19 / TypeScript / Vite)
     - Stage 7: Walk-Forward Backtesting Engine & Slippage Simulation
     - Stage 8: Production Readiness (PostgreSQL / SQLite, JWT Auth, RBAC, Tenancy)
     - Stage 9: Scenario Analysis, Stress Testing & Sensitivity Sweeps
     - Stage 10: Monte Carlo Simulation, Probabilistic Risk Analysis, VaR & CVaR
     - Stage 11: Performance Attribution & Benchmark Analysis (Menchero)
     - Stage 12: Research Lab Experiments, Strategy Comparison & Provenance Fingerprinting
     - Stage 13: Robust Portfolio Optimization & Estimation Uncertainty Sets
     - Stage 14: Black-Litterman Bayesian View Portfolio Optimization
     - Stage 15: Equal Risk Contribution (ERC) & Hierarchical Risk Parity (HRP)
     - Stage 16: Advanced Factor Investing & Barra Structural Risk Decomposition
     - Stage 17: Dynamic Factor Walk-Forward Backtesting & Multi-Factor Alpha Generation
   - **Roadmap Gap:** No Stage 18 is documented in `docs/MASTER_PLAN.md`, `docs/REQUIREMENTS_SPEC.md`, or `docs/SYSTEM_ARCHITECTURE.md`.
   - In strict compliance with Master Prompt Section 3, implementation is paused until the user explicitly selects and authorizes the Stage 18 objective.

---

## 2. In-Depth Validation of Session 21 (Dynamic Factor Engine)

Before planning Stage 18, the Stage 17 implementation in [`backend/app/quant/dynamic_factor_backtest.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/dynamic_factor_backtest.py), [`backend/app/factor_investing/service.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/factor_investing/service.py), and [`frontend/src/components/pages/FactorInvestingPage.tsx`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/frontend/src/components/pages/FactorInvestingPage.tsx) was validated against Section 4 criteria:

### 2.1 Walk-Forward Integrity & Look-Ahead Prevention
- **Rolling Lookback Windows:** At each rebalance date $t_k$, factor synthesis and multivariate OLS regressions operate strictly on the trailing window slice $R[t_k - W : t_k, :]$ (rows ending strictly at $t_k - 1$).
- **Look-Ahead Invariance:** Re-verified by `test_dynamic_factor_backtest_look_ahead_prevention`: altering future returns occurring after rebalance day $t_k$ leaves historical weights, realized portfolio betas, and risk contributions strictly invariant to $< 10^{-14}$.
- **Boundary Handling:** Minimum estimation window $W \ge 30$ and sample sufficiency $T > W + 5$ are enforced; violations return structured `ValueError` / HTTP 422 errors.

### 2.2 Portfolio Construction & Accounting
- **Asset Weight Drift:** Between rebalance dates, asset weights drift naturally with daily simple returns:
  $$w_{i,t} = \frac{w_{i,t-1}(1 + R_{i,t})}{1 + R_{p,t}}$$
- **1-Way Turnover & Frictional Deductions:** 
  $$\text{Turnover}_{t_k} = \frac{1}{2}\sum_{i=1}^N |w_{i,t_k} - w_{i,t_k}^{\text{drift}}|$$
  $$\text{Cost}_{t_k} = 2.0 \times \text{Turnover}_{t_k} \times \text{Equity}_{t_k} \times \frac{c_{\text{bps}} + s_{\text{bps}}}{10000}$$
  Trading friction is deducted exactly once from capital at the rebalance timestamp.
- **Turnover Penalization:** Solved via smooth Euclidean regularization in SLSQP with analytical gradients; quadratic utility balances expected factor alpha against rebalancing friction.
- **Solver Failure Safeguards:** If factor bounds are infeasible, the engine executes a secondary optimization relaxing factor constraints; if that fails, it falls back to equal weighting with an explicit status diagnostic.

### 2.3 Factor Model Validity & Risk Accounting
- **Economic Grounding:** Synthetic factor proxies ($MKT$, $SMB$, $HML$, $MOM$, $PCA$) are computed deterministically from observed returns.
- **Barra Structural Covariance:** $\Sigma_{\text{model}} = B \Sigma_F B^\top + \Sigma_\epsilon$ enforces exact symmetry and positive semidefiniteness.
- **Exposure Time-Series:** Portfolio factor betas $\beta_{p,k}(t_k) = \sum_i w_i(t_k) \beta_{i,k}(t_k)$ are recorded at every rebalance event and timestamped consistently with optimal allocations.

### 2.4 Security & Integration
- **Authentication & Tenancy:** Strict JWT bearer verification on `POST /api/v1/factor-investing/backtest`; cross-tenant access to private datasets yields HTTP 403 Forbidden / 404 Not Found.
- **Frontend UI Quality:** Tab 3 in `FactorInvestingPage.tsx` handles empty results, solver warnings, interactive SVG chart rendering, and audit tables without console errors.

---

## 3. Roadmap Gap Identification & Candidate Options for Stage 18

Because `docs/MASTER_PLAN.md` concludes at Stage 17, four evidence-based, institutional-grade candidate directions are proposed for user review and approval:

### Option 1 (Recommended): Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging Engine
- **Objective:** Extend the portfolio optimization and risk engine from single-currency homogeneous equities to multi-asset class allocation (Equities, Fixed Income, Commodities, Cash/Treasuries) with explicit multi-currency FX risk decomposition and currency hedging strategies.
- **Scope & Capabilities:**
  - Multi-asset class taxonomy: Asset class classification (Equities, Fixed Income/Bonds, Commodities, Cash).
  - Cash drag & yield modeling: Explicit cash balance earning risk-free rate $r_f$ with dynamic cash rebalancing buffers.
  - Multi-currency / FX risk decomposition: Assets denominated in local currencies ($USD$, $PKR$, $EUR$, $GBP$) converted to base portfolio currency; decompose portfolio variance into asset return variance, FX return variance, and asset-FX cross-covariance:
    $$\sigma_p^2 = w^\top \Sigma_{\text{asset}} w + w^\top \Sigma_{\text{FX}} w + 2 w^\top \Sigma_{\text{cross}} w$$
  - Currency hedging overlay: Fully hedged, unhedged, or partial hedge ratio with forward contract cost-of-carry.
  - Multi-asset constraints: Hierarchical allocation bounds by asset class (e.g. $40\% \le \text{Equities} \le 70\%$, $20\% \le \text{Fixed Income} \le 50\%$, Cash $\ge 5\%$).
  - Chronological walk-forward multi-asset backtest with currency conversion and rebalancing friction.
- **Dependencies:** Stage 3 (Constraints), Stage 4 (Optimization), Stage 7 (Backtest), Stage 11 (Performance Attribution).
- **Institutional Value:** Essential for real-world global multi-asset wealth management and cross-market portfolios (e.g. US + PSX portfolios with PKR/USD dynamics).
- **Risks & Complexity:** Requires handling missing exchange rate dates, aligning currency trading calendars, and maintaining strict cash accounting.

### Option 2: Regime-Switching & Macroeconomic State-Dependent Allocation Engine (Markov & Volatility Regimes)
- **Objective:** Formulate an adaptive portfolio allocation engine that identifies latent or macroeconomic market regimes (e.g. Bull/Low-Vol, Bear/High-Vol, Crisis/Liquidity-Shock) and dynamically switches allocation strategies.
- **Scope & Capabilities:**
  - Statistical regime detection: 2-state / 3-state Hidden Markov Model (HMM) or Gaussian Mixture Model (GMM) calibrated on returns and rolling realized volatility.
  - Regime-conditional parameter estimation: Transition probability matrix $P$, regime-specific return vectors $\mu_s$, and regime covariance matrices $\Sigma_s$.
  - Regime-blended covariance: $\Sigma_{\text{blended}} = \sum_s p_s \Sigma_s + \sum_s p_s (\mu_s - \bar{\mu})(\mu_s - \bar{\mu})^\top$.
  - Dynamic regime allocation policy: Automatic strategy transitions (e.g. Risk-Parity in High-Vol regime, Max Sharpe in Low-Vol regime, Min-Variance / Cash preservation in Crisis).
  - Chronological walk-forward backtest with zero look-ahead bias and realistic detection lag.
- **Dependencies:** Stage 7 (Backtesting), Stage 10 (Monte Carlo), Stage 15 (Risk Parity).
- **Institutional Value:** Protects portfolios against structural market crashes, volatility clustering, and drawdowns.
- **Risks & Complexity:** HMM parameter estimation can be sensitive to initialization and regime labeling stability.

### Option 3: Advanced Execution Cost & Non-Linear Market Impact Modeling (Almgren-Chriss Optimal Execution)
- **Objective:** Upgrade the linear basis-point transaction cost model in backtesting and optimization to institutional non-linear market impact, bid-ask spread liquidity modeling, and capacity analysis.
- **Scope & Capabilities:**
  - Almgren-Chriss market impact formulation: Permanent impact $g(v) = \gamma v$ and temporary impact $h(v) = \eta (v / \text{ADV})^\alpha$.
  - Liquidity-constrained portfolio optimization: Penalizes illiquid assets and enforces volume participation bounds ($w_i \cdot \text{AUM} \le \phi \cdot \text{ADV}_i$).
  - Portfolio capacity frontier: Evaluates Sharpe ratio decay as AUM scales from \$1M to \$100M+.
  - Realized execution attribution: Separates gross performance from spread cost, market impact drag, and timing risk.
- **Dependencies:** Stage 7 (Backtesting Engine), Stage 17 (Dynamic Factor Engine).
- **Institutional Value:** Bridges the critical gap between academic paper backtests and deployable institutional capital management.
- **Risks & Complexity:** Requires trading volume data (ADV) and non-linear solver conditioning.

### Option 4: Signal Combination, Multi-Alpha Blending & Ensembling Engine
- **Objective:** Create a multi-strategy quantitative signal blending engine combining fundamental, momentum, mean-reversion, and statistical arbitrage signals into composite alpha weights.
- **Scope & Capabilities:**
  - Cross-sectional signal scoring: Z-score normalization, Winsorization, Rank-to-Normal quantile transformation.
  - Multi-alpha weighting methods: Equal-signal weighting, Information Ratio (IR) / Information Coefficient (IC) weighting, and orthogonal signal projection.
  - Dynamic signal decay & turnover tuning: Exponential decay smoothing to balance predictive power vs turnover.
  - Out-of-sample signal evaluation: IC time series, cumulative rank IC, and quantile spread decile backtests.
- **Dependencies:** Stage 11 (Performance), Stage 16 (Factor Investing), Stage 17 (Dynamic Factor Backtest).
- **Institutional Value:** Standard systematic hedge fund workflow for combining diverse predictive alpha signals.
- **Risks & Complexity:** Requires robust rank statistics and careful handling of cross-sectional cross-correlations.

---

## 4. Strict Stop Condition

In compliance with Master Prompt Section 3 and Section 9:
- No code modifications for Stage 18 will be initiated until the user reviews this audit and provides explicit authorization for the approved scope.
