# SESSION 28 AUDIT — STAGE 22 INDEPENDENT QUANTITATIVE INTEGRITY & ARCHITECTURAL AUDIT

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 28  
**Audited Stage:** Stage 22 — Copula-Based Tail Dependency, Non-Linear Extreme Co-Movement & Tail Risk Parity Allocation  
**Audit Date:** 2026-10-19  
**Auditor:** Senior Quantitative-Finance Researcher, Computational Statistician & Software Quality Auditor  
**Alembic Migration Head:** `b2c3d4e5f6a7 (head)` (Verified via `.venv\Scripts\alembic.exe current`)  
**Actual Test Execution Results:**
- Backend Regression Suite: **372 passed**, 6 warnings in 49.88s
- Focused Copula Suite (`test_copula_tail_risk_engine.py`, `test_copula_tail_risk_api.py`): **13 passed**, 1 warning in 2.31s
- Frontend Vitest Suite: **38 passed** across 2 test files in 9.75s
- Frontend Production Build: Clean (`tsc -b && vite build` completed in 2.21s, exit code 0)

---

## 1. Executive Summary & Audit Scope

This audit independently reviews the Stage 22 implementation completed in Session 27. The scope encompasses:
1. Sklar's theorem pseudo-observation transformations and parametric marginal estimation.
2. Canonical Maximum Likelihood (CML) estimators for bivariate Clayton, Gumbel, Student-t, and Gaussian copulas.
3. Multivariate dependent return simulation algorithms and joint distribution validity for $N \ge 3$ assets.
4. Portfolio Copula-CVaR ($\text{CVaR}_\alpha$) and Euler tail risk contributions ($TRC_i$).
5. Tail Risk Parity (TRP) allocation objective, SLSQP solver constraints, and baseline comparisons.
6. Multi-tenant API security, Pydantic v2 schemas, and React 19 institutional frontend workspace.

---

## 2. Code Paths & Components Inspected

| Component | Repository Path | Inspection Focus |
|---|---|---|
| **Numerical Core** | `backend/app/quant/copula_tail_risk.py` (771 LOC) | Mathematical formulas, estimators, simulation generators, Euler decomposition, SLSQP TRP solver. |
| **Service Layer** | `backend/app/copula/service.py` (246 LOC) | Multi-tenant dataset retrieval, simple returns `.dropna()`, ticker mapping, orchestration. |
| **Pydantic Schemas** | `backend/app/copula/models.py` (98 LOC) | Request/response models, field bounds, type literals, alias mappings. |
| **API Endpoints** | `backend/app/api/v1/copula_routes.py` (90 LOC) | Route definitions, JWT dependency injection, DB session management. |
| **Router Registry**| `backend/app/api/v1/routes.py` | Inclusion of `copula_router`, health check stage verification. |
| **Engine Tests** | `backend/tests/test_copula_tail_risk_engine.py` (174 LOC) | Closed-form benchmarks, simulation seed reproducibility, Euler identity, TRP constraints. |
| **API Tests** | `backend/tests/test_copula_tail_risk_api.py` (227 LOC) | 401 unauthenticated checks, cross-tenant 403/404 isolation, payload validation. |
| **Frontend UI** | `frontend/src/components/pages/CopulaTailRiskPage.tsx` (721 LOC) | Heatmap matrix, pairwise table, simulation view, allocation charts, UX states. |
| **Frontend API** | `frontend/src/api/client.ts` & `frontend/src/types/api.ts` | Axios client methods and TypeScript interface contracts. |

---

## 3. Audit A — Copula Modeling and Multivariate Validity

### 3.1 Marginal Transformations
- **Empirical Pseudo-Observations:**
  $$\hat{u}_{i,t} = \frac{\operatorname{rank}(R_{i,t})}{T + 1}$$
  - Evaluated using `scipy.stats.rankdata(col, method="average") / (T + 1.0)`.
  - For sample size $T$, $\hat{u}_{i,t} \in \left[\frac{1}{T+1}, \frac{T}{T+1}\right] \subset (0, 1)$. Boundary singularities at $0$ and $1$ are strictly avoided.
  - Average rank method resolves ties symmetrically without distorting marginal probabilities.
  - Guard conditions: rejects non-finite observations (`np.all(np.isfinite(col))`), rejects constant series ($\operatorname{std}(col) < 10^{-12}$), and rejects degenerate samples ($T < 10$ in core, $T < 15$ in service).
