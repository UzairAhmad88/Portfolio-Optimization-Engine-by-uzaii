/**
 * Stage 34 Deterministic Reporting Fixtures for Frontend Tests and Component Renders.
 * Directly mirrors backend reporting fixtures: Normal, Edge (Zero Vol/Undefined Calmar/Zero TE),
 * and Multi-Testing Research Diagnostics Annex.
 */

import type {
  CommonReportEnvelope,
  StrategyMandate,
  ExecutiveKPIs,
  BenchmarkRelativeMetrics,
  AssetAllocationItem,
  TimeSeriesPoint,
  MonthlyReturnCell,
  FrictionAndExecutionMetrics,
  StrategyFactSheetPayload,
  InstitutionalTearSheetPayload,
  ResearchDiagnosticsAnnexPayload,
  InstitutionalReportResponse,
} from '../types/reporting';

export function createMockEnvelope(overrides: Partial<CommonReportEnvelope> = {}): CommonReportEnvelope {
  return {
    contract_version: '1.0',
    report_type: 'tear_sheet',
    report_title: 'US Large-Cap Multi-Factor Strategy',
    generated_at: '2026-10-23T00:00:00Z',
    base_currency: 'USD',
    reporting_start_date: '2023-01-03',
    reporting_end_date: '2023-12-29',
    dataset_id: 'ds-us-equities-2023',
    dataset_filename: 'us_large_cap_prices.csv',
    snapshot_id: 'snap-audit-2023-certified',
    snapshot_manifest_digest: 'a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890',
    source_backtest_id: 'bt-sample-run-001',
    source_experiment_id: 'exp-sample-001',
    calculation_version: '1.0',
    warnings: [],
    is_hypothetical: true,
    regulatory_disclaimer:
      'Hypothetical backtested performance results have inherent limitations. Past performance does not guarantee future results.',
    ...overrides,
  };
}

export function createMockMandate(overrides: Partial<StrategyMandate> = {}): StrategyMandate {
  return {
    strategy_type: 'walk_forward_optimization',
    investment_universe: ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'NVDA'],
    rebalance_frequency: 'monthly',
    optimization_objective: 'max_sharpe',
    initial_capital: 100000.0,
    risk_free_rate: 0.02,
    constraints_summary: [
      'Long-only (0.0 <= w_i <= 0.30)',
      'Fully invested (sum(w_i) = 1.0)',
      'Maximum monthly turnover: 50%',
    ],
    ...overrides,
  };
}

export function createMockKPIs(overrides: Partial<ExecutiveKPIs> = {}): ExecutiveKPIs {
  return {
    cumulative_return_net: 0.245,
    cumulative_return_gross: 0.258,
    cagr_net: 0.245,
    cagr_gross: 0.258,
    annualized_return_net: 0.221,
    annualized_return_gross: 0.233,
    annualized_volatility_net: 0.142,
    annualized_volatility_gross: 0.1415,
    sharpe_ratio_net: 1.4155,
    sharpe_ratio_gross: 1.5053,
    sortino_ratio_net: 2.124,
    sortino_ratio_gross: 2.251,
    max_drawdown_net: 0.0845,
    max_drawdown_gross: 0.082,
    calmar_ratio_net: 2.8994,
    calmar_ratio_gross: 3.1463,
    drawdown_peak_date: '2023-07-18',
    drawdown_trough_date: '2023-08-25',
    drawdown_recovery_date: '2023-10-12',
    drawdown_duration_days: 38,
    positive_periods_count: 138,
    negative_periods_count: 112,
    win_rate: 0.552,
    profit_loss_ratio: 1.285,
    observation_count: 250,
    periods_per_year: 252,
    ...overrides,
  };
}

export function createMockBenchmarkMetrics(
  overrides: Partial<BenchmarkRelativeMetrics> = {}
): BenchmarkRelativeMetrics {
  return {
    benchmark_id: 'SPY:US',
    benchmark_name: 'S&P 500 ETF Trust',
    benchmark_cumulative_return: 0.182,
    benchmark_annualized_return: 0.175,
    benchmark_annualized_volatility: 0.131,
    benchmark_sharpe_ratio: 1.1832,
    benchmark_max_drawdown: 0.102,
    arithmetic_active_return: 0.063,
    geometric_excess_return: 0.0533,
    annualized_active_return: 0.046,
    tracking_error: 0.042,
    information_ratio: 1.0952,
    beta: 0.98,
    alpha_annualized: 0.0495,
    treynor_ratio: 0.2051,
    up_capture_ratio: 1.08,
    down_capture_ratio: 0.89,
    correlation: 0.92,
    ...overrides,
  };
}

