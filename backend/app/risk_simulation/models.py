"""
Pydantic schemas and typed models for Monte Carlo simulation and probabilistic risk analysis.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DistributionModel(str, Enum):
    """Supported joint return distributions."""
    MULTIVARIATE_NORMAL = "multivariate_normal"
    MULTIVARIATE_STUDENT_T = "multivariate_student_t"


class RebalancePolicy(str, Enum):
    """Portfolio rebalancing convention during path simulation."""
    BUY_AND_HOLD = "buy_and_hold"
    CONSTANT_WEIGHTS = "constant_weights"


class VaRCVaREstimate(BaseModel):
    """Value at Risk and Conditional Value at Risk metrics at a specific confidence level."""
    confidence_level: float = Field(..., ge=0.5, le=0.9999, description="Quantile confidence level (e.g. 0.95)")
    var_absolute: float = Field(..., description="Monetary Value at Risk (positive number represents loss)")
    var_percentage: float = Field(..., description="Percentage Value at Risk relative to initial capital")
    cvar_absolute: float = Field(..., description="Monetary Conditional Value at Risk")
    cvar_percentage: float = Field(..., description="Percentage Conditional Value at Risk")


class MultiEstimatorComparison(BaseModel):
    """Comparative breakdown of VaR and CVaR across Monte Carlo, Parametric, and Historical estimators."""
    confidence_level: float
    monte_carlo_var: float
    monte_carlo_cvar: float
    parametric_var: float
    parametric_cvar: float
    historical_var: float | None = None
    historical_cvar: float | None = None


class SimulationPathPoint(BaseModel):
    """Point in time along the simulation horizon capturing distribution envelope and sample paths."""
    day: int
    median_value: float
    percentile_5: float
    percentile_95: float
    sample_paths: list[float] = Field(default_factory=list, description="Downsampled individual simulated paths")


class DistributionBin(BaseModel):
    """Histogram bin for terminal returns or losses."""
    bin_start: float
    bin_end: float
    count: int
    relative_frequency: float


class RiskSimulationSummary(BaseModel):
    """Comprehensive statistical summary of Monte Carlo simulated terminal wealth and losses."""
    initial_capital: float
    expected_terminal_value: float
    median_terminal_value: float
    expected_terminal_return: float
    terminal_return_volatility: float
    terminal_quantiles: dict[str, float] = Field(
        default_factory=dict,
        description="Key percentiles: p1, p5, p10, p25, p50, p75, p90, p95, p99",
    )
    prob_negative_return: float = Field(..., ge=0.0, le=1.0, description="P(V_T < V_0)")
    prob_exceed_threshold: float | None = Field(None, ge=0.0, le=1.0, description="P(Loss > user_threshold)")
    min_terminal_value: float = Field(..., description="Observed sample minimum terminal wealth")
    max_terminal_value: float = Field(..., description="Observed sample maximum terminal wealth")
    var_cvar_metrics: list[VaRCVaREstimate]
    estimator_comparisons: list[MultiEstimatorComparison]
    currency: str


class RiskSimulationRequest(BaseModel):
    """Request payload for running a Monte Carlo portfolio risk simulation."""
    dataset_id: str = Field(..., min_length=1, description="Source market dataset ID")
    name: str = Field(..., min_length=1, max_length=150, description="User-assigned scenario/simulation name")
    assets: list[str] = Field(..., min_length=1, description="Constituent asset identifiers")
    weights: dict[str, float] = Field(..., description="Asset allocation weights summing to <= 1.0")
    initial_capital: float = Field(100000.0, gt=0.0, description="Initial portfolio valuation")
    horizon_days: int = Field(21, ge=1, le=252, description="Simulation horizon in trading days")
    num_paths: int = Field(1000, ge=100, le=10000, description="Number of Monte Carlo paths to generate")
    confidence_levels: list[float] = Field(
        default=[0.95, 0.99],
        min_length=1,
        description="Confidence levels for VaR and CVaR",
    )
    distribution: DistributionModel = Field(
        default=DistributionModel.MULTIVARIATE_NORMAL,
        description="Joint return distribution assumption",
    )
    degrees_of_freedom: float = Field(
        5.0,
        ge=2.5,
        le=30.0,
        description="Degrees of freedom for Student-t distribution",
    )
    rebalance_policy: RebalancePolicy = Field(
        default=RebalancePolicy.BUY_AND_HOLD,
        description="Portfolio compounding / rebalancing convention",
    )
    seed: int | None = Field(None, ge=0, le=2147483647, description="Optional integer seed for exact determinism")
    loss_threshold: float | None = Field(None, description="Optional monetary loss threshold to compute exceedance probability")
    custom_expected_returns: dict[str, float] | None = Field(None, description="Optional override periodic returns")


class RiskSimulationResponse(BaseModel):
    """Response payload containing full Monte Carlo simulation results."""
    id: str
    dataset_id: str
    name: str
    distribution: str
    rebalance_policy: str
    horizon_days: int
    num_paths: int
    seed: int
    summary: RiskSimulationSummary
    distribution_bins: list[DistributionBin]
    trajectory: list[SimulationPathPoint]
    warnings: list[str] = Field(default_factory=list)
    is_hypothetical: bool = True
    disclaimer: str = (
        "Hypothetical simulation based on estimated parameters and mathematical models. "
        "Outputs do not predict future performance and cannot account for unprecedented market disruptions."
    )
    created_at: str


class RiskSimulationListItem(BaseModel):
    """Brief summary item for listing stored simulation runs."""
    id: str
    dataset_id: str
    user_id: str | None = None
    name: str
    distribution: str
    horizon_days: int
    num_paths: int
    expected_terminal_return: float
    var_95: float
    cvar_95: float
    currency: str
    created_at: str


class VaRCVaRStandaloneRequest(BaseModel):
    """Request payload for on-the-fly analytical or empirical VaR/CVaR calculations."""
    dataset_id: str = Field(..., min_length=1)
    assets: list[str] = Field(..., min_length=1)
    weights: dict[str, float]
    initial_capital: float = Field(100000.0, gt=0.0)
    horizon_days: int = Field(1, ge=1, le=252)
    confidence_levels: list[float] = Field(default=[0.95, 0.99], min_length=1)