- **Parametric Student-t Marginals:**
  $$\hat{u}_{i,t} = t_{\hat{\nu}}\left(\frac{R_{i,t} - \hat{\mu}}{\hat{\sigma}}\right)$$
  - Parameters fitted via maximum likelihood with degrees of freedom constrained to $\hat{\nu} \ge 2.1$.
  - Probabilities clipped to $[10^{-6}, 1 - 10^{-6}]$ to prevent overflow in subsequent inverse CDF transforms.
  - Graceful fallback: defaults to empirical ranks if parametric MLE fails.
  - Look-ahead leakage check: Estimation operates strictly on historical in-sample training arrays without incorporating subsequent observations.
- **Return Differencing:** Daily simple returns computed via `app.quant.returns.simple_returns` with explicit `.dropna()` removing the initial differencing NaN.

---

### 3.2 Bivariate Estimation & Tail Dependence Benchmarks

Independent mathematical calculations were verified against closed-form benchmarks:

#### 1. Clayton Copula ($\theta > 0$)
- **Closed-Form Expressions:**
  $$C_\theta(u, v) = (u^{-\theta} + v^{-\theta} - 1)^{-1/\theta}, \qquad \lambda_L = 2^{-1/\theta}, \quad \lambda_U = 0$$
- **Benchmark Test Case:** $\tau = 0.50 \implies \theta = \frac{2\tau}{1 - \tau} = 2.0$:
  $$\lambda_L = 2^{-1/2} = \frac{1}{\sqrt{2}} \approx 0.7071067812, \qquad \lambda_U = 0.0$$
- **Engine Output:** $\lambda_L = 0.7071067812$ (residual error $< 10^{-12}$).
- **Estimation:** CML optimization over $\theta \in [0.01, 40.0]$ with Kendall's tau inversion initialization.

#### 2. Gumbel Copula ($\theta \ge 1$)
- **Closed-Form Expressions:**
  $$C_\theta(u, v) = \exp\left( - \left[ (-\ln u)^\theta + (-\ln v)^\theta \right]^{1/\theta} \right), \qquad \lambda_L = 0, \quad \lambda_U = 2 - 2^{1/\theta}$$
- **Benchmark Test Case:** $\tau = 0.50 \implies \theta = \frac{1}{1 - \tau} = 2.0$:
  $$\lambda_L = 0.0, \qquad \lambda_U = 2 - \sqrt{2} \approx 0.5857864376$$
- **Engine Output:** $\lambda_U = 0.5857864376$ (residual error $< 10^{-12}$).
- **Estimation:** CML optimization over $\theta \in [1.0, 40.0]$ with Kendall's tau inversion initialization.

#### 3. Student-t Copula ($\nu > 2$)
- **Closed-Form Expression:**
  $$\lambda_L = \lambda_U = 2 t_{\nu+1}\left( -\sqrt{\frac{(\nu + 1)(1 - \rho)}{1 + \rho}} \right)$$
- **Benchmark Test Case:** $\rho = 0.50, \nu = 4.0$:
  $$\text{Argument} = -\sqrt{\frac{5(0.5)}{1.5}} = -\sqrt{\frac{5}{3}} \approx -1.29099445$$
  $$\lambda = 2 t_5(-1.29099445) \approx 0.2581688124$$
- **Engine Output:** $\lambda = 0.2581688124$ (residual error $< 10^{-8}$).
- **Estimation:** Bivariate CML optimization over $\rho \in (-0.99, 0.99)$ and $\nu \in (2.1, 35.0)$.

#### 4. Gaussian Copula Baseline
- **Closed-Form Expression:** $\lambda_L = \lambda_U = 0.0$ for $|\rho| < 1$.
- **Engine Output:** Exactly $0.0$.

