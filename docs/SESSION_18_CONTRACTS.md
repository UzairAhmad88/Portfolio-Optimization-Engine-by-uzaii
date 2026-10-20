# Black-Litterman Portfolio Optimization & Bayesian View Incorporation Contracts

**Specification Version:** 1.0.0  
**Effective Date:** 2026-10-18  
**Module:** `backend/app/quant/black_litterman.py`, `backend/app/black_litterman/`  
**Governing Standard:** Institutional Quantitative Portfolio Engineering (Session 18)  

---

## 1. Mathematical Formulation

The Black-Litterman model (Black & Litterman 1992, He & Litterman 1999) formalizes a Bayesian approach to portfolio optimization. It combines the neutral market equilibrium return distribution (prior) with explicit analyst views (likelihood) to derive a well-conditioned posterior return distribution without extreme corner allocations.

### 1.1 Market Implied Equilibrium Returns (The Prior)
Let $N$ be the number of assets. Let $\mathbf{\Sigma} \in \mathbb{R}^{N \times N}$ be the annualized asset covariance matrix, and $\mathbf{w}_{\text{eq}} \in \mathbb{R}^N$ be the market equilibrium or benchmark asset weights ($\sum_{i=1}^N w_{\text{eq},i} = 1.0$).

Under mean-variance equilibrium, the implied excess returns $\boldsymbol{\Pi} \in \mathbb{R}^N$ satisfy:
$$\boldsymbol{\Pi} = \gamma \mathbf{\Sigma} \mathbf{w}_{\text{eq}}$$

Where $\gamma > 0$ is the market risk-aversion coefficient:
$$\gamma = \frac{\mathbb{E}[R_m] - R_f}{\sigma_m^2}$$
If market portfolio return and variance are not directly observed, an institutional convention sets $\gamma = 2.50$ or computes it directly from the equilibrium benchmark.

The prior distribution on asset expected returns is:
$$\mathbf{r} \sim \mathcal{N}(\boldsymbol{\Pi}, \tau \mathbf{\Sigma})$$
where $\tau > 0$ represents the uncertainty in the prior equilibrium estimate (typically $\tau \in [0.01, 0.10]$ or $\tau = 1/T$).

### 1.2 Investor Views & Uncertainty Matrix (The Likelihood)
Let $K$ be the number of independent investor views. Views are expressed as a linear system:
$$\mathbf{P} \mathbf{r} = \mathbf{q} + \boldsymbol{\epsilon}, \quad \boldsymbol{\epsilon} \sim \mathcal{N}(\mathbf{0}, \mathbf{\Omega})$$
where:
- $\mathbf{P} \in \mathbb{R}^{K \times N}$ is the view pick matrix.
  - **Absolute view on asset $i$:** $P_{k,i} = 1$, $P_{k,j} = 0$ ($j \ne i$), $q_k = \text{expected return}$.
  - **Relative view ("Asset $i$ outperforms Asset $j$ by $d$"):** $P_{k,i} = 1$, $P_{k,j} = -1$, $P_{k,l} = 0$, $q_k = d$.
- $\mathbf{q} \in \mathbb{R}^K$ is the vector of view target returns.
- $\mathbf{\Omega} \in \mathbb{R}^{K \times K}$ is the diagonal covariance matrix of view errors.

#### Calibrating View Uncertainty ($\mathbf{\Omega}$)
Two institutional methods are supported:
1. **He-Litterman Proportional Variance:**
   $$\Omega_{kk} = \mathbf{P}_k (\tau \mathbf{\Sigma}) \mathbf{P}_k^\top$$
   View variances are proportional to the intrinsic variance of the view portfolio.
2. **Idzorek's Confidence Calibration:**
   Let $c_k \in (0, 1)$ be the researcher's confidence in view $k$. View variance scales inversely with confidence:
   $$\Omega_{kk} = \frac{1 - c_k}{c_k} \mathbf{P}_k (\tau \mathbf{\Sigma}) \mathbf{P}_k^\top$$
   When $c_k \to 1$ (100% confidence), $\Omega_{kk} \to 0$ (unyielding constraint). When $c_k \to 0$, $\Omega_{kk} \to \infty$ (view ignored).

