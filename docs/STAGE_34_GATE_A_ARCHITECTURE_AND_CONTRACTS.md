# Stage 34 Gate A: Reporting Architecture, Domain Contracts & Analytical Fixtures
**Document ID:** `docs/STAGE_34_GATE_A_ARCHITECTURE_AND_CONTRACTS.md`  
**Stage:** 34 — Institutional Tear Sheets, Strategy Fact Sheets & Research PDF Export Engine  
**Gate:** A — Reporting Architecture, Domain Contracts & Analytical Fixtures  
**Status:** Completed & Validated  
**Date:** October 23, 2026  
**Author:** Principal Quantitative Finance Engineer, Financial Reporting Architect & Test-Driven Development Lead  

---

## 1. Executive Summary & Gate A Objectives

Stage 34 establishes institutional-grade, audit-ready reporting artifacts for the Quantitative Portfolio Optimization Engine. Gate A specifies the foundational architecture, canonical domain contracts, metric registry, missing-data semantics, analytical fixtures, and contract tests for three primary outputs:

1. **Strategy Fact Sheet:** A concise 1-page executive summary tailored for investment committees and allocators.
2. **Institutional Tear Sheet:** A comprehensive 2-page portfolio performance, risk attribution, and transaction cost analysis report.
3. **Research Diagnostics Annex:** An optional 3rd page dedicated to multiple-testing corrections, Probability of Backtest Overfitting (PBO), and Deflated Sharpe Ratio (DSR) diagnostics for eligible research experiments (reusing validated Stage 33 diagnostics).

### Scope Boundary & Governance
- **Strict Scope:** Gate A establishes domain contracts, metric registries, TypeScript types, analytical fixtures, and contract tests only.
- **No Early Implementation:** Does not implement report aggregation services (Gate B), PDF templates or print CSS (Gate C), UI integrations (Gate D), or release audits (Gate E).
- **No Premature Persistence:** No database tables, schemas, or migrations are created in Gate A.
- **Client-Side CSS Paged Media Architecture:** PDF generation relies on modern browser print layout engines (`@media print` / CSS Paged Media). No server-side PDF rendering engine (such as WeasyPrint, Puppeteer, or ReportLab) is introduced.

---

## 2. Reporting Architecture & Responsibility Split

```
+--------------------------------------------------------------------------+
|                       CANONICAL BACKEND DOMAIN                           |
|  - Strategy / Backtest / Research Models (SQLAlchemy, Immutable Snaps)   |
|  - Validated Financial Metric Engines (Annualized, Gross vs Net)         |
|  - Data Provenance (Dataset ID, Snapshot SHA-256 Digest, Manifest)       |
|  - Missing-Data & Undefined Classification (None / Status, Not Coerced)  |
|  - Structured Warnings & Audit Disclaimers                               |
+--------------------------------------------------------------------------+
                                     |
                                     v (Strict Pydantic v2 Contract)
+--------------------------------------------------------------------------+
|                       TYPED REPORT API PAYLOAD                           |
|  - CommonReportEnvelope (Metadata, Date Range, Provenance, Warnings)    |
|  - ExecutiveKPIs (Dual Gross / Net metrics, Drawdowns, Win/Loss)         |
|  - BenchmarkRelativeMetrics (Active Return, Tracking Error, IR, Beta)    |
|  - MonthlyReturnGrid & TimeSeries (Normalized NAV & DD curves)           |
|  - AssetAllocation & Attribution (Weights, Brinson-Menchero components)   |
|  - FrictionMetrics (Turnover, Commission, Slippage, Drag in bps)         |
|  - ResearchOverfittingPayload (PBO, DSR, MinBTL, CSCV Distributions)     |
+--------------------------------------------------------------------------+
                                     |
                                     v (JSON over HTTP / API Client)
+--------------------------------------------------------------------------+
|                       FRONTEND PRESENTATION LAYER                        |
|  - Mirroring TypeScript Interfaces (`frontend/src/types/reporting.ts`)   |
|  - Screen Preview & Interactive Inspection UI                            |
|  - Responsive Print Previews with CSS Paged Media (`@page`, `@media`)    |
|  - Deterministic Vector SVG Visualizations (Equity, Drawdown, Alloc)     |
|  - Browser-Native "Save as PDF" Execution (Zero Server-Side Dependency)   |
+--------------------------------------------------------------------------+
```

