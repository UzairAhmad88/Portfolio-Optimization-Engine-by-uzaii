"""Pydantic v2 schemas for Execution and Market Impact Modeling."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class OptimalExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_size: float = Field(..., gt=0, description="Total number of shares or units to execute.")
    asset_price: float = Field(..., gt=0, description="Initial spot arrival price.")
    daily_volume: float = Field(..., gt=0, description="Average daily volume (ADV) in shares.")
    daily_volatility: float = Field(..., gt=0, description="Daily asset volatility in price units.")
    bid_ask_spread: float = Field(default=0.0, ge=0, description="Quoted bid-ask spread in currency units.")
    horizon_periods: int = Field(default=10, ge=2, le=100, description="Number of execution intervals N.")
    trading_hours: float = Field(default=6.5, gt=0, le=24, description="Total trading window in hours.")
    risk_aversion: float = Field(default=1e-6, ge=0, description="Trader risk aversion parameter lambda.")
    temporary_impact_factor: float | None = Field(default=None, gt=0, description="Custom temporary impact eta.")
    permanent_impact_factor: float | None = Field(default=None, ge=0, description="Custom permanent impact gamma.")
    volume_profile: list[float] | None = Field(default=None, description="Intraday volume fractions summing to 1.0.")


class ExecutionSchedulePoint(BaseModel):
    period: int
    time_elapsed_hours: float
    time_elapsed_pct: float
    almgren_chriss_shares: float
    almgren_chriss_remaining: float
    twap_shares: float
    twap_remaining: float
    vwap_shares: float
    vwap_remaining: float
    volume_weight_pct: float


class ExecutionSummaryMetrics(BaseModel):
    urgency_parameter: float
    half_life_hours: float
    expected_cost: float
    expected_cost_bps: float
    timing_risk_variance: float
    timing_risk_std: float
    execution_utility: float
    twap_expected_cost: float
    twap_expected_cost_bps: float
    twap_timing_risk_std: float
    twap_utility: float
    vwap_expected_cost: float
    vwap_expected_cost_bps: float
    cost_savings_vs_twap: float
    cost_savings_vs_twap_bps: float


class OptimalExecutionResponse(BaseModel):
    parameters: dict[str, Any]
    summary: ExecutionSummaryMetrics
    schedule: list[ExecutionSchedulePoint]


class RebalanceImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(..., description="Persistent dataset identifier.")
    target_weights: dict[str, float] = Field(..., description="Target asset weights summing to <= 1.0.")
    current_weights: dict[str, float] | None = Field(default=None, description="Current drifted asset weights.")
    portfolio_equity: float = Field(default=1_000_000.0, gt=0, description="Total portfolio value in base currency.")
    execution_horizon_days: float = Field(default=1.0, ge=0.1, le=20.0, description="Trading days allocated to rebalance.")
    impact_model: Literal["square_root", "linear", "fixed_bps"] = Field(
        default="square_root", description="Market impact model archetype."
    )
    spread_bps_override: dict[str, float] | None = Field(
        default=None, description="Optional per-ticker bid-ask spread overrides in basis points."
    )


class AssetImpactMetrics(BaseModel):
    ticker: str
    traded_notional: float
    adv: float
    participation_rate_pct: float
    spread_cost: float
    temporary_impact_cost: float
    permanent_impact_cost: float
    total_cost: float
    total_cost_bps: float


class RebalanceImpactSummary(BaseModel):
    impact_model: str
    execution_horizon_days: float
    total_traded_notional: float
    total_spread_cost: float
    total_temporary_impact_cost: float
    total_permanent_impact_cost: float
    total_impact_cost: float
    effective_cost_bps: float


class RebalanceImpactResponse(BaseModel):
    summary: RebalanceImpactSummary
    asset_impacts: list[AssetImpactMetrics]
