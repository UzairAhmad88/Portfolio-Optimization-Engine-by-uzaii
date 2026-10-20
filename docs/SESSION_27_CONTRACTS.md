# SESSION 27 CONTRACTS — STAGE 22 IMPLEMENTED SPECIFICATIONS

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 27  
**Governance Stage:** Stage 22 — Copula-Based Tail Dependency, Non-Linear Extreme Co-Movement & Tail Risk Parity Allocation  
**Implementation Status:** Completed & Mathematically Verified  

---

## 1. Quantitative & Mathematical Contracts

### 1.1 Sklar's Theorem & Probability Integral Transforms
For multivariate asset returns $\mathbf{R} = (R_1, \dots, R_N)^\top$ with marginal CDFs $F_i(r_i) = \mathbb{P}(R_i \le r_i)$:
$$F(r_1, \dots, r_N) = C(F_1(r_1), \dots, F_N(r_N)) = C(u_1, \dots, u_N)$$
where $u_i = F_i(r_i) \in (0, 1)$ are uniform pseudo-observations.

#### Marginal Transformations
1. **Empirical Rank Transform (CML / Pseudo-Observations):**
   $$\hat{u}_{i,t} = \frac{\operatorname{rank}(R_{i,t})}{T + 1}$$
   guaranteeing $\hat{u}_{i,t} \in \left[\frac{1}{T+1}, \frac{T}{T+1}\right] \subset (0, 1)$, strictly avoiding boundary singularities at $0$ and $1$.
2. **Parametric Student-t Marginal Transform:**
   $$\hat{u}_{i,t} = t_{\hat{\nu}_i}\left(\frac{R_{i,t} - \hat{\mu}_i}{\hat{\sigma}_i}\right)$$
   where location $\hat{\mu}_i$, scale $\hat{\sigma}_i$, and degrees of freedom $\hat{\nu}_i > 2$ are fitted via univariate maximum likelihood on training data only (preventing look-ahead leakage).

---

### 1.2 Bivariate Copula Estimators & Tail Dependence Coefficients

#### 1. Clayton Copula (Asymmetric Crash Risk / Downside Co-Movement)
- **CDF:**
  $$C_\theta(u, v) = \left( u^{-\theta} + v^{-\theta} - 1 \right)^{-1/\theta}, \quad \theta > 0$$
- **Density:**
  $$c_\theta(u, v) = (1 + \theta)(u v)^{-(1 + \theta)} \left( u^{-\theta} + v^{-\theta} - 1 \right)^{-(2 + 1/\theta)}$$
- **Log-Likelihood:**
  $$\ln \mathcal{L}(\theta) = \sum_{t=1}^T \left[ \ln(1 + \theta) - (1 + \theta)(\ln u_t + \ln v_t) - \left(2 + \frac{1}{\theta}\right) \ln\left(u_t^{-\theta} + v_t^{-\theta} - 1\right) \right]$$
- **Theoretical Tail Dependence:**
  $$\lambda_L = 2^{-1/\theta} \in (0, 1], \qquad \lambda_U = 0$$
- **Kendall's $\tau$ Inversion Starting Point:**
  $$\tau = \frac{\theta}{\theta + 2} \implies \theta_0 = \max\left(10^{-4}, \frac{2\tau}{1 - \tau}\right)$$

#### 2. Gumbel Copula (Asymmetric Boom Risk / Upper Tail Co-Movement)
- **CDF:**
  $$C_\theta(u, v) = \exp\left( - \left[ (-\ln u)^\theta + (-\ln v)^\theta \right]^{1/\theta} \right), \quad \theta \ge 1$$
- **Density:**
  $$c_\theta(u, v) = \frac{C_\theta(u, v)}{u v} \frac{(\tilde{u} \tilde{v})^{\theta - 1}}{A^{2 - 1/\theta}} \left( A^{1/\theta} + \theta - 1 \right)$$
  where $\tilde{u} = -\ln u$, $\tilde{v} = -\ln v$, and $A = \tilde{u}^\theta + \tilde{v}^\theta$.
- **Theoretical Tail Dependence:**
  $$\lambda_L = 0, \qquad \lambda_U = 2 - 2^{1/\theta} \in [0, 1)$$
