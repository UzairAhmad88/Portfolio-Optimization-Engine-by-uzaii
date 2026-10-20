# SESSION 24 AUDIT & ROADMAP EVALUATION REPORT

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 24  
**Date:** 2026-10-18  
**Auditor:** Quantitative Finance Research Engineer & Software Quality Auditor  
**Status:** AUDIT COMPLETE — AWAITING USER GATE A APPROVAL (NO IMPLEMENTATION UNDERTAKEN)

---

## 1. Repository & Roadmap Baseline Audit

### 1.1 Working Tree & Environment State
- **Workspace:** `d:\Quants\Projects\quant-portfolio-engine-starter`
- **Git State:** Not a root Git repository (local standalone project tree). Working files from Sessions 22 and 23 are intact and consistent.
- **Database Migrations:** SQLite / PostgreSQL Alembic migration head is at `b2c3d4e5f6a7 (head)` (incorporating `research_experiments` and `research_experiment_runs`). No unapplied or broken migrations detected.
- **Backend Test Status:** **335 passed**, 0 failed, 6 Starlette deprecation warnings in 43.00s (`backend\.venv\Scripts\pytest.exe -q`).
- **Frontend Test Status:** **32 passed**, 0 failed in 8.86s (`npx vitest run --pool=threads` across `api-client.test.ts` and `App.test.tsx`).
- **Frontend Production Build:** `tsc -b && vite build` completed cleanly with exit code `0` (HTML: 0.80 kB, CSS: 10.61 kB, JS: 679.70 kB).

### 1.2 Master Plan & Roadmap State
- Inspection of `docs/MASTER_PLAN.md`, `docs/REQUIREMENTS_SPEC.md`, and `docs/SYSTEM_ARCHITECTURE.md` confirms:
  - **Stage 18:** Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging Engine (Completed in Session 22).
  - **Stage 19:** Non-Linear Execution Costs, Market Impact Modeling & Optimal Trade Scheduling (Almgren-Chriss Engine) (Completed in Session 23).
  - **Stage 20:** **MISSING / UNDEFINED**. Neither `docs/MASTER_PLAN.md` nor architectural documentation specifies Stage 20.
- In accordance with **Non-Negotiable Rule 4** and **Gate A**, implementation of Stage 20 must NOT begin until candidate scopes are formally audited, presented, and explicitly approved by the user.

---

## 2. Phase B — Mandatory Stage 19 Quantitative Audit

A comprehensive independent audit of `backend/app/quant/execution.py`, `backend/app/execution/service.py`, and `backend/tests/test_execution_engine.py` was conducted.

### 2.1 Almgren-Chriss (2000) Trajectory Formulation & Units

#### A. Trajectory Formulation
The optimal execution trajectory minimizing expected execution shortfall plus timing risk variance $U[x] = E[x] + \lambda V[x]$ over $N$ discrete intervals $\tau = T/N$ is:
$$x_j^* = X_0 \frac{\sinh(\kappa (T - t_j))}{\sinh(\kappa T)}, \quad j \in \{0, 1, \dots, N\}$$
where $n_j = x_{j-1} - x_j$ represents discrete trade sizes.

In `execution.py:95-99`, the code uses the exact discrete recurrence relation from Almgren-Chriss (2000) equation (19):
$$2 \left[\cosh(\kappa \tau) - 1\right] = \frac{\lambda \sigma^2 \tau^2}{\eta} \implies \cosh(\kappa \tau) = 1 + \frac{1}{2}\frac{\lambda \sigma^2 \tau^2}{\eta}$$
$$\kappa = \frac{\operatorname{arccosh}\left(1 + \frac{1}{2}\frac{\lambda \sigma^2 \tau^2}{\eta}\right)}{\tau}$$

