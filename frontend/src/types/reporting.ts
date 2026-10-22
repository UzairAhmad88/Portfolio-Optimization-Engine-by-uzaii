/**
 * Institutional Reporting Domain Contracts matching backend Pydantic models (Stage 34).
 * Covers Strategy Fact Sheets (1-Page), Institutional Tear Sheets (2-Page),
 * and Research Diagnostics Annexes (3rd-Page).
 */

import type {
  PBORiskLevel,
  DegradationRegression,
  CSCVCombinationsPoint,
  CSCVHistogramBin,
  RunOverfittingSummary,
} from './api';

export type ReportType = 'fact_sheet' | 'tear_sheet' | 'research_diagnostics' | 'unified_tear_sheet';
export type WarningSeverity = 'info' | 'warning' | 'critical';
export type MetricAvailabilityStatus = 'available' | 'unavailable' | 'undefined' | 'invalid' | 'not_applicable';

export interface ReportWarning {
  code: string;
  severity: WarningSeverity;
  message: string;
  affected_metric?: string | null;
  provenance_ref?: string | null;
}

export interface CommonReportEnvelope {
  contract_version: string;
  report_type: ReportType;
  report_title: string;
  generated_at: string;
  base_currency: string;
  reporting_start_date: string;
  reporting_end_date: string;
  
  // Provenance and lineage
  dataset_id: string;
  dataset_filename?: string | null;
  snapshot_id?: string | null;
  snapshot_manifest_digest?: string | null;
  source_backtest_id?: string | null;
  source_experiment_id?: string | null;
  source_run_id?: string | null;
  calculation_version: string;
  
  warnings: ReportWarning[];
  is_hypothetical: boolean;
  regulatory_disclaimer: string;
}

export interface ExecutiveKPIs {
  // Standalone Net Performance (after costs)
  cumulative_return_net: number;
  cumulative_return_gross?: number | null;
  cagr_net: number;
  cagr_gross?: number | null;
  annualized_return_net: number;
  annualized_return_gross?: number | null;
  annualized_volatility_net: number;
  annualized_volatility_gross?: number | null;
  sharpe_ratio_net?: number | null;
  sharpe_ratio_gross?: number | null;
  sortino_ratio_net?: number | null;
  sortino_ratio_gross?: number | null;
  max_drawdown_net: number;
  max_drawdown_gross?: number | null;
  calmar_ratio_net?: number | null;
  calmar_ratio_gross?: number | null;
  
  // Peak / Trough dates
  drawdown_peak_date?: string | null;
  drawdown_trough_date?: string | null;
  drawdown_recovery_date?: string | null;
  drawdown_duration_days?: number | null;
  
  // Trading period counts
  positive_periods_count?: number | null;
  negative_periods_count?: number | null;
  win_rate?: number | null;
  profit_loss_ratio?: number | null;
  
  observation_count: number;
  periods_per_year: number;
}

export interface BenchmarkRelativeMetrics {
  benchmark_id: string;
  benchmark_name: string;
  benchmark_cumulative_return: number;
  benchmark_annualized_return: number;
  benchmark_annualized_volatility: number;
  benchmark_sharpe_ratio?: number | null;
  benchmark_max_drawdown: number;
  
  // Relative / Active Metrics
  arithmetic_active_return: number;
  geometric_excess_return: number;
  annualized_active_return: number;
  tracking_error: number;
  information_ratio?: number | null;
  beta?: number | null;
  alpha_annualized?: number | null;
  treynor_ratio?: number | null;
  up_capture_ratio?: number | null;
  down_capture_ratio?: number | null;
  correlation?: number | null;
}

export interface AssetAllocationItem {
  asset_id: string;
  ticker: string;
  market: string;
  name?: string | null;
  target_weight: number;
  effective_weight: number;
  asset_cumulative_return?: number | null;
  total_contribution?: number | null;
  share_of_return?: number | null;
}

export interface TimeSeriesPoint {
  date: string;
  portfolio_value_net: number;
  portfolio_value_gross?: number | null;
  return_net: number;
  return_gross?: number | null;
  drawdown_net: number;
  drawdown_gross?: number | null;
  benchmark_value?: number | null;
  benchmark_return?: number | null;
  benchmark_drawdown?: number | null;
}

export interface MonthlyReturnCell {
  year: number;
  month: number;
  return_net: number;
  return_gross?: number | null;
  benchmark_return?: number | null;
}

export interface FrictionAndExecutionMetrics {
  total_turnover: number;
  annualized_turnover?: number | null;
  transaction_cost_bps: number;
  slippage_bps: number;
  total_transaction_costs: number;
  total_slippage_costs: number;
  total_friction_costs: number;
  friction_drag_bps: number;
  number_of_rebalances: number;
}

export interface StrategyMandate {
  strategy_type: string;
  investment_universe: string[];
  rebalance_frequency: string;
  optimization_objective?: string | null;
  initial_capital: number;
  risk_free_rate: number;
  constraints_summary: string[];
}

export interface StrategyFactSheetPayload {
  envelope: CommonReportEnvelope;
  mandate: StrategyMandate;
  kpis: ExecutiveKPIs;
  benchmark_metrics?: BenchmarkRelativeMetrics | null;
  top_holdings: AssetAllocationItem[];
  compact_wealth_curve: TimeSeriesPoint[];
  monthly_returns: MonthlyReturnCell[];
}

export interface InstitutionalTearSheetPayload {
  envelope: CommonReportEnvelope;
  mandate: StrategyMandate;
  kpis: ExecutiveKPIs;
  benchmark_metrics?: BenchmarkRelativeMetrics | null;
  asset_allocation: AssetAllocationItem[];
  friction_and_execution?: FrictionAndExecutionMetrics | null;
  equity_curve: TimeSeriesPoint[];
  monthly_returns_table: MonthlyReturnCell[];
}

export interface ResearchDiagnosticsAnnexPayload {
  envelope: CommonReportEnvelope;
  evaluated_runs_count: number;
  aligned_observations_count: number;
  n_slices: number;
  total_combinations_count: number;
  
  // Overfitting metrics
  pbo: number;
  pbo_risk_level: PBORiskLevel;
  best_run_id: string;
  best_run_number: number;
  best_nominal_sharpe: number;
  expected_max_sharpe: number;
  deflated_sharpe_ratio: number;
  is_statistically_significant: boolean;
  min_backtest_length_years?: number | null;
  actual_backtest_length_years: number;
  skewness: number;
  kurtosis: number;
  
  degradation_regression: DegradationRegression;
  combinations_sample: CSCVCombinationsPoint[];
  rank_distribution: CSCVHistogramBin[];
  runs_summary: RunOverfittingSummary[];
}

export interface InstitutionalReportResponse {
  envelope: CommonReportEnvelope;
  fact_sheet?: StrategyFactSheetPayload | null;
  tear_sheet?: InstitutionalTearSheetPayload | null;
  research_annex?: ResearchDiagnosticsAnnexPayload | null;
}
