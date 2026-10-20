# SESSION 21 AUDIT — Roadmap Gap Verification, Stage 16 Audit & Stage 17 Scope Candidates

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 21  
**Audit Timestamp:** 2026-10-18T18:00:00+05:00  
**Governing Rule:** Master Prompt Section 3: *"If Stage 17 is missing, ambiguous, or inconsistent with other project documents, do not invent its objective. Present the roadmap gap and relevant options, then stop and request explicit approval. Do not silently choose a new quantitative-finance feature merely because it would be useful."*

---

## 1. Executive Summary & Repository Baseline State

A comprehensive pre-implementation audit was conducted across repository code, database migrations, configuration, tests, and documentation:

1. **Current Test Suite Execution Status:**
   - **Backend pytest:** **304 passed**, 0 failed, 4 warnings in 46.25s. Zero regressions across all prior stages.
   - **Frontend vitest:** **27 passed**, 0 failed across 2 test files in 10.59s.
   - **Frontend build:** `npm run build` (`tsc -b && vite build`) executes cleanly with Exit Code 0, transforming 1,944 modules and producing minified production bundles in `dist/`.
   - **Database Migration State:** SQLite Alembic migration is at `b2c3d4e5f6a7 (head)` (`research_experiments` and `research_experiment_runs`). All tables and relationships are fully synchronized.

2. **Roadmap State (`docs/MASTER_PLAN.md`):**
   - Stages 1 through 16 are formally documented and marked `Complete`:
     - Stage 1: Market Data Ingestion & CSV Validation
     - Stage 2: Portfolio Universe & Constraints Definition
     - Stage 3: Numerical Optimization Engine (SLSQP Mean-Variance)
     - Stage 4: Markowitz Efficient Frontier Spectrum
     - Stage 5: Downside Risk Tear-Sheet Analytics
     - Stage 6: Comparative Portfolio Allocations
     - Stage 7: Walk-Forward Backtesting Engine
     - Stage 8: Interactive Institutional Web Dashboard
     - Stage 9: Scenario Analysis & Stress Testing
     - Stage 10: Monte Carlo Risk Simulation, VaR & CVaR
     - Stage 11: Performance Attribution & Benchmark Analysis (Menchero)
     - Stage 12: Research Lab Experiments & Cryptographic Provenance
     - Stage 13: Robust Portfolio Optimization & Estimation Uncertainty
     - Stage 14: Black-Litterman Bayesian View Optimization
     - Stage 15: Equal Risk Contribution (ERC) & Hierarchical Risk Parity (HRP)
     - Stage 16: Advanced Factor Investing, Systematic Risk Decomposition & Multi-Factor Model
   - **Roadmap Gap:** No Stage 17 is currently defined in `docs/MASTER_PLAN.md`, `docs/REQUIREMENTS_SPEC.md`, or `docs/SYSTEM_ARCHITECTURE.md`. In strict adherence to Section 3 of the Master Prompt, implementation is paused until the user explicitly selects and approves the Stage 17 scope.

---

## 2. In-Depth Mathematical & Integration Verification of Stage 16 (Factor Investing)

Before planning Stage 17, the Stage 16 factor model implementation in [`backend/app/quant/factor_model.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/quant/factor_model.py) and service layer in [`backend/app/factor_investing/service.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/factor_investing/service.py) were audited against the criteria in Master Prompt Section 4:

### 2.1 Multivariate OLS Regressions & Statistical Diagnostics
- **Design Matrix:** $X = [\mathbf{1}, F_1, \dots, F_K] \in \mathbb{R}^{T \times (K+1)}$. Solved via `np.linalg.lstsq(X, y, rcond=None)` for numerical stability.
- **Degrees of Freedom & Variance:** $df = T - K - 1$. Specific variance per period is $s_\epsilon^2 = \frac{\text{RSS}}{df}$.
- **Coefficient Standard Errors:** Evaluated via $\operatorname{Var}(\hat{\theta}) = s_\epsilon^2 \cdot \operatorname{diag}((X^\top X)^{-1})$. Falls back to pseudo-inverse `np.linalg.pinv` if $(X^\top X)$ is singular.
- **Hypothesis Testing:** Two-sided p-values evaluated via Student-t survival function $2 \cdot (1 - F_t(|t|; df))$.
- **Goodness-of-Fit:** $R^2 = 1 - \frac{\text{RSS}}{\text{TSS}}$ and Adjusted $R^2 = 1 - (1 - R^2)\frac{T-1}{df}$.
- **Data Validation:** Explicit checks reject NaNs, infinite returns, and insufficient sample lengths ($T \le K + 1$).

