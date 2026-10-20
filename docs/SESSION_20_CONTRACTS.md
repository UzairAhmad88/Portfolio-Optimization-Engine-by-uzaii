# SESSION 20 CONTRACTS — Advanced Factor Investing, Systematic Risk Decomposition & Multi-Factor Optimization

**Document Version:** 1.0.0  
**Status:** Approved & Implemented  
**Date:** 2026-10-18  

---

## 1. Mathematical Specifications & Core Formulations

### 1.1 Multi-Factor Return Model
Asset excess returns $R_{i,t}^e = R_{i,t} - R_{f,t}$ are modeled via linear multi-factor regression:
$$R_{i,t}^e = \alpha_i + \sum_{k=1}^K \beta_{i,k} F_{k,t} + \epsilon_{i,t}, \quad t = 1, \dots, T$$
where:
- $F_{k,t}$ is the excess return of factor $k$ at time $t$.
- $\beta_{i,k}$ is the factor loading (sensitivity) of asset $i$ to factor $k$.
- $\alpha_i$ is asset $i$'s idiosyncratic alpha (unexplained return).
- $\epsilon_{i,t}$ is the idiosyncratic error term with $\mathbb{E}[\epsilon_i] = 0, \operatorname{Var}(\epsilon_i) = \sigma_{\epsilon,i}^2$, and $\operatorname{Cov}(\epsilon_i, \epsilon_j) = 0$ for $i \neq j$.

In matrix form for asset $i$:
$$R_i^e = X \theta_i + \epsilon_i$$
where $X = [\mathbf{1}_T, F_1, \dots, F_K] \in \mathbb{R}^{T \times (K+1)}$ and $\theta_i = [\alpha_i, \beta_{i,1}, \dots, \beta_{i,K}]^\top$.
The OLS estimator is:
$$\hat{\theta}_i = (X^\top X)^{-1} X^\top R_i^e$$
With residual variance estimator:
$$s_{\epsilon,i}^2 = \frac{1}{T - K - 1} \sum_{t=1}^T \hat{\epsilon}_{i,t}^2$$
Standard errors of factor loadings:
$$\operatorname{SE}(\hat{\beta}_{i,k}) = \sqrt{s_{\epsilon,i}^2 \cdot [(X^\top X)^{-1}]_{k+1, k+1}}$$
$t$-statistic and $p$-value:
$$t_{i,k} = \frac{\hat{\beta}_{i,k}}{\operatorname{SE}(\hat{\beta}_{i,k})}, \quad p_{i,k} = 2 \cdot (1 - F_{t, T-K-1}(|t_{i,k}|))$$
Coefficient of determination ($R^2$):
$$R_i^2 = 1 - \frac{\sum_{t=1}^T \hat{\epsilon}_{i,t}^2}{\sum_{t=1}^T (R_{i,t}^e - \bar{R}_i^e)^2}$$

### 1.2 Barra-Style Covariance Decomposition
The structural multi-factor covariance matrix $\Sigma_{\text{model}} \in \mathbb{R}^{N \times N}$ is:
$$\Sigma_{\text{model}} = B \Sigma_F B^\top + \Sigma_\epsilon$$
where:
- $B \in \mathbb{R}^{N \times K}$ is the factor loading matrix with elements $B_{i,k} = \hat{\beta}_{i,k}$.
- $\Sigma_F \in \mathbb{R}^{K \times K}$ is the sample factor covariance matrix: $\Sigma_F = \frac{1}{T-1} (F - \bar{F})^\top (F - \bar{F})$.
- $\Sigma_\epsilon = \operatorname{diag}(s_{\epsilon,1}^2, \dots, s_{\epsilon,N}^2) \in \mathbb{R}^{N \times N}$ is the diagonal specific variance matrix.

### 1.3 Portfolio Risk Decomposition
For a portfolio with capital allocation weights $w \in \mathbb{R}^N$ ($\mathbf{1}^\top w = 1.0$):
- **Portfolio Factor Exposures:**
  $$\beta_p = B^\top w \in \mathbb{R}^K, \quad \beta_{p,k} = \sum_{i=1}^N w_i \hat{\beta}_{i,k}$$
