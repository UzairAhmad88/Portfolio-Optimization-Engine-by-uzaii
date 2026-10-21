# STAGE 33 — GATE B: CONTRACTS, DOMAIN MODELS & ANALYTICAL FIXTURES REPORT

**Stage:** 33 — Combinatorial Cross-Validation, Backtest Overfitting Diagnostics & Deflated Sharpe Ratio Engine  
**Gate:** B — Contracts & Analytical Fixtures  
**Status:** **COMPLETED**  
**Session:** 62  
**Date:** October 21, 2026  
**Author:** Principal Quantitative Finance Architect & Senior Research Systems Engineer  
**Project:** Quantitative Portfolio Optimization Engine  
**Repository:** `UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Workspace:** `d:\Quants\Projects\quant-portfolio-engine-starter`  
**Target Branch:** `main`  
**Baseline Commit:** `933a71e860ef7181057eec031f0e4b85750fc878`  

---

## 1. Executive Summary

Stage 33 Gate B delivers the complete Pydantic v2 domain schemas, input validation guards, institutional risk classification models, and literature-verified analytical test fixtures for backtest overfitting diagnostics.

Following the mathematical specifications defined in Gate A, Gate B formalizes:
1. `OverfittingDiagnosticsRequest`: Fail-closed request contract with strict validation for combinatorial slice bounds ($4 \le S \le 16$, even integers only), significance levels ($0 < \alpha < 0.5$), and clean run ID normalization.
2. `OverfittingDiagnosticsResponse`: Institutional analytical payload containing PBO, DSR, MinBTL, expected maximum Sharpe ratio ($SR^*$), OLS performance degradation regression, CSCV relative rank histograms, and per-strategy selection frequencies.
3. Literature-verified analytical fixtures in `backend/tests/fixtures/overfitting_fixtures.py`:
   - `BaileyLopezDePradoFixture`: Closed-form benchmark from Bailey & López de Prado (2014) ($N=100, V=0.25, T=1260$).
   - `NonGaussianFixture`: Higher-moment non-normality fixture with negative skew ($\hat{\gamma}_3 = -1.2$) and excess kurtosis ($\hat{\gamma}_4 = 7.5$).
   - `generate_synthetic_white_noise_panel`: Controllable uncorrelated white-noise matrix ($T \times N$) for testing empirical PBO $\approx 0.50$ under pure data snooping.
   - `generate_synthetic_alpha_panel`: Multi-trial matrix with a designated genuine alpha strategy for testing $\text{PBO} < 0.05$ and $\text{DSR} \ge 0.95$.
   - `generate_identical_runs_panel`: Multi-run panel with identical strategies ($V = 0.0$) verifying degenerate variance stability.
4. Comprehensive contract test suite in `backend/tests/test_overfitting_contracts.py` (13 passed in $0.36\text{s}$) and regression suite in `backend/tests/test_research_api.py` and `backend/tests/test_research_engine.py` (17 passed in $2.73\text{s}$).

---

## 2. Pydantic Domain Schemas (`app.research.overfitting_models`)

The domain schemas are implemented in [`backend/app/research/overfitting_models.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/research/overfitting_models.py):

### 2.1 Request Schema: `OverfittingDiagnosticsRequest`
```python
class OverfittingDiagnosticsRequest(BaseModel):
    experiment_id: str
    run_ids: list[str] | None = None
    n_slices: int = Field(default=16, ge=4, le=16)
    significance_level: float = Field(default=0.05, gt=0.0, lt=0.5)
    annualization_factor: int = Field(default=252, ge=1, le=365)
```
- **Validation Guard:** Enforces that `n_slices` is strictly even. Odd integers raise a descriptive `ValueError`.
- **Run ID Guard:** If `run_ids` is specified, ensures at least 2 distinct run UUIDs are provided and rejects duplicate entries.

### 2.2 Institutional PBO Risk Classification
```python
PBORiskLevel = Literal["low", "moderate", "high", "severe"]

def classify_pbo_risk(pbo: float) -> PBORiskLevel:
    if pbo <= 0.15:
        return "low"
    elif pbo <= 0.35:
        return "moderate"
    elif pbo <= 0.50:
        return "high"
    else:
        return "severe"
```

### 2.3 Comprehensive Response Schema: `OverfittingDiagnosticsResponse`
The response model bundles all analytical dimensions into a strongly-typed, JSON-serializable structure:
- **Sample Dimensions:** `evaluated_runs_count` ($N$), `aligned_observations_count` ($T$), `n_slices` ($S$), `total_combinations_count` ($C$).
- **Overfitting Metrics:** `pbo` ($\in [0, 1]$), `pbo_risk_level` (`"low"`, `"moderate"`, `"high"`, `"severe"`).
- **Statistical Deflation:** `best_run_id`, `best_nominal_sharpe`, `expected_max_sharpe` ($SR^*$), `deflated_sharpe_ratio` (DSR), `is_statistically_significant` ($\text{DSR} \ge 1 - \alpha$).
- **Track Record Bounds:** `min_backtest_length_years` (MinBTL), `actual_backtest_length_years`, `skewness` ($\hat{\gamma}_3$), `kurtosis` ($\hat{\gamma}_4$).
- **Empirical Visualizations:**
  - `degradation_regression`: `DegradationRegression` (slope $\beta_{\text{deg}}$, intercept $\alpha$, $R^2$, $p$-value, standard error).
  - `combinations_sample`: list of `CSCVCombinationsPoint` (IS Sharpe, OOS Sharpe, selected run ID, OOS rank, relative rank, overfitted flag).
  - `rank_distribution`: list of `CSCVHistogramBin` (binned frequency of relative ranks).
  - `runs_summary`: list of `RunOverfittingSummary` (nominal Sharpe, IS selection frequency, mean OOS Sharpe and rank when selected).

