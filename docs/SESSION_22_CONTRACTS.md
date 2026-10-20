# SESSION 22 CONTRACTS: MULTI-ASSET CLASS ALLOCATION, CASH DRAG & MULTI-CURRENCY FX HEDGING ENGINE (STAGE 18)

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 22  
**Approved Stage:** Stage 18 — Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging Engine  
**Contract Author:** Senior Quantitative Finance Research Engineer & Software Quality Auditor  
**Date:** 2026-10-18  
**Status:** **APPROVED BASELINE CONTRACT**

---

## 1. Mathematical Notation & Financial Foundations

### 1.1 Multi-Asset Universe & Taxonomy
Let the investment universe comprise $N$ risky assets indexed by $i \in \{1, \dots, N\}$, partitioned into distinct asset classes $\mathcal{C}$:
$$\mathcal{C} = \{\text{Equity}, \text{Fixed Income}, \text{Commodity}, \text{Real Estate}, \dots\}$$
and an explicit Cash / Treasury buffer balance $C$, earning the daily risk-free interest rate $r_f$.

Let:
- $w = [w_1, \dots, w_N]^\top \in \mathbb{R}^N$ be the vector of risky asset weights.
- $w_{\text{cash}} \in [0, 1]$ be the portfolio cash weight.
- Full budget condition:
  $$\sum_{i=1}^N w_i + w_{\text{cash}} = 1.0, \quad w_i \ge 0, \quad w_{\text{cash}} \ge 0$$
- Asset class group constraints: For each asset class $c \in \mathcal{C}$,
  $$L_c \le \sum_{i \in c} w_i \le U_c, \quad L_{\text{cash}} \le w_{\text{cash}} \le U_{\text{cash}}$$

---

### 1.2 Multi-Currency FX Conversion & Exact Discrete Simple Return Identity
Let asset $i$ be traded in local currency $k(i) \in \{\text{USD}, \text{PKR}, \text{EUR}, \text{GBP}, \dots\}$.  
Let base portfolio reporting currency be $B$ (e.g. $\text{USD}$ or $\text{PKR}$).  
Let $S_{k,t}$ be the spot exchange rate defined as the price of 1 unit of local currency $k$ in units of base currency $B$:
$$P_{i,t}^{\text{base}} = P_{i,t}^{\text{loc}} \times S_{k(i),t}$$

The discrete simple return in base reporting currency satisfies the exact multiplicative compounding identity:
$$1 + R_{i,t}^{\text{base}} = \frac{P_{i,t}^{\text{base}}}{P_{i,t-1}^{\text{base}}} = \frac{P_{i,t}^{\text{loc}}}{P_{i,t-1}^{\text{loc}}} \times \frac{S_{k(i),t}}{S_{k(i),t-1}} = (1 + R_{i,t}^{\text{loc}})(1 + R_{k(i),t}^{\text{fx}})$$
$$R_{i,t}^{\text{base}} = R_{i,t}^{\text{loc}} + R_{k(i),t}^{\text{fx}} + R_{i,t}^{\text{loc}} R_{k(i),t}^{\text{fx}}$$
where $R_{k(i),t}^{\text{fx}} = \frac{S_{k(i),t} - S_{k(i),t-1}}{S_{k(i),t-1}}$ is the simple return of local currency $k$ against base currency $B$.

---

### 1.3 FX Currency Risk Decomposition (Unhedged Portfolio)
For an unhedged portfolio, total base portfolio return is:
$$R_{p,t}^{\text{base}} = \sum_{i=1}^N w_i R_{i,t}^{\text{base}} + w_{\text{cash}} R_{\text{cash},t}$$

For risky assets, the base covariance matrix $\Sigma_{\text{base}} \in \mathbb{R}^{N \times N}$ decomposes into three distinct structural components:
1. **Asset Local Risk:** $\Sigma_{\text{loc}} = \operatorname{Cov}(R^{\text{loc}})$
2. **FX Currency Risk:** $\Sigma_{\text{fx}} = \operatorname{Cov}(R^{\text{fx}})$
3. **Cross-Covariance Interaction:** $\Sigma_{\text{cross}} = \operatorname{Cov}(R^{\text{loc}}, R^{\text{fx}})$

$$\Sigma_{\text{base}} \approx \Sigma_{\text{loc}} + \Sigma_{\text{fx}} + \Sigma_{\text{cross}} + \Sigma_{\text{cross}}^\top$$
The total portfolio variance decomposes additively into:
$$\sigma_p^2 = w^\top \Sigma_{\text{loc}} w + w^\top \Sigma_{\text{fx}} w + 2 w^\top \Sigma_{\text{cross}} w$$
$$\% \text{Risk}_{\text{asset}} = \frac{w^\top \Sigma_{\text{loc}} w}{\sigma_p^2} \times 100\%, \quad \% \text{Risk}_{\text{fx}} = \frac{w^\top \Sigma_{\text{fx}} w + 2 w^\top \Sigma_{\text{cross}} w}{\sigma_p^2} \times 100\%$$

