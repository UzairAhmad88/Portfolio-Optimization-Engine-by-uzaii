# PERFORMANCE ATTRIBUTION & BENCHMARK EVALUATION CONTRACTS

## 1. Scope and Research Purpose

This document establishes the financial mathematics, statistical definitions, date-alignment policies, and attribution conventions for **Session 15: Portfolio Performance Attribution, Benchmark Analysis & Risk-Adjusted Performance Evaluation**.

The system is designed for quantitative investment research, strategy validation, and institutional risk oversight. All calculations are historical measurements and diagnostic metrics; they do not represent guarantees of future performance, forecast actual returns, or offer personalized investment recommendations.

---

## 2. Mathematical Definitions & Return Conventions

### 2.1 Return Measurement Convention
All returns are discrete simple arithmetic returns unless explicitly designated otherwise:
$$r_t = \frac{P_t - P_{t-1}}{P_{t-1}}$$
where $P_t$ is the adjusted closing price on trading day $t$.

- **Simple Compounding:** Multi-period cumulative return over horizon $t \in [1, T]$ is defined by compounding:
  $$R_{0:T} = \prod_{t=1}^T (1 + r_t) - 1$$
- **Gross vs. Net Portfolio Returns:**
  - **Net Returns ($r_{\text{net}, t}$):** Portfolio return after deducting basis-point transaction fees, slippage drag, and execution friction. Net return is the primary performance view.
  - **Gross Returns ($r_{\text{gross}, t}$):** Portfolio return based purely on asset price movements before transaction frictions.
  - Both series compound independently: $R_{\text{net}} = \prod (1 + r_{\text{net}, t}) - 1$, $R_{\text{gross}} = \prod (1 + r_{\text{gross}, t}) - 1$.
- **Benchmark Return ($r_{b, t}$):** Simple arithmetic return of the validated reference benchmark series.

### 2.2 Active Return & Excess Return Distinctions
We maintain strict separation between periodic active return, cumulative arithmetic active return, and compounded excess return:
1. **Periodic Active Return ($a_t$):**
   $$a_t = r_{p, t} - r_{b, t}$$
2. **Cumulative Arithmetic Active Return ($\Delta R$):**
   $$\Delta R = R_p - R_b$$
   The direct arithmetic difference between the cumulative portfolio return and cumulative benchmark return.
3. **Compounded Geometric Excess Return ($R_{\text{excess}}$):**
   $$R_{\text{excess}} = \frac{1 + R_p}{1 + R_b} - 1$$
   Reflects the relative wealth ratio ($V_{p, T} / V_{b, T} - 1$) under equal starting capital.
4. **Important Mathematical Disambiguation:**
   $$\prod_{t=1}^T (1 + a_t) - 1 \ne R_p - R_b$$
   The compounded active return of the periodic difference series $a_t$ does not equal the difference between compounded portfolio and benchmark returns. Both figures must be reported with explicit labeling.

---

## 3. Date Alignment, Missing Observations & Currency Policy

### 3.1 Date Alignment Policy
- Portfolio returns $\{r_{p, t}\}$ and benchmark returns $\{r_{b, t}\}$ must be synchronized via an **exact inner join on trading calendar dates**.
- Observation count $N = |\{t : t \in \mathcal{D}_p \cap \mathcal{D}_b\}|$.
- Minimum required observations: $N \ge 3$ for variance/covariance, and $N \ge 20$ for robust regression statistics (Beta, Alpha).

### 3.2 Missing Observation & Imputation Prohibition
- **Zero Imputation:** The engine will **never** forward-fill, backward-fill, or synthesize missing benchmark or portfolio observations.
- Dates where either the portfolio or benchmark lacks an empirical price/return are excluded from the comparative sample, and the effective aligned date range is explicitly reported.

