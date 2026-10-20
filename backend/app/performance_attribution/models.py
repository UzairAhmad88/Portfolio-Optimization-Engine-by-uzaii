"""
Pydantic v2 schemas for Multi-Asset Performance Attribution,
Brinson-Fachler Decomposition, and Systematic Factor Risk Attribution.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class BrinsonAttributionRequest(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")
    portfolio_weights: dict[str, float] = Field(..., description="Target or realized portfolio weights by ticker")
    benchmark_weights: dict[str, float] = Field(..., description="Benchmark weights by ticker")
    segment_mapping: dict[str, str] | None = Field(
        default=None,
        description="Optional mapping from ticker to segment (e.g. Sector or Asset Class). Defaults to ticker names if omitted.",
    )
    frequency: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly", description="Sub-period compounding interval"
    )
    method: Literal["brinson_fachler", "brinson_hood_beebower"] = Field(
        default="brinson_fachler", description="Attribution formulation methodology"
    )
    start_date: str | None = Field(default=None, description="Optional ISO start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="Optional ISO end date YYYY-MM-DD")


class SegmentAttributionItem(BaseModel):
    segment: str
    average_portfolio_weight: float
    average_benchmark_weight: float
    active_weight: float
    linked_allocation_effect: float
    linked_selection_effect: float
    linked_interaction_effect: float
    total_contribution: float


class AttributionTimeSeriesPoint(BaseModel):
    period_index: int
    start_date: str
    end_date: str
    portfolio_return: float
    benchmark_return: float
    active_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float


class BrinsonAttributionSummary(BaseModel):
    cumulative_portfolio_return: float
    cumulative_benchmark_return: float
    cumulative_active_return: float
    total_allocation_effect: float
    total_selection_effect: float
    total_interaction_effect: float
    reconciliation_error: float
    total_periods: int


class BrinsonAttributionResponse(BaseModel):
    dataset_id: str
    method: str
    frequency: str
    summary: BrinsonAttributionSummary
    segment_attribution: list[SegmentAttributionItem]
    time_series: list[AttributionTimeSeriesPoint]


class FactorAttributionRequest(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")
    portfolio_weights: dict[str, float] = Field(..., description="Portfolio weights by ticker")
    benchmark_weights: dict[str, float] = Field(..., description="Benchmark weights by ticker")
    factor_model: Literal["capm", "fama_french_3", "carhart_4", "pca"] = Field(
        default="fama_french_3", description="Systematic factor risk model architecture"
    )
    annualization_factor: int = Field(default=252, ge=1, le=365, description="Annualization factor for trading days")
    start_date: str | None = Field(default=None, description="Optional ISO start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="Optional ISO end date YYYY-MM-DD")


class FactorContributionItem(BaseModel):
    factor: str
    portfolio_beta: float
    benchmark_beta: float
    active_beta: float
    annualized_factor_return: float
    annualized_contribution: float


class FactorAttributionResponse(BaseModel):
    dataset_id: str
    factor_model: str
    annualized_portfolio_return: float
    annualized_benchmark_return: float
    total_active_return: float
    systematic_active_return: float
    specific_active_return: float
    total_tracking_error: float
    systematic_tracking_error: float
    specific_tracking_error: float
    systematic_risk_percent: float
    specific_risk_percent: float
    factor_contributions: list[FactorContributionItem]