#### B. Dimensional Consistency & Unit Analysis
- **Initial inventory ($X_0$) & holdings ($x_j$):** Shares ($\text{shares}$).
- **Trade increments ($n_j$):** Shares ($\text{shares}$), strictly non-negative for liquidation.
- **Trading horizon ($T$) & interval ($\tau$):** Trading days ($\text{days}$), with $T = 1.0$ normalized trading day and $\tau = 1.0 / N$.
- **Volatility ($\sigma$):** Absolute daily price volatility ($\$ / (\text{share} \cdot \sqrt{\text{day}})$).
- **Temporary impact coefficient ($\eta$):** $(\$ \cdot \text{day}) / \text{shares}^2$.
- **Permanent impact coefficient ($\gamma$):** $\$ / \text{shares}^2$.
- **Risk aversion parameter ($\lambda$):** $1 / \$$ ($\text{dollars}^{-1}$).
- **Urgency parameter argument ($\frac{\lambda \sigma^2 \tau^2}{\eta}$):**
  $$\left[\frac{\lambda \sigma^2 \tau^2}{\eta}\right] = \frac{(1/\$) \cdot (\$^2 / (\text{shares}^2 \cdot \text{day})) \cdot \text{day}^2}{(\$ \cdot \text{day}) / \text{shares}^2} = \frac{\$ \cdot \text{day} / \text{shares}^2}{\$ \cdot \text{day} / \text{shares}^2} = 1 \quad (\text{Dimensionless})$$
  Therefore, $\kappa \tau$ is dimensionless, and $\kappa$ has dimension $\text{days}^{-1}$ (execution urgency/frequency). The units are mutually consistent.

#### C. Boundary Behavior
- **Risk-Neutral Limit ($\lambda \to 0$):** As $\lambda \to 0$, $\kappa \to 0$, and $\lim_{\kappa \to 0} \frac{\sinh(\kappa(T - t_j))}{\sinh(\kappa T)} = 1 - \frac{t_j}{T} = 1 - \frac{j}{N}$. Verified: converges bitwise to linear TWAP.
- **Infinite Urgency ($\lambda \to \infty$ or $\eta \to 0$):** $\kappa \to \infty$, causing $x_1^* \to 0$, liquidating all shares in the very first interval.
- **Terminal Liquidation Condition:** $x_N^* = X_0 \frac{\sinh(0)}{\sinh(\kappa T)} = 0.0$ shares identically. Verified.

---

### 2.2 Independent Recalculation of the 2-Period Analytical Benchmark

The Session 23 benchmark inputs were audited independently from primary principles:
- Order Size: $X_0 = 1,000,000\text{ shares}$
- Spot Price: $S_0 = \$50.00$ ($\text{Notional} = \$50,000,000$)
- Periods: $N = 2$, Horizon $T = 1.0\text{ day} \implies \tau = 0.5\text{ days}$
- Volatility: $\sigma = \$1.00 / (\text{share} \cdot \sqrt{\text{day}})$
- Temporary Impact: $\eta = 2.5 \times 10^{-6}\text{ \$}\cdot\text{day}/\text{shares}^2$
- Permanent Impact: $\gamma = 0.0$
- Spread: $\text{Spread} = \$0.00$
- Risk Aversion: $\lambda = 5.0 \times 10^{-6}\text{ \$}^{-1}$

#### Step-by-Step Mathematical Derivation:
1. **Urgency Parameter:**
   $$\cosh(\kappa \tau) = 1 + \frac{1}{2} \frac{(5.0 \times 10^{-6})(1.0^2)(0.5^2)}{2.5 \times 10^{-6}} = 1 + \frac{1}{2} \frac{1.25 \times 10^{-6}}{2.5 \times 10^{-6}} = 1 + 0.25 = 1.25$$
   $$\kappa \tau = \operatorname{arccosh}(1.25) = \ln(1.25 + \sqrt{1.25^2 - 1}) = \ln(1.25 + 0.75) = \ln(2.0) \approx 0.69314718056$$
   $$\kappa = \frac{\ln(2.0)}{0.5} = 2 \ln(2.0) \approx 1.38629436112\text{ day}^{-1}$$

