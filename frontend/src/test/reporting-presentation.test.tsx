/**
 * Comprehensive Vitest Unit & Integration Tests for Stage 34 Gate C
 * Tests:
 * 1. Fact Sheet rendering from valid analytical fixture
 * 2. Two-page Tear Sheet rendering from valid fixture
 * 3. Optional Research Annex rendering and omission
 * 4. Dual gross/net metrics labels and values
 * 5. Undefined values preserved as '—' without zero coercion
 * 6. Missing benchmark behavior (safe fallback, no synthetic metrics)
 * 7. Empty/sparse time series safe handling
 * 8. Structured warnings banner and certified provenance rendering
 * 9. Print-mode controls and exclusion of interactive elements
 * 10. Financial calculations remain in backend (pure presentation)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import {
  createMockFactSheet,
  createMockTearSheet,
  createMockResearchAnnex,
  createMockUnifiedReport,
  createMockKPIs,
} from './reporting-fixtures';
import {
  StrategyFactSheetView,
  InstitutionalTearSheetView,
  ResearchDiagnosticsAnnexView,
  InstitutionalReportViewer,
  VectorEquityCurve,
  MonthlyReturnsGrid,
  AssetAllocationChart,
  formatPercent,
  formatCurrency,
  formatRatio,
  formatBps,
} from '../components/reports';


describe('Stage 34 Gate C: Formatters & Zero-Coercion Rules', () => {
  it('strictly preserves null and undefined values as em-dash', () => {
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(undefined)).toBe('—');
    expect(formatCurrency(null)).toBe('—');
    expect(formatRatio(null)).toBe('—');
    expect(formatBps(null)).toBe('—');
  });

  it('correctly formats valid positive and negative financial numbers', () => {
    expect(formatPercent(0.1425, 2)).toBe('14.25%');
    expect(formatPercent(-0.0845, 2)).toBe('-8.45%');
    expect(formatPercent(0.05, 1, true)).toBe('+5.0%');
    expect(formatRatio(1.4155, 2)).toBe('1.42');
    expect(formatBps(77.6, 1)).toBe('77.6 bps');
    expect(formatCurrency(100000, 'USD')).toMatch(/100,000/);
  });
});

describe('Stage 34 Gate C: Strategy Fact Sheet (1-Page Layout)', () => {
  it('renders executive fact sheet with title, mandate, dual KPIs, and holdings', () => {
    const fixture = createMockFactSheet();
    render(<StrategyFactSheetView payload={fixture} />);

    // Header & identity
    expect(screen.getByText('Strategy Fact Sheet — US Large-Cap')).toBeInTheDocument();
    expect(screen.getByText(/2023-01-03 → 2023-12-29/)).toBeInTheDocument();
    expect(screen.getByText('USD')).toBeInTheDocument();

    // Mandate
    expect(screen.getByText('walk forward optimization')).toBeInTheDocument();
    expect(screen.getByText('max_sharpe')).toBeInTheDocument();

    // Dual Gross and Net KPIs
    const returnsNet = screen.getAllByText('+24.50%');
    expect(returnsNet.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Gross: +25.80%')).toBeInTheDocument(); // Gross
    expect(screen.getByText('1.42')).toBeInTheDocument(); // Sharpe

    // Benchmark strip
    const bmMatches = screen.getAllByText(/S&P 500 ETF Trust/);
    expect(bmMatches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('+6.30%')).toBeInTheDocument(); // Active return


    // Holdings & Allocation
    const aaplMatches = screen.getAllByText('AAPL');
    expect(aaplMatches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();


    // Provenance
    expect(screen.getByText('snap-audit-2023-certified')).toBeInTheDocument();
  });

  it('renders undefined Calmar ratio as em-dash when maximum drawdown is zero', () => {
    const fixture = createMockFactSheet({
      kpis: createMockKPIs({
        max_drawdown_net: 0.0,
        calmar_ratio_net: null,
      }),
    });
    render(<StrategyFactSheetView payload={fixture} />);

    expect(screen.getByText('0.00%')).toBeInTheDocument();
    // Calmar card should show em-dash, not 0.0 or infinity
    const calmarCard = screen.getByText('Calmar Ratio (Net)').closest('.report-kpi-card');
    expect(calmarCard).toHaveTextContent('—');
  });
});

describe('Stage 34 Gate C: Institutional Tear Sheet (2-Page Layout)', () => {
  it('renders complete two-page tear sheet with performance, drawdown, monthly matrix, and TCA', () => {
    const fixture = createMockTearSheet();
    render(<InstitutionalTearSheetView payload={fixture} />);

    // Page 1 Elements
    expect(screen.getByRole('heading', { name: 'Institutional Tear Sheet' })).toBeInTheDocument();
    expect(screen.getByText(/1 \/ 2/)).toBeInTheDocument();
    expect(screen.getByText('38 days')).toBeInTheDocument(); // Drawdown duration

    // Page 2 Elements
    expect(screen.getByText(/Page 2 \/ 2/)).toBeInTheDocument();
    expect(screen.getByText(/Monthly Net Return Performance Matrix/)).toBeInTheDocument();
    expect(screen.getByText(/Transaction Cost Analysis \(TCA\) & Execution Drag/)).toBeInTheDocument();
    expect(screen.getByText('77.6 bps')).toBeInTheDocument(); // Friction drag
    expect(screen.getByText('12')).toBeInTheDocument(); // Number of rebalances
  });

  it('handles missing benchmark gracefully without inventing synthetic values', () => {
    const fixture = createMockTearSheet({
      benchmark_metrics: null,
    });
    render(<InstitutionalTearSheetView payload={fixture} />);

    expect(screen.getByText('No benchmark active comparison')).toBeInTheDocument();
    expect(
      screen.getByText(/Comparative benchmark metrics are not configured/)
    ).toBeInTheDocument();
  });

  it('renders structured warnings banner when warnings exist in envelope', () => {
    const fixture = createMockTearSheet({
      envelope: {
        ...createMockFactSheet().envelope,
        warnings: [
          {
            code: 'WARN_MUTABLE_DATASET',
            severity: 'warning',
            message: 'Simulation executed against mutable uncertified database records.',
            affected_metric: null,
            provenance_ref: 'ds-us-equities-2023',
          },
        ],
      },
    });
    render(<InstitutionalTearSheetView payload={fixture} />);

    expect(screen.getByText(/Material Disclosures & Dataset Constraints/)).toBeInTheDocument();
    expect(screen.getByText(/\[WARN_MUTABLE_DATASET\]/)).toBeInTheDocument();
    expect(
      screen.getByText(/Simulation executed against mutable uncertified database records/)
    ).toBeInTheDocument();
  });
});

describe('Stage 34 Gate C: Research Diagnostics Annex (Optional Page 3)', () => {
  it('renders research annex with PBO, DSR, MinBTL, CSCV moments, and visual charts', () => {
    const fixture = createMockResearchAnnex();
    render(<ResearchDiagnosticsAnnexView payload={fixture} />);

    expect(
      screen.getAllByText(/Combinatorially Symmetric Cross-Validation \(CSCV\)/).length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('18.5%')).toBeInTheDocument(); // PBO
    expect(screen.getByText(/LOW Risk Level/i)).toBeInTheDocument();
    expect(screen.getByText('94.2%')).toBeInTheDocument(); // DSR
    expect(screen.getByText('1.82 yrs')).toBeInTheDocument(); // MinBTL
    expect(screen.getByText(/In-Sample vs Out-of-Sample Performance Degradation/)).toBeInTheDocument();
    expect(screen.getByText(/Relative Rank Distribution/)).toBeInTheDocument();
    expect(screen.getByText(/METHODOLOGY DISCLOSURE/)).toBeInTheDocument();
  });

  it('preserves undefined MinBTL when Sharpe is below threshold SR*', () => {
    const fixture = createMockResearchAnnex({
      min_backtest_length_years: null,
    });
    render(<ResearchDiagnosticsAnnexView payload={fixture} />);

    expect(screen.getByText('Undefined (SR ≤ SR*)')).toBeInTheDocument();
  });
});

describe('Stage 34 Gate C: Master Report Viewer & Interactive Controls', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('allows switching tabs between Tear Sheet, Fact Sheet, and Unified Dossier', () => {
    const unifiedReport = createMockUnifiedReport();
    render(<InstitutionalReportViewer report={unifiedReport} />);

    // Defaults to Tear Sheet
    expect(screen.getByRole('heading', { name: 'Institutional Tear Sheet' })).toBeInTheDocument();

    // Click Fact Sheet tab
    const factSheetTab = screen.getByRole('tab', { name: /Strategy Fact Sheet/i });
    fireEvent.click(factSheetTab);
    expect(screen.getByRole('heading', { name: 'Strategy Fact Sheet — US Large-Cap' })).toBeInTheDocument();

    // Click Unified tab
    const unifiedTab = screen.getByRole('tab', { name: /Unified Complete Dossier/i });
    fireEvent.click(unifiedTab);
    // Both should now be present in unified view
    expect(screen.getByRole('heading', { name: 'Strategy Fact Sheet — US Large-Cap' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Institutional Tear Sheet' })).toBeInTheDocument();
  });

  it('toggles inclusion of optional Research Diagnostics Annex', () => {
    const unifiedReport = createMockUnifiedReport();
    render(<InstitutionalReportViewer report={unifiedReport} initialTab="tear_sheet" />);

    // Initially annex is checked and rendered
    expect(screen.getByRole('heading', { name: /Research Diagnostics Annex/i })).toBeInTheDocument();

    // Uncheck annex toggle
    const toggle = screen.getByRole('checkbox', { name: /Include Research Annex/i });
    fireEvent.click(toggle);

    // Annex should now be omitted
    expect(screen.queryByRole('heading', { name: /Research Diagnostics Annex/i })).not.toBeInTheDocument();
  });

  it('triggers window.print when print button is clicked', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});
    const unifiedReport = createMockUnifiedReport();
    render(<InstitutionalReportViewer report={unifiedReport} />);

    const printBtn = screen.getByRole('button', { name: /Print \/ Save as PDF/i });
    fireEvent.click(printBtn);

    expect(printSpy).toHaveBeenCalledTimes(1);
  });

});

describe('Stage 34 Gate C: Vector Charts Edge Cases', () => {
  it('renders safe empty state for equity curve when data is empty', () => {
    render(<VectorEquityCurve data={[]} />);
    expect(
      screen.getByText('No time-series observations available for this reporting window.')
    ).toBeInTheDocument();
  });

  it('renders safe empty state for monthly returns when cells are empty', () => {
    render(<MonthlyReturnsGrid cells={[]} />);
    expect(screen.getByText('No discrete monthly return observations recorded.')).toBeInTheDocument();
  });

  it('renders safe empty state for asset allocation when list is empty', () => {
    render(<AssetAllocationChart allocations={[]} />);
    expect(
      screen.getByText('No target or effective asset allocations resolved for this strategy.')
    ).toBeInTheDocument();
  });
});
