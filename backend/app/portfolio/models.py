"""
Domain and API Pydantic models for portfolio definition, asset references,
and investment constraints.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetMetadata(BaseModel):
    """
    Standardized asset reference containing verified dataset metadata.
    """

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(
        description="Unique asset identifier in format 'TICKER:MARKET'"
    )
    ticker: str = Field(description="Normalized asset ticker symbol")
    market: Literal["US", "PSX"] = Field(description="Exchange market identifier")
    currency: str = Field(description="Trading currency ISO code (e.g. USD, PKR)")
    start_date: str = Field(
        description="Earliest available observation date (YYYY-MM-DD)"
    )
    end_date: str = Field(description="Latest available observation date (YYYY-MM-DD)")
    observation_count: int = Field(
        description="Number of valid historical price bars in dataset", ge=1
    )


class WeightBoundsModel(BaseModel):
    """
    Lower and upper bound constraints for a single asset.
    """

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(
        description="Minimum allowable portfolio weight for this asset"
    )
    upper: float = Field(
        description="Maximum allowable portfolio weight for this asset"
    )

    @field_validator("lower", "upper")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        import numpy as np

        if not np.isfinite(v):
            raise ValueError("Bound values must be finite numbers.")
        return float(v)


class InvestmentConstraintsModel(BaseModel):
    """
    User-configurable investment constraints for portfolio construction.
    """

    model_config = ConfigDict(extra="forbid")

    default_min_weight: float = Field(
        default=0.0,
        description="Default minimum weight applied to assets without an explicit override (e.g. 0.0 for long-only)",
    )
    default_max_weight: float = Field(
        default=1.0,
        description="Default maximum weight cap applied to assets without an explicit override (e.g. 1.0 or 0.25)",
    )
    asset_bounds: dict[str, WeightBoundsModel] = Field(
        default_factory=dict,
        description="Optional per-asset weight bounds overriding the defaults (keyed by ticker or asset_id)",
    )
    target_total_weight: float = Field(
        default=1.0,
        description="Target sum of portfolio weights (1.0 for a fully invested portfolio)",
    )
    allow_short: bool = False
    max_gross_exposure: float | None = Field(
        default=None,
        description="Maximum permitted gross exposure sum(|w_i|). Omit to allow unconstrained gross leverage.",
    )
    min_net_exposure: float | None = Field(
        default=None,
        description="Minimum permitted net exposure sum(w_i). If None, target_total_weight is used.",
    )
    max_net_exposure: float | None = Field(
        default=None,
        description="Maximum permitted net exposure sum(w_i). If None, target_total_weight is used.",
    )
    included_assets: list[str] = Field(
        default_factory=list,
        description="List of asset identifiers that must receive a positive allocation in the portfolio",
    )
    excluded_assets: list[str] = Field(
        default_factory=list,
        description="List of asset identifiers barred from receiving an allocation (forced to 0.0)",
    )


class PortfolioDefinition(BaseModel):
    """
    Specification for a portfolio constructed from a registered historical dataset.
    """

    model_config = ConfigDict(extra="forbid")

    portfolio_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the portfolio definition",
    )
    name: str = Field(
        min_length=1,
        max_length=120,
        description="Human-readable descriptive name for the portfolio",
        examples=["US Tech Core Allocation"],
    )
    dataset_id: str = Field(
        description="UUIDv4 identifier of the registered market-data dataset",
    )
    assets: list[str] = Field(
        min_length=1,
        max_length=100,
        description="Ordered list of selected tickers or asset identifiers (e.g. ['AAPL', 'MSFT'] or ['AAPL:US', 'MSFT:US'])",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description="Optional user-specified portfolio weights. Must match assets if provided.",
    )
    constraints: InvestmentConstraintsModel = Field(
        default_factory=InvestmentConstraintsModel,
        description="Portfolio investment constraints and position caps",
    )
    start_date: date | None = Field(
        default=None,
        description="Optional inclusive start date for historical price slicing",
    )
    end_date: date | None = Field(
        default=None,
        description="Optional inclusive end date for historical price slicing",
    )
    base_currency: str | None = Field(
        default=None,
        description="Base currency for portfolio evaluation (e.g. 'USD' or 'PKR')",
    )
    version: str = Field(
        default="1.0",
        description="Portfolio schema specification version",
    )

    @field_validator("assets")
    @classmethod
    def validate_unique_assets(cls, v: list[str]) -> list[str]:
        cleaned = [str(a).strip().upper() for a in v if str(a).strip()]
        if not cleaned:
            raise ValueError("Assets list cannot be empty.")
        if len(cleaned) != len(set(cleaned)):
            duplicates = [a for a in cleaned if cleaned.count(a) > 1]
            raise ValueError(
                f"Duplicate asset selections detected: {sorted(set(duplicates))}."
            )
        return cleaned


class PortfolioValidationReport(BaseModel):
    """
    Comprehensive verification and audit report for a portfolio definition.
    """

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = Field(
        description="True if the portfolio definition satisfies all data, currency, and constraint invariants"
    )
    portfolio_name: str
    dataset_id: str
    selected_assets: list[str]
    asset_details: list[AssetMetadata] = Field(default_factory=list)
    currency_policy: dict[str, Any] = Field(
        description="Currency analysis (currencies present, multi-currency status, base currency)"
    )
    date_coverage: dict[str, Any] = Field(
        description="Effective common historical date range and observation counts"
    )
    weight_summary: dict[str, Any] | None = Field(
        default=None, description="Diagnostic summary of explicit weights if provided"
    )
    feasibility: dict[str, Any] = Field(
        description="Mathematical constraint feasibility check summary"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Actionable blocking errors preventing valid portfolio construction",
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-blocking informational warnings"
    )


class OptimizationRequest(BaseModel):
    """
    Typed request model for portfolio optimization.
    """

    model_config = ConfigDict(extra="forbid")

    portfolio: PortfolioDefinition = Field(
        description="Validated portfolio specification with assets, dataset reference, and constraints"
    )
    objective: Literal["min_variance", "max_sharpe", "equal_weight", "target_return"] = Field(
        default="min_variance",
        description="Optimization objective: 'min_variance', 'max_sharpe', 'equal_weight', or 'target_return'",
    )
    target_return: float | None = Field(
        default=None,
        description="Target expected return as decimal (e.g. 0.15 for 15.0%) when objective is 'target_return'",
    )
    risk_free_rate: float = Field(
        default=0.0,
        description="Annual risk-free rate as decimal (e.g. 0.02 for 2.0%) for Sharpe calculation",
    )
    annualized: bool = Field(
        default=True,
        description="Whether expected returns, volatility, and covariance are annualized",
    )
    periods_per_year: int = Field(
        default=252,
        ge=1,
        le=365,
        description="Compounding periods per year (e.g. 252 for US equities, 250 for PSX equities)",
    )


class PortfolioMetricsModel(BaseModel):
    """
    Independently verified portfolio performance and risk metrics.
    """

    model_config = ConfigDict(extra="forbid")

    expected_return: float = Field(description="Portfolio expected return (arithmetic mean)")
    variance: float = Field(description="Portfolio variance (w^T Sigma w)", ge=0.0)
    volatility: float = Field(description="Portfolio volatility (standard deviation)", ge=0.0)
    sharpe_ratio: float | None = Field(
        default=None,
        description="Sharpe ratio (excess return / volatility), or None if volatility is near-zero",
    )
    total_weight: float = Field(description="Algebraic sum of portfolio weights (net exposure)")
    gross_exposure: float = Field(description="Sum of absolute weights sum(|w_i|)", ge=0.0)
    is_fully_invested: bool = Field(description="True if total_weight is within 1e-6 of 1.0")
    is_long_only: bool = Field(description="True if all weights are non-negative")
    has_short_positions: bool = Field(description="True if any weight is negative")


class SolverDiagnosticsModel(BaseModel):
    """
    Numerical optimization solver metadata and diagnostics.
    """

    model_config = ConfigDict(extra="forbid")

    solver_name: str = Field(description="Numerical solver algorithm used (e.g. 'SciPy SLSQP')")
    status: str = Field(description="Solver exit status classification")
    message: str = Field(description="Detailed solver termination message or explanation")
    converged: bool = Field(description="True if solver achieved numerical convergence and satisfied constraints")
    iterations: int | None = Field(default=None, description="Number of solver iterations executed")
    objective_value: float | None = Field(default=None, description="Final optimized objective function value")


class OptimizationResponse(BaseModel):
    """
    Standardized API response for portfolio optimization.
    """

    model_config = ConfigDict(extra="forbid")

    is_success: bool = Field(description="True if optimization converged and produced valid feasible weights")
    portfolio_name: str
    dataset_id: str
    currency: str = Field(default="USD", description="Currency of portfolio asset returns")
    objective: str
    assets: list[str] = Field(description="Assets in exact calculation vector order")
    weights: dict[str, float] = Field(description="Optimized weights mapped by asset identifier")
    metrics: PortfolioMetricsModel | None = Field(
        default=None, description="Independently verified portfolio return and risk metrics"
    )
    is_feasible: bool = Field(description="True if weights satisfy all configured investment constraints")
    constraint_violations: list[str] = Field(
        default_factory=list, description="List of constraint violations if any limits were breached"
    )
    solver_diagnostics: SolverDiagnosticsModel
    annualization: dict[str, Any] = Field(
        description="Annualization parameters (annualized, periods_per_year, risk_free_rate)"
    )
    date_coverage: dict[str, Any] = Field(
        description="Effective historical observation window and common bar count"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-blocking numerical or data quality warnings"
    )
    errors: list[str] = Field(
        default_factory=list, description="Blocking failure reasons or infeasibility explanations"
    )


class FrontierPointModel(BaseModel):
    """
    Representation of an individual portfolio point along the efficient frontier.
    """

    model_config = ConfigDict(extra="forbid")

    target_return: float = Field(description="Requested expected return target")
    actual_return: float = Field(description="Actual expected return computed from optimal weights")
    variance: float = Field(description="Independently calculated variance (w^T Sigma w)", ge=0.0)
    volatility: float = Field(description="Independently calculated volatility sqrt(variance)", ge=0.0)
    sharpe_ratio: float | None = Field(default=None, description="Sharpe ratio if volatility > 0")
    weights: dict[str, float] = Field(description="Asset weights mapped by ticker/asset_id")
    is_feasible: bool = Field(description="Whether weights strictly satisfy all constraints")
    status: str = Field(description="Solver status enum value")
    classification: Literal["efficient", "dominated_inefficient", "infeasible", "failed"] = Field(
        description="Point classification: efficient (upper branch), dominated_inefficient (lower branch), infeasible, or failed"
    )
    solver_message: str = Field(description="Solver status or failure message")
    target_residual: float = Field(description="Absolute residual |actual_return - target_return|", ge=0.0)
    constraint_violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EfficientFrontierRequest(BaseModel):
    """
    Typed request model for generating an efficient frontier.
    """

    model_config = ConfigDict(extra="forbid")

    portfolio: PortfolioDefinition = Field(
        description="Validated portfolio specification with assets, dataset reference, and constraints"
    )
    target_count: int = Field(
        default=20,
        ge=2,
        le=100,
        description="Number of target return points to generate along the feasible spectrum",
    )
    target_returns: list[float] | None = Field(
        default=None,
        description="Optional explicit list of target expected returns to evaluate in exact order",
    )
    risk_free_rate: float = Field(
        default=0.0,
        description="Annual risk-free rate as decimal (e.g. 0.02 for 2.0%)",
    )
    annualized: bool = Field(
        default=True,
        description="Whether returns and volatility are annualized",
    )
    periods_per_year: int = Field(
        default=252,
        ge=1,
        le=365,
        description="Compounding periods per year",
    )


class EfficientFrontierResponse(BaseModel):
    """
    Typed response model for efficient-frontier generation.
    """

    model_config = ConfigDict(extra="forbid")

    is_success: bool = Field(description="True if at least one feasible point was generated")
    portfolio_name: str
    dataset_id: str
    currency: str
    points: list[FrontierPointModel] = Field(description="Evaluated risk-return points")
    global_minimum_variance: FrontierPointModel | None = Field(
        default=None,
        description="Global Minimum-Variance (GMV) portfolio anchor",
    )
    requested_count: int = Field(description="Total number of target returns requested", ge=0)
    successful_count: int = Field(description="Number of feasible frontier points found", ge=0)
    failed_count: int = Field(description="Number of failed or infeasible points", ge=0)
    is_complete: bool = Field(description="True if 100% of requested target returns succeeded")
    min_feasible_return: float | None = Field(default=None, description="Exact lower bound on achievable return")
    max_feasible_return: float | None = Field(default=None, description="Exact upper bound on achievable return")
    annualization: dict[str, Any] = Field(description="Annualization and risk-free rate parameters")
    date_coverage: dict[str, Any] = Field(description="Historical date range and observation count")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PortfolioRiskSummaryModel(BaseModel):
    """
    Comprehensive historical risk and return metrics for an allocated portfolio.
    """

    model_config = ConfigDict(extra="forbid")

    arithmetic_mean_return: float = Field(description="Historical periodic arithmetic mean return")
    geometric_cumulative_return: float = Field(description="Total compounding cumulative return across observation window")
    annualized_return: float = Field(description="Annualized compound/arithmetic return")
    periodic_volatility: float = Field(description="Periodic return sample standard deviation", ge=0.0)
    annualized_volatility: float = Field(description="Annualized volatility (sigma * sqrt(periods_per_year))", ge=0.0)
    variance: float = Field(description="Periodic return variance", ge=0.0)
    maximum_drawdown: float = Field(description="Peak-to-trough maximum drawdown as positive decimal", ge=0.0)
    downside_deviation: float = Field(description="Sample semi-deviation below MAR", ge=0.0)
    sharpe_ratio: float | None = Field(default=None, description="Annualized Sharpe ratio, or None if volatility near-zero")
    sortino_ratio: float | None = Field(default=None, description="Annualized Sortino ratio, or None if downside deviation is zero")
    mar_annualized: float = Field(description="Minimum Acceptable Return used for Sortino calculation")
    risk_free_rate: float = Field(description="Annual risk-free rate used for Sharpe calculation")
    observation_count: int = Field(description="Number of clean historical return observations", ge=1)
    start_date: str = Field(description="Earliest date of observation period (YYYY-MM-DD)")
    end_date: str = Field(description="Latest date of observation period (YYYY-MM-DD)")
    periods_per_year: int = Field(description="Annualization factor used", ge=1)


class PortfolioComparisonItemModel(BaseModel):
    """
    Risk and performance profile of a specific portfolio allocation within a comparative analysis.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Portfolio label (e.g. 'Global Minimum Variance', 'Maximum Sharpe', 'Equal Weight')")
    weights: dict[str, float] = Field(description="Asset allocation weights")
    metrics: PortfolioMetricsModel = Field(description="Standardized portfolio metrics")
    risk_summary: PortfolioRiskSummaryModel | None = Field(
        default=None,
        description="Comprehensive historical risk summary if historical series is available",
    )
    is_feasible: bool = Field(description="True if weights satisfy constraints")