- **Total Portfolio Variance:**
  $$\sigma_p^2 = w^\top \Sigma_{\text{model}} w = \underbrace{\beta_p^\top \Sigma_F \beta_p}_{\sigma_{\text{sys}}^2 \text{ (Systematic Variance)}} + \underbrace{w^\top \Sigma_\epsilon w}_{\sigma_{\text{idio}}^2 \text{ (Idiosyncratic Variance)}}$$
- **Systematic & Idiosyncratic Risk Shares:**
  $$\%_{\text{sys}} = \frac{\sigma_{\text{sys}}^2}{\sigma_p^2}, \quad \%_{\text{idio}} = \frac{\sigma_{\text{idio}}^2}{\sigma_p^2}, \quad \%_{\text{sys}} + \%_{\text{idio}} \equiv 1.0$$
- **Factor Variance Attribution (Marginal and Total):**
  $$\sigma_{\text{sys}}^2 = \sum_{k=1}^K \beta_{p,k} (\Sigma_F \beta_p)_k$$
  - Factor $k$'s Marginal Contribution: $\text{MFC}_k = (\Sigma_F \beta_p)_k$.
  - Factor $k$'s Total Variance Contribution: $\text{TFC}_k = \beta_{p,k} \cdot (\Sigma_F \beta_p)_k$.
  - Percentage Contribution to Factor Risk: $\%FC_k = \frac{\text{TFC}_k}{\sigma_{\text{sys}}^2}$, satisfying $\sum_{k=1}^K \%FC_k \equiv 1.0$.

### 1.4 Factor-Constrained Portfolio Optimization
$$\min_w \frac{1}{2} w^\top \Sigma_{\text{model}} w - \lambda w^\top \mu \quad \text{or} \quad \max_w \frac{w^\top \mu - R_f}{\sqrt{w^\top \Sigma_{\text{model}} w}}$$
Subject to:
1. Full investment: $\sum_{i=1}^N w_i = 1.0$.
2. Asset position bounds: $w_{\min} \le w_i \le w_{\max}$.
3. Linear Factor Tilt Constraints:
   $$\beta_{k,\min} \le \sum_{i=1}^N w_i \hat{\beta}_{i,k} \le \beta_{k,\max} \quad \forall k \in \mathcal{K}_{\text{constrained}}$$
Examples:
- **Market Neutral:** $-0.05 \le \beta_{p,\text{MKT}} \le 0.05$.
- **Target Value Tilt:** $\beta_{p,\text{HML}} \ge 0.30$.
- **Momentum Constrained:** $\beta_{p,\text{MOM}} \ge 0.0$.

### 1.5 Factor Models Supported
1. **Capital Asset Pricing Model (CAPM):** 1 factor ($MKT$).
2. **Fama-French 3-Factor Model (FF3):** 3 factors ($MKT, SMB, HML$).
3. **Carhart 4-Factor Model (C4):** 4 factors ($MKT, SMB, HML, MOM$).
4. **Statistical PCA Factor Model:** $K$ principal components extracted from the empirical correlation matrix, capturing user-selected variance threshold (e.g. 70%, 80%, 90%).

---

## 2. API Data Contracts

### 2.1 Request Schema: `FactorAttributionRequest`
```json
{
  "dataset_id": "string (UUID)",
  "factor_model": "capm | ff3 | carhart4 | pca",
  "num_pca_factors": 3,
  "weights": { "AAPL:US": 0.5, "MSFT:US": 0.5 },
  "risk_free_rate": 0.02,
  "start_date": "2023-01-01",
  "end_date": "2023-12-31"
}
```