#### 5. Model Selection (AIC / BIC)
- All four candidate copulas compute the log-likelihood of their bivariate density on the identical pseudo-observation sample $(u_{1,t}, u_{2,t})_{t=1}^T$.
- Model parameter counts: $k=1$ for Clayton, Gumbel, Gaussian; $k=2$ for Student-t ($\rho, \nu$).
- Likelihood constructions are mathematically comparable.

---

### 3.3 Critical Multivariate Construction Audit (Mandatory Audit Gate)

A critical requirement of Session 28 is to audit the joint distribution construction for $N \ge 3$ assets:

#### 1. Gaussian Copula Simulation ($N \ge 3$)
- **Implementation:** Evaluates full $N \times N$ correlation matrix on Gaussian scores $Z = \Phi^{-1}(U)$, applies eigenvalue clipping ($\lambda_{\min} \ge 10^{-6}$), computes Cholesky factor $L = \text{chol}(R_{\text{norm}})$, draws $Z_{\text{raw}} \sim \mathcal{N}(0, I)$, and sets $U_{\text{sim}} = \Phi(Z_{\text{raw}} L^\top)$.
- **Audit Verdict:** **VALID.** Proper multivariate Gaussian distribution with correct joint CDF.

#### 2. Student-t Copula Simulation ($N \ge 3$)
- **Implementation:** Evaluates median degrees of freedom $\bar{\nu}$ across asset pairs, constructs correlation matrix $R_t$, computes Cholesky factor $L$, generates correlated Gaussian vectors $Z_{\text{corr}} = Z_{\text{raw}} L^\top$.
- **Crucial Common Scale Mixture:** Draws a single scalar $\chi^2$ variable $S_m \sim \chi^2_{\bar{\nu}}$ per scenario $m \in \{1, \dots, M\}$ of dimension $(M, 1)$, and scales all $N$ assets by the same scalar $\sqrt{S_m / \bar{\nu}}$:
  $$X_m = \frac{Z_{\text{corr}, m}}{\sqrt{S_m / \bar{\nu}}}, \qquad U_{m, i} = t_{\bar{\nu}}(X_{m, i})$$
- **Audit Verdict:** **VALID.** Correct canonical multivariate Student-t scale-mixture generator.

#### 3. Clayton Copula Simulation ($N \ge 3$)
- **Implementation:** Employs Marshall-Olkin (1988) Archimedean generator using median parameter $\bar{\theta}$:
  1. Draws common latent frailty $V_m \sim \text{Gamma}(1/\bar{\theta}, 1)$ of dimension $(M, 1)$.
  2. Draws independent standard exponentials $E_{m, i} \sim \text{Exponential}(1)$ of dimension $(M, N)$.
  3. Evaluates $U_{m, i} = (1 + E_{m, i} / V_m)^{-1/\bar{\theta}}$.
- **Audit Verdict:** **VALID EXCHANGEABLE ARCHIMEDEAN CONSTRUCTION.**
  - The resulting joint CDF is:
    $$C(u_1, \dots, u_N) = \left( \sum_{i=1}^N u_i^{-\bar{\theta}} - N + 1 \right)^{-1/\bar{\theta}}$$
  - **Limitation Identified:** This formulation generates an *exchangeable* multivariate Clayton copula where every asset pair exhibits identical tail dependence $\lambda_L = 2^{-1/\bar{\theta}}$. It cannot model heterogeneous cross-asset tail correlations (which requires hierarchical Archimedean or vine copulas).

#### 4. Gumbel Copula Simulation ($N \ge 3$) — [CONFIRMED MODELING DEFECT]
- **Implementation (`copula_tail_risk.py` lines 544–566):**
  ```python
  elif copula_type == "gumbel":
      ...
      tau_target = 1.0 - 1.0 / avg_theta
      rho_gauss = math.sin(0.5 * math.pi * tau_target)
      R_gumbel = np.full((N, N), rho_gauss)
      np.fill_diagonal(R_gumbel, 1.0)
      L = np.linalg.cholesky(R_gumbel)
      z_raw = rng.standard_normal((num_simulations, N))
      z_corr = z_raw @ L.T
      U_sim = stats.norm.cdf(z_corr)
  ```
