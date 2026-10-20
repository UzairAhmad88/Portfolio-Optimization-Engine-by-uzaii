# SESSION 19 CONTRACTS — Equal Risk Contribution (ERC) & Hierarchical Risk Parity (HRP)

**Governing Standard:** Institutional Quantitative Portfolio Engineering  
**Session:** Session 19 (Stage 15)  
**Status:** Approved & Formally Specified  

---

## 1. Mathematical Formulations

### 1.1 Euler's Decomposition of Portfolio Risk
Let $w \in \mathbb{R}^N$ be a long-only portfolio weight vector satisfying $\sum_{i=1}^N w_i = 1$ and $w_i \ge 0$.  
Let $\Sigma \in \mathbb{R}^{N \times N}$ be the positive definite asset return covariance matrix.  
Portfolio volatility is defined as:
$$\sigma_p(w) = \sqrt{w^\top \Sigma w}$$

Because $\sigma_p(w)$ is a positively homogeneous function of degree 1 (i.e. $\sigma_p(c w) = c \sigma_p(w)$ for all $c > 0$), Euler's homogeneous function theorem applies:
$$\sigma_p(w) = \sum_{i=1}^N w_i \frac{\partial \sigma_p}{\partial w_i}(w)$$

1. **Marginal Risk Contribution (MRC):**
   $$\text{MRC}_i = \frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sqrt{w^\top \Sigma w}} = \frac{(\Sigma w)_i}{\sigma_p}$$
2. **Total Risk Contribution (TRC):**
   $$\text{TRC}_i = w_i \text{MRC}_i = \frac{w_i (\Sigma w)_i}{\sigma_p}$$
   satisfying the exact additive reconciliation property:
   $$\sum_{i=1}^N \text{TRC}_i = \sigma_p(w)$$
3. **Percentage Risk Contribution (%RC):**
   $$\%RC_i = \frac{\text{TRC}_i}{\sigma_p} = \frac{w_i (\Sigma w)_i}{w^\top \Sigma w}$$
   satisfying the unit-sum invariant:
   $$\sum_{i=1}^N \%RC_i = 1.0$$

---

### 1.2 Equal Risk Contribution (ERC) & Risk Budgeting

#### Equal Risk Contribution (ERC) Condition:
Under an Equal Risk Contribution portfolio, every asset contributes an identical amount of volatility to the portfolio:
$$\text{TRC}_i = \text{TRC}_j = \frac{\sigma_p(w)}{N} \quad \forall i, j \in \{1, \dots, N\} \iff \%RC_i = \frac{1}{N} \quad \forall i$$

#### Generalized Risk Budgeting:
Given an exogenous risk budget vector $b \in \mathbb{R}^N$ with $b_i > 0$ and $\sum_{i=1}^N b_i = 1$:
$$\%RC_i = b_i \quad \forall i \in \{1, \dots, N\}$$

#### Convex Log-Barrier Formulation (Maillard, Roncalli & Teïletche 2010; Spingarn 1988):
The general risk budgeting portfolio can be formulated as a strictly convex unconstrained optimization problem:
$$x^* = \arg\min_{x \in \mathbb{R}^N} \left[ \frac{1}{2} x^\top \Sigma x - \sum_{i=1}^N b_i \ln(x_i) \right] \quad \text{s.t.} \quad x_i > 0$$
The gradient is:
$$\nabla_x f(x) = \Sigma x - \left( \frac{b_1}{x_1}, \dots, \frac{b_N}{x_N} \right)^\top$$
The Hessian is:
$$\nabla^2_x f(x) = \Sigma + \operatorname{diag}\left( \frac{b_1}{x_1^2}, \dots, \frac{b_N}{x_N^2} \right)$$
Because $\Sigma$ is positive definite and the diagonal term is strictly positive, the Hessian is strictly positive definite everywhere on $\mathbb{R}_{++}^N$. Therefore, a unique global minimum $x^*$ exists!
The optimal normalized weights are given by:
$$w_i^* = \frac{x_i^*}{\sum_{j=1}^N x_j^*}$$

#### Cyclical Coordinate Descent (Griveau-Billion et al., 2013) & SLSQP Formulation:
Under linear bounds ($w_i \in [w_{\min}, w_{\max}]$) or additional constraints, the problem can also be solved by minimizing the dispersion of risk contributions:
$$\min_w \sum_{i=1}^N \sum_{j=1}^N \left( \frac{w_i (\Sigma w)_i}{b_i} - \frac{w_j (\Sigma w)_j}{b_j} \right)^2 \quad \text{s.t.} \quad \sum_{i=1}^N w_i = 1, \quad w_{\min} \le w_i \le w_{\max}$$

---

### 1.3 Hierarchical Risk Parity (HRP — Marcos López de Prado, 2016)

Hierarchical Risk Parity eliminates the quadratic programming inversion of the covariance matrix $\Sigma^{-1}$, making it completely robust to ill-conditioned and singular covariance matrices.

