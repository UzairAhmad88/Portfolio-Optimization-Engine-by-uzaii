# Robust Portfolio Optimization, Estimation Uncertainty & Constraint Sensitivity Contracts

**Specification Version:** 1.0.0  
**Effective Date:** 2026-10-18  
**Module:** `backend/app/quant/robust_optimization.py`, `backend/app/robust/`  
**Governing Standard:** Institutional Quantitative Portfolio Engineering (Session 17)

---

## 1. Scope & Foundational Taxonomy

This document establishes the mathematical, architectural, and data contracts for robust portfolio optimization under parameter and constraint uncertainty. 

The system strictly distinguishes between four distinct quantitative concepts:
1. **Conventional Point-Estimate Optimization:** Solves the canonical Markowitz problem assuming empirical sample estimates $(\hat{\boldsymbol{\mu}}, \hat{\mathbf{\Sigma}})$ are exact, known parameters without estimation noise.
2. **Robust Optimization under Explicit Uncertainty Sets:** Formulates worst-case optimization problems where parameters $\boldsymbol{\mu} \in \mathcal{U}_\mu$ and/or $\mathbf{\Sigma} \in \mathcal{U}_\Sigma$ belong to explicitly bounded convex sets, maximizing minimum utility over the set.
3. **Parametric Sensitivity Analysis:** Evaluates the derivative and behavioral path of optimal weights $\mathbf{w}^*(\theta)$ and risk-return characteristics as uncertainty or constraint parameters $\theta \in [\theta_{\min}, \theta_{\max}]$ vary over a bounded discrete grid.
4. **Historical Out-of-Sample Evaluation:** Evaluates realized portfolio performance across strictly subsequent, non-overlapping historical evaluation windows, verifying that in-sample robustness yields measurable empirical stability without look-ahead bias.

> [!WARNING]
> Robust portfolio optimization minimizes sensitivity to parameter estimation error; it does **not** guarantee future market profitability, eliminate downside volatility, or protect against systematic structural regime breaks.

---

## 2. Input Estimation & Data Contracts

### 2.1 Return & Covariance Estimation Conventions
1. **Return Series:** Let $P_{i,t}$ be the verified closing price of asset $i$ on day $t$. Discrete simple return is:
   $$r_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$$
2. **Sample Expected Return Vector ($\hat{\boldsymbol{\mu}}$):**
   $$\hat{\mu}_i = \frac{1}{T} \sum_{t=1}^T r_{i,t}, \quad \hat{\boldsymbol{\mu}}_{\text{ann}} = m \cdot \hat{\boldsymbol{\mu}}$$
   Where $m$ is the annualization factor ($m = 252$ for US equities, $m = 250$ for PSX equities).
3. **Sample Covariance Matrix ($\hat{\mathbf{\Sigma}}$):**
   $$\hat{\Sigma}_{ij} = \frac{1}{T-1} \sum_{t=1}^T (r_{i,t} - \hat{\mu}_i)(r_{j,t} - \hat{\mu}_j), \quad \hat{\mathbf{\Sigma}}_{\text{ann}} = m \cdot \hat{\mathbf{\Sigma}}$$
4. **Calendar Alignment Invariant:** All inputs must be aligned via listwise deletion (`handle_na="drop_any"`). The number of aligned historical trading sessions $T$ must satisfy $T \ge N + 2$.
5. **Currency Consistency:** All assets in the optimization universe must share the exact same base currency. Cross-currency portfolios without explicit FX adjustment are rejected with HTTP 422.

---

## 3. Mathematical Uncertainty Formulations

### 3.1 Expected-Return Uncertainty Sets

#### A. Box Uncertainty Model
$$\mathcal{U}_{\text{box}}(\boldsymbol{\delta}) = \left\{ \boldsymbol{\mu} \in \mathbb{R}^N : \hat{\mu}_i - \delta_i \le \mu_i \le \hat{\mu}_i + \delta_i, \, \forall i \right\}$$
Where $\delta_i \ge 0$ is the uncertainty radius for asset $i$.
1. **Statistical Standard-Error Calibration:**
   $$\delta_i = \kappa_\mu \cdot \frac{\hat{\sigma}_i}{\sqrt{T}} \cdot \sqrt{m}$$
   Where $\kappa_\mu \ge 0$ is a dimensionless confidence scaling parameter (e.g. $\kappa_\mu = 1.96$ corresponds to a 95% marginal confidence interval for the mean).
2. **Worst-Case Return Formulation:**
   For a portfolio weight vector $\mathbf{w} \in \mathcal{W}$ with long-only weights ($w_i \ge 0$):
   $$\mu^{\text{worst}}(\mathbf{w}) = \min_{\boldsymbol{\mu} \in \mathcal{U}_{\text{box}}} \mathbf{w}^\top \boldsymbol{\mu} = \mathbf{w}^\top (\hat{\boldsymbol{\mu}} - \boldsymbol{\delta}) = \mathbf{w}^\top \hat{\boldsymbol{\mu}} - \sum_{i=1}^N w_i \delta_i$$
   For general weights with short positions permitted:
   $$\mu^{\text{worst}}(\mathbf{w}) = \mathbf{w}^\top \hat{\boldsymbol{\mu}} - \sum_{i=1}^N |w_i| \delta_i = \mathbf{w}^\top \hat{\boldsymbol{\mu}} - \boldsymbol{\delta}^\top |\mathbf{w}|$$