### Architectural Principles
1. **Single Source of Numerical Truth:** The backend is the sole authority for financial calculations, risk-adjusted metrics, attribution, and overfitting statistics. The frontend never re-computes financial KPIs or re-interpolates time series.
2. **Explicit Gross vs. Net Separation:** Gross and net figures are never co-mingled or silently substituted. All performance KPIs (CAGR, Sharpe, Sortino, Drawdown, Calmar) carry explicit `_gross` and `_net` variants.
3. **No Numerical Coercion:** Missing or mathematically undefined metrics (e.g. Calmar ratio when maximum drawdown is $0.0$, Information Ratio when tracking error is $0.0$, or MinBTL when Sharpe $\le SR^*$) remain strictly `None` (null) in contracts and `"Undefined"` in presentations—never coerced to `0.0` or arbitrary defaults.
4. **Data Isolation & Anti-Tampering:** Every report envelope embeds dataset snapshot identifiers and SHA-256 manifest digests where available, establishing audit lineage back to Stage 32 immutable datasets.

---

## 3. Reporting Domain Contracts

All models are authored in `backend/app/reports/contracts.py` using Pydantic v2 and mirrored in `frontend/src/types/reporting.ts`.

### 3.1 Common Report Envelope (`CommonReportEnvelope`)
Encapsulates metadata common to all institutional reports:
- `schema_version`: String literal (defaulting to `"1.0.0"`).
- `report_type`: Enum (`FACT_SHEET`, `TEAR_SHEET`, `RESEARCH_ANNEX`).
- `report_id`: Unique report identifier string.
- `report_title`: Institutional report title.
- `generated_at_utc`: ISO 8601 UTC timestamp of report compilation.
- `reporting_start_date` & `reporting_end_date`: Inclusive portfolio/backtest evaluation window.
- `base_currency`: ISO 4217 currency code (e.g., `"USD"`, `"PKR"`, `"EUR"`).
- `dataset_snapshot_id` & `snapshot_manifest_digest`: Immutable data lineage digests (from Stage 32).
- `strategy_id`, `portfolio_id`, `backtest_id`, `experiment_id`: Source record lineage.
- `calculation_engine_version`: Underlying engine build tag.
- `warnings`: Array of structured `ReportWarning` models (code, severity, message, affected metric).
- `disclaimers`: Array of regulatory, institutional, and quantitative disclosures.

### 3.2 Strategy Fact Sheet Contract (`StrategyFactSheetPayload`)
Designed for a 1-page executive deliverable:
- `envelope`: Common report envelope.
- `mandate`: Strategy identity, investment objective, rebalancing frequency, benchmark symbol.
- `kpis`: High-level executive performance and risk KPIs (net and gross).
- `benchmark_metrics`: Active return, tracking error, beta, and information ratio (optional).
- `monthly_returns`: Trailing or full multi-year monthly returns grid.
- `trailing_returns`: Standard multi-horizon returns (1M, 3M, 6M, 1Y, 3Y, 5Y, Inception).
- `top_holdings`: Top asset allocations with weights and contribution components.
- `methodology_notes`: Summary methodology disclosures.

### 3.3 Institutional Tear Sheet Contract (`InstitutionalTearSheetPayload`)
Designed for a 2-page detailed risk, return, and attribution deliverable:
- `envelope`: Common report envelope.
- `mandate`: Strategy identity, universe, constraints, target cash floor.
- `kpis`: Full suite of net and gross metrics, drawdown duration, recovery time, win/loss stats.
- `benchmark_metrics`: Benchmark correlation, tracking error, Jensen's alpha, capture ratios.
- `equity_curve`: Chronological array of `TimeSeriesPoint` records with normalized wealth, daily return, drawdown, and benchmark wealth.
- `drawdown_curve`: Downside underwater equity curve series.
- `monthly_returns`: Complete historical calendar-year monthly return grid.
- `asset_allocations`: Asset-level portfolio constituent allocations and risk contributions.
- `friction_metrics`: Portfolio turnover, commission, adverse slippage, and aggregate friction drag in bps.

