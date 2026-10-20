"""
Pydantic v2 Models for Copula Tail Dependency Estimation,
Multivariate Simulation & Tail Risk Parity Allocation.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class CopulaFitRequest(BaseModel):
    dataset_id: str
    copula_type: Literal["clayton", "gumbel", "student_t", "gaussian", "best_fit"] = "best_fit"
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class PairwiseCopulaResult(BaseModel):
    asset_1: str
    asset_2: str
    copula_type: str
    theta: float
    df: float | None = None
    kendall_tau: float
    pearson_corr: float
    lower_tail_dependence: float
    upper_tail_dependence: float
    aic: float
    bic: float


class CopulaFitResponse(BaseModel):
    dataset_id: str
    copula_type: str
    marginal_method: str
    tickers: list[str]
    tail_dependence_matrix: list[list[float]]
    kendall_tau_matrix: list[list[float]]
    pearson_corr_matrix: list[list[float]]
    pairwise_results: list[PairwiseCopulaResult]


class CopulaSimulateRequest(BaseModel):
    dataset_id: str
    copula_type: Literal["clayton", "gumbel", "student_t", "gaussian"] = "clayton"
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    num_simulations: int = Field(default=5000, ge=500, le=50000)
    random_seed: int = Field(default=42, ge=0)
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class CopulaSimulateResponse(BaseModel):
    dataset_id: str
    copula_type: str
    num_simulations: int
    random_seed: int
    tickers: list[str]
    simulated_means: dict[str, float]
    simulated_volatilities: dict[str, float]
    sample_correlation_matrix: list[list[float]]
    sample_scenarios: list[dict[str, float]]


class TailRiskParityRequest(BaseModel):
    dataset_id: str
    copula_type: Literal["clayton", "gumbel", "student_t", "gaussian"] = "clayton"
    confidence_level: float = Field(default=0.99, ge=0.90, le=0.999)
    num_simulations: int = Field(default=5000, ge=1000, le=50000)
    random_seed: int = Field(default=42, ge=0)
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class TailRiskParityResponse(BaseModel):
    dataset_id: str
    copula_type: str
    confidence_level: float
    converged: bool
    weights: dict[str, float]
    tail_risk_contributions: dict[str, float]
    portfolio_var: float
    portfolio_cvar: float
    euler_reconciliation_error: float
    simulated_loss_distribution: list[float]
    baselines: dict[str, Any]


# Alias for contracts compatibility
CopulaOptimizeRequest = TailRiskParityRequest
CopulaOptimizeResponse = TailRiskParityResponse


# ============================================================================
# Regular Vine Copula (Stage 23) Models
# ============================================================================

class VineEdge(BaseModel):
    tree: int
    node_1: str
    node_2: str
    conditioned_on: list[str]
    copula_type: str
    theta: float
    df: float | None = None
    kendall_tau: float
    lower_tail_dependence: float
    upper_tail_dependence: float
    aic: float


class VineCopulaFitRequest(BaseModel):
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    family_set: list[str] | None = None
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class VineCopulaFitResponse(BaseModel):
    dataset_id: str
    vine_type: str
    marginal_method: str
    ordered_tickers: list[str]
    dimension: int
    trees: list[list[VineEdge]]


class VineCopulaSimulateRequest(BaseModel):
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    num_simulations: int = Field(default=5000, ge=500, le=50000)
    random_seed: int = Field(default=42, ge=0)
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class VineCopulaSimulateResponse(BaseModel):
    dataset_id: str
    vine_type: str
    num_simulations: int
    random_seed: int
    tickers: list[str]
    simulated_means: dict[str, float]
    simulated_volatilities: dict[str, float]
    sample_correlation_matrix: list[list[float]]
    sample_scenarios: list[dict[str, float]]


class VineTailRiskParityRequest(BaseModel):
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    confidence_level: float = Field(default=0.99, ge=0.90, le=0.999)
    num_simulations: int = Field(default=5000, ge=1000, le=50000)
    random_seed: int = Field(default=42, ge=0)
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class VineTailRiskParityResponse(BaseModel):
    dataset_id: str
    vine_type: str
    confidence_level: float
    converged: bool
    weights: dict[str, float]
    tail_risk_contributions: dict[str, float]
    portfolio_var: float
    portfolio_cvar: float
    euler_reconciliation_error: float
    simulated_loss_distribution: list[float]
    baselines: dict[str, Any]


# ============================================================================
# Dynamic Walk-Forward Vine Backtesting (Stage 24) Models
# ============================================================================

class VineBacktestRequest(BaseModel):
    dataset_id: str
    vine_type: Literal["c_vine", "d_vine"] = "c_vine"
    estimation_window: int = Field(default=60, ge=30, le=500)
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly"
    num_simulations: int = Field(default=2000, ge=500, le=20000)
    confidence_level: float = Field(default=0.99, ge=0.90, le=0.999)
    marginal_method: Literal["empirical", "student_t"] = "empirical"
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    initial_capital: float = Field(default=100000.0, gt=0.0)
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=0.20)
    random_seed: int = Field(default=42, ge=0)
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    execution_model: Literal["fixed_bps", "linear", "square_root"] = "square_root"
    bid_ask_spread_bps: float = Field(default=5.0, ge=0.0, le=1000.0)
    max_participation_rate: float = Field(default=0.10, ge=0.001, le=1.0)
    participation_policy: Literal["warn", "cap", "reject"] = "warn"
    execution_horizon_days: float = Field(default=1.0, ge=0.1, le=20.0)
    c_temp: float = Field(default=0.5, ge=0.0, le=5.0)
    c_perm: float = Field(default=0.1, ge=0.0, le=5.0)
    default_adv: float = Field(default=10_000_000.0, gt=0.0)
    enable_endogenous_liquidity: bool = True
    spread_stress_sensitivity: float = Field(default=5.0, ge=0.0, le=50.0)
    adv_stress_sensitivity: float = Field(default=5.0, ge=0.0, le=50.0)
    execution_scheduling_mode: Literal["single_day", "twap", "vwap", "almgren_chriss"] = "single_day"
    max_scheduling_days: int = Field(default=5, ge=1, le=20)
    scheduling_risk_aversion: float = Field(default=1e-6, ge=0.0, le=1.0)
    enable_regime_aware_execution: bool = False
    regime_num_states: int = Field(default=2, ge=2, le=5)
    regime_adaptation_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    min_participation_rate: float = Field(default=0.02, ge=0.001, le=1.0)


class VineBacktestStrategyMetrics(BaseModel):
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    historical_var_99: float
    historical_cvar_99: float
    l_var_99: float = 0.0
    l_cvar_99: float = 0.0
    stressed_l_var_99: float = 0.0
    stressed_l_cvar_99: float = 0.0
    average_cash_weight: float = 0.0
    total_turnover: float
    total_transaction_costs: float
    total_spread_costs: float = 0.0
    total_market_impact_costs: float = 0.0
    total_commission_costs: float = 0.0
    max_participation_rate_observed: float = 0.0
    participation_warnings_count: int = 0
    total_return_gross: float = 0.0
    total_return_net: float = 0.0
    cagr_gross: float = 0.0
    cagr_net: float = 0.0
    annualized_volatility_gross: float = 0.0
    annualized_volatility_net: float = 0.0
    sharpe_ratio_gross: float = 0.0
    sharpe_ratio_net: float = 0.0


class VineBacktestEquityPoint(BaseModel):
    date: str
    strategy_equity: float
    benchmark_equity: float
    static_trp_equity: float
    drawdown: float


class VineBacktestRebalanceEvent(BaseModel):
    rebalance_index: int
    date: str
    training_window_start: str
    training_window_end: str
    requested_weights: dict[str, float] | None = None
    executed_weights: dict[str, float] | None = None
    weights: dict[str, float]
    turnover: float
    transaction_cost: float
    spread_cost: float = 0.0
    market_impact_cost: float = 0.0
    commission_cost: float = 0.0
    portfolio_cvar: float
    portfolio_var: float
    liquidity_adjusted_cvar: float = 0.0
    liquidity_adjusted_var: float = 0.0
    stressed_liquidity_adjusted_cvar: float = 0.0
    stressed_liquidity_adjusted_var: float = 0.0
    liquidation_cost_pct: float = 0.0
    cash_weight: float = 0.0
    max_participation_rate: float = 0.0
    participation_warning: bool = False
    rebalance_rejected: bool = False
    adv_source: str = "model_fallback"
    tail_risk_contributions: dict[str, float]
    converged: bool
    solver_message: str
    scheduled_days: int = 1
    scheduling_mode: str = "single_day"
    regime_state: int | None = None
    regime_probabilities: list[float] | None = None
    effective_participation_rate: float | None = None
    effective_risk_aversion: float | None = None
    regime_adaptation_strength: float | None = None


# ============================================================================
# Transaction Cost Analysis (Stage 30) Models
# ============================================================================

class TCACostMetrics(BaseModel):
    fill_count: int = 0
    total_requested_notional: float = 0.0
    total_executed_notional: float = 0.0
    total_unexecuted_notional: float = 0.0
    total_cost: float = 0.0
    effective_bps: float = 0.0
    spread_cost: float = 0.0
    spread_bps: float = 0.0
    temporary_impact_cost: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_cost: float = 0.0
    permanent_impact_bps: float = 0.0
    market_impact_cost: float = 0.0
    market_impact_bps: float = 0.0
    commission_cost: float = 0.0
    commission_bps: float = 0.0
    opportunity_cost: float = 0.0
    opportunity_bps: float = 0.0
    realized_slippage: float = 0.0
    realized_slippage_bps: float = 0.0
    unattributed_cost: float = 0.0
    fill_rate_pct: float = 100.0
    friction_drag_on_capital_pct: float | None = None


class TCAEventMetrics(TCACostMetrics):
    date: str
    regime_state: int | None = None
    scheduling_mode: str = "single_day"
    scheduled_horizon_days: int = 1


class TCAProvenance(BaseModel):
    observed_components: list[str] = Field(default_factory=list)
    modeled_components: list[str] = Field(default_factory=list)
    opportunity_cost_status: str = "modeled_daily_drift"
    intraday_vwap_status: str = "unavailable_daily_bars"
    currency_basis: str = "USD"
    decomposition_type: str = "structural_modeled_identity"
    permanent_impact_status: str = "modeled_linear_adv_ratio"
    reconciliation_status: str = "exact_modeled_identity_verified"


class TCAReport(BaseModel):
    summary: TCACostMetrics
    by_regime: dict[str, TCACostMetrics] = Field(default_factory=dict)
    by_mode: dict[str, TCACostMetrics] = Field(default_factory=dict)
    by_asset: dict[str, TCACostMetrics] = Field(default_factory=dict)
    by_event: list[TCAEventMetrics] = Field(default_factory=list)
    provenance: TCAProvenance = Field(default_factory=TCAProvenance)


class VineBacktestResponse(BaseModel):
    dataset_id: str
    vine_type: str
    estimation_window: int
    rebalance_frequency: str
    confidence_level: float
    num_simulations: int
    marginal_method: str
    evaluation_start_date: str
    evaluation_end_date: str
    total_evaluation_days: int
    total_rebalances: int
    fallback_rebalances: int
    execution_model: str = "square_root"
    bid_ask_spread_bps: float = 5.0
    max_participation_rate: float = 0.10
    participation_policy: str = "warn"
    enable_endogenous_liquidity: bool = True
    spread_stress_sensitivity: float = 5.0
    adv_stress_sensitivity: float = 5.0
    adv_source: str = "model_fallback"
    execution_scheduling_mode: str = "single_day"
    max_scheduling_days: int = 5
    scheduling_risk_aversion: float = 1e-6
    enable_regime_aware_execution: bool = False
    regime_num_states: int = 2
    regime_adaptation_strength: float = 0.5
    min_participation_rate: float = 0.02
    strategy_metrics: VineBacktestStrategyMetrics
    benchmark_metrics: VineBacktestStrategyMetrics
    static_trp_metrics: VineBacktestStrategyMetrics
    equity_curve: list[VineBacktestEquityPoint]
    rebalance_history: list[VineBacktestRebalanceEvent]
    tca_report: TCAReport | None = None