### 3.3 Homogeneous Currency Policy
- Cross-currency performance comparison (e.g., USD portfolio against PKR benchmark) is **strictly prohibited** without an approved, audited FX rate conversion contract.
- Any request attempting multi-currency comparison without matching currencies returns HTTP 422 with a structured error explanation.

---

## 4. Asset-Level Return Contribution

### 4.1 Single-Period Contribution
For a portfolio holding $N$ assets with beginning-of-period weights $\mathbf{w}_{t-1} = [w_{1, t-1}, \dots, w_{N, t-1}]^T$ and asset simple returns $\mathbf{r}_t = [r_{1, t}, \dots, r_{N, t}]^T$, the asset-level contribution $c_{i, t}$ is:
$$c_{i, t} = w_{i, t-1} \cdot r_{i, t}$$

Under a fully invested cash-neutral portfolio:
$$r_{p, t} = \sum_{i=1}^N c_{i, t}$$
If cash $C_{t-1}$ earning return $r_{c, t}$ is held, portfolio return reconciles as:
$$r_{p, t} = \sum_{i=1}^N c_{i, t} + w_{\text{cash}, t-1} r_{c, t}$$

### 4.2 Multi-Period Contribution & Linking Methodology
In multi-period compounding, simple summation of periodic contributions $\sum_{t=1}^T c_{i, t}$ does not equal the cumulative portfolio return $R_p = \prod_{t=1}^T (1 + r_{p, t}) - 1$ because of compounding cross-product effects.

To preserve exact additive reconciliation ($\sum_{i=1}^N C_i = R_p$), we implement the **Menchero (2000) Logarithmic Linking Algorithm**:
1. For each period $t$, compute the linking coefficient $L_t$:
   $$L_t = \begin{cases} \frac{\ln(1 + r_{p, t})}{r_{p, t}} \cdot \frac{R_p}{\ln(1 + R_p)} & \text{if } r_{p, t} \ne 0 \text{ and } R_p \ne 0 \\ 1.0 & \text{if } r_{p, t} = 0 \text{ or } R_p = 0 \end{cases}$$
2. The linked multi-period contribution $C_i$ for asset $i$ is:
   $$C_i = \sum_{t=1}^T L_t \cdot c_{i, t}$$
3. **Exact Reconciliation Property:**
   $$\sum_{i=1}^N C_i = R_p \pm 10^{-6}$$
   Every performance report verifies this identity and logs the reconciliation residual $\epsilon = |R_p - \sum C_i|$.

---

## 5. Brinson Attribution — Conditional Scope Decision

- **Brinson-Fachler / Brinson-Hood-Beebower Attribution** decomposes excess return into:
  - Allocation Effect: $\sum_j (w_{p, j} - w_{b, j}) (R_{b, j} - R_b)$
  - Selection Effect: $\sum_j w_{b, j} (R_{p, j} - R_{b, j})$
  - Interaction Effect: $\sum_j (w_{p, j} - w_{b, j}) (R_{p, j} - R_{b, j})$
- **Data Prerequisite:** Requires complete historical time-series of **benchmark constituent weights** $w_{b, j}$ and constituent sector classifications.
- **Repository Audit Finding:** The current dataset registry stores prices of traded assets and single index benchmarks; it does not store constituent weighting tables or industry classifications of external market indices (such as S&P 500 or KSE 100).
- **Integrity Rule:** In compliance with instructions, the system **does not fabricate or approximate benchmark weights**. Brinson allocation and selection is marked as `deferred_pending_benchmark_constituents`. Asset-level return contribution analysis is the authoritative attribution method.

---

## 6. Risk-Adjusted Performance Metrics

All risk-adjusted metrics assume annualization factor $m = 252$ trading days per year.

### 6.1 Annualized Tracking Error ($TE$)
Tracking Error measures the volatility of periodic active returns:
$$TE = \sqrt{m} \cdot \sqrt{\frac{1}{N - 1} \sum_{t=1}^N (a_t - \overline{a})^2}$$
where $\overline{a} = \frac{1}{N} \sum_{t=1}^N a_t$. If $N < 2$ or $\operatorname{Var}(a_t) = 0$, $TE = 0.0$.

