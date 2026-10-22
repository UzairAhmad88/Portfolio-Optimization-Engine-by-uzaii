# Stage 34 Gate C: Institutional Paged-Media Layouts & Vector Charts

**Status:** IMPLEMENTED — Awaiting Independent Review & Acceptance  
**Branch:** `main`  
**Base Commit:** `61b50c0`  
**Delivery Scope:** Presentation Layer, Vector Visualizations, and CSS Paged Media System for Stage 34 Institutional Reports.

---

## 1. Executive Summary

Stage 34 Gate C establishes the client-side, print-ready institutional reporting presentation engine for the Quantitative Portfolio Optimization Engine.

Rather than introducing heavy, brittle server-side headless browser dependencies (e.g. Puppeteer, Playwright, WeasyPrint), Gate C leverages **native CSS Paged Media standards (`@page`, `@media print`)** paired with **vector-sharp SVG components** and a responsive screen-preview canvas. This enables quant researchers, portfolio managers, and investment committees to review institutional Fact Sheets and Tear Sheets on-screen and print or export them to PDF directly using the browser's native **Print / Save as PDF** dialog (`Ctrl+P` / `Cmd+P`).

---

## 2. Component Architecture & Modular Layouts

All reporting presentation components reside under `frontend/src/components/reports/`:

```
frontend/src/components/reports/
├── formatters.ts                     # Institutional currency, basis point, ratio & null-safe formatters
├── ReportHeaderAndProvenance.tsx    # Executive branded header, mandate strip, warnings banner & lineage footer
├── ExecutiveKPISummary.tsx           # Dual Gross vs Net performance grid & benchmark active attribution strip
├── VectorEquityCurve.tsx             # Zero-dependency SVG wealth curve with net/gross/benchmark & drawdown overlay
├── MonthlyReturnsGrid.tsx            # Compounded discrete monthly matrix with emerald/crimson shading & YTD totals
├── AssetAllocationChart.tsx          # Vector stacked allocation bar & top holdings contribution table
├── ResearchDiagnosticsVisuals.tsx   # Overfitting degradation OLS scatter & PBO relative rank histogram
├── StrategyFactSheetView.tsx         # Exactly 1-Page Strategy Fact Sheet document
├── InstitutionalTearSheetView.tsx    # Exactly 2-Page Institutional Tear Sheet document (Page 1: Risk, Page 2: Alloc/TCA)
├── ResearchDiagnosticsAnnexView.tsx  # Optional 3rd-Page Research Diagnostics Annex (CSCV / Overfitting)
├── InstitutionalReportViewer.tsx     # Master interactive studio with tabbed views, annex toggle & print trigger
└── index.ts                          # Component export barrel
```

### Component Roles & Specifications

| Component | Intended Output | Key Data Rendered |
| :--- | :--- | :--- |
| **`StrategyFactSheetView`** | **Exactly 1 Page** | Executive mandate, Dual Gross/Net KPIs, benchmark strip, 250-point downsampled wealth curve, discrete monthly grid, top 6 asset holdings, certified dataset snapshot ID & cryptographic digest. |
| **`InstitutionalTearSheetView`** | **Exactly 2 Pages** | **Page 1:** Executive KPIs, benchmark relative alpha/beta/IR, high-resolution vector wealth curve with underwater drawdown overlay, peak-to-trough drawdown details.<br>**Page 2:** Complete monthly return matrix, complete asset allocations with return contributions, Transaction Cost Analysis (TCA), turnover, and friction drag. |
| **`ResearchDiagnosticsAnnexView`** | **Optional Page 3** | Combinatorially Symmetric Cross-Validation (CSCV) metrics: Probability of Backtest Overfitting (PBO), Deflated Sharpe Ratio (DSR), Minimum Backtest Length (MinBTL), OLS regression degradation scatter, rank histogram, and academic methodology disclaimer (Bailey et al.). |
| **`InstitutionalReportViewer`** | **Interactive Screen & Print Shell** | Screen toolbar with tab switching (Fact Sheet vs Tear Sheet vs Unified Complete Dossier), toggle for optional research annex, and native browser print trigger. |

---

## 3. Financial Visualization & Vector Charts

All visual charts are built with **pure SVG elements** without external charting library dependencies, ensuring deterministic rendering, zero bundle bloat, and infinite resolution scaling when printed or saved to PDF:

1. **`VectorEquityCurve` (`VectorEquityCurve.tsx`):**
   - Synchronizes Portfolio Net NAV, Portfolio Gross NAV, and scaled Benchmark wealth ($V_0 \cdot \prod (1 + r_{bm, t})$).
   - Renders dual-gradient area shading under the Net NAV curve.
   - Provides optional underwater drawdown overlay shaded in subtle crimson.
   - Preserves downsampled observation points faithfully without synthesizing interpolated points.
