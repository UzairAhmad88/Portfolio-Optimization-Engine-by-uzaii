import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../api/client';

describe('API Client Layer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches health status successfully', async () => {
    const mockHealth = { status: 'ok', stage: 'market-data-foundation' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockHealth,
    } as Response);

    const result = await apiClient.getHealth();
    expect(result).toEqual(mockHealth);
  });

  it('handles structured 422 error details correctly without throwing raw unhandled exceptions', async () => {
    const errorPayload = {
      detail: {
        errors: ['Asset AAPL and MSFT have non-overlapping historical date ranges.'],
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => errorPayload,
    } as Response);

    await expect(
      apiClient.validatePortfolio({
        name: 'Infeasible Portfolio',
        dataset_id: 'test-id',
        assets: ['AAPL', 'MSFT'],
        constraints: {
          default_min_weight: 0,
          default_max_weight: 1,
        },
      })
    ).rejects.toThrow('Asset AAPL and MSFT have non-overlapping historical date ranges.');
  });

  it('handles 415 unsupported media type error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 415,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Upload a .csv file.' }),
    } as Response);

    const dummyFile = new File(['content'], 'test.txt', { type: 'text/plain' });
    await expect(apiClient.previewCsv(dummyFile)).rejects.toThrow('Upload a .csv file.');
  });

  it('performs login and returns bearer token and user identity', async () => {
    const mockAuthResponse = {
      access_token: 'mock-jwt-token-xyz',
      token_type: 'bearer',
      user: {
        id: 'usr-123',
        email: 'quant@firm.com',
        full_name: 'Quant Lead',
        role: 'researcher',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockAuthResponse,
    } as Response);

    const result = await apiClient.login({
      email: 'quant@firm.com',
      password: 'Password123!',
    });

    expect(result.access_token).toBe('mock-jwt-token-xyz');
    expect(result.user.email).toBe('quant@firm.com');
  });

  it('fetches current user profile from /auth/me', async () => {
    const mockUser = {
      id: 'usr-123',
      email: 'quant@firm.com',
      full_name: 'Quant Lead',
      role: 'admin',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockUser,
    } as Response);

    const user = await apiClient.getMe();
    expect(user.role).toBe('admin');
    expect(user.id).toBe('usr-123');
  });

  it('executes backtest and retrieves run results', async () => {
    const mockBacktestResponse = {
      id: 'bt-123',
      dataset_id: 'ds-123',
      name: 'Tech Growth',
      strategy_type: 'walk_forward_optimization',
      rebalance_frequency: 'monthly',
      initial_capital: 1000000.0,
      transaction_cost_bps: 10.0,
      slippage_bps: 5.0,
      status: 'completed',
      created_at: '2026-01-01T00:00:00Z',
      metrics: {
        initial_value: 1000000.0,
        final_value_net: 1250000.0,
        final_value_gross: 1252175.0,
        cumulative_return_net: 0.25,
        cumulative_return_gross: 0.252,
        cagr_net: 0.22,
        cagr_gross: 0.222,
        annualized_return_net: 0.22,
        annualized_return_gross: 0.222,
        volatility_annualized_net: 0.18,
        volatility_annualized_gross: 0.18,
        sharpe_ratio_net: 1.22,
        sharpe_ratio_gross: 1.23,
        sortino_ratio_net: 1.65,
        sortino_ratio_gross: 1.66,
        max_drawdown_net: -0.08,
        max_drawdown_gross: -0.078,
        drawdown_peak_date: '2023-06-01',
        drawdown_trough_date: '2023-07-01',
        total_turnover: 1.45,
        total_transaction_costs: 1450.0,
        total_slippage_costs: 725.0,
        total_friction_costs: 2175.0,
        number_of_rebalances: 12,
        observation_count: 252,
        periods_per_year: 252,
        effective_start_date: '2023-01-01',
        effective_end_date: '2023-12-31',
      },
      equity_curve: [
        {
          date: '2023-01-01',
          portfolio_value_net: 1000000.0,
          portfolio_value_gross: 1000000.0,
          return_net: 0.0,
          return_gross: 0.0,
          drawdown_net: 0.0,
          drawdown_gross: 0.0,
        },
        {
          date: '2023-12-31',
          portfolio_value_net: 1250000.0,
          portfolio_value_gross: 1252175.0,
          return_net: 0.25,
          return_gross: 0.252,
          drawdown_net: 0.0,
          drawdown_gross: 0.0,
        },
      ],
      rebalance_events: [],
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.executeBacktest({
      dataset_id: 'ds-123',
      name: 'Tech Growth',
      strategy_type: 'walk_forward_optimization',
      rebalance_frequency: 'monthly',
      initial_capital: 1000000.0,
      transaction_cost_bps: 10.0,
      slippage_bps: 5.0,
      assets: ['AAPL', 'MSFT'],
    });

    expect(result.id).toBe('bt-123');
    expect(result.metrics.sharpe_ratio_net).toBe(1.22);
  });

  it('executes scenario shock analysis and returns stressed metrics', async () => {
    const mockScenarioResponse = {
      id: 'scen-123',
      name: 'Tech Crash',
      scenario_type: 'custom_asset_shock',
      dataset_id: 'ds-123',
      status: 'completed',
      metrics: {
        baseline_portfolio_value: 1000000.0,
        stressed_portfolio_value: 850000.0,
        absolute_change: -150000.0,
        percentage_change: -0.15,
        currency: 'USD',
        cash_value: 0.0,
        baseline_volatility: 0.18,
        stressed_volatility: 0.22,
        volatility_change: 0.04,
      },
      contributions: [
        {
          asset: 'AAPL:US',
          weight: 0.6,
          baseline_value: 600000.0,
          shock_pct: -0.2,
          stressed_value: 480000.0,
          value_change: -120000.0,
          return_contribution: -0.12,
          share_of_total_change: 0.8,
        },
        {
          asset: 'MSFT:US',
          weight: 0.4,
          baseline_value: 400000.0,
          shock_pct: -0.075,
          stressed_value: 370000.0,
          value_change: -30000.0,
          return_contribution: -0.03,
          share_of_total_change: 0.2,
        },
      ],
      warnings: [],
      is_hypothetical: true,
      disclaimer: 'For institutional research only.',
      created_at: '2026-01-01T00:00:00Z',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockScenarioResponse,
    } as Response);

    const result = await apiClient.executeScenario({
      dataset_id: 'ds-123',
      name: 'Tech Crash',
      scenario_type: 'custom_asset_shock',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      initial_capital: 1000000.0,
      asset_shocks: { 'AAPL:US': -0.2, 'MSFT:US': -0.075 },
    });

    expect(result.id).toBe('scen-123');
    expect(result.metrics.percentage_change).toBe(-0.15);
    expect(result.contributions).toHaveLength(2);
  });

  it('executes sensitivity analysis over bounded shock range', async () => {
    const mockSensitivityResponse = {
      id: 'sens-123',
      dataset_id: 'ds-123',
      name: 'AAPL Sensitivity',
      factor_1_asset: 'AAPL:US',
      grid: [
        {
          factor_1_value: -0.1,
          stressed_portfolio_value: 940000.0,
          percentage_change: -0.06,
          absolute_change: -60000.0,
        },
        {
          factor_1_value: 0.0,
          stressed_portfolio_value: 1000000.0,
          percentage_change: 0.0,
          absolute_change: 0.0,
        },
      ],
      baseline_portfolio_value: 1000000.0,
      currency: 'USD',
      warnings: [],
      is_hypothetical: true,
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockSensitivityResponse,
    } as Response);

    const result = await apiClient.executeSensitivity({
      dataset_id: 'ds-123',
      name: 'AAPL Sensitivity',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      initial_capital: 1000000.0,
      factor_1_asset: 'AAPL:US',
      factor_1_min_shock: -0.1,
      factor_1_max_shock: 0.1,
      factor_1_steps: 2,
    });

    expect(result.factor_1_asset).toBe('AAPL:US');
    expect(result.grid).toHaveLength(2);
    expect(result.grid[0].percentage_change).toBe(-0.06);
  });

  it('executes Monte Carlo risk simulation and returns full distribution metrics', async () => {
    const mockSimulationResponse = {
      id: 'sim-123',
      name: 'Baseline 10k Paths',
      dataset_id: 'ds-123',
      distribution: 'multivariate_normal',
      rebalance_policy: 'buy_and_hold',
      horizon_days: 21,
      num_paths: 1000,
      seed: 42,
      summary: {
        initial_capital: 1000000.0,
        expected_terminal_value: 1015000.0,
        median_terminal_value: 1012000.0,
        expected_terminal_return: 0.015,
        terminal_return_volatility: 0.045,
        prob_negative_return: 0.35,
        min_terminal_value: 880000.0,
        max_terminal_value: 1180000.0,
        var_cvar_metrics: [
          {
            confidence_level: 0.95,
            var_absolute: 45000.0,
            var_percentage: 0.045,
            cvar_absolute: 65000.0,
            cvar_percentage: 0.065,
          },
        ],
        estimator_comparisons: [],
        terminal_quantiles: { '0.05': 955000.0, '0.5': 1012000.0, '0.95': 1075000.0 },
        currency: 'USD',
      },
      distribution_bins: [
        { bin_start: 880000.0, bin_end: 910000.0, count: 20, relative_frequency: 0.02 },
      ],
      trajectory: [
        { day: 0, median_value: 1000000.0, percentile_5: 980000.0, percentile_95: 1020000.0, sample_paths: [1000000.0] },
      ],
      warnings: [],
      is_hypothetical: true,
      disclaimer: 'For institutional research only.',
      created_at: '2026-01-01T00:00:00Z',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockSimulationResponse,
    } as Response);

    const result = await apiClient.executeRiskSimulation({
      dataset_id: 'ds-123',
      name: 'Baseline 10k Paths',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      horizon_days: 21,
      num_paths: 1000,
      confidence_levels: [0.95, 0.99],
      distribution: 'multivariate_normal',
      seed: 42,
    });

    expect(result.id).toBe('sim-123');
    expect(result.summary.expected_terminal_value).toBe(1015000.0);
    expect(result.summary.var_cvar_metrics).toHaveLength(1);
    expect(result.summary.var_cvar_metrics[0].var_absolute).toBe(45000.0);
  });

  it('calculates standalone multi-estimator VaR and CVaR', async () => {
    const mockVarCvarResponse = [
      {
        confidence_level: 0.95,
        monte_carlo_var: 0.045,
        monte_carlo_cvar: 0.065,
        parametric_var: 0.042,
        parametric_cvar: 0.053,
        historical_var: 0.044,
        historical_cvar: 0.058,
      },
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockVarCvarResponse,
    } as Response);

    const result = await apiClient.calculateStandaloneVaRCVaR({
      dataset_id: 'ds-123',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      horizon_days: 21,
      confidence_levels: [0.95],
    });

    expect(result).toHaveLength(1);
    expect(result[0].parametric_var).toBe(0.042);
    expect(result[0].historical_cvar).toBe(0.058);
  });

  it('analyzes comparative performance against benchmark', async () => {
    const mockPerfResponse = {
      id: 'perf-123',
      name: 'Tech vs SPY',
      dataset_id: 'ds-123',
      backtest_id: null,
      benchmark_asset: 'SPY:US',
      risk_free_rate: 0.02,
      start_date: '2023-01-01',
      end_date: '2023-01-10',
      status: 'completed',
      metrics: {
        observation_count: 9,
        periods_per_year: 252,
        start_date: '2023-01-01',
        end_date: '2023-01-10',
        portfolio_cumulative_return: 0.05,
        portfolio_annualized_return: 0.12,
        portfolio_annualized_volatility: 0.15,
        portfolio_sharpe_ratio: 0.67,
        portfolio_sortino_ratio: 0.85,
        portfolio_max_drawdown: -0.04,
        benchmark_cumulative_return: 0.03,
        benchmark_annualized_return: 0.08,
        benchmark_annualized_volatility: 0.12,
        benchmark_sharpe_ratio: 0.50,
        benchmark_sortino_ratio: 0.60,
        benchmark_max_drawdown: -0.03,
        arithmetic_active_return: 0.02,
        geometric_excess_return: 0.0194,
        annualized_active_return: 0.04,
        tracking_error: 0.05,
        information_ratio: 0.80,
        beta: 1.10,
        alpha_annualized: 0.032,
        treynor_ratio: 0.09,
        up_capture_ratio: 1.15,
        down_capture_ratio: 0.95,
      },
      contributions: [
        {
          asset: 'AAPL:US',
          weight: 0.6,
          cumulative_return: 0.06,
          total_contribution: 0.035,
          share_of_return: 0.70,
        },
        {
          asset: 'MSFT:US',
          weight: 0.4,
          cumulative_return: 0.0375,
          total_contribution: 0.015,
          share_of_return: 0.30,
        },
      ],
      timeseries: [
        {
          date: '2023-01-02',
          portfolio_return: 0.01,
          benchmark_return: 0.005,
          active_return: 0.005,
          portfolio_cumulative: 0.01,
          benchmark_cumulative: 0.005,
          active_cumulative: 0.005,
          drawdown_portfolio: 0.0,
          drawdown_benchmark: 0.0,
        },
      ],
      warnings: [],
      is_hypothetical: true,
      disclaimer: 'Research diagnostic only.',
      created_at: '2026-10-18T00:00:00Z',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockPerfResponse,
    } as Response);

    const result = await apiClient.analyzePerformance({
      dataset_id: 'ds-123',
      name: 'Tech vs SPY',
      benchmark_asset: 'SPY:US',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
    });

    expect(result.id).toBe('perf-123');
    expect(result.metrics.arithmetic_active_return).toBe(0.02);
    expect(result.metrics.information_ratio).toBe(0.80);
    expect(result.metrics.beta).toBe(1.10);
    expect(result.contributions).toHaveLength(2);
  });

  it('lists saved performance reports', async () => {
    const mockReports = [
      {
        id: 'perf-1',
        name: 'Report 1',
        dataset_id: 'ds-123',
        backtest_id: null,
        benchmark_asset: 'SPY:US',
        portfolio_cumulative_return: 0.05,
        benchmark_cumulative_return: 0.03,
        arithmetic_active_return: 0.02,
        information_ratio: 0.8,
        beta: 1.1,
        alpha_annualized: 0.03,
        status: 'completed',
        created_at: '2026-10-18T00:00:00Z',
      },
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockReports,
    } as Response);

    const result = await apiClient.listPerformanceReports();
    expect(result).toHaveLength(1);
    expect(result[0].benchmark_asset).toBe('SPY:US');
  });

  it('creates research experiment definition successfully', async () => {
    const mockExp = {
      id: 'exp-123',
      name: 'Alpha Strategy Hypothesis',
      strategy_type: 'equal_weight',
      dataset_id: 'ds-123',
      version: 1,
      config_fingerprint: 'a'.repeat(64),
      created_at: '2026-10-18T00:00:00Z',
      updated_at: '2026-10-18T00:00:00Z',
      config: { assets: ['AAPL:US', 'MSFT:US'] },
      total_runs_count: 0,
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockExp,
    } as Response);

    const result = await apiClient.createExperiment({
      name: 'Alpha Strategy Hypothesis',
      strategy_type: 'equal_weight',
      dataset_id: 'ds-123',
      config: { assets: ['AAPL:US', 'MSFT:US'] },
    });

    expect(result.id).toBe('exp-123');
    expect(result.strategy_type).toBe('equal_weight');
    expect(result.version).toBe(1);
  });

  it('lists research experiments', async () => {
    const mockList = [
      {
        id: 'exp-1',
        name: 'Exp 1',
        strategy_type: 'target_weights',
        dataset_id: 'ds-1',
        version: 1,
        config_fingerprint: 'b'.repeat(64),
        total_runs_count: 2,
        created_at: '2026-10-18T00:00:00Z',
        updated_at: '2026-10-18T00:00:00Z',
      },
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockList,
    } as Response);

    const result = await apiClient.listExperiments();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Exp 1');
  });

  it('executes cross-strategy comparison', async () => {
    const mockComp = {
      runs: [
        {
          run_id: 'run-1',
          experiment_id: 'exp-1',
          experiment_name: 'Exp 1',
          strategy_type: 'equal_weight',
          run_number: 1,
          status: 'succeeded',
          dataset_id: 'ds-1',
          dataset_version_hash: 'c'.repeat(64),
          config_fingerprint: 'd'.repeat(64),
          currency: 'USD',
          is_reproducible: true,
          execution_date: '2026-10-18 00:00:00',
          metrics: { cumulative_return: 0.12, sharpe_ratio: 1.5 },
          config_summary: { rebalance_frequency: 'monthly' },
        },
      ],
      common_currency: 'USD',
      has_period_divergence: false,
      has_provenance_divergence: false,
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockComp,
    } as Response);

    const result = await apiClient.compareExperimentRuns({ run_ids: ['run-1', 'run-2'] });
    expect(result.common_currency).toBe('USD');
    expect(result.runs).toHaveLength(1);
    expect(result.runs[0].metrics.sharpe_ratio).toBe(1.5);
  });

  it('calls optimizeRobustPortfolio with correct payload and returns response', async () => {
    const mockResponse = {
      objective: 'max_sharpe',
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      weights: [
        {
          asset_id: 'AAPL',
          baseline_weight: 0.5,
          robust_weight: 0.45,
          weight_difference: -0.05,
          nominal_return: 0.12,
          worst_case_return: 0.09,
          uncertainty_radius: 0.03,
        },
        {
          asset_id: 'MSFT',
          baseline_weight: 0.5,
          robust_weight: 0.55,
          weight_difference: 0.05,
          nominal_return: 0.14,
          worst_case_return: 0.11,
          uncertainty_radius: 0.03,
        },
      ],
      baseline_weights: { AAPL: 0.5, MSFT: 0.5 },
      robust_weights: { AAPL: 0.45, MSFT: 0.55 },
      baseline_metrics: {
        nominal_return: 0.12,
        worst_case_return: 0.12,
        volatility: 0.15,
        sharpe_ratio: 0.67,
      },
      robust_metrics: {
        nominal_return: 0.115,
        worst_case_return: 0.085,
        volatility: 0.145,
        sharpe_ratio: 0.655,
      },
      diagnostics: {
        weight_distance_d1: 0.1,
        max_weight_shift: 0.05,
        max_weight_shift_asset: 'AAPL',
        baseline_n_eff: 2.0,
        robust_n_eff: 1.98,
        baseline_hhi: 0.5,
        robust_hhi: 0.505,
      },
      shrunk_covariance: [[0.04, 0.01], [0.01, 0.04]],
      is_feasible: true,
      solver_status: 'converged',
      solver_message: 'Optimization terminated successfully',
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockResponse,
    } as Response);

    const result = await apiClient.optimizeRobustPortfolio({
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      objective: 'max_sharpe',
      uncertainty: { model: 'box', confidence_level: 1.96 },
      shrinkage: { target: 'diagonal', intensity: 0.2 },
      constraints: {
        default_min_weight: 0.0,
        default_max_weight: 1.0,
        target_total_weight: 1.0,
        allow_short: false,
      },
      risk_free_rate: 0.02,
      risk_aversion: 2.5,
    });

    expect(result.objective).toBe('max_sharpe');
    expect(result.diagnostics.weight_distance_d1).toBe(0.1);
    expect(result.robust_weights.MSFT).toBe(0.55);
  });

  it('calls runRobustSensitivity with sweep parameters', async () => {
    const mockSweep = {
      parameter_name: 'uncertainty_level',
      parameter_description: 'Uncertainty level multiplier',
      baseline_value: 1.0,
      points: [
        {
          parameter_value: 0.0,
          parameter_label: '0.00',
          is_feasible: true,
          solver_status: 'converged',
          weights: { AAPL: 0.5, MSFT: 0.5 },
          nominal_expected_return: 0.12,
          worst_case_expected_return: 0.12,
          volatility: 0.15,
          sharpe_ratio: 0.67,
          weight_distance_d1: 0.0,
          hhi: 0.5,
          effective_assets: 2.0,
          binding_constraints: [],
        },
      ],
      total_evaluations: 1,
      feasible_evaluations: 1,
      infeasible_evaluations: 0,
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockSweep,
    } as Response);

    const result = await apiClient.runRobustSensitivity({
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      objective: 'max_sharpe',
      parameter_to_sweep: 'uncertainty_level',
      grid_min: 0.0,
      grid_max: 2.0,
      num_steps: 5,
      uncertainty: { model: 'box', confidence_level: 1.0 },
      shrinkage: { target: 'diagonal', intensity: 0.2 },
      constraints: {
        default_min_weight: 0.0,
        default_max_weight: 1.0,
        target_total_weight: 1.0,
        allow_short: false,
      },
      risk_free_rate: 0.02,
    });

    expect(result.parameter_name).toBe('uncertainty_level');
    expect(result.points).toHaveLength(1);
    expect(result.points[0].is_feasible).toBe(true);
  });

  it('executes Black-Litterman optimization successfully', async () => {
    const mockBlResponse = {
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      equilibrium_returns: { AAPL: 0.05, MSFT: 0.08 },
      posterior_returns: { AAPL: 0.07, MSFT: 0.06 },
      prior_weights: { AAPL: 0.5, MSFT: 0.5 },
      unconstrained_bl_weights: { AAPL: 0.7, MSFT: 0.3 },
      optimal_weights: { AAPL: 0.65, MSFT: 0.35 },
      active_tilts: { AAPL: 0.15, MSFT: -0.15 },
      portfolio_metrics: { expected_return: 0.066, volatility: 0.12, sharpe_ratio: 0.55 },
      diagnostics: {
        weight_distance_d1: 0.3,
        max_tilt_asset: 'AAPL',
        max_tilt_value: 0.15,
        hhi_prior: 0.5,
        hhi_optimal: 0.545,
        effective_assets_prior: 2.0,
        effective_assets_optimal: 1.83,
      },
      views_summary: [
        {
          description: 'AAPL outperforms MSFT by 3%',
          view_type: 'relative',
          confidence: 0.7,
          target_return: 0.03,
          prior_expected_spread: -0.03,
          posterior_expected_spread: 0.01,
          absorbed_difference: 0.04,
        },
      ],
      is_feasible: true,
      solver_status: 'converged',
      solver_message: 'Optimization terminated successfully',
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBlResponse,
    } as Response);

    const result = await apiClient.optimizeBlackLitterman({
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      tau: 0.05,
      risk_aversion: 2.5,
      views: [
        {
          view_type: 'relative',
          assets: ['AAPL', 'MSFT'],
          weights: [1.0, -1.0],
          target_return: 0.03,
          confidence: 0.7,
        },
      ],
      objective: 'max_sharpe',
    });

    expect(result.is_feasible).toBe(true);
    expect(result.active_tilts.AAPL).toBe(0.15);
    expect(result.diagnostics.weight_distance_d1).toBe(0.3);
    expect(result.views_summary).toHaveLength(1);
  });

  it('executes Black-Litterman chronological backtest successfully', async () => {
    const mockBacktestResponse = {
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      train_period: { start: '2023-01-01', end: '2023-06-30' },
      test_period: { start: '2023-07-01', end: '2023-12-31' },
      equilibrium_weights: { AAPL: 0.5, MSFT: 0.5 },
      optimal_weights: { AAPL: 0.65, MSFT: 0.35 },
      active_tilts: { AAPL: 0.15, MSFT: -0.15 },
      equilibrium_kpis: {
        cumulative_return: 0.08,
        annualized_return: 0.16,
        annualized_volatility: 0.14,
        sharpe_ratio: 1.0,
        max_drawdown: -0.05,
        total_turnover: 0.0,
        total_friction_costs: 0.0,
        final_value: 108000,
      },
      black_litterman_kpis: {
        cumulative_return: 0.11,
        annualized_return: 0.22,
        annualized_volatility: 0.15,
        sharpe_ratio: 1.33,
        max_drawdown: -0.04,
        total_turnover: 0.15,
        total_friction_costs: 15.0,
        final_value: 111000,
      },
      equity_curves: [
        {
          date: '2023-07-01',
          equilibrium_portfolio_value: 100000,
          black_litterman_portfolio_value: 100000,
          equilibrium_drawdown: 0.0,
          black_litterman_drawdown: 0.0,
        },
      ],
      warnings: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.backtestBlackLitterman({
      dataset_id: 'ds-1',
      assets: ['AAPL', 'MSFT'],
      train_end_date: '2023-06-30',
      views: [],
    });

    expect(result.dataset_id).toBe('ds-1');
    expect(result.black_litterman_kpis.sharpe_ratio).toBe(1.33);
    expect(result.equity_curves).toHaveLength(1);
  });

  it('optimizes risk parity portfolio (ERC / HRP) via API client', async () => {
    const mockOptResponse = {
      dataset_id: 'ds-1',
      method: 'erc',
      linkage_method: 'single',
      assets: ['AAPL', 'MSFT'],
      weights: { AAPL: 0.6, MSFT: 0.4 },
      marginal_risk_contributions: { AAPL: 0.12, MSFT: 0.18 },
      total_risk_contributions: { AAPL: 0.072, MSFT: 0.072 },
      percentage_risk_contributions: { AAPL: 0.5, MSFT: 0.5 },
      target_risk_budgets: { AAPL: 0.5, MSFT: 0.5 },
      portfolio_volatility: 0.144,
      diagnostics: {
        risk_gini: 0.0,
        effective_bets: 2.0,
        diversification_ratio: 1.25,
      },
      reordered_indices: null,
      is_feasible: true,
      solver_status: 'Optimal',
      solver_message: 'Convergence achieved',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockOptResponse,
    } as Response);

    const result = await apiClient.optimizeRiskParity({
      dataset_id: 'ds-1',
      method: 'erc',
    });

    expect(result.dataset_id).toBe('ds-1');
    expect(result.method).toBe('erc');
    expect(result.weights['AAPL']).toBe(0.6);
    expect(result.percentage_risk_contributions['AAPL']).toBe(0.5);
    expect(result.diagnostics.effective_bets).toBe(2.0);
    expect(result.is_feasible).toBe(true);
  });

  it('executes out-of-sample risk parity backtest via API client', async () => {
    const mockBacktestResponse = {
      dataset_id: 'ds-1',
      method: 'hrp',
      split_date: '2023-06-30',
      in_sample_end: '2023-06-30',
      out_of_sample_start: '2023-07-01',
      out_of_sample_end: '2023-12-31',
      strategy_metrics: {
        annualized_return: 0.15,
        annualized_volatility: 0.11,
        sharpe_ratio: 1.18,
        sortino_ratio: 1.65,
        max_drawdown: -0.06,
        calmar_ratio: 2.5,
        total_net_return: 0.075,
        total_transaction_costs: 20.0,
        total_slippage_costs: 10.0,
        rebalance_count: 6,
      },
      equal_weight_benchmark_metrics: {
        annualized_return: 0.13,
        annualized_volatility: 0.14,
        sharpe_ratio: 0.78,
        sortino_ratio: 1.1,
        max_drawdown: -0.09,
        calmar_ratio: 1.44,
        total_net_return: 0.065,
        total_transaction_costs: 20.0,
        total_slippage_costs: 10.0,
        rebalance_count: 6,
      },
      strategy_weights: { AAPL: 0.55, MSFT: 0.45 },
      equity_curve: [
        { date: '2023-07-01', strategy: 100000, benchmark: 100000 },
        { date: '2023-12-31', strategy: 107500, benchmark: 106500 },
      ],
      drawdown_curve: [
        { date: '2023-07-01', strategy: 0.0, benchmark: 0.0 },
        { date: '2023-12-31', strategy: -1.5, benchmark: -3.2 },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.backtestRiskParity({
      dataset_id: 'ds-1',
      method: 'hrp',
      split_date: '2023-06-30',
    });

    expect(result.dataset_id).toBe('ds-1');
    expect(result.method).toBe('hrp');
    expect(result.strategy_metrics.sharpe_ratio).toBe(1.18);
    expect(result.equity_curve).toHaveLength(2);
  });

  it('performs factor attribution and parses systematic risk decomposition', async () => {
    const mockAttributionResponse = {
      dataset_id: 'ds-factor-1',
      factor_model: 'carhart4',
      factors: ['MKT', 'SMB', 'HML', 'MOM'],
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.5, 'MSFT:US': 0.5 },
      asset_profiles: {
        'AAPL:US': {
          alpha_annualized: 0.05,
          alpha_stderr: 0.02,
          alpha_tstat: 2.5,
          alpha_pvalue: 0.012,
          betas: {
            MKT: { beta: 1.15, stderr: 0.05, tstat: 23.0, pvalue: 0.0001 },
          },
          r_squared: 0.75,
          r_squared_adj: 0.73,
          specific_variance_annualized: 0.015,
          specific_volatility_annualized: 0.1225,
        },
      },
      asset_loadings: {},
      portfolio_betas: { MKT: 1.05 },
      risk_decomposition: {
        total_volatility: 0.18,
        systematic_volatility: 0.15,
        idiosyncratic_volatility: 0.099,
        systematic_variance: 0.0225,
        idiosyncratic_variance: 0.0099,
        total_variance: 0.0324,
        systematic_share_pct: 69.4,
        idiosyncratic_share_pct: 30.6,
        systematic_variance_pct: 69.4,
        specific_variance_pct: 30.6,
        portfolio_volatility_pct: 18.0,
        portfolio_betas: { MKT: 1.05 },
        factor_contributions: {
          MKT: {
            exposure: 1.05,
            marginal_contrib: 0.02,
            total_variance_contrib: 0.021,
            pct_of_systematic_risk: 93.3,
          },
        },
      },
      factor_covariance: [[0.04]],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockAttributionResponse,
    } as Response);

    const result = await apiClient.attributeFactorRisk({
      dataset_id: 'ds-factor-1',
      factor_model: 'carhart4',
    });

    expect(result.dataset_id).toBe('ds-factor-1');
    expect(result.factor_model).toBe('carhart4');
    expect(result.factors).toEqual(['MKT', 'SMB', 'HML', 'MOM']);
    expect(result.risk_decomposition.systematic_share_pct).toBe(69.4);
  });

  it('solves factor-constrained optimization and validates target beta bounds', async () => {
    const mockOptimizeResponse = {
      dataset_id: 'ds-factor-1',
      factor_model: 'carhart4',
      objective: 'min_variance',
      assets: ['AAPL:US', 'MSFT:US'],
      weights: { 'AAPL:US': 0.45, 'MSFT:US': 0.55 },
      portfolio_betas: { MKT: 0.95 },
      realized_factor_betas: { MKT: 0.95 },
      risk_decomposition: {
        total_volatility: 0.16,
        systematic_volatility: 0.14,
        idiosyncratic_volatility: 0.077,
        systematic_variance: 0.0196,
        idiosyncratic_variance: 0.006,
        total_variance: 0.0256,
        systematic_share_pct: 76.5,
        idiosyncratic_share_pct: 23.5,
        systematic_variance_pct: 76.5,
        specific_variance_pct: 23.5,
        portfolio_volatility_pct: 16.0,
        portfolio_betas: { MKT: 0.95 },
        factor_contributions: {},
      },
      is_success: true,
      is_feasible: true,
      solver_status: 'Optimal',
      solver_message: 'Converged successfully.',
      diagnostics: { converged: true },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockOptimizeResponse,
    } as Response);

    const result = await apiClient.optimizeFactorConstrained({
      dataset_id: 'ds-factor-1',
      factor_model: 'carhart4',
      factor_constraints: {
        MKT: { min_beta: 0.8, max_beta: 1.0 },
      },
    });

    expect(result.is_feasible).toBe(true);
    expect(result.weights['AAPL:US']).toBe(0.45);
    expect(result.portfolio_betas.MKT).toBe(0.95);
  });

  it('executes dynamic factor walk-forward backtest successfully', async () => {
    const mockBacktestResponse = {
      dataset_id: 'ds-dyn-1',
      strategy_type: 'factor_tilt',
      factor_model: 'carhart4',
      estimation_window: 60,
      rebalance_frequency: 'monthly',
      total_rebalances: 4,
      summary_metrics: {
        total_return: 0.22,
        cagr: 0.22,
        annualized_volatility: 0.15,
        sharpe_ratio: 1.33,
        sortino_ratio: 1.85,
        max_drawdown: -0.07,
        calmar_ratio: 3.14,
        active_return: 0.05,
        tracking_error: 0.04,
        information_ratio: 1.25,
        average_turnover: 0.12,
        total_transaction_costs: 180.5,
      },
      benchmark_metrics: {
        total_return: 0.17,
        cagr: 0.17,
        annualized_volatility: 0.14,
        sharpe_ratio: 1.07,
        max_drawdown: -0.09,
      },
      equity_curve: [
        { date: '2023-01-03', strategy_equity: 100000, benchmark_equity: 100000, drawdown: 0 },
        { date: '2023-04-03', strategy_equity: 122000, benchmark_equity: 117000, drawdown: -0.02 },
      ],
      rebalance_history: [
        {
          date: '2023-01-03',
          weights: { AAPL: 0.5, MSFT: 0.5 },
          portfolio_betas: { MKT: 1.05, MOM: 0.35 },
          systematic_volatility: 0.13,
          idiosyncratic_volatility: 0.06,
          systematic_share_pct: 82.4,
          turnover: 0.15,
          cost_incurred: 25.0,
          is_feasible: true,
          solver_message: 'Optimization converged.',
        },
      ],
      factor_exposure_series: {
        dates: ['2023-01-03'],
        exposures: { MKT: [1.05], MOM: [0.35] },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.backtestDynamicFactors({
      dataset_id: 'ds-dyn-1',
      factor_model: 'carhart4',
      strategy_type: 'factor_tilt',
      estimation_window: 60,
      rebalance_frequency: 'monthly',
      factor_tilts: { MKT: 1.0, MOM: 0.5 },
    });

    expect(result.strategy_type).toBe('factor_tilt');
    expect(result.total_rebalances).toBe(4);
    expect(result.summary_metrics.sharpe_ratio).toBe(1.33);
    expect(result.rebalance_history[0].portfolio_betas.MKT).toBe(1.05);
  });

  it('posts multi-asset optimization request and parses response', async () => {
    const mockOptimizeResponse = {
      risky_weights: { SPY: 0.5, BND: 0.35 },
      cash_weight: 0.15,
      asset_class_allocations: { Equity: 0.5, 'Fixed Income': 0.35, Cash: 0.15 },
      expected_annual_return: 0.085,
      annual_volatility: 0.112,
      sharpe_ratio: 0.491,
      fx_risk_decomposition: {
        asset_local_variance: 0.0125,
        fx_currency_variance: 0.0,
        cross_covariance: 0.0,
        total_unhedged_variance: 0.0125,
        asset_risk_share_pct: 100.0,
        fx_risk_share_pct: 0.0,
        unhedged_volatility: 0.1118,
        local_asset_volatility: 0.1118,
      },
      is_feasible: true,
      solver_message: 'Optimization converged.',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockOptimizeResponse,
    } as Response);

    const result = await apiClient.optimizeMultiAsset({
      dataset_id: 'ds-multi-1',
      base_currency: 'USD',
      min_cash_weight: 0.10,
      max_cash_weight: 0.20,
    });

    expect(result.is_feasible).toBe(true);
    expect(result.cash_weight).toBe(0.15);
    expect(result.asset_class_allocations.Equity).toBe(0.5);
    expect(result.fx_risk_decomposition.asset_risk_share_pct).toBe(100.0);
  });

  it('posts multi-asset backtest request and parses walk-forward response', async () => {
    const mockBacktestResponse = {
      summary: {
        initial_capital: 100000,
        final_equity: 112500,
        total_return: 0.125,
        cagr: 0.082,
        annualized_volatility: 0.095,
        sharpe_ratio: 0.863,
        sortino_ratio: 1.15,
        max_drawdown: -0.065,
        calmar_ratio: 1.26,
        total_turnover: 0.45,
        total_transaction_costs: 67.5,
        total_rebalances: 3,
        active_return: 0.025,
        tracking_error: 0.038,
        information_ratio: 0.658,
        total_cash_drag: 0.0072,
      },
      benchmark: {
        final_equity: 109500,
        total_return: 0.095,
        cagr: 0.062,
        annualized_volatility: 0.115,
        sharpe_ratio: 0.539,
      },
      fx_risk_decomposition: {
        asset_local_variance: 0.009,
        fx_currency_variance: 0.001,
        cross_covariance: 0.0002,
        total_unhedged_variance: 0.0102,
        asset_risk_share_pct: 88.2,
        fx_risk_share_pct: 11.8,
        unhedged_volatility: 0.101,
        local_asset_volatility: 0.095,
      },
      equity_curve: [
        {
          date: '2023-01-03',
          portfolio_equity: 100000,
          benchmark_equity: 100000,
          portfolio_return: 0.0,
          benchmark_return: 0.0,
          drawdown: 0.0,
          cash_drag: 0.0,
        },
      ],
      rebalance_history: [
        {
          date: '2023-01-03',
          risky_weights: { SPY: 0.5, BND: 0.4 },
          cash_weight: 0.1,
          asset_class_allocations: { Equity: 0.5, 'Fixed Income': 0.4, Cash: 0.1 },
          turnover: 0.25,
          cost_incurred: 37.5,
          is_feasible: true,
          solver_message: 'Optimization converged.',
        },
      ],
      asset_class_allocation_history: [
        { date: '2023-01-03', Equity: 0.5, 'Fixed Income': 0.4, Cash: 0.1 },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.backtestMultiAsset({
      dataset_id: 'ds-multi-1',
      base_currency: 'USD',
      rebalance_frequency: 'monthly',
      estimation_window: 40,
    });

    expect(result.summary.total_rebalances).toBe(3);
    expect(result.summary.total_cash_drag).toBe(0.0072);
    expect(result.rebalance_history[0].cash_weight).toBe(0.1);
  });

  it('computes Almgren-Chriss optimal execution schedule via API client', async () => {
    const mockExecutionResponse = {
      parameters: {
        order_size: 100000,
        asset_price: 50.0,
        order_value: 5000000,
        daily_volume: 1000000,
        daily_volatility: 1.0,
        bid_ask_spread: 0.02,
        horizon_periods: 5,
        trading_hours: 6.5,
        risk_aversion: 1e-6,
        temporary_impact_eta: 0.000005,
        permanent_impact_gamma: 0.000001,
      },
      summary: {
        urgency_parameter: 1.414,
        half_life_hours: 3.25,
        expected_cost: 15000.0,
        expected_cost_bps: 30.0,
        timing_risk_variance: 50000000,
        timing_risk_std: 7071.0,
        execution_utility: 15050.0,
        twap_expected_cost: 14000.0,
        twap_expected_cost_bps: 28.0,
        twap_timing_risk_std: 8500.0,
        twap_utility: 15500.0,
        vwap_expected_cost: 14500.0,
        vwap_expected_cost_bps: 29.0,
        cost_savings_vs_twap: 450.0,
        cost_savings_vs_twap_bps: 0.9,
      },
      schedule: [
        {
          period: 1,
          time_elapsed_hours: 1.3,
          time_elapsed_pct: 0.2,
          almgren_chriss_shares: 30000,
          almgren_chriss_remaining: 70000,
          twap_shares: 20000,
          twap_remaining: 80000,
          vwap_shares: 25000,
          vwap_remaining: 75000,
          volume_weight_pct: 25.0,
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockExecutionResponse,
    } as Response);

    const result = await apiClient.getOptimalExecutionSchedule({
      order_size: 100000,
      asset_price: 50.0,
      daily_volume: 1000000,
      daily_volatility: 1.0,
      horizon_periods: 5,
    });

    expect(result.summary.urgency_parameter).toBe(1.414);
    expect(result.summary.expected_cost).toBe(15000.0);
    expect(result.schedule).toHaveLength(1);
    expect(result.schedule[0].almgren_chriss_shares).toBe(30000);
  });

  it('evaluates portfolio rebalance market impact via API client', async () => {
    const mockImpactResponse = {
      summary: {
        impact_model: 'square_root',
        execution_horizon_days: 1.0,
        total_traded_notional: 1000000.0,
        total_spread_cost: 250.0,
        total_temporary_impact_cost: 1200.0,
        total_permanent_impact_cost: 300.0,
        total_impact_cost: 1750.0,
        effective_cost_bps: 17.5,
      },
      asset_impacts: [
        {
          ticker: 'AAPL',
          traded_notional: 600000.0,
          adv: 5000000.0,
          participation_rate_pct: 12.0,
          spread_cost: 150.0,
          temporary_impact_cost: 720.0,
          permanent_impact_cost: 180.0,
          total_cost: 1050.0,
          total_cost_bps: 17.5,
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockImpactResponse,
    } as Response);

    const result = await apiClient.evaluateRebalanceImpact({
      dataset_id: 'ds-impact-1',
      target_weights: { AAPL: 0.6 },
      portfolio_equity: 1000000.0,
      impact_model: 'square_root',
    });

    expect(result.summary.impact_model).toBe('square_root');
    expect(result.summary.total_impact_cost).toBe(1750.0);
    expect(result.summary.effective_cost_bps).toBe(17.5);
    expect(result.asset_impacts).toHaveLength(1);
    expect(result.asset_impacts[0].ticker).toBe('AAPL');
  });

  it('detects market regimes via Gaussian HMM and returns transition matrix', async () => {
    const mockDetectResponse = {
      dataset_id: 'ds-regime-1',
      num_states: 2,
      state_labels: ['Low Volatility (Bull)', 'High Volatility (Turbulent)'],
      transition_matrix: [
        [0.92, 0.08],
        [0.15, 0.85],
      ],
      state_means: [0.0008, -0.0015],
      state_volatilities_annual: [0.12, 0.28],
      current_state: 0,
      current_state_label: 'Low Volatility (Bull)',
      current_regime_probabilities: [0.88, 0.12],
      timeline: [
        {
          date: '2024-01-02',
          return_val: 0.005,
          state: 0,
          state_label: 'Low Volatility (Bull)',
          filtered_prob: [0.88, 0.12],
          smoothed_prob: [0.91, 0.09],
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockDetectResponse,
    } as Response);

    const result = await apiClient.detectRegimes({
      dataset_id: 'ds-regime-1',
      num_states: 2,
    });

    expect(result.num_states).toBe(2);
    expect(result.current_state).toBe(0);
    expect(result.state_labels[0]).toBe('Low Volatility (Bull)');
    expect(result.transition_matrix[0][0]).toBe(0.92);
    expect(result.timeline).toHaveLength(1);
  });

  it('executes walk-forward backtest with volatility targeting', async () => {
    const mockBacktestResponse = {
      dataset_id: 'ds-regime-1',
      summary: {
        initial_equity: 100000.0,
        final_equity: 124500.0,
        cagr: 0.142,
        annualized_volatility: 0.098,
        sharpe_ratio: 1.04,
        sortino_ratio: 1.48,
        max_drawdown: -0.085,
        calmar_ratio: 1.67,
        benchmark_cagr: 0.095,
        benchmark_volatility: 0.165,
        benchmark_sharpe: 0.58,
        target_volatility: 0.10,
        max_leverage: 1.5,
        total_rebalances: 12,
      },
      equity_curve: [
        {
          date: '2024-01-02',
          portfolio_equity: 100000.0,
          benchmark_equity: 100000.0,
          cash_weight: 0.25,
          leverage: 0.75,
          regime_state: 0,
        },
      ],
      rebalance_events: [
        {
          date: '2024-01-02',
          regime_state: 0,
          regime_probs: [0.85, 0.15],
          scaling_factor: 0.75,
          cash_weight: 0.25,
          turnover: 0.15,
          fee_deducted: 15.0,
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBacktestResponse,
    } as Response);

    const result = await apiClient.backtestRegimes({
      dataset_id: 'ds-regime-1',
      target_volatility: 0.10,
      max_leverage: 1.5,
    });

    expect(result.summary.cagr).toBe(0.142);
    expect(result.summary.target_volatility).toBe(0.10);
    expect(result.equity_curve).toHaveLength(1);
    expect(result.rebalance_events[0].scaling_factor).toBe(0.75);
  });

  it('computes multi-period Brinson-Fachler attribution with Carino linking', async () => {
    const mockBrinsonResponse = {
      dataset_id: 'ds-attrib-1',
      method: 'brinson_fachler',
      frequency: 'monthly',
      summary: {
        cumulative_portfolio_return: 0.15,
        cumulative_benchmark_return: 0.10,
        cumulative_active_return: 0.05,
        total_allocation_effect: 0.03,
        total_selection_effect: 0.02,
        total_interaction_effect: 0.00,
        reconciliation_error: 0.0,
        total_periods: 3,
      },
      segment_attribution: [
        {
          segment: 'Information Technology',
          average_portfolio_weight: 0.60,
          average_benchmark_weight: 0.40,
          active_weight: 0.20,
          linked_allocation_effect: 0.025,
          linked_selection_effect: 0.015,
          linked_interaction_effect: 0.0,
          total_contribution: 0.040,
        },
      ],
      time_series: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockBrinsonResponse,
    } as Response);

    const result = await apiClient.computeBrinsonAttribution({
      dataset_id: 'ds-attrib-1',
      portfolio_weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      benchmark_weights: { 'AAPL:US': 0.5, 'MSFT:US': 0.5 },
      method: 'brinson_fachler',
      frequency: 'monthly',
    });

    expect(result.summary.cumulative_active_return).toBe(0.05);
    expect(result.summary.total_allocation_effect).toBe(0.03);
    expect(result.segment_attribution[0].segment).toBe('Information Technology');
  });

  it('computes systematic factor risk and return attribution', async () => {
    const mockFactorResponse = {
      dataset_id: 'ds-factor-1',
      factor_model: 'fama_french_3',
      annualized_portfolio_return: 0.18,
      annualized_benchmark_return: 0.12,
      total_active_return: 0.06,
      systematic_active_return: 0.04,
      specific_active_return: 0.02,
      total_tracking_error: 0.05,
      systematic_tracking_error: 0.035,
      specific_tracking_error: 0.035,
      systematic_risk_percent: 50.0,
      specific_risk_percent: 50.0,
      factor_contributions: [
        {
          factor: 'MKT',
          portfolio_beta: 1.1,
          benchmark_beta: 1.0,
          active_beta: 0.1,
          annualized_factor_return: 0.08,
          annualized_contribution: 0.008,
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockFactorResponse,
    } as Response);

    const result = await apiClient.computeSystematicFactorAttribution({
      dataset_id: 'ds-factor-1',
      portfolio_weights: { 'AAPL:US': 0.6, 'MSFT:US': 0.4 },
      benchmark_weights: { 'AAPL:US': 0.5, 'MSFT:US': 0.5 },
    });

    expect(result.total_active_return).toBe(0.06);
    expect(result.systematic_active_return).toBe(0.04);
    expect(result.factor_contributions[0].factor).toBe('MKT');
  });

  it('fits copula models and parses tail dependence matrix', async () => {
    const mockCopulaFitResponse = {
      dataset_id: 'ds-copula-1',
      copula_type: 'best_fit',
      marginal_method: 'empirical',
      tickers: ['AAPL', 'MSFT'],
      tail_dependence_matrix: [
        [1.0, 0.45],
        [0.45, 1.0],
      ],
      kendall_tau_matrix: [
        [1.0, 0.38],
        [0.38, 1.0],
      ],
      pearson_corr_matrix: [
        [1.0, 0.52],
        [0.52, 1.0],
      ],
      pairwise_results: [
        {
          asset_1: 'AAPL',
          asset_2: 'MSFT',
          copula_type: 'clayton',
          theta: 1.85,
          kendall_tau: 0.38,
          pearson_corr: 0.52,
          lower_tail_dependence: 0.45,
          upper_tail_dependence: 0.0,
          aic: -120.5,
          bic: -115.2,
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockCopulaFitResponse,
    } as Response);

    const result = await apiClient.fitCopula({
      dataset_id: 'ds-copula-1',
      copula_type: 'best_fit',
    });

    expect(result.tickers).toEqual(['AAPL', 'MSFT']);
    expect(result.tail_dependence_matrix[0][1]).toBe(0.45);
    expect(result.pairwise_results[0].copula_type).toBe('clayton');
  });

  it('optimizes Tail Risk Parity allocation and parses risk contributions', async () => {
    const mockTrpResponse = {
      dataset_id: 'ds-copula-1',
      copula_type: 'clayton',
      confidence_level: 0.99,
      converged: true,
      weights: { AAPL: 0.55, MSFT: 0.45 },
      tail_risk_contributions: { AAPL: 0.025, MSFT: 0.025 },
      portfolio_var: 0.035,
      portfolio_cvar: 0.05,
      euler_reconciliation_error: 1e-12,
      simulated_loss_distribution: [0.01, 0.02, 0.05],
      baselines: {
        equal_weight: {
          weights: { AAPL: 0.5, MSFT: 0.5 },
          portfolio_var: 0.038,
          portfolio_cvar: 0.054,
          tail_risk_contributions: { AAPL: 0.03, MSFT: 0.024 },
        },
        inverse_volatility: {
          weights: { AAPL: 0.52, MSFT: 0.48 },
          portfolio_var: 0.036,
          portfolio_cvar: 0.052,
          tail_risk_contributions: { AAPL: 0.028, MSFT: 0.024 },
        },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockTrpResponse,
    } as Response);

    const result = await apiClient.optimizeTailRiskParity({
      dataset_id: 'ds-copula-1',
      copula_type: 'clayton',
    });

    expect(result.converged).toBe(true);
    expect(result.weights.AAPL).toBe(0.55);
    expect(result.portfolio_cvar).toBe(0.05);
    expect(result.baselines.equal_weight.portfolio_cvar).toBe(0.054);
  });

  it('fits Regular Vine Copula decomposition and parses hierarchical trees', async () => {
    const mockVineFitResponse = {
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
      marginal_method: 'empirical',
      ordered_tickers: ['AAPL', 'MSFT', 'GOOGL'],
      dimension: 3,
      trees: [
        [
          {
            tree: 1,
            node_1: 'AAPL',
            node_2: 'MSFT',
            conditioned_on: [],
            copula_type: 'clayton',
            theta: 1.5,
            df: null,
            kendall_tau: 0.42,
            lower_tail_dependence: 0.38,
            upper_tail_dependence: 0.0,
            aic: -150.2,
          },
          {
            tree: 1,
            node_1: 'AAPL',
            node_2: 'GOOGL',
            conditioned_on: [],
            copula_type: 'gumbel',
            theta: 1.8,
            df: null,
            kendall_tau: 0.45,
            lower_tail_dependence: 0.0,
            upper_tail_dependence: 0.48,
            aic: -162.1,
          },
        ],
        [
          {
            tree: 2,
            node_1: 'MSFT',
            node_2: 'GOOGL',
            conditioned_on: ['AAPL'],
            copula_type: 'gaussian',
            theta: 0.25,
            df: null,
            kendall_tau: 0.16,
            lower_tail_dependence: 0.0,
            upper_tail_dependence: 0.0,
            aic: -45.0,
          },
        ],
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockVineFitResponse,
    } as Response);

    const result = await apiClient.fitVineCopula({
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
    });

    expect(result.vine_type).toBe('c_vine');
    expect(result.dimension).toBe(3);
    expect(result.ordered_tickers).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    expect(result.trees.length).toBe(2);
    expect(result.trees[0][0].copula_type).toBe('clayton');
    expect(result.trees[1][0].conditioned_on).toEqual(['AAPL']);
  });

  it('simulates dependent returns from Regular Vine Copula', async () => {
    const mockVineSimResponse = {
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
      num_simulations: 2000,
      random_seed: 42,
      tickers: ['AAPL', 'MSFT'],
      simulated_means: { AAPL: 0.0008, MSFT: 0.0007 },
      simulated_volatilities: { AAPL: 0.015, MSFT: 0.014 },
      sample_correlation_matrix: [
        [1.0, 0.45],
        [0.45, 1.0],
      ],
      sample_scenarios: [{ AAPL: 0.01, MSFT: 0.012 }],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockVineSimResponse,
    } as Response);

    const result = await apiClient.simulateVineCopula({
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
      num_simulations: 2000,
    });

    expect(result.num_simulations).toBe(2000);
    expect(result.simulated_means.AAPL).toBe(0.0008);
    expect(result.sample_correlation_matrix[0][1]).toBe(0.45);
  });

  it('optimizes Vine Tail Risk Parity allocation', async () => {
    const mockVineTrpResponse = {
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
      confidence_level: 0.99,
      converged: true,
      weights: { AAPL: 0.52, MSFT: 0.48 },
      tail_risk_contributions: { AAPL: 0.024, MSFT: 0.024 },
      portfolio_var: 0.034,
      portfolio_cvar: 0.048,
      euler_reconciliation_error: 1e-12,
      simulated_loss_distribution: [0.01, 0.02, 0.048],
      baselines: {
        equal_weight: {
          weights: { AAPL: 0.5, MSFT: 0.5 },
          portfolio_var: 0.035,
          portfolio_cvar: 0.05,
          tail_risk_contributions: { AAPL: 0.026, MSFT: 0.024 },
        },
        inverse_volatility: {
          weights: { AAPL: 0.51, MSFT: 0.49 },
          portfolio_var: 0.034,
          portfolio_cvar: 0.049,
          tail_risk_contributions: { AAPL: 0.025, MSFT: 0.024 },
        },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockVineTrpResponse,
    } as Response);

    const result = await apiClient.optimizeVineTailRiskParity({
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
    });

    expect(result.converged).toBe(true);
    expect(result.weights.AAPL).toBe(0.52);
    expect(result.portfolio_cvar).toBe(0.048);
  });

  it('executes dynamic walk-forward Vine Backtest via API client', async () => {
    const mockVineBacktestResponse = {
      vine_type: 'c_vine',
      estimation_window: 60,
      rebalance_frequency: 'monthly',
      num_simulations: 2000,
      confidence_level: 0.99,
      transaction_cost_bps: 10.0,
      slippage_bps: 5.0,
      initial_capital: 100000.0,
      random_seed: 42,
      out_of_sample_period: {
        start_date: '2024-04-01',
        end_date: '2024-10-01',
        trading_days: 120,
      },
      rebalance_count: 6,
      strategies: {
        dynamic_vine_trp: {
          total_return_gross: 0.135,
          total_return_net: 0.125,
          cagr_net: 0.265,
          annualized_volatility: 0.142,
          sharpe_ratio: 1.72,
          max_drawdown: -0.062,
          cvar_99: 0.029,
          cumulative_turnover: 0.85,
          total_transaction_costs: 125.5,
        },
        equal_weight: {
          total_return_gross: 0.098,
          total_return_net: 0.095,
          cagr_net: 0.198,
          annualized_volatility: 0.168,
          sharpe_ratio: 1.06,
          max_drawdown: -0.088,
          cvar_99: 0.035,
          cumulative_turnover: 0.15,
          total_transaction_costs: 22.0,
        },
        static_vine_trp: {
          total_return_gross: 0.108,
          total_return_net: 0.105,
          cagr_net: 0.221,
          annualized_volatility: 0.155,
          sharpe_ratio: 1.29,
          max_drawdown: -0.075,
          cvar_99: 0.032,
          cumulative_turnover: 0.0,
          total_transaction_costs: 15.0,
        },
      },
      equity_curves: [
        {
          date: '2024-04-01',
          dynamic_vine_trp: 100000.0,
          equal_weight: 100000.0,
          static_vine_trp: 100000.0,
        },
      ],
      rebalance_events: [
        {
          date: '2024-04-01',
          training_window_start: '2024-01-02',
          training_window_end: '2024-03-29',
          target_weights: { AAPL: 0.52, MSFT: 0.48 },
          pre_trade_weights: { AAPL: 0.50, MSFT: 0.50 },
          turnover: 0.15,
          cost: 22.5,
          status: 'converged',
        },
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockVineBacktestResponse,
    } as Response);

    const result = await apiClient.runVineBacktest({
      dataset_id: 'ds-vine-1',
      vine_type: 'c_vine',
      estimation_window: 60,
      rebalance_frequency: 'monthly',
    });

    expect(result.vine_type).toBe('c_vine');
    expect(result.strategies.dynamic_vine_trp.sharpe_ratio).toBe(1.72);
    expect(result.rebalance_count).toBe(6);
    expect(result.rebalance_events[0].target_weights.AAPL).toBe(0.52);
  });

  it('correctly maps and preserves Stage 30 TCA report data contract', async () => {
    const mockTcaReport = {
      summary: {
        fill_count: 5,
        total_requested_notional: 150000.0,
        total_executed_notional: 150000.0,
        total_unexecuted_notional: 0.0,
        total_cost: 125.5,
        effective_bps: 8.37,
        spread_cost: 37.5,
        spread_bps: 2.5,
        temporary_impact_cost: 62.5,
        temporary_impact_bps: 4.17,
        permanent_impact_cost: 10.5,
        permanent_impact_bps: 0.7,
        market_impact_cost: 73.0,
        market_impact_bps: 4.87,
        commission_cost: 15.0,
        commission_bps: 1.0,
        opportunity_cost: 0.0,
        opportunity_bps: 0.0,
        realized_slippage: 110.5,
        realized_slippage_bps: 7.37,
        unattributed_cost: 0.0,
        fill_rate_pct: 100.0,
        friction_drag_on_capital_pct: 0.0125,
      },
      by_regime: {},
      by_mode: {},
      by_asset: {},
      by_event: [],
      provenance: {
        observed_components: ['total_traded_notional', 'commission_cost', 'fill_rate_pct'],
        modeled_components: ['spread_cost', 'temporary_impact_cost', 'permanent_impact_cost'],
        opportunity_cost_status: 'modeled_daily_drift',
        intraday_vwap_status: 'unavailable_daily_bars',
        currency_basis: 'USD',
        decomposition_type: 'structural_modeled_identity',
        permanent_impact_status: 'modeled_linear_adv_ratio',
        reconciliation_status: 'exact_modeled_identity_verified',
      },
    };

    const mockResponseWithTCA = {
      dataset_id: 'ds-tca-1',
      vine_type: 'd_vine',
      rebalance_history: [],
      equity_curve: [],
      tca_report: mockTcaReport,
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockResponseWithTCA,
    } as Response);

    const result = await apiClient.runVineBacktest({
      dataset_id: 'ds-tca-1',
      vine_type: 'd_vine',
    });

    expect(result.tca_report).toBeDefined();
    expect(result.tca_report?.summary.total_cost).toBe(125.5);
    expect(result.tca_report?.summary.effective_bps).toBe(8.37);
    expect(result.tca_report?.summary.unattributed_cost).toBe(0.0);
    expect(result.tca_report?.summary.realized_slippage).toBe(110.5);
    expect(result.tca_report?.provenance.reconciliation_status).toBe('exact_modeled_identity_verified');
    expect(result.tca_report?.provenance.decomposition_type).toBe('structural_modeled_identity');
  });
});




