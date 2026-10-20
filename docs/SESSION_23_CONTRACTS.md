# SESSION 23 FORMAL SPECIFICATION & MATHEMATICAL CONTRACTS
## Stage 19: Non-Linear Execution Costs, Market Impact Modeling & Optimal Trade Scheduling (Almgren-Chriss Engine)

**Milestone:** Stage 19  
**Session:** 23  
**Status:** APPROVED & CONTRACTUALLY SEALED  
**Author:** Senior Quantitative Finance Research Engineer, Systematic Portfolio Manager & Software Quality Auditor  
**Date:** 2026-10-18T22:30:00+05:00  

---

## 1. Problem Statement & Operational Boundary

In institutional quantitative asset management, executing portfolio rebalances incurs significant market friction. Previous stages (Stages 7, 13, 14, 15, 17, 18) relied on linear transaction costs ($c_{\text{bps}} \times \text{Turnover}$). However, for institutional capital pools (\$10M - \$1B+), trading significant fractions of Average Daily Volume (ADV) moves market prices against the trader:

1. **Permanent Market Impact:** Caused by informational asymmetry and inventory absorption; permanently shifts the equilibrium mid-price.
2. **Temporary Market Impact:** Caused by transient liquidity depletion in the order book; dissipates after trading ceases.
3. **Execution Horizon Trade-Off:** Executing quickly minimizes market risk (variance of execution price) but incurs massive temporary impact costs. Executing slowly minimizes market impact but exposes the portfolio to drift and timing risk.

Stage 19 implements the seminal **Almgren-Chriss (2000)** optimal execution framework, **Square-Root Law market impact modeling**, **TWAP / VWAP / Almgren-Chriss schedule generation**, and integrates non-linear liquidity penalties into portfolio rebalancing and walk-forward backtesting.

### Explicit Scope Exclusions:
- High-frequency limit order book (LOB) matching engine simulation at the microsecond level (Level 3 tick-by-tick order matching is out of scope).
- Live broker FIX protocol routing (simulated execution and institutional order schedule generation only).

---

## 2. Mathematical Definitions & Core Formulations

### A. Almgren-Chriss Discrete Framework
Let an institutional order require selling or buying $X_0$ shares (or base currency notional) over a total execution horizon $T$, partitioned into $N$ equal discrete trading intervals:
$$t_k = k \tau, \quad k = 0, \dots, N, \quad \tau = \frac{T}{N}$$

- $x_k$: Remaining shares to be executed at time $t_k$, with boundary conditions:
  $$x_0 = X_0, \quad x_N = 0$$
- $n_k = x_{k-1} - x_k$: Number of shares executed during interval $(t_{k-1}, t_k]$, with $\sum_{k=1}^N n_k = X_0$.
- $v_k = \frac{n_k}{\tau}$: Trading rate / velocity.

### B. Price Dynamics & Market Impact
The security price evolves as:
$$S_k = S_{k-1} + \sigma \tau^{1/2} \xi_k - \tau \gamma(v_k)$$
where $\xi_k \sim \mathcal{N}(0, 1)$ are i.i.d. innovations, $\sigma$ is daily asset volatility, and $\gamma(v) = \gamma v$ is the **permanent market impact parameter**.

The realized execution price for the $k$-th trade is:
$$\tilde{S}_k = S_{k-1} - \eta(v_k)$$
where $\eta(v) = \frac{\text{Spread}}{2} + \eta v$ is the **temporary market impact function**.

### C. Expected Cost (Implementation Shortfall) and Timing Risk
The total implementation shortfall $I(x)$ relative to the initial arrival price $S_0$ is:
$$I(x) = X_0 S_0 - \sum_{k=1}^N n_k \tilde{S}_k$$

The expected total cost is:
$$\mathbb{E}[I(x)] = \frac{1}{2} \gamma X_0^2 + \frac{\text{Spread}}{2} X_0 + \frac{\eta}{\tau} \sum_{k=1}^N n_k^2$$

The variance of execution cost (timing risk from price volatility):
$$V[I(x)] = \sigma^2 \tau \sum_{k=1}^N x_k^2$$

### D. Optimal Execution Trajectory Formulation
The portfolio manager minimizes the risk-adjusted execution utility function:
$$\min_{x} U[x] = \mathbb{E}[I(x)] + \lambda V[I(x)]$$
subject to $x_0 = X_0$, $x_N = 0$, where $\lambda \ge 0$ is the trader's **risk aversion parameter**.