---

### 1.4 Currency Hedging Overlay & Covered Interest Parity (CIP) Carry
An investor can apply a currency hedge ratio $h_k \in [0, 1]$ to each non-base currency $k \in \mathcal{K}$:
- $h_k = 0.0$: Fully unhedged (100% FX volatility exposure).
- $h_k = 1.0$: Fully hedged (FX exchange rate fluctuations neutralized).
- $h_k \in (0, 1)$: Partially hedged.

Under Covered Interest Parity (CIP), forward contracts sell the local currency at forward rate $F_{k,t}$, generating a theoretical carry return:
$$\text{Carry}_{k} = \frac{r_{\text{base}} - r_{k,\text{loc}}}{252}$$
The hedged return of asset $i$ denominated in local currency $k$ is:
$$R_{i,t}^{\text{hedged}} = R_{i,t}^{\text{base}} - h_k \left( R_{k,t}^{\text{fx}} - \text{Carry}_{k} \right)$$
When $h_k = 1.0$, the first-order FX return $R_{k,t}^{\text{fx}}$ is eliminated, leaving:
$$R_{i,t}^{\text{hedged}} = R_{i,t}^{\text{loc}} + \text{Carry}_{k} + R_{i,t}^{\text{loc}} R_{k,t}^{\text{fx}}$$

---

### 1.5 Cash Drag & Yield Modeling
Cash earns the annualized risk-free rate compounded daily:
$$R_{\text{cash}, t} = \frac{r_f}{252}$$
When risky assets rally with expected return $\mu_{\text{risky}} > r_f$, holding cash causes return dilution:
$$\text{Cash Drag}_t = w_{\text{cash}} \cdot \left( \sum_{i=1}^N \frac{w_i}{1 - w_{\text{cash}}} R_{i,t} - r_f \right)$$
In downturns, cash dampens volatility and preserves capital:
$$\sigma_p = (1 - w_{\text{cash}}) \sigma_{\text{risky}}$$

---

## 2. Independent Hand-Calculated Analytical Benchmark

### 2.1 Specification (2 Assets, 1 Cash, 2 Currencies)
- **Base Reporting Currency:** USD
- **Asset 1 (US Equity):**
  - Currency: USD ($S_{1} \equiv 1.0$, $R_{1}^{\text{fx}} \equiv 0$)
  - Local Return: $R_1^{\text{loc}} = [0.02, -0.01, 0.03, -0.02]^\top$
  - Asset Class: `Equity`
- **Asset 2 (European Bond):**
  - Currency: EUR
  - Local Return: $R_2^{\text{loc}} = [0.005, 0.002, -0.001, 0.004]^\top$
  - Asset Class: `Fixed Income`
  - Spot FX Return (EUR/USD): $R_{\text{EUR}}^{\text{fx}} = [0.010, -0.015, 0.020, -0.005]^\top$
  - Forward carry differential: $\text{Carry}_{\text{EUR}} = \frac{0.04 - 0.02}{252} \approx 0.000079365$
- **Cash:**
  - $w_{\text{cash}} = 0.20$, earning $r_f = 0.03$ ($R_{\text{cash}} = \frac{0.03}{252} \approx 0.0001190476$)
- **Portfolio Allocation:**
  - $w_1 = 0.50$ (US Equity)
  - $w_2 = 0.30$ (European Bond)
  - $w_{\text{cash}} = 0.20$ (USD Cash)
  - $\sum w_i + w_{\text{cash}} = 0.50 + 0.30 + 0.20 = 1.00$

### 2.2 Period 1 Computations ($t = 1$)
1. **Asset 1 Base Return:**
   $$R_{1,1}^{\text{base}} = 0.020000$$
2. **Asset 2 Unhedged Base Return ($h = 0.0$):**
   $$R_{2,1}^{\text{base}} = (1 + R_{2,1}^{\text{loc}})(1 + R_{\text{EUR},1}^{\text{fx}}) - 1 = (1.005)(1.010) - 1 = 1.01505 - 1 = 0.015050$$
3. **Asset 2 Fully Hedged Base Return ($h = 1.0$):**
   $$R_{2,1}^{\text{hedged}} = R_{2,1}^{\text{base}} - 1.0 \times (R_{\text{EUR},1}^{\text{fx}} - \text{Carry}_{\text{EUR}}) = 0.015050 - (0.010 - 0.000079365) = 0.005129365$$
4. **Portfolio Unhedged Return ($t=1$):**
   $$R_{p,1}^{\text{unhedged}} = 0.50(0.020000) + 0.30(0.015050) + 0.20(0.0001190476) = 0.010000 + 0.004515 + 0.00002381 = 0.01453881$$
5. **Portfolio Hedged Return ($t=1$):**
   $$R_{p,1}^{\text{hedged}} = 0.50(0.020000) + 0.30(0.005129365) + 0.20(0.0001190476) = 0.010000 + 0.00153881 + 0.00002381 = 0.01156262$$
