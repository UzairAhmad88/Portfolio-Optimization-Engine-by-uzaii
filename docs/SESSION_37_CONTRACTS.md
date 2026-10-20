# SESSION 37 CONTRACTS: STAGE 28
## Multi-Day Execution Scheduling (TWAP, VWAP & Almgren–Chriss Trajectory Execution)

**Project:** Quant Research Dashboard & Portfolio Optimization Engine  
**Stage:** 28  
**Status:** Implemented, Audited & Verified  
**Date:** October 2026  

---

### 1. Data Contracts & Enums

#### 1.1 Scheduling Mode Enum
```python
class ExecutionSchedulingMode(str, Enum):
    SINGLE_DAY = "single_day"
    TWAP = "twap"
    VWAP = "vwap"
    ALMGREN_CHRISS = "almgren_chriss"
```

Frontend TypeScript definition:
```typescript
export type ExecutionSchedulingMode = 'single_day' | 'twap' | 'vwap' | 'almgren_chriss';
```

#### 1.2 Request Schema Enhancements (`VineBacktestRequest`)
```python
execution_scheduling_mode: ExecutionSchedulingMode = Field(
    default=ExecutionSchedulingMode.SINGLE_DAY,
    description="Multi-day algorithmic execution scheduling: 'single_day', 'twap', 'vwap', 'almgren_chriss'."
)
max_scheduling_days: int = Field(
    default=5,
    ge=1,
    le=20,
    description="Maximum allowed multi-day execution scheduling horizon (D_max)."
)
scheduling_risk_aversion: float = Field(
    default=1e-6,
    ge=0.0,
    description="Risk aversion parameter (lambda) for Almgren-Chriss optimal trajectory execution."
)
```

#### 1.3 Audit Trail Event Enhancements (`VineBacktestRebalanceEvent`)
```python
scheduled_days: Optional[int] = Field(
    default=1,
    description="Total days scheduled for this rebalance order tranche."
)
scheduling_mode: Optional[str] = Field(
    default="single_day",
    description="Active execution scheduling mode."
)
```

#### 1.4 Response Schema Enhancements (`VineBacktestResponse`)
```python
execution_scheduling_mode: Optional[str] = Field(
    default="single_day",
    description="Active execution scheduling mode."
)
max_scheduling_days: Optional[int] = Field(
    default=5,
    description="Configured maximum scheduling days."
)
scheduling_risk_aversion: Optional[float] = Field(
    default=1e-6,
    description="Configured risk aversion parameter for Almgren-Chriss scheduling."
)
```

---

### 2. Mathematical Contracts

#### 2.1 Dynamic Execution Horizon
Given order notional vector $\Delta \mathbf{N}$ (in currency units), point-in-time ADV vector $\mathbf{ADV}$ (in currency units/day), participation cap $\text{PR}_{\max} \in (0, 1]$, and ceiling $D_{\max} \ge 1$:
$$D_i = \min\left(D_{\max}, \max\left(1, \left\lceil \frac{|\Delta N_i|}{\text{ADV}_i \cdot \text{PR}_{\max}} \right\rceil\right)\right) \quad \forall i \in \{1, \dots, N\}$$
$$D = \max_{i=1,\dots,N} D_i$$
Validation Rules:
- If $\text{ADV}_i \le 0$ or $\text{PR}_{\max} \le 0$, raise `ValueError`.
- If $\Delta N_i = 0$, $D_i = 1$.
- $D$ is strictly an integer in $[1, D_{\max}]$.

#### 2.2 Slicing Algorithms
For horizon $D \ge 1$ and trading days $d \in \{1, \dots, D\}$:

1. **TWAP (Uniform Slicing):**
   $$n_{i, d} = \frac{\Delta N_i}{D} \quad \forall d \in \{1, \dots, D-1\}$$
   $$n_{i, D} = \Delta N_i - \sum_{d=1}^{D-1} n_{i, d}$$

2. **VWAP (Volume-Weighted Profile):**
   Using historical day-of-week volume averages $\{v_d\}_{d=1}^D$ strictly from estimation window $[t_k - W, t_k - 1]$ normalized such that $\sum_{d=1}^D v_d = 1.0$:
   $$n_{i, d} = \Delta N_i \cdot v_d \quad \forall d \in \{1, \dots, D-1\}$$
   $$n_{i, D} = \Delta N_i - \sum_{d=1}^{D-1} n_{i, d}$$
   Fallback Rule: If volume data is absent, zero, or non-finite, $v_d = 1/D$ (TWAP).