export function createMockAllocations(): AssetAllocationItem[] {
  return [
    {
      asset_id: 'AAPL:US',
      ticker: 'AAPL',
      market: 'US',
      name: 'Apple Inc.',
      target_weight: 0.25,
      effective_weight: 0.265,
      asset_cumulative_return: 0.32,
      total_contribution: 0.0848,
      share_of_return: 0.346,
    },
    {
      asset_id: 'MSFT:US',
      ticker: 'MSFT',
      market: 'US',
      name: 'Microsoft Corp.',
      target_weight: 0.25,
      effective_weight: 0.248,
      asset_cumulative_return: 0.28,
      total_contribution: 0.0694,
      share_of_return: 0.283,
    },
    {
      asset_id: 'AMZN:US',
      ticker: 'AMZN',
      market: 'US',
      name: 'Amazon.com Inc.',
      target_weight: 0.2,
      effective_weight: 0.195,
      asset_cumulative_return: 0.22,
      total_contribution: 0.0429,
      share_of_return: 0.175,
    },
    {
      asset_id: 'GOOGL:US',
      ticker: 'GOOGL',
      market: 'US',
      name: 'Alphabet Inc.',
      target_weight: 0.15,
      effective_weight: 0.147,
      asset_cumulative_return: 0.19,
      total_contribution: 0.0279,
      share_of_return: 0.114,
    },
    {
      asset_id: 'NVDA:US',
      ticker: 'NVDA',
      market: 'US',
      name: 'NVIDIA Corp.',
      target_weight: 0.15,
      effective_weight: 0.145,
      asset_cumulative_return: 0.45,
      total_contribution: 0.0652,
      share_of_return: 0.266,
    },
  ];
}

export function createMockTimeSeries(): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  let navNet = 100000;
  let navGross = 100000;
  let navBm = 100000;
  let peakNet = 100000;
  let peakGross = 100000;
  let peakBm = 100000;

  for (let i = 1; i <= 30; i++) {
    const day = i < 10 ? `0${i}` : `${i}`;
    const rNet = (Math.sin(i * 0.5) * 0.01) + 0.001;
    const rGross = rNet + 0.0002;
    const rBm = (Math.cos(i * 0.4) * 0.008) + 0.0008;

    navNet *= (1 + rNet);
    navGross *= (1 + rGross);
    navBm *= (1 + rBm);

    if (navNet > peakNet) peakNet = navNet;
    if (navGross > peakGross) peakGross = navGross;
    if (navBm > peakBm) peakBm = navBm;

    const ddNet = (peakNet - navNet) / peakNet;
    const ddGross = (peakGross - navGross) / peakGross;
    const ddBm = (peakBm - navBm) / peakBm;

    points.push({
      date: `2023-01-${day}`,
      portfolio_value_net: Math.round(navNet * 100) / 100,
      portfolio_value_gross: Math.round(navGross * 100) / 100,
      return_net: rNet,
      return_gross: rGross,
      drawdown_net: ddNet,
      drawdown_gross: ddGross,
      benchmark_value: Math.round(navBm * 100) / 100,
      benchmark_return: rBm,
      benchmark_drawdown: ddBm,
    });
  }
  return points;
}

export function createMockMonthlyReturns(): MonthlyReturnCell[] {
  return [
    { year: 2023, month: 1, return_net: 0.042, return_gross: 0.044, benchmark_return: 0.038 },
    { year: 2023, month: 2, return_net: -0.015, return_gross: -0.013, benchmark_return: -0.022 },
    { year: 2023, month: 3, return_net: 0.031, return_gross: 0.033, benchmark_return: 0.025 },
    { year: 2023, month: 4, return_net: 0.018, return_gross: 0.02, benchmark_return: 0.012 },
    { year: 2023, month: 5, return_net: 0.024, return_gross: 0.026, benchmark_return: 0.019 },
    { year: 2023, month: 6, return_net: 0.051, return_gross: 0.053, benchmark_return: 0.042 },
    { year: 2023, month: 7, return_net: 0.028, return_gross: 0.03, benchmark_return: 0.031 },
    { year: 2023, month: 8, return_net: -0.032, return_gross: -0.03, benchmark_return: -0.039 },
    { year: 2023, month: 9, return_net: -0.021, return_gross: -0.019, benchmark_return: -0.028 },
    { year: 2023, month: 10, return_net: 0.015, return_gross: 0.017, benchmark_return: -0.011 },
    { year: 2023, month: 11, return_net: 0.062, return_gross: 0.064, benchmark_return: 0.058 },
    { year: 2023, month: 12, return_net: 0.038, return_gross: 0.04, benchmark_return: 0.032 },
  ];
}

export function createMockFrictionMetrics(): FrictionAndExecutionMetrics {
  return {
    total_turnover: 3.45,
    annualized_turnover: 3.4776,
    transaction_cost_bps: 10.0,
    slippage_bps: 5.0,
    total_transaction_costs: 517.5,
    total_slippage_costs: 258.75,
    total_friction_costs: 776.25,
    friction_drag_bps: 77.625,
    number_of_rebalances: 12,
  };
}

