# SESSION 24 CONTRACTS & SPECIFICATION

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 24  
**Stage:** Stage 20 — Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting  
**Status:** APPROVED BY USER (Gate A Cleared)  
**Date:** 2026-10-18  

---

## 1. Problem Statement & Exclusions

### 1.1 Problem Statement
Financial asset returns and cross-asset correlations exhibit pronounced regime dependency. Market environments shift between periods of sustained low volatility with positive trend (expansion/bull regimes) and sudden high-volatility, crash-prone states with heightened correlation breakdown (turbulent/crisis regimes). Static portfolio optimization or naive rolling historical windows suffer from severe look-ahead lag, maintaining excessive risk during sudden market breaks and failing to de-risk before catastrophic drawdowns occur.

Stage 20 resolves this by introducing:
1. **Gaussian Hidden Markov Models (HMM):** Estimation of discrete latent regimes ($M \in \{2, 3\}$ states) via the Expectation-Maximization (Baum-Welch) algorithm, computing state transition matrices ($A$), state mean returns ($\mu_k$), and state covariance matrices ($\Sigma_k$).
2. **Causal Forward Filtering (Zero Look-Ahead):** Recursive computation of filtered regime probabilities $\pi_{k,t} = \mathbb{P}(S_t = k \mid r_{1:t})$ ensuring allocations at time $t$ use strictly causal historical observations without future leakage.
3. **Regime-Conditioned Covariance Blending:** Dynamic synthesis of expected returns and risk matrices conditioned on instantaneous regime belief vectors:
   $$\Sigma_t^{\text{blended}} = \sum_{k=1}^M \pi_{k,t} \left[\Sigma_k + (\mu_k - \mu_t^{\text{blended}})(\mu_k - \mu_t^{\text{blended}})^\top\right]$$
4. **Dynamic Volatility Targeting Overlay:** Continuous scaling of portfolio risk exposure ($k_t = \min(\text{Lev}_{\max}, \sigma_{\text{target}} / \hat{\sigma}_t)$) into cash or leverage to stabilize realized portfolio volatility across volatile market regimes.
5. **Interactive Institutional Workspace:** Tabbed visualization comparing regime posterior curves, transition heatmaps, volatility target exposure scalers, and walk-forward equity/drawdown backtests.

### 1.2 Explicit Exclusions
- High-frequency intraday regime switching (this engine targets daily discrete bars).
- Continuous-time jump-diffusion processes with non-Markovian memory.
- Unbounded leverage ($k_t$ is strictly bounded by user-configured $\text{Lev}_{\max} \le 2.0$).
- Automatic live broker execution (the platform remains an institutional research and simulation engine).

---

## 2. Mathematical Formulations & Notation

### 2.1 Hidden Markov Model Specification
- Let $r_t \in \mathbb{R}^N$ be the vector of asset returns at time $t \in \{1, \dots, T\}$.
- Latent state $S_t \in \{1, \dots, M\}$ with $M \in \{2, 3\}$.
- Initial state distribution: $\pi = [\pi_1, \dots, \pi_M]^\top$, with $\sum_{i=1}^M \pi_i = 1$.
- Transition probability matrix: $A \in \mathbb{R}^{M \times M}$, where:
  $$A_{ij} = \mathbb{P}(S_t = j \mid S_{t-1} = i), \quad \sum_{j=1}^M A_{ij} = 1, \quad \forall i$$
- State emission distributions (Gaussian):
  $$r_t \mid S_t = i \sim \mathcal{N}(\mu_i, \Sigma_i)$$
  where $\mu_i \in \mathbb{R}^N$ and $\Sigma_i \in \mathbb{R}^{N \times N}$ is symmetric positive semi-definite.
- **Label-Switching Resolution:** Regimes are deterministically sorted by total volatility ($\operatorname{Tr}(\Sigma_1) < \operatorname{Tr}(\Sigma_2) < \dots < \operatorname{Tr}(\Sigma_M)$), guaranteeing that State 1 is always the Low-Volatility / Calm regime and State $M$ is the High-Volatility / Turbulent regime.

### 2.2 Forward-Backward Scaling Algorithm (Numerical Stability)
To prevent numerical underflow over long horizons ($T > 100$):
1. **Forward Pass (Filtered Causal Probabilities):**
   $$\alpha_1(i) = \pi_i b_i(r_1), \quad c_1 = \frac{1}{\sum_{i=1}^M \alpha_1(i)}, \quad \hat{\alpha}_1(i) = c_1 \alpha_1(i)$$
   For $t = 2, \dots, T$:
   $$\alpha_t(j) = \left[\sum_{i=1}^M \hat{\alpha}_{t-1}(i) A_{ij}\right] b_j(r_t), \quad c_t = \frac{1}{\sum_{j=1}^M \alpha_t(j)}, \quad \hat{\alpha}_t(j) = c_t \alpha_t(j)$$
   **Filtered Probability at time $t$:** $\mathbb{P}(S_t = j \mid r_1, \dots, r_t) = \hat{\alpha}_t(j)$.