2. **`MonthlyReturnsGrid` (`MonthlyReturnsGrid.tsx`):**
   - Displays discrete monthly returns compounded geometrically: $R_M = \prod_{t \in M}(1 + r_t) - 1$.
   - Computes compounded annual/YTD totals across all recorded trading months.
   - Color-coded dynamically based on return magnitude with high-contrast text thresholds.
3. **`AssetAllocationChart` (`AssetAllocationChart.tsx`):**
   - Horizontal stacked vector bar displaying asset weight distribution.
   - Detailed holdings table displaying ticker, market, target weight, effective weight, cumulative asset return, and active return contribution.
4. **`ResearchDiagnosticsVisuals` (`ResearchDiagnosticsVisuals.tsx`):**
   - **IS vs OOS Performance Degradation Scatter:** Plots in-sample vs out-of-sample Sharpe ratios for CSCV sub-matrices with an OLS regression trendline ($R^2$, slope, and $p$-value).
   - **Relative Rank Distribution Histogram:** Visualizes the frequency of strategy rankings in test partitions, highlighting the median overfit threshold ($\text{Rank} > 0.5$).

---

## 4. CSS Paged Media & Browser Print Specifications

The print stylesheet is defined directly in `frontend/src/index.css`:

```css
@page {
  size: letter portrait;
  margin: 10mm 12mm 10mm 12mm;
}

@media print {
  /* Suppress screen navigation, headers, toolbars, and controls */
  .no-print, .report-toolbar, .sidebar, .header, .app-sidebar, .app-header {
    display: none !important;
  }

  /* Reset canvas background to clean white */
  html, body {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }

  /* Physical page separation and break control */
  .report-sheet-page {
    width: 100% !important;
    box-shadow: none !important;
    page-break-after: always !important;
    break-after: page !important;
  }

  /* Prevent broken tables and split KPI cards */
  .report-kpi-grid,
  .report-two-panel-grid,
  .report-monthly-grid-container,
  .report-allocation-container,
  .report-tca-section,
  .report-visual-two-col {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
  }
}
```

### Verified Print Behavior
- **Target Paper Size:** Standard US Letter (8.5in × 11in) and international A4 (210mm × 297mm).
- **Margins:** 10mm top/bottom, 12mm left/right.
- **Color Fidelity:** `-webkit-print-color-adjust: exact` forces browser print engines to render table heatmaps, SVG gradients, and allocation colors without stripping them.

---

## 5. Quantitative Data Integrity & Zero-Coercion Policy

The presentation layer operates as a **strictly pure renderer** of authorized backend payloads:
1. **Zero Coercion Rule:** Missing, unavailable, or undefined metrics (e.g. Calmar ratio with 0.0 drawdown, or Sharpe ratio with zero volatility) are rendered as an em-dash (`—`), never coerced to `0.0`, `NaN`, or fabricated numbers.
2. **Gross vs. Net Preservation:** All KPI components explicitly display both Net and Gross values when gross data exists in the payload, clearly distinguishing post-friction returns.
3. **Structured Warnings Banner:** If the envelope contains warnings (such as `WARN_MUTABLE_DATASET` or `WARN_NO_BENCHMARK`), an alert banner is rendered prominently at the top of the report.
4. **Data Lineage:** Every report footer discloses dataset ID, certified snapshot UUID, manifest SHA-256 digest, and statutory hypothetical performance disclaimers.

---

## 6. Verification & Test Evidence

### Test Execution
```bash
npm test
```
**Results:**
- `src/test/reporting-presentation.test.tsx`: 15 passed (100%)
- `src/test/overfitting-diagnostics.test.tsx`: 21 passed (100%)
- `src/test/api-client.test.ts`: 43 passed (100%)
- `src/test/snapshot-provenance.test.tsx`: 5 passed (100%)
- `src/test/App.test.tsx`: 4 passed (100%)
- **Total Frontend Test Suite:** **88/88 passed** across 5 test files.

### Production Typecheck & Build
```bash
npm run build (tsc -b && vite build)
```
- **Exit Status:** `0` (Success, no TypeScript errors).
- **Bundle Output:** `dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`.

### Linting & Code Quality
```bash
npm run lint (oxlint)
```
- **Exit Status:** `0` (0 errors).
- **Whitespace / Git Check:** `git diff --check` executed cleanly with zero warnings or trailing whitespace.