2. **Optimal Trajectory & Trade Sizes:**
   $$\sinh(2 \kappa \tau) = 2 \sinh(\kappa \tau) \cosh(\kappa \tau)$$
   $$x_1^* = X_0 \frac{\sinh(\kappa(1.0 - 0.5))}{\sinh(\kappa \cdot 1.0)} = X_0 \frac{\sinh(\kappa \tau)}{2 \sinh(\kappa \tau) \cosh(\kappa \tau)} = \frac{X_0}{2 \cosh(\kappa \tau)} = \frac{1,000,000}{2 \times 1.25} = 400,000\text{ shares}$$
   $$x_0^* = 1,000,000\text{ shares}, \quad x_1^* = 400,000\text{ shares}, \quad x_2^* = 0\text{ shares}$$
   $$n_1^* = x_0 - x_1 = 600,000\text{ shares}, \quad n_2^* = x_1 - x_2 = 400,000\text{ shares}$$

3. **Expected Shortfall ($E[x]$):**
   Trading velocities: $v_1 = 600,000 / 0.5 = 1,200,000\text{ shares/day}$, $v_2 = 400,000 / 0.5 = 800,000\text{ shares/day}$.
   Price concessions: $\Delta \tilde{S}_1 = 2.5 \times 10^{-6} \times 1,200,000 = \$3.00/\text{share}$, $\Delta \tilde{S}_2 = 2.5 \times 10^{-6} \times 800,000 = \$2.00/\text{share}$.
   $$E[x] = n_1 \Delta \tilde{S}_1 + n_2 \Delta \tilde{S}_2 = (600,000 \times \$3.00) + (400,000 \times \$2.00) = \$1,800,000 + \$800,000 = \$2,600,000.00$$
   Equivalently via the quadratic sum formula:
   $$E[x] = \frac{\eta}{\tau} (n_1^2 + n_2^2) = \frac{2.5 \times 10^{-6}}{0.5} (600,000^2 + 400,000^2) = 5.0 \times 10^{-6} \times (3.6 \times 10^{11} + 1.6 \times 10^{11}) = \$2,600,000.00$$

4. **Timing Risk Variance ($V[x]$):**
   Remaining inventory subject to price Brownian motion over $[t_1, t_2]$ is $x_1 = 400,000$ shares.
   Price variance over interval $\tau = 0.5$ is $\sigma^2 \tau = 1.0^2 \times 0.5 = 0.5\text{ \$}^2/\text{share}^2$.
   $$V[x] = \sigma^2 \tau x_1^2 = 0.5 \times (400,000)^2 = 0.5 \times 1.6 \times 10^{11} = 8.0 \times 10^{10}\text{ \$}^2$$
   Standard deviation of dollar shortfall: $\sqrt{V[x]} = \sqrt{8.0 \times 10^{10}} = \$282,842.71$.

5. **Risk-Penalized Utility ($U^*$):**
   $$U^* = E[x] + \lambda V[x] = \$2,600,000 + (5.0 \times 10^{-6}\text{ \$}^{-1}) \times (8.0 \times 10^{10}\text{ \$}^2) = \$2,600,000 + \$400,000 = \$3,000,000.00$$

6. **TWAP Comparison:**
   $n_1^{\text{twap}} = 500,000$, $n_2^{\text{twap}} = 500,000$, $x_1^{\text{twap}} = 500,000$.
   $$E^{\text{twap}} = 5.0 \times 10^{-6} \times (500,000^2 + 500,000^2) = 5.0 \times 10^{-6} \times 5.0 \times 10^{11} = \$2,500,000.00$$
   $$V^{\text{twap}} = 0.5 \times (500,000)^2 = 1.25 \times 10^{11}\text{ \$}^2$$
   $$U^{\text{twap}} = \$2,500,000 + (5.0 \times 10^{-6} \times 1.25 \times 10^{11}) = \$2,500,000 + \$625,000 = \$3,125,000.00$$
   $$\text{Utility Savings vs TWAP} = U^{\text{twap}} - U^* = \$3,125,000 - \$3,000,000 = \$125,000.00$$

