# SESSION 36 CONTRACTS: STAGE 28 SPECIFICATION
## Multi-Day Execution Scheduling (TWAP / VWAP / Almgren-Chriss Trajectory Execution in Dynamic Backtesting)

**Project:** Quant Research Dashboard & Portfolio Optimization Engine  
**Stage:** 28  
**Prerequisite:** Stage 27 — Queue-Based Cash-Financed Execution & Unified Out-of-Sample Liquidation Loss Distribution  
**Mode:** Architecture Specification, Mathematical Formulation, API Contracts & Implementation Plan  
**Status:** Approved by Project Owner; Ready for Implementation

---

### 1. Executive Summary & Objective

In Stage 27, when portfolio rebalancing orders exceed daily volume participation limits under the `cap` policy, sell orders are capped at $\text{ADV}_i \cdot H \cdot \text{PR}_{\max}$ and residual unexecuted order notional is retained in pre-trade holdings, while buy orders are funded up to available cash.

In institutional portfolio management, large rebalance orders are not simply abandoned on day 1. Instead, executing brokers and quant trading desks utilize **Multi-Day Algorithmic Execution Scheduling**:
1. When an intended rebalance order $\Delta N_i$ exceeds the single-day volume participation cap $\text{ADV}_i \cdot \text{PR}_{\max}$, an execution schedule spans multiple consecutive trading days:
   $$D_i = \min\left(D_{\max}, \max\left(1, \left\lceil \frac{|\Delta N_i|}{\text{ADV}_i \cdot \text{PR}_{\max}} \right\rceil\right)\right)$$
2. Slicing algorithms determine daily execution tranches over the multi-day horizon $D = \max_i D_i$:
   - **Single-Day:** Baseline Stage 27 behavior (immediate execution up to cap, residual abandoned).
   - **TWAP (Time-Weighted Average Price):** Uniform daily slicing across $D$ days.
   - **VWAP (Volume-Weighted Average Price):** Volume-weighted daily slicing based on projected ADV profiles.
   - **Almgren-Chriss Optimal Trajectory:** Non-linear optimal trajectory minimizing expected market impact and volatility risk under parameter $\lambda$.
3. The dynamic walk-forward backtest engine executes tranches day-by-day:
   - On each day $t \in [t_k, t_k + D - 1]$, that day's scheduled sell tranches execute first, net sell proceeds fund scheduled buy tranches, and execution friction is deducted.
   - Both held positions and pending in-flight orders evolve dynamically as market prices drift and cash accrues interest.
   - Pre-allocates buy transaction costs into the cash availability pool, fully remediating **OBS-36-01**.

---

### 2. Mathematical Formulation & Accounting Invariants

#### 2.1 Multi-Day Execution Horizon Determination
Let $t_k$ be a rebalance decision date with portfolio equity $V_{t_k}$, drifted asset weights $w_{t_k}^{\text{pre}}$, and target weights $w_{t_k}^*$.  
The required trade notional for asset $i$ is:
$$\Delta N_i = (w_{t_k, i}^* - w_{t_k, i}^{\text{pre}}) \cdot V_{t_k}$$

For a maximum daily volume participation rate $\text{PR}_{\max} \in (0, 1]$ and point-in-time Average Daily Volume $\text{ADV}_{i, t_k}$, the maximum executable single-day notional is $\text{VolCap}_{i, t_k} = \text{ADV}_{i, t_k} \cdot \text{PR}_{\max}$.

If $|\Delta N_i| > \text{VolCap}_{i, t_k}$ and multi-day scheduling is enabled, the required trading days for asset $i$ is:
$$D_i = \min\left(D_{\max}, \max\left(1, \left\lceil \frac{|\Delta N_i|}{\text{VolCap}_{i, t_k}} \right\rceil\right)\right)$$
where $D_{\max} \in [1, 20]$ is the maximum allowable scheduling horizon. The portfolio-level execution window is:
$$D = \max_{i=1,\dots,N} D_i$$

#### 2.2 Slicing Trajectory Formulation

For an order $\Delta N_i$ scheduled across $D$ trading days $d \in \{1, 2, \dots, D\}$:

1. **TWAP (Uniform Slicing):**
   $$n_{i, d}^{\text{TWAP}} = \frac{\Delta N_i}{D} \quad \forall d \in \{1, \dots, D\}$$