#### B. Ellipsoidal Uncertainty Model
$$\mathcal{U}_{\text{ellip}}(\kappa_e) = \left\{ \boldsymbol{\mu} \in \mathbb{R}^N : (\boldsymbol{\mu} - \hat{\boldsymbol{\mu}})^\top \mathbf{\Omega}^{-1} (\boldsymbol{\mu} - \hat{\boldsymbol{\mu}}) \le \kappa_e^2 \right\}$$
Where $\mathbf{\Omega}$ is the estimation covariance of the mean estimator ($\mathbf{\Omega} = \frac{1}{T} \mathbf{\Sigma}$).
By Cauchy-Schwarz, the worst-case expected return is:
$$\mu^{\text{worst}}(\mathbf{w}) = \min_{\boldsymbol{\mu} \in \mathcal{U}_{\text{ellip}}} \mathbf{w}^\top \boldsymbol{\mu} = \mathbf{w}^\top \hat{\boldsymbol{\mu}} - \kappa_e \sqrt{\mathbf{w}^\top \mathbf{\Omega} \mathbf{w}} = \mathbf{w}^\top \hat{\boldsymbol{\mu}} - \frac{\kappa_e}{\sqrt{T}} \sqrt{\mathbf{w}^\top \mathbf{\Sigma} \mathbf{w}}$$
This proves that ellipsoidal mean uncertainty acts as a direct analytical penalty on portfolio standard deviation ($\sigma_p$).

### 3.2 Covariance Shrinkage & Regularization
Sample covariance matrices are regularized via linear shrinkage:
$$\mathbf{\Sigma}_{\text{shrunk}}(\lambda) = (1 - \lambda) \hat{\mathbf{\Sigma}} + \lambda \mathbf{T}, \quad \lambda \in [0, 1]$$
Where $\lambda$ is the shrinkage intensity. Supported structured targets $\mathbf{T}$:
1. `diagonal`: Preserves diagonal variances while zeroing off-diagonal covariances:
   $$T_{ij} = \begin{cases} \hat{\Sigma}_{ii} & i = j \\ 0 & i \ne j \end{cases}$$
2. `scaled_identity`: Spherical isotropic target:
   $$\mathbf{T} = \bar{\sigma}^2 \mathbf{I}, \quad \bar{\sigma}^2 = \frac{1}{N} \operatorname{Tr}(\hat{\mathbf{\Sigma}})$$
3. `constant_correlation`: Preserves individual variances and shrinks pairwise correlations to their cross-sectional mean $\bar{\rho}$:
   $$T_{ii} = \hat{\Sigma}_{ii}, \quad T_{ij} = \bar{\rho} \sqrt{\hat{\Sigma}_{ii} \hat{\Sigma}_{jj}} \, (i \ne j), \quad \bar{\rho} = \frac{2}{N(N-1)} \sum_{i < j} \frac{\hat{\Sigma}_{ij}}{\sqrt{\hat{\Sigma}_{ii} \hat{\Sigma}_{jj}}}$$

**Mathematical Invariants:**
- For any $\lambda \in [0, 1]$, if $\hat{\mathbf{\Sigma}} \succeq 0$ and $\mathbf{T} \succeq 0$, then $\mathbf{\Sigma}_{\text{shrunk}}(\lambda) \succeq 0$.
- Matrix symmetry is strictly preserved: $\mathbf{\Sigma}_{\text{shrunk}} = \mathbf{\Sigma}_{\text{shrunk}}^\top$.
- When $\lambda = 0$, $\mathbf{\Sigma}_{\text{shrunk}} = \hat{\mathbf{\Sigma}}$ (sample covariance).
- When $\lambda = 1$, $\mathbf{\Sigma}_{\text{shrunk}} = \mathbf{T}$ (pure target).

---

## 4. Supported Robust Optimization Objectives

The robust optimizer supports three core formulations:

### 4.1 Robust Maximum Sharpe Ratio
Maximizes the worst-case Sharpe ratio under expected-return uncertainty $\mathcal{U}_\mu$ and shrunk covariance $\mathbf{\Sigma}_{\text{shrunk}}$:
$$\max_{\mathbf{w} \in \mathcal{W}} \frac{\mu^{\text{worst}}(\mathbf{w}) - R_f}{\sqrt{\mathbf{w}^\top \mathbf{\Sigma}_{\text{shrunk}} \mathbf{w}}}$$
Subject to:
$$\sum_{i=1}^N w_i = 1.0, \quad l_i \le w_i \le u_i, \quad \sum_{i=1}^N |w_i| \le \text{gross\_exposure}$$

