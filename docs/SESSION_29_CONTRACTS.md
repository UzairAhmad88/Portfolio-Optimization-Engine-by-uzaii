# SESSION 29 CONTRACTS — REGULAR VINE COPULA ARCHITECTURE & REMEDIATED SIMULATION

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 29  
**Specification Type:** Mathematical, Algorithmic & API Interface Contracts  
**Module:** `backend/app/quant/vine_copula.py`, `backend/app/quant/copula_tail_risk.py`, `backend/app/api/v1/copula_routes.py`  
**Frontend Types:** `frontend/src/types/api.ts`  

---

## 1. Mathematical & Algorithmic Contracts

### 1.1 Positive-Stable Frailty Gumbel Sampler Contract
```python
def simulate_positive_stable_gumbel(
    theta: float,
    d: int,
    num_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
```
- **Preconditions**:
  - $\theta \ge 1.0$, finite.
  - $d \ge 2$, integer.
  - $\text{num\_simulations} \ge 1$, integer.
- **Postconditions**:
  - Returns array $U \in \mathbb{R}^{M \times d}$ where $U_{ij} \in (0, 1)$ strictly.
  - For $\theta = 1.0$: columns $U_{\cdot, j}$ are mutually independent uniforms.
  - For $\theta > 1.0$: pairwise Kendall's tau satisfies $E[\hat{\tau}] = 1 - 1/\theta$.
  - Theoretical upper tail dependence $\lambda_U = 2 - 2^{1/\theta}$ is recovered.
  - Lower tail dependence satisfies $\lambda_L = 0$.

---

### 1.2 Conditional $h$-Function & Inverse Transform Contracts
```python
def h_function(
    u: np.ndarray,
    v: np.ndarray,
    copula_type: str,
    theta: float = 0.0,
    df: float = 4.0,
) -> np.ndarray:

def h_inv_function(
    w: np.ndarray,
    v: np.ndarray,
    copula_type: str,
    theta: float = 0.0,
    df: float = 4.0,
) -> np.ndarray:
```
- **Definition**: $h(u, v; \theta) = P(U \le u \mid V = v) = \frac{\partial C(u, v)}{\partial v}$.
- **Invariance**: $h^{-1}(h(u, v; \theta), v; \theta) = u$ for all $u, v \in (0, 1)$ and all supported families:
  - `"independence"`: $h(u, v) = u, \quad h^{-1}(w, v) = w$.
  - `"gaussian"`: $\Phi\left( \frac{\Phi^{-1}(u) - \rho \Phi^{-1}(v)}{\sqrt{1 - \rho^2}} \right)$, with $|\rho| \le 0.999$.
  - `"student_t"`: $t_{\nu+1}\left( \frac{t_\nu^{-1}(u) - \rho t_\nu^{-1}(v)}{\sqrt{\frac{(\nu + (t_\nu^{-1}(v))^2)(1 - \rho^2)}{\nu + 1}}} \right)$, with $\nu \ge 2.1$.
  - `"clayton"`: $v^{-(1+\theta)} (u^{-\theta} + v^{-\theta} - 1)^{-(1 + 1/\theta)}$, with $\theta \ge 10^{-4}$.
  - `"gumbel"`: $\frac{\partial C_{\text{Gumbel}}}{\partial v}$, with $\theta \ge 1.0$, inverted via Brent's method with residual $< 10^{-6}$.

---

### 1.3 Regular Vine Decomposition Contract
A vine tree structure contains $d-1$ trees. In tree $m \in \{1, \dots, d-1\}$:
- Number of edges: $d - m$.
- Total pair copulas: $d(d-1)/2$.
- Each edge object defines:
```json
{
  "edge_id": "T1_e0",
  "tree_level": 1,
  "node_1": "SPY",
  "node_2": "TLT",
  "conditioned_on": [],
  "copula_type": "clayton",
  "theta": 1.452,
  "df": null,
  "kendall_tau": 0.421,
  "lower_tail_dependence": 0.619,
  "upper_tail_dependence": 0.0,
  "aic": -142.5
}
```

---

## 2. API Route & Schema Contracts

### 2.1 `POST /api/v1/copula/vine/fit`
**Request Body**:
```json
{
  "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "tickers": ["SPY", "TLT", "GLD"],
  "vine_type": "c_vine",
  "marginal_method": "empirical"
}
```
**Response Body**:
```json
{
  "vine_type": "c_vine",
  "dimension": 3,
  "ordered_tickers": ["SPY", "TLT", "GLD"],
  "marginal_method": "empirical",
  "trees": [
    [
      { "edge_id": "T1_e0", "tree_level": 1, "node_1": "SPY", "node_2": "TLT", "copula_type": "gaussian", "theta": -0.32, "aic": -45.2 },
      { "edge_id": "T1_e1", "tree_level": 1, "node_1": "SPY", "node_2": "GLD", "copula_type": "clayton", "theta": 0.54, "aic": -28.1 }
    ],
    [
      { "edge_id": "T2_e0", "tree_level": 2, "node_1": "TLT", "node_2": "GLD", "conditioned_on": ["SPY"], "copula_type": "student_t", "theta": 0.22, "df": 5.0, "aic": -12.4 }
    ]
  ],
  "total_aic": -85.7
}
```

---

### 2.2 `POST /api/v1/copula/vine/simulate`
**Request Body**:
```json
{
  "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "tickers": ["SPY", "TLT", "GLD"],
  "vine_type": "d_vine",
  "num_simulations": 5000,
  "random_seed": 42,
  "marginal_method": "empirical"
}
```
**Response Body**:
```json
{
  "vine_type": "d_vine",
  "num_simulations": 5000,
  "random_seed": 42,
  "tickers": ["SPY", "TLT", "GLD"],
  "simulated_returns": [ ... ],
  "trees": [ ... ]
}
```

---

### 2.3 `POST /api/v1/copula/vine/tail-risk-parity`
**Request Body**:
```json
{
  "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "tickers": ["SPY", "TLT", "GLD"],
  "vine_type": "c_vine",
  "alpha": 0.95,
  "num_simulations": 5000,
  "random_seed": 42,
  "marginal_method": "empirical"
}
```
**Response Body**:
```json
{
  "weights": { "SPY": 0.312, "TLT": 0.445, "GLD": 0.243 },
  "tail_risk_contributions": { "SPY": 0.0075, "TLT": 0.0075, "GLD": 0.0075 },
  "portfolio_var": 0.0162,
  "portfolio_cvar": 0.0225,
  "dispersion": 0.00000012,
  "iterations": 18,
  "converged": true,
  "vine_type": "c_vine",
  "trees": [ ... ]
}
```

---

## 3. Euler Risk Identity Invariant
For weights $w \in \Delta^{N-1}$ and empirical tail scenarios $\mathcal{T}_\alpha = \{m : L_m \ge \widehat{\text{VaR}}_\alpha\}$:
$$\text{TRC}_i(w) = - w_i \cdot \frac{1}{|\mathcal{T}_\alpha|} \sum_{m \in \mathcal{T}_\alpha} R_{m, i}$$
$$\sum_{i=1}^N \text{TRC}_i(w) \equiv \widehat{\text{CVaR}}_\alpha(w)$$
The numerical difference $|\sum \text{TRC}_i - \widehat{\text{CVaR}}_\alpha| \le 10^{-12}$ is maintained identically in all vine simulation allocations.