### 1.3 The Master Black-Litterman Bayesian Posterior
Combining the normal prior $\mathcal{N}(\boldsymbol{\Pi}, \tau \mathbf{\Sigma})$ and normal likelihood $\mathcal{N}(\mathbf{P}^\top \mathbf{q}, \mathbf{\Omega})$, the posterior distribution of expected returns is $\mathbf{r} \sim \mathcal{N}(\boldsymbol{\mu}_{\text{BL}}, \mathbf{M})$:

#### Posterior Expected Return:
$$\boldsymbol{\mu}_{\text{BL}} = \left[ (\tau \mathbf{\Sigma})^{-1} + \mathbf{P}^\top \mathbf{\Omega}^{-1} \mathbf{P} \right]^{-1} \left[ (\tau \mathbf{\Sigma})^{-1} \boldsymbol{\Pi} + \mathbf{P}^\top \mathbf{\Omega}^{-1} \mathbf{q} \right]$$

Via the Woodbury matrix inversion identity, this is equivalently computed as:
$$\boldsymbol{\mu}_{\text{BL}} = \boldsymbol{\Pi} + \tau \mathbf{\Sigma} \mathbf{P}^\top \left[ \mathbf{P} (\tau \mathbf{\Sigma}) \mathbf{P}^\top + \mathbf{\Omega} \right]^{-1} (\mathbf{q} - \mathbf{P} \boldsymbol{\Pi})$$
This formulation avoids inverting $\mathbf{\Sigma}$ directly, which ensures numerical stability when $N > K$.

#### Posterior Covariance Matrix:
The predictive posterior covariance matrix including parameter estimation uncertainty is:
$$\mathbf{\Sigma}_{\text{post}} = \mathbf{\Sigma} + \mathbf{M}$$
$$\mathbf{M} = \left[ (\tau \mathbf{\Sigma})^{-1} + \mathbf{P}^\top \mathbf{\Omega}^{-1} \mathbf{P} \right]^{-1} = \tau \mathbf{\Sigma} - \tau \mathbf{\Sigma} \mathbf{P}^\top \left[ \mathbf{P} (\tau \mathbf{\Sigma}) \mathbf{P}^\top + \mathbf{\Omega} \right]^{-1} \mathbf{P} (\tau \mathbf{\Sigma})$$

### 1.4 Unconstrained vs. Constrained Allocation
- **Unconstrained Black-Litterman Optimal Weights:**
  $$\mathbf{w}_{\text{BL}} = \frac{1}{\gamma} \mathbf{\Sigma}^{-1} \boldsymbol{\mu}_{\text{BL}}$$
- **Constrained Black-Litterman Optimization:**
  When institutional constraints (long-only $w_i \ge 0$, individual caps $w_i \le u_i$, or gross exposure limits) are imposed, $\boldsymbol{\mu}_{\text{BL}}$ and $\mathbf{\Sigma}_{\text{post}}$ are passed to SciPy SLSQP to solve:
  $$\max_{\mathbf{w} \in \mathcal{W}} \frac{\mathbf{w}^\top \boldsymbol{\mu}_{\text{BL}} - R_f}{\sqrt{\mathbf{w}^\top \mathbf{\Sigma}_{\text{post}} \mathbf{w}}} \quad \text{or} \quad \max_{\mathbf{w} \in \mathcal{W}} \left( \mathbf{w}^\top \boldsymbol{\mu}_{\text{BL}} - \frac{\gamma}{2} \mathbf{w}^\top \mathbf{\Sigma}_{\text{post}} \mathbf{w} \right)$$
  Subject to:
  $$\sum_{i=1}^N w_i = 1.0, \quad l_i \le w_i \le u_i, \quad \sum_{i=1}^N |w_i| \le \text{gross\_exposure}$$

---

## 2. Worked Analytical Reference Benchmark