### 3.4 Research Diagnostics Annex Contract (`ResearchDiagnosticsAnnexPayload`)
Designed as an optional 3rd page for research experiments evaluated under Stage 33:
- `envelope`: Common report envelope.
- `experiment_id` & `experiment_name`: Source research trial metadata.
- `trial_count`: Number of candidate strategies evaluated ($N$).
- `pbo`: Empirical Probability of Backtest Overfitting ($0.0 \le \text{PBO} \le 1.0$).
- `pbo_risk_level`: Institutional classification (`LOW`, `MODERATE`, `HIGH`).
- `deflated_sharpe_ratio`: Multiple-testing adjusted DSR value and significance flag ($p < 0.05$).
- `expected_maximum_sharpe`: Asymptotic EVT expected maximum Sharpe under null hypothesis.
- `minimum_backtest_length_years`: MinBTL in years required to avoid spurious discovery (or `None` if undefined).
- `degradation_slope`: CSCV OOS vs. IS performance decay regression slope ($\beta$).
- `cscv_pairs_count`: Number of combinatorial partitions evaluated ($C_{S}^{S/2}$).
- `cscv_relative_rank_distribution`: Histogram bin frequencies and labels.
- `sampling_disclosure`: Disclosure when combinatorial space is evaluated via uniform sampling.

---

## 4. Canonical Metric Registry

Documented in `backend/app/reports/metric_registry.py`, 15 canonical financial and statistical metrics are formally registered:

| Metric Name | Canonical Symbol | Unit / Format | Annualization / Horizon | Gross/Net Semantics | Undefined When |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Cumulative Return | $R_{\text{cum}}$ | Percentage (`+0.00%`) | Full Horizon | Dual (Net & Gross) | Period length $< 1$ day |
| CAGR | $R_{\text{CAGR}}$ | Annualized Pct (`+0.00%`) | Calendar Years ($N_{\text{days}}/365.25$) | Dual (Net & Gross) | Horizon $\le 0$ days or $1 + R_{\text{cum}} \le 0$ |
| Annualized Volatility | $\sigma_{\text{ann}}$ | Annualized Pct (`0.00%`) | $\sqrt{252}$ for daily observations | Dual (Net & Gross) | Observations $< 2$ or variance $< 0$ |
| Sharpe Ratio | $SR$ | Decimal Ratio (`0.00`) | Daily $\times \sqrt{252}$ | Dual (Net & Gross) | $\sigma_{\text{ann}} = 0.0$ |
| Sortino Ratio | $SoR$ | Decimal Ratio (`0.00`) | Daily Downside Vol $\times \sqrt{252}$ | Dual (Net & Gross) | Downside deviation $= 0.0$ |
| Maximum Drawdown | $MDD$ | Negative Pct (`-0.00%`) | Peak-to-Trough over Horizon | Dual (Net & Gross) | Period length $< 1$ day |
| Calmar Ratio | $CR$ | Decimal Ratio (`0.00`) | Annualized Return / $|MDD|$ | Dual (Net & Gross) | $MDD = 0.0$ (never coerce to 0.0) |
| Tracking Error | $TE$ | Annualized Pct (`0.00%`) | Sample Vol of Excess Returns | Net vs Benchmark | Observations $< 2$ or benchmark missing |
| Information Ratio | $IR$ | Decimal Ratio (`0.00`) | Geometric Excess / $TE$ | Net vs Benchmark | $TE = 0.0$ or benchmark missing |
| Beta | $\beta$ | Decimal Coefficient (`0.00`) | Covariance / Benchmark Variance | Net vs Benchmark | Benchmark Variance $= 0.0$ |
| Jensen's Alpha | $\alpha$ | Annualized Pct (`+0.00%`) | CAPM Excess Intercept | Net vs Benchmark | Benchmark missing or Variance $= 0.0$ |
| Portfolio Turnover | $TO$ | Percentage (`0.00%`) | Annualized Rebalance Sum | Net portfolio trades | No rebalances executed |
| Transaction Cost Drag | $D_{\text{fric}}$ | Basis Points (`0.0 bps`) | Aggregate Fee + Slippage / NAV | Net portfolio drag | Trade fill logs missing |
| Probability of Backtest Overfitting | $\text{PBO}$ | Probability (`0.00%`) | CSCV Combinatorial Evaluation | Research Trials | Trials $N < 2$ or Combinations $< 2$ |
| Deflated Sharpe Ratio | $\text{DSR}$ | Probability (`0.00%`) | Bailey & López de Prado (2014) | Multiple Testing Adj | In-sample Sharpe is non-finite |