### 6.2 Information Ratio ($IR$)
The Information Ratio measures excess return per unit of active risk:
$$IR = \frac{\overline{a} \cdot m}{TE}$$
If $TE = 0$ or $N < 3$, $IR$ is reported as `None` (undefined) with an explanatory flag.

### 6.3 Portfolio Beta ($\beta$)
$$\beta = \frac{\operatorname{Cov}(r_p, r_b)}{\operatorname{Var}(r_b)} = \frac{\sum_{t=1}^N (r_{p, t} - \overline{r}_p)(r_{b, t} - \overline{r}_b)}{\sum_{t=1}^N (r_{b, t} - \overline{r}_b)^2}$$
If $\operatorname{Var}(r_b) \le 10^{-12}$ (e.g. constant benchmark price), $\beta$ is reported as `None`.

### 6.4 Jensen's Alpha ($\alpha$)
Jensen's Alpha measures average return in excess of the CAPM benchmark return:
$$\alpha_{\text{periodic}} = (\overline{r}_p - \overline{r}_f) - \beta (\overline{r}_b - \overline{r}_f)$$
$$\alpha_{\text{annualized}} = \alpha_{\text{periodic}} \cdot m$$
where $\overline{r}_f$ is the periodic risk-free rate.

### 6.5 Treynor Ratio
$$\text{Treynor} = \frac{(\overline{r}_p - \overline{r}_f) \cdot m}{\beta}$$
If $\beta = 0$ or undefined, Treynor Ratio is reported as `None`.

### 6.6 Up-Market and Down-Market Capture Ratios
1. **Up-Market Periods:** $\mathcal{T}_{\text{up}} = \{t : r_{b, t} > 0\}$
   $$\text{Up-Capture} = \frac{R_{p, \text{up}}}{R_{b, \text{up}}} = \frac{\prod_{t \in \mathcal{T}_{\text{up}}} (1 + r_{p, t}) - 1}{\prod_{t \in \mathcal{T}_{\text{up}}} (1 + r_{b, t}) - 1}$$
2. **Down-Market Periods:** $\mathcal{T}_{\text{down}} = \{t : r_{b, t} < 0\}$
   $$\text{Down-Capture} = \frac{R_{p, \text{down}}}{R_{b, \text{down}}} = \frac{\prod_{t \in \mathcal{T}_{\text{down}}} (1 + r_{p, t}) - 1}{\prod_{t \in \mathcal{T}_{\text{down}}} (1 + r_{b, t}) - 1}$$
A ratio $> 1.0$ in up-markets indicates outperformance on positive days; a ratio $< 1.0$ in down-markets indicates downside protection.

### 6.7 Reused Performance Metrics
The performance module directly reuses audited functions from `backend/app/quant/risk.py`:
- `annualized_return(returns, periods_per_year=252)`
- `annualized_volatility(returns, periods_per_year=252)`
- `sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=252)`
- `sortino_ratio(returns, risk_free_rate=0.0, periods_per_year=252)`
- `maximum_drawdown(returns)`
- `annual_to_periodic_rate(annual_rate, periods_per_year=252)`:
  $$r_{\text{periodic}} = (1 + R_f)^{1/m} - 1$$

---

## 7. Numerical Precision & Output Constraints

1. **Floating Point Precision:** IEEE 754 64-bit double precision (`float64`).
2. **Deterministic Reproducibility:** Identical portfolio and benchmark series must yield bitwise identical metrics across platforms.
3. **Reconciliation Tolerance:** Multi-period asset contribution must satisfy $|\sum C_i - R_p| \le 10^{-5}$.
4. **Bounds Enforcement:** Active return series, cumulative trajectories, and drawdowns are validated for finite real numbers (`np.isfinite`).