Consider a 2-asset universe with equal equilibrium weights:
$$\mathbf{w}_{\text{eq}} = \begin{bmatrix} 0.50 \\ 0.50 \end{bmatrix}, \quad \gamma = 2.50, \quad \tau = 0.05$$
Sample covariance matrix (annualized):
$$\mathbf{\Sigma} = \begin{bmatrix} 0.04 & 0.01 \\ 0.01 & 0.09 \end{bmatrix}$$

### Step 1: Equilibrium Implied Returns
$$\boldsymbol{\Pi} = 2.50 \begin{bmatrix} 0.04 & 0.01 \\ 0.01 & 0.09 \end{bmatrix} \begin{bmatrix} 0.50 \\ 0.50 \end{bmatrix} = 2.50 \begin{bmatrix} 0.025 \\ 0.050 \end{bmatrix} = \begin{bmatrix} 0.0625 \\ 0.1250 \end{bmatrix}$$

### Step 2: Single Relative View
Researcher states: "Asset 1 will outperform Asset 2 by 2.0% ($0.020$)":
$$\mathbf{P} = \begin{bmatrix} 1 & -1 \end{bmatrix}, \quad q = 0.020$$
Prior expected difference from equilibrium is:
$$\mathbf{P} \boldsymbol{\Pi} = 0.0625 - 0.1250 = -0.0625$$
View discrepancy:
$$q - \mathbf{P} \boldsymbol{\Pi} = 0.020 - (-0.0625) = +0.0825$$

### Step 3: He-Litterman View Variance
$$\mathbf{P} (\tau \mathbf{\Sigma}) \mathbf{P}^\top = 0.05 \begin{bmatrix} 1 & -1 \end{bmatrix} \begin{bmatrix} 0.04 & 0.01 \\ 0.01 & 0.09 \end{bmatrix} \begin{bmatrix} 1 \\ -1 \end{bmatrix} = 0.05 \times (0.04 - 0.01 - 0.01 + 0.09) = 0.05 \times 0.11 = 0.0055$$
$$\Omega = 0.0055$$

### Step 4: Posterior Adjustment
$$\mathbf{P} (\tau \mathbf{\Sigma}) \mathbf{P}^\top + \Omega = 0.0055 + 0.0055 = 0.0110$$
$$\left[ \mathbf{P} (\tau \mathbf{\Sigma}) \mathbf{P}^\top + \Omega \right]^{-1} (q - \mathbf{P} \boldsymbol{\Pi}) = \frac{0.0825}{0.0110} = 7.50$$
$$\tau \mathbf{\Sigma} \mathbf{P}^\top = 0.05 \begin{bmatrix} 0.04 & 0.01 \\ 0.01 & 0.09 \end{bmatrix} \begin{bmatrix} 1 \\ -1 \end{bmatrix} = 0.05 \begin{bmatrix} 0.03 \\ -0.08 \end{bmatrix} = \begin{bmatrix} 0.0015 \\ -0.0040 \end{bmatrix}$$
$$\boldsymbol{\mu}_{\text{BL}} = \begin{bmatrix} 0.0625 \\ 0.1250 \end{bmatrix} + \begin{bmatrix} 0.0015 \\ -0.0040 \end{bmatrix} \times 7.50 = \begin{bmatrix} 0.0625 + 0.01125 \\ 0.1250 - 0.03000 \end{bmatrix} = \begin{bmatrix} 0.07375 \\ 0.09500 \end{bmatrix}$$

**Conclusion:** The view that Asset 1 will outperform Asset 2 lifts Asset 1's expected return from $6.25\%$ to $7.375\%$ and reduces Asset 2's return from $12.50\%$ to $9.50\%$. The relative spread narrows from $-6.25\%$ to $-2.125\%$, smoothly incorporating the view proportional to confidence. This analytical example is codified in unit tests.

---

## 3. Limiting & Invariant Behavior

1. **Zero Views ($K = 0$):**
   $$\boldsymbol{\mu}_{\text{BL}} = \boldsymbol{\Pi}, \quad \mathbf{\Sigma}_{\text{post}} = (1 + \tau) \mathbf{\Sigma}$$
   The optimal portfolio matches the equilibrium portfolio: $\mathbf{w}^* = \mathbf{w}_{\text{eq}}$.
