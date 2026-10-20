# SESSION 39 CONTRACTS & SPECIFICATIONS: STAGE 29
## Regime-Aware Execution Dynamics (Adaptive Multi-Day Scheduling)

**Document:** Formal Mathematical & Architectural Specifications  
**Session:** 39  
**Stage:** 29 — Option 1: Regime-Aware Execution Dynamics  
**Status:** Active Production Contract  

---

### 1. Mathematical Formulation

#### 1.1 Regime Model Contract
Let the market index return series across $N$ universe assets at time $\tau$ be:
$$r_{m, \tau} = \frac{1}{N} \sum_{i=1}^N R_{\tau, i}$$
The regime belief state is governed by an $M$-state discrete-time Hidden Markov Model with Gaussian emissions:
$$S_\tau \in \{0, 1, \dots, M-1\}, \quad M \in [2, 5]$$
$$r_{m, \tau} \mid S_\tau = k \sim \mathcal{N}(\mu_k, \Sigma_k)$$

**Deterministic State Ordering Invariant:**
States are uniquely and monotonically indexed by covariance trace:
$$\text{Tr}(\Sigma_0) < \text{Tr}(\Sigma_1) < \dots < \text{Tr}(\Sigma_{M-1})$$
- State 0: Lowest volatility (Calm regime)
- State $M-1$: Highest volatility (Turbulent/Crisis regime)

#### 1.2 Causal State Filtering
At decision timestamp $t_k$, using historical returns strictly within the causal estimation window $[t_k - W, t_k - 1]$:
$$\hat{\alpha}_{t_k - 1}(m) = P(S_{t_k - 1} = m \mid r_{m, t_k - W : t_k - 1})$$
The turbulence belief probability is:
$$p_{\text{turbulent}} = \hat{\alpha}_{t_k - 1}(M - 1) \in [0.0, 1.0]$$
The dominant regime state is:
$$s^* = \arg\max_{m \in \{0, \dots, M-1\}} \hat{\alpha}_{t_k - 1}(m)$$

#### 1.3 Adaptive Participation Rate Contraction Policy
Given baseline participation rate $p_{\text{base}} \in (0, 1]$, user-configured adaptation strength $s \in [0, 1]$, participation floor $p_{\min} \in (0, p_{\text{base}}]$, and ceiling $p_{\max} = p_{\text{base}}$:
$$g_p(p_{\text{turbulent}}, s) = \max\left(0.0, 1.0 - s \cdot p_{\text{turbulent}}\right)$$
$$p^{\text{eff}} = \operatorname{clip}\left(p_{\text{base}} \cdot g_p(p_{\text{turbulent}}, s), p_{\min}, p_{\max}\right)$$

**Boundary Conditions:**
1. $s = 0.0$ (disabled adaptation): $g_p = 1.0 \implies p^{\text{eff}} = p_{\text{base}}$.
2. $p_{\text{turbulent}} = 0.0$ (fully calm): $g_p = 1.0 \implies p^{\text{eff}} = p_{\text{base}}$.
3. $p_{\text{turbulent}} = 1.0$ (fully turbulent): $g_p = 1.0 - s \implies p^{\text{eff}} = \max(p_{\min}, p_{\text{base}}(1 - s))$.
4. Clamping invariant: $p^{\text{eff}} \in [p_{\min}, p_{\max}]$ is guaranteed $\forall p_{\text{turbulent}}, s$.

#### 1.4 Adaptive Almgren–Chriss Risk Aversion
Given baseline risk aversion $\lambda_{\text{base}} \ge 0$:
$$g_\lambda(p_{\text{turbulent}}, s) = 1.0 + s \cdot p_{\text{turbulent}}$$
$$\lambda^{\text{eff}} = \begin{cases} 0.0 & \text{if } \lambda_{\text{base}} = 0.0 \\ \operatorname{clip}\left(\lambda_{\text{base}} \cdot g_\lambda(p_{\text{turbulent}}, s), 0.0, 1.0\right) & \text{if } \lambda_{\text{base}} > 0.0 \end{cases}$$

