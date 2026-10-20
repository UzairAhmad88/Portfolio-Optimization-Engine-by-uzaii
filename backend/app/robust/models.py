"""
Robust portfolio optimization schemas and data contracts.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ExpectedReturnUncertaintyRequest(BaseModel):
    model: str = Field(
        default="box",
        description="Uncertainty model type: 'none', 'box', or 'ellipsoidal'",
    )
    confidence_level: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Standard-error scaling multiplier kappa (e.g. 1.96 for ~95% confidence)",
    )
    absolute_radius: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional fixed absolute return uncertainty radius across all assets (e.g. 0.02 = 2%)",
    )


class CovarianceShrinkageRequest(BaseModel):
    target: str = Field(
        default="diagonal",
        description="Structured shrinkage target: 'none', 'diagonal', 'scaled_identity', 'constant_correlation'",
    )
    intensity: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Linear shrinkage intensity lambda in [0.0, 1.0]",
    )


class RobustConstraintsRequest(BaseModel):
    default_min_weight: float = Field(default=0.0, ge=-1.0, le=1.0)
    default_max_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    target_total_weight: float = Field(default=1.0, ge=0.1, le=2.0)
    allow_short: bool = Field(default=False)
    max_gross_exposure: float | None = Field(default=None, ge=0.1, le=5.0)


class RobustOptimizationRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset identifier")
    assets: list[str] = Field(..., min_length=2, max_length=100, description="Asset universe")
    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD")
    objective: str = Field(
        default="max_sharpe",
        description="Robust objective: 'max_sharpe', 'min_variance', 'mean_variance_utility'",
    )
    uncertainty: ExpectedReturnUncertaintyRequest = Field(
        default_factory=ExpectedReturnUncertaintyRequest
    )
    shrinkage: CovarianceShrinkageRequest = Field(
        default_factory=CovarianceShrinkageRequest
    )
    constraints: RobustConstraintsRequest = Field(
        default_factory=RobustConstraintsRequest
    )
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.50)
    risk_aversion: float = Field(default=2.5, ge=0.1, le=20.0)


class PortfolioWeightItem(BaseModel):
    asset_id: str
    baseline_weight: float
    robust_weight: float
    weight_difference: float
    nominal_return: float
    worst_case_return: float
    uncertainty_radius: float


class RobustOptimizationResponse(BaseModel):
    objective: str
    dataset_id: str
    assets: list[str]
    weights: list[PortfolioWeightItem]
    baseline_weights: dict[str, float]
    robust_weights: dict[str, float]
    baseline_metrics: dict[str, Any]
    robust_metrics: dict[str, Any]
    diagnostics: dict[str, Any]
    shrunk_covariance: list[list[float]]
    is_feasible: bool
    solver_status: str
    solver_message: str
    warnings: list[str]


class SensitivityAnalysisRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset identifier")
    assets: list[str] = Field(..., min_length=2, max_length=100)
    start_date: str | None = None
    end_date: str | None = None
    parameter_to_sweep: str = Field(
        default="max_weight",
        description="Parameter to sweep: 'max_weight', 'uncertainty_level', 'shrinkage_intensity'",
    )
    grid_min: float = Field(default=0.20)
    grid_max: float = Field(default=1.0)
    num_steps: int = Field(default=8, ge=3, le=25)
    objective: str = Field(default="max_sharpe")
    uncertainty: ExpectedReturnUncertaintyRequest = Field(
        default_factory=ExpectedReturnUncertaintyRequest
    )
    shrinkage: CovarianceShrinkageRequest = Field(
        default_factory=CovarianceShrinkageRequest
    )
    constraints: RobustConstraintsRequest = Field(
        default_factory=RobustConstraintsRequest
    )
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.50)


class SensitivityPointResponse(BaseModel):
    parameter_value: float
    parameter_label: str
    is_feasible: bool
    solver_status: str
    weights: dict[str, float]
    nominal_expected_return: float
    worst_case_expected_return: float
    volatility: float
    sharpe_ratio: float | None
    weight_distance_d1: float
    hhi: float
    effective_assets: float
    binding_constraints: list[str]


class SensitivityAnalysisResponse(BaseModel):
    parameter_name: str
    parameter_description: str
    baseline_value: float
    points: list[SensitivityPointResponse]
    total_evaluations: int
    feasible_evaluations: int
    infeasible_evaluations: int
    warnings: list[str]


class RobustBacktestRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset identifier")
    assets: list[str] = Field(..., min_length=2, max_length=100)
    train_end_date: str = Field(
        ...,
        description="Date (YYYY-MM-DD) separating in-sample estimation and out-of-sample evaluation",
    )
    objective: str = Field(default="max_sharpe")
    uncertainty: ExpectedReturnUncertaintyRequest = Field(
        default_factory=ExpectedReturnUncertaintyRequest
    )
    shrinkage: CovarianceShrinkageRequest = Field(
        default_factory=CovarianceShrinkageRequest
    )
    constraints: RobustConstraintsRequest = Field(
        default_factory=RobustConstraintsRequest
    )
    rebalance_frequency: str = Field(default="monthly")
    cost_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.50)


class RobustBacktestResponse(BaseModel):
    dataset_id: str
    assets: list[str]
    train_period: dict[str, str]
    test_period: dict[str, str]
    baseline_weights: dict[str, float]
    robust_weights: dict[str, float]
    weight_distance_d1: float
    baseline_kpis: dict[str, Any]
    robust_kpis: dict[str, Any]
    out_of_sample_comparison: dict[str, Any]
    equity_curves: list[dict[str, Any]]
    warnings: list[str]
