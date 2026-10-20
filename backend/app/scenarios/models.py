"""
Pydantic typed models for Scenario Analysis, Stress Testing & Sensitivity Analysis.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


ScenarioType = Literal["custom_asset_shock", "historical_window", "covariance_stress"]


class AssetShockContribution(BaseModel):
    """
    Detailed attribution of a single asset's response to a shock.
    """
    asset_id: str
    ticker: str
    baseline_weight: float
    baseline_value: float
    shock_pct: float
    stressed_value: float
    value_change: float
    return_contribution: float
    share_of_total_change: float


class ScenarioSummaryMetrics(BaseModel):
    """
    Aggregated portfolio-level shock and stress metrics.
    """
    baseline_portfolio_value: float
    stressed_portfolio_value: float
    absolute_change: float
    percentage_change: float
    currency: str
    cash_value: float
    baseline_volatility: float | None = None
    stressed_volatility: float | None = None
    volatility_change: float | None = None


class ScenarioRequest(BaseModel):
    """
    User request to execute an instantaneous shock, historical window stress, or covariance stress.
    """
    dataset_id: str = Field(..., description="Target dataset ID")
    name: str = Field(..., min_length=1, max_length=150, description="User-assigned scenario title")
    scenario_type: ScenarioType = Field(default="custom_asset_shock")
    assets: list[str] = Field(..., min_length=1, description="List of asset tickers or composite IDs")
    weights: dict[str, float] = Field(..., description="Asset allocation weights summing to <= 1.0")
    initial_capital: float = Field(default=100000.0, gt=0, description="Base portfolio capital")
    
    # Custom Shock Inputs
    asset_shocks: dict[str, float] | None = Field(
        default=None,
        description="Dictionary mapping asset -> fractional shock (e.g. -0.15 for -15%)"
    )
    
    # Historical Window Inputs
    historical_start_date: str | None = Field(
        default=None,
        description="Start date for historical return extraction (YYYY-MM-DD)"
    )
    historical_end_date: str | None = Field(
        default=None,
        description="End date for historical return extraction (YYYY-MM-DD)"
    )
    
    # Covariance Stress Inputs
    volatility_multiplier: float | None = Field(
        default=None,
        gt=0,
        description="Factor to scale asset volatilities (e.g. 1.50 for +50% vol)"
    )
    correlation_multiplier: float | None = Field(
        default=None,
        gt=0,
        le=2.0,
        description="Factor to scale off-diagonal correlations (e.g. 1.25)"
    )
    auto_project_psd: bool = Field(
        default=True,
        description="Whether to project stressed covariance matrix to positive semi-definite"
    )

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("Weights dictionary cannot be empty.")
        total_w = sum(v.values())
        if total_w > 1.000001:
            raise ValueError(f"Sum of asset weights ({total_w:.6f}) exceeds 1.0.")
        for k, w in v.items():
            if w < -1e-6:
                raise ValueError(f"Negative weight ({w}) for asset '{k}' is not supported in long-only mode.")
        return v


class ScenarioResponse(BaseModel):
    """
    Complete response containing scenario results, contributions, and governance metadata.
    """
    id: str
    dataset_id: str
    name: str
    scenario_type: str
    status: str = "completed"
    created_at: str
    metrics: ScenarioSummaryMetrics
    contributions: list[AssetShockContribution]
    warnings: list[str] = Field(default_factory=list)
    is_hypothetical: bool = True
    disclaimer: str = (
        "Hypothetical scenario results are instantaneous mathematical projections based on user-supplied "
        "or historical assumptions. They do not constitute investment advice, forecasts, or guarantees of future performance."
    )


class SensitivityGridPoint(BaseModel):
    """
    Single evaluation point on a 1D curve or 2D grid.
    """
    factor_1_value: float
    factor_2_value: float | None = None
    stressed_portfolio_value: float
    percentage_change: float
    absolute_change: float


class SensitivityRequest(BaseModel):
    """
    Request for a 1-factor or 2-factor parametric sensitivity sweep.
    """
    dataset_id: str
    name: str = Field(default="Portfolio Sensitivity Analysis", min_length=1, max_length=150)
    assets: list[str] = Field(..., min_length=1)
    weights: dict[str, float]
    initial_capital: float = Field(default=100000.0, gt=0)
    
    # Factor 1
    factor_1_asset: str
    factor_1_min_shock: float = Field(default=-0.30, ge=-1.0, le=2.0)
    factor_1_max_shock: float = Field(default=0.30, ge=-1.0, le=2.0)
    factor_1_steps: int = Field(default=13, ge=2, le=101)
    
    # Factor 2 (Optional)
    factor_2_asset: str | None = None
    factor_2_min_shock: float | None = Field(default=None, ge=-1.0, le=2.0)
    factor_2_max_shock: float | None = Field(default=None, ge=-1.0, le=2.0)
    factor_2_steps: int | None = Field(default=None, ge=2, le=21)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("Weights dictionary cannot be empty.")
        total_w = sum(v.values())
        if total_w > 1.000001:
            raise ValueError(f"Sum of asset weights ({total_w:.6f}) exceeds 1.0.")
        return v


class SensitivityResponse(BaseModel):
    """
    Output of a 1D or 2D sensitivity analysis.
    """
    id: str
    dataset_id: str
    name: str
    factor_1_asset: str
    factor_2_asset: str | None = None
    grid: list[SensitivityGridPoint]
    baseline_portfolio_value: float
    currency: str
    warnings: list[str] = Field(default_factory=list)
    is_hypothetical: bool = True


class ScenarioListItem(BaseModel):
    """
    Summary view of a saved scenario run for listing.
    """
    id: str
    dataset_id: str
    user_id: str | None = None
    name: str
    scenario_type: str
    percentage_change: float
    absolute_change: float
    currency: str
    created_at: str