3. **Almgren–Chriss Optimal Trajectory:**
   Using point-in-time daily return volatility $\sigma_i$ and temporary impact parameter $\eta_i$:
   $$\kappa_i = \operatorname{arccosh}\left(1 + \frac{1}{2} \frac{\lambda \sigma_i^2}{\eta_i}\right)$$
   For remaining target notional $x_i(d) = |\Delta N_i| \cdot \frac{\sinh(\kappa_i (D - d))}{\sinh(\kappa_i D)}$:
   $$n_{i, d} = \operatorname{sign}(\Delta N_i) \cdot [x_i(d - 1) - x_i(d)] \quad \forall d \in \{1, \dots, D-1\}$$
   $$n_{i, D} = \Delta N_i - \sum_{d=1}^{D-1} n_{i, d}$$
   Limiting Behavior: $\lim_{\lambda \to 0} n_{i, d}^{\text{AC}} = n_{i, d}^{\text{TWAP}} = \Delta N_i / D$.

---

### 3. State Machine & Execution Accounting

#### 3.1 Persistent In-Flight Order State
When $D > 1$, day $1$ executes slice $d=1$. Remaining slices for days $d \in \{2, \dots, D\}$ are queued:
$$\text{Queue} = \left[ \{n_{i, 2}\}_{i=1}^N, \{n_{i, 3}\}_{i=1}^N, \dots, \{n_{i, D}\}_{i=1}^N \right]$$

#### 3.2 Daily Execution Lifecycle
For each day $t$:
1. **Pre-trade Valuation & Drift:** Existing positions update with realized daily returns $R_{i, t-1}$:
   $$V_t^{\text{pre}} = \sum_{i=1}^N V_{i, t-1}(1 + R_{i, t-1}) + V_{\text{cash}, t-1}(1 + r_f / 252)$$
   $$w_{i, t}^{\text{pre}} = \frac{V_{i, t-1}(1 + R_{i, t-1})}{V_t^{\text{pre}}}$$
2. **Tranche Identification:** If a rebalance triggers on day $t$, clear any in-flight queue, compute $D$, execute slice $d=1$, and queue slices $2..D$. Otherwise, if queue is non-empty, pop the next daily slice.
3. **Sell Priority:** Sells execute first up to daily volume cap $\text{ADV}_{i, t} \cdot \text{PR}_{\max}$.
4. **Cash Pool & Buy Friction Pre-Allocation (OBS-36-01):**
   $$V_{\text{cash, avail}} = w_{t, \text{cash}}^{\text{pre}} V_t^{\text{pre}} + \text{NetSellProceeds}$$
   $$\text{TotalBuyDemand} = \sum_{j \in \text{Buys}} \Delta N_{j, t}^{\text{capped}} \cdot (1 + f_{j, \text{est}})$$
   $$\psi = \min\left(1.0, \frac{V_{\text{cash, avail}}}{\max(10^{-6}, \text{TotalBuyDemand})}\right)$$
   $$\Delta N_{j, t}^{\text{exec}} = \psi \cdot \Delta N_{j, t}^{\text{capped}}$$
5. **Post-Trade Reconciliation:**
   $$V_{\text{cash}, t} = V_{\text{cash, avail}} - \sum_{j \in \text{Buys}} \Delta N_{j, t}^{\text{exec}} - \text{TotalBuyFriction} \ge 0.0$$
   $$\sum_{i=1}^N w_{i, t}^{\text{exec}} + w_{t, \text{cash}}^{\text{exec}} \equiv 1.0$$

#### 3.3 Conflict Policy
If rebalance date $t_{k+1}$ arrives while queue from $t_k$ is still active ($t_{k+1} < t_k + D$):
- In-flight pending slices are cancelled immediately.
- Optimization targets $w_{t_{k+1}}^*$ are compared against current drifted holdings $w_{t_{k+1}}^{\text{pre}}$.
- New execution horizon $D_{\text{new}}$ and slices are generated afresh.
- Zero duplicate execution or phantom orders.