### 2.2 Factor Construction & Economic Grounding (Zero Look-Ahead Bias)
- **Market ($MKT$):** Equal-weight cross-sectional excess return $\frac{1}{N}\sum_{i=1}^N (R_{i,t} - r_{f,t})$.
- **Size Proxy ($SMB$):** Volatility-spread deciles subtracting low-volatility asset returns from high-volatility asset returns.
- **Value Proxy ($HML$):** Cumulative historical performance spread subtracting lagging asset returns from leading growth returns.
- **Momentum Proxy ($MOM$):** Trailing rolling window momentum spread subtracting lagging asset returns from top-performing asset returns.
- **PCA Eigen-Factors:** Singular Value Decomposition (SVD) of normalized returns $R_{\text{std}} = U S V^\top$. Factor scores $F_{\text{PCA}} = R_{\text{std}} V_{:k}^\top$. Factor signs are mathematically arbitrary; OLS beta loadings invert accordingly, preserving total variance attribution identically.
- **Zero Look-Ahead Bias:** Factors are deterministically synthesized directly from observed in-sample prices without external fabrication or future information leakage.

### 2.3 Barra Structural Covariance & Risk Decomposition
- **Model Equation:**
  $$\Sigma_{\text{model}} = B \Sigma_F B^\top + \Sigma_\epsilon$$
  where $B \in \mathbb{R}^{N \times K}$ is the factor loadings matrix, $\Sigma_F \in \mathbb{R}^{K \times K}$ is the factor covariance, and $\Sigma_\epsilon = \operatorname{diag}(s_{\epsilon,1}^2, \dots, s_{\epsilon,N}^2)$.
- **Symmetry & Positive Definiteness:** $\Sigma_{\text{model}} = \frac{1}{2}(\Sigma_{\text{model}} + \Sigma_{\text{model}}^\top)$ enforces exact symmetry ($\|\Sigma - \Sigma^\top\|_\infty = 0$). Specific variances along the diagonal are strictly positive ($\ge 10^{-14}$), guaranteeing $\min(\operatorname{eig}(\Sigma)) > 0$ without distorting the covariance structure.
- **Risk Decomposition:**
  $$\sigma_p^2 = \sigma_{\text{sys}}^2 + \sigma_{\text{idio}}^2 = w^\top B \Sigma_F B^\top w + w^\top \Sigma_\epsilon w$$
  Euler factor contributions $\text{Contr}_k = \beta_{p,k}(\Sigma_F \beta_p)_k$ sum exactly to $\sigma_{\text{sys}}^2$.
- **Analytical Benchmark Verification:**
  - 2-asset 1-factor test verified analytically in `test_2_asset_1_factor_analytical_benchmark`:
    - $w = [0.5, 0.5], \beta = [1.2, 0.8], \sigma_F^2 = 0.04, s_\epsilon = [0.01, 0.02]$
    - $\beta_p = 1.0, \sigma_{\text{sys}}^2 = 0.0400, \sigma_{\text{idio}}^2 = 0.0075, \sigma_p^2 = 0.0475, \%_{\text{sys}} \approx 84.21\%$
    - Reconciled to $10^{-12}$.

### 2.4 Factor-Constrained Optimization Solver
- Solves Minimum Variance, Maximum Sharpe, or Maximum Quadratic Utility subject to $\sum w_i = 1$, $w_i \in [w_{\min}, w_{\max}]$, and $\beta_{k,\min} \le B_{:,k}^\top w \le \beta_{k,\max}$ using SciPy SLSQP with analytical Jacobians.
- Solver convergence and constraint satisfaction verified across unit and integration tests.

