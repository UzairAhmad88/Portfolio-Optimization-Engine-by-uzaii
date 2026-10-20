# SESSION 26 CONTRACTS — STAGE 22 APPROVED SCOPE SPECIFICATION

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 26  
**Governance Stage:** Stage 22 — Roadmap Audit, Mathematical Verification & Scope Approval  
**Status:** Approved by User for Implementation in Subsequent Session  
**Approved Scope:** Option 1 — Copula-Based Tail Dependency, Non-Linear Extreme Co-Movement & Tail Risk Parity Allocation  

---

## 1. Quantitative & Mathematical Formulations

### 1.1 Sklar's Theorem & Marginal Transformation
For asset return vectors $X = (X_1, \dots, X_N)^\top$ with marginal cumulative distribution functions $F_i(x_i) = P(X_i \le x_i)$:
$$F(x_1, \dots, x_N) = C(F_1(x_1), \dots, F_N(x_N)) = C(u_1, \dots, u_N)$$
where $u_i = F_i(x_i) \in [0, 1]$ are uniform pseudo-observations.

Marginal transformation methods:
1. **Empirical Copula (Non-parametric rank transformation):**
   $$\hat{u}_{i,t} = \frac{\operatorname{rank}(X_{i,t})}{T + 1}$$
2. **Parametric Student-t Marginal:**
   $$\hat{u}_{i,t} = t_{\nu_i}\left(\frac{X_{i,t} - \hat{\mu}_i}{\hat{\sigma}_i}\right)$$

---

### 1.2 Copula Families & Tail Dependence Coefficients

#### 1. Bivariate Clayton Copula (Asymmetric Lower Tail Crash Risk)
- **Cumulative Distribution Function:**
  $$C_\theta(u_1, u_2) = \left( u_1^{-\theta} + u_2^{-\theta} - 1 \right)^{-1/\theta}, \quad \theta > 0$$
- **Probability Density Function:**
  $$c_\theta(u_1, u_2) = (1 + \theta)(u_1 u_2)^{-(1 + \theta)} \left( u_1^{-\theta} + u_2^{-\theta} - 1 \right)^{-(2 + 1/\theta)}$$
- **Log-Likelihood:**
  $$\ln \mathcal{L}(\theta) = \sum_{t=1}^T \left[ \ln(1 + \theta) - (1 + \theta)(\ln u_{1,t} + \ln u_{2,t}) - \left(2 + \frac{1}{\theta}\right) \ln\left(u_{1,t}^{-\theta} + u_{2,t}^{-\theta} - 1\right) \right]$$
- **Tail Dependence Coefficients:**
  - Lower Tail Dependence: $\lambda_L = 2^{-1/\theta} \in (0, 1]$
  - Upper Tail Dependence: $\lambda_U = 0$
- **Kendall's Tau ($\tau$):**
  $$\tau = \frac{\theta}{\theta + 2} \implies \theta = \frac{2\tau}{1 - \tau}$$

#### 2. Bivariate Gumbel Copula (Asymmetric Upper Tail Risk)
- **Cumulative Distribution Function:**
  $$C_\theta(u_1, u_2) = \exp\left( - \left[ (-\ln u_1)^\theta + (-\ln u_2)^\theta \right]^{1/\theta} \right), \quad \theta \ge 1$$
- **Tail Dependence Coefficients:**
  - Lower Tail Dependence: $\lambda_L = 0$
  - Upper Tail Dependence: $\lambda_U = 2 - 2^{1/\theta} \in [0, 1)$
- **Kendall's Tau ($\tau$):**
  $$\tau = 1 - \frac{1}{\theta} \implies \theta = \frac{1}{1 - \tau}$$

#### 3. Bivariate Student-t Copula (Symmetric Fat Tails)
- **Tail Dependence Coefficients:**
  $$\lambda_L = \lambda_U = 2 t_{\nu+1}\left( - \sqrt{\frac{(\nu + 1)(1 - \rho)}{1 + \rho}} \right)$$

---

### 1.3 Copula Monte Carlo Simulation & Copula-CVaR
1. **Simulation Algorithm:**
   - Draw $M$ independent uniform samples $(u_1^{(m)}, \dots, u_N^{(m)})$ from fitted copula $C_{\hat{\theta}}$.
   - Invert marginal distributions: $r_i^{(m)} = F_i^{-1}(u_i^{(m)})$.
   - Compute portfolio return samples: $r_p^{(m)} = \sum_{i=1}^N w_i r_i^{(m)}$.
2. **Copula-CVaR ($\text{CVaR}_\alpha$):**
   - At tail confidence $\alpha \in [0.95, 0.99]$:
     $$\text{VaR}_\alpha(w) = - \text{quantile}_{1-\alpha}(r_p)$$
     $$\text{CVaR}_\alpha(w) = -\mathbb{E}[r_p \mid r_p \le -\text{VaR}_\alpha(w)]$$
3. **Tail Risk Contribution ($TRC_i$):**
   $$TRC_i = w_i \frac{\partial \text{CVaR}_\alpha(w)}{\partial w_i} = -w_i \mathbb{E}\left[ r_i \mid r_p \le -\text{VaR}_\alpha(w) \right]$$
4. **Tail Risk Parity Objective:**
   $$\min_w \sum_{i=1}^N \sum_{j=1}^N \left( TRC_i - TRC_j \right)^2 \quad \text{s.t.} \quad \sum_{i=1}^N w_i = 1, \quad w_i \ge 0$$

---

## 2. API Schema Contracts

### 2.1 Request Models
```python
class CopulaFitRequest(BaseModel):
    dataset_id: str
    copula_type: Literal["clayton", "gumbel", "student_t", "best_fit"] = "best_fit"
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    tickers: list[str] | None = None

class CopulaOptimizeRequest(BaseModel):
    dataset_id: str
    copula_type: Literal["clayton", "gumbel", "student_t"] = "clayton"
    confidence_level: float = Field(default=0.99, ge=0.90, le=0.999)
    num_simulations: int = Field(default=5000, ge=1000, le=50000)
    tickers: list[str] | None = None
```

### 2.2 Response Models
```python
class PairwiseCopulaResult(BaseModel):
    asset_1: str
    asset_2: str
    copula_type: str
    theta: float
    kendall_tau: float
    pearson_corr: float
    lower_tail_dependence: float
    upper_tail_dependence: float
    aic: float
    bic: float

class CopulaFitResponse(BaseModel):
    dataset_id: str
    copula_type: str
    marginal_method: str
    tickers: list[str]
    tail_dependence_matrix: list[list[float]]
    kendall_tau_matrix: list[list[float]]
    pairwise_results: list[PairwiseCopulaResult]

class CopulaOptimizeResponse(BaseModel):
    dataset_id: str
    copula_type: str
    confidence_level: float
    weights: dict[str, float]
    tail_risk_contributions: dict[str, float]
    portfolio_cvar: float
    portfolio_var: float
    simulated_loss_distribution: list[float]
```

---

## 3. Independent Worked Benchmark

### 3.1 Bivariate Analytical Benchmark for Clayton Copula
Given $\tau = 0.50$:
$$\theta = \frac{2 \times 0.50}{1 - 0.50} = 2.0$$
Lower tail dependence:
$$\lambda_L = 2^{-1/\theta} = 2^{-1/2} = \frac{1}{\sqrt{2}} \approx 0.70710678$$
Upper tail dependence:
$$\lambda_U = 0.0$$

Verification Tolerance: $| \lambda_L - 0.70710678 | < 10^{-6}$.