#### Step 1: Correlation Distance & Tree Clustering
Given correlation matrix $\mathbf{P} \in \mathbb{R}^{N \times N}$, define the metric distance matrix $D \in \mathbb{R}^{N \times N}$:
$$d_{i,j} = \sqrt{\frac{1}{2}(1 - \rho_{i,j})} \in [0, 1]$$
Euclidean distance between distance vectors:
$$\tilde{d}_{i,j} = \|d_i - d_j\|_2 = \sqrt{\sum_{k=1}^N (d_{i,k} - d_{j,k})^2}$$
Apply hierarchical clustering using `scipy.cluster.hierarchy.linkage` with single, complete, or average linkage to produce a cluster linkage tree $Z$.

#### Step 2: Quasi-Diagonalization (Matrix Seriation)
Reorder the asset indices based on the dendrogram leaves so that highly correlated assets are contiguous along the diagonal:
$$O = \operatorname{dendrogram\_order}(Z)$$
Reorder covariance matrix: $\tilde{\Sigma} = \Sigma[O, O]$.

#### Step 3: Recursive Bisection
Initialize weights $w_i = 1.0$ for all $i \in \{1, \dots, N\}$.
For any cluster $C = [i_1, \dots, i_M]$ with $M > 1$, bisect into two sub-clusters $C_1 = [i_1, \dots, i_{\lfloor M/2 \rfloor}]$ and $C_2 = [i_{\lfloor M/2 \rfloor + 1}, \dots, i_M]$.
Compute the inverse-variance variance of each sub-cluster:
$$\tilde{w}_{C_k} = \frac{\operatorname{diag}(\Sigma_{C_k})^{-1}}{\operatorname{Tr}(\operatorname{diag}(\Sigma_{C_k})^{-1})}, \quad k \in \{1, 2\}$$
$$V_{C_k} = \tilde{w}_{C_k}^\top \Sigma_{C_k} \tilde{w}_{C_k}$$
Compute the allocation split factor:
$$\alpha = 1 - \frac{V_{C_1}}{V_{C_1} + V_{C_2}} = \frac{V_{C_2}}{V_{C_1} + V_{C_2}} \in [0, 1]$$
Update weights:
$$w_i \leftarrow w_i \times \alpha \quad \forall i \in C_1$$
$$w_j \leftarrow w_j \times (1 - \alpha) \quad \forall j \in C_2$$
Recursively apply bisection until all sub-clusters are singletons.
Finally, normalize weights: $w_i^* = \frac{w_i}{\sum_{j=1}^N w_j}$.

---

### 1.4 Risk Concentration & Diversification Metrics

1. **Risk Gini Coefficient ($G_{\text{risk}}$):**
   Measures the inequality of percentage risk contributions:
   $$G_{\text{risk}} = \frac{\sum_{i=1}^N \sum_{j=1}^N |\%RC_i - \%RC_j|}{2 N \sum_{i=1}^N \%RC_i} = \frac{\sum_{i=1}^N \sum_{j=1}^N |\%RC_i - \%RC_j|}{2 N} \in [0, 1]$$
   - $G_{\text{risk}} = 0$: Perfect Risk Parity ($\%RC_i = 1/N$ for all $i$).
   - $G_{\text{risk}} \to 1$: Maximum risk concentration (one asset contributes 100% of risk).

2. **Effective Number of Bets ($N_{\text{bets}}$ — Meucci 2009):**
   $$N_{\text{bets}} = \exp\left( - \sum_{i=1}^N \%RC_i \ln(\%RC_i) \right) \in [1, N]$$
   or inverse Herfindahl of risk contributions:
   $$N_{\text{eff, risk}} = \frac{1}{\sum_{i=1}^N (\%RC_i)^2} \in [1, N]$$

3. **Diversification Ratio ($DR$ — Choueifaty & Coignard 2008):**
   $$DR = \frac{\sum_{i=1}^N w_i \sigma_i}{\sqrt{w^\top \Sigma w}} \ge 1.0$$
   A portfolio is diversified if and only if $DR > 1.0$.

---

### 1.5 Prerequisite Black-Litterman Refinement
In accordance with Section 2 of Session 19 prompt:
1. `compute_unconstrained_bl_weights(posterior_mean, covariance, risk_aversion, risk_free_rate)`:
   $$w_{\text{unconstrained}} = \frac{1}{\gamma} \Sigma^{-1} (\mu_{\text{BL}} - r_f \mathbf{1})$$
   normalized to sum to 1.0. This guarantees that when views are zero ($K=0$), $\mu_{\text{BL}} = \Pi = r_f \mathbf{1} + \gamma \Sigma w_{\text{eq}}$, and $w_{\text{unconstrained}} \equiv w_{\text{eq}}$ for any $r_f \ge 0$.