6. **Cash Drag on Return ($t=1$):**
   $$\text{Drag}_1 = 0.20 \times \left( \frac{0.50(0.02) + 0.30(0.01505)}{0.80} - 0.00011905 \right) = 0.20 \times (0.01814375 - 0.00011905) = 0.00360494$$
7. **Tolerance:**
   All numerical implementations must match these exact benchmark values to within **$1 \times 10^{-12}$**.

---

## 3. Optimization Solver & Group Constraints Formulation

The optimization problem incorporates asset class bounds and cash weighting:
$$\min_{w \in \mathbb{R}^N, w_{\text{cash}} \in [0, 1]} \frac{1}{2} w^\top \Sigma_{\text{base}} w - \gamma \left( w^\top \mu_{\text{base}} + w_{\text{cash}} r_f \right)$$
subject to:
1. **Full Budget Equality:** $\sum_{i=1}^N w_i + w_{\text{cash}} = 1.0$
2. **Individual Box Bounds:** $w_i \in [w_{\min}, w_{\max}], \forall i \in \{1, \dots, N\}$
3. **Cash Bounds:** $w_{\text{cash}} \in [w_{\text{cash},\min}, w_{\text{cash},\max}]$
4. **Asset Class Group Constraints:** For each class $c \in \mathcal{C}$,
   $$\sum_{i \in c} w_i \ge L_c \implies \sum_{i \in c} w_i - L_c \ge 0$$
   $$\sum_{i \in c} w_i \le U_c \implies U_c - \sum_{i \in c} w_i \ge 0$$
5. **Analytical Jacobians:**
   - Budget gradient: $\mathbf{1}_{N+1}$
   - Class group gradient: Indicator vector with $1$ for $i \in c$ and $0$ otherwise.

---

## 4. REST API & Pydantic Contracts

### 4.1 Endpoints
- `POST /api/v1/multi-asset/optimize`: Solves multi-asset allocation under class limits, cash buffers, and FX hedge overlays.
- `POST /api/v1/multi-asset/backtest`: Executes chronological walk-forward multi-asset simulation with dynamic currency conversion, cash interest compounding, and weight drift.

### 4.2 Request & Response Schemas
```python
class AssetMetadata(BaseModel):
    ticker: str
    asset_class: Literal["Equity", "Fixed Income", "Commodity", "Real Estate", "Other"]
    currency: str  # e.g. "USD", "PKR", "EUR", "GBP"

class MultiAssetOptimizeRequest(BaseModel):
    dataset_id: str
    base_currency: str = "USD"
    assets_metadata: list[AssetMetadata]
    fx_rates_dataset_id: str | None = None
    hedge_ratios: dict[str, float] = Field(default_factory=dict)  # currency -> ratio [0.0, 1.0]
    asset_class_limits: dict[str, dict[str, float]] = Field(default_factory=dict)  # class -> {min_weight, max_weight}
    min_cash_weight: float = Field(0.05, ge=0.0, le=1.0)
    max_cash_weight: float = Field(0.30, ge=0.0, le=1.0)
    objective: Literal["max_sharpe", "min_variance", "risk_parity"] = "max_sharpe"
    risk_free_rate: float = Field(0.03, ge=0.0, le=0.20)
    min_asset_weight: float = Field(0.0, ge=0.0, le=1.0)
    max_asset_weight: float = Field(1.0, ge=0.0, le=1.0)
```

---

## 5. Security, Multi-Tenant Isolation & Look-Ahead Discipline

1. **Authentication & Tenancy:**
   All endpoints require valid JWT authentication via `Depends(get_current_active_user)`. Dataset access must be strictly verified using `check_dataset_access`.
2. **Strict Chronological Data Alignment:**
   Currency FX series and asset price series must be joined strictly on matching calendar dates. Future exchange rates or forward rates must never leak into historical asset conversions or rebalance decisions.
3. **Backward Compatibility:**
   Existing single-currency endpoints (`/api/v1/optimization/solve`, `/api/v1/backtests`) remain 100% backward-compatible and unaffected.

---

## 6. Acceptance Criteria

1. **Analytical Benchmark:** 2-asset 1-cash hand calculation reconciles to $< 10^{-12}$.
2. **Budget Invariant:** $\sum_{i=1}^N w_i + w_{\text{cash}} = 1.0$ satisfied within $10^{-6}$.
3. **FX Risk Decomposition:** $\% \text{Risk}_{\text{asset}} + \% \text{Risk}_{\text{fx}} = 100\%$ within $10^{-6}$.
4. **Group Constraints:** All optimal asset class allocations strictly respect $[L_c, U_c]$ bounds.
5. **Zero Look-Ahead Bias:** Future FX rates or asset prices do not alter historical in-sample rebalance decisions.
6. **Regression Suite:** All 314 existing backend tests pass without failure.
7. **Frontend Tests & Build:** Vitest suite and `npm run build` pass with exit code 0.