- **Audit Finding & Classification: [MATERIAL DEFECT — DEF-28-01]**
  - In `simulate_copula_returns`, when `copula_type == "gumbel"`, the engine does **not** sample from a multivariate Gumbel copula. Instead, it generates samples from an equicorrelated **Gaussian copula** with Kendall's tau matched to the Gumbel parameter.
  - **Mathematical Consequence:** A Gaussian copula has asymptotic upper tail dependence $\lambda_U = 0$. The simulated return sample therefore completely lacks the theoretical upper-tail comovement ($\lambda_U = 2 - 2^{1/\theta} > 0$) that the Gumbel model is designed to represent.
  - **Root Cause:** A proper multivariate Gumbel generator requires sampling a positive stable frailty variable $V \sim S(\alpha = 1/\theta, \beta = 1, \gamma = (\cos(\frac{\pi}{2\theta}))^\theta, \delta = 0)$ via the Chambers-Mallows-Stuck algorithm, or bivariate conditional quantile inversion. The previous implementation substituted a Gaussian proxy with matched Kendall's tau.

---

## 4. Audit B — Portfolio CVaR and Tail Risk Contributions

### 4.1 Loss Convention and Quantiles
- Portfolio loss defined as $L = -R_p = -\sum w_i R_i$.
- $\text{VaR}_\alpha = \text{quantile}_\alpha(L) = -\text{quantile}_{1-\alpha}(R_p)$.
- $\text{CVaR}_\alpha = \mathbb{E}[L \mid L \ge \text{VaR}_\alpha] = -\mathbb{E}[R_p \mid R_p \le -\text{VaR}_\alpha]$.
- Empirical tail selection: `tail_mask = losses >= var_alpha`.
- Positive loss convention is consistently maintained across backend, schemas, tests, and UI.

### 4.2 Euler Tail Risk Decomposition Identity
- Mathematical Euler contribution:
  $$TRC_i = w_i \frac{\partial \text{CVaR}_\alpha(w)}{\partial w_i} = -w_i \mathbb{E}[R_i \mid L \ge \text{VaR}_\alpha]$$
- Discrete sample verification:
  $$\sum_{i=1}^N TRC_i = \sum_{i=1}^N w_i \frac{1}{K} \sum_{m \in \text{Tail}} (-R_{m, i}) = \frac{1}{K} \sum_{m \in \text{Tail}} \left( -\sum_{i=1}^N w_i R_{m, i} \right) = \frac{1}{K} \sum_{m \in \text{Tail}} L_m \equiv \text{CVaR}_\alpha$$
- Verified numerically: residual error $\|\sum TRC_i - \text{CVaR}_\alpha\|_\infty < 10^{-12}$.

### 4.3 Tail Risk Parity (TRP) Allocation Objective
- Implemented objective:
  $$\min_{\mathbf{w}} \sum_{i=1}^N \left( \frac{TRC_i(\mathbf{w})}{\sum_{k=1}^N TRC_k(\mathbf{w})} - \frac{1}{N} \right)^2 \quad \text{s.t.} \quad \sum_{i=1}^N w_i = 1, \quad 0 \le w_i \le 1$$
- **Comparison with Session 26 Contract:**
  - Session 26 contract proposed $\min_w \sum_{i,j} (TRC_i - TRC_j)^2$ (absolute contribution dispersion).
  - The implementation uses relative contribution dispersion $\sum (TRC_i / \text{CVaR} - 1/N)^2$.
  - **Audit Evaluation:** Both objectives achieve exact risk parity when the objective is zero ($TRC_i = \text{CVaR}/N$). Relative dispersion is scale-invariant, avoiding numerical instability when portfolio CVaR is small.
  - **Limitation Identified:** If a portfolio contains short positions or extreme hedging assets where $\text{CVaR} \approx 0$ or $TRC_i < 0$, relative normalization can become non-monotonic. For long-only equity portfolios ($w_i \ge 0, R_i \text{ correlated}$), $\text{CVaR} > 0$ and $TRC_i > 0$ consistently.
- **Solver Invariants:**
  - Multi-start SLSQP (initialized at Equal-Weight $w_0 = 1/N$ and Inverse-Volatility $w_{\text{iv}}$).
  - Budget $\sum w_i = 1.0$ and non-negativity $w_i \ge 0$ strictly satisfied in all tests.
  - Fallback logic safely sets `converged=False` and returns $w_{\text{iv}}$ if SLSQP fails.

