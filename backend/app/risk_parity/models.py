"""
Pydantic Request and Response models for Risk Parity and Hierarchical Risk Parity.
"""

from __future__ import annotations

from typing import Literal, Any
from pydantic import BaseModel, Field


class RiskParityConstraints(BaseModel):
    default_min_weight: float = Field(0.0, ge=0.0, le=1.0, description="Minimum single asset weight.")
    default_max_weight: float = Field(1.0, ge=0.0, le=1.0, description="Maximum single asset weight.")


class RiskParityOptimizeRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset ID containing asset price bars.")
    method: Literal["erc", "hrp", "inverse_variance", "equal_weight"] = Field(
        "erc",
        description="Optimization method: 'erc' (Equal Risk Contribution), 'hrp' (Hierarchical Risk Parity), 'inverse_variance', or 'equal_weight'.",
    )
    linkage_method: Literal["single", "complete", "average"] = Field(
        "single",
        description="Hierarchical clustering linkage method for HRP.",
    )
    custom_risk_budgets: dict[str, float] | None = Field(
        None,
        description="Optional custom percentage risk budgets summing to 1.0 (for ERC).",
    )
    constraints: RiskParityConstraints = Field(
        default_factory=RiskParityConstraints,
        description="Weight bounds for ERC optimization.",
    )


class RiskParityOptimizeResponse(BaseModel):
    dataset_id: str
    method: str
    asset_order: list[str]
    weights: dict[str, float]
    marginal_risk_contributions: dict[str, float]
    total_risk_contributions: dict[str, float]
    percentage_risk_contributions: dict[str, float]
    portfolio_volatility: float
    risk_gini_coefficient: float
    effective_number_of_bets: float
    effective_number_of_constituents: float
    diversification_ratio: float
    herfindahl_index: float
    reordered_indices: list[int] | None = None
    is_feasible: bool
    solver_status: str
    solver_message: str


class RiskParityBacktestRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset ID.")
    method: Literal["erc", "hrp", "inverse_variance", "equal_weight"] = Field(
        "erc",
        description="Strategy method to evaluate out-of-sample.",
    )
    linkage_method: Literal["single", "complete", "average"] = Field("single")
    split_date: str = Field(
        ...,
        description="In-sample training cut-off date (YYYY-MM-DD). Backtest executes on dates > split_date.",
    )
    rebalance_frequency: Literal["daily", "weekly", "monthly", "quarterly"] = Field("monthly")
    transaction_cost_bps: float = Field(10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(5.0, ge=0.0, le=500.0)
    initial_cash: float = Field(100_000.0, gt=0.0)


class RiskParityBacktestComparisonMetrics(BaseModel):
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    calmar_ratio: float | None
    total_net_return: float
    total_transaction_costs: float
    total_slippage_costs: float
    rebalance_count: int


class RiskParityBacktestResponse(BaseModel):
    dataset_id: str
    method: str
    split_date: str
    in_sample_end: str
    out_of_sample_start: str
    out_of_sample_end: str
    strategy_metrics: RiskParityBacktestComparisonMetrics
    equal_weight_benchmark_metrics: RiskParityBacktestComparisonMetrics
    strategy_weights: dict[str, float]
    equity_curve: list[dict[str, Any]]
    drawdown_curve: list[dict[str, Any]]
