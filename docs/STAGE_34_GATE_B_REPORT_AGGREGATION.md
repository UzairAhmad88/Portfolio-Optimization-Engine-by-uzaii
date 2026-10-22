# Stage 34 Gate B: Report Aggregation Service & Analytical Assembler
**Document ID:** `docs/STAGE_34_GATE_B_REPORT_AGGREGATION.md`  
**Stage:** 34 — Institutional Tear Sheets, Strategy Fact Sheets & Research PDF Export Engine  
**Gate:** B — Report Aggregation Service and Analytical Assembler  
**Status:** Completed & Validated (Pending Independent Audit)  
**Date:** October 23, 2026  
**Author:** Principal Quantitative Finance Engineer, Senior Python/FastAPI Architect, Financial Reporting Specialist & Security Lead  

---

## 1. Executive Summary & Gate B Objectives

Stage 34 Gate B delivers the backend analytical aggregation and reporting assembly layer for the Quantitative Portfolio Optimization Engine. Building directly upon the canonical domain contracts established in Gate A (`backend/app/reports/contracts.py`), Gate B compiles existing, authorized application records into deterministic, institutional-grade reporting payloads.

### Deliverables Produced in Gate B:
1. **Report Assembler Service (`backend/app/reports/assembler.py`):**
   - High-performance, single-responsibility analytical aggregation service (`ReportAssemblerService`).
   - Compiles Strategy Fact Sheet (1-page payload), Institutional Tear Sheet (2-page payload), Research Diagnostics Annex (Stage 33 overfitting diagnostics), and Unified Institutional Report.
   - Enforces strict gross-versus-net separation, prevents zero-coercion of undefined metrics, downsamples compact summary curves preserving endpoints, and emits structured non-fatal warnings for data limitations.
2. **REST API Routing Layer (`backend/app/api/v1/reporting_routes.py`):**
   - Clean, versioned REST endpoints mounted under `/api/v1/reports`:
     - `GET /api/v1/reports/fact-sheet/{backtest_id}`
     - `GET /api/v1/reports/tear-sheet/{backtest_id}`
     - `POST /api/v1/reports/research-annex/{experiment_id}`
     - `GET /api/v1/reports/unified/{backtest_id}`
   - Standard FastAPI dependency injection (`get_current_active_user`, `get_db`).
3. **Rigorous Security & Authorization:**
   - Multi-tenant data isolation: Access to unowned backtests or experiments fails closed with HTTP 404 (preventing resource ID enumeration).
   - Administrative override: Users with `role="admin"` have verified read access across tenant boundaries.
   - Authentication requirement: Missing or invalid JWT tokens yield HTTP 401 Unauthorized.
4. **Comprehensive Test Suite:**
   - 7 unit tests in `backend/tests/test_reporting_assembler.py`.
   - 7 integration/security tests in `backend/tests/test_reporting_api.py`.
   - 100% pass rate with zero regressions across the 626 backend tests and 73 frontend tests.

---

## 2. Report Assembly Architecture & Data Flow

```
                                  [ Client Request ]
                                          |
                                          v
                    +-------------------------------------------+
                    | FastAPI Routing Layer (v1/reporting_routes)|
                    | - JWT Bearer Auth Verification            |
                    | - Input Parameter & Schema Validation     |
                    +-------------------------------------------+
                                          |
                                          v
                    +-------------------------------------------+
                    | ReportAssemblerService (assembler.py)     |
                    | 1. Authorization & Tenant Isolation Check |
                    | 2. Envelope & Provenance Construction     |
                    | 3. Mandate & Strategy Config Extraction   |
                    | 4. Executive KPIs & Dual Gross/Net Mapping|
                    | 5. Benchmark Alignment & Relative Metrics |
                    | 6. Asset Allocation & Menchero Contribs   |
                    | 7. Friction & TCA Cost Aggregation        |
                    | 8. Synchronized Curves & Downsampling     |
                    | 9. Compounded Monthly Return Grid (Prod)  |
                    +-------------------------------------------+
                       /                 |                   \
                      v                  v                    v
              +---------------+  +---------------+  +---------------------+
              | BacktestRun   |  | Performance   |  | ResearchService     |
              | Model (Curve, |  | Report Model  |  | (Stage 33 Engine    |
              | Summary JSON) |  | (Attribution) |  |  PBO, DSR, CSCV)    |
              +---------------+  +---------------+  +---------------------+
                      \                  |                    /
                       ------------------+--------------------
                                         |
                                         v
                     +---------------------------------------+
                     | Validated Gate A Pydantic v2 Payload  |
                     | - Fact Sheet (1-page)                 |
                     | - Tear Sheet (2-page)                 |
                     | - Research Annex (3rd-page)           |
                     | - Unified Institutional Report        |
                     +---------------------------------------+
```

