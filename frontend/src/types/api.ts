/**
 * TypeScript API contracts matching backend FastAPI models and endpoints.
 */

export interface HealthResponse {
  status: string;
  stage: string;
  database?: string;
}

export interface RowIssue {
  row: number;
  reasons: string[];
}

export interface ValidationWarning {
  message: string;
}

export interface ValidationReportResponse {
  content_sha256: string;
  rows_examined: number;
  valid_rows: number;
  rejected_rows: number;
  errors: RowIssue[];
  warnings: ValidationWarning[];
  valid_data?: Record<string, any>[] | null;
}

export interface DatasetMetadataResponse {
  dataset_id: string;
  filename: string;
  created_at: string;
  content_sha256: string;
  rows_examined: number;
  valid_rows: number;
  rejected_rows: number;
  errors: RowIssue[];
  warnings: ValidationWarning[];
  user_id?: string | null;
  is_shared?: boolean;
  point_in_time_status?: string;
  calendar_version?: string | null;
  adjustment_policy_version?: string | null;
}

export interface CorporateActionEvent {
  id: string;
  dataset_id?: string | null;
  asset_id: string;
  ticker: string;
  market: 'US' | 'PSX';
  event_type: 'stock_split' | 'reverse_split' | 'cash_dividend' | 'symbol_change' | 'complex_unsupported';
  effective_date: string;
  announcement_date?: string | null;
  ex_date?: string | null;
  record_date?: string | null;
  payment_date?: string | null;
  value: number;
  currency: string;
  source: string;
  revision_id?: string | null;
  status: 'active' | 'superseded' | 'cancelled';
  is_point_in_time_verified: boolean;
  created_at: string;
}

export interface QualityFinding {
  rule_id: string;
  severity: 'error' | 'warning' | 'info';
  ticker: string;
  market: string;
  date: string;
  message: string;
  details?: Record<string, any>;
  policy_version?: string;
}

export interface QualityAuditReport {
  policy_version: string;
  is_valid: boolean;
  total_findings: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  findings: QualityFinding[];
}

export interface ExchangeCalendarSessionInfo {
  market: string;
  calendar_id: string;
  version: string;
  timezone: string;
  sessions: string[];
  holidays: Array<{ date: string; reason: string }>;
}

export interface DatasetSnapshotCreateRequest {
  tag?: string | null;
  description?: string | null;
  as_of_date?: string | null;
  strict_pit?: boolean;
  adjustment_policy_version?: string | null;
}

export interface DatasetSnapshotResponse {
  id: string;
  snapshot_id?: string;
  dataset_id: string;
  user_id?: string | null;
  tag?: string | null;
  description?: string | null;
  snapshot_type: string;
  manifest_sha256: string;
  manifest_hash?: string;
  manifest: Record<string, any>;
  as_of_date?: string | null;
  point_in_time_status: string;
  calendar_version?: string | null;
  adjustment_policy_version?: string | null;
  is_frozen: boolean;
  total_bars_count: number;
  bar_count?: number;
  total_actions_count: number;
  created_at: string;
}

export interface DatasetSnapshotVerifyResponse {
  snapshot_id: string;
  is_verified: boolean;
  manifest_sha256: string;
  expected_hash?: string;
  computed_hash?: string;
  message: string;
  verified_at?: string;
}

export interface AssetMetadata {
  asset_id: string;
  ticker: string;
  market: 'US' | 'PSX';
  currency: string;
  start_date: string;
  end_date: string;
  observation_count: number;
}

export interface DatasetAssetsResponse {
  dataset_id: string;
  asset_count: number;
  assets: AssetMetadata[];
}

export interface DatasetQuery {
  dataset_id: string;
  start_date: string;
  end_date: string;
  tickers?: string[] | null;
  market?: 'US' | 'PSX' | null;
}

export interface DatasetQueryResponse {
  dataset_id: string;
  start_date: string;
  end_date: string;
  row_count: number;
  data: Record<string, any>[];
}

export interface WeightBoundsModel {
  lower: number;
  upper: number;
}

export interface InvestmentConstraintsModel {
  default_min_weight: number;
  default_max_weight: number;
  asset_bounds?: Record<string, WeightBoundsModel>;
  target_total_weight?: number;
  allow_short?: boolean;
  max_gross_exposure?: number | null;
  min_net_exposure?: number | null;
  max_net_exposure?: number | null;
  included_assets?: string[];
  excluded_assets?: string[];
}

export interface PortfolioDefinition {
  portfolio_id?: string;
  name: string;
  dataset_id: string;
  assets: string[];
  weights?: Record<string, number> | null;
  constraints: InvestmentConstraintsModel;
  start_date?: string | null;
  end_date?: string | null;
  base_currency?: string | null;
  version?: string;
}

export interface PortfolioValidationReport {
  is_valid: boolean;
  portfolio_name: string;
  dataset_id: string;
  selected_assets: string[];
  asset_details: AssetMetadata[];
  currency_policy: {
    base_currency?: string;
    currencies_present?: string[];
    is_multi_currency?: boolean;
    valid?: boolean;
    [key: string]: any;
  };
  date_coverage: {
    start_date?: string;
    end_date?: string;
    common_bar_count?: number;
    has_sufficient_bars?: boolean;
    [key: string]: any;
  };
  weight_summary?: Record<string, any> | null;
  feasibility: {
    is_feasible?: boolean;
    [key: string]: any;
  };
  errors: string[];
  warnings: string[];
}

export type OptimizationObjective = 'min_variance' | 'max_sharpe' | 'equal_weight' | 'target_return';

export interface OptimizationRequest {
  portfolio: PortfolioDefinition;
  objective: OptimizationObjective;
  target_return?: number | null;
  risk_free_rate?: number;
  annualized?: boolean;
  periods_per_year?: number;
}

export interface PortfolioMetricsModel {
  expected_return: number;
  variance: number;
  volatility: number;
  sharpe_ratio?: number | null;
  total_weight: number;
  gross_exposure: number;
  is_fully_invested: boolean;
  is_long_only: boolean;
  has_short_positions: boolean;
}

export interface SolverDiagnosticsModel {
  solver_name: string;
  status: string;
  message: string;
  converged: boolean;
  iterations?: number | null;
  objective_value?: number | null;
}

export interface OptimizationResponse {
  is_success: boolean;
  portfolio_name: string;
  dataset_id: string;
  currency: string;
  objective: string;
  assets: string[];
  weights: Record<string, number>;
  metrics?: PortfolioMetricsModel | null;
  is_feasible: boolean;
  constraint_violations: string[];
  solver_diagnostics: SolverDiagnosticsModel;
  annualization: {
    annualized?: boolean;
    periods_per_year?: number;
    risk_free_rate?: number;
    [key: string]: any;
  };
  date_coverage: {
    start_date?: string;
    end_date?: string;
    common_bar_count?: number;
    [key: string]: any;
  };
  warnings: string[];
  errors: string[];
}

export type FrontierPointClassification = 'efficient' | 'dominated_inefficient' | 'infeasible' | 'failed';

export interface FrontierPointModel {
  target_return: number;
  actual_return: number;
  variance: number;
  volatility: number;
  sharpe_ratio?: number | null;
  weights: Record<string, number>;
  is_feasible: boolean;
  status: string;
  classification: FrontierPointClassification;
  solver_message: string;
  target_residual: number;
  constraint_violations: string[];
  warnings: string[];
}

export interface EfficientFrontierRequest {
  portfolio: PortfolioDefinition;
  target_count?: number;
  target_returns?: number[] | null;
  risk_free_rate?: number;
  annualized?: boolean;
  periods_per_year?: number;
}

export interface EfficientFrontierResponse {
  is_success: boolean;
  portfolio_name: string;
  dataset_id: string;
  currency: string;
  points: FrontierPointModel[];
  global_minimum_variance?: FrontierPointModel | null;
  requested_count: number;
  successful_count: number;
  failed_count: number;
  is_complete: boolean;
  min_feasible_return?: number | null;
  max_feasible_return?: number | null;
  annualization: {
    annualized?: boolean;
    periods_per_year?: number;
    risk_free_rate?: number;
    [key: string]: any;
  };
  date_coverage: {
    start_date?: string;
    end_date?: string;
    common_bar_count?: number;
    [key: string]: any;
  };
  warnings: string[];
  errors: string[];
}

