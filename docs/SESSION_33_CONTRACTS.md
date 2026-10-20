# SESSION 33 CONTRACTS — LIQUIDITY-ADJUSTED VAR & MARKET IMPACT FRICTION MODELING
## Stage 25 Mathematical & Temporal Specifications

**Document Version:** 1.0.0  
**Status:** Approved Mathematical & Architectural Contract  
**Roadmap Stage:** Stage 25  
**Date:** 2026-10-19  

---

## 1. Overview & Objectives

This document formalizes the mathematical, temporal, portfolio accounting, and API contracts for **Stage 25 — Liquidity-Adjusted VaR & Market Impact Friction Modeling**.

Stage 25 upgrades the dynamic walk-forward Vine Tail Risk Parity (TRP) backtesting engine from a flat basis-point transaction fee assumption to an institutional liquidity-depth model incorporating:
1. **Exogenous half bid-ask spread crossing costs.**
2. **Endogenous non-linear market impact** (Square-Root Law & Linear Kyle model) calibrated to asset volatility and Average Daily Dollar Volume ($\text{ADV}$).
3. **Volume participation limits** ($\text{PR}_{\max}$) with configurable execution policies (`warn`, `cap`, `reject`).
4. **Liquidity-Adjusted Value-at-Risk ($\text{L-VaR}_\alpha$) and Expected Shortfall ($\text{L-CVaR}_\alpha$)** evaluating total financial liquidation risk.
5. **Strict causal, point-in-time ADV and volatility estimation** with zero look-ahead bias.

---

## 2. Mathematical Execution Cost Model

### 2.1 Trade Notional & Rebalance Sizing
At rebalance date $t_k$, for a portfolio with current equity $V_{t_k}^{\text{pre}}$, target weights $w_{t_k}^*$, and pre-trade drifted weights $w_{t_k}^{\text{pre}}$, the traded notional for asset $i \in \{1, \dots, d\}$ is:
$$\Delta N_{i, t_k} = \left|w_{t_k, i}^* - w_{t_k, i}^{\text{pre}}\right| \cdot V_{t_k}^{\text{pre}}$$
Total traded volume across the portfolio is:
$$\text{Traded Notional} = \sum_{i=1}^d \Delta N_{i, t_k} = 2 \cdot \text{Turnover}_{t_k} \cdot V_{t_k}^{\text{pre}}$$

### 2.2 Cost Breakdown Formulation
The total execution cost for asset $i$ is decomposed additively into three distinct, non-overlapping components:
$$C_i = C_{\text{spread}, i} + C_{\text{impact}, i} + C_{\text{fee}, i}$$

1. **Bid-Ask Spread Cost (One-Sided Half-Spread):**
   $$C_{\text{spread}, i} = \Delta N_i \cdot \left(\frac{1}{2} \cdot \text{Spread}_{\text{bps}, i} \cdot 10^{-4}\right)$$
   *Convention:* Bid-ask spread represents the full quoted round-trip spread in basis points. Half the spread is paid on trade arrival.

2. **Market Impact Cost ($C_{\text{impact}, i}$):**
   - **Participation Rate ($\text{PR}_i$):**
     $$\text{PR}_i = \frac{\Delta N_i}{\text{ADV}_i \cdot H}$$
     where $\text{ADV}_i$ is the Average Daily Dollar Volume and $H$ is the execution horizon in trading days ($H \ge 0.1$).
   - **Square-Root Law Model (`square_root`, default):**
     $$C_{\text{temp}, i} = \Delta N_i \cdot \left(c_{\text{temp}} \cdot \sigma_{i, \text{daily}} \cdot \sqrt{\min(\text{PR}_i, \text{PR}_{\text{cap}})}\right)$$
     $$C_{\text{perm}, i} = \Delta N_i \cdot \left(c_{\text{perm}} \cdot \sigma_{i, \text{daily}} \cdot \min\left(\frac{\Delta N_i}{\text{ADV}_i}, 1.0\right)\right)$$
     $$C_{\text{impact}, i} = C_{\text{temp}, i} + C_{\text{perm}, i}$$
     where $\sigma_{i, \text{daily}} = \frac{\sigma_{i, \text{annual}}}{\sqrt{252}}$, $c_{\text{temp}} = 0.5$ (default), $c_{\text{perm}} = 0.1$ (default).
   - **Linear Impact Model (`linear`):**
     $$C_{\text{impact}, i} = \Delta N_i \cdot \left(c_{\text{temp}} \cdot \sigma_{i, \text{daily}} \cdot \text{PR}_i + c_{\text{perm}} \cdot \sigma_{i, \text{daily}} \cdot \frac{\Delta N_i}{\text{ADV}_i}\right)$$
   - **Fixed Rate Baseline (`fixed_bps`):**
     $$C_{\text{impact}, i} = \Delta N_i \cdot (\text{FixedRate}_{\text{bps}} \cdot 10^{-4})$$