### E. Analytical Closed-Form Solution
The Euler-Lagrange optimality condition yields a second-order linear difference equation:
$$\frac{x_{j-1} - 2 x_j + x_{j+1}}{\tau^2} = \tilde{\kappa}^2 x_j, \quad \tilde{\kappa}^2 = \frac{\lambda \sigma^2}{\eta}$$

In continuous time / discrete approximation, the unique analytical trajectory is:
$$x_j^* = \frac{\sinh(\kappa (T - t_j))}{\sinh(\kappa T)} X_0$$
where $\kappa$ is the **urgency parameter**:
$$\kappa = \frac{1}{\tau} \operatorname{arccosh}\left( 1 + \frac{\lambda \sigma^2 \tau^2}{2 \eta} \right) \approx \sqrt{\frac{\lambda \sigma^2}{\eta}}$$

#### Limiting Archetypes:
1. **Risk-Neutral ($\lambda \to 0 \implies \kappa \to 0$):**
   $$\lim_{\kappa \to 0} x_j^* = X_0 \left( 1 - \frac{t_j}{T} \right) \implies n_k^* = \frac{X_0}{N} \quad (\text{Pure TWAP})$$
2. **Infinite Risk Aversion ($\lambda \to \infty \implies \kappa \to \infty$):**
   Executes immediately at $t_1$ ($n_1 = X_0$, market order), incurring maximum temporary impact to eliminate all volatility risk.
3. **Volume-Weighted Average Price (VWAP):**
   Given historical intraday volume profile $\{V_k\}_{k=1}^N$:
   $$n_k^{\text{VWAP}} = X_0 \frac{V_k}{\sum_{m=1}^N V_m}$$

### F. Square-Root Law of Market Impact for Portfolio Rebalancing
For a multi-asset portfolio rebalancing from drifted weights $w^{\text{drift}}$ to target weights $w^{\text{target}}$ on portfolio equity $E$:
The traded notional for asset $i$ is:
$$\Delta \$ _i = |w_i^{\text{target}} - w_i^{\text{drift}}| \times E$$

Let $\text{ADV}_i$ be Average Daily Dollar Volume and $\sigma_i$ be annualized volatility.
The institutional **Barra / Almgren Square-Root Law** models total execution cost as:
$$\text{Cost}_i = \Delta \$ _i \cdot \left[ \frac{\text{Spread}_i}{2} + c_{\text{temp}} \cdot \sigma_i \cdot \left( \frac{\Delta \$ _i}{\text{ADV}_i \cdot \text{Horizon}} \right)^{1/2} + c_{\text{perm}} \cdot \sigma_i \cdot \left( \frac{\Delta \$ _i}{\text{ADV}_i} \right) \right]$$
where $c_{\text{temp}} \approx 0.5$ and $c_{\text{perm}} \approx 0.1$ are empirical market constants.

---

## 3. Input & Output Schemas and Units

### A. Execution Trajectory Request (`OptimalExecutionRequest`)
- `order_size`: float $> 0$ (Total shares or currency value to execute).
- `asset_price`: float $> 0$ (Current spot price $S_0$).
- `daily_volume`: float $> 0$ (Average daily volume in shares or currency).
- `daily_volatility`: float $> 0$ (Daily return volatility $\sigma$).
- `bid_ask_spread`: float $\ge 0$ (Quoted spread in price units, default 0.05% of price).
- `horizon_periods`: int $\ge 2, \le 100$ (Number of execution intervals $N$, default 10).
- `trading_hours`: float $> 0$ (Total execution window in hours, e.g. 6.5).
- `risk_aversion`: float $\ge 0$ (Trader risk aversion $\lambda$).
- `temporary_impact_factor`: float $> 0$ (Impact scaling coefficient $\eta$).
- `permanent_impact_factor`: float $\ge 0$ (Permanent impact coefficient $\gamma$).
- `volume_profile`: Optional list of floats (Intraday volume fractions summing to 1.0).

### B. Execution Trajectory Response (`OptimalExecutionResponse`)
- `schedule_points`: List of execution intervals containing:
  - `period`: int ($1 \dots N$).
  - `time_elapsed_pct`: float ($0.0 \dots 1.0$).
  - `almgren_chriss_shares`: float.
  - `almgren_chriss_rate`: float.
  - `twap_shares`: float.
  - `vwap_shares`: float.
  - `remaining_shares`: float.
