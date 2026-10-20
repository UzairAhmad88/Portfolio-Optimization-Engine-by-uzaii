# SESSION 41 CONTRACTS & SPECIFICATIONS: STAGE 30
## Transaction Cost Analysis (TCA) and Slippage Performance Attribution

**Document:** Formal Mathematical & Architectural Specifications  
**Session:** 41  
**Stage:** 30 — Transaction Cost Analysis (TCA) and Slippage Attribution  
**Status:** Active Production Contract  

---

### 1. Mathematical Formulation

#### 1.1 Trade Direction & Adverse Cost Sign Convention
For each fill $j \in \{1, \dots, J\}$ on asset $i$:
- $s_j \in \{+1, -1\}$ denotes the trade direction: $s_j = +1$ for a buy ($\Delta w_i > 0$) and $s_j = -1$ for a sell ($\Delta w_i < 0$).
- $N_j > 0$ is the executed trade notional in portfolio base currency (USD).
- $P_j^{\text{arr}} > 0$ is the causal arrival reference price strictly anchored at the decision-time bar close $t_k$.
- $P_j^{\text{fill}} > 0$ is the realized execution fill price over the execution interval $[t_k, t_k + \Delta t]$.

The realized arrival-price slippage cost $C_j^{\text{slip}}$ follows the strict adverse-cost accounting convention:
$$C_j^{\text{slip}} = s_j \cdot N_j \cdot \left(\frac{P_j^{\text{fill}} - P_j^{\text{arr}}}{P_j^{\text{arr}}}\right)$$

**Sign Economic Invariants:**
1. **Adverse Buy Execution:** $s_j = +1$, $P_j^{\text{fill}} > P_j^{\text{arr}} \implies C_j^{\text{slip}} > 0$ (adverse friction drag).
2. **Favorable Buy Execution (Price Improvement):** $s_j = +1$, $P_j^{\text{fill}} < P_j^{\text{arr}} \implies C_j^{\text{slip}} < 0$ (favorable execution).
3. **Adverse Sell Execution:** $s_j = -1$, $P_j^{\text{fill}} < P_j^{\text{arr}} \implies C_j^{\text{slip}} > 0$ (adverse friction drag).
4. **Favorable Sell Execution (Price Improvement):** $s_j = -1$, $P_j^{\text{fill}} > P_j^{\text{arr}} \implies C_j^{\text{slip}} < 0$ (favorable execution).

#### 1.2 Delay and Opportunity Cost Accounting
For unexecuted, deferred, or rejected trade notional $N_j^{\text{unexec}} \ge 0$ (arising from participation rate caps, max scheduling horizon truncation, or liquidity stress rejections), the missed performance cost over the execution interval is:
$$C_j^{\text{opp}} = s_j \cdot N_j^{\text{unexec}} \cdot R_{t, i}$$
where $R_{t, i} = \frac{P_t - P_{t-1}}{P_{t-1}}$ is the asset return over the period.

**Non-Double-Counting Guardrail:**
$C_j^{\text{opp}}$ is classified strictly as an **informational attribution diagnostic**. It is never deducted from cash balances or portfolio equity curves. Cash and equity are debited solely by actual realized friction ($C^{\text{total}}$).

#### 1.3 Basis Points Normalization & Division-by-Zero Safety
For any cost aggregate $C$ and reference notional $N_{\text{ref}}$:
$$C_{\text{bps}} = \begin{cases} 10^4 \cdot \frac{C}{N_{\text{ref}}} & \text{if } N_{\text{ref}} > 0 \\ 0.0 & \text{if } N_{\text{ref}} \le 0 \end{cases}$$
Per-trade basis points are never averaged using simple arithmetic means. All aggregate basis point metrics are strictly **reference-notional weighted**.

#### 1.4 Component Decomposition and Exact Accounting Identity
Total realized execution friction decomposes identically across constituent friction drivers:
$$C_j^{\text{total}} = C_j^{\text{spread}} + C_j^{\text{temp\_impact}} + C_j^{\text{perm\_impact}} + C_j^{\text{comm}} + C_j^{\text{unattributed}}$$