### 2.5 Security, Tenant Isolation & Boundaries
- Authenticated endpoints `/api/v1/factor-investing/attribute` and `/api/v1/factor-investing/optimize`.
- Tenant isolation enforced via `check_dataset_access`. Cross-tenant queries return HTTP 403/404.

---

## 3. Roadmap Gap Identification & Stage 17 Scope Candidates

In accordance with Master Prompt Section 3, because `docs/MASTER_PLAN.md` concludes at Stage 16, four candidate quantitative finance scopes are proposed for user selection:

### Candidate Option 1 (Recommended): Dynamic Factor Walk-Forward Backtesting & Multi-Factor Alpha Generation Engine
- **Objective:** Extend the Stage 16 static factor model into an out-of-sample dynamic walk-forward strategy engine.
- **Scope & Capabilities:**
  - Rolling estimation window with periodic re-estimation of factor loadings $B_t$ and factor covariance $\Sigma_{F,t}$.
  - Dynamic factor-tilted portfolio rebalancing with turnover constraints, basis-point transaction costs, and execution slippage.
  - Multi-factor momentum, value, and size dynamic tilting strategies.
  - Cumulative active wealth compounding, dynamic factor exposure tracking over time, and realized factor attribution.
- **Dependencies:** Stage 7 (Backtesting Engine), Stage 11 (Performance Attribution), Stage 16 (Factor Investing Core).

### Candidate Option 2: Regime-Switching & Hidden Markov Model (HMM) Portfolio Allocation
- **Objective:** Implement a regime-switching portfolio engine that adapts allocations based on latent macroeconomic/volatility market states.
- **Scope & Capabilities:**
  - 2-state and 3-state Gaussian Hidden Markov Model (HMM) fitted to historical return/volatility panels.
  - Estimation of state transition probability matrices, regime persistence, and regime-conditional expected returns and covariance matrices.
  - Adaptive regime-dependent portfolio allocation (e.g. Max Sharpe in low-volatility expansion; GMV / Equal Risk Contribution / Cash preservation in high-volatility crash regimes).
  - Chronological out-of-sample backtest cross-examining regime-switching portfolios against static buy-and-hold benchmarks.
- **Dependencies:** Stage 3 (Optimization), Stage 7 (Backtesting), Stage 15 (Risk Parity).

### Candidate Option 3: Copula-Based Tail Dependence & Non-Linear Risk Modeling
- **Objective:** Replace linear Gaussian covariance assumptions with non-linear copula tail-dependence models to capture asymmetric joint downside contagion during market panics.
- **Scope & Capabilities:**
  - Bivariate and vine copula modeling (Gaussian, Student-t, Clayton, Gumbel copulas).
  - Estimation of lower tail dependence coefficients $\lambda_L$ and upper tail dependence $\lambda_U$.
  - Copula-based Monte Carlo simulation of joint tail risk, computing Tail Value-at-Risk (TVaR) and Expected Shortfall.
  - Tail-risk-constrained portfolio optimization minimizing Expected Shortfall under asymmetric joint collapse.
- **Dependencies:** Stage 10 (Monte Carlo / VaR / CVaR), Stage 3 (Optimization).

### Candidate Option 4: Direct Exogenous Market & Macro Factor Ingestion Engine (FRED / Macro Integration)
- **Objective:** Integrate external macroeconomic time series (Treasury yield curve, inflation/CPI, credit default spreads, Fed Funds rates) directly into the factor attribution and stress testing framework.
- **Scope & Capabilities:**
  - Macro series schema, normalization, and date synchronization with asset return panels.
  - Macro-conditioned factor regressions and macroeconomic sensitivity betas.
  - Macroeconomic scenario stress testing (e.g. stagflation, yield curve inversion shock, credit spread widening).
- **Dependencies:** Stage 1 (Market Data), Stage 9 (Scenario Analysis), Stage 16 (Factor Investing).

---

## 4. Immediate Action & Stop Condition

In strict accordance with Master Prompt Section 3, Section 8, and Section 10:
- Implementation is stopped until the user reviews this audit and explicitly approves the Stage 17 objective.
- The interactive question modal is invoked below to solicit the user's decision.