---

## 5. Missing-Data, Warning, and Error Semantics

The reporting engine enforces a strict taxonomy for metric presence and missing data:
1. **Available:** Data was provided and validated, and calculation executed successfully.
2. **Unavailable:** Required source inputs (such as trade fills, tick data, or benchmark series) do not exist in the source run.
3. **Undefined:** Inputs are present, but the mathematical operation is undefined (e.g. division by zero in Calmar ratio when $MDD = 0.0$, or non-convergent MinBTL when Sharpe $\le SR^*$). Represented strictly as `None` in models and formatted as `"Undefined"` in UI.
4. **Invalid:** Inputs violate domain rules or constraints (e.g. negative prices, dates out of bounds). Triggers model validation errors (`ValidationError`) or warning generation.
5. **Not Applicable:** The metric is outside the mandate or configuration of the report (e.g., active return when no benchmark was configured). Represented as `None` with `BenchmarkRelativeMetrics = None`.

### Warning Architecture (`ReportWarning`)
Warnings are non-fatal, structured notifications embedded directly into the report envelope:
- `code`: Stable string identifier (e.g. `WARN_NO_BENCHMARK`, `WARN_MISSING_SNAPSHOT`, `WARN_INCOMPLETE_TCA`).
- `severity`: Structured level (`INFO`, `WARNING`, `CRITICAL`).
- `message`: Sanitized institutional explanation with no internal stack traces or secrets.
- `affected_metric`: Optional metric key affected by the warning.

---

## 6. Analytical Fixtures Specification

Located in `backend/tests/fixtures/reporting_fixtures.py`, 15 deterministic fixtures ensure reproducible test verification across normal and edge cases:

1. `FIXTURE_VALID_TEAR_SHEET_NET_BENCHMARK`: Complete 252-day institutional tear sheet with net returns and S&P 500 benchmark.
2. `FIXTURE_VALID_DUAL_GROSS_NET_TEAR_SHEET`: Dual return stream report showing 35.8 bps fee and slippage drag.
3. `FIXTURE_NO_BENCHMARK_REPORT`: Absolute-return hedge fund strategy with `benchmark_metrics = None` and `WARN_NO_BENCHMARK` warning.
4. `FIXTURE_UNDEFINED_METRICS_REPORT`: Perfect upward equity curve ($MDD = 0.0$, Calmar is `None`, Information Ratio is `None`).
5. `FIXTURE_INCOMPLETE_PERIOD_REPORT`: 12-day short track record emitting an `INFO` warning on annualization reliability.
6. `FIXTURE_CURRENCY_MISMATCH_REPORT`: Multi-currency portfolio (USD cash, EUR assets) emitting `WARN_CURRENCY_MISMATCH`.
7. `FIXTURE_MISSING_SNAPSHOT_REPORT`: Report derived from mutable operational data with `WARN_MUTABLE_DATASET` disclosure.
8. `FIXTURE_IDENTIFIED_SNAPSHOT_REPORT`: Fully verified Stage 32 report with SHA-256 manifest digest and snapshot ID.
9. `FIXTURE_PARTIAL_TCA_REPORT`: Valid commission tracking but unavailable slippage logs emitting `WARN_PARTIAL_TCA`.
10. `FIXTURE_VALID_STAGE_33_RESEARCH_ANNEX`: 50-trial research experiment with valid PBO (14.2%), DSR (0.978), and MinBTL (1.42 years).
11. `FIXTURE_UNDEFINED_STAGE_33_RESEARCH_ANNEX`: Underperforming strategy ($SR \le SR^*$) with mathematically undefined MinBTL (`None`).
12. `FIXTURE_MALFORMED_PERIOD_PAYLOAD`: Invalid date chronology (`start_date > end_date`) asserting schema rejection.
13. `FIXTURE_EMPTY_ALLOCATIONS_REPORT`: Cash-only portfolio with empty allocation lists.
14. `FIXTURE_LARGE_TIMESERIES_REPORT`: 5-year daily time series (1,260 points) verifying serialization efficiency ($< 35\text{ ms}$).
15. `FIXTURE_SERIALIZATION_WARNINGS_REPORT`: Multi-severity warnings array testing lossless JSON round-tripping.

