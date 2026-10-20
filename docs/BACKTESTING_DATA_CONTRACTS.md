# Backtesting Data Contracts & Financial Simulation Accounting
**Document Version:** 1.0.0  
**Status:** Approved Simulation Accounting Baseline  
**Date:** 2026-10-17  
**Engine Release Version:** v0.8.0  
**Author:** Senior Quantitative Research Engineer, Financial Mathematics Specialist & Backtesting Systems Architect  

---

## 1. Executive Scope & Objective

The **Backtesting Engine** simulates how a quantitative portfolio strategy would have performed over historical market observations under defined investment constraints, rebalancing rules, transaction costs, and slippage frictions.

The simulation answers:
> **"How would this strategy have performed under the specified historical data, rebalancing rules, and trading-cost assumptions?"**

The engine provides reproducible, audit-traceable historical simulations for research and decision support. It does not predict future performance or guarantee investment results.

---

## 2. Price Series Selection & Adjustment Policy

### 2.1 Authoritative Price Field
1. **Primary Field:** For all return calculations and portfolio valuations, `adjusted_close` is the authoritative price field when present and strictly positive ($P > 0.0$).
2. **Fallback Field:** If `adjusted_close` is absent or null for an asset, the system falls back to raw `close` and records an explicit audit warning:
   > *"Unadjusted close used for asset {ticker}; returns may not account for historical stock splits or cash dividends."*
3. **Consistency Rule:** Price series selection is evaluated per asset. If unadjusted close is used, it is flagged in the backtest result metadata.
4. **Invalid Prices:** Non-positive prices ($P \le 0.0$), `NaN`, and infinite values are strictly rejected prior to simulation.

### 2.2 Date Alignment Policy (Multi-Asset Synchronization)
- Multi-asset historical simulations require synchronized price panels.
- **Default Policy (Intersection):** The simulation is conducted on the inner join of trading dates where all selected assets have valid price observations:
  $$\mathcal{D}_{\text{sim}} = \bigcap_{i=1}^N \mathcal{D}_i$$
- This guarantees no synthetic zero-returns or artificial holiday fills.
- When $M$ assets have differing holidays (e.g. US vs. PSX), the effective simulation period consists of shared market sessions. Cross-currency portfolios remain restricted unless explicit FX conversion series are provided.

---

## 3. Return Conventions & Wealth Compounding

### 3.1 Discrete Simple Returns
Asset returns are computed using arithmetic simple returns:
$$r_{i, t} = \frac{P_{i, t} - P_{i, t-1}}{P_{i, t-1}}$$
where $P_{i, t}$ is the authoritative price of asset $i$ on trading day $t$.

### 3.2 Discrete Portfolio Return
On any trading day $t$ without rebalancing friction:
$$R_{p, t}^{\text{gross}} = \sum_{i=1}^N w_{i, t-1} \cdot r_{i, t}$$
where $w_{i, t-1}$ is the weight of asset $i$ held at the close of day $t-1$ (beginning of day $t$).

### 3.3 True Multiplicative Wealth Compounding
Portfolio wealth compounds multiplicatively over time. **Returns are NEVER summed linearly across time**:
$$V_t^{\text{gross}} = V_{t-1} \cdot (1 + R_{p, t}^{\text{gross}})$$
$$V_t^{\text{net}} = V_{t-1}^{\text{net}} \cdot (1 + R_{p, t}^{\text{net}})$$

At the end of period $T$:
$$V_T = V_0 \prod_{t=1}^T (1 + R_{p, t}^{\text{net}})$$
$$\text{Cumulative Return} = \frac{V_T - V_0}{V_0} = \prod_{t=1}^T (1 + R_{p, t}^{\text{net}}) - 1$$

---

## 4. Initial Capital & Allocation Mechanics

1. **Initial Capital ($V_0$):**
   - Configurable positive float: $V_0 > 0.0$ (standard default: $\$100,000.00$).
2. **Day 0 Allocation:**
   - At the inception of the backtest ($t=0$), capital is fully allocated to target asset weights $w_{0} = [w_{1, 0}, \dots, w_{N, 0}]^T$.
   - Initial transaction costs and slippage are computed based on the initial allocation notional:
     $$\text{Initial Traded Notional} = V_0 \sum_{i=1}^N w_{i, 0} = V_0$$
   - Net initial portfolio value after day-0 implementation friction:
     $$V_0^{\text{net}} = V_0 - (\text{Initial Traded Notional} \times (\text{fee\_rate} + \text{slippage\_rate}))$$