### 2.2 Response Schema: `FactorAttributionResponse`
```json
{
  "dataset_id": "string",
  "factor_model": "carhart4",
  "factors": ["MKT", "SMB", "HML", "MOM"],
  "asset_loadings": {
    "AAPL:US": {
      "alpha": 0.035,
      "alpha_tstat": 1.85,
      "alpha_pvalue": 0.065,
      "r_squared": 0.72,
      "specific_variance": 0.015,
      "betas": {
        "MKT": { "beta": 1.15, "tstat": 12.4, "pvalue": 0.0001, "stderr": 0.093 },
        "SMB": { "beta": -0.25, "tstat": -2.1, "pvalue": 0.038, "stderr": 0.119 },
        "HML": { "beta": -0.35, "tstat": -3.2, "pvalue": 0.0016, "stderr": 0.109 },
        "MOM": { "beta": 0.20, "tstat": 2.5, "pvalue": 0.013, "stderr": 0.080 }
      }
    }
  },
  "portfolio_exposures": {
    "MKT": 1.12,
    "SMB": -0.15,
    "HML": -0.28,
    "MOM": 0.18
  },
  "portfolio_variance_decomposition": {
    "total_volatility": 0.185,
    "systematic_volatility": 0.162,
    "idiosyncratic_volatility": 0.089,
    "systematic_share_pct": 76.8,
    "idiosyncratic_share_pct": 23.2,
    "factor_contributions": {
      "MKT": { "total_contrib": 0.021, "pct_share": 80.2 },
      "SMB": { "total_contrib": 0.001, "pct_share": 3.8 },
      "HML": { "total_contrib": 0.002, "pct_share": 7.6 },
      "MOM": { "total_contrib": 0.0022, "pct_share": 8.4 }
    }
  },
  "factor_covariance_matrix": [[0.04, 0.0], [0.0, 0.02]]
}
```

### 2.3 Request Schema: `FactorConstrainedOptimizationRequest`
```json
{
  "dataset_id": "string",
  "factor_model": "capm | ff3 | carhart4 | pca",
  "objective": "min_variance | max_sharpe | max_utility",
  "risk_aversion": 2.5,
  "risk_free_rate": 0.02,
  "min_weight": 0.0,
  "max_weight": 0.6,
  "factor_constraints": {
    "MKT": { "min_beta": -0.1, "max_beta": 0.1 },
    "HML": { "min_beta": 0.2, "max_beta": null }
  }
}
```

---

## 3. Analytical Reference Benchmarks & Tolerances

### 3.1 2-Asset 1-Factor Analytical Benchmark
Let asset excess returns be:
$$R_1^e = \beta_1 F + \epsilon_1, \quad R_2^e = \beta_2 F + \epsilon_2$$
with factor variance $\sigma_F^2 = 0.04$ ($20\%$ vol), factor loadings $\beta_1 = 1.20, \beta_2 = 0.80$, specific variances $\sigma_{\epsilon,1}^2 = 0.01, \sigma_{\epsilon,2}^2 = 0.02$.
Equal weight portfolio $w = [0.50, 0.50]$:
1. **Portfolio Beta:**
   $$\beta_p = 0.50 \times 1.20 + 0.50 \times 0.80 = 1.00$$
2. **Systematic Variance:**
   $$\sigma_{\text{sys}}^2 = \beta_p^2 \sigma_F^2 = 1.00^2 \times 0.04 = 0.0400$$
3. **Idiosyncratic Variance:**
   $$\sigma_{\text{idio}}^2 = 0.50^2 \times 0.01 + 0.50^2 \times 0.02 = 0.0025 + 0.0050 = 0.0075$$
4. **Total Variance:**
   $$\sigma_p^2 = 0.0400 + 0.0075 = 0.0475 \implies \sigma_p \approx 0.217945$$
5. **Systematic vs. Idiosyncratic Shares:**
   $$\%_{\text{sys}} = \frac{0.0400}{0.0475} \approx 84.2105\%, \quad \%_{\text{idio}} = \frac{0.0075}{0.0475} \approx 15.7895\%$$

### 3.2 Tolerances
- OLS regression coefficients: within $10^{-8}$ of analytical formula $(X^\top X)^{-1} X^\top y$.
- Systematic + Idiosyncratic variance sum: $|(\sigma_{\text{sys}}^2 + \sigma_{\text{idio}}^2) - \sigma_p^2| \le 10^{-12}$.
- Factor exposure equality: $|\sum w_i \beta_{i,k} - \beta_{p,k}| \le 10^{-12}$.
- Optimization factor constraint satisfaction: $\beta_{k,\min} - 10^{-5} \le \beta_{p,k} \le \beta_{k,\max} + 10^{-5}$.
