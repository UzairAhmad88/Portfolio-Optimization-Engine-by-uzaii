# SESSION 32 CONTRACTS — DYNAMIC WALK-FORWARD VINE TAIL RISK PARITY BACKTESTING

**Document Version:** 1.0.0  
**Status:** Approved Mathematical & Architectural Contract  
**Roadmap Stage:** Stage 24  
**Date:** 2026-10-19  

---

## 1. Overview & Objectives

This document establishes the exact mathematical, temporal, portfolio accounting, and API contracts for the **Dynamic Walk-Forward Vine Tail Risk Parity Backtesting Engine**.

The engine evaluates dynamic C-Vine and D-Vine Tail Risk Parity (TRP) strategies over historical out-of-sample periods, enforcing strict chronological separation between training data and realized evaluation returns.

---

## 2. Chronological Decision Protocol & Data Contracts

### 2.1 Return & Price Observation Convention
- **Data Source:** Aligned daily closing prices $P_{t, i}$ for asset $i \in \{1, \dots, d\}$ on date $t \in \{1, \dots, T\}$.
- **Return Definition:** Discrete simple percentage returns:
  $$R_{t, i} = \frac{P_{t, i} - P_{t-1, i}}{P_{t-1, i}}$$
- **Missing Value & Alignment Policy:** Only dates where all selected assets possess valid, strictly positive closing prices are included. Duplicate timestamps are rejected during validation.

### 2.2 Rolling Estimation Window Semantics (Zero Look-Ahead Rule)
Let $t_k$ denote the $k$-th rebalance decision date.
- **Estimation Lookback Window ($\mathcal{W}_k$):**
  $$\mathcal{W}_k = \{ R_\tau \mid \tau \in [t_k - W, t_k - 1] \}$$
  where $W \ge 30$ is the user-configured `estimation_window` in trading days.
- **Strict Causality Invariant:**
  Under no circumstances may $R_{t_k}$ or any future return $\tau \ge t_k$ enter:
  1. The marginal distribution estimation or empirical pseudo-observations $\hat{u}_i$.
  2. The pairwise copula family selection or maximum-likelihood parameter estimation.
  3. The C-Vine or D-Vine tree structures and conditional transformations.
  4. The Monte Carlo scenario simulations.
  5. The Tail Risk Parity optimization.

---

## 3. Dynamic Vine Estimation & Simulation

At each rebalance date $t_k$:
1. **Marginal Transformation:**
   Using strictly $\mathcal{W}_k$, compute pseudo-observations $U_{\mathcal{W}_k}$ via:
   - Empirical ranking: $\hat{u}_{t, i} = \frac{\operatorname{rank}(R_{t, i})}{W + 1}$, or
   - Parametric Student-t marginals fitted on $\mathcal{W}_k$.
2. **Vine Decomposition:**
   Fit selected vine topology:
   - **C-Vine:** Star-pivot tree decomposition via greedy sum of absolute Kendall's $\tau$ on Tree 1.
   - **D-Vine:** Path tree decomposition with left-right conditional distribution tracking ($L[(k, j)]$ and $R[(k, i)]$).
   - Pair-copula families: AIC-selected among Gaussian, Student-t, Clayton, Gumbel (using vectorized safeguarded Newton $h$-inversion), and Independence.
3. **Scenario Simulation:**
   Simulate $M$ independent uniform variates and propagate through inverse $h$-functions to produce uniform scenarios $U_{\text{sim}} \in (0, 1)^{M \times d}$.
4. **Return Space Inversion:**
   Invert $U_{\text{sim}}$ into return space $R_{\text{sim}} \in \mathbb{R}^{M \times d}$ using marginal quantiles derived strictly from $\mathcal{W}_k$.

---

## 4. Tail Risk Parity Optimization Contract

### 4.1 Loss & Tail Risk Conventions
- **Portfolio Loss:** $L_p(w) = -R_{\text{sim}} w$.
- **Value-at-Risk ($\text{VaR}_\alpha$):**
  $$\text{VaR}_\alpha(w) = \text{Quantile}_\alpha(L_p(w))$$
- **Conditional Value-at-Risk ($\text{CVaR}_\alpha$):**
  $$\text{CVaR}_\alpha(w) = \mathbb{E}[L_p(w) \mid L_p(w) \ge \text{VaR}_\alpha(w)]$$
- **Euler Tail Risk Contribution ($\text{TRC}_i$):**
  $$\text{TRC}_i(w) = -w_i \mathbb{E}[R_{\text{sim}, :, i} \mid L_p(w) \ge \text{VaR}_\alpha(w)]$$
- **Exact Additive Identity:**
  $$\sum_{i=1}^d \text{TRC}_i(w) \equiv \text{CVaR}_\alpha(w)$$