---

## 5. Holdings, Weight Drift & Rebalancing Accounting

### 5.1 Drift Between Rebalance Events
Between scheduled rebalancing events, asset dollar holdings grow or shrink according to each asset's realized return:
$$H_{i, t} = H_{i, t-1} \cdot (1 + r_{i, t})$$
$$V_t = \sum_{i=1}^N H_{i, t}$$

The portfolio weights drift naturally according to asset performance:
$$w_{i, t} = \frac{H_{i, t}}{V_t} = \frac{w_{i, t-1}(1 + r_{i, t})}{\sum_{j=1}^N w_{j, t-1}(1 + r_{j, t})}$$

### 5.2 Rebalancing Execution & Turnover
At a rebalancing date $t_{\text{reb}}$:
1. **Pre-Rebalance State:** Current market value $V_{\text{pre}}$ and current drifted weights $\mathbf{w}_{\text{pre}}$.
2. **Target State:** Desired target weights $\mathbf{w}_{\text{target}}$ determined by strategy.
3. **Weight Difference:** $\Delta w_i = w_{\text{target}, i} - w_{\text{pre}, i}$.
4. **Traded Notional per Asset:**
   $$\Delta H_i = |\Delta w_i| \cdot V_{\text{pre}}$$
5. **Total Traded Notional:**
   $$\text{Traded Notional} = \sum_{i=1}^N \Delta H_i = V_{\text{pre}} \sum_{i=1}^N |w_{\text{target}, i} - w_{\text{pre}, i}|$$
6. **Portfolio Turnover ($\tau$):** Standard two-sided turnover convention:
   $$\tau = \frac{1}{2} \sum_{i=1}^N |w_{\text{target}, i} - w_{\text{pre}, i}| = \frac{\text{Traded Notional}}{2 \cdot V_{\text{pre}}}$$

---

## 6. Transaction Cost & Slippage Conventions

### 6.1 Transaction Cost (Commission / Brokerage Fees)
- Configurable basis points: $\text{bps}_{\text{fee}} \ge 0.0$ (e.g. 10.0 bps = 0.0010 = 0.10%).
- Applied proportionally to total traded notional:
  $$C_{\text{trans}} = \text{Traded Notional} \times \frac{\text{bps}_{\text{fee}}}{10,000}$$

### 6.2 Slippage (Execution Drag / Market Impact Proxy)
- Configurable basis points: $\text{bps}_{\text{slip}} \ge 0.0$ (e.g. 5.0 bps = 0.0005 = 0.05%).
- Models adverse execution price deviation relative to benchmark closing price:
  $$C_{\text{slip}} = \text{Traded Notional} \times \frac{\text{bps}_{\text{slip}}}{10,000}$$

### 6.3 Friction Deduction
Total friction cost is deducted from portfolio equity at the rebalance timestamp:
$$\text{Total Friction} = C_{\text{trans}} + C_{\text{slip}}$$
$$V_{\text{post}} = V_{\text{pre}} - \text{Total Friction}$$

Post-rebalance asset holdings are re-established at target weights on $V_{\text{post}}$:
$$H_{i, \text{post}} = w_{\text{target}, i} \cdot V_{\text{post}}$$

---

## 7. Rebalancing Schedules & Signal / Execution Timing

### 7.1 Supported Rebalance Schedules
1. **`buy_and_hold`:** No rebalancing after day 0. Weights drift freely with market prices.
2. **`daily`:** Rebalanced every active trading day.
3. **`weekly`:** Rebalanced on the first trading day of each calendar week (or every 5 trading days).
4. **`monthly`:** Rebalanced on the first trading day of each calendar month (or every 21 trading days).
5. **`quarterly`:** Rebalanced on the first trading day of each calendar quarter (or every 63 trading days).

### 7.2 Look-Ahead Bias Prevention & Execution Timing
To prevent look-ahead bias and unrealistic execution assumptions:
- **Signal Generation:** Strategy parameters, return estimates, covariance matrices, and target weights are determined strictly using prices available up to the close of day $t-1$.
- **Execution Timing:** Rebalancing trades are executed at the opening or close of day $t$ before day $t$'s subsequent price movement.
- **In-Sample / Out-of-Sample Separation:** For walk-forward optimization, the estimation/training window $[\tau - W_{\text{train}}, \tau - 1]$ strictly precedes the out-of-sample rebalance evaluation date $\tau$. Zero future observations enter the covariance matrix or optimization objective.

