# Scenario Analysis, Stress Testing & Sensitivity Analysis Contracts

**Document Version:** 1.0.0  
**Status:** Approved Quantitative Finance Specification  
**Date:** 2026-10-18  
**Scope:** Formal mathematical conventions, data schemas, validation invariants, and accounting rules for scenario analysis and stress testing.

---

## 1. Core Principles & Semantic Distinctions

### 1.1 Instantaneous Shocks vs. Multi-Period Simulation Paths
- **Instantaneous Shock (Static Evaluation):**
  A hypothetical, immediate repricing of portfolio assets evaluated at a single point in time ($t = 0 \to 0^+$).
  - Formula: $V_{\text{after}} = \sum_{i=1}^n V_i (1 + s_i) + C$
  - Time dimension: $\Delta t = 0$.
  - **Prohibited Metrics:** Time-dependent metrics such as Sharpe ratio, Sortino ratio, CAGR, and annualized volatility **must not** be calculated from an instantaneous shock. Only static change metrics ($\Delta V$, $\% \Delta V$, asset-level contribution) are permitted.
- **Historical Stress Period (Historical Window Replay):**
  An evaluation of cumulative observed asset returns over a verified historical date range $[t_{\text{start}}, t_{\text{end}}]$ from the active dataset.
  - Formula: $r_{i, \text{observed}} = (P_{i, t_{\text{end}}} - P_{i, t_{\text{start}}}) / P_{i, t_{\text{start}}}$
  - **No Fabrication Guarantee:** Historical returns must be derived exclusively from actual verified price bars. Missing dates or unobserved assets are not forward-filled or fabricated.
- **Covariance & Correlation Stress:**
  A mathematical perturbation applied to an estimated baseline covariance matrix $\mathbf{\Sigma}_0$ to evaluate changes in theoretical portfolio volatility $\sigma_p = \sqrt{\mathbf{w}^T \mathbf{\Sigma}_{\text{stressed}} \mathbf{w}}$.
  - Volatilities may not be negative.
  - The resulting matrix $\mathbf{\Sigma}_{\text{stressed}}$ must remain symmetric and positive semi-definite (PSD: $\forall \lambda_i \ge -10^{-8}$).

---

## 2. Mathematical Formulations & Accounting

### 2.1 Portfolio Valuation & Cash Handling
Let a portfolio consist of $n$ assets with pre-shock market values $V_i \ge 0$ (or weights $w_i$) and uninvested cash $C \ge 0$.
The baseline total portfolio value is:
$$V_{\text{pre}} = \sum_{i=1}^n V_i + C$$

When specified via weights $\mathbf{w}$ and total capital $V_{\text{pre}}$:
$$V_i = w_i \cdot V_{\text{pre}}$$
$$\sum_{i=1}^n w_i \le 1.0, \quad C = V_{\text{pre}} \left(1.0 - \sum_{i=1}^n w_i\right)$$
For a fully invested portfolio, $\sum w_i = 1.0 \implies C = 0$.

### 2.2 Instantaneous Asset Shocks
Let $s_i \in \mathbb{R}$ represent the fractional price shock applied to asset $i$ (e.g., $s_i = -0.15$ denotes a $-15\%$ drop).
The shocked value of asset $i$ is:
$$V_{i, \text{after}} = V_i (1 + s_i)$$

The stressed portfolio value is:
$$V_{\text{after}} = \sum_{i=1}^n V_{i, \text{after}} + C = \sum_{i=1}^n V_i (1 + s_i) + C$$

The absolute portfolio value change is:
$$\Delta V = V_{\text{after}} - V_{\text{pre}} = \sum_{i=1}^n V_i \cdot s_i$$

The percentage portfolio change is:
$$\% \Delta V = \begin{cases} 
\frac{\Delta V}{V_{\text{pre}}}, & \text{if } V_{\text{pre}} > 0 \\
0.0, & \text{if } V_{\text{pre}} = 0 \text{ (with warning)}
\end{cases}$$

