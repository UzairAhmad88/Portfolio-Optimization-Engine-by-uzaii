import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  OverfittingDiagnosticsStudio,
  formatCscvSamplingDisclosure,
  escapeCsvField,
  toCsvRow,
  formatHistogramBinRange,
  generateDiagnosticsCsv,
} from '../components/research/OverfittingDiagnosticsStudio';
import { apiClient } from '../api/client';
import type {
  ExperimentListItem,
  ExperimentRunListItem,
  OverfittingDiagnosticsResponse,
} from '../types/api';

describe('OverfittingDiagnosticsStudio & Overfitting API', () => {
  const mockExperiments: ExperimentListItem[] = [
    {
      id: 'exp-momentum-alpha',
      name: 'Cross-Sectional Momentum Alpha',
      description: 'Hypothesis testing multi-lookback momentum alpha',
      strategy_type: 'target_weights',
      dataset_id: 'ds-us-equities',
      version: 1,
      config_fingerprint: 'fp-1234567890',
      total_runs_count: 4,
      latest_run_number: 4,
      latest_run_status: 'succeeded',
      created_at: '2026-03-01T00:00:00Z',
      updated_at: '2026-03-01T00:00:00Z',
    },
    {
      id: 'exp-empty-runs',
      name: 'Empty Hypothesis',
      description: 'Experiment without runs',
      strategy_type: 'equal_weight',
      dataset_id: 'ds-us-equities',
      version: 1,
      config_fingerprint: 'fp-empty',
      total_runs_count: 0,
      latest_run_number: null,
      latest_run_status: null,
      created_at: '2026-03-02T00:00:00Z',
      updated_at: '2026-03-02T00:00:00Z',
    },
  ];

  const mockRuns: ExperimentRunListItem[] = [
    {
      id: 'run-1-mom-10d',
      experiment_id: 'exp-momentum-alpha',
      run_number: 1,
      status: 'succeeded',
      config_fingerprint: 'fp-run-1',
      is_reproducible: true,
      created_at: '2026-03-01T01:00:00Z',
      summary_kpis: { sharpe_ratio: 1.45 },
    },
    {
      id: 'run-2-mom-20d',
      experiment_id: 'exp-momentum-alpha',
      run_number: 2,
      status: 'succeeded',
      config_fingerprint: 'fp-run-2',
      is_reproducible: true,
      created_at: '2026-03-01T02:00:00Z',
      summary_kpis: { sharpe_ratio: 1.82 },
    },
    {
      id: 'run-3-mom-60d',
      experiment_id: 'exp-momentum-alpha',
      run_number: 3,
      status: 'succeeded',
      config_fingerprint: 'fp-run-3',
      is_reproducible: true,
      created_at: '2026-03-01T03:00:00Z',
      summary_kpis: { sharpe_ratio: 0.95 },
    },
    {
      id: 'run-4-failed',
      experiment_id: 'exp-momentum-alpha',
      run_number: 4,
      status: 'failed',
      config_fingerprint: 'fp-run-4',
      is_reproducible: false,
      created_at: '2026-03-01T04:00:00Z',
    },
  ];

  const mockDiagnosticsResponse: OverfittingDiagnosticsResponse = {
    experiment_id: 'exp-momentum-alpha',
    experiment_name: 'Cross-Sectional Momentum Alpha',
    strategy_type: 'target_weights',
    dataset_id: 'ds-us-equities',
    snapshot_id: 'snap-pit-certified-2026',
    evaluated_runs_count: 3,
    aligned_observations_count: 756,
    n_slices: 16,
    total_combinations_count: 12870,
    pbo: 0.185,
    pbo_risk_level: 'moderate',
    best_run_id: 'run-2-mom-20d',
    best_run_number: 2,
    best_nominal_sharpe: 1.82,
    expected_max_sharpe: 1.25,
    deflated_sharpe_ratio: 0.968,
    is_statistically_significant: true,
    min_backtest_length_years: 1.74,
    actual_backtest_length_years: 3.0,
    skewness: -0.42,
    kurtosis: 4.15,
    degradation_regression: {
      slope: 0.58,
      intercept: 0.15,
      r_squared: 0.44,
      p_value: 0.001,
      std_err: 0.05,
    },
    combinations_sample: [
      {
        combination_id: 0,
        selected_run_id: 'run-2-mom-20d',
        is_sharpe: 2.1,
        oos_sharpe: 1.45,
        oos_rank: 3,
        relative_rank: 0.75,
        is_overfitted: false,
      },
      {
        combination_id: 1,
        selected_run_id: 'run-1-mom-10d',
        is_sharpe: 1.95,
        oos_sharpe: 0.4,
        oos_rank: 1,
        relative_rank: 0.25,
        is_overfitted: true,
      },
    ],
    rank_distribution: [
      { bin_start: 0.0, bin_end: 0.1, count: 500, relative_frequency: 0.0388 },
      { bin_start: 0.1, bin_end: 0.2, count: 880, relative_frequency: 0.0684 },
      { bin_start: 0.2, bin_end: 0.3, count: 1000, relative_frequency: 0.0777 },
      { bin_start: 0.3, bin_end: 0.4, count: 0, relative_frequency: 0.0 },
      { bin_start: 0.4, bin_end: 0.5, count: 0, relative_frequency: 0.0 },
      { bin_start: 0.5, bin_end: 0.6, count: 2000, relative_frequency: 0.1554 },
      { bin_start: 0.6, bin_end: 0.7, count: 2500, relative_frequency: 0.1943 },
      { bin_start: 0.7, bin_end: 0.8, count: 2990, relative_frequency: 0.2323 },
      { bin_start: 0.8, bin_end: 0.9, count: 1500, relative_frequency: 0.1166 },
      { bin_start: 0.9, bin_end: 1.0, count: 1500, relative_frequency: 0.1166 },
    ],
    runs_summary: [
      {
        run_id: 'run-1-mom-10d',
        run_number: 1,
        nominal_sharpe: 1.45,
        selection_frequency_is: 0.32,
        mean_oos_sharpe_when_selected: 0.88,
        mean_oos_rank_when_selected: 1.95,
      },
      {
        run_id: 'run-2-mom-20d',
        run_number: 2,
        nominal_sharpe: 1.82,
        selection_frequency_is: 0.68,
        mean_oos_sharpe_when_selected: 1.42,
        mean_oos_rank_when_selected: 2.74,
      },
      {
        run_id: 'run-3-mom-60d',
        run_number: 3,
        nominal_sharpe: 0.95,
        selection_frequency_is: 0.0,
        mean_oos_sharpe_when_selected: null,
        mean_oos_rank_when_selected: null,
      },
    ],
    warnings: ['Daily return series was trimmed by 5 days for temporal alignment across runs.'],
    generated_at: '2026-03-01T12:00:00Z',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('correctly dispatches computeOverfittingDiagnostics via apiClient', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockDiagnosticsResponse,
    } as any);

    const result = await apiClient.computeOverfittingDiagnostics('exp-momentum-alpha', {
      experiment_id: 'exp-momentum-alpha',
      n_slices: 16,
      significance_level: 0.05,
      annualization_factor: 252,
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain('/api/v1/research/experiments/exp-momentum-alpha/overfitting-diagnostics');
    expect(options?.method).toBe('POST');
    const parsedBody = JSON.parse(options?.body as string);
    expect(parsedBody.n_slices).toBe(16);
    expect(parsedBody.significance_level).toBe(0.05);
    expect(result.pbo).toBe(0.185);
    expect(result.deflated_sharpe_ratio).toBe(0.968);
  });

  it('renders experiment selection and candidate strategy runs list', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValueOnce(mockRuns);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    // Header & subtitle
    expect(screen.getByText(/Institutional Overfitting Diagnostics & Deflated Sharpe Engine/i)).toBeInTheDocument();

    // Succeeded runs are displayed, failed run is filtered from eligible multi-selection
    await waitFor(() => {
      expect(screen.getByText(/Candidate Strategy Runs \(3 of 3 selected\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Run #1/i)).toBeInTheDocument();
      expect(screen.getByText(/Run #2/i)).toBeInTheDocument();
      expect(screen.getByText(/Run #3/i)).toBeInTheDocument();
      expect(screen.queryByText(/Run #4/i)).not.toBeInTheDocument();
    });

    // CSCV Slices preview
    expect(screen.getByText(/12,870 IS\/OOS partitions/i)).toBeInTheDocument();
  });

  it('enforces validation requiring at least 2 candidate strategy runs', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValueOnce(mockRuns);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Candidate Strategy Runs/i)).toBeInTheDocument();
    });

    // Click "Clear" button to deselect all runs
    const clearButton = screen.getByText('Clear');
    fireEvent.click(clearButton);

    expect(screen.getByText(/Please select at least 2 runs \(currently selected: 0\)/i)).toBeInTheDocument();
    const computeButton = screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i });
    expect(computeButton).toBeDisabled();

    // Select 1 run
    const run1Checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(run1Checkbox);

    expect(screen.getByText(/Please select at least 2 runs \(currently selected: 1\)/i)).toBeInTheDocument();
    expect(computeButton).toBeDisabled();

    // Select 2nd run -> ready to run
    const run2Checkbox = screen.getAllByRole('checkbox')[1];
    fireEvent.click(run2Checkbox);

    expect(computeButton).toBeEnabled();
  });

  it('displays empty state when an experiment has fewer than 2 completed runs', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValueOnce([]);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-empty-runs"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/No completed simulation runs found for this experiment/i)).toBeInTheDocument();
    });

    const computeButton = screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i });
    expect(computeButton).toBeDisabled();
  });

  it('computes diagnostics, renders KPI cards, PBO risk tier, and DSR significance', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    const computeButton = screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i });
    fireEvent.click(computeButton);

    // Awaits calculation results
    await waitFor(() => {
      // PBO card
      expect(screen.getByText('18.5%')).toBeInTheDocument();
      expect(screen.getByText(/Moderate Overfitting Risk \(18.5%\)/i)).toBeInTheDocument();

      // DSR card
      expect(screen.getByText('96.8%')).toBeInTheDocument();
      expect(screen.getByText(/Significant \(p < 0.05\)/i)).toBeInTheDocument();

      // MinBTL card
      expect(screen.getByText('1.74 Years')).toBeInTheDocument();
      expect(screen.getByText(/Track record length exceeds statistical discovery threshold/i)).toBeInTheDocument();

      // Degradation slope beta
      expect(screen.getByText('0.58')).toBeInTheDocument();
      expect(screen.getByText(/Moderate to strong persistence between IS and OOS/i)).toBeInTheDocument();
    });

    // Advisory warning rendered
    expect(
      screen.getByText(/Daily return series was trimmed by 5 days for temporal alignment across runs/i)
    ).toBeInTheDocument();

    // Provenance badge rendered
    expect(screen.getByText(/Dataset Provenance/i)).toBeInTheDocument();
  });

  it('handles undefined MinBTL gracefully without NaN or Infinity', async () => {
    const responseWithNullMinBTL: OverfittingDiagnosticsResponse = {
      ...mockDiagnosticsResponse,
      min_backtest_length_years: null,
      actual_backtest_length_years: 1.5,
    };

    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(responseWithNullMinBTL);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText('Undefined')).toBeInTheDocument();
      expect(screen.getByText(/Undefined under current statistical assumptions/i)).toBeInTheDocument();
    });
  });

  it('renders interactive SVG scatter plot and supports accessible tabular toggle', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText(/In-Sample vs Out-of-Sample Sharpe Degradation/i)).toBeInTheDocument();
    });

    // Toggle tabular view for screen readers & non-visual accessibility
    const dataTableButton = screen.getAllByRole('button', { name: /Show Data Table/i })[0];
    fireEvent.click(dataTableButton);

    expect(screen.getByText('Split #')).toBeInTheDocument();
    expect(screen.getByText('IS Sharpe')).toBeInTheDocument();
    expect(screen.getByText('OOS Sharpe')).toBeInTheDocument();
    expect(screen.getByText('Rel Rank')).toBeInTheDocument();

    // Toggle back to chart
    const showChartButton = screen.getByRole('button', { name: /Show Chart/i });
    fireEvent.click(showChartButton);
    expect(screen.getByText(/In-Sample vs Out-of-Sample Sharpe Degradation/i)).toBeInTheDocument();
  });

  it('renders relative-rank histogram with PBO cutoff threshold', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText(/Out-of-Sample Relative-Rank Distribution/i)).toBeInTheDocument();
      expect(screen.getByText(/PBO Cutoff/i)).toBeInTheDocument();
    });
  });

  it('renders per-run summary table with highest nominal Sharpe distinction and missing-value handling', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText(/Candidate Strategy Trials Performance/i)).toBeInTheDocument();
      expect(screen.getByText('Highest Nominal SR')).toBeInTheDocument();
      // Run 3 has null for mean OOS Sharpe because it was never selected In-Sample
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('marks results as stale when user modifies inputs after calculation', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText('18.5%')).toBeInTheDocument();
    });

    // User modifies parameter: unchecks run 3
    const run3Checkbox = screen.getAllByRole('checkbox')[2];
    fireEvent.click(run3Checkbox);

    // Stale banner appears
    expect(screen.getByText(/Inputs modified since last execution. Results below reflect prior calculation/i)).toBeInTheDocument();
  });

  it('handles backend API error (e.g. 422 unprocessable entity) gracefully without fabricating fake results', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockRejectedValueOnce(
      new Error('Return matrices could not be synchronized: insufficient overlapping observations.')
    );

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByText(/Diagnostic Calculation Failed/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Return matrices could not be synchronized: insufficient overlapping observations/i)
      ).toBeInTheDocument();
      // Never renders synthetic results
      expect(screen.queryByText('18.5%')).not.toBeInTheDocument();
    });
  });

  it('supports export actions (CSV, JSON, Markdown tear sheet copy)', async () => {
    vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
    vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    render(
      <OverfittingDiagnosticsStudio
        experiments={mockExperiments}
        initialExperimentId="exp-momentum-alpha"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Copy Tear Sheet/i })).toBeInTheDocument();
    });

    const copyButton = screen.getByRole('button', { name: /Copy Tear Sheet/i });
    fireEvent.click(copyButton);

    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    expect((navigator.clipboard.writeText as any).mock.calls[0][0]).toContain('### Institutional Research Tear Sheet');
  });

  /* ========================================================================= */
  /* DEF-E-01 Regression Tests: Histogram Boundaries & PBO Consistency         */
  /* ========================================================================= */
  describe('DEF-E-01: PBO Histogram Boundary Interval Notation', () => {
    it('formats bin ranges with mathematically consistent interval boundaries', () => {
      // Bins < 0.5: left-closed, right-open [start, end)
      expect(formatHistogramBinRange({ bin_start: 0.0, bin_end: 0.1, count: 10, relative_frequency: 0.1 })).toBe('[0.00, 0.10)');
      expect(formatHistogramBinRange({ bin_start: 0.1, bin_end: 0.2, count: 5, relative_frequency: 0.05 })).toBe('[0.10, 0.20)');
      expect(formatHistogramBinRange({ bin_start: 0.3, bin_end: 0.4, count: 8, relative_frequency: 0.08 })).toBe('[0.30, 0.40)');

      // Median boundary bin (bin ending at 0.5): closed on both sides [0.40, 0.50]
      expect(formatHistogramBinRange({ bin_start: 0.4, bin_end: 0.5, count: 12, relative_frequency: 0.12 })).toBe('[0.40, 0.50]');

      // Bins > 0.5 (persistent region): left-open, right-closed (start, end]
      expect(formatHistogramBinRange({ bin_start: 0.5, bin_end: 0.6, count: 15, relative_frequency: 0.15 })).toBe('(0.50, 0.60]');
      expect(formatHistogramBinRange({ bin_start: 0.6, bin_end: 0.7, count: 20, relative_frequency: 0.20 })).toBe('(0.60, 0.70]');
      expect(formatHistogramBinRange({ bin_start: 0.9, bin_end: 1.0, count: 25, relative_frequency: 0.25 })).toBe('(0.90, 1.00]');
    });

    it('renders accurate boundary interval notation in the accessible data table', async () => {
      vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
      vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

      render(
        <OverfittingDiagnosticsStudio
          experiments={mockExperiments}
          initialExperimentId="exp-momentum-alpha"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
      });

      fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

      await waitFor(() => {
        expect(screen.getByText(/Out-of-Sample Relative-Rank Distribution/i)).toBeInTheDocument();
      });

      // Switch to histogram data table
      const dataTableButtons = screen.getAllByRole('button', { name: /Show Data Table/i });
      fireEvent.click(dataTableButtons[1]); // second one is for histogram

      expect(screen.getByText('[0.00, 0.10)')).toBeInTheDocument();
      expect(screen.getByText('[0.40, 0.50]')).toBeInTheDocument();
      expect(screen.getByText('(0.50, 0.60]')).toBeInTheDocument();
      expect(screen.getByText('(0.90, 1.00]')).toBeInTheDocument();
    });
  });

  /* ========================================================================= */
  /* DEF-E-02 Regression Tests: CSCV Subsampling Disclosure                    */
  /* ========================================================================= */
  describe('DEF-E-02: CSCV Scatter Subsampling Disclosure', () => {
    it('accurately distinguishes sampled points from total combinations count', () => {
      // Subsampled case
      expect(formatCscvSamplingDisclosure(500, 12870)).toBe('500 sampled points of 12,870 total CSCV combinations');

      // Complete partition case (no subsampling)
      expect(formatCscvSamplingDisclosure(70, 70)).toBe('70 total CSCV combinations (complete partition)');

      // Missing or undefined total count metadata
      expect(formatCscvSamplingDisclosure(500, null)).toBe('500 CSCV combinations');
      expect(formatCscvSamplingDisclosure(500, undefined)).toBe('500 CSCV combinations');
    });

    it('displays sampled-vs-total disclosure in the scatter plot header', async () => {
      vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
      vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

      render(
        <OverfittingDiagnosticsStudio
          experiments={mockExperiments}
          initialExperimentId="exp-momentum-alpha"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
      });

      fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

      await waitFor(() => {
        // mockDiagnosticsResponse has 2 sample points and total_combinations_count: 12870
        expect(screen.getByText(/2 sampled points of 12,870 total CSCV combinations/i)).toBeInTheDocument();
      });
    });
  });

  /* ========================================================================= */
  /* DEF-E-03 Regression Tests: RFC 4180 CSV Escaping & Warning Preservation    */
  /* ========================================================================= */
  describe('DEF-E-03: CSV Escaping & Advisory Warnings Preservation', () => {
    it('escapes fields containing commas, double quotes, and newlines correctly', () => {
      expect(escapeCsvField('StandardName')).toBe('StandardName');
      expect(escapeCsvField(123.45)).toBe('123.45');
      expect(escapeCsvField(null)).toBe('');
      expect(escapeCsvField(undefined)).toBe('');

      // Comma escaping
      expect(escapeCsvField('Alpha, Beta & Gamma')).toBe('"Alpha, Beta & Gamma"');

      // Embedded double quotes (RFC 4180: double each quote)
      expect(escapeCsvField('Strategy "Beta" 2.0')).toBe('"Strategy ""Beta"" 2.0"');

      // Newlines
      expect(escapeCsvField('Line 1\nLine 2')).toBe('"Line 1\nLine 2"');
      expect(escapeCsvField('Line 1\r\nLine 2')).toBe('"Line 1\r\nLine 2"');
    });

    it('formats a CSV row with proper escaping across mixed field types', () => {
      const row = toCsvRow(['Exp1', 'Momentum, Value', 1.82, 'Notes with "quotes"']);
      expect(row).toBe('Exp1,"Momentum, Value",1.82,"Notes with ""quotes"""');
    });

    it('generates self-contained CSV preserving metadata, provenance, and warnings', () => {
      const diagnosticsWithEscapes: OverfittingDiagnosticsResponse = {
        ...mockDiagnosticsResponse,
        experiment_name: 'Alpha, Trend & Momentum "Core"',
        min_backtest_length_years: null,
        warnings: [
          'First warning: data trimmed by 5 days.',
          'Second warning with "quoted detail", comma included.',
        ],
      };

      const csv = generateDiagnosticsCsv(diagnosticsWithEscapes);

      // Verify header and experiment name escaping
      expect(csv).toContain('Experiment Name,"Alpha, Trend & Momentum ""Core"""');

      // Verify null MinBTL is preserved as 'Undefined', not coerced to zero
      expect(csv).toContain('MinBTL (Years),Undefined');

      // Verify advisory warnings section
      expect(csv).toContain('--- ADVISORY WARNINGS ---');
      expect(csv).toContain('Warning Index,Warning Message');
      expect(csv).toContain('1,First warning: data trimmed by 5 days.');
      expect(csv).toContain('2,"Second warning with ""quoted detail"", comma included."');

      // Verify run-level summary table is preserved
      expect(csv).toContain('--- RUN-LEVEL SUMMARY TABLE ---');
      expect(csv).toContain('Run Number,Run ID,Nominal Sharpe,IS Selection Frequency,Mean OOS Sharpe,Mean OOS Relative Rank');

      // Verify CSCV combinations sample is preserved
      expect(csv).toContain('--- CSCV COMBINATIONS SAMPLE ---');
    });

    it('handles diagnostics without warnings cleanly in CSV export', () => {
      const diagnosticsWithoutWarnings: OverfittingDiagnosticsResponse = {
        ...mockDiagnosticsResponse,
        warnings: [],
      };

      const csv = generateDiagnosticsCsv(diagnosticsWithoutWarnings);
      expect(csv).toContain('--- ADVISORY WARNINGS ---');
      expect(csv).toContain('Status,No advisory warnings detected.');
    });
  });

  /* ========================================================================= */
  /* DEF-E-04 Regression Tests: SVG Plot Area Clipping                         */
  /* ========================================================================= */
  describe('DEF-E-04: SVG Scatter Plot Area Clipping', () => {
    it('renders a scoped clipPath element and wraps plotted elements in a clipped group', async () => {
      vi.spyOn(apiClient, 'listExperimentRuns').mockResolvedValue(mockRuns);
      vi.spyOn(apiClient, 'computeOverfittingDiagnostics').mockResolvedValueOnce(mockDiagnosticsResponse);

      const { container } = render(
        <OverfittingDiagnosticsStudio
          experiments={mockExperiments}
          initialExperimentId="exp-momentum-alpha"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i })).toBeEnabled();
      });

      fireEvent.click(screen.getByRole('button', { name: /Compute Overfitting Diagnostics/i }));

      await waitFor(() => {
        expect(screen.getByText(/In-Sample vs Out-of-Sample Sharpe Degradation/i)).toBeInTheDocument();
      });

      // Find Scatter SVG element in container
      const svg = container.querySelector('svg[data-testid="cscv-scatter-chart"]');
      expect(svg).toBeInTheDocument();

      // Check for <clipPath> with a valid ID
      const clipPath = svg?.querySelector('clipPath, clippath');
      expect(clipPath).toBeInTheDocument();
      const clipId = clipPath?.getAttribute('id');
      expect(clipId).toBeTruthy();

      // Check that a group uses this clipPath
      const clippedGroup = svg?.querySelector(`g[clip-path="url(#${clipId})"], g[clipPath="url(#${clipId})"]`);
      expect(clippedGroup).toBeInTheDocument();

      // Ensure points and lines are inside the clipped group
      const circles = clippedGroup?.querySelectorAll('circle');
      expect(circles && circles.length).toBeGreaterThan(0);

      // Ensure axis labels are OUTSIDE the clipped group
      const texts = svg?.querySelectorAll('text');
      const axisText = Array.from(texts || []).find((t) => t.textContent?.includes('In-Sample Sharpe Ratio'));
      expect(axisText).toBeInTheDocument();
      expect(clippedGroup?.contains(axisText!)).toBe(false);
    });
  });
});