where:
- $C_j^{\text{spread}} = N_j \cdot \frac{\text{spread\_bps}}{2 \times 10^4}$: Spread-crossing half-spread friction.
- $C_j^{\text{temp\_impact}} = N_j \cdot \sigma_i \sqrt{\frac{N_j}{\text{ADV}_i \cdot D_i}}$: Modeled square-root temporary market impact.
- $C_j^{\text{perm\_impact}}$: Permanent impact / post-trade drift (explicitly marked as $0.0$ / `not_modeled_daily_resolution` on daily bars).
- $C_j^{\text{comm}} = N_j \cdot \text{commission\_rate}$: Fixed or linear broker fees.
- $C_j^{\text{unattributed}}$: Accounting residual.

**Reconciliation Invariant:**
$$C^{\text{unattributed}} \equiv C^{\text{observed\_total}} - \sum_k C_k = 0.0$$
The engine verifies that $|C^{\text{unattributed}}| < 10^{-4}$ against the backtest engine's `total_transaction_costs`, ensuring zero double-counting and complete auditability.

---

### 2. Multi-Dimensional Attribution Contract

TCA aggregates are computed deterministically across four orthogonal dimensions:
1. **By Market Regime:** Grouped by filtered regime state $S_k \in \{0, \dots, M-1\}$ at decision time $t_k$.
2. **By Scheduling Mode:** Grouped by execution policy mode (`single_day`, `twap`, `almgren_chriss`).
3. **By Asset:** Grouped by universe asset ticker $i \in \{1, \dots, N\}$.
4. **By Rebalance Event:** Chronological audit trail linking event date, decision date, regime belief state, traded notional, unexecuted notional, fill count, and component breakdown.

---

### 3. Data Provenance & Boundary Disclosure

Because daily bars do not contain sub-minute tick observations or limit order book state, the engine maintains explicit transparency regarding data provenance:
- **`arrival_price_source`**: `"decision_time_bar_close"` (causal close on rebalance day $t_k$).
- **`execution_horizon`**: `"t_to_t_plus_1_close"` (execution realized on trade day $t$).
- **`fill_model`**: `"square_root_temporary_impact"` (Kyle/Almgren-Chriss power-law impact model).
- **`interval_vwap_status`**: `"unavailable_daily_bars"` (explicitly declared unavailable; never fabricated or interpolated).
- **`post_trade_drift_status`**: `"not_modeled_daily_resolution"` (multi-day drift requires tick-level post-trade horizons).
- **`reconciliation_status`**: `"exact_reconciled"`.
- **`causality_verified`**: `true` (decision-time features invariant to future data mutations).

---

### 4. API & Schema Contracts

```typescript
export interface TCACostMetrics {
  total_cost: number;
  total_cost_bps: number;
  spread_cost: number;
  spread_cost_bps: number;
  temporary_impact_cost: number;
  temporary_impact_cost_bps: number;
  permanent_impact_cost: number;
  permanent_impact_cost_bps: number;
  commission_cost: number;
  commission_cost_bps: number;
  realized_slippage: number;
  realized_slippage_bps: number;
  opportunity_cost: number;
  opportunity_cost_bps: number;
  unattributed_residual: number;
  unattributed_residual_bps: number;
  total_traded_notional: number;
  trade_count: number;
}

export interface TCAEventMetrics {
  event_date: string;
  decision_date: string;
  regime_state: number;
  scheduling_mode: string;
  total_cost: number;
  total_cost_bps: number;
  spread_cost: number;
  spread_cost_bps: number;
  temporary_impact: number;
  temporary_impact_bps: number;
  permanent_impact: number;
  permanent_impact_bps: number;
  commission: number;
  commission_bps: number;
  opportunity_cost: number;
  opportunity_cost_bps: number;
  unattributed_residual: number;
  unattributed_residual_bps: number;
  traded_notional: number;
  unexecuted_notional: number;
  fill_count: number;
}

export interface TCAProvenance {
  arrival_price_source: string;
  execution_horizon: string;
  fill_model: string;
  interval_vwap_status: string;
  post_trade_drift_status: string;
  reconciliation_status: string;
  causality_verified: boolean;
}

export interface TCAReport {
  portfolio_summary: TCACostMetrics;
  by_regime: Record<string, TCACostMetrics>;
  by_mode: Record<string, TCACostMetrics>;
  by_asset: Record<string, TCACostMetrics>;
  by_event: TCAEventMetrics[];
  provenance: TCAProvenance;
  reconciled_with_backtest: boolean;
  reconciliation_discrepancy: number;
}
```