### 2.3 Asset-Level Contribution Attribution
The dollar contribution of asset $i$ to the total portfolio change is:
$$\text{ContributionDollar}_i = V_i \cdot s_i = \Delta V_i$$

The relative contribution of asset $i$ to the total portfolio percentage return is:
$$\text{ContributionReturn}_i = w_i \cdot s_i$$
Notice the exact conservation property:
$$\sum_{i=1}^n \text{ContributionDollar}_i = \Delta V$$
$$\sum_{i=1}^n \text{ContributionReturn}_i = \% \Delta V \quad (\text{when } C = 0)$$

The percentage share of total portfolio loss/gain attributed to asset $i$ is:
$$\text{ShareOfChange}_i = \begin{cases} 
\frac{\Delta V_i}{\Delta V}, & \text{if } |\Delta V| > 10^{-12} \\
\frac{1}{n}, & \text{if } \Delta V = 0
\end{cases}$$

### 2.4 Covariance & Correlation Stress Mathematics
Let $\mathbf{\Sigma}_0 = \mathbf{D}_0 \mathbf{R}_0 \mathbf{D}_0$ be the baseline covariance matrix, where $\mathbf{D}_0 = \text{diag}(\sigma_1, \dots, \sigma_n)$ is the diagonal matrix of asset standard deviations and $\mathbf{R}_0$ is the correlation matrix ($R_{ii} = 1.0, -1 \le R_{ij} \le 1$).

1. **Volatility Scaling:**
   Applying volatility shock factor $\alpha_i > 0$ to asset $i$:
   $$\sigma_{i, \text{stressed}} = \sigma_i \cdot \alpha_i$$
   $$\mathbf{D}_{\text{stressed}} = \text{diag}(\sigma_{1, \text{stressed}}, \dots, \sigma_{n, \text{stressed}})$$
   $$\mathbf{\Sigma}_{\text{vol\_stressed}} = \mathbf{D}_{\text{stressed}} \mathbf{R}_0 \mathbf{D}_{\text{stressed}}$$

2. **Correlation Contraction / Expansion:**
   Applying correlation stress factor $\beta \in [0.0, 2.0]$ to off-diagonal elements:
   $$R_{ij, \text{stressed}} = \begin{cases} 
   1.0, & \text{if } i = j \\
   \text{clip}\left(R_{ij} \cdot \beta, -0.999, 0.999\right), & \text{if } i \ne j 
   \end{cases}$$
   
3. **Positive Semi-Definiteness (PSD) Verification & Projection:**
   An arbitrary modification of $\mathbf{R}$ may yield negative eigenvalues ($\exists \lambda_k < 0$).
   - The engine validates eigenvalues via `numpy.linalg.eigh`.
   - If $\lambda_{\min} < -10^{-8}$, the matrix is mathematically invalid.
   - If user requests automatic PSD projection, the nearest correlation matrix in the Frobenius norm is computed via spectral eigenvalue clipping:
     $$\mathbf{R}_{\text{proj}} = \sum_{k=1}^n \max(\lambda_k, 10^{-8}) \mathbf{v}_k \mathbf{v}_k^T$$
     followed by diagonal normalization ($R_{ii} \gets 1.0$).
     A structured warning is emitted detailing the eigenvalue shift.

4. **Stressed Portfolio Volatility:**
   $$\sigma_{p, \text{stressed}} = \sqrt{\mathbf{w}^T \mathbf{\Sigma}_{\text{stressed}} \mathbf{w}}$$
   $$\Delta \sigma_p = \sigma_{p, \text{stressed}} - \sigma_{p, \text{baseline}}$$

---

## 3. Data Validation & Boundary Invariants