---

## 3. API Endpoint Specifications

All endpoints are authenticated and require a valid JWT Bearer token in the `Authorization` header.

### 3.1 Strategy Fact Sheet
- **Route:** `GET /api/v1/reports/fact-sheet/{backtest_id}`
- **Query Parameters:**
  - `benchmark_asset` *(optional string)*: Explicit benchmark asset ticker (e.g. `SPY`). Defaults to the backtest's configured benchmark.
- **Response Contract:** `StrategyFactSheetPayload` (HTTP 200)
- **Features:** Mandate summary, dual gross/net executive KPIs, benchmark relative metrics, top holdings (sorted by weight, up to 10), compact downsampled wealth curve ($\le 250$ points), monthly return matrix.

### 3.2 Institutional Tear Sheet
- **Route:** `GET /api/v1/reports/tear-sheet/{backtest_id}`
- **Query Parameters:**
  - `benchmark_asset` *(optional string)*: Explicit benchmark asset ticker.
- **Response Contract:** `InstitutionalTearSheetPayload` (HTTP 200)
- **Features:** Full 2-page institutional payload with complete constituent asset allocation table, detailed transaction cost and friction metrics (turnover, commissions, slippage, friction drag in bps), full synchronized daily equity curve (252+ points), multi-year monthly returns table.

### 3.3 Research Diagnostics Annex
- **Route:** `POST /api/v1/reports/research-annex/{experiment_id}`
- **Request Body:** `OverfittingDiagnosticsRequest` *(optional JSON)*
  - `run_ids` *(optional list[str])*: Subset of candidate run UUIDs to evaluate.
  - `n_slices` *(optional int, default 16)*: Number of CSCV partitions.
  - `significance_level` *(optional float, default 0.05)*: Alpha threshold for DSR hypothesis testing.
  - `annualization_factor` *(optional int, default 252)*: Return frequency factor.
- **Response Contract:** `ResearchDiagnosticsAnnexPayload` (HTTP 200)
- **Features:** Reuses validated Stage 33 overfitting diagnostics: Probability of Backtest Overfitting (PBO), PBO risk level classification, Deflated Sharpe Ratio (DSR), statistical significance flag, Minimum Backtest Length (MinBTL in years), CSCV degradation OLS regression, rank distribution histogram (10 deciles), run summary statistics.

### 3.4 Unified Institutional Report
- **Route:** `GET /api/v1/reports/unified/{backtest_id}`
- **Query Parameters:**
  - `benchmark_asset` *(optional string)*: Explicit benchmark asset ticker.
  - `experiment_id` *(optional string)*: Explicit research experiment UUID to bind.
- **Response Contract:** `InstitutionalReportResponse` (HTTP 200)
- **Features:** Bundles `fact_sheet`, `tear_sheet`, and optional `research_annex` into a single cohesive response envelope (`unified_tear_sheet`). If the experiment cannot be evaluated, `research_annex` is omitted with a structured warning.

---

## 4. Quantitative & Metric Mapping Rules