### 4.2 Robust Minimum Variance
Minimizes portfolio variance under the shrunk, well-conditioned covariance matrix:
$$\min_{\mathbf{w} \in \mathcal{W}} \mathbf{w}^\top \mathbf{\Sigma}_{\text{shrunk}} \mathbf{w}$$
Subject to portfolio equality and box constraints.

### 4.3 Robust Mean-Variance Utility
Maximizes worst-case risk-adjusted net utility for risk aversion parameter $\gamma > 0$:
$$\max_{\mathbf{w} \in \mathcal{W}} \left( \mu^{\text{worst}}(\mathbf{w}) - \frac{\gamma}{2} \mathbf{w}^\top \mathbf{\Sigma}_{\text{shrunk}} \mathbf{w} \right)$$

---

## 5. Constraint Sensitivity & Stability Diagnostics Contract

### 5.1 Sensitivity Parameter Sweeps
The sensitivity engine computes the optimal portfolio across a 1D discrete parameter grid of maximum 25 evaluation steps:
1. **Weight Cap Sweep:** Evaluates $w_{\max} \in [1/N, 1.0]$ with step count $K \le 20$.
2. **Uncertainty Multiplier Sweep:** Evaluates $\kappa_\mu \in [0.0, 3.0]$ with step count $K \le 20$.
3. **Shrinkage Intensity Sweep:** Evaluates $\lambda \in [0.0, 1.0]$ with step count $K \le 20$.

### 5.2 Stability & Diversification Metrics
For each solution $\mathbf{w}^{\text{robust}}$ compared to baseline $\mathbf{w}^{\text{base}}$:
1. **$L_1$ Weight Distance ($D_1$):**
   $$D_1 = \sum_{i=1}^N |w_i^{\text{robust}} - w_i^{\text{base}}|$$
   Expressed in absolute weight units ($0.0 \le D_1 \le 2.0$ for fully invested long-only portfolios).
2. **Maximum Single-Asset Shift ($\Delta_{\max}$):**
   $$\Delta_{\max} = \max_{i=1,\dots,N} |w_i^{\text{robust}} - w_i^{\text{base}}|$$
3. **Herfindahl-Hirschman Index (Concentration):**
   $$\text{HHI}(\mathbf{w}) = \sum_{i=1}^N w_i^2$$
4. **Effective Number of Assets ($N_{\text{eff}}$):**
   $$N_{\text{eff}} = \frac{1}{\text{HHI}(\mathbf{w})}$$
5. **Turnover Impact:** Estimated rebalancing turnover from baseline to robust allocation.

---

## 6. Numerical Solver Tolerances & Failure Boundaries

1. **Solver Algorithm:** SciPy Sequential Least Squares Programming (SLSQP).
2. **Tolerance Bounds:** Function tolerance $\text{ftol} = 1 \times 10^{-7}$, max iterations = 500.
3. **Feasibility Thresholds:** Constraint violation tolerance $\epsilon_{\text{feas}} = 1 \times 10^{-5}$.
4. **Feasibility Classification:**
   - `converged`: Solver converged and weights satisfy all constraints within $\epsilon_{\text{feas}}$.
   - `infeasible`: Pre-optimization feasibility test failed or solver cannot find feasible point.
   - `failed`: Solver exceeded iteration limits or numerical divergence occurred.
5. **No Synthetic Fallback Guarantee:** Under no circumstances will the system silently alter bounds, relax constraints, or forward-fill synthetic weights. Infeasible problems explicitly return `is_feasible = False` with structured violation messages.

---

## 7. Out-of-Sample Historical Backtesting Contract

To rigorously evaluate whether robust portfolios mitigate estimation risk out-of-sample:
1. **Strict Train/Test Split:** Given historical window $[t_0, t_M]$:
   - **In-Sample Estimation Window:** $[t_0, t_{\text{split}}]$ used strictly to compute $\hat{\boldsymbol{\mu}}$, $\hat{\mathbf{\Sigma}}$, $\boldsymbol{\delta}$, $\mathbf{\Sigma}_{\text{shrunk}}$, and optimal weights $\mathbf{w}^{\text{base}}, \mathbf{w}^{\text{robust}}$.
   - **Out-of-Sample Evaluation Window:** $[t_{\text{split}+1}, t_M]$ used strictly to simulate realization wealth without re-estimation or look-ahead.
2. **Metrics Evaluated:**
   - Realized Cumulative Net Return ($R_{\text{net}}$)
   - Realized Annualized Volatility ($\sigma_{\text{realized}}$)
   - Realized Sharpe Ratio ($S_{\text{realized}}$)
   - Realized Maximum Drawdown ($\text{MDD}$)
   - Total Friction Cost Drag (transaction costs and slippage)
3. **Equivalence Principle:** Both baseline and robust portfolios are evaluated over the exact same out-of-sample dates, start capital ($V_0$), transaction cost rates, and slippage assumptions.