export interface PortfolioRiskSummaryModel {
  arithmetic_mean_return: number;
  geometric_cumulative_return: number;
  annualized_return: number;
  periodic_volatility: number;
  annualized_volatility: number;
  variance: number;
  maximum_drawdown: number;
  downside_deviation: number;
  sharpe_ratio?: number | null;
  sortino_ratio?: number | null;
  mar_annualized: number;
  risk_free_rate: number;
  observation_count: number;
  start_date: string;
  end_date: string;
  periods_per_year: number;
}

export interface PortfolioComparisonItemModel {
  name: string;
  weights: Record<string, number>;
  metrics: PortfolioMetricsModel;
  risk_summary?: PortfolioRiskSummaryModel | null;
  is_feasible: boolean;
}

export interface PortfolioComparisonRequest {
  portfolio: PortfolioDefinition;
  include_gmv?: boolean;
  include_max_sharpe?: boolean;
  include_equal_weight?: boolean;
  custom_portfolios?: Record<string, Record<string, number>>;
  risk_free_rate?: number;
  annualized?: boolean;
  periods_per_year?: number;
}

export interface PortfolioComparisonResponse {
  is_success: boolean;
  portfolio_name: string;
  dataset_id: string;
  currency: string;
  portfolios: PortfolioComparisonItemModel[];
  annualization: Record<string, any>;
  date_coverage: Record<string, any>;
  warnings: string[];
  errors: string[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: 'researcher' | 'admin' | string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
  role?: 'researcher' | 'admin';
}

export interface AuthMessageResponse {
  detail: string;
}

export type StrategyType = 'target_weights' | 'equal_weight' | 'walk_forward_optimization';
export type RebalanceFrequency = 'buy_and_hold' | 'daily' | 'weekly' | 'monthly' | 'quarterly';
export type BacktestOptimizationObjective = 'min_variance' | 'max_sharpe';

export interface BacktestRequest {
  dataset_id: string;
  name: string;
  strategy_type: StrategyType;
  assets: string[];
  weights?: Record<string, number> | null;
  rebalance_frequency: RebalanceFrequency;
  initial_capital: number;
  transaction_cost_bps: number;
  slippage_bps: number;
  start_date?: string | null;
  end_date?: string | null;
  training_window?: number;
  test_window?: number;
  optimization_objective?: BacktestOptimizationObjective;
  risk_free_rate?: number;
  use_point_in_time?: boolean;
  as_of_date?: string | null;
  strict_pit?: boolean;
  adjustment_type?: "total" | "price";
  snapshot_id?: string | null;
  auto_snapshot?: boolean;
}


export interface EquityPoint {
  date: string;
  portfolio_value_net: number;
  portfolio_value_gross: number;
  return_net: number;
  return_gross: number;
  drawdown_net: number;
  drawdown_gross: number;
}

export interface RebalanceEvent {
  date: string;
  reason: string;
  turnover: number;
  traded_notional: number;
  transaction_cost: number;
  slippage_cost: number;
  portfolio_value_before: number;
  portfolio_value_after: number;
  pre_weights: Record<string, number>;
  post_weights: Record<string, number>;
}

export interface BacktestSummaryMetrics {
  initial_value: number;
  final_value_net: number;
  final_value_gross: number;
  cumulative_return_net: number;
  cumulative_return_gross: number;
  cagr_net: number;
  cagr_gross: number;
  annualized_return_net: number;
  annualized_return_gross: number;
  volatility_annualized_net: number;
  volatility_annualized_gross: number;
  sharpe_ratio_net: number | null;
  sharpe_ratio_gross: number | null;
  sortino_ratio_net: number | null;
  sortino_ratio_gross: number | null;
  max_drawdown_net: number;
  max_drawdown_gross: number;
  drawdown_peak_date: string | null;
  drawdown_trough_date: string | null;
  total_turnover: number;
  total_transaction_costs: number;
  total_slippage_costs: number;
  total_friction_costs: number;
  number_of_rebalances: number;
  observation_count: number;
  periods_per_year: number;
  effective_start_date: string;
  effective_end_date: string;
}

export interface BacktestResponse {
  id: string;
  dataset_id: string;
  user_id?: string | null;
  name: string;
  strategy_type: string;
  rebalance_frequency: string;
  initial_capital: number;
  transaction_cost_bps: number;
  slippage_bps: number;
  status: string;
  created_at: string;
  metrics: BacktestSummaryMetrics;
  equity_curve: EquityPoint[];
  rebalance_events: RebalanceEvent[];
  warnings: string[];
  point_in_time_metadata?: Record<string, any> | null;
  snapshot_id?: string | null;
  snapshot_provenance?: Record<string, any> | null;
}


export interface BacktestListItem {
  id: string;
  dataset_id: string;
  user_id?: string | null;
  name: string;
  strategy_type: string;
  rebalance_frequency: string;
  initial_capital: number;
  final_value_net: number;
  cumulative_return_net: number;
  cagr_net: number;
  sharpe_ratio_net: number | null;
  max_drawdown_net: number;
  status: string;
  created_at: string;
  snapshot_id?: string | null;
}

export type ScenarioType = 'custom_asset_shock' | 'historical_window' | 'covariance_stress';

export interface AssetShockContribution {
  asset_id: string;
  ticker: string;
  baseline_weight: number;
  baseline_value: number;
  shock_pct: number;
  stressed_value: number;
  value_change: number;
  return_contribution: number;
  share_of_total_change: number;
}

export interface ScenarioSummaryMetrics {
  baseline_portfolio_value: number;
  stressed_portfolio_value: number;
  absolute_change: number;
  percentage_change: number;
  currency: string;
  cash_value: number;
  baseline_volatility?: number | null;
  stressed_volatility?: number | null;
  volatility_change?: number | null;
}

export interface ScenarioRequest {
  dataset_id: string;
  name: string;
  scenario_type: ScenarioType;
  assets: string[];
  weights: Record<string, number>;
  initial_capital?: number;
  asset_shocks?: Record<string, number> | null;
  historical_start_date?: string | null;
  historical_end_date?: string | null;
  volatility_multiplier?: number | null;
  correlation_multiplier?: number | null;
  auto_project_psd?: boolean;
}

export interface ScenarioResponse {
  id: string;
  dataset_id: string;
  name: string;
  scenario_type: string;
  status: string;
  created_at: string;
  metrics: ScenarioSummaryMetrics;
  contributions: AssetShockContribution[];
  warnings: string[];
  is_hypothetical: boolean;
  disclaimer: string;
}

export interface SensitivityGridPoint {
  factor_1_value: number;
  factor_2_value?: number | null;
  stressed_portfolio_value: number;
  percentage_change: number;
  absolute_change: number;
}

export interface SensitivityRequest {
  dataset_id: string;
  name: string;
  assets: string[];
  weights: Record<string, number>;
  initial_capital?: number;
  factor_1_asset: string;
  factor_1_min_shock?: number;
  factor_1_max_shock?: number;
  factor_1_steps?: number;
  factor_2_asset?: string | null;
  factor_2_min_shock?: number | null;
  factor_2_max_shock?: number | null;
  factor_2_steps?: number | null;
}

export interface SensitivityResponse {
  id: string;
  dataset_id: string;
  name: string;
  factor_1_asset: string;
  factor_2_asset?: string | null;
  grid: SensitivityGridPoint[];
  baseline_portfolio_value: number;
  currency: string;
  warnings: string[];
  is_hypothetical: boolean;
}

export interface ScenarioListItem {
  id: string;
  dataset_id: string;
  user_id?: string | null;
  name: string;
  scenario_type: string;
  percentage_change: number;
  absolute_change: number;
  currency: string;
  created_at: string;
}

export type DistributionModel = 'multivariate_normal' | 'multivariate_student_t';
export type RebalancePolicy = 'buy_and_hold' | 'constant_weights';

export interface VaRCVaREstimate {
  confidence_level: number;
  var_absolute: number;
  var_percentage: number;
  cvar_absolute: number;
  cvar_percentage: number;
}

export interface MultiEstimatorComparison {
  confidence_level: number;
  monte_carlo_var: number;
  monte_carlo_cvar: number;
  parametric_var: number;
  parametric_cvar: number;
  historical_var?: number | null;
  historical_cvar?: number | null;
}

export interface SimulationPathPoint {
  day: number;
  median_value: number;
  percentile_5: number;
  percentile_95: number;
  sample_paths: number[];
}

export interface DistributionBin {
  bin_start: number;
  bin_end: number;
  count: number;
  relative_frequency: number;
}

export interface RiskSimulationSummary {
  initial_capital: number;
  expected_terminal_value: number;
  median_terminal_value: number;
  expected_terminal_return: number;
  terminal_return_volatility: number;
  terminal_quantiles: Record<string, number>;
  prob_negative_return: number;
  prob_exceed_threshold?: number | null;
  min_terminal_value: number;
  max_terminal_value: number;
  var_cvar_metrics: VaRCVaREstimate[];
  estimator_comparisons: MultiEstimatorComparison[];
  currency: string;
}

export interface RiskSimulationRequest {
  dataset_id: string;
  name: string;
  assets: string[];
  weights: Record<string, number>;
  initial_capital?: number;
  horizon_days?: number;
  num_paths?: number;
  confidence_levels?: number[];
  distribution?: DistributionModel;
  degrees_of_freedom?: number;
  rebalance_policy?: RebalancePolicy;
  seed?: number | null;
  loss_threshold?: number | null;
  custom_expected_returns?: Record<string, number> | null;
}

export interface RiskSimulationResponse {
  id: string;
  dataset_id: string;
  name: string;
  distribution: string;
  rebalance_policy: string;
  horizon_days: number;
  num_paths: number;
  seed: number;
  summary: RiskSimulationSummary;
  distribution_bins: DistributionBin[];
  trajectory: SimulationPathPoint[];
  warnings: string[];
  is_hypothetical: boolean;
  disclaimer: string;
  created_at: string;
}

export interface RiskSimulationListItem {
  id: string;
  dataset_id: string;
  user_id?: string | null;
  name: string;
  distribution: string;
  horizon_days: number;
  num_paths: number;
  expected_terminal_return: number;
  var_95: number;
  cvar_95: number;
  currency: string;
  created_at: string;
}

export interface VaRCVaRStandaloneRequest {
  dataset_id: string;
  assets: string[];
  weights: Record<string, number>;
  initial_capital?: number;
  horizon_days?: number;
  confidence_levels?: number[];
}

export interface PerformanceAnalysisRequest {
  dataset_id: string;
  backtest_id?: string | null;
  name?: string;
  benchmark_asset: string;
  assets?: string[] | null;
  weights?: Record<string, number> | null;
  risk_free_rate?: number;
  start_date?: string | null;
  end_date?: string | null;
  save_report?: boolean;
}

export interface AssetContribution {
  asset: string;
  weight: number;
  cumulative_return: number;
  total_contribution: number;
  share_of_return: number;
}

export interface PerformanceTimeseriesPoint {
  date: string;
  portfolio_return: number;
  benchmark_return: number;
  active_return: number;
  portfolio_cumulative: number;
  benchmark_cumulative: number;
  active_cumulative: number;
  drawdown_portfolio: number;
  drawdown_benchmark: number;
}

export interface PerformanceSummaryMetrics {
  observation_count: number;
  periods_per_year: number;
  start_date?: string | null;
  end_date?: string | null;