### 4.1 Strict Gross vs. Net Separation
- **No Co-mingling:** Net and gross metrics are strictly distinct fields across all contracts (`cagr_net` vs `cagr_gross`, `sharpe_ratio_net` vs `sharpe_ratio_gross`, `drawdown_net` vs `drawdown_gross`).
- **No Inference:** Gross returns are never inferred from net returns by guessing transaction costs. If gross performance data is absent from stored records, gross fields remain `None`.

### 4.2 Zero-Coercion Prohibition
- Mathematically undefined ratios are strictly preserved as `None`:
  - **Calmar Ratio:** `cagr / max_drawdown` when `max_drawdown > 1e-6`; if drawdown is zero, Calmar is `None`. Never coerced to 0.0 or $\infty$.
  - **Sharpe Ratio:** `(ann_return - rfr) / ann_vol` when `ann_vol > 1e-6`; if volatility is zero, Sharpe is `None`.
  - **Sortino Ratio:** `(ann_return - rfr) / downside_vol` when `downside_vol > 1e-6`; if downside volatility is zero, Sortino is `None`.
  - **Information Ratio:** `active_return / tracking_error` when `tracking_error > 1e-6`; if tracking error is zero, IR is `None`.
  - **Treynor Ratio:** `(ann_return - rfr) / beta` when `|beta| > 1e-6`; otherwise `None`.

### 4.3 Provenance & Dataset Snapshot Integrity
- **Snapshot Binding:** When a backtest is linked to a certified `DatasetSnapshotModel`, the snapshot UUID and its 64-character SHA-256 manifest digest are populated in `CommonReportEnvelope`.
- **Mutable Warning:** If a backtest was executed against a mutable or uncertified dataset (no frozen snapshot), the report emits `WARN_MUTABLE_DATASET` advising that results are not cryptographically immutable.
- **Date Sanitization (`OBS-34-A-01`):** Dates are parsed via `date.fromisoformat`. Inverted date ranges are swapped deterministically with `WARN_DATE_REORDERED` emitted.

### 4.4 Monthly Returns Compounding
- Discrete monthly returns are compounded geometrically from valid daily returns:
  $$R_M = \prod_{t=1}^{T_M} (1 + r_t) - 1$$
- Missing months are never populated with invented zero returns. Incomplete calendar years are flagged with `WARN_INCOMPLETE_CALENDAR_YEAR`.

### 4.5 Downsampling with Endpoint Preservation
- The Fact Sheet compact wealth curve is downsampled using evenly spaced indices via `np.round(np.linspace(0, N - 1, max_points))`.
- Length is strictly bounded: $\text{len} \le \text{max\_points}$ (default 250).
- The initial inception observation (index 0) and terminal observation (index $N - 1$) are guaranteed to be preserved.

---

## 5. Structured Warning Registry

The service emits non-fatal, structured machine-readable warnings (`ReportWarning`) when encountering data limitations:

| Warning Code | Severity | Trigger Condition |
| :--- | :--- | :--- |
| `WARN_MUTABLE_DATASET` | `warning` | Backtest executed against an uncertified or mutable dataset without snapshot binding. |
| `WARN_NO_BENCHMARK` | `info` | No benchmark asset configured; active comparative metrics are omitted. |
| `WARN_BENCHMARK_UNAVAILABLE` | `warning` | Benchmark asset specified but price bars cannot be extracted from dataset. |
| `WARN_DATASET_BARS_EMPTY` | `warning` | Market dataset contains no price bars for return alignment. |
| `WARN_BENCHMARK_MISMATCH` | `warning` | Benchmark and portfolio observation counts differ after alignment. |
| `WARN_PARTIAL_TCA` | `info` | Trading transaction costs modeled with zero slippage bps. |
| `WARN_MISSING_ALLOCATION` | `info` | Portfolio strategy configuration contains no constituent weight allocations. |
| `WARN_INCOMPLETE_CALENDAR_YEAR` | `info` | Track record covers less than a full calendar year (annualized metrics scaled). |
| `WARN_DATE_REORDERED` | `warning` | Reporting start date was chronologically after end date; boundaries swapped. |
| `WARN_RESEARCH_DIAGNOSTICS` | `warning`/`info`| Notes from Stage 33 overfitting diagnostics evaluation. |