2. **Backward Pass (Smoothed Full-Sample Probabilities):**
   $$\hat{\beta}_T(i) = 1.0$$
   For $t = T-1, \dots, 1$:
   $$\beta_t(i) = \sum_{j=1}^M A_{ij} b_j(r_{t+1}) \hat{\beta}_{t+1}(j), \quad \hat{\beta}_t(i) = c_{t+1} \beta_t(i)$$
   **Smoothed Probability:** $\gamma_t(i) = \mathbb{P}(S_t = i \mid r_1, \dots, r_T) = \hat{\alpha}_t(i) \hat{\beta}_t(i)$.
3. **Viterbi Algorithm:**
   Computes the globally optimal state trajectory $S_{1:T}^* = \arg\max_{S_{1:T}} \mathbb{P}(S_{1:T} \mid r_{1:T})$.

### 2.3 Regime-Conditioned Portfolio Construction
At decision date $t$, using causal filtered state probabilities $p_{k,t} = \hat{\alpha}_t(k)$:
$$\mu_t^{\text{blended}} = \sum_{k=1}^M p_{k,t} \mu_k$$
$$\Sigma_t^{\text{blended}} = \sum_{k=1}^M p_{k,t} \left[\Sigma_k + (\mu_k - \mu_t^{\text{blended}})(\mu_k - \mu_t^{\text{blended}})^\top\right]$$
The allocator optimizes base risky weights $w_t^* \in \mathbb{R}^N$ via SLSQP quadratic programming:
$$\min_w \frac{1}{2} w^\top \Sigma_t^{\text{blended}} w - \frac{1}{\gamma} w^\top \mu_t^{\text{blended}}$$
subject to $\sum_{i=1}^N w_i = 1$, $w_{\min} \le w_i \le w_{\max}$.

### 2.4 Dynamic Volatility Targeting Overlay
Given target annualized volatility $\sigma_{\text{target}}$ (e.g. $10\%$), maximum leverage $\text{Lev}_{\max}$ (e.g. $1.5$), and estimated annualized portfolio volatility $\hat{\sigma}_{p,t} = \sqrt{252 \cdot (w_t^{*\top} \Sigma_t^{\text{blended}} w_t^*)}$:
- Risk scaling factor:
  $$k_t = \min\left(\text{Lev}_{\max}, \frac{\sigma_{\text{target}}}{\hat{\sigma}_{p,t}}\right)$$
- Targeted risky weights:
  $$w_{i,t}^{\text{targeted}} = k_t \cdot w_{i,t}^*$$
- Cash buffer / borrowing:
  $$w_{\text{cash},t} = 1.0 - \sum_{i=1}^N w_{i,t}^{\text{targeted}} = 1.0 - k_t$$
  - When $k_t < 1.0$: Portfolio de-risks by holding $w_{\text{cash},t} > 0$ in risk-free cash earning $r_f / 252$.
  - When $k_t > 1.0$: Portfolio levers up, borrowing at cash rate $(r_f + c_{\text{borrow}}) / 252$.

---

## 3. Independent Hand-Calculated Analytical Benchmark

To guarantee mathematical correctness without circular test assertions, the following 2-state HMM test case is evaluated analytically:

### Benchmark Setup
- $M = 2$ states: State 1 (Low Vol), State 2 (High Vol)
- $\pi = [0.80, 0.20]^\top$
- Transition Matrix:
  $$A = \begin{pmatrix} 0.90 & 0.10 \\ 0.20 & 0.80 \end{pmatrix}$$
- Emission Parameters (daily returns):
  - State 1: $\mu_1 = +0.0010$, $\sigma_1 = 0.0100$
  - State 2: $\mu_2 = -0.0020$, $\sigma_2 = 0.0300$
- Observations: $r_1 = +0.0050$, $r_2 = -0.0350$
- Volatility Target: $\sigma_{\text{target}} = 0.10$ annualized ($10\%$), $\text{Lev}_{\max} = 1.50$

### Step-by-Step Analytical Derivation:
1. **$t = 1$ ($r_1 = +0.0050$):**
   $$b_1(r_1) = \frac{1}{0.01 \sqrt{2\pi}} \exp\left(-\frac{(0.005 - 0.001)^2}{2 \times 0.01^2}\right) = 39.894228 \times \exp(-0.08) \approx 36.827014$$
   $$b_2(r_1) = \frac{1}{0.03 \sqrt{2\pi}} \exp\left(-\frac{(0.005 - (-0.002))^2}{2 \times 0.03^2}\right) = 13.298076 \times \exp(-0.027222) \approx 12.940956$$
   $$\alpha_1^{\text{raw}} = [0.80 \times 36.827014, 0.20 \times 12.940956] = [29.461611, 2.588191]$$
   $$c_1 = \frac{1}{29.461611 + 2.588191} = \frac{1}{32.049802} \approx 0.03120144$$
   $$\hat{\alpha}_1 = [\mathbf{0.91924471}, \mathbf{0.08075529}]$$
   *Interpretation:* Positive return decisively identifies the Low-Volatility State ($91.92\%$).
   Daily portfolio volatility at $t=1$:
   $$\sigma_{1,\text{daily}} = \sqrt{0.91924471 \times 0.01^2 + 0.08075529 \times 0.03^2} = \sqrt{0.0001646} \approx 0.01282982$$
   $$\sigma_{1,\text{ann}} = 0.01282982 \times \sqrt{252} \approx 0.20366705\quad (20.37\%)$$
   Exposure scaling factor:
   $$k_1 = \min\left(1.50, \frac{0.10}{0.20366705}\right) = \mathbf{0.49099744}$$