3. **Brokerage Commission & Exchange Fees:**
   $$C_{\text{fee}, i} = \Delta N_i \cdot (\text{Fee}_{\text{bps}} \cdot 10^{-4})$$

4. **Aggregate Rebalance Cost & Deductions:**
   $$C_{\text{total}, t_k} = \sum_{i=1}^d C_i$$
   Post-rebalance capital satisfies:
   $$V_{t_k}^{\text{post}} = \max\left(0.0, V_{t_k}^{\text{pre}} - C_{\text{total}, t_k}\right)$$
   Costs are deducted **strictly once** at trade settlement.

---

## 3. Volume Participation Limits & Execution Policies

Let $\text{PR}_{\max}$ denote the maximum allowed participation rate (default: $0.10$, i.e., $10\%$ of daily volume).

For each asset $i$:
$$\text{PR}_i = \frac{\Delta N_i}{\text{ADV}_i \cdot H}$$

### Configurable Policies:
1. **`warn` (Default):**
   - The full rebalance trade $\Delta N_i$ is executed.
   - If $\text{PR}_i > \text{PR}_{\max}$, an audit warning is generated (`participation_warning: true`).
   - Impact calculation applies square-root scaling with participation capped at $2.0$ for numerical safety.
2. **`cap`:**
   - The executed trade notional is constrained to:
     $$\Delta N_i^{\text{exec}} = \min\left(\Delta N_i, \text{PR}_{\max} \cdot \text{ADV}_i \cdot H\right)$$
   - Executed target weight becomes $w_i^{\text{exec}} = w_i^{\text{pre}} + \operatorname{sgn}(w_i^* - w_i^{\text{pre}}) \cdot \frac{\Delta N_i^{\text{exec}}}{V}$.
   - Remaining unexecuted notional remains in cash or drifts.
3. **`reject`:**
   - If any asset exceeds $\text{PR}_{\max}$, the entire rebalance is aborted for that date.
   - Pre-trade drifted weights $w_{t_k}^{\text{pre}}$ are retained; zero turnover is incurred ($TO = 0, C = 0$).

---

## 4. Liquidity-Adjusted Value-at-Risk (L-VaR & L-CVaR)

### 4.1 Liquidity Cost Function
To liquidate the portfolio of current weights $w$ under immediate orderly unwind over horizon $H$:
$$\text{Liquidation Notional}_i = w_i \cdot V$$
Estimated liquidation cost rate:
$$c_{\text{liq}}(w) = \frac{\sum_{i=1}^d C_i(\text{notional} = w_i \cdot V)}{V}$$

### 4.2 L-VaR and L-CVaR Definition (Lawrence & Robinson / Bangia et al.)
Let $L_{\text{market}} = -R_p = -w^\top R_{\text{sim}}$ denote portfolio market loss.
The total combined loss incorporating endogenous liquidation friction is:
$$L_{\text{combined}} = L_{\text{market}} + c_{\text{liq}}(w)$$