**TWAP Limit Invariant:**
When $\lambda_{\text{base}} = 0.0$, $\lambda^{\text{eff}} \equiv 0.0$ under any regime $p_{\text{turbulent}}$ and strength $s$, strictly preserving analytical convergence to linear TWAP.

#### 1.5 Dynamic Execution Horizon
For asset $i$ with target trade notional $\Delta N_i$ and point-in-time $\text{ADV}_i$:
$$D_i = \min\left(D_{\max}, \max\left(1, \left\lceil \frac{|\Delta N_i|}{\text{ADV}_i \cdot p^{\text{eff}}} \right\rceil\right)\right)$$
$$D = \max_{i=1,\dots,N} D_i \in [1, D_{\max}]$$
Because $p^{\text{eff}} \le p_{\text{base}}$:
$$D(p^{\text{eff}}) \ge D(p_{\text{base}})$$
Execution horizons naturally expand during turbulent regimes to prevent volume cap breaches.

---

### 2. Causality and Look-Ahead Prevention Timeline

```
t_k - W                                  t_k - 1 (Close)                 t_k (Rebalance Decision)
|-----------------------------------------------|-----------------------------------|
[  Strict Historical Training Window Slice W   ]
Returns: R[t_k - W : t_k, :]
Volume:  V[t_k - W : t_k, :]

1. HMM Fitting on R[t_k - W : t_k, :]
2. Causal forward filtering -> p_turbulent
3. Compute p^eff and lambda^eff
4. Sched = compute_multi_day_execution_schedule(..., p^eff, lambda^eff)
5. Execute Tranche 0 on Day t_k with limit p^eff
6. Enqueue Tranches 1..D-1 into in_flight_queue with limit p^eff
```

**Temporal Mutation Invariant:**
For any modification to returns $R_{\tau, :}$ or volumes $V_{\tau, :}$ where $\tau \ge t_k$:
$$\Delta p_{\text{turbulent}}(t_k) \equiv 0, \quad \Delta p^{\text{eff}}(t_k) \equiv 0, \quad \Delta D(t_k) \equiv 0, \quad \Delta w_{t_k} \equiv 0$$

---

### 3. API & Pydantic Data Contracts

#### 3.1 `VineBacktestRequest` Schema Extensions
```python
enable_regime_aware_execution: bool = Field(default=False)
regime_num_states: int = Field(default=2, ge=2, le=5)
regime_adaptation_strength: float = Field(default=0.5, ge=0.0, le=1.0)
min_participation_rate: float = Field(default=0.02, ge=0.001, le=1.0)
```

#### 3.2 `VineBacktestRebalanceEvent` Schema Extensions
```python
regime_state: int | None = Field(default=None)
regime_probabilities: list[float] | None = Field(default=None)
effective_participation_rate: float | None = Field(default=None)
effective_risk_aversion: float | None = Field(default=None)
regime_adaptation_strength: float | None = Field(default=None)
```

#### 3.3 `VineBacktestResponse` Schema Extensions
```python
enable_regime_aware_execution: bool = Field(default=False)
regime_num_states: int = Field(default=2)
regime_adaptation_strength: float = Field(default=0.5)
min_participation_rate: float = Field(default=0.02)
```

---

### 4. Queue Lifecycle & Conflict Resolution Contracts

1. **Daily Tranche Limit:** Each in-flight tranche $d \in \{0, \dots, D-1\}$ executed on day $t_k + d$ must not exceed $\text{ADV}_i \cdot p^{\text{eff}}$.
2. **Cash Pre-Allocation:** Buy tranches reserve estimated execution fees in advance to guarantee $V_{\text{cash}} \ge 0$.
3. **Rebalance Override:** If a new rebalance triggers on day $t_{k+1}$ while tranches remain in flight from rebalance $k$:
   - The remaining tranches in `in_flight_queue` are instantly purged.
   - Rebalance optimization operates on actual pre-trade drifted portfolio weights $w_{t_{k+1}}^{\text{drifted}}$.
   - No phantom orders or duplicate trades are executed.