2. **$t = 2$ ($r_2 = -0.0350$):**
   $$\alpha_2^{\text{pred}}(1) = 0.91924471 \times 0.90 + 0.08075529 \times 0.20 = 0.82732024 + 0.01615106 = 0.84347130$$
   $$\alpha_2^{\text{pred}}(2) = 0.91924471 \times 0.10 + 0.08075529 \times 0.80 = 0.09192447 + 0.06460423 = 0.15652870$$
   $$b_1(r_2) = \frac{1}{0.01 \sqrt{2\pi}} \exp\left(-\frac{(-0.035 - 0.001)^2}{2 \times 0.01^2}\right) = 39.894228 \times \exp(-6.48) \approx 0.06119019$$
   $$b_2(r_2) = \frac{1}{0.03 \sqrt{2\pi}} \exp\left(-\frac{(-0.035 - (-0.002))^2}{2 \times 0.03^2}\right) = 13.298076 \times \exp(-0.605) \approx 7.26173923$$
   $$\alpha_2^{\text{raw}} = [0.84347130 \times 0.06119019, 0.15652870 \times 7.26173923] = [0.05161217, 1.13667054]$$
   $$c_2 = \frac{1}{0.05161217 + 1.13667054} = \frac{1}{1.18828271} \approx 0.84155059$$
   $$\hat{\alpha}_2 = [\mathbf{0.04343425}, \mathbf{0.95656575}]$$
   *Interpretation:* Crash return shifts probability overwhelmingly to the High-Volatility State ($95.66\%$).
   Daily portfolio volatility at $t=2$:
   $$\sigma_{2,\text{daily}} = \sqrt{0.04343425 \times 0.01^2 + 0.95656575 \times 0.03^2} = \sqrt{0.00086525} \approx 0.02941518$$
   $$\sigma_{2,\text{ann}} = 0.02941518 \times \sqrt{252} \approx 0.46695145\quad (46.70\%)$$
   Exposure scaling factor:
   $$k_2 = \min\left(1.50, \frac{0.10}{0.46695145}\right) = \mathbf{0.21415503}$$

The numerical test suite must verify these figures to within $< 10^{-8}$ tolerance.

---

## 4. API & Integration Contracts

### 4.1 Endpoint: `POST /api/v1/regime-switching/detect`
Performs HMM regime detection and state attribution over historical price data.
- **Request Body (`RegimeDetectionRequest`):**
  - `dataset_id`: str (required)
  - `tickers`: list[str] (optional; defaults to all assets in dataset)
  - `num_states`: int (2 or 3, default: 2)
  - `max_iter`: int (default: 100)
  - `tolerance`: float (default: 1e-4)
- **Response Body (`RegimeDetectionResponse`):**
  - `num_states`: int
  - `state_labels`: list[str] (e.g. `["Low Volatility (Bull)", "High Volatility (Bear)"]`)
  - `transition_matrix`: list[list[float]]
  - `state_means`: list[float]
  - `state_volatilities`: list[float]
  - `current_state`: int
  - `current_regime_probabilities`: list[float]
  - `timeline`: list[dict] (date, returns, state, filtered_probs, smoothed_probs)

### 4.2 Endpoint: `POST /api/v1/regime-switching/backtest`
Executes chronological walk-forward backtesting with regime-switching allocation and volatility targeting.
- **Request Body (`RegimeBacktestRequest`):**
  - `dataset_id`: str (required)
  - `tickers`: list[str] (required)
  - `num_states`: int (default: 2)
  - `target_volatility`: float (e.g. 0.10 for 10% ann vol)
  - `max_leverage`: float (default: 1.5, max: 2.0)
  - `rebalance_frequency`: Literal["daily", "weekly", "monthly"]
  - `transaction_cost_bps`: float (default: 10.0)
- **Response Body (`RegimeBacktestResponse`):**
  - `summary`: dict (CAGR, Volatility, Sharpe, Sortino, Max Drawdown, Turnover)
  - `equity_curve`: list[dict] (date, portfolio_equity, benchmark_equity, cash_weight, leverage, regime_state)
  - `regime_statistics`: dict (time spent per regime, average transition frequency)

---

## 5. Security & Resource Bounds

1. **Authentication:** All routes require active researcher JWT Bearer token or session cookie (`get_current_user`).
2. **Tenant Isolation:** Validates `dataset_id` access using `check_dataset_access(dataset_id, user.id, db)`.
3. **Resource Bounds:** `num_states` limited to $\{2, 3\}$, `max_iter` limited to 500, `max_leverage` bounded in $[1.0, 2.0]$.
4. **Data Verification:** Minimum history required: $T \ge 60$ trading days for reliable EM convergence.