Because $c_{\text{liq}}(w)$ is deterministic conditional on the portfolio weights and point-in-time liquidity parameters:
$$\text{L-VaR}_\alpha(w) = \text{Quantile}_\alpha(L_{\text{combined}}) = \text{VaR}_\alpha(w) + c_{\text{liq}}(w)$$
$$\text{L-CVaR}_\alpha(w) = \mathbb{E}[L_{\text{combined}} \mid L_{\text{combined}} \ge \text{L-VaR}_\alpha] = \text{CVaR}_\alpha(w) + c_{\text{liq}}(w)$$

### 4.3 Invariants & Guarantees
1. **Non-negativity of Liquidity Adjustment:** Since $C_i \ge 0$, $c_{\text{liq}}(w) \ge 0$, guaranteeing:
   $$\text{L-VaR}_\alpha \ge \text{VaR}_\alpha \quad \text{and} \quad \text{L-CVaR}_\alpha \ge \text{CVaR}_\alpha$$
2. **Zero Spread & Infinite Volume Limit:**
   $$\lim_{\text{Spread} \to 0, \text{ADV} \to \infty} \text{L-VaR}_\alpha = \text{VaR}_\alpha$$
3. **No Double-Counting:** Market return variance captures purely price volatility; liquidation friction is additively attributed without modifying underlying price return series.

---

## 5. Temporal Protocol & Point-in-Time Data Contract

At rebalance date $t_k$:
- **Estimation Window:** $\mathcal{W}_k = [t_k - W, t_k - 1]$.
- **Point-in-Time ADV:**
  $$\text{ADV}_{i, t_k} = \frac{1}{W} \sum_{\tau = t_k - W}^{t_k - 1} \text{Volume}_{i, \tau} \cdot P_{i, \tau}$$
- **Point-in-Time Volatility:**
  $$\sigma_{i, t_k} = \sqrt{\frac{252}{W - 1} \sum_{\tau = t_k - W}^{t_k - 1} \left(R_{i, \tau} - \bar{R}_i\right)^2}$$
- **Anti-Look-Ahead Rule:**
  Day $t_k$ prices, returns, and volumes are **strictly excluded** from $\text{ADV}_{i, t_k}$ and $\sigma_{i, t_k}$.

---

## 6. API & Service Data Contracts

### 6.1 Extended Request Schema (`VineBacktestRequest`)
```python
class VineBacktestRequest(BaseModel):
    # Existing Stage 24 fields
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    estimation_window: int = Field(default=60, ge=30)
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly"
    num_simulations: int = Field(default=2000, ge=500, le=20000)
    confidence_level: float = Field(default=0.99, ge=0.90, le=0.999)
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    transaction_cost_bps: float = Field(default=10.0, ge=0.0) # Brokerage fee
    slippage_bps: float = Field(default=5.0, ge=0.0)
    initial_capital: float = Field(default=100000.0, gt=0.0)
    risk_free_rate: float = Field(default=0.02, ge=0.0)
    random_seed: int = Field(default=42)
    tickers: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # New Stage 25 Liquidity & Execution Fields
    execution_model: Literal["fixed_bps", "linear", "square_root"] = "square_root"
    bid_ask_spread_bps: float = Field(default=5.0, ge=0.0)
    max_participation_rate: float = Field(default=0.10, ge=0.01, le=1.0)
    participation_policy: Literal["warn", "cap", "reject"] = "warn"
    execution_horizon_days: float = Field(default=1.0, ge=0.1, le=10.0)
    c_temp: float = Field(default=0.5, ge=0.0)
    c_perm: float = Field(default=0.1, ge=0.0)
    default_adv: float = Field(default=10_000_000.0, gt=0.0)
```

### 6.2 Extended Response Schema (`VineBacktestResponse`)
Extended with:
- `strategy_metrics`: includes `l_var_99`, `l_cvar_99`, `spread_costs`, `market_impact_costs`, `commission_costs`.
- `rebalance_history`: each event includes `spread_cost`, `market_impact_cost`, `commission_cost`, `max_participation_rate`, `participation_warning`, `l_cvar`.