  // Standalone Portfolio
  portfolio_cumulative_return: number;
  portfolio_annualized_return: number;
  portfolio_annualized_volatility: number;
  portfolio_sharpe_ratio: number | null;
  portfolio_sortino_ratio: number | null;
  portfolio_max_drawdown: number;

  // Standalone Benchmark
  benchmark_cumulative_return: number;
  benchmark_annualized_return: number;
  benchmark_annualized_volatility: number;
  benchmark_sharpe_ratio: number | null;
  benchmark_sortino_ratio: number | null;
  benchmark_max_drawdown: number;

  // Active / Comparative
  arithmetic_active_return: number;
  geometric_excess_return: number;
  annualized_active_return: number;
  tracking_error: number;
  information_ratio: number | null;
  beta: number | null;
  alpha_annualized: number | null;
  treynor_ratio: number | null;
  up_capture_ratio: number | null;
  down_capture_ratio: number | null;
}

export interface PerformanceResponse {
  id: string;
  name: string;
  dataset_id: string;
  backtest_id?: string | null;
  benchmark_asset: string;
  risk_free_rate: number;
  start_date?: string | null;
  end_date?: string | null;
  status: string;
  metrics: PerformanceSummaryMetrics;
  contributions: AssetContribution[];
  timeseries: PerformanceTimeseriesPoint[];
  warnings: string[];
  is_hypothetical: boolean;
  disclaimer: string;
  created_at: string;
}

export interface PerformanceReportListItem {
  id: string;
  name: string;
  dataset_id: string;
  backtest_id?: string | null;
  benchmark_asset: string;
  portfolio_cumulative_return: number;
  benchmark_cumulative_return: number;
  arithmetic_active_return: number;
  information_ratio: number | null;
  beta: number | null;
  alpha_annualized: number | null;
  status: string;
  created_at: string;
}

// ============================================================================
// Research Experiments, Strategy Comparison & Reproducible Runs Types
// ============================================================================

export type ResearchStrategyType =
  | 'target_weights'
  | 'equal_weight'
  | 'walk_forward_optimization'
  | 'benchmark_attribution'
  | 'monte_carlo_risk';

export interface ResearchExperimentConfig {
  strategy_type: ResearchStrategyType;
  dataset_id: string;
  assets: string[];
  weights?: Record<string, number> | null;
  rebalance_frequency?: string;
  transaction_cost_bps?: number;
  slippage_bps?: number;
  objective?: string | null;
  training_window?: number;
  benchmark_asset?: string | null;
  risk_free_rate?: number;
  distribution?: string;
  degrees_of_freedom?: number;
  horizon_days?: number;
  num_paths?: number;
  initial_capital?: number;
  rebalance_policy?: string;
  seed?: number | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface ExperimentCreateRequest {
  name: string;
  description?: string | null;
  strategy_type: ResearchStrategyType;
  dataset_id: string;
  config: Record<string, any>;
}

export interface ExperimentUpdateRequest {
  name?: string;
  description?: string | null;
  config?: Record<string, any>;
}

export interface ExperimentResponse {
  id: string;
  user_id?: string | null;
  dataset_id: string;
  name: string;
  description?: string | null;
  strategy_type: ResearchStrategyType;
  config: Record<string, any>;
  config_fingerprint: string;
  version: number;
  created_at: string;
  updated_at: string;
  latest_run_status?: string | null;
  latest_run_number?: number | null;
  total_runs_count: number;
}

export interface ExperimentListItem {
  id: string;
  name: string;
  description?: string | null;
  strategy_type: ResearchStrategyType;
  dataset_id: string;
  version: number;
  config_fingerprint: string;
  latest_run_status?: string | null;
  latest_run_number?: number | null;
  total_runs_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExperimentRunResponse {
  id: string;
  experiment_id: string;
  run_number: number;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  dataset_version_hash?: string | null;
  config_fingerprint: string;
  execution_duration_ms?: number | null;
  backtest_id?: string | null;
  performance_report_id?: string | null;
  risk_simulation_id?: string | null;
  summary_kpis?: Record<string, any> | null;
  error_message?: string | null;
  snapshot_id?: string | null;
  is_reproducible: boolean;
  reproducibility_notes: string[];
  created_at: string;
  completed_at?: string | null;
}

export interface ExperimentRunListItem {
  id: string;
  experiment_id: string;
  run_number: number;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  config_fingerprint: string;
  execution_duration_ms?: number | null;
  snapshot_id?: string | null;
  is_reproducible: boolean;
  created_at: string;
  completed_at?: string | null;
  summary_kpis?: Record<string, any> | null;
}

export interface ComparisonRequest {
  run_ids: string[];
}

export interface ComparisonRunMetricItem {
  run_id: string;
  experiment_id: string;
  experiment_name: string;
  strategy_type: ResearchStrategyType;
  run_number: number;
  status: string;
  dataset_id: string;
  dataset_version_hash?: string | null;
  config_fingerprint: string;
  currency: string;
  is_reproducible: boolean;
  execution_date: string;
  start_date?: string | null;
  end_date?: string | null;
  observations_count?: number | null;
  metrics: Record<string, any>;
  config_summary: Record<string, any>;
}

export interface ComparisonResponse {
  runs: ComparisonRunMetricItem[];
  common_currency: string;
  has_period_divergence: boolean;
  has_provenance_divergence: boolean;
  warnings: string[];
}

export interface ExpectedReturnUncertaintyRequest {
  model: 'none' | 'box' | 'ellipsoidal';
  confidence_level: number;
  absolute_radius?: number | null;
}

export interface CovarianceShrinkageRequest {
  target: 'none' | 'diagonal' | 'scaled_identity' | 'constant_correlation';
  intensity: number;
}

export interface RobustConstraintsRequest {
  default_min_weight: number;
  default_max_weight: number;
  target_total_weight: number;
  allow_short: boolean;
  max_gross_exposure?: number | null;
}

export interface RobustOptimizationRequest {
  dataset_id: string;
  assets: string[];
  start_date?: string | null;
  end_date?: string | null;
  objective: 'max_sharpe' | 'min_variance' | 'mean_variance_utility';
  uncertainty: ExpectedReturnUncertaintyRequest;
  shrinkage: CovarianceShrinkageRequest;
  constraints: RobustConstraintsRequest;
  risk_free_rate: number;
  risk_aversion: number;
}

export interface PortfolioWeightItem {
  asset_id: string;
  baseline_weight: number;
  robust_weight: number;
  weight_difference: number;
  nominal_return: number;
  worst_case_return: number;
  uncertainty_radius: number;
}

export interface RobustOptimizationResponse {
  objective: string;
  dataset_id: string;
  assets: string[];
  weights: PortfolioWeightItem[];
  baseline_weights: Record<string, number>;
  robust_weights: Record<string, number>;
  baseline_metrics: Record<string, any>;
  robust_metrics: Record<string, any>;
  diagnostics: Record<string, any>;
  shrunk_covariance: number[][];
  is_feasible: boolean;
  solver_status: string;
  solver_message: string;
  warnings: string[];
}

export interface SensitivityAnalysisRequest {
  dataset_id: string;
  assets: string[];
  start_date?: string | null;
  end_date?: string | null;
  parameter_to_sweep: 'max_weight' | 'uncertainty_level' | 'shrinkage_intensity';
  grid_min: number;
  grid_max: number;
  num_steps: number;
  objective: string;
  uncertainty: ExpectedReturnUncertaintyRequest;
  shrinkage: CovarianceShrinkageRequest;
  constraints: RobustConstraintsRequest;
  risk_free_rate: number;
}

export interface SensitivityPointResponse {
  parameter_value: number;
  parameter_label: string;
  is_feasible: boolean;
  solver_status: string;
  weights: Record<string, number>;
  nominal_expected_return: number;
  worst_case_expected_return: number;
  volatility: number;
  sharpe_ratio: number | null;
  weight_distance_d1: number;
  hhi: number;
  effective_assets: number;
  binding_constraints: string[];
}

export interface SensitivityAnalysisResponse {
  parameter_name: string;
  parameter_description: string;
  baseline_value: number;
  points: SensitivityPointResponse[];
  total_evaluations: number;
  feasible_evaluations: number;
  infeasible_evaluations: number;
  warnings: string[];
}

export interface RobustBacktestRequest {
  dataset_id: string;
  assets: string[];
  train_end_date: string;
  objective: string;
  uncertainty: ExpectedReturnUncertaintyRequest;
  shrinkage: CovarianceShrinkageRequest;
  constraints: RobustConstraintsRequest;
  rebalance_frequency: string;
  cost_bps: number;
  slippage_bps: number;
  risk_free_rate: number;
}

export interface RobustBacktestResponse {
  dataset_id: string;
  assets: string[];
  train_period: { start: string; end: string };
  test_period: { start: string; end: string };
  baseline_weights: Record<string, number>;
  robust_weights: Record<string, number>;
  weight_distance_d1: number;
  baseline_kpis: Record<string, any>;
  robust_kpis: Record<string, any>;
  out_of_sample_comparison: Record<string, any>;
  equity_curves: Array<{
    date: string;
    baseline_portfolio_value: number;
    robust_portfolio_value: number;
    baseline_drawdown: number;
    robust_drawdown: number;
  }>;
  warnings: string[];
}

export interface BlackLittermanViewItem {
  view_type: 'relative' | 'absolute';
  assets: string[];
  weights: number[];
  target_return: number;
  confidence: number;
  description?: string;
}

export interface BlackLittermanConstraints {
  default_min_weight: number;
  default_max_weight: number;
  target_total_weight?: number;
  allow_short?: boolean;
  max_gross_exposure?: number;
}

export interface BlackLittermanViewSummaryItem {
  description: string;
  view_type: string;
  confidence: number;
  target_return: number;
  prior_expected_spread: number;
  posterior_expected_spread: number;
  absorbed_difference: number;
}

export interface BlackLittermanOptimizeRequest {
  dataset_id: string;
  assets: string[];
  start_date?: string | null;
  end_date?: string | null;
  tau?: number;
  risk_aversion?: number;
  equilibrium_weights?: Record<string, number> | null;
  views?: BlackLittermanViewItem[];
  objective?: string;
  constraints?: BlackLittermanConstraints;
  risk_free_rate?: number;
}

export interface BlackLittermanOptimizeResponse {
  dataset_id: string;
  assets: string[];
  equilibrium_returns: Record<string, number>;
  posterior_returns: Record<string, number>;
  prior_weights: Record<string, number>;
  unconstrained_bl_weights: Record<string, number>;
  optimal_weights: Record<string, number>;
  active_tilts: Record<string, number>;
  portfolio_metrics: {
    expected_return?: number;
    volatility?: number;
    sharpe_ratio?: number | null;
    [key: string]: any;
  };
  diagnostics: {
    weight_distance_d1: number;
    max_tilt_asset: string;
    max_tilt_value: number;
    hhi_prior: number;
    hhi_optimal: number;
    effective_assets_prior: number;
    effective_assets_optimal: number;
    [key: string]: any;
  };
  views_summary: BlackLittermanViewSummaryItem[];
  is_feasible: boolean;
  solver_status: string;
  solver_message: string;
  warnings: string[];
}

export interface BlackLittermanBacktestRequest {
  dataset_id: string;
  assets: string[];
  train_end_date: string;
  tau?: number;
  risk_aversion?: number;
  equilibrium_weights?: Record<string, number> | null;
  views?: BlackLittermanViewItem[];
  objective?: string;
  min_weight?: number;
  max_weight?: number;
  rebalance_frequency?: string;
  cost_bps?: number;
  slippage_bps?: number;
  risk_free_rate?: number;
}

export interface BlackLittermanBacktestResponse {
  dataset_id: string;
  assets: string[];
  train_period: { start: string; end: string };
  test_period: { start: string; end: string };
  equilibrium_weights: Record<string, number>;
  optimal_weights: Record<string, number>;
  active_tilts: Record<string, number>;
  equilibrium_kpis: {
    cumulative_return: number;
    annualized_return: number;
    annualized_volatility: number;
    sharpe_ratio: number;
    max_drawdown: number;
    total_turnover: number;
    total_friction_costs: number;
    final_value: number;
    [key: string]: any;
  };
  black_litterman_kpis: {
    cumulative_return: number;
    annualized_return: number;
    annualized_volatility: number;
    sharpe_ratio: number;
    max_drawdown: number;
    total_turnover: number;
    total_friction_costs: number;
    final_value: number;
    [key: string]: any;
  };
  equity_curves: Array<{
    date: string;
    equilibrium_portfolio_value: number;
    black_litterman_portfolio_value: number;
    equilibrium_drawdown: number;
    black_litterman_drawdown: number;
  }>;
  warnings: string[];
}

export interface RiskParityConstraints {
  default_min_weight?: number;
  default_max_weight?: number;
}

export interface RiskParityOptimizeRequest {
  dataset_id: string;
  method: 'erc' | 'hrp' | 'inverse_variance' | 'equal_weight';
  linkage_method?: 'single' | 'complete' | 'average';
  risk_budgets?: Record<string, number> | null;
  constraints?: RiskParityConstraints | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface RiskParityOptimizeResponse {
  dataset_id: string;
  method: string;
  linkage_method: string;
  assets: string[];
  weights: Record<string, number>;
  marginal_risk_contributions: Record<string, number>;
  total_risk_contributions: Record<string, number>;
  percentage_risk_contributions: Record<string, number>;
  target_risk_budgets: Record<string, number>;
  portfolio_volatility: number;
  diagnostics: {
    risk_gini: number;
    effective_bets: number;
    diversification_ratio: number;
    [key: string]: any;
  };
  reordered_indices?: number[] | null;
  is_feasible: boolean;
  solver_status: string;
  solver_message: string;
}

export interface RiskParityBacktestRequest {
  dataset_id: string;
  method: 'erc' | 'hrp' | 'inverse_variance' | 'equal_weight';
  linkage_method?: 'single' | 'complete' | 'average';
  split_date: string;
  rebalance_frequency?: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  transaction_cost_bps?: number;
  slippage_bps?: number;
  initial_cash?: number;
}

export interface RiskParityBacktestComparisonMetrics {
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  calmar_ratio: number | null;
  total_net_return: number;
  total_transaction_costs: number;
  total_slippage_costs: number;
  rebalance_count: number;
}

export interface RiskParityBacktestResponse {
  dataset_id: string;
  method: string;
  split_date: string;
  in_sample_end: string;
  out_of_sample_start: string;
  out_of_sample_end: string;
  strategy_metrics: RiskParityBacktestComparisonMetrics;
  equal_weight_benchmark_metrics: RiskParityBacktestComparisonMetrics;
  strategy_weights: Record<string, number>;
  equity_curve: Array<{
    date: string;
    strategy: number;
    benchmark: number;
  }>;
  drawdown_curve: Array<{
    date: string;
    strategy: number;
    benchmark: number;
  }>;
}

// ============================================================================
// Factor Investing & Systematic Risk Decomposition
// ============================================================================

export interface FactorBetaMetric {
  beta: number;
  stderr: number;
  tstat: number;
  pvalue: number;
}

export interface AssetFactorProfile {
  alpha_annualized: number;
  alpha_stderr: number;
  alpha_tstat: number;
  alpha_pvalue: number;
  betas: Record<string, FactorBetaMetric>;
  r_squared: number;
  r_squared_adj: number;
  specific_variance_annualized: number;
  specific_volatility_annualized: number;
}

export interface FactorContributionDetail {
  exposure: number;
  marginal_contrib: number;
  total_variance_contrib: number;
  pct_of_systematic_risk: number;
}

export interface PortfolioRiskDecomposition {
  total_volatility: number;
  systematic_volatility: number;
  idiosyncratic_volatility: number;
  systematic_variance: number;
  idiosyncratic_variance: number;
  total_variance: number;
  systematic_share_pct: number;
  idiosyncratic_share_pct: number;
  systematic_variance_pct: number;
  specific_variance_pct: number;
  portfolio_volatility_pct: number;
  portfolio_betas: Record<string, number>;
  factor_contributions: Record<string, FactorContributionDetail>;
}

export interface FactorAttributionRequest {
  dataset_id: string;
  factor_model?: 'capm' | 'ff3' | 'carhart4' | 'pca';
  num_pca_factors?: number;
  weights?: Record<string, number>;
  risk_free_rate?: number;
  start_date?: string | null;
  end_date?: string | null;
}

export interface FactorAttributionResponse {
  dataset_id: string;
  factor_model: string;
  factors: string[];
  assets: string[];
  weights: Record<string, number>;
  asset_profiles: Record<string, AssetFactorProfile>;
  asset_loadings: Record<string, AssetFactorProfile>;
  portfolio_betas: Record<string, number>;
  risk_decomposition: PortfolioRiskDecomposition;
  factor_covariance: number[][];
}

export interface FactorConstraintBound {
  min_beta?: number | null;
  max_beta?: number | null;
}

export interface FactorConstrainedOptimizeRequest {
  dataset_id: string;
  factor_model?: 'capm' | 'ff3' | 'carhart4' | 'pca';
  num_pca_factors?: number;
  objective?: 'min_variance' | 'max_sharpe' | 'max_utility';
  risk_aversion?: number;
  risk_free_rate?: number;
  min_weight?: number;
  max_weight?: number;
  factor_constraints?: Record<string, FactorConstraintBound>;
}

export interface FactorConstrainedOptimizeResponse {
  dataset_id: string;
  factor_model: string;
  objective: string;
  assets: string[];
  weights: Record<string, number>;
  portfolio_betas: Record<string, number>;
  realized_factor_betas: Record<string, number>;
  risk_decomposition: PortfolioRiskDecomposition;
  is_success: boolean;
  is_feasible: boolean;
  solver_status: string;
  solver_message: string;
  diagnostics: Record<string, any>;
}

export interface DynamicFactorSummaryMetrics {
  total_return: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  calmar_ratio: number;
  active_return: number;
  tracking_error: number;
  information_ratio: number;
  average_turnover: number;
  total_transaction_costs: number;
}

export interface DynamicFactorBenchmarkMetrics {
  total_return: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export interface DynamicFactorEquityPoint {
  date: string;
  strategy_equity: number;
  benchmark_equity: number;
  drawdown: number;
}

export interface DynamicFactorRebalanceEvent {
  date: string;
  weights: Record<string, number>;
  portfolio_betas: Record<string, number>;
  systematic_volatility: number;
  idiosyncratic_volatility: number;
  systematic_share_pct: number;
  turnover: number;
  cost_incurred: number;
  is_feasible: boolean;
  solver_message: string;
}

export interface DynamicFactorExposureSeries {
  dates: string[];
  exposures: Record<string, number[]>;
}

export interface DynamicFactorBacktestRequest {
  dataset_id: string;
  factor_model?: 'capm' | 'ff3' | 'carhart4' | 'pca';
  num_pca_factors?: number;
  strategy_type?: 'factor_tilt' | 'factor_min_variance' | 'factor_momentum_rotation';
  estimation_window?: number;
  rebalance_frequency?: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly';
  factor_tilts?: Record<string, number>;
  factor_constraints?: Record<string, FactorConstraintBound>;
  top_n_assets?: number;
  risk_aversion?: number;
  turnover_penalty?: number;
  min_weight?: number;
  max_weight?: number;
  transaction_cost_bps?: number;
  slippage_bps?: number;
  initial_capital?: number;
  risk_free_rate?: number;
  start_date?: string;
  end_date?: string;
}

export interface DynamicFactorBacktestResponse {
  dataset_id: string;
  strategy_type: string;
  factor_model: string;
  estimation_window: number;
  rebalance_frequency: string;
  total_rebalances: number;
  summary_metrics: DynamicFactorSummaryMetrics;
  benchmark_metrics: DynamicFactorBenchmarkMetrics;
  equity_curve: DynamicFactorEquityPoint[];
  rebalance_history: DynamicFactorRebalanceEvent[];
  factor_exposure_series: DynamicFactorExposureSeries;
}

// Stage 18: Multi-Asset Class Allocation, Cash Drag & FX Hedging
export type AssetClassType = 'Equity' | 'Fixed Income' | 'Commodity' | 'Real Estate' | 'Other';

export interface MultiAssetClassMetadata {
  ticker: string;
  asset_class: AssetClassType;
  currency: string;
}

export interface FxRiskDecomposition {
  asset_local_variance: number;
  fx_currency_variance: number;
  cross_covariance: number;
  total_unhedged_variance: number;
  asset_risk_share_pct: number;
  fx_risk_share_pct: number;
  unhedged_volatility: number;
  local_asset_volatility: number;
}

export interface MultiAssetOptimizeRequest {
  dataset_id: string;
  base_currency?: string;
  assets_metadata?: MultiAssetClassMetadata[];
  hedge_ratios?: Record<string, number>;
  carry_rates?: Record<string, number>;
  asset_class_limits?: Record<string, { min_weight?: number; max_weight?: number }>;
  min_cash_weight?: number;
  max_cash_weight?: number;
  min_asset_weight?: number;
  max_asset_weight?: number;
  objective?: 'max_sharpe' | 'min_variance' | 'risk_parity';
  risk_free_rate?: number;
  start_date?: string;
  end_date?: string;
}

export interface MultiAssetOptimizeResponse {
  risky_weights: Record<string, number>;
  cash_weight: number;
  asset_class_allocations: Record<string, number>;
  expected_annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  fx_risk_decomposition: FxRiskDecomposition;
  is_feasible: boolean;
  solver_message: string;
}

export interface MultiAssetBacktestRequest {
  dataset_id: string;
  base_currency?: string;
  assets_metadata?: MultiAssetClassMetadata[];
  hedge_ratios?: Record<string, number>;
  carry_rates?: Record<string, number>;
  asset_class_limits?: Record<string, { min_weight?: number; max_weight?: number }>;
  min_cash_weight?: number;
  max_cash_weight?: number;
  rebalance_frequency?: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly';
  estimation_window?: number;
  objective?: 'max_sharpe' | 'min_variance' | 'risk_parity';
  risk_free_rate?: number;
  transaction_cost_bps?: number;
  slippage_bps?: number;
  initial_capital?: number;
  start_date?: string;
  end_date?: string;
}

export interface MultiAssetSummaryMetrics {
  initial_capital: number;
  final_equity: number;
  total_return: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  calmar_ratio: number;
  total_turnover: number;
  total_transaction_costs: number;
  total_rebalances: number;
  active_return: number;
  tracking_error: number;
  information_ratio: number;
  total_cash_drag: number;
}

export interface MultiAssetBenchmarkMetrics {
  final_equity: number;
  total_return: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
}

export interface MultiAssetEquityPoint {
  date: string;
  portfolio_equity: number;
  benchmark_equity: number;
  portfolio_return: number;
  benchmark_return: number;
  drawdown: number;
  cash_drag: number;
}

export interface MultiAssetRebalanceEvent {
  date: string;
  risky_weights: Record<string, number>;
  cash_weight: number;
  asset_class_allocations: Record<string, number>;
  turnover: number;
  cost_incurred: number;
  is_feasible: boolean;
  solver_message: string;
}

export interface MultiAssetBacktestResponse {
  summary: MultiAssetSummaryMetrics;
  benchmark: MultiAssetBenchmarkMetrics;
  fx_risk_decomposition: FxRiskDecomposition;
  equity_curve: MultiAssetEquityPoint[];
  rebalance_history: MultiAssetRebalanceEvent[];
  asset_class_allocation_history: Array<{ date: string; [assetClass: string]: string | number }>;
}

// ============================================================================
// STAGE 19: OPTIMAL EXECUTION & MARKET IMPACT MODELING (ALMGREN-CHRISS)
// ============================================================================

export interface OptimalExecutionRequest {
  order_size: number;
  asset_price: number;
  daily_volume: number;
  daily_volatility: number;
  bid_ask_spread?: number;
  horizon_periods?: number;
  trading_hours?: number;
  risk_aversion?: number;
  temporary_impact_factor?: number | null;
  permanent_impact_factor?: number | null;
  volume_profile?: number[] | null;
}

export interface ExecutionSchedulePoint {
  period: number;
  time_elapsed_hours: number;
  time_elapsed_pct: number;
  almgren_chriss_shares: number;
  almgren_chriss_remaining: number;
  twap_shares: number;
  twap_remaining: number;
  vwap_shares: number;
  vwap_remaining: number;
  volume_weight_pct: number;
}

export interface ExecutionSummaryMetrics {
  urgency_parameter: number;
  half_life_hours: number;
  expected_cost: number;
  expected_cost_bps: number;
  timing_risk_variance: number;
  timing_risk_std: number;
  execution_utility: number;
  twap_expected_cost: number;
  twap_expected_cost_bps: number;
  twap_timing_risk_std: number;
  twap_utility: number;
  vwap_expected_cost: number;
  vwap_expected_cost_bps: number;
  cost_savings_vs_twap: number;
  cost_savings_vs_twap_bps: number;
}

export interface OptimalExecutionResponse {
  parameters: Record<string, any>;
  summary: ExecutionSummaryMetrics;
  schedule: ExecutionSchedulePoint[];
}

export interface RebalanceImpactRequest {
  dataset_id: string;
  target_weights: Record<string, number>;
  current_weights?: Record<string, number> | null;
  portfolio_equity?: number;
  execution_horizon_days?: number;
  impact_model?: 'square_root' | 'linear' | 'fixed_bps';
  spread_bps_override?: Record<string, number> | null;
}

export interface AssetImpactMetrics {
  ticker: string;
  traded_notional: number;
  adv: number;
  participation_rate_pct: number;
  spread_cost: number;
  temporary_impact_cost: number;
  permanent_impact_cost: number;
  total_cost: number;
  total_cost_bps: number;
}

export interface RebalanceImpactSummary {
  impact_model: string;
  execution_horizon_days: number;
  total_traded_notional: number;
  total_spread_cost: number;
  total_temporary_impact_cost: number;
  total_permanent_impact_cost: number;
  total_impact_cost: number;
  effective_cost_bps: number;
}

export interface RebalanceImpactResponse {
  summary: RebalanceImpactSummary;
  asset_impacts: AssetImpactMetrics[];
}

// ============================================================================
// STAGE 20: REGIME-SWITCHING ASSET ALLOCATION & VOLATILITY TARGETING
// ============================================================================

export interface RegimeDetectionRequest {
  dataset_id: string;
  tickers?: string[] | null;
  num_states?: number;
  max_iter?: number;
  tolerance?: number;
}

export interface RegimeTimelinePoint {
  date: string;
  return_val: number;
  state: number;
  state_label: string;
  filtered_prob: number[];
  smoothed_prob: number[];
}

export interface RegimeDetectionResponse {
  dataset_id: string;
  num_states: number;
  state_labels: string[];
  transition_matrix: number[][];
  state_means: number[];
  state_volatilities_annual: number[];
  current_state: number;
  current_state_label: string;
  current_regime_probabilities: number[];
  timeline: RegimeTimelinePoint[];
}

export interface RegimeBacktestRequest {
  dataset_id: string;
  tickers?: string[] | null;
  num_states?: number;
  target_volatility?: number;
  max_leverage?: number;
  rebalance_frequency?: 'daily' | 'weekly' | 'monthly';
  transaction_cost_bps?: number;
  lookback_window?: number;
  risk_free_rate?: number;
}

export interface RegimeEquityPoint {
  date: string;
  portfolio_equity: number;
  benchmark_equity: number;
  cash_weight: number;
  leverage: number;
  regime_state: number;
}

export interface RegimeRebalanceEvent {
  date: string;
  regime_state: number;
  regime_probs: number[];
  scaling_factor: number;
  cash_weight: number;
  turnover: number;
  fee_deducted: number;
}

export interface RegimeBacktestSummary {
  initial_equity: number;
  final_equity: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  calmar_ratio: number;
  benchmark_cagr: number;
  benchmark_volatility: number;
  benchmark_sharpe: number;
  target_volatility: number;
  max_leverage: number;
  total_rebalances: number;
}

export interface RegimeBacktestResponse {
  dataset_id: string;
  summary: RegimeBacktestSummary;
  equity_curve: RegimeEquityPoint[];
  rebalance_events: RegimeRebalanceEvent[];
}

// ============================================================================
// Stage 21: Multi-Asset Performance Attribution & Factor Attribution Types
// ============================================================================

export interface BrinsonAttributionRequest {
  dataset_id: string;
  portfolio_weights: Record<string, number>;
  benchmark_weights: Record<string, number>;
  segment_mapping?: Record<string, string>;
  frequency?: 'daily' | 'weekly' | 'monthly';
  method?: 'brinson_fachler' | 'brinson_hood_beebower';
  start_date?: string;
  end_date?: string;
}

export interface SegmentAttributionItem {
  segment: string;
  average_portfolio_weight: number;
  average_benchmark_weight: number;
  active_weight: number;
  linked_allocation_effect: number;
  linked_selection_effect: number;
  linked_interaction_effect: number;
  total_contribution: number;
}

export interface AttributionTimeSeriesPoint {
  period_index: number;
  start_date: string;
  end_date: string;
  portfolio_return: number;
  benchmark_return: number;
  active_return: number;
  allocation_effect: number;
  selection_effect: number;
  interaction_effect: number;
}

export interface BrinsonAttributionSummary {
  cumulative_portfolio_return: number;
  cumulative_benchmark_return: number;
  cumulative_active_return: number;
  total_allocation_effect: number;
  total_selection_effect: number;
  total_interaction_effect: number;
  reconciliation_error: number;
  total_periods: number;
}

export interface BrinsonAttributionResponse {
  dataset_id: string;
  method: string;
  frequency: string;
  summary: BrinsonAttributionSummary;
  segment_attribution: SegmentAttributionItem[];
  time_series: AttributionTimeSeriesPoint[];
}

export interface SystematicFactorAttributionRequest {
  dataset_id: string;
  portfolio_weights: Record<string, number>;
  benchmark_weights: Record<string, number>;
  factor_model?: 'capm' | 'fama_french_3' | 'carhart_4' | 'pca';
  annualization_factor?: number;
  start_date?: string;
  end_date?: string;
}

export interface FactorContributionItem {
  factor: string;
  portfolio_beta: number;
  benchmark_beta: number;
  active_beta: number;
  annualized_factor_return: number;
  annualized_contribution: number;
}

export interface SystematicFactorAttributionResponse {
  dataset_id: string;
  factor_model: string;
  annualized_portfolio_return: number;
  annualized_benchmark_return: number;
  total_active_return: number;
  systematic_active_return: number;
  specific_active_return: number;
  total_tracking_error: number;
  systematic_tracking_error: number;
  specific_tracking_error: number;
  systematic_risk_percent: number;
  specific_risk_percent: number;
  factor_contributions: FactorContributionItem[];
}

// ============================================================================
// Copula Tail Risk & Tail Risk Parity (Stage 22)
// ============================================================================

export type CopulaType = 'clayton' | 'gumbel' | 'student_t' | 'gaussian' | 'best_fit';
export type MarginalMethod = 'empirical' | 'student_t';

export interface PairwiseCopulaResult {
  asset_1: string;
  asset_2: string;
  copula_type: string;
  theta: number;
  df?: number | null;
  kendall_tau: number;
  pearson_corr: number;
  lower_tail_dependence: number;
  upper_tail_dependence: number;
  aic: number;
  bic: number;
}

export interface CopulaFitRequest {
  dataset_id: string;
  copula_type?: CopulaType;
  marginal_method?: MarginalMethod;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface CopulaFitResponse {
  dataset_id: string;
  copula_type: string;
  marginal_method: string;
  tickers: string[];
  tail_dependence_matrix: number[][];
  kendall_tau_matrix: number[][];
  pearson_corr_matrix: number[][];
  pairwise_results: PairwiseCopulaResult[];
}

export interface CopulaSimulateRequest {
  dataset_id: string;
  copula_type?: 'clayton' | 'gumbel' | 'student_t' | 'gaussian';
  marginal_method?: MarginalMethod;
  num_simulations?: number;
  random_seed?: number;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface CopulaSimulateResponse {
  dataset_id: string;
  copula_type: string;
  num_simulations: number;
  random_seed: number;
  tickers: string[];
  simulated_means: Record<string, number>;
  simulated_volatilities: Record<string, number>;
  sample_correlation_matrix: number[][];
  sample_scenarios: Record<string, number>[];
}

export interface BaselinePortfolioRisk {
  weights: Record<string, number>;
  portfolio_var: number;
  portfolio_cvar: number;
  tail_risk_contributions: Record<string, number>;
}

export interface TailRiskParityRequest {
  dataset_id: string;
  copula_type?: 'clayton' | 'gumbel' | 'student_t' | 'gaussian';
  confidence_level?: number;
  num_simulations?: number;
  random_seed?: number;
  marginal_method?: MarginalMethod;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface TailRiskParityResponse {
  dataset_id: string;
  copula_type: string;
  confidence_level: number;
  converged: boolean;
  weights: Record<string, number>;
  tail_risk_contributions: Record<string, number>;
  portfolio_var: number;
  portfolio_cvar: number;
  euler_reconciliation_error: number;
  simulated_loss_distribution: number[];
  baselines: {
    equal_weight: BaselinePortfolioRisk;
    inverse_volatility: BaselinePortfolioRisk;
  };
}

// Stage 23: Regular Vine Copula Types
export type VineType = 'c_vine' | 'd_vine';

export interface VineEdge {
  tree: number;
  node_1: string;
  node_2: string;
  conditioned_on: string[];
  copula_type: string;
  theta: number;
  df?: number | null;
  kendall_tau: number;
  lower_tail_dependence: number;
  upper_tail_dependence: number;
  aic: number;
}

export interface VineCopulaFitRequest {
  dataset_id: string;
  vine_type?: VineType;
  marginal_method?: MarginalMethod;
  family_set?: string[];
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface VineCopulaFitResponse {
  dataset_id: string;
  vine_type: string;
  marginal_method: string;
  ordered_tickers: string[];
  dimension: number;
  trees: VineEdge[][];
}

export interface VineCopulaSimulateRequest {
  dataset_id: string;
  vine_type?: VineType;
  marginal_method?: MarginalMethod;
  num_simulations?: number;
  random_seed?: number;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface VineCopulaSimulateResponse {
  dataset_id: string;
  vine_type: string;
  num_simulations: number;
  random_seed: number;
  tickers: string[];
  simulated_means: Record<string, number>;
  simulated_volatilities: Record<string, number>;
  sample_correlation_matrix: number[][];
  sample_scenarios: Record<string, number>[];
}

export interface VineTailRiskParityRequest {
  dataset_id: string;
  vine_type?: VineType;
  confidence_level?: number;
  num_simulations?: number;
  random_seed?: number;
  marginal_method?: MarginalMethod;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
}

export interface VineTailRiskParityResponse {
  dataset_id: string;
  vine_type: string;
  confidence_level: number;
  converged: boolean;
  weights: Record<string, number>;
  tail_risk_contributions: Record<string, number>;
  portfolio_var: number;
  portfolio_cvar: number;
  euler_reconciliation_error: number;
  simulated_loss_distribution: number[];
  baselines: {
    equal_weight: BaselinePortfolioRisk;
    inverse_volatility: BaselinePortfolioRisk;
  };
}

// ============================================================================
// Stage 24: Dynamic Walk-Forward Vine Backtesting Types
// ============================================================================

export type VineBacktestFrequency = 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly';
export type ExecutionModel = 'square_root' | 'linear' | 'fixed_bps';
export type ParticipationPolicy = 'warn' | 'cap' | 'reject';
export type ExecutionSchedulingMode = 'single_day' | 'twap' | 'vwap' | 'almgren_chriss';

export interface VineBacktestRequest {
  dataset_id: string;
  vine_type?: VineType;
  estimation_window?: number;
  rebalance_frequency?: VineBacktestFrequency;
  num_simulations?: number;
  confidence_level?: number;
  marginal_method?: MarginalMethod;
  transaction_cost_bps?: number;
  slippage_bps?: number;
  initial_capital?: number;
  risk_free_rate?: number;
  random_seed?: number;
  tickers?: string[];
  start_date?: string;
  end_date?: string;
  execution_model?: ExecutionModel;
  bid_ask_spread_bps?: number;
  max_participation_rate?: number;
  participation_policy?: ParticipationPolicy;
  execution_horizon_days?: number;
  c_temp?: number;
  c_perm?: number;
  default_adv?: number;
  enable_endogenous_liquidity?: boolean;
  spread_stress_sensitivity?: number;
  adv_stress_sensitivity?: number;
  execution_scheduling_mode?: ExecutionSchedulingMode;
  max_scheduling_days?: number;
  scheduling_risk_aversion?: number;
  enable_regime_aware_execution?: boolean;
  regime_num_states?: number;
  regime_adaptation_strength?: number;
  min_participation_rate?: number;
}

export interface VineBacktestStrategyMetrics {
  total_return_gross: number;
  total_return_net: number;
  cagr_net: number;
  cagr_gross?: number;
  annualized_volatility: number;
  annualized_volatility_gross?: number;
  annualized_volatility_net?: number;
  sharpe_ratio: number;
  sharpe_ratio_gross?: number;
  sharpe_ratio_net?: number;
  max_drawdown: number;
  cvar_99: number;
  l_var_99?: number;
  l_cvar_99?: number;
  stressed_l_var_99?: number;
  stressed_l_cvar_99?: number;
  average_cash_weight?: number;
  cumulative_turnover: number;
  total_transaction_costs: number;
  total_spread_costs?: number;
  total_market_impact_costs?: number;
  total_commission_costs?: number;
  max_participation_rate_observed?: number;
  participation_warnings_count?: number;
}

export interface VineBacktestEquityPoint {
  date: string;
  dynamic_vine_trp: number;
  equal_weight: number;
  static_vine_trp: number;
}

export interface VineBacktestRebalanceEvent {
  date: string;
  training_window_start: string;
  training_window_end: string;
  requested_weights?: Record<string, number>;
  executed_weights?: Record<string, number>;
  target_weights: Record<string, number>;
  pre_trade_weights: Record<string, number>;
  turnover: number;
  cost: number;
  spread_cost?: number;
  market_impact_cost?: number;
  commission_cost?: number;
  liquidity_adjusted_cvar?: number;
  liquidity_adjusted_var?: number;
  stressed_liquidity_adjusted_cvar?: number;
  stressed_liquidity_adjusted_var?: number;
  liquidation_cost_pct?: number;
  cash_weight?: number;
  max_participation_rate?: number;
  participation_warning?: boolean;
  rebalance_rejected?: boolean;
  adv_source?: string;
  status: string;
  scheduled_days?: number;
  scheduling_mode?: string;
  regime_state?: number;
  regime_probabilities?: number[];
  effective_participation_rate?: number;
  effective_risk_aversion?: number;
  regime_adaptation_strength?: number;
}

// Stage 30: Transaction Cost Analysis (Stage 30) Types
export interface TCACostMetrics {
  fill_count: number;
  total_requested_notional: number;
  total_executed_notional: number;
  total_unexecuted_notional: number;
  total_cost: number;
  effective_bps: number;
  spread_cost: number;
  spread_bps: number;
  temporary_impact_cost: number;
  temporary_impact_bps: number;
  permanent_impact_cost: number;
  permanent_impact_bps: number;
  market_impact_cost: number;
  market_impact_bps: number;
  commission_cost: number;
  commission_bps: number;
  opportunity_cost: number;
  opportunity_bps: number;
  realized_slippage: number;
  realized_slippage_bps: number;
  unattributed_cost: number;
  fill_rate_pct: number;
  friction_drag_on_capital_pct?: number | null;
}

export interface TCAEventMetrics extends TCACostMetrics {
  date: string;
  regime_state?: number | null;
  scheduling_mode: string;
  scheduled_horizon_days: number;
}

export interface TCAProvenance {
  observed_components: string[];
  modeled_components: string[];
  opportunity_cost_status: string;
  intraday_vwap_status: string;
  currency_basis: string;
  decomposition_type: string;
  permanent_impact_status: string;
  reconciliation_status: string;
}

export interface TCAReport {
  summary: TCACostMetrics;
  by_regime: Record<string, TCACostMetrics>;
  by_mode: Record<string, TCACostMetrics>;
  by_asset: Record<string, TCACostMetrics>;
  by_event: TCAEventMetrics[];
  provenance: TCAProvenance;
}

export interface VineBacktestResponse {
  vine_type: string;
  estimation_window: number;
  rebalance_frequency: string;
  num_simulations: number;
  confidence_level: number;
  transaction_cost_bps: number;
  slippage_bps: number;
  initial_capital: number;
  random_seed: number;
  execution_model?: string;
  bid_ask_spread_bps?: number;
  max_participation_rate?: number;
  participation_policy?: string;
  enable_endogenous_liquidity?: boolean;
  spread_stress_sensitivity?: number;
  adv_stress_sensitivity?: number;
  adv_source?: string;
  execution_scheduling_mode?: string;
  max_scheduling_days?: number;
  scheduling_risk_aversion?: number;
  enable_regime_aware_execution?: boolean;
  regime_num_states?: number;
  regime_adaptation_strength?: number;
  min_participation_rate?: number;
  out_of_sample_period: {
    start_date: string;
    end_date: string;
    trading_days: number;
  };
  rebalance_count: number;
  strategies: {
    dynamic_vine_trp: VineBacktestStrategyMetrics;
    equal_weight: VineBacktestStrategyMetrics;
    static_vine_trp: VineBacktestStrategyMetrics;
    [key: string]: VineBacktestStrategyMetrics;
  };
  equity_curves: VineBacktestEquityPoint[];
  rebalance_events: VineBacktestRebalanceEvent[];
  tca_report?: TCAReport;
}

// ============================================================================
// Stage 33: Combinatorial Cross-Validation, PBO, DSR & Overfitting Diagnostics
// ============================================================================

export type PBORiskLevel = 'low' | 'moderate' | 'high' | 'severe';

export interface OverfittingDiagnosticsRequest {
  experiment_id?: string | null;
  run_ids?: string[] | null;
  n_slices?: number;
  significance_level?: number;
  annualization_factor?: number;
}

export interface DegradationRegression {
  slope: number;
  intercept: number;
  r_squared: number;
  p_value?: number | null;
  std_err?: number | null;
}

export interface CSCVCombinationsPoint {
  combination_id: number;
  selected_run_id: string;
  is_sharpe: number;
  oos_sharpe: number;
  oos_rank: number;
  relative_rank: number;
  is_overfitted: boolean;
}

export interface CSCVHistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
  relative_frequency: number;
}

export interface RunOverfittingSummary {
  run_id: string;
  run_number: number;
  nominal_sharpe: number;
  selection_frequency_is: number;
  mean_oos_sharpe_when_selected?: number | null;
  mean_oos_rank_when_selected?: number | null;
}

export interface OverfittingDiagnosticsResponse {
  experiment_id: string;
  experiment_name: string;
  strategy_type: string;
  dataset_id: string;
  snapshot_id?: string | null;

  // Sample dimensions
  evaluated_runs_count: number;
  aligned_observations_count: number;
  n_slices: number;
  total_combinations_count: number;

  // Overfitting Metrics
  pbo: number;
  pbo_risk_level: PBORiskLevel;

  // Statistical Deflation
  best_run_id: string;
  best_run_number: number;
  best_nominal_sharpe: number;
  expected_max_sharpe: number;
  deflated_sharpe_ratio: number;
  is_statistically_significant: boolean;

  // Track Record & Higher Moments
  min_backtest_length_years?: number | null;
  actual_backtest_length_years: number;
  skewness: number;
  kurtosis: number;

  // Empirical Cross-Validation Analytics
  degradation_regression: DegradationRegression;
  combinations_sample: CSCVCombinationsPoint[];
  rank_distribution: CSCVHistogramBin[];
  runs_summary: RunOverfittingSummary[];

  warnings: string[];
  generated_at: string;
}

export * from './reporting';