- `summary_metrics`:
  - `urgency_parameter`: float ($\kappa$).
  - `half_life`: float ($\ln(2)/\kappa$, time to execute 50% of order).
  - `expected_cost`: float ($\mathbb{E}[I]$ in currency units).
  - `expected_cost_bps`: float (Cost in basis points of order value).
  - `timing_risk_variance`: float ($V[I]$).
  - `timing_risk_std`: float ($\sqrt{V[I]}$ in currency units).
  - `twap_expected_cost_bps`: float.
  - `cost_savings_vs_twap_bps`: float.

### C. Rebalance Impact Analysis Request (`RebalanceImpactRequest`)
- `dataset_id`: str (Persistent dataset identifier).
- `target_weights`: dict[str, float] (Asset target allocations).
- `portfolio_equity`: float $> 0$ (Total portfolio value, e.g. \$10,000,000).
- `execution_horizon_days`: float $> 0$ (Days to execute rebalance, default 1.0).
- `impact_model`: Literal["square_root", "linear", "fixed_bps"].

### D. Rebalance Impact Analysis Response (`RebalanceImpactResponse`)
- `total_traded_notional`: float.
- `total_impact_cost`: float.
- `effective_cost_bps`: float.
- `asset_impacts`: List of per-asset metrics:
  - `ticker`: str.
  - `traded_notional`: float.
  - `adv`: float.
  - `participation_rate_pct`: float ($\frac{\text{Traded}}{\text{ADV}} \times 100$).
  - `spread_cost`: float.
  - `temporary_impact_cost`: float.
  - `permanent_impact_cost`: float.
  - `total_cost`: float.
  - `total_cost_bps`: float.

---

## 4. Deterministic Hand-Calculated Analytical Benchmark

### 2-Period Almgren-Chriss Benchmark:
- **Parameters:**
  - $X_0 = 1,000,000$ shares
  - $S_0 = \$50.00$
  - Horizon: $N = 2$ periods, $\tau = 0.5$ days ($T = 1.0$ day)
  - Volatility: $\sigma = \$1.00$ per share-day ($\sigma^2 = 1.0$)
  - Temporary Impact: $\eta = 2.5 \times 10^{-6}$
  - Permanent Impact: $\gamma = 0$
  - Spread: $\$0.00$
  - Risk Aversion: $\lambda = 5.0 \times 10^{-6}$

- **Analytical Formulation:**
  $$\tilde{\kappa}^2 = \frac{\lambda \sigma^2}{\eta} = \frac{5.0 \times 10^{-6} \times 1.0}{2.5 \times 10^{-6}} = 2.0$$
  $$\cosh(\kappa \tau) = 1 + \frac{\lambda \sigma^2 \tau^2}{2 \eta} = 1 + \frac{2.0 \times 0.25}{2} = 1.25$$
  $$\kappa \tau = \operatorname{arccosh}(1.25) = \ln(1.25 + \sqrt{1.25^2 - 1}) = \ln(1.25 + 0.75) = \ln(2.0) = 0.69314718$$
  Since $N = 2$, $\kappa T = 2 \kappa \tau = 2 \ln(2) = \ln(4) = 1.38629436$.

- **Optimal Share Trajectory:**
  At $t_1 = 0.5$:
  $$x_1^* = X_0 \frac{\sinh(\kappa(T - t_1))}{\sinh(\kappa T)} = X_0 \frac{\sinh(\kappa \tau)}{\sinh(2 \kappa \tau)}$$
  Using double angle identity $\sinh(2 u) = 2 \sinh(u) \cosh(u)$:
  $$x_1^* = X_0 \frac{\sinh(\kappa \tau)}{2 \sinh(\kappa \tau) \cosh(\kappa \tau)} = \frac{X_0}{2 \cosh(\kappa \tau)} = \frac{1,000,000}{2 \times 1.25} = 400,000 \text{ shares}$$

- **Trade Amounts:**
  - Period 1 ($k=1$): $n_1 = x_0 - x_1 = 1,000,000 - 400,000 = 600,000 \text{ shares}$ ($60\%$).
  - Period 2 ($k=2$): $n_2 = x_1 - x_2 = 400,000 - 0 = 400,000 \text{ shares}$ ($40\%$).