2. **Absolute Confidence ($c_k \to 1 \implies \Omega_{kk} \to 0$):**
   The posterior projection enforces $\mathbf{P}_k \boldsymbol{\mu}_{\text{BL}} = q_k$ exactly.
3. **Zero Confidence ($c_k \to 0 \implies \Omega_{kk} \to \infty$):**
   The view has zero weight in the posterior update; $\boldsymbol{\mu}_{\text{BL}} \to \boldsymbol{\Pi}$.
4. **Covariance Symmetry & Positive Definiteness:**
   $$\mathbf{\Sigma}_{\text{post}} = \mathbf{\Sigma}_{\text{post}}^\top, \quad \min(\operatorname{eig}(\mathbf{\Sigma}_{\text{post}})) > 0$$
   Guaranteed by the additive formulation $\mathbf{\Sigma}_{\text{post}} = \mathbf{\Sigma} + \mathbf{M}$ where both $\mathbf{\Sigma} \succ 0$ and $\mathbf{M} \succeq 0$.

---

## 4. Input & Output Data Contracts

### 4.1 Request Contract (`BlackLittermanOptimizeRequest`)
```json
{
  "dataset_id": "string (UUID)",
  "assets": ["string (Ticker/ID)"],
  "start_date": "string (YYYY-MM-DD, optional)",
  "end_date": "string (YYYY-MM-DD, optional)",
  "tau": 0.05,
  "risk_aversion": 2.50,
  "equilibrium_weights": {
    "AAPL": 0.50,
    "MSFT": 0.50
  },
  "views": [
    {
      "view_type": "relative",
      "assets": ["AAPL", "MSFT"],
      "weights": [1.0, -1.0],
      "target_return": 0.02,
      "confidence": 0.75
    }
  ],
  "objective": "max_sharpe",
  "constraints": {
    "default_min_weight": 0.0,
    "default_max_weight": 1.0,
    "target_total_weight": 1.0,
    "allow_short": false
  },
  "risk_free_rate": 0.02
}
```

### 4.2 Response Contract (`BlackLittermanOptimizeResponse`)
```json
{
  "dataset_id": "string",
  "assets": ["AAPL", "MSFT"],
  "equilibrium_returns": { "AAPL": 0.0625, "MSFT": 0.1250 },
  "posterior_returns": { "AAPL": 0.07375, "MSFT": 0.0950 },
  "prior_weights": { "AAPL": 0.50, "MSFT": 0.50 },
  "unconstrained_bl_weights": { "AAPL": 0.58, "MSFT": 0.42 },
  "optimal_weights": { "AAPL": 0.58, "MSFT": 0.42 },
  "active_tilts": { "AAPL": 0.08, "MSFT": -0.08 },
  "portfolio_metrics": {
    "expected_return": 0.0827,
    "volatility": 0.1412,
    "sharpe_ratio": 0.444
  },
  "is_feasible": true,
  "solver_status": "converged",
  "views_summary": [
    {
      "description": "AAPL outperforms MSFT by 2.0%",
      "confidence": 0.75,
      "prior_spread": -0.0625,
      "posterior_spread": -0.02125
    }
  ]
}
```

---

## 5. Chronological Out-of-Sample Backtesting Contract

When backtesting Black-Litterman allocations:
1. Historical price bars up to in-sample date $T_{\text{train}}$ are used to compute sample covariance $\mathbf{\Sigma}$ and implied equilibrium returns $\boldsymbol{\Pi}$.
2. Analyst views ($P, q, \Omega$) are declared using in-sample assumptions.
3. The posterior return $\boldsymbol{\mu}_{\text{BL}}$ and covariance $\mathbf{\Sigma}_{\text{post}}$ are computed strictly from training inputs.
4. Optimal weights are evaluated out-of-sample ($t > T_{\text{train}}$) using discrete compounding with realistic transaction costs and slippage.
5. **Zero Look-Ahead Rule:** Under no circumstances do evaluation-period returns contaminate covariance estimation, equilibrium calculations, or view calibration.

---

*Contract Approved.*