class PortfolioComparisonRequest(BaseModel):
    """
    Request model for comparing multiple portfolio strategies on identical data.
    """

    model_config = ConfigDict(extra="forbid")

    portfolio: PortfolioDefinition = Field(
        description="Base portfolio definition specifying universe, dataset, and constraints"
    )
    include_gmv: bool = Field(default=True, description="Include Global Minimum-Variance portfolio")
    include_max_sharpe: bool = Field(default=True, description="Include Maximum Sharpe Ratio portfolio")
    include_equal_weight: bool = Field(default=True, description="Include Equal Weight baseline portfolio")
    custom_portfolios: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Optional additional portfolios to compare: dict mapping name to weights dictionary",
    )
    risk_free_rate: float = Field(default=0.0, description="Annual risk-free rate")
    annualized: bool = Field(default=True, description="Annualization flag")
    periods_per_year: int = Field(default=252, ge=1, le=365, description="Periods per year")


class PortfolioComparisonResponse(BaseModel):
    """
    Response model comparing multiple portfolio allocations under identical assumptions.
    """

    model_config = ConfigDict(extra="forbid")

    is_success: bool = Field(description="True if comparison was executed successfully")
    portfolio_name: str
    dataset_id: str
    currency: str
    portfolios: list[PortfolioComparisonItemModel] = Field(description="Comparative list of portfolios")
    annualization: dict[str, Any]
    date_coverage: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


