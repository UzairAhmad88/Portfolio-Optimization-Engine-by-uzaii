"""
Pydantic v2 domain schemas and API contracts for institutional reporting,
Strategy Fact Sheets, Institutional Tear Sheets, and Research Diagnostics Annexes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

from app.research.overfitting_models import (
    CSCVCombinationsPoint,
    CSCVHistogramBin,
    DegradationRegression,
    PBORiskLevel,
    RunOverfittingSummary,
)

ReportType = Literal["fact_sheet", "tear_sheet", "research_diagnostics", "unified_tear_sheet"]
WarningSeverity = Literal["info", "warning", "critical"]
MetricAvailabilityStatus = Literal["available", "unavailable", "undefined", "invalid", "not_applicable"]

DEFAULT_DISCLAIMER = (
    "This report is for institutional research and decision-support purposes only. "
    "Hypothetical or simulated performance results have inherent limitations and do not represent actual trading. "
    "Past performance, backtested results, or statistical confidence metrics do not guarantee future profitability "
    "or protect against risk of loss."
)


class ReportWarning(BaseModel):
    """
    Structured, machine-readable advisory warning or limitation note.
    """
    code: str = Field(description="Unique stable warning classification code, e.g. 'WARN_TRIMMING_DIVERGENCE'.")
    severity: WarningSeverity = Field(default="warning", description="Severity level: 'info', 'warning', or 'critical'.")
    message: str = Field(description="Clear, non-technical explanation of the limitation or data condition.")
    affected_metric: str | None = Field(default=None, description="Optional canonical metric name impacted.")
    provenance_ref: str | None = Field(default=None, description="Optional entity or dataset identifier reference.")


class CommonReportEnvelope(BaseModel):
    """
    Common contextual and provenance envelope present on every institutional report output.
    """
    contract_version: str = Field(default="1.0", description="Contract schema specification version.")
    report_type: ReportType = Field(description="Type of report: 'fact_sheet', 'tear_sheet', 'research_diagnostics', or 'unified_tear_sheet'.")
    report_title: str = Field(description="Formal title displayed in header.")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of report generation.")
    base_currency: str = Field(default="USD", description="Reporting base currency ISO code.")
    reporting_start_date: str = Field(description="Effective evaluation start date (YYYY-MM-DD).")
    reporting_end_date: str = Field(description="Effective evaluation end date (YYYY-MM-DD).")
    
    # Provenance and lineage
    dataset_id: str = Field(description="Primary persistent market dataset UUID.")
    dataset_filename: str | None = Field(default=None, description="Display filename of market dataset.")
    snapshot_id: str | None = Field(default=None, description="Immutable dataset snapshot UUID if bound.")
    snapshot_manifest_digest: str | None = Field(default=None, description="Cryptographic SHA-256 manifest digest if snapshot certified.")
    source_backtest_id: str | None = Field(default=None, description="Underlying BacktestRun UUID if derived from a backtest.")
    source_experiment_id: str | None = Field(default=None, description="Parent ResearchExperiment UUID if derived from research.")
    source_run_id: str | None = Field(default=None, description="Specific ResearchExperimentRun UUID if applicable.")
    calculation_version: str = Field(default="1.0", description="Financial engine and methodology version.")
    
    warnings: list[ReportWarning] = Field(default_factory=list, description="Collection of advisory warnings and data limitations.")
    is_hypothetical: bool = Field(default=True, description="Strict disclosure flag certifying simulated nature of data.")
    regulatory_disclaimer: str = Field(default=DEFAULT_DISCLAIMER, description="Statutory institutional disclosure copy.")

    @model_validator(mode="after")
    def validate_date_ordering(self) -> CommonReportEnvelope:
        if self.reporting_start_date and self.reporting_end_date:
            if self.reporting_start_date > self.reporting_end_date:
                raise ValueError(
                    f"reporting_start_date ({self.reporting_start_date}) cannot be after reporting_end_date ({self.reporting_end_date})."
                )
        return self


class ExecutiveKPIs(BaseModel):
    """
    Core risk-adjusted performance scorecard metrics with strict separation between gross and net returns.
    """
    # Standalone Net Performance (authoritative client-facing after transaction costs)
    cumulative_return_net: float = Field(description="Cumulative total net return over track record.")
    cumulative_return_gross: float | None = Field(default=None, description="Cumulative total gross return before friction costs.")
    cagr_net: float = Field(description="Compound Annual Growth Rate net of costs.")
    cagr_gross: float | None = Field(default=None, description="Compound Annual Growth Rate gross of costs.")
    annualized_return_net: float = Field(description="Annualized net mean return.")
    annualized_return_gross: float | None = Field(default=None, description="Annualized gross mean return.")
    annualized_volatility_net: float = Field(description="Annualized sample standard deviation of net returns.")
    annualized_volatility_gross: float | None = Field(default=None, description="Annualized sample standard deviation of gross returns.")
    sharpe_ratio_net: float | None = Field(default=None, description="Annualized net Sharpe ratio (None if volatility is zero).")
    sharpe_ratio_gross: float | None = Field(default=None, description="Annualized gross Sharpe ratio.")
    sortino_ratio_net: float | None = Field(default=None, description="Annualized net Sortino ratio (None if downside deviation is zero).")
    sortino_ratio_gross: float | None = Field(default=None, description="Annualized gross Sortino ratio.")
    max_drawdown_net: float = Field(description="Peak-to-trough maximum drawdown of net equity curve (positive decimal, e.g. 0.15 = 15%).")
    max_drawdown_gross: float | None = Field(default=None, description="Maximum drawdown of gross equity curve.")
    calmar_ratio_net: float | None = Field(default=None, description="CAGR divided by Max Drawdown (None if max drawdown is zero).")
    calmar_ratio_gross: float | None = Field(default=None, description="Gross Calmar ratio.")
    
    # Peak/Trough dates
    drawdown_peak_date: str | None = Field(default=None, description="Date of historical peak preceding max drawdown.")
    drawdown_trough_date: str | None = Field(default=None, description="Date of max drawdown trough.")
    drawdown_recovery_date: str | None = Field(default=None, description="Date of recovery to new high (None if still in drawdown).")
    drawdown_duration_days: int | None = Field(default=None, description="Calendar or trading days spent in maximum drawdown.")
    
    # Trading period counts
    positive_periods_count: int | None = Field(default=None, description="Number of trading periods with positive returns.")
    negative_periods_count: int | None = Field(default=None, description="Number of trading periods with negative returns.")
    win_rate: float | None = Field(default=None, ge=0.0, le=1.0, description="Fraction of positive trading periods.")
    profit_loss_ratio: float | None = Field(default=None, description="Average gain on winning periods divided by average loss on losing periods.")
    
    observation_count: int = Field(ge=1, description="Number of historical daily return observations.")
    periods_per_year: int = Field(default=252, ge=1, description="Annualization factor used.")


class BenchmarkRelativeMetrics(BaseModel):
    """
    Attribution and comparative analytics against an authoritative market benchmark.
    """
    benchmark_id: str = Field(description="Benchmark ticker or identifier (e.g. 'SPY:US').")
    benchmark_name: str = Field(description="Display label of the benchmark.")
    benchmark_cumulative_return: float = Field(description="Cumulative return of benchmark over identical synchronized period.")
    benchmark_annualized_return: float = Field(description="Annualized return of benchmark.")
    benchmark_annualized_volatility: float = Field(description="Annualized volatility of benchmark.")
    benchmark_sharpe_ratio: float | None = Field(default=None, description="Benchmark Sharpe ratio.")
    benchmark_max_drawdown: float = Field(description="Benchmark maximum drawdown.")
    
    # Relative / Active Metrics
    arithmetic_active_return: float = Field(description="Portfolio return minus benchmark return.")
    geometric_excess_return: float = Field(description="Compounded wealth ratio minus one ((1 + Rp) / (1 + Rb) - 1).")
    annualized_active_return: float = Field(description="Annualized active excess return.")
    tracking_error: float = Field(description="Annualized standard deviation of daily active returns.")
    information_ratio: float | None = Field(default=None, description="Annualized active return divided by tracking error (None if tracking error is zero).")
    beta: float | None = Field(default=None, description="Market beta regression coefficient Cov(Rp, Rb) / Var(Rb).")
    alpha_annualized: float | None = Field(default=None, description="Annualized Jensen's alpha intercept.")
    treynor_ratio: float | None = Field(default=None, description="Excess return divided by beta (None if beta is non-positive or zero).")
    up_capture_ratio: float | None = Field(default=None, description="Performance ratio during positive benchmark periods.")
    down_capture_ratio: float | None = Field(default=None, description="Performance ratio during negative benchmark periods.")
    correlation: float | None = Field(default=None, ge=-1.0, le=1.0, description="Pearson correlation coefficient between portfolio and benchmark.")


class AssetAllocationItem(BaseModel):
    """
    Constituent asset representation with weights and Menchero attribution contributions.
    """
    asset_id: str = Field(description="Canonical asset identifier.")
    ticker: str = Field(description="Market ticker symbol.")
    market: str = Field(description="Exchange market (US, PSX, etc.).")
    name: str | None = Field(default=None, description="Human-readable asset name if known.")
    target_weight: float = Field(description="Designed target allocation weight.")
    effective_weight: float = Field(description="Realized average or terminal effective weight.")
    asset_cumulative_return: float | None = Field(default=None, description="Underlying asset return over track record.")
    total_contribution: float | None = Field(default=None, description="Menchero geometrically linked additive return contribution.")
    share_of_return: float | None = Field(default=None, description="Percentage share of cumulative portfolio return.")


class TimeSeriesPoint(BaseModel):
    """
    Synchronized daily performance point for vector charting and print curve rendering.
    """
    date: str = Field(description="Observation date (YYYY-MM-DD).")
    portfolio_value_net: float = Field(description="Net portfolio wealth index (normalized to initial_capital).")
    portfolio_value_gross: float | None = Field(default=None, description="Gross portfolio wealth index before friction costs.")
    return_net: float = Field(description="Discrete net simple return.")
    return_gross: float | None = Field(default=None, description="Discrete gross simple return.")
    drawdown_net: float = Field(description="Net drawdown depth from peak (positive decimal, 0.0 to 1.0).")
    drawdown_gross: float | None = Field(default=None, description="Gross drawdown depth.")
    benchmark_value: float | None = Field(default=None, description="Normalized benchmark wealth index.")
    benchmark_return: float | None = Field(default=None, description="Benchmark daily return.")
    benchmark_drawdown: float | None = Field(default=None, description="Benchmark drawdown depth.")


class MonthlyReturnCell(BaseModel):
    """
    Single month discrete return for institutional monthly returns heatmaps.
    """
    year: int = Field(ge=1900, le=2100)
    month: int = Field(ge=1, le=12)
    return_net: float = Field(description="Compounded net monthly return.")
    return_gross: float | None = Field(default=None, description="Compounded gross monthly return.")
    benchmark_return: float | None = Field(default=None, description="Benchmark monthly return.")


class FrictionAndExecutionMetrics(BaseModel):
    """
    Transaction cost analysis (TCA) and liquidity friction drag disclosure.
    """
    total_turnover: float = Field(description="Cumulative portfolio turnover (sum of abs trade weights).")
    annualized_turnover: float | None = Field(default=None, description="Annualized portfolio turnover rate.")
    transaction_cost_bps: float = Field(description="Configured brokerage fee rate in basis points.")
    slippage_bps: float = Field(description="Configured execution price slippage in basis points.")
    total_transaction_costs: float = Field(description="Total monetary transaction costs incurred.")
    total_slippage_costs: float = Field(description="Total monetary execution slippage incurred.")
    total_friction_costs: float = Field(description="Total aggregate friction drag (costs + slippage).")
    friction_drag_bps: float = Field(description="Total friction drag in basis points relative to initial capital.")
    number_of_rebalances: int = Field(ge=0, description="Total discrete rebalance execution events.")


class StrategyMandate(BaseModel):
    """
    Portfolio strategy operational parameters and investment constraints.
    """
    strategy_type: str = Field(description="Strategy archetype label (e.g. Target Weights, Mean-Variance, HRP).")
    investment_universe: list[str] = Field(description="List of tickers or assets eligible for inclusion.")
    rebalance_frequency: str = Field(description="Rebalancing cadence: 'buy_and_hold', 'daily', 'monthly', etc.")
    optimization_objective: str | None = Field(default=None, description="Mathematical objective (e.g. 'max_sharpe', 'min_variance').")
    initial_capital: float = Field(gt=0.0, description="Starting cash capital.")
    risk_free_rate: float = Field(default=0.0, description="Annualized benchmark risk-free rate.")
    constraints_summary: list[str] = Field(default_factory=list, description="Human-readable constraints summary lines.")


class StrategyFactSheetPayload(BaseModel):
    """
    Contract payload for the 1-Page Strategy Fact Sheet.
    Designed for executive decision-makers and investment committee overviews.
    """
    envelope: CommonReportEnvelope
    mandate: StrategyMandate
    kpis: ExecutiveKPIs
    benchmark_metrics: BenchmarkRelativeMetrics | None = None
    top_holdings: list[AssetAllocationItem] = Field(default_factory=list, description="Top portfolio holdings (e.g. top 5-10 assets).")
    compact_wealth_curve: list[TimeSeriesPoint] = Field(default_factory=list, description="Downsampled or full wealth series for summary chart.")
    monthly_returns: list[MonthlyReturnCell] = Field(default_factory=list, description="Recent monthly return summary grid.")


class InstitutionalTearSheetPayload(BaseModel):
    """
    Contract payload for the Comprehensive 2-Page Institutional Tear Sheet.
    Includes full attribution, friction analysis, drawdown chronology, and monthly return matrices.
    """
    envelope: CommonReportEnvelope
    mandate: StrategyMandate
    kpis: ExecutiveKPIs
    benchmark_metrics: BenchmarkRelativeMetrics | None = None
    asset_allocation: list[AssetAllocationItem] = Field(default_factory=list, description="Complete constituent asset allocations.")
    friction_and_execution: FrictionAndExecutionMetrics | None = None
    equity_curve: list[TimeSeriesPoint] = Field(default_factory=list, description="Full synchronized daily equity curve.")
    monthly_returns_table: list[MonthlyReturnCell] = Field(default_factory=list, description="Multi-year monthly returns grid.")


class ResearchDiagnosticsAnnexPayload(BaseModel):
    """
    Contract payload for the 3rd-Page Research Diagnostics Annex.
    Integrates Stage 33 Overfitting Diagnostics (PBO, DSR, MinBTL, and CSCV relative-rank distribution).
    """
    envelope: CommonReportEnvelope
    evaluated_runs_count: int = Field(ge=1, description="Number of candidate trials N evaluated.")
    aligned_observations_count: int = Field(ge=1, description="Number of synchronized return observations T.")
    n_slices: int = Field(ge=4, le=16, description="CSCV partition slice count S.")
    total_combinations_count: int = Field(ge=1, description="Combinatorial partition count C = binom(S, S/2).")
    
    # Overfitting metrics
    pbo: float = Field(ge=0.0, le=1.0, description="Probability of Backtest Overfitting.")
    pbo_risk_level: PBORiskLevel = Field(description="Institutional risk classification.")
    best_run_id: str = Field(description="UUID of selected best strategy.")
    best_run_number: int = Field(ge=1, description="Run number of best strategy.")
    best_nominal_sharpe: float = Field(description="Nominal annualized Sharpe ratio of best strategy.")
    expected_max_sharpe: float = Field(description="Expected maximum Sharpe ratio under selection bias.")
    deflated_sharpe_ratio: float = Field(ge=0.0, le=1.0, description="Deflated Sharpe Ratio (DSR).")
    is_statistically_significant: bool = Field(description="True if DSR >= (1 - alpha).")
    min_backtest_length_years: float | None = Field(default=None, description="Minimum Backtest Length in years (None if unreachable).")
    actual_backtest_length_years: float = Field(description="Observed track record length in years.")
    skewness: float = Field(description="Sample skewness of best strategy returns.")
    kurtosis: float = Field(description="Sample Pearson kurtosis of best strategy returns.")
    
    degradation_regression: DegradationRegression = Field(description="CSCV OLS degradation regression metrics.")
    combinations_sample: list[CSCVCombinationsPoint] = Field(default_factory=list, description="Plotted combinations sample (up to 500 points).")
    rank_distribution: list[CSCVHistogramBin] = Field(default_factory=list, description="10-decile relative-rank histogram distribution.")
    runs_summary: list[RunOverfittingSummary] = Field(default_factory=list, description="Per-trial selection and performance statistics.")


class InstitutionalReportResponse(BaseModel):
    """
    Unified institutional report API response envelope.
    Supports delivering Fact Sheet, Tear Sheet, and optional Research Annex in a single cohesive payload.
    """
    envelope: CommonReportEnvelope
    fact_sheet: StrategyFactSheetPayload | None = None
    tear_sheet: InstitutionalTearSheetPayload | None = None
    research_annex: ResearchDiagnosticsAnnexPayload | None = None