2. **VWAP (Volume-Weighted Slicing):**
   Let $v_d$ be the relative volume expectation for trading day $d$ (default: uniform or historical day-of-week profile $\sum_{d=1}^D v_d = 1.0$):
   $$n_{i, d}^{\text{VWAP}} = \Delta N_i \cdot v_d$$

3. **Almgren-Chriss Optimal Trajectory:**
   Using the Almgren-Chriss (2000) framework with daily volatility $\sigma_i$, daily volume $\text{ADV}_i$, temporary impact $\eta_i$, permanent impact $\gamma_i$, and risk aversion $\lambda$:
   $$\kappa_i = \frac{1}{\tau} \operatorname{arccosh}\left(1 + \frac{1}{2} \frac{\lambda \sigma_i^2 \tau^2}{\eta_i}\right)$$
   For daily discretization ($\tau = 1$ day, total horizon $T = D$ days), the remaining target notional at the end of day $d$ is:
   $$x_i(d) = |\Delta N_i| \cdot \frac{\sinh(\kappa_i (D - d))}{\sinh(\kappa_i D)}$$
   The scheduled execution slice for day $d$ is:
   $$n_{i, d}^{\text{AC}} = \operatorname{sign}(\Delta N_i) \cdot [x_i(d - 1) - x_i(d)]$$
   As $\lambda \to 0$, $\kappa_i \to 0$, and $n_{i, d}^{\text{AC}}$ converges continuously to $n_{i, d}^{\text{TWAP}} = \frac{\Delta N_i}{D}$.

#### 2.3 Daily In-Flight Queue Execution & Cash Accounting
On each day $t = t_k + d - 1$ for $d = 1, \dots, D$:
1. **Sell Tranches First:**
   For all assets with scheduled sales ($n_{i, d} < 0$):
   $$\Delta N_{i, t}^{\text{exec, sell}} = \min(|n_{i, d}|, \text{ADV}_{i, t} \cdot \text{PR}_{\max})$$
   Realized sell friction $\text{Cost}_{i, t}^{\text{sell}}$ is computed using that day's point-in-time market impact and spread.
2. **Available Cash Pool with Buy Fee Pre-Allocation (Resolving OBS-36-01):**
   $$V_{\text{cash, avail}, t} = \max\left(0, w_{\text{cash}, t}^{\text{pre}} V_t + \sum_{i \in \text{Sells}} \Delta N_{i, t}^{\text{exec, sell}} - \sum_{i \in \text{Sells}} \text{Cost}_{i, t}^{\text{sell}}\right)$$
   Estimated buy friction rate $f_{\text{est}} \approx \text{Spread}_{\text{half}} + \text{Impact}_{\text{est}} + \text{Commission}$.  
   The buy cash financing ratio strictly reserves buy fees:
   $$\psi_t = \min\left(1.0, \frac{V_{\text{cash, avail}, t}}{\sum_{j \in \text{Buys}} n_{j, d}^{\text{capped}} \cdot (1 + f_{\text{est}})}\right)$$
3. **Buy Tranches Executed:**
   $$\Delta N_{j, t}^{\text{exec, buy}} = \min(n_{j, d}, \text{ADV}_{j, t} \cdot \text{PR}_{\max}) \cdot \psi_t$$
4. **Holdings & Budget Invariant:**
   $$w_{i, t}^{\text{post}} = w_{i, t}^{\text{pre}} + \frac{\Delta N_{i, t}^{\text{exec, buy}} - \Delta N_{i, t}^{\text{exec, sell}}}{V_t}$$
   $$\sum_{i=1}^N w_{i, t}^{\text{post}} + w_{\text{cash}, t}^{\text{post}} \equiv 1.0$$
5. **Drift & Accrual on Interim Days:**
   Between execution tranches ($t \to t + 1$), holdings drift with daily simple returns $R_{i, t+1}$, uninvested cash earns daily risk-free interest $r_f / 252$, and portfolio equity updates net of that day's trading friction.