---

## 6. Verification and Test Results

### 6.1 Test Suites Executed

1. **Gate B Unit Tests (`backend/tests/test_reporting_assembler.py`):**
   - `test_assemble_fact_sheet_success`: Validates mandate, KPIs, downsampled wealth curve ($\le 250$ pts), monthly returns matrix.
   - `test_assemble_fact_sheet_unauthorized_user_raises_404`: Tenant isolation verification.
   - `test_assemble_fact_sheet_admin_user_has_access`: Admin cross-tenant read permission.
   - `test_assemble_tear_sheet_comprehensive`: Validates 2-page payload, full allocations, TCA drag in bps.
   - `test_assemble_tear_sheet_mutable_dataset_warning`: Emits `WARN_MUTABLE_DATASET` for uncertified data.
   - `test_assemble_tear_sheet_undefined_calmar_on_zero_drawdown`: Zero-coercion rule verified (`calmar_ratio == None`).
   - `test_assemble_unified_report`: Bundled Fact Sheet, Tear Sheet, and Research Annex assembly.
   - **Result:** **7 passed in 0.31s**

2. **Gate B API Integration & Security Tests (`backend/tests/test_reporting_api.py`):**
   - `test_fact_sheet_unauthenticated`: HTTP 401 Unauthorized without token.
   - `test_fact_sheet_cross_user_isolation`: HTTP 404 Not Found for cross-tenant access.
   - `test_fact_sheet_owner_success`: HTTP 200 and schema validation against `StrategyFactSheetPayload`.
   - `test_tear_sheet_admin_access`: HTTP 200 for admin user inspecting tear sheet.
   - `test_research_annex_success`: HTTP 200 and schema validation against `ResearchDiagnosticsAnnexPayload`.
   - `test_research_annex_cross_user_denial`: HTTP 404 for unowned experiment.
   - `test_unified_report_endpoint`: HTTP 200 and validation against `InstitutionalReportResponse`.
   - **Result:** **7 passed in 1.40s**

3. **Gate A Contract Regression Tests (`backend/tests/test_reporting_contracts.py`):**
   - **Result:** **21 passed in 0.39s**

4. **Stage 33 Overfitting Engine & API Regression Tests (`backend/tests/test_overfitting_*.py`):**
   - **Result:** **43 passed in 3.32s**

5. **Full Backend Test Suite (`backend/tests/`):**
   - **Result:** **626 passed in 93.93s**

6. **Frontend Test Suite (`frontend/src/test/`):**
   - **Result:** **73 passed in 23.20s**

7. **Frontend Production Build (`npm run build`):**
   - **Result:** **Built successfully in 1.03s**

---

## 7. Scope Boundaries & Deferred Items

### In Scope for Gate B (Completed):
- Analytical report assembler service.
- REST API routes with authentication and tenant isolation.
- Integration with existing backtest, performance, and Stage 33 diagnostics services.
- Unit, API, and regression test suites.
- Gate B architecture documentation.

### Out of Scope (Deferred to Future Gates):
- **Gate C:** Print-ready React report templates, CSS Paged Media (`@page`, `@media print`), vector SVG chart rendering.
- **Gate D:** UI report export buttons, interactive report preview modals, frontend API client bindings.
- **Gate E:** Formal release verification and audit report.
- **Server-Side PDF Rendering:** No server-side PDF binaries (WeasyPrint, ReportLab, or Puppeteer) are used; PDF export will be executed browser-natively in Gate C/D.

---

## 8. Governance and Next Actions

Stage 34 Gate B is complete, fully tested, and ready for review.
In accordance with project release discipline:
- Gate B is **not marked accepted**; acceptance rests solely with the project owner.
- Recommended next action: **Independent read-only audit of Stage 34 Gate B**.
