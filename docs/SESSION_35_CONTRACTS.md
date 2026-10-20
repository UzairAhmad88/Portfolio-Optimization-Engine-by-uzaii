# SESSION 35 CONTRACTS: Stage 27
## Unified Out-of-Sample Liquidity Loss Distribution & Queue-Based Cash-Financed Execution

**Stage:** 27  
**Remediation Target:** DEF-35-01 (Sell-order asymmetry & unfunded buy scaling) & DEF-35-02 (Strategy-level hybrid risk aggregation heuristic)  
**Status:** Design & Specifications  

---

### 1. Mathematical Formalization

#### 1.1 Queue-Based Cash-Financed Execution Model (Resolving DEF-35-01)
In a portfolio rebalance from drifted weights $w_{t_k}^{\text{pre}}$ to target weights $w^*$ with portfolio equity $V_{t_k}$:

1. **Step 1: Execute Sell Orders First**  
   For all assets $i$ where $w_i^* < w_{t_k, i}^{\text{pre}}$, the intended sell notional is:
   $$\Delta N_i^{\text{sell}} = (w_{t_k, i}^{\text{pre}} - w_i^*) \cdot V_{t_k}$$
   Under participation limit $\text{PR}_{\max}$ and policy `cap`:
   $$\Delta N_i^{\text{exec, sell}} = \min\left(\Delta N_i^{\text{sell}}, \; \text{ADV}_i \cdot H \cdot \text{PR}_{\max}\right)$$
   Executed sell weight:
   $$w_i^{\text{exec}} = w_{t_k, i}^{\text{pre}} - \frac{\Delta N_i^{\text{exec, sell}}}{V_{t_k}}$$
   Each sell incurs trading friction $\text{Cost}_i^{\text{sell}}$ (spread crossing, market impact, commission).

2. **Step 2: Calculate Available Cash for Purchases**  
   The cash available to fund buy orders is the pre-rebalance cash plus net proceeds from realized sales:
   $$V_{\text{cash, avail}} = w_{t_k, \text{cash}}^{\text{pre}} \cdot V_{t_k} + \sum_{i \in \text{Sells}} \Delta N_i^{\text{exec, sell}} - \sum_{i \in \text{Sells}} \text{Cost}_i^{\text{sell}}$$
   Available purchase fraction: $w_{\text{cash, avail}} = \max\left(0.0, \; \frac{V_{\text{cash, avail}}}{V_{t_k}}\right)$.

3. **Step 3: Execute Buy Orders Constrained by Available Cash**  
   For all assets $j$ where $w_j^* > w_{t_k, j}^{\text{pre}}$, the intended buy notional is:
   $$\Delta N_j^{\text{buy}} = (w_j^* - w_{t_k, j}^{\text{pre}}) \cdot V_{t_k}$$
   Volume-capped buy notional:
   $$\Delta N_j^{\text{cap, buy}} = \min\left(\Delta N_j^{\text{buy}}, \; \text{ADV}_j \cdot H \cdot \text{PR}_{\max}\right)$$
   Total intended buy notional after volume caps: $\Delta N_{\text{total}}^{\text{cap, buy}} = \sum_{j \in \text{Buys}} \Delta N_j^{\text{cap, buy}}$.  
   If $\Delta N_{\text{total}}^{\text{cap, buy}} > V_{\text{cash, avail}}$:
   Buys are scaled by the cash-availability ratio $\psi = \frac{V_{\text{cash, avail}}}{\Delta N_{\text{total}}^{\text{cap, buy}}} \in [0, 1]$:
   $$\Delta N_j^{\text{exec, buy}} = \Delta N_j^{\text{cap, buy}} \cdot \psi$$
   Executed buy weight:
   $$w_j^{\text{exec}} = w_{t_k, j}^{\text{pre}} + \frac{\Delta N_j^{\text{exec, buy}}}{V_{t_k}}$$