2. In `optimize_black_litterman_portfolio`, allow passing `covariance_type="posterior"` or `"sample"`, and evaluate `mean_variance_utility` as:
   $$\max_w w^\top (\mu_{\text{BL}} - r_f \mathbf{1}) - \frac{1}{2}\gamma w^\top \Sigma w$$
   recovering $w_{\text{eq}}$ when $K = 0$.

---

## 2. Analytical Benchmark Example

### 2-Asset Uncorrelated System
- Asset 1: Variance $\sigma_1^2 = 0.04 \implies \sigma_1 = 0.20$ (20% annualized volatility).
- Asset 2: Variance $\sigma_2^2 = 0.09 \implies \sigma_2 = 0.30$ (30% annualized volatility).
- Covariance: $\sigma_{12} = 0.0$.
$$\Sigma = \begin{bmatrix} 0.04 & 0.00 \\ 0.00 & 0.09 \end{bmatrix}$$

#### Equal Risk Contribution Derivation:
$$\text{TRC}_1 = \text{TRC}_2 \iff w_1 (\Sigma w)_1 = w_2 (\Sigma w)_2$$
$$w_1 (\sigma_1^2 w_1) = w_2 (\sigma_2^2 w_2) \iff w_1^2 \sigma_1^2 = w_2^2 \sigma_2^2 \iff w_1 \sigma_1 = w_2 \sigma_2$$
$$w_1 \cdot 0.20 = w_2 \cdot 0.30 \implies w_1 = 1.5 w_2$$
With $w_1 + w_2 = 1.0$:
$$1.5 w_2 + w_2 = 1.0 \implies 2.5 w_2 = 1.0 \implies w_2^* = \frac{1}{2.5} = 0.40, \quad w_1^* = 0.60$$

- Portfolio Variance:
  $$\sigma_p^2 = (0.60)^2(0.04) + (0.40)^2(0.09) = 0.0144 + 0.0144 = 0.0288$$
- Portfolio Volatility:
  $$\sigma_p = \sqrt{0.0288} \approx 0.169706$$
- Risk Contributions:
  $$\text{TRC}_1 = \frac{w_1 (\Sigma w)_1}{\sigma_p} = \frac{0.60 \cdot 0.0240}{\sigma_p} = \frac{0.0144}{\sigma_p}$$
  $$\text{TRC}_2 = \frac{w_2 (\Sigma w)_2}{\sigma_p} = \frac{0.40 \cdot 0.0360}{\sigma_p} = \frac{0.0144}{\sigma_p}$$
- Percentage Risk Contributions:
  $$\%RC_1 = \frac{0.0144}{0.0288} = 50.0\%, \quad \%RC_2 = \frac{0.0144}{0.0288} = 50.0\%$$
- Risk Gini Coefficient:
  $$G_{\text{risk}} = 0.000000$$

This independent analytical solution ($w^* = [0.60, 0.40]$) will serve as the exact validation benchmark in unit tests.

---

## 3. Input & Output Schemas

### 3.1 `RiskParityOptimizeRequest`
```json
{
  "dataset_id": "string",
  "method": "erc", // 'erc', 'hrp', 'equal_weight', 'inverse_variance'
  "linkage_method": "single", // for hrp: 'single', 'complete', 'average'
  "custom_risk_budgets": { "AAPL:US": 0.5, "MSFT:US": 0.5 }, // optional
  "min_weight": 0.0,
  "max_weight": 1.0
}
```

### 3.2 `RiskParityOptimizeResponse`
```json
{
  "method": "erc",
  "weights": { "AAPL:US": 0.60, "MSFT:US": 0.40 },
  "marginal_risk_contributions": { "AAPL:US": 0.1414, "MSFT:US": 0.2121 },
  "total_risk_contributions": { "AAPL:US": 0.0848, "MSFT:US": 0.0848 },
  "percentage_risk_contributions": { "AAPL:US": 0.50, "MSFT:US": 0.50 },
  "portfolio_volatility": 0.1697,
  "risk_gini_coefficient": 0.0,
  "effective_number_of_bets": 2.0,
  "diversification_ratio": 1.4142,
  "is_feasible": true,
  "solver_status": "optimal"
}
```

### 3.3 `RiskParityBacktestRequest`
```json
{
  "dataset_id": "string",
  "split_date": "2023-01-01",
  "rebalance_frequency": "monthly",
  "transaction_cost_bps": 10.0,
  "slippage_bps": 5.0
}
```

---

## 4. Chronological & Data Invariants
- In-sample window ($t \le T_{\text{split}}$) is used strictly for covariance estimation $\Sigma$ and HRP dendrogram clustering.
- Out-of-sample window ($t > T_{\text{split}}$) evaluates chronological daily returns, weight drift, rebalancing friction, and transaction cost drag.
- Zero look-ahead bias: cluster linkages and covariance are fitted only on observations prior to each rebalance point.