#### Audit Outcome:
The reported figures ($E[x] = \$2,600,000$, $V[x] = 8.0 \times 10^{10}\text{ \$}^2$, $U^* = \$3,000,000$) are **100% mathematically correct and rigorously derived**. There is no dimensional error or hidden inconsistency.

---

### 2.3 Square-Root Market Impact Model Audit

In `backend/app/quant/execution.py:294-301`:
$$\text{Cost}_{\text{spread}} = \Delta \$ \times \frac{\text{Spread}_{\text{bps}} \times 10^{-4}}{2}$$
$$\text{Cost}_{\text{temp}} = \Delta \$ \times \left(c_{\text{temp}} \times \sigma_{\text{daily}} \times \sqrt{\min\left(\frac{\Delta \$}{\text{ADV} \times H}, 2.0\right)}\right)$$
$$\text{Cost}_{\text{perm}} = \Delta \$ \times \left(c_{\text{perm}} \times \sigma_{\text{daily}} \times \min\left(\frac{\Delta \$}{\text{ADV}}, 1.0\right)\right)$$
$$\text{Total Cost} = \text{Cost}_{\text{spread}} + \text{Cost}_{\text{temp}} + \text{Cost}_{\text{perm}}$$

- $\Delta \$$: Traded notional in currency units (dollars).
- $\text{ADV}$: Average Daily Volume in currency units (dollars).
- $\sigma_{\text{daily}}$: Daily decimal return volatility ($\sigma_{\text{ann}} / \sqrt{252}$).
- **Evaluation:**
  - $\frac{\Delta \$}{\text{ADV} \times H}$ is dimensionless participation rate.
  - $c_{\text{temp}} \sigma_{\text{daily}} \sqrt{\text{PartRate}}$ is decimal price concession.
  - Multiplication by $\Delta \$$ correctly yields total dollar impact.
  - Additive separation of bid-ask spread crossing, temporary impact, and permanent impact avoids double-counting.
  - Capping participation rate in the square root prevents numerical instability for extreme orders.

---

## 3. Candidate Roadmap Options for Stage 20 (Gate A)

Since Stage 20 is not defined in `docs/MASTER_PLAN.md`, three high-impact, mathematically sound candidate scopes are proposed for user selection:

### Candidate 1: Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting
- **Business Purpose:** Macroeconomic regimes alternate between Low Volatility/Expansion and High Volatility/Crisis regimes. Static weights or simple rolling windows suffer from severe lag during sudden regime breaks (e.g. 2008, 2020). Quantitative allocators need automated regime detection and dynamic volatility scaling to protect capital.
- **Quantitative Rationale:**
  1. 2-State and 3-State Gaussian Hidden Markov Model (HMM) estimating transition probabilities $P_{ij} = \mathbb{P}(S_t = j \mid S_{t-1} = i)$, state return vectors $\mu_k$, and covariance matrices $\Sigma_k$ via expectation-maximization (EM / Baum-Welch).
  2. Recursive forward-filtering yielding causal posterior probabilities $\pi_{k,t} = \mathbb{P}(S_t = k \mid r_{1:t})$ with zero look-ahead bias.
  3. Regime-conditioned portfolio optimization blending state covariances $\Sigma_t = \sum_k \pi_{k,t} \Sigma_k$.
  4. Dynamic Volatility Targeting overlay: $w_t^{\text{scaled}} = \min\left(\text{Lev}_{\max}, \frac{\sigma_{\text{target}}}{\hat{\sigma}_t}\right) w_t^*$, adjusting cash buffer/leverage dynamically.
- **Dependencies:** Pure NumPy/SciPy core, existing market data and walk-forward simulation framework.
- **Implementation Risks:** EM local optima, label-switching across bootstrap iterations.
- **Acceptance Criteria:** Analytical 2-state synthetic benchmark with known transition matrix and state parameters; strict temporal causality (filtered probabilities $\pi_{k,t}$ use only $t \le T$); volatility target scaling accurately bounds realized volatility to target; 100% test pass rate and dedicated React workspace.