| Invariant ID | Rule | Failure Action |
|---|---|---|
| **INV-SCN-001** | **Asset Resolution:** All shocked assets must map uniquely to canonical IDs (`TICKER:MARKET`) in the dataset. | HTTP 422 with list of unresolvable assets. |
| **INV-SCN-002** | **Currency Homogeneity:** All assets in the portfolio must share the same currency (e.g. `USD`). Cross-currency mixtures (e.g. `USD` + `PKR`) are strictly rejected. | HTTP 422 with conflicting currencies list. |
| **INV-SCN-003** | **Finite Shocks:** Shocks must be finite IEEE 754 floats ($\text{NaN}, \pm\infty$ rejected). Shocks must satisfy $s_i \ge -1.0$ (assets cannot lose more than 100% in an unleveraged long holding). | HTTP 422 with out-of-bounds error. |
| **INV-SCN-004** | **Weight Consistency:** Pre-shock weights must satisfy $\sum w_i \le 1.0 + 10^{-6}$ and $w_i \ge -10^{-12}$ for long-only portfolios. | HTTP 422 feasibility rejection. |
| **INV-SCN-005** | **Grid Bound Ceilings:** 1D sensitivity sweeps are capped at $\le 101$ points. 2D sensitivity grids are capped at $\le 21 \times 21 = 441$ points. | HTTP 422 grid resolution limit exceeded. |
| **INV-SCN-006** | **Historical Range Alignment:** Historical stress date ranges $[t_{\text{start}}, t_{\text{end}}]$ must contain at least 2 valid overlapping price observations for all portfolio assets. | HTTP 422 insufficient date coverage. |
| **INV-SCN-007** | **Zero Silent Imputation:** The engine must never manufacture missing observations or silently forward-fill gaps. | Strict error or explicit warning log. |

---

## 4. API Request & Response Schemas

### 4.1 Custom Asset Shock Request (`POST /api/v1/scenarios`)
```json
{
  "dataset_id": "ds-tech-5yr",
  "name": "Tech Sector -20% Drawdown",
  "scenario_type": "custom_asset_shock",
  "assets": ["AAPL:US", "MSFT:US", "GOOGL:US"],
  "weights": {
    "AAPL:US": 0.40,
    "MSFT:US": 0.35,
    "GOOGL:US": 0.25
  },
  "initial_capital": 1000000.0,
  "asset_shocks": {
    "AAPL:US": -0.15,
    "MSFT:US": -0.20,
    "GOOGL:US": -0.10
  }
}
```

### 4.2 Sensitivity Analysis Request (`POST /api/v1/scenarios/sensitivity`)
```json
{
  "dataset_id": "ds-tech-5yr",
  "name": "AAPL Return Sensitivity Sweep",
  "assets": ["AAPL:US", "MSFT:US", "GOOGL:US"],
  "weights": {
    "AAPL:US": 0.40,
    "MSFT:US": 0.35,
    "GOOGL:US": 0.25
  },
  "initial_capital": 1000000.0,
  "factor_1_asset": "AAPL:US",
  "factor_1_min_shock": -0.30,
  "factor_1_max_shock": 0.30,
  "factor_1_steps": 13,
  "factor_2_asset": null
}
```

### 4.3 Covariance & Correlation Stress Request (`POST /api/v1/scenarios/stress-test`)
```json
{
  "dataset_id": "ds-tech-5yr",
  "name": "High Volatility & Correlation Breakdown",
  "assets": ["AAPL:US", "MSFT:US", "GOOGL:US"],
  "weights": {
    "AAPL:US": 0.40,
    "MSFT:US": 0.35,
    "GOOGL:US": 0.25
  },
  "stress_type": "covariance_stress",
  "volatility_multiplier": 1.50,
  "correlation_multiplier": 1.25,
  "auto_project_psd": true
}
```

---

## 5. Provenance, Governance & Disclaimer

1. **Non-Prediction Disclaimer:**
   Every scenario response emits `is_hypothetical: true` and an explicit disclaimer notice:
   *"Hypothetical scenario results are instantaneous mathematical projections based on user-supplied or historical assumptions. They do not constitute investment advice, forecasts, or guarantees of future performance."*
2. **Audit Logging & Provenance:**
   Every scenario execution records the authenticated `user_id`, `dataset_id`, exact timestamps, calculation duration in milliseconds, parameter inputs, and warnings in relational storage for reproducibility and regulatory auditability.