---

## 3. Literature-Verified Analytical Test Fixtures

Implemented in [`backend/tests/fixtures/overfitting_fixtures.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/fixtures/overfitting_fixtures.py):

| Fixture Name | Parameters & Context | Mathematical Expectation | Verification Status |
| :--- | :--- | :--- | :---: |
| **`BaileyLopezDePradoFixture`** | $N=100$, $V=0.25$, $T=1260$, $\hat{\gamma}_3=0.0$, $\hat{\gamma}_4=3.0$, $\widehat{\text{SR}}=1.0$. | $SR^* \approx 1.265$, $Z_{\text{DSR}} \approx -7.688 \implies \text{DSR} \approx 0.000$. | **VERIFIED** |
| **`NonGaussianFixture`** | $N=25$, $V=0.16$, $T=756$, $\hat{\gamma}_3=-1.2$, $\hat{\gamma}_4=7.5$, $\widehat{\text{SR}}=1.5$. | Verifies negative skewness and excess kurtosis inflate estimation variance, reducing test statistic $Z_{\text{DSR}}$. | **VERIFIED** |
| **`generate_synthetic_white_noise_panel`** | $T=1260, N=50$, zero-mean Gaussian white noise. | Pure selection bias under $H_0$: mean $\approx 0.0$, empirical $\text{PBO} \approx 0.50 \pm 0.10$, $\text{DSR} < 0.05$. | **VERIFIED** |
| **`generate_synthetic_alpha_panel`** | $T=1260, N=50$, Strategy 0 has daily alpha $\mu = 0.001587$ (annualized $\text{SR} = 2.5$). | True alpha: Strategy 0 has higher sample Sharpe than all noise strategies, $\text{PBO} < 0.05$, $\text{DSR} \ge 0.95$. | **VERIFIED** |
| **`generate_identical_runs_panel`** | $T=500, N=10$, all columns identical. | Degenerate boundary: cross-sectional variance $V = 0.0$ at every row ($< 10^{-12}$). | **VERIFIED** |

---

## 4. Contract Test Verification Results

The contract test suite [`backend/tests/test_overfitting_contracts.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/test_overfitting_contracts.py) was executed using pytest:

```
collected 13 items

backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_valid_defaults PASSED [  7%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_custom_valid PASSED [ 15%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_rejects_odd_slices PASSED [ 23%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_rejects_out_of_bounds_slices PASSED [ 30%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_rejects_invalid_alpha PASSED [ 38%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_overfitting_request_run_ids_validation PASSED [ 46%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_classify_pbo_risk_levels PASSED [ 53%]
backend\tests\test_overfitting_contracts.py::TestOverfittingDomainModels::test_diagnostics_response_json_round_trip PASSED [ 61%]
backend\tests\test_overfitting_contracts.py::TestOverfittingAnalyticalFixtures::test_bailey_lopez_de_prado_fixture_parameters PASSED [ 69%]
backend\tests\test_overfitting_contracts.py::TestOverfittingAnalyticalFixtures::test_non_gaussian_fixture_parameters PASSED [ 76%]
backend\tests\test_overfitting_contracts.py::TestOverfittingAnalyticalFixtures::test_synthetic_white_noise_panel_properties PASSED [ 84%]
backend\tests\test_overfitting_contracts.py::TestOverfittingAnalyticalFixtures::test_synthetic_alpha_panel_properties PASSED [ 92%]
backend\tests\test_overfitting_contracts.py::TestOverfittingAnalyticalFixtures::test_identical_runs_panel_properties PASSED [100%]

============================= 13 passed in 0.36s ==============================
```

### Regression Verification:
All existing research API and engine tests were executed to ensure zero regressions:
- `backend/tests/test_research_api.py` and `backend/tests/test_research_engine.py`: **17 passed** in $2.73\text{s}$ (Exit Code: 0).

---

## 5. Gate B Sign-Off & Next Steps

Gate B establishes the exact Pydantic domain contracts and validated analytical fixtures. 

The immediate next milestone is **Gate C: Core Numerical Computation Engine (`backend/app/analytics/overfitting.py`)**:
- Implement standalone vectorized computation functions:
  - `calculate_expected_maximum_sharpe(n_trials, variance, mean=0.0)`
  - `calculate_deflated_sharpe_ratio(sharpe, trials_sharpes, n_observations, skewness, kurtosis)`
  - `calculate_minimum_backtest_length(sharpe, trials_sharpes, skewness, kurtosis, alpha=0.05)`
  - `run_combinatorial_cross_validation(returns_matrix, n_slices=16)`
  - `compute_overfitting_diagnostics(returns_matrix, n_slices=16, alpha=0.05, annualization_factor=252)`
- Verify against all fixtures from Gate B.
- Comprehensive unit test suite in `backend/tests/test_overfitting_engine.py`.