---

## 8. Walk-Forward Simulation Architecture

### 8.1 Chronological Rolling Window Protocol
```
Time Index: ------------------------------------------------------------------------>
Window 1:  [ Training Window: T_0 to T_k-1 ] => Solve w_1 => [ Test Window 1: T_k to T_k+m ]
Window 2:         [ Training Window: T_m to T_k+m-1 ] => Solve w_2 => [ Test Window 2 ]
Window 3:                [ Training Window: T_2m to T_k+2m-1 ] => Solve w_3 => [ Test 3 ]
```
1. **Training Window ($W_{\text{train}}$):** Number of historical trading days used to estimate expected returns and covariance (e.g. 126 or 252 days).
2. **Test Window ($W_{\text{test}}$):** Rebalance horizon during which weights remain frozen (e.g. 21 days for monthly rebalancing).
3. **Optimizers Supported:**
   - Minimum Variance: $\min_\mathbf{w} \mathbf{w}^T \mathbf{\Sigma} \mathbf{w}$
   - Maximum Sharpe: $\max_\mathbf{w} \frac{\mathbf{w}^T \mathbf{\mu} - R_f}{\sqrt{\mathbf{w}^T \mathbf{\Sigma} \mathbf{w}}}$
   - Equal Weight: $w_i = 1/N$
   - Target Weights: User-specified constant asset targets
4. **Infeasible Optimization Fallback:** If the numerical optimizer fails to converge in an expanding or rolling window, the engine holds the previous window's weights or falls back to equal weight, logging a diagnostic warning in `rebalance_events`.

---

## 9. Performance & Risk Analytics Definitions

| Metric | Mathematical Definition | Annualization Factor |
|---|---|---|
| **Initial Value ($V_0$)** | Starting capital | N/A |
| **Final Value ($V_T$)** | Ending portfolio equity net of all frictions | N/A |
| **Cumulative Return ($R_{\text{cum}}$)** | $\frac{V_T - V_0}{V_0} = \prod_{t=1}^T (1 + R_{p, t}) - 1$ | N/A |
| **Annualized Return (CAGR)** | $(1 + R_{\text{cum}})^{\frac{N_{\text{ann}}}{T}} - 1$ | $N_{\text{ann}} = 252$ (US) or $250$ (PSX) |
| **Arithmetic Annual Return** | $\text{mean}(R_{p, t}) \times N_{\text{ann}}$ | $N_{\text{ann}}$ |
| **Annualized Volatility ($\sigma_{\text{ann}}$)** | $\text{std}(R_{p, t}, \text{ddof}=1) \times \sqrt{N_{\text{ann}}}$ | $\sqrt{N_{\text{ann}}}$ |
| **Sharpe Ratio** | $\frac{\text{CAGR} - R_f}{\sigma_{\text{ann}}}$ | $N_{\text{ann}}$ |
| **Sortino Ratio** | $\frac{\text{CAGR} - \text{MAR}}{\text{Downside Deviation}_{\text{ann}}}$ | $N_{\text{ann}}$ |
| **Maximum Drawdown (MDD)** | $\min_{t} \left( \frac{V_t - \max_{s \le t} V_s}{\max_{s \le t} V_s} \right)$ | N/A (Expressed as negative percentage) |
| **Total Turnover** | $\sum_{\text{events}} \tau_k$ | Total portfolio turnover across all rebalances |
| **Total Friction Cost** | $\sum_{\text{events}} (C_{\text{trans}, k} + C_{\text{slip}, k})$ | Absolute currency amount |

---

## 10. Numerical Tolerances & Boundary Invariants

- **Weight Equality Tolerance:** $\left| \sum_{i=1}^N w_i - 1.0 \right| \le 1.0 \times 10^{-5}$.
- **Long-Only Bounds:** $\forall i, w_i \ge -1.0 \times 10^{-7}$ (clamped to 0.0).
- **Portfolio Value Invariant:** If all asset prices are positive and total friction $< V_t$, $V_t$ must remain strictly positive ($V_t > 0.0$).
- **Zero Cost Equivalence:** When $\text{bps}_{\text{fee}} = 0.0$ and $\text{bps}_{\text{slip}} = 0.0$, Net Return bitwise reconciles with Gross Return: $R_{p, t}^{\text{net}} \equiv R_{p, t}^{\text{gross}}$.
