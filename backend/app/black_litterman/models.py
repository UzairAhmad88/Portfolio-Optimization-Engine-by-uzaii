"""
Black-Litterman request and response schemas and data contracts.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ViewItem(BaseModel):
    view_type: str = Field(
        default="relative",
        description="Type of view: 'absolute' or 'relative'",
    )
    assets: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Assets involved in view. For relative: [asset_long, asset_short]. For absolute: [asset].",
    )
    weights: list[float] = Field(
        default_factory=lambda: [1.0, -1.0],
        description="Pick matrix weights P_k for the assets. Sums to 0 for relative, 1 for absolute.",
    )
    target_return: float = Field(
        ...,
        description="Annualized return target q_k (e.g. 0.03 = 3% outperformance or absolute return).",
    )
    confidence: float = Field(
        default=0.50,
        ge=0.01,
        le=0.99,
        description="Analyst confidence in the view in [0.01, 0.99] (used in Idzorek uncertainty scaling).",
    )


class BlackLittermanConstraints(BaseModel):
    default_min_weight: float = Field(default=0.0, ge=-1.0, le=1.0)
    default_max_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    target_total_weight: float = Field(default=1.0, ge=0.1, le=2.0)
    allow_short: bool = Field(default=False)
    max_gross_exposure: float = Field(default=1.0, ge=0.1, le=5.0)


class BlackLittermanOptimizeRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset identifier")
    assets: list[str] = Field(..., min_length=2, max_length=100, description="Asset universe")
    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD")
    tau: float = Field(default=0.05, ge=0.001, le=1.0, description="Prior uncertainty scalar tau")
    risk_aversion: float = Field(default=2.50, ge=0.1, le=20.0, description="Market risk aversion gamma")
    equilibrium_weights: dict[str, float] | None = Field(
        default=None,
        description="Optional equilibrium or benchmark weights w_eq. Defaults to equal-weight 1/N.",
    )
    views: list[ViewItem] = Field(
        default_factory=list,
        max_length=25,
        description="List of analyst/quantitative views",
    )
    objective: str = Field(
        default="max_sharpe",
        description="Optimization objective: 'max_sharpe', 'min_variance', 'mean_variance_utility'",
    )
    constraints: BlackLittermanConstraints = Field(
        default_factory=BlackLittermanConstraints
    )
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.50)


class ViewSummaryItem(BaseModel):
    description: str
    view_type: str
    confidence: float
    target_return: float
    prior_expected_spread: float
    posterior_expected_spread: float
    absorbed_difference: float


class BlackLittermanOptimizeResponse(BaseModel):
    dataset_id: str
    assets: list[str]
    equilibrium_returns: dict[str, float]
    posterior_returns: dict[str, float]
    prior_weights: dict[str, float]
    unconstrained_bl_weights: dict[str, float]
    optimal_weights: dict[str, float]
    active_tilts: dict[str, float]
    portfolio_metrics: dict[str, Any]
    diagnostics: dict[str, Any]
    views_summary: list[ViewSummaryItem]
    is_feasible: bool
    solver_status: str
    solver_message: str
    warnings: list[str]


class BlackLittermanBacktestRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset identifier")
    assets: list[str] = Field(..., min_length=2, max_length=100)
    train_end_date: str = Field(..., description="In-sample training end date (YYYY-MM-DD)")
    tau: float = Field(default=0.05, ge=0.001, le=1.0)
    risk_aversion: float = Field(default=2.50, ge=0.1, le=20.0)
    equilibrium_weights: dict[str, float] | None = None
    views: list[ViewItem] = Field(default_factory=list, max_length=25)
    objective: str = Field(default="max_sharpe")
    min_weight: float = Field(default=0.0, ge=-1.0, le=1.0)
    max_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    rebalance_frequency: str = Field(default="monthly")
    cost_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.50)


class BlackLittermanBacktestResponse(BaseModel):
    dataset_id: str
    assets: list[str]
    train_period: dict[str, str]
    test_period: dict[str, str]
    equilibrium_weights: dict[str, float]
    optimal_weights: dict[str, float]
    active_tilts: dict[str, float]
    equilibrium_kpis: dict[str, Any]
    black_litterman_kpis: dict[str, Any]
    equity_curves: list[dict[str, Any]]
    warnings: list[str]