- **Kendall's $\tau$ Inversion Starting Point:**
  $$\tau = 1 - \frac{1}{\theta} \implies \theta_0 = \max\left(1.0001, \frac{1}{1 - \tau}\right)$$

#### 3. Student-t Copula (Symmetric Heavy Tails)
- **Parameters:** Correlation $\rho \in (-1, 1)$, degrees of freedom $\nu \in (2, 50]$.
- **Density:**
  $$c_{\rho, \nu}(u, v) = \frac{f_{\rho, \nu}(t_\nu^{-1}(u), t_\nu^{-1}(v))}{f_\nu(t_\nu^{-1}(u)) f_\nu(t_\nu^{-1}(v))}$$
- **Theoretical Tail Dependence:**
  $$\lambda_L = \lambda_U = 2 t_{\nu+1}\left( - \sqrt{\frac{(\nu + 1)(1 - \rho)}{1 + \rho}} \right)$$

#### 4. Gaussian Copula Baseline
- **Parameters:** Correlation matrix $P$ projected to nearest positive semi-definite matrix.
- **Theoretical Tail Dependence:**
  $$\lambda_L = \lambda_U = 0 \quad (\text{for } |\rho| < 1)$$

#### 5. Model Selection Criterion
$$\text{AIC} = 2k - 2\ln \mathcal{L}, \qquad \text{BIC} = k\ln T - 2\ln \mathcal{L}$$
Best-fit copula selects family minimizing AIC across Clayton, Gumbel, Student-t, and Gaussian.

---

### 1.3 Multivariate Dependent Return Simulation
1. **Clayton Copula Simulation (Marshall-Olkin Laplace Transform):**
   - Sample $V \sim \text{Gamma}(1/\theta, 1)$.
   - Draw independent uniform random variables $E_i \sim \text{Uniform}(0, 1)$ for $i=1, \dots, N$.
   - Compute:
     $$U_i = \left( 1 - \frac{\ln E_i}{V} \right)^{-1/\theta}$$
2. **Student-t Copula Simulation:**
   - Draw $\mathbf{Z} \sim \mathcal{N}(\mathbf{0}, \mathbf{P})$ via Cholesky factor $\mathbf{L}\mathbf{L}^\top = \mathbf{P}$.
   - Draw independent $S \sim \chi^2_\nu$.
   - Scale: $\mathbf{X} = \mathbf{Z} \sqrt{\frac{\nu}{S}}$, and set $U_i = t_\nu(X_i)$.
3. **Marginal Inversion:**
   - Empirical: $R_i^{(m)} = \text{EmpiricalQuantile}(U_i^{(m)})$.
   - Parametric: $R_i^{(m)} = \hat{\mu}_i + \hat{\sigma}_i t_{\hat{\nu}_i}^{-1}(U_i^{(m)})$.

---

### 1.4 Copula-CVaR & Euler Tail Risk Decomposition
- **Portfolio Loss:** $L = -R_p = -\sum_{i=1}^N w_i R_i$.
- **Value-at-Risk ($\text{VaR}_\alpha$):**
  $$\text{VaR}_\alpha(L) = \inf\{\ell : \mathbb{P}(L \le \ell) \ge \alpha\} = -\text{quantile}_{1-\alpha}(R_p)$$
- **Conditional Value-at-Risk ($\text{CVaR}_\alpha$):**
  $$\text{CVaR}_\alpha(L) = \mathbb{E}[L \mid L \ge \text{VaR}_\alpha(L)] = -\mathbb{E}[R_p \mid R_p \le -\text{VaR}_\alpha(L)]$$
- **Euler Tail Risk Contribution ($TRC_i$):**
  By Euler's homogeneous function theorem, for degree-1 positive homogeneous risk measure $\rho(w) = \text{CVaR}_\alpha(w)$:
  $$TRC_i = w_i \frac{\partial \text{CVaR}_\alpha(w)}{\partial w_i} = -w_i \mathbb{E}[R_i \mid R_p \le -\text{VaR}_\alpha(L)]$$