#### 2.4 Rebalance Conflict Resolution
If a scheduled rebalance arrives at $t_{k+1}$ while an in-flight execution trajectory is still active ($t_{k+1} < t_k + D$):
- Any unfinished pending tranches from $t_k$ are cancelled.
- The new optimization at $t_{k+1}$ takes the actual realized drifted holdings at $t_{k+1}$ as its initial pre-trade state $w_{t_{k+1}}^{\text{pre}}$.
- A new execution schedule is generated for $w_{t_{k+1}}^* - w_{t_{k+1}}^{\text{pre}}$.
- Guarantees zero phantom orders, zero double execution, and strict state consistency.

---

### 3. API Request & Response Contracts

#### 3.1 Pydantic Model Updates in `backend/app/copula/models.py`

```python
class VineBacktestRequest(BaseModel):
    # Existing fields preserved...
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    estimation_window: int = Field(default=252, ge=30, le=1260)
    rebalance_frequency: Literal["daily", "weekly", "monthly", "quarterly"] = "monthly"
    # Stage 25 & 26 fields preserved...
    execution_model: Literal["fixed_bps", "linear", "square_root"] = "square_root"
    bid_ask_spread_bps: float = Field(default=5.0, ge=0.0, le=1000.0)
    max_participation_rate: float = Field(default=0.10, ge=0.001, le=1.0)
    participation_policy: Literal["warn", "cap", "reject"] = "warn"
    execution_horizon_days: float = Field(default=1.0, ge=0.1, le=20.0)
    enable_endogenous_liquidity: bool = True
    spread_stress_sensitivity: float = Field(default=5.0, ge=0.0, le=50.0)
    adv_stress_sensitivity: float = Field(default=5.0, ge=0.0, le=50.0)
    
    # NEW Stage 28 Multi-Day Scheduling Fields:
    execution_scheduling_mode: Literal["single_day", "twap", "vwap", "almgren_chriss"] = "single_day"
    max_scheduling_days: int = Field(default=5, ge=1, le=20)
    scheduling_risk_aversion: float = Field(default=1e-6, ge=0.0, le=1.0)
```

```python
class VineBacktestRebalanceEvent(BaseModel):
    # Existing fields preserved...
    rebalance_index: int
    date: str
    requested_weights: dict[str, float] | None = None
    executed_weights: dict[str, float] | None = None
    weights: dict[str, float]
    # NEW Stage 28 Scheduling Fields:
    scheduled_days: int = 1
    scheduling_mode: str = "single_day"
    daily_tranches_executed: list[dict[str, Any]] | None = None
```

```python
class VineBacktestResponse(BaseModel):
    # Existing fields preserved...
    execution_scheduling_mode: str = "single_day"
    max_scheduling_days: int = 5
    scheduling_risk_aversion: float = 1e-6
    # Metrics and curves preserved...
```

---

### 4. Acceptance Criteria & Test Strategy

1. **Exact Backward Compatibility:**
   `execution_scheduling_mode="single_day"` must produce numerical results identical to Stage 27 across all metrics to $< 10^{-12}$ precision.
2. **TWAP Slicing Exactness:**
   For an order $\Delta N_i$ scheduled across $D$ days, $\sum_{d=1}^D n_{i, d}^{\text{TWAP}} \equiv \Delta N_i$ within float tolerance ($< 10^{-10}$).
3. **Almgren-Chriss Limiting Convergence:**
   As $\lambda \to 0$, $n_{i, d}^{\text{AC}} \to n_{i, d}^{\text{TWAP}}$ with max difference $< 10^{-6}$.
4. **Participation Rate Compliance:**
   Daily executed notional for each tranche must satisfy $\Delta N_{i, t}^{\text{exec}} \le \text{ADV}_{i, t} \cdot \text{PR}_{\max}$ within tolerance.
5. **Cash & Holdings Conservation Invariant:**
   On every trading day during multi-day execution, $\sum_{i=1}^N w_{i, t} + w_{\text{cash}, t} \equiv 1.0$ and $w_{\text{cash}, t} \ge 0.0$ hold strictly.
6. **Temporal Anti-Lookahead Invariance:**
   Multi-day execution schedules and day $t$ fills must rely solely on information up to day $t$; future volume or price shocks on day $t+1$ must not affect day $t$ decisions.
7. **Zero Regression:**
   All 431 existing backend tests and 42 frontend tests must pass cleanly.