4. **Step 4: Residual Cash Accounting & Invariant**  
   Any unspent cash balance after buys and all friction deductions remains in cash:
   $$w_{\text{cash}} = 1.0 - \sum_{i=1}^N w_i^{\text{exec}} \ge 0.0$$
   $$\sum_{i=1}^N w_i^{\text{exec}} + w_{\text{cash}} \equiv 1.0$$
   **Result:** Holdings can *never* exceed 1.0 ($\sum w_i^{\text{exec}} \le 1.0$ is guaranteed by construction), completely eliminating the need for post-hoc proportional renormalization of existing holdings.

---

#### 1.2 Unified Out-of-Sample Realized Liquidation Loss Distribution (Resolving DEF-35-02)
Rather than adding an average in-sample simulation increment $\Delta_{\text{stress}}$ to out-of-sample historical return CVaR, the engine computes the daily net liquidation loss time series on every out-of-sample trading day $t \in \{1, \dots, T_{\text{oos}}\}$:

1. **Daily Net Liquidation Loss:**
   $$l_t^{\text{market}} = -R_{p, t}^{\text{gross}}$$
   $$l_t^{\text{det}} = -R_{p, t}^{\text{gross}} + c_{\text{liq}, t}^{\text{det}}$$
   $$l_t^{\text{stressed}} = -R_{p, t}^{\text{gross}} + c_{\text{liq}, t}^{\text{stressed}}$$
   where $c_{\text{liq}, t}^{\text{stressed}}$ uses day $t$'s realized return $r_{i, t}$ and portfolio return $R_{p, t}^{\text{gross}}$ to evaluate endogenous spread widening and volume contraction under point-in-time ADV and volatility:
   $$\text{Spread}_{i, t} = \text{Spread}_{0, i} \cdot [1 + \kappa \max(0, -r_{i, t})]$$
   $$\text{ADV}_{i, t} = \frac{\text{ADV}_{0, i}}{1 + \eta \max(0, -R_{p, t}^{\text{gross}})}$$

2. **Unified Out-of-Sample Risk Quantiles:**
   $$\text{historical\_var\_99} = \text{Quantile}_{0.99}\left(\{l_t^{\text{market}}\}\right)$$
   $$\text{historical\_cvar\_99} = \mathbb{E}\left[l_t^{\text{market}} \;\middle|\; l_t^{\text{market}} \ge \text{historical\_var\_99}\right]$$
   $$\text{l\_var\_99} = \text{Quantile}_{0.99}\left(\{l_t^{\text{det}}\}\right)$$
   $$\text{l\_cvar\_99} = \mathbb{E}\left[l_t^{\text{det}} \;\middle|\; l_t^{\text{det}} \ge \text{l\_var\_99}\right]$$
   $$\text{stressed\_l\_var\_99} = \text{Quantile}_{0.99}\left(\{l_t^{\text{stressed}}\}\right)$$
   $$\text{stressed\_l\_cvar\_99} = \mathbb{E}\left[l_t^{\text{stressed}} \;\middle|\; l_t^{\text{stressed}} \ge \text{stressed\_l\_var\_99}\right]$$

3. **Mathematical Properties:**
   - Single-distribution statistical consistency: all metrics are quantiles of realized out-of-sample daily losses.
   - Natural monotonicity: because $c_{\text{liq}, t}^{\text{stressed}} \ge c_{\text{liq}, t}^{\text{det}} \ge 0$, it follows that $l_t^{\text{stressed}} \ge l_t^{\text{det}} \ge l_t^{\text{market}}$ pointwise on every day $t$.
   - Monotonic quantile preservation:
     $$\text{stressed\_l\_cvar\_99} \ge \text{l\_cvar\_99} \ge \text{historical\_cvar\_99}$$
   - Identical recovery: When endogenous liquidity is disabled or $\kappa = 0, \eta = 0$, $l_t^{\text{stressed}} \equiv l_t^{\text{det}}$ pointwise, so $\text{stressed\_l\_cvar\_99} \equiv \text{l\_cvar\_99}$ identically.