### Candidate 2: Multi-Asset Performance Attribution & Brinson-Fachler Factor Breakdown
- **Business Purpose:** Institutional allocators, pension funds, and LPs require formal performance attribution to decompose active return ($R_p - R_b$) into explicit driver effects: Did outperformance come from market timing across asset classes (allocation), stock picking within classes (selection), or cross-currency hedging?
- **Quantitative Rationale:**
  1. Classic Brinson-Fachler (1985) arithmetic attribution:
     - Allocation Effect: $A_i = (w_{p,i} - w_{b,i})(R_{b,i} - R_b)$
     - Selection Effect: $S_i = w_{b,i}(R_{p,i} - R_{b,i})$
     - Interaction Effect: $I_i = (w_{p,i} - w_{b,i})(R_{p,i} - R_{b,i})$
  2. Multi-period geometric linking (Carino / Menchero algorithms) guaranteeing exact multi-period reconciliation without compounding residuals.
  3. Ankrim-Hensel multi-currency extension separating asset allocation from currency overlay gains.
- **Dependencies:** Existing portfolio backtest records, benchmark price data, and multi-asset taxonomy.
- **Implementation Risks:** Multi-period compounding residuals under volatile returns; benchmark weight alignment.
- **Acceptance Criteria:** Hand-calculated 3-sector 2-period analytical benchmark confirming exact zero-residual additivity; zero active weight yields zero allocation effect; interactive React workspace with waterfall attribution charts.

### Candidate 3: Non-Parametric Tail Risk Modeling & Extreme Value Theory (EVT / Cornish-Fisher)
- **Business Purpose:** Standard parametric VaR and CVaR assume elliptical/Gaussian distributions, severely underestimating fat-tailed black swan events, skewness, and kurtosis in extreme crashes. Quantitative risk committees require extreme value theory (Generalized Pareto Distribution / Peaks-over-Threshold) and Cornish-Fisher polynomial expansions to price catastrophic tail risk.
- **Quantitative Rationale:**
  1. Cornish-Fisher expansion adjusting VaR for skewness $\mathcal{S}$ and excess kurtosis $\mathcal{K}$:
     $\tilde{z}_\alpha = z_\alpha + \frac{1}{6}(z_\alpha^2 - 1)\mathcal{S} + \frac{1}{24}(z_\alpha^3 - 3z_\alpha)\mathcal{K} - \frac{1}{36}(2z_\alpha^3 - 5z_\alpha)\mathcal{S}^2$.
  2. Peaks-Over-Threshold (POT) fitting a Generalized Pareto Distribution (GPD):
     $F_u(y) = 1 - \left(1 + \frac{\xi y}{\beta}\right)^{-1/\xi}$, yielding EVT VaR and EVT Expected Shortfall (CVaR).
  3. Tail risk constrained portfolio optimization minimizing Expected Shortfall under non-Gaussian tail parameters.
- **Dependencies:** Existing returns and risk analytics core.
- **Implementation Risks:** Threshold selection sensitivity ($u$) in POT; stability of MLE for GPD parameters $(\xi, \beta)$.
- **Acceptance Criteria:** Analytical GPD benchmark with known shape $\xi$ and scale $\beta$; Cornish-Fisher reduces to Gaussian quantile when skewness and excess kurtosis are 0; VaR/CVaR backtest coverage tests (Kupiec POF test); interactive React workspace.

---

## 4. Gate A Conclusion & Stop Condition

In strict accordance with **Non-Negotiable Rule 4** and **Rule 10**:
- Stage 20 implementation is **BLOCKED** pending explicit user selection and approval of one of the candidate scopes above.
- Zero production code for Stage 20 has been written.
- The repository remains fully operational, verified at 335 passing backend tests and 32 passing frontend tests.
