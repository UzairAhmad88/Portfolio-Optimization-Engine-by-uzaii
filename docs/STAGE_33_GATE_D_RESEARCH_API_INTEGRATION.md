# Stage 33 — Gate D: Research Lab Integration, Data Alignment & REST API Endpoints

**Role:** Principal Quantitative Software Architect, Senior Backend Engineer, Quantitative Research Engineer, API Contract Auditor, and QA Lead.  
**Project:** Quantitative Finance & Portfolio Optimization Engine  
**Repository:** `UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Workspace:** `d:\Quants\Projects\quant-portfolio-engine-starter`  
**Branch:** `main`  
**Stage:** 33 — Combinatorial Cross-Validation, Backtest Overfitting Diagnostics & Deflated Sharpe Ratio Engine  
**Gate:** D — Research Lab Integration, Data Alignment & REST API Endpoints  
**Previous Gate:** C — Core Numerical Computation Engine (Commit: `583ed4adcb496f86ca40f2f354fdb19b5c2a11b8`)  
**Authorization:** Authorized by Project Owner for Stage 33 Gate D.

---

## 1. Executive Summary

Stage 33 Gate D successfully integrates the Stage 33 vectorized numerical computation engine (`backend/app/analytics/overfitting.py`) into the project's established research architecture and REST API layer. 

The implementation exposes on-demand Combinatorially Symmetric Cross-Validation (CSCV), Probability of Backtest Overfitting (PBO), Deflated Sharpe Ratio (DSR), and Minimum Backtest Length (MinBTL) across historical strategy trials of a `ResearchExperimentModel`.

Strict financial data integrity and security rules are enforced:
1. **Deterministic Date Alignment:** Historical daily net return series (`return_net`) are extracted directly from `BacktestRunModel.equity_curve_json` and synchronized via inner join across candidate strategy runs. Missing observations are never silently forward-filled, backfilled, interpolated, or zero-filled.
2. **Tenant Isolation:** All experiment and run accesses require authenticated JWT credentials and enforce strict tenant ownership checks. Cross-tenant or unauthorized accesses fail closed with HTTP 404 (preventing private experiment discovery).
3. **Fail-Closed Numerical Diagnostics:** If fewer than 2 eligible runs exist, or overlapping history is insufficient ($T < \max(20, 2S)$), or returns contain non-finite numbers/duplicate dates, the request fails closed with HTTP 422.
4. **Zero Out-of-Sample Leakage:** In-sample strategy selection and out-of-sample relative ranking remain strictly segregated across all combinatorial partitions.

All 19 dedicated integration tests in `backend/tests/test_overfitting_api.py`, all 13 Gate B contract tests, all 22 Gate C numerical engine tests, and all 589 tests in the full backend suite pass with 100% success.

---

## 2. API Contract & Endpoint Specification

### 2.1 Endpoint Route
- **HTTP Method:** `POST`
- **Route Path:** `/api/v1/research/experiments/{experiment_id}/overfitting-diagnostics`
- **Tags:** `Portfolio Research Experiments`
- **Summary:** Compute backtest overfitting diagnostics (CSCV, PBO, DSR, MinBTL) across experiment runs.
- **Success Status Code:** `HTTP 200 OK`

### 2.2 Request Schema (`OverfittingDiagnosticsRequest`)
```json
{
  "experiment_id": "Optional string matching URL path or omitted",
  "run_ids": ["Optional list of explicit run UUIDs (min 2, max 100)"],
  "n_slices": 16,
  "significance_level": 0.05,
  "annualization_factor": 252
}
```

#### Field Specifications & Constraints
- `experiment_id` (`str | None`, default `None`): UUID of the parent experiment. If supplied in the request body, it must match the `{experiment_id}` in the URL path; otherwise an HTTP 422 Unprocessable Content error is returned.
- `run_ids` (`list[str] | None`, default `None`): Optional explicit subset of strategy run IDs to analyze. If omitted, all succeeded runs with attached backtests for the experiment are analyzed. If provided, requires at least 2 distinct IDs, rejects duplicates, and enforces a maximum cap of 100 runs.
- `n_slices` (`int`, default `16`, $4 \le S \le 16$, even): Number of contiguous temporal slices for CSCV partitioning ($C = \binom{S}{S/2}$). Rejects odd integers and values outside $[4, 16]$.
- `significance_level` (`float`, default `0.05`, $0.0 < \alpha < 0.5$): Statistical significance threshold for hypothesis testing.
- `annualization_factor` (`int`, default `252`, $1 \le Q \le 365$): Trading frequency annualization factor (252 for daily, 52 for weekly, 12 for monthly).

### 2.3 Response Schema (`OverfittingDiagnosticsResponse`)
```json
{
  "experiment_id": "string",
  "experiment_name": "string",
  "strategy_type": "string",
  "dataset_id": "string",
  "snapshot_id": "string | null",
  "evaluated_runs_count": 5,
  "aligned_observations_count": 504,
  "n_slices": 16,
  "total_combinations_count": 12870,
  "pbo": 0.1245,
  "pbo_risk_level": "low",
  "best_run_id": "uuid-string",
  "best_run_number": 3,
  "best_nominal_sharpe": 1.452,
  "expected_max_sharpe": 1.215,
  "deflated_sharpe_ratio": 0.962,
  "is_statistically_significant": true,
  "min_backtest_length_years": 1.42,
  "actual_backtest_length_years": 2.0,
  "skewness": -0.15,
  "kurtosis": 3.42,
  "degradation_regression": {
    "slope": 0.742,
    "intercept": 0.125,
    "r_squared": 0.612,
    "p_value": 0.00001,
    "std_err": 0.021
  },
  "combinations_sample": [
    {
      "combination_id": 0,
      "selected_run_id": "uuid-string",
      "is_sharpe": 1.62,
      "oos_sharpe": 1.35,
      "oos_rank": 4,
      "relative_rank": 0.6667,
      "is_overfitted": false
    }
  ],
  "rank_distribution": [
    {
      "bin_start": 0.0,
      "bin_end": 0.1,
      "count": 120,
      "relative_frequency": 0.0093
    }
  ],
  "runs_summary": [
    {
      "run_id": "uuid-string",
      "run_number": 1,
      "nominal_sharpe": 0.85,
      "selection_frequency_is": 0.12,
      "mean_oos_sharpe_when_selected": 0.71,
      "mean_oos_rank_when_selected": 0.54
    }
  ],
  "warnings": [],
  "generated_at": "2026-10-22T00:44:00Z"
}
```

---

## 3. Data Integrity & Alignment Architecture

### 3.1 Run Identity & Deterministic Ordering
1. Runs are selected either from `req.run_ids` or queried across all succeeded runs of the experiment (`ResearchExperimentRunModel.experiment_id == exp.id`, `status == "succeeded"`, `backtest_id.isnot(None)`).
2. Runs are deterministically ordered by `run_number`. This ordering remains immutable across DataFrame columns, slice aggregations, combinatorial evaluation, and final JSON response serialization.

### 3.2 Historical Return Extraction
- Returns are extracted directly from `BacktestRunModel.equity_curve_json`.
- Each point in the equity curve provides an ISO-8601 `date` and a discrete net return `return_net`.
- Semantics: `return_net` represents the discrete simple return ($r_t = \frac{V_t - V_{t-1}}{V_{t-1}}$) net of all transaction costs, slippage, and rebalance frictions.
- Cumulative portfolio equity curves ($V_t$) are never mistaken for periodic returns.

### 3.3 Fail-Closed Alignment Policy
- **Inner Join Synchronization:** Return series are synchronized by taking the intersection of observation dates across all candidate strategies (`df.dropna(how="any").sort_index()`).
- **Zero Fabrication:** Missing dates are never filled with zero, forward-filled, backfilled, or interpolated.
- **Duplicate Date Detection:** Any run containing non-unique observation dates is immediately rejected with HTTP 422.
- **Non-Finite Return Rejection:** Any series containing `NaN`, `+Inf`, `-Inf`, or `None` is immediately rejected with HTTP 422.
- **Sufficiency Threshold:** Aligned observations must satisfy $T_{\text{aligned}} \ge \max(20, 2S)$. If $T$ is shorter, the request fails with HTTP 422.
- **Alignment Trimming Advisory:** If date alignment trims $> 20\%$ of any strategy's observations, an advisory warning is included: `"Date alignment trimmed significant non-overlapping observations... Strategy evaluation periods may diverge."`
- **Snapshot Divergence Audit:** If selected runs were executed against different dataset snapshots, an advisory warning is appended informing the researcher of underlying market data divergence.

---

## 4. Mathematical Conventions Inherited from Gate C

1. **CSCV Combinatorial Splits:**  
   Given $S$ even slices ($S \in [4, 16]$), exactly $C = \binom{S}{S/2}$ combinations are generated. In-sample (IS) uses half the slices ($S/2$), while out-of-sample (OOS) uses the complementary half ($S - S/2$).
2. **Probability of Backtest Overfitting (PBO):**  
   For each split $c$, the strategy with maximum in-sample annualized Sharpe ratio ($i_c^* = \arg\max \text{SR}_{c, \text{IS}}$) is evaluated on out-of-sample data. Its OOS rank is determined ($1 = \text{worst}, N = \text{best}$). Normalized relative rank is computed:
   $$\bar{\omega}_c = \frac{\text{Rank}_{c, \text{OOS}}(i_c^*)}{N + 1}$$
   PBO is the empirical proportion of splits where $\bar{\omega}_c \le 0.5$:
   $$\text{PBO} = \frac{1}{C} \sum_{c=1}^C \mathbf{1}_{\{\bar{\omega}_c \le 0.5\}}$$
3. **PBO Risk Classification:**
   - $\text{PBO} \le 0.15$: `low`
   - $0.15 < \text{PBO} \le 0.35$: `moderate`
   - $0.35 < \text{PBO} \le 0.50$: `high`
   - $\text{PBO} > 0.50$: `severe`
4. **Expected Maximum Sharpe Ratio ($\text{SR}^*$):**  
   Computed via Extreme Value Theory (EVT) (Bailey & López de Prado, 2014, Eq. 6) under the null hypothesis of selection bias across $N$ trials with sample variance $V$ and mean $\bar{\mu}$:
   $$\text{SR}^* = \bar{\mu} + \sqrt{V}\left[(1 - \gamma)\Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N e}\right)\right]$$
   where $\gamma \approx 0.5772156649$ is the Euler-Mascheroni constant.
5. **Deflated Sharpe Ratio (DSR):**  
   Applies Mertens (2002) and Lo (2002) non-normal asymptotic Sharpe standard error with uncentered Pearson sample kurtosis ($\text{Normal} = 3.0$) and sample skewness. When annualization factor $Q > 1$, Sharpe ratios are de-annualized to periodic frequency for variance denominator evaluation.
6. **Minimum Backtest Length (MinBTL):**  
   Calculates minimum track record length in periodic observations $T^*$ required to reject false discovery at significance level $\alpha$. Returns $T^* / Q$ in years. If the observed Sharpe ratio does not exceed the random selection benchmark ($\text{SR} \le \text{SR}^*$), MinBTL is unreachable and safely serialized as JSON `null` (`None`).
7. **Moment Robustness:**  
   In degenerate zero-variance or constant-return scenarios where sample skewness or kurtosis suffers catastrophic cancellation yielding `NaN`, moments fall back safely to Gaussian baseline ($\text{skew}=0.0, \text{kurt}=3.0$).

---

## 5. Statistical Assumptions & Interpretative Limitations

The API communicates objective statistical metrics under documented quantitative finance assumptions. The integration does NOT imply that:
- A low PBO or high DSR guarantees live profitability or eliminates market risk.
- CSCV replaces chronological walk-forward validation or live out-of-sample forward testing.
- The engine automatically corrects for non-stationarity, regime shifts, or high serial correlation (unless pre-filtered).
- An unreachable MinBTL indicates an invalid calculation; rather, it indicates the strategy's observed return is statistically indistinguishable from random trial selection.

---

## 6. Security, Authorization & Error Mapping

| HTTP Code | Condition | Rationale |
|:---|:---|:---|
| **401 Unauthorized** | Missing, invalid, or expired JWT token | Enforces authenticated access on all endpoints. |
| **404 Not Found** | Experiment does not exist OR belongs to another tenant | Prevents cross-tenant experiment discovery. |
| **404 Not Found** | Specified `run_ids` not found or belonging to another user | Fail-closed validation on requested run identifiers. |
| **422 Unprocessable Content** | Fewer than 2 eligible candidate strategies | CSCV requires multiple trials for cross-validation. |
| **422 Unprocessable Content** | Odd `n_slices` or $S \notin [4, 16]$ | Enforces valid combinatorial partitioning limits. |
| **422 Unprocessable Content** | `run_ids` contains duplicates or $> 100$ items | Prevents unbounded computational resource exhaustion. |
| **422 Unprocessable Content** | Insufficient aligned dates ($T < \max(20, 2S)$) | Guarantees minimum statistical sample size. |
| **422 Unprocessable Content** | Non-finite returns or duplicate observation dates | Rejects corrupted or ambiguous historical data. |
| **500 Internal Server Error** | Unexpected unhandled execution failure | Returns sanitized non-sensitive message to client. |

---

## 7. Verification Protocol & Test Results

### 7.1 New API Integration Tests (`backend/tests/test_overfitting_api.py`)
- **Category A (API Contracts):** Valid request/response, default parameter resolution, optional run selection, invalid slice counts, invalid alpha values.
- **Category B (Run Selection):** Unknown experiment (404), unknown run (404), run from foreign experiment (422), duplicate run IDs (422), insufficient runs (422), failed/non-backtest run filtering.
- **Category C (Data Alignment):** Synchronized inner join on missing dates, duplicate date rejection (422), non-finite return rejection (422), short observation rejection (422).
- **Category D (Numerical Integration):** Strict numerical agreement between REST API response and core numerical engine ($< 10^{-10}$ tolerance on all Sharpe and DSR fields), provenance and run metadata preservation.
- **Category E (Security & Resource Limits):** Unauthenticated request rejection (401), cross-tenant isolation enforcement (404), max run cap enforcement ($> 100$ runs rejected with 422).
- **Result:** `19 passed in 2.04s`

### 7.2 Gate B & Gate C Tests
- `backend/tests/test_overfitting_contracts.py`: `13 passed in 0.35s`
- `backend/tests/test_overfitting_engine.py`: `22 passed in 0.52s`

### 7.3 Existing Research API & Engine Regressions
- `backend/tests/test_research_api.py`: `9 passed in 3.10s`
- `backend/tests/test_research_engine.py`: `8 passed in 0.45s`

### 7.4 Full Backend Regression Suite
- **Command:** `backend\.venv\Scripts\pytest backend\tests`
- **Result:** `589 passed, 16 warnings in 144.24s (0:02:24)`
- **Exit Code:** `0`

---

## 8. Summary of Files Changed

| File Path | Role | Description of Changes |
|:---|:---|:---|
| `backend/app/research/overfitting_models.py` | Domain Contracts | Set `experiment_id: str \| None = Field(default=None)` to support path injection in REST calls. |
| `backend/app/analytics/overfitting.py` | Core Numerical Engine | Propagated actual `run_number` from `run_metadata` to `runs_summary`; safeguarded skewness and kurtosis against `NaN` on degenerate zero-variance series. |
| `backend/app/research/service.py` | Research Service Layer | Implemented `ResearchService.compute_experiment_overfitting` with tenant authorization, backtest resolution, date alignment, and diagnostic orchestration. |
| `backend/app/api/v1/research_routes.py` | REST API Layer | Mounted `POST /experiments/{experiment_id}/overfitting-diagnostics` endpoint with request/response serialization. |
| `backend/tests/conftest.py` | PyTest Config | Added `test_overfitting_api` to the unmocked authentication test suite list. |
| `backend/tests/test_overfitting_api.py` | Integration Tests | 19 end-to-end integration, security, alignment, and numerical agreement tests. |
| `docs/STAGE_33_GATE_D_RESEARCH_API_INTEGRATION.md` | Gate Documentation | Created comprehensive architectural and verification report. |
| `docs/MASTER_PLAN.md` | Roadmap Status | Updated Stage 33 to record Gate D completion. |

---

## 9. Gate D Verdict

**Verdict:** `PASS`

The Stage 33 numerical engine is fully integrated into the Research Lab workflow and REST API layer. Historical return panels are aligned deterministically, tenant security is enforced fail-closed, numerical agreement with literature benchmarks is verified, and all 589 backend tests pass cleanly.

**Next Milestone:** Stage 33 Gate E (Research Lab UX, Overfitting Diagnostics Visualizations & Tear-Sheet Components) awaits explicit project owner authorization.