export function createMockFactSheet(overrides: Partial<StrategyFactSheetPayload> = {}): StrategyFactSheetPayload {
  return {
    envelope: createMockEnvelope({ report_type: 'fact_sheet', report_title: 'Strategy Fact Sheet — US Large-Cap' }),
    mandate: createMockMandate(),
    kpis: createMockKPIs(),
    benchmark_metrics: createMockBenchmarkMetrics(),
    top_holdings: createMockAllocations(),
    compact_wealth_curve: createMockTimeSeries(),
    monthly_returns: createMockMonthlyReturns(),
    ...overrides,
  };
}

export function createMockTearSheet(
  overrides: Partial<InstitutionalTearSheetPayload> = {}
): InstitutionalTearSheetPayload {
  return {
    envelope: createMockEnvelope({ report_type: 'tear_sheet', report_title: 'Institutional Tear Sheet' }),
    mandate: createMockMandate(),
    kpis: createMockKPIs(),
    benchmark_metrics: createMockBenchmarkMetrics(),
    asset_allocation: createMockAllocations(),
    friction_and_execution: createMockFrictionMetrics(),
    equity_curve: createMockTimeSeries(),
    monthly_returns_table: createMockMonthlyReturns(),
    ...overrides,
  };
}

export function createMockResearchAnnex(
  overrides: Partial<ResearchDiagnosticsAnnexPayload> = {}
): ResearchDiagnosticsAnnexPayload {
  return {
    envelope: createMockEnvelope({
      report_type: 'research_diagnostics',
      report_title: 'Research Diagnostics Annex — Overfitting Analysis',
    }),
    evaluated_runs_count: 20,
    aligned_observations_count: 250,
    n_slices: 16,
    total_combinations_count: 12870,
    pbo: 0.185,
    pbo_risk_level: 'low',
    best_run_id: 'run-opt-014',
    best_run_number: 14,
    best_nominal_sharpe: 1.85,
    expected_max_sharpe: 1.42,
    deflated_sharpe_ratio: 0.942,
    is_statistically_significant: true,
    min_backtest_length_years: 1.82,
    actual_backtest_length_years: 1.0,
    skewness: -0.15,
    kurtosis: 3.25,
    degradation_regression: {
      slope: 0.65,
      intercept: 0.12,
      r_squared: 0.48,
      p_value: 0.001,
      std_err: 0.08,
    },
    combinations_sample: [
      {
        combination_id: 1,
        selected_run_id: 'run-opt-014',
        is_sharpe: 1.82,
        oos_sharpe: 1.45,
        oos_rank: 2,
        relative_rank: 0.1,
        is_overfitted: false,
      },
      {
        combination_id: 2,
        selected_run_id: 'run-opt-014',
        is_sharpe: 1.88,
        oos_sharpe: 1.15,
        oos_rank: 5,
        relative_rank: 0.25,
        is_overfitted: false,
      },
      {
        combination_id: 3,
        selected_run_id: 'run-opt-014',
        is_sharpe: 1.95,
        oos_sharpe: 0.42,
        oos_rank: 12,
        relative_rank: 0.6,
        is_overfitted: true,
      },
    ],
    rank_distribution: [
      { bin_start: 0.0, bin_end: 0.1, count: 240, relative_frequency: 0.24 },
      { bin_start: 0.1, bin_end: 0.2, count: 310, relative_frequency: 0.31 },
      { bin_start: 0.2, bin_end: 0.3, count: 210, relative_frequency: 0.21 },
      { bin_start: 0.3, bin_end: 0.4, count: 120, relative_frequency: 0.12 },
      { bin_start: 0.4, bin_end: 0.5, count: 60, relative_frequency: 0.06 },
      { bin_start: 0.5, bin_end: 0.6, count: 30, relative_frequency: 0.03 },
      { bin_start: 0.6, bin_end: 0.7, count: 15, relative_frequency: 0.015 },
      { bin_start: 0.7, bin_end: 0.8, count: 10, relative_frequency: 0.01 },
      { bin_start: 0.8, bin_end: 0.9, count: 3, relative_frequency: 0.003 },
      { bin_start: 0.9, bin_end: 1.0, count: 2, relative_frequency: 0.002 },
    ],
    runs_summary: [
      {
        run_id: 'run-opt-014',
        run_number: 14,
        nominal_sharpe: 1.85,
        selection_frequency_is: 0.45,
        mean_oos_rank_when_selected: 2.4,
        mean_oos_sharpe_when_selected: 1.35,
      },
    ],
    ...overrides,
  };
}


export function createMockUnifiedReport(): InstitutionalReportResponse {
  return {
    envelope: createMockEnvelope({
      report_type: 'unified_tear_sheet',
      report_title: 'Unified Institutional Portfolio Report',
    }),
    fact_sheet: createMockFactSheet(),
    tear_sheet: createMockTearSheet(),
    research_annex: createMockResearchAnnex(),
  };
}