### 4.2 Optimization Formulation
Find $w^* \in \mathbb{R}^d$ minimizing the squared relative dispersion of tail risk contributions:
$$\min_{w} \sum_{i=1}^d \left( \frac{\text{TRC}_i(w)}{\sum_{j=1}^d \text{TRC}_j(w)} - \frac{1}{d} \right)^2$$
subject to:
$$\sum_{i=1}^d w_i = 1.0, \quad w_i \ge 0 \quad (\forall i \in \{1, \dots, d\})$$

---

## 5. Portfolio Accounting, Drift & Transaction Costs

### 5.1 Weight Drift Between Rebalances
When asset returns $R_{t, i}$ are realized on non-rebalance days, portfolio weights drift:
$$w_{t+1, i}^{\text{pre}} = \frac{w_{t, i}(1 + R_{t, i})}{1 + R_{p, t}^{\text{gross}}}, \quad \text{where } R_{p, t}^{\text{gross}} = \sum_{i=1}^d w_{t, i} R_{t, i}$$

### 5.2 Turnover & Friction Calculation
At rebalance date $t_k$ from pre-trade drifted weights $w_{t_k}^{\text{pre}}$ to target weights $w_{t_k}^*$:
- **One-Way Turnover:**
  $$\text{Turnover}_{t_k} = \frac{1}{2} \sum_{i=1}^d |w_{t_k, i}^* - w_{t_k, i}^{\text{pre}}|$$
- **Total Friction Rate:**
  $$\phi = \frac{\text{transaction\_cost\_bps} + \text{slippage\_bps}}{10,000}$$
- **Transaction Cost Incurred:**
  $$C_{t_k} = 2 \cdot \text{Turnover}_{t_k} \cdot V_{t_k}^{\text{pre}} \cdot \phi$$
- **Post-Rebalance Equity:**
  $$V_{t_k}^{\text{post}} = V_{t_k}^{\text{pre}} - C_{t_k}$$

### 5.3 Net Return Compounding
Daily portfolio equity compounds sequentially:
$$V_{t} = V_{t-1} (1 + R_{p, t}^{\text{net}})$$
where $R_{p, t}^{\text{net}} = R_{p, t}^{\text{gross}} - \frac{C_t}{V_{t-1}}$ on rebalance dates, and $R_{p, t}^{\text{net}} = R_{p, t}^{\text{gross}}$ on non-rebalance dates.

---

## 6. Baseline Benchmark Strategies

Every backtest execution includes simultaneous out-of-sample simulation for:
1. **Equal-Weight (1/N):** $w_i = 1/d$, rebalanced on the same schedule with identical turnover and friction accounting.
2. **Static Vine Tail Risk Parity:** Optimized once on the initial training window $\mathcal{W}_0$; held without re-estimation, drifting with historical returns.
3. **Dynamic Vine Tail Risk Parity:** Actively re-estimated at each rebalance period.

---

## 7. API Request & Response Contracts

**Endpoint:** `POST /api/v1/copula/vine/backtest`  
**Authentication:** Required (`HTTPBearer` or session cookie)  
**Tenant Isolation:** `check_dataset_access` strictly enforced.

### 7.1 Request Schema (`VineBacktestRequest`)
```json
{
  "dataset_id": "string (UUID)",
  "vine_type": "c_vine | d_vine",
  "estimation_window": "integer (>= 30, default: 60)",
  "rebalance_frequency": "daily | weekly | biweekly | monthly | quarterly",
  "num_simulations": "integer (1000 - 20000, default: 2000)",
  "confidence_level": "float (0.90 - 0.999, default: 0.99)",
  "marginal_method": "empirical | student_t",
  "transaction_cost_bps": "float (>= 0.0, default: 10.0)",
  "slippage_bps": "float (>= 0.0, default: 5.0)",
  "initial_capital": "float (> 0.0, default: 100000.0)",
  "risk_free_rate": "float (default: 0.02)",
  "random_seed": "integer (default: 42)",
  "tickers": ["optional list of asset tickers"]
}
```

### 7.2 Response Schema (`VineBacktestResponse`)
Exposes:
- `dataset_id`, `vine_type`, `evaluation_start_date`, `evaluation_end_date`, `rebalance_count`.
- `strategy_metrics` vs `benchmark_metrics` (Equal-Weight) vs `static_trp_metrics`: Total Return, CAGR, Annualized Volatility, Sharpe Ratio, Max Drawdown, Historical VaR/CVaR, Total Turnover, Total Costs.
- `equity_curve`: Time series of date, strategy_equity, benchmark_equity, static_trp_equity, drawdown.
- `rebalance_history`: Chronological audit trail of rebalance events, target weights, turnover, costs, and solver diagnostics.