---

## 7. Verification Evidence

### 7.1 Automated Contract & Fixture Tests
Execution of `backend/tests/test_reporting_contracts.py` alongside Stage 33 regression suites:
```bash
.\backend\.venv\Scripts\pytest.exe backend/tests/test_reporting_contracts.py backend/tests/test_overfitting_engine.py backend/tests/test_overfitting_api.py -v
```
**Output:**
```
============================== 64 passed in 2.88s ==============================
```
- 21 dedicated Stage 34 Gate A reporting contract tests passed in 0.94s.
- 43 Stage 33 regression tests passed with zero regressions.

### 7.2 Frontend TypeScript & Lint Verification
```bash
npx vitest run --pool=threads
npm run build
npm run lint
```
**Output:**
```
Test Files  4 passed (4)
     Tests  73 passed (73)
  Duration  8.14s
vite v5.4.19 building for production...
✓ 1876 modules transformed.
dist/index.html                   0.84 kB │ gzip:  0.42 kB
dist/assets/index-CQH-YF0G.css   57.65 kB │ gzip: 10.42 kB
dist/assets/index-DKj27a44.js   566.21 kB │ gzip: 153.28 kB
✓ built in 2.04s
eslint: 0 errors, 0 warnings
```

---

## 8. Client-Side CSS Paged Media Architecture & Security Boundaries

### 8.1 Why Client-Side CSS Paged Media?
In financial software, server-side PDF engines (e.g. WeasyPrint, Headless Chrome/Puppeteer, ReportLab) introduce substantial operational overhead:
- Heavy system binaries and native C dependencies (Cairo, Pango) that complicate cross-platform deployment.
- High memory footprint and CPU spikes during high-concurrency export operations.
- Font rendering discrepancies between browser web view and server-side PDF generation.
- Increased attack surface (SSRF, local file read exploits via headless browser rendering).

By adopting client-side CSS Paged Media (`@page`, `@media print`), the engine leverages the user's native, hardware-accelerated browser printing engine:
- Visual fidelity is $100\%$ pixel-identical to the on-screen preview.
- Scalable vector SVG charts print at native 600+ DPI printer resolution without rasterization artifacts.
- Zero server-side rendering vulnerabilities.

### 8.2 Security Boundaries
1. **XSS & HTML Injection Prevention:** Reports never accept raw unescaped HTML strings from client input. All narrative text is parsed and rendered as pure text or bounded Markdown.
2. **Tenant Isolation:** Report generation strictly enforces tenant boundary authorization on underlying backtest and experiment IDs before payload compilation.
3. **Lineage Authentication:** Snapshot digests ensure that report data reflects immutable frozen history, preventing post-facto modification.

---

## 9. Decisions Deferred to Subsequent Gates

| Gate | Scope | Deferred Decisions & Implementation Items |
| :--- | :--- | :--- |
| **Gate B** | Report Aggregation & Assembler Service | Aggregation service combining backtest runs, benchmark series, and Stage 32/33 outputs into report models; warning generation logic; caching. |
| **Gate C** | Institutional PDF Templates & Print CSS | 1-page Fact Sheet, 2-page Tear Sheet, and 3-page Annex visual layouts; `@page` margin rules; vector SVG charting components; page-break controls. |
| **Gate D** | Application & UI Integration | "Export Institutional PDF" triggers in Backtesting and Research Lab pages; interactive print preview modal; export status handling. |
| **Gate E** | Independent Release Audit | Full independent quantitative and visual audit across all three report types; print fidelity verification; final stage acceptance review. |

---

## 10. Gate A Verdict & Governance Sign-Off

**Verdict:** `PASS — GATE A COMPLETE`  
**Evidence:**
- Domain contracts and schemas implemented in Pydantic v2 and TypeScript.
- Metric registry formally specifies 15 canonical quantitative metrics.
- 15 deterministic analytical fixtures covering normal and edge cases established.
- 100% test pass rate across 21 dedicated contract tests, 43 Stage 33 regression tests, 73 frontend tests, clean Vite production build, and clean ESLint.
- Scope boundary preserved: zero server-side PDF engines, zero database migrations, zero API routes created.
- Readiness confirmed to proceed to Gate B upon Project Owner review and approval.