---

## 5. Audit C — Data, API, Security, and Frontend Review

1. **API Routes:**
   - `POST /api/v1/copula/fit`: Fits pairwise copulas; returns tail dependence matrix, Kendall's tau matrix, Pearson correlation matrix, pairwise metrics.
   - `POST /api/v1/copula/simulate`: Simulates multivariate copula returns; returns annualized means, volatilities, correlation matrix, sample scenarios.
   - `POST /api/v1/copula/tail-risk-parity`: Solves for TRP allocation; returns optimal weights, tail risk contributions, VaR, CVaR, reconciliation error, loss distribution samples, baseline comparisons.
   - `POST /api/v1/copula/optimize`: Alias endpoint pointing to `execute_tail_risk_parity`.
2. **Security & Tenant Isolation:**
   - Endpoints require JWT Bearer token authentication via `Depends(get_current_active_user)`.
   - Dataset ownership validated via `check_dataset_access(db, dataset_id, current_user)`.
   - Verified by tests: HTTP 401 on missing auth; HTTP 403/404 on cross-tenant access.
3. **Frontend Review (`CopulaTailRiskPage.tsx`):**
   - Three structured tabs: Diagnostics (Tail Dependence Matrix Heatmap, Pairwise Table), Simulation (Statistics & Scenario Preview), Allocation (TRP Weights, TRC Breakdown, Loss Histogram).
   - Proper empty, loading, error, and validation states.
   - Prominent methodology banner explicitly stating:
     *"Copula models do not eliminate crash risk, predict crises reliably, or guarantee superior out-of-sample portfolio performance."*

---

## 6. Confirmed Defects and Deficiencies Summary

| ID | Severity | Category | Description | Impact |
|---|---|---|---|---|
| **DEF-28-01** | **Medium** | Numerical / Simulation | Gumbel copula simulation in `simulate_copula_returns` (lines 544–566) uses an equicorrelated Gaussian copula proxy with matched Kendall's tau rather than sampling from a true Gumbel copula. | Simulated Gumbel returns exhibit zero upper tail dependence ($\lambda_U = 0$) instead of theoretical $\lambda_U = 2 - 2^{1/\theta}$. Clayton, Student-t, and Gaussian simulations are unaffected. |
| **DEF-28-02** | **Low** | Modeling Limitation | Multivariate Clayton copula uses an exchangeable Archimedean construction with scalar $\bar{\theta} = \text{median}(\theta_{ij})$, forcing identical pairwise dependence across all asset pairs. | In universes with heterogeneous asset correlations (e.g. Equities + Bonds + Gold), pairwise tail dependence in simulation is smoothed to a single median parameter. |

---

## 7. Recommended Remediation Plan

1. **Remediate DEF-28-01 (Gumbel Simulation):**
   - Implement the exact Chambers-Mallows-Stuck positive-stable distribution generator:
     $$V \sim S\left(\alpha = \frac{1}{\theta}, \beta = 1, \gamma = \left(\cos\frac{\pi}{2\theta}\right)^\theta, \delta = 0\right)$$
   - Generate independent unit exponentials $E_i \sim \text{Exp}(1)$ and set:
     $$U_i = \exp\left( - \left(\frac{E_i}{V}\right)^{1/\theta} \right)$$
   - This produces an exact exchangeable multivariate Gumbel copula with true upper tail dependence.
2. **Remediate DEF-28-02 (Heterogeneous High-Dimensional Dependence):**
   - Address in Stage 23 by introducing Regular Vine Copula (R-Vine / C-Vine / D-Vine) tree structures, enabling fully heterogeneous pairwise copula families and parameters across arbitrary dimensions.

---

## 8. Audit Verdict

Stage 22 demonstrates high quantitative rigor, exact closed-form benchmark validation, robust tenant isolation, and a complete institutional user workspace. The single confirmed numerical defect in Gumbel simulation (DEF-28-01) and the exchangeable limitation (DEF-28-02) are clearly documented and isolated.