- **TWAP Baseline Comparison:**
  - $n_1^{\text{TWAP}} = 500,000$, $n_2^{\text{TWAP}} = 500,000$ shares ($50\% / 50\%$).
  - TWAP Expected Cost:
    $$\mathbb{E}[I_{\text{TWAP}}] = \frac{\eta}{\tau} (500,000^2 + 500,000^2) = \frac{2.5 \times 10^{-6}}{0.5} (5.0 \times 10^{11}) = 5.0 \times 10^{-6} \times 5.0 \times 10^{11} = \$2,500,000$$
    TWAP Variance:
    $$V[I_{\text{TWAP}}] = \sigma^2 \tau (x_1^2 + x_2^2) = 1.0 \times 0.5 \times (500,000^2 + 0) = 0.5 \times 2.5 \times 10^{11} = 1.25 \times 10^{11}$$
    TWAP Utility:
    $$U_{\text{TWAP}} = 2,500,000 + 5.0 \times 10^{-6} \times 1.25 \times 10^{11} = 2,500,000 + 625,000 = \$3,125,000$$

- **Almgren-Chriss Optimal Cost & Utility:**
  - Optimal Expected Cost:
    $$\mathbb{E}[I^*] = \frac{2.5 \times 10^{-6}}{0.5} (600,000^2 + 400,000^2) = 5.0 \times 10^{-6} \times (3.6 \times 10^{11} + 1.6 \times 10^{11}) = 5.0 \times 10^{-6} \times 5.2 \times 10^{11} = \$2,600,000$$
  - Optimal Variance:
    $$V[I^*] = 1.0 \times 0.5 \times (400,000^2 + 0) = 0.5 \times 1.6 \times 10^{11} = 8.0 \times 10^{10}$$
  - Optimal Utility:
    $$U^* = 2,600,000 + 5.0 \times 10^{-6} \times 8.0 \times 10^{10} = 2,600,000 + 400,000 = \$3,000,000$$
  - **Exact Utility Improvement:** $\$3,125,000 - \$3,000,000 = \$125,000$ reduction in risk-adjusted cost!
  - **Numerical Tolerance:** Analytical test must reconcile $x_1 = 400,000$, $n_1 = 600,000$, $n_2 = 400,000$, $U^* = 3,000,000$ to within $10^{-12}$.

---

## 5. Temporal Integrity & Look-Ahead Prevention

- Liquidity estimation (ADV, Spread, Volatility) for rebalance date $t_k$ must use observations strictly prior to $t_k$: $\tau \in [t_k - W, t_k - 1]$.
- In walk-forward backtesting, future trading volume or future price spikes beyond date $t_k$ must never be accessed to compute historical market impact.
- Mutating out-of-sample volume or prices after $t_k$ must produce bitwise identical execution schedules at $t_k$.

---

## 6. Security, Authentication & Multi-Tenancy

- Endpoints under `/api/v1/execution` must require valid JWT Bearer tokens via `get_current_active_user`.
- Rebalance impact analysis on persistent datasets must enforce `check_dataset_access`.
- Unauthenticated requests must yield HTTP 401 Unauthorized; cross-tenant requests must yield HTTP 403 Forbidden or HTTP 404 Not Found.
- Numerical inputs must be strictly bounded ($X_0 > 0$, $\tau > 0$, $N \in [2, 100]$) to prevent denial-of-service / memory exhaustion.

---

## 7. Acceptance Criteria

1. **Analytical Benchmark Reconciliation:** The 2-period Almgren-Chriss closed-form benchmark is verified to $< 10^{-12}$ precision.
2. **Convexity & Monotonicity:** Higher risk aversion $\lambda$ strictly accelerates execution ($n_1^*(\lambda_2) > n_1^*(\lambda_1)$ for $\lambda_2 > \lambda_1$).
3. **Limiting Recovery:** When $\lambda = 0$, the Almgren-Chriss schedule converges exactly to TWAP within $10^{-8}$.
4. **Volume Tracking:** VWAP schedule accurately matches the provided intraday volume profile.
5. **Non-Linear Rebalance Cost Scaling:** Large portfolio notional trades experience non-linear basis-point impact scaling per the Square-Root Law.
6. **Regression Suite:** All existing 324 backend tests and 30 frontend tests continue to pass.
7. **Production Build:** `npm run build` succeeds with zero errors.
