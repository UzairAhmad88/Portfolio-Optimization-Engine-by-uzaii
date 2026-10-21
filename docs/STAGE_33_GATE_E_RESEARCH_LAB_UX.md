# Stage 33 — Gate E: Institutional Research Lab UX, Overfitting Diagnostics Visualizations & Tear-Sheet Components

**Stage:** 33 — Combinatorial Cross-Validation, Backtest Overfitting Diagnostics & Deflated Sharpe Ratio Engine  
**Gate:** E — Research Lab UX and Overfitting Diagnostics Visualizations  
**Status:** Completed  
**Repository:** `UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Workspace:** `d:\Quants\Projects\quant-portfolio-engine-starter`  
**Branch:** `main`  
**Prior Gate Commit:** `f1fe3c4c02fd4212b430c1fe1fa1425f3ec363d7` (Gate D)

---

## 1. Executive Summary

Stage 33 Gate E delivers an institutional-grade quantitative research workstation for backtest overfitting diagnostics, Deflated Sharpe Ratio (DSR) evaluation, Combinatorially Symmetric Cross-Validation (CSCV), Probability of Backtest Overfitting (PBO), and Minimum Backtest Length (MinBTL).

The implementation strictly honors the primary principle: **visual polish must never conceal statistical uncertainty, incomplete evidence, invalid inputs, or the limitations of the underlying methods.**

### Key Capabilities Delivered
1. **Interactive Overfitting Diagnostics Studio:** A dedicated workspace (`OverfittingDiagnosticsStudio.tsx`) integrated directly into `ResearchLabPage.tsx` under a new `'overfitting'` tab, plus direct shortcut navigation from the research experiment catalog.
2. **Dynamic Run & Partition Configuration:** Researcher-driven selection of candidate strategy runs (with strict fail-closed enforcement of $\ge 2$ runs), configurable CSCV partition slices $S \in [4, 16]$, significance levels $\alpha \in \{0.01, 0.05, 0.10\}$, and annualization factors.
3. **Core Institutional Scorecard:**
   - **PBO:** Percentage estimate with institutional risk badges (`low`, `moderate`, `high`, `severe`) derived strictly from backend classification contracts.
   - **DSR:** Deflated Sharpe Ratio probability with explicit hypothesis testing badges (`Significant (p < alpha)` vs `False Discovery Risk`), contrasting observed nominal Sharpe against expected maximum Sharpe ($SR^*$) under the null hypothesis.
   - **MinBTL:** Minimum Backtest Length in years, gracefully handling undefined values (e.g. when observed Sharpe $\le$ benchmark or non-convergent) as `"Undefined under current assumptions"` without ever emitting `null`, `NaN`, or `Infinity`.
   - **Degradation Slope ($\beta$):** Ordinary Least Squares (OLS) regression metrics of Out-of-Sample (OOS) Sharpe on In-Sample (IS) Sharpe across CSCV splits.
4. **Accessible Native SVG Visualizations:**
   - **CSCV Scatter Plot:** In-Sample vs Out-of-Sample Sharpe scatter plot with $y = x$ zero-degradation parity line, OLS degradation regression line, interactive split tooltips, and an accessible data table toggle.
   - **Relative-Rank Histogram:** 10-decile distribution of normalized Out-of-Sample relative ranks $\bar{\omega} \in [0, 1]$ with an explicit vertical cutoff at $\bar{\omega} = 0.5$ (median rank) denoting the PBO threshold, complete with tabular view toggling.
5. **Multi-Trial Run Summary Table:** Financial table of all evaluated candidate trials with sortable columns, nominal Sharpe ratios, In-Sample selection frequencies, mean OOS Sharpe and rank when selected, and best-trial distinctions.
6. **Self-Contained Research Tear Sheet & Export:** One-click exports in **CSV** (runs summary + combination points), **JSON** (full raw API response), and **Markdown** (pre-formatted GitHub-Flavored Markdown institutional research memo copied to clipboard).
7. **Fail-Closed Truth in Financial UX:** Stale-result invalidation banners when parameters change after execution, visible data alignment and provenance warnings, and formal methodology disclosures.

---

## 2. Architecture & Component Responsibilities

### Frontend File Map
| File | Role & Responsibilities |
| :--- | :--- |
| `frontend/src/types/api.ts` | Added Stage 33 domain contracts: `PBORiskLevel`, `OverfittingDiagnosticsRequest`, `DegradationRegression`, `CSCVCombinationsPoint`, `CSCVHistogramBin`, `RunOverfittingSummary`, `OverfittingDiagnosticsResponse`. |
| `frontend/src/api/client.ts` | Added authenticated client method `apiClient.computeOverfittingDiagnostics(experimentId, payload)`. |
| `frontend/src/components/research/OverfittingDiagnosticsStudio.tsx` | Primary research lab component: parameter configuration, run checklist, KPI cards, SVG scatter plot, SVG rank histogram, tabular fallbacks, per-run table, tear sheet, and export handlers. |
| `frontend/src/components/pages/ResearchLabPage.tsx` | Registered `'overfitting'` in `ActiveTab`, added navigation tab, added catalog table action button, and wired state to `OverfittingDiagnosticsStudio`. |
| `frontend/src/test/overfitting-diagnostics.test.tsx` | Comprehensive test suite (12 tests) verifying API client dispatch, run selection, parameter validation, loading states, error states, SVG charts, accessibility toggles, and tear sheet export. |

---

## 3. Integration & Contract Alignment

### Authenticated REST API Endpoint
```http
POST /api/v1/research/experiments/{experiment_id}/overfitting-diagnostics
Content-Type: application/json
Authorization: Bearer <token>
```

#### Request Payload (`OverfittingDiagnosticsRequest`)
```json
{
  "experiment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "run_ids": ["run-uuid-1", "run-uuid-2", "run-uuid-3"],
  "n_slices": 16,
  "significance_level": 0.05,
  "annualization_factor": 252
}
```

#### Response Contract (`OverfittingDiagnosticsResponse`)
- **Sample Dimensions:** `evaluated_runs_count`, `aligned_observations_count`, `n_slices`, `total_combinations_count`.
- **PBO Metrics:** `pbo` ($\in [0, 1]$), `pbo_risk_level` (`low`, `moderate`, `high`, `severe`).
- **Deflated Sharpe Metrics:** `best_run_id`, `best_run_number`, `best_nominal_sharpe`, `expected_max_sharpe`, `deflated_sharpe_ratio`, `is_statistically_significant`.
- **Track Record & Moments:** `min_backtest_length_years` (`float | null`), `actual_backtest_length_years`, `skewness`, `kurtosis`.
- **CSCV Analytics:** `degradation_regression` (slope $\beta$, intercept $\alpha$, $R^2$), `combinations_sample` (points), `rank_distribution` (10 histogram bins), `runs_summary` (per-run statistics).
- **Provenance & Warnings:** `snapshot_id`, `warnings`, `generated_at`.

---

## 4. Visualizations & Analytical Interpretation

### 1. In-Sample vs Out-of-Sample Sharpe Scatter Plot (`CSCVScatterChart`)
- **Axes:** X-axis = In-Sample Sharpe Ratio ($SR_{IS}$); Y-axis = Out-of-Sample Sharpe Ratio ($SR_{OOS}$).
- **Points:** Rendered from `combinations_sample`. Color-coded by `is_overfitted`:
  - **Red / Coral:** $\bar{\omega} \le 0.5$ (Overfitted partition where selected strategy ranks at or below the median).
  - **Green / Emerald:** $\bar{\omega} > 0.5$ (Persistent partition where selected strategy outperforms the median).
- **Reference Lines:**
  - **1:1 Parity Line (Dashed Gray):** $y = x$, representing zero performance degradation between IS and OOS.
  - **Degradation Line (Solid Accent Blue):** Ordinary Least Squares fitted line $y = \beta x + \alpha$. $\beta \approx 1$ signifies alpha persistence; $\beta \le 0$ indicates complete overfitting.
- **Interactivity:** Point hover displays Combination Split ID, Selected Strategy Run ID, IS Sharpe, OOS Sharpe, OOS rank, and normalized relative rank $\bar{\omega}$.
- **Accessibility:** "Show Data Table" toggle provides a fully accessible HTML table of all combination splits.

### 2. Out-of-Sample Relative-Rank Distribution (`CSCVHistogramChart`)
- **Domain:** Relative rank $\bar{\omega} = \frac{\text{oos\_rank}}{N + 1} \in [0, 1]$.
  - $\bar{\omega} = 0.0$: Worst possible out-of-sample performance across all $N$ candidate strategies.
  - $\bar{\omega} = 1.0$: Best possible out-of-sample performance across all $N$ candidate strategies.
- **PBO Cutoff Line:** Vertical dashed line at $\bar{\omega} = 0.5$ (Median rank).
- **Bar Coloring:** Bins $\le 0.5$ are highlighted in red (representing the cumulative area equal to PBO); bins $> 0.5$ are green.
- **Accessibility:** "Show Data Table" toggle allows reviewing bin bounds, counts, and relative frequencies in tabular format.

### 3. Multi-Trial Candidate Summary Table
- **Columns:** Run Number, Strategy UUID, Nominal Sharpe, In-Sample Selection Frequency, Mean OOS Sharpe When Selected, Mean OOS Relative Rank When Selected, Status/Distinction.
- **Sorting:** Interactive ascending/descending sorting across any numeric metric.
- **Best Strategy Distinction:** Highlighted row with a distinct gold badge for the strategy achieving the highest nominal Sharpe.
- **Missing-Value Handling:** Strategies never selected In-Sample display clean dashes (`—`) rather than `null` or `0.0`.

---

## 5. Research Tear Sheet & Export Capabilities

The Institutional Tear Sheet provides a self-contained report view suitable for investment committee reviews, quant research memos, and compliance archiving:

1. **Copy Tear Sheet (Markdown):** Copies a formatted GitHub-Flavored Markdown summary table to the clipboard with metadata, core metrics, sample dimensions, and methodology disclosures.
2. **Download CSV:** Exports a comprehensive spreadsheet containing experiment metadata, run-level summary performance, and combinatorial split observations.
3. **Download JSON:** Exports the complete, unadulterated raw API response for programmatic archiving and reproducibility audit trails.

---

## 6. Accessibility & Responsive Design

- **Semantic Hierarchy:** Logical `h2`, `h3`, `h4`, `label`, and `table` elements.
- **Non-Color Reliance:** Statuses, risk levels, and significance indicators always include text descriptions, icons, and numerical percentages alongside color tokens.
- **Responsive Layout:** Responsive CSS Grid (`repeat(auto-fit, minmax(...))`) and scalable native SVG with `viewBox` coordinates ensure fluid readability across mobile, tablet, and 4K displays.
- **Tabular Alternatives:** Every SVG chart includes an accessible toggle to inspect data in standard HTML tables for screen reader users and financial analyst copy-pasting.

---

## 7. Verification Evidence

### Frontend Tests (`vitest`)
```bash
npm test
```
**Result: 64 passed across 4 test files in 4.29s**
- `src/test/overfitting-diagnostics.test.tsx`: 12 passed
- `src/test/api-client.test.ts`: 43 passed
- `src/test/snapshot-provenance.test.tsx`: 5 passed
- `src/test/App.test.tsx`: 4 passed

### Production Build & Typecheck (`tsc -b && vite build`)
```bash
npm run build
```
**Result: Code 0 (Success in 700ms)**
- TypeScript compilation: 0 errors
- Bundled production chunks: `dist/assets/index-CHt709Pj.js` (894 kB), `dist/assets/index-DtJMXJ5u.css` (10.6 kB).

### Linting (`npm run lint`)
```bash
npm run lint
```
**Result: 0 errors (Code 0)**

### Backend Regression Suite (`pytest backend/tests`)
```bash
.\backend\.venv\Scripts\pytest.exe backend/tests/test_overfitting_api.py backend/tests/test_overfitting_engine.py
```
**Result: 41 passed in 1.37s**

---

## 8. Completion Criteria & Gate Verdict

All Gate E completion criteria specified in Session 65 have been satisfied:
- [x] Research Lab workflow integrated with the existing authenticated overfitting diagnostics API.
- [x] Users can configure CSCV slices, significance levels, annualization factors, and candidate run subsets.
- [x] PBO, DSR, MinBTL, and degradation metrics accurately presented without confounding definitions.
- [x] Interactive native SVG visualizations for CSCV scatter degradation and relative-rank distribution.
- [x] Advisory warnings and snapshot provenance remain visible and prominent.
- [x] Stale results invalidated when parameters change; errors handled fail-closed.
- [x] Institutional research tear sheet with multi-format export (Markdown, CSV, JSON).
- [x] Accessibility and responsive behavior verified.
- [x] All 64 frontend tests, 41 backend overfitting tests, production build, and linting pass.

**Gate E Verdict:** `PASS` (Remediated in Session 67)

---

## 9. Session 67 Gate E Remediation Verification

Following the Session 66 independent quantitative audit, four specific findings were remediated and verified:

### 1. `DEF-E-01` — PBO Histogram Boundary Consistency (P1)
- **Disposition:** Remediated and tested.
- **Root Cause:** Half-open interval convention in `backend/app/analytics/overfitting.py` placed relative ranks of exactly 0.5 into Bin 5 (`[0.5, 0.6)`), whereas PBO inclusively defines overfitted splits as $\omega_c \le 0.5$.
- **Remediation:**
  - In `backend/app/analytics/overfitting.py`, modified decile binning: Bins 0..3 partition $[0.0, 0.4)$, Bin 4 covers $[0.4, 0.5]$ (inclusive of 0.5 boundary), and Bins 5..9 partition $(0.5, 1.0]$.
  - The sum of counts and relative frequencies of bins with `bin_end <= 0.5` now reconciles to exact equality with the PBO count and probability.
  - In `frontend/src/components/research/OverfittingDiagnosticsStudio.tsx`, introduced `formatHistogramBinRange` displaying `[start, end)` for bins $< 0.5$, `[0.40, 0.50]` for the median boundary, and `(start, end]` for bins $> 0.5$.
- **Test Evidence:** Verified via `TestHistogramBoundaryConsistency` in `backend/tests/test_overfitting_engine.py` (deterministic 3-strategy panel and explicit boundary array `[0.0, 0.49, 0.50, 0.51, 1.0]`), plus Vitest table range verification.

### 2. `DEF-E-02` — CSCV Scatter Subsampling Disclosure (P2)
- **Disposition:** Remediated and tested.
- **Root Cause:** When CSCV splits exceeded 500, the scatter plot rendered 500 sample points, but the header labeled it as `"500 CSCV combinations"` without clarifying that 500 was an evenly-spaced subsample of the total combinatorial count $C$.
- **Remediation:**
  - In `frontend/src/components/research/OverfittingDiagnosticsStudio.tsx`, implemented `formatCscvSamplingDisclosure(sampleCount, totalCount)`.
  - When subsampled, header displays: `{sampleCount} sampled points of {totalCount} total CSCV combinations`.
  - Handles complete partitions (`{totalCount} total CSCV combinations (complete partition)`) and missing total-count metadata gracefully.
- **Test Evidence:** Verified across all four branching paths via Vitest unit tests in `frontend/src/test/overfitting-diagnostics.test.tsx`.

### 3. `DEF-E-03` — CSV Escaping & Warning Preservation (P2)
- **Disposition:** Remediated and tested.
- **Root Cause:** `handleExportCsv` concatenated unescaped strings (risking column shifting if names contained commas or quotes) and omitted advisory warnings from the CSV report.
- **Remediation:**
  - Implemented standard RFC 4180 CSV helpers `escapeCsvField` (wrapping commas/quotes/newlines in double quotes, doubling embedded quotes) and `toCsvRow`.
  - Exported `generateDiagnosticsCsv` creating self-contained reports that serialize the `--- ADVISORY WARNINGS ---` section, preserving null metrics as `'Undefined'` and maintaining full provenance.
- **Test Evidence:** Verified with unit tests covering commas, quotes, newlines, missing MinBTL, and warning arrays in `frontend/src/test/overfitting-diagnostics.test.tsx`.

### 4. `DEF-E-04` — SVG Regression Line Plot Area Clipping (P3)
- **Disposition:** Remediated and tested.
- **Root Cause:** Steep regression slopes could project `regYStart` or `regYEnd` beyond visible $[yMin, yMax]$ bounds without clipping, protruding past the SVG chart grid.
- **Remediation:**
  - In `CSCVScatterChart`, generated a unique clip identifier using React's `useId()` hook (`clipId`).
  - Added `<defs><clipPath id={clipId}><rect ... /></clipPath></defs>` covering the plot area rectangle.
  - Wrapped zero lines, parity line, degradation regression line, and scatter circles inside `<g clipPath={`url(#${clipId})`}>`.
  - Left axes, tick marks, numeric labels, and axis titles outside the clip group to ensure they remain crisp and unclipped.
- **Test Evidence:** Verified via DOM tree assertions in `frontend/src/test/overfitting-diagnostics.test.tsx` confirming `<clipPath>` presence, unique scoping, and containment.