- **Reconciliation Invariant:**
  $$\sum_{i=1}^N TRC_i \equiv \text{CVaR}_\alpha(w)$$
  Numerical residual $\|\sum TRC_i - \text{CVaR}_\alpha\|_\infty < 10^{-12}$.

---

### 1.5 Tail Risk Parity (TRP) Allocation
- **Objective Formulation:**
  $$\min_{\mathbf{w}} \sum_{i=1}^N \sum_{j=1}^N \left( TRC_i(\mathbf{w}) - TRC_j(\mathbf{w}) \right)^2$$
- **Constraints:**
  $$\sum_{i=1}^N w_i = 1, \qquad 0 \le w_i \le 1 \quad \forall i=1,\dots,N$$
- **Solver:** SciPy SLSQP with multi-start deterministic initializations (equal-weight $w_0 = 1/N$, inverse marginal volatility $w_{\text{iv}}$, minimum variance $w_{\text{minv}}$).

---

## 2. API Contract Specifications

### 2.1 Request Schemas
- `POST /api/v1/copula/fit`
  ```json
  {
    "dataset_id": "string",
    "copula_type": "clayton | gumbel | student_t | gaussian | best_fit",
    "marginal_method": "empirical | student_t",
    "tickers": ["AAPL", "MSFT"]
  }
  ```
- `POST /api/v1/copula/simulate`
  ```json
  {
    "dataset_id": "string",
    "copula_type": "clayton | gumbel | student_t | gaussian",
    "marginal_method": "empirical | student_t",
    "num_simulations": 5000,
    "seed": 42,
    "tickers": ["AAPL", "MSFT"]
  }
  ```
- `POST /api/v1/copula/tail-risk-parity` (and alias `POST /api/v1/copula/optimize`)
  ```json
  {
    "dataset_id": "string",
    "copula_type": "clayton | gumbel | student_t | gaussian",
    "marginal_method": "empirical | student_t",
    "confidence_level": 0.95,
    "num_simulations": 5000,
    "seed": 42,
    "tickers": ["AAPL", "MSFT"]
  }
  ```

### 2.2 Response Schemas
- `CopulaFitResponse`: Contains `dataset_id`, `copula_type`, `marginal_method`, `tickers`, `tail_dependence_matrix`, `kendall_tau_matrix`, `pairwise_results`.
- `CopulaSimulateResponse`: Contains `dataset_id`, `copula_type`, `num_simulations`, `seed`, `tickers`, `simulated_returns`.
- `TailRiskParityResponse`: Contains `dataset_id`, `copula_type`, `confidence_level`, `weights`, `tail_risk_contributions`, `portfolio_cvar`, `portfolio_var`, `simulated_loss_distribution`, `equal_weight_cvar`, `cvar_reduction_pct`, `euler_residual`.

---

## 3. Independent Analytical Benchmarks

| Copula Model | Input Parameters | Analytical Closed-Form | Implementation Formula | Test Verification Tolerance |
|---|---|---|---|---|
| **Clayton** | $\theta = 2.0$ ($\tau = 0.50$) | $\lambda_L = 2^{-1/2} = \frac{1}{\sqrt{2}} \approx 0.70710678$ | $\lambda_L = 2^{-1/\theta}$ | $|\lambda_L - 0.70710678| < 10^{-7}$ |
| **Gumbel** | $\theta = 2.0$ ($\tau = 0.50$) | $\lambda_U = 2 - 2^{1/2} \approx 0.58578644$ | $\lambda_U = 2 - 2^{1/\theta}$ | $|\lambda_U - 0.58578644| < 10^{-7}$ |
| **Student-t** | $\rho = 0.50, \nu = 4.0$ | $\lambda = 2 t_5\left(-\sqrt{\frac{5(0.5)}{1.5}}\right) = 2 t_5(-\sqrt{5/3}) \approx 0.25816881$ | $\lambda = 2 t_{\nu+1}\left(-\sqrt{\frac{(\nu+1)(1-\rho)}{1+\rho}}\right)$ | $|\lambda - 0.25816881| < 10^{-7}$ |
| **Gaussian** | $\rho = 0.75$ | $\lambda_L = \lambda_U = 0.0$ | $\lambda_L = \lambda_U = 0.0$ | Identically 0.0 |
