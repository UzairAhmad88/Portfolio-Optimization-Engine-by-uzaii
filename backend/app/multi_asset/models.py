"""
Pydantic Models for Multi-Asset Class Allocation, Cash Drag & FX Hedging.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class AssetMetadata(BaseModel):
    ticker: str
    asset_class: Literal["Equity", "Fixed Income", "Commodity", "Real Estate", "Other"] = "Equity"
    currency: str = "USD"


class MultiAssetOptimizeRequest(BaseModel):
    dataset_id: str
    base_currency: str = "USD"
    assets_metadata: list[AssetMetadata] = Field(default_factory=list)
    hedge_ratios: dict[str, float] = Field(default_factory=dict)
    carry_rates: dict[str, float] = Field(default_factory=dict)
    asset_class_limits: dict[str, dict[str, float]] = Field(default_factory=dict)
    min_cash_weight: float = Field(0.05, ge=0.0, le=1.0)
    max_cash_weight: float = Field(0.25, ge=0.0, le=1.0)
    min_asset_weight: float = Field(0.0, ge=0.0, le=1.0)
    max_asset_weight: float = Field(1.0, ge=0.0, le=1.0)
    objective: Literal["max_sharpe", "min_variance", "risk_parity"] = "max_sharpe"
    risk_free_rate: float = Field(0.03, ge=0.0, le=0.20)
    start_date: str | None = None
    end_date: str | None = None


class FxRiskDecomposition(BaseModel):
    asset_local_variance: float
    fx_currency_variance: float
    cross_covariance: float
    total_unhedged_variance: float
    asset_risk_share_pct: float
    fx_risk_share_pct: float
    unhedged_volatility: float
    local_asset_volatility: float


class MultiAssetOptimizeResponse(BaseModel):
    risky_weights: dict[str, float]
    cash_weight: float
    asset_class_allocations: dict[str, float]
    expected_annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    fx_risk_decomposition: FxRiskDecomposition
    is_feasible: bool
    solver_message: str


class MultiAssetBacktestRequest(BaseModel):
    dataset_id: str
    base_currency: str = "USD"
    assets_metadata: list[AssetMetadata] = Field(default_factory=list)
    hedge_ratios: dict[str, float] = Field(default_factory=dict)
    carry_rates: dict[str, float] = Field(default_factory=dict)
    asset_class_limits: dict[str, dict[str, float]] = Field(default_factory=dict)
    min_cash_weight: float = Field(0.05, ge=0.0, le=1.0)
    max_cash_weight: float = Field(0.25, ge=0.0, le=1.0)
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly"
    estimation_window: int = Field(60, ge=20, le=252)
    objective: Literal["max_sharpe", "min_variance", "risk_parity"] = "max_sharpe"
    risk_free_rate: float = Field(0.03, ge=0.0, le=0.20)
    transaction_cost_bps: float = Field(10.0, ge=0.0, le=100.0)
    slippage_bps: float = Field(5.0, ge=0.0, le=100.0)
    initial_capital: float = Field(100000.0, gt=0.0)
    start_date: str | None = None
    end_date: str | None = None


class MultiAssetSummaryMetrics(BaseModel):
    initial_capital: float
    final_equity: float
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    total_turnover: float
    total_transaction_costs: float
    total_rebalances: int
    active_return: float
    tracking_error: float
    information_ratio: float
    total_cash_drag: float


class MultiAssetBenchmarkMetrics(BaseModel):
    final_equity: float
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float


class MultiAssetEquityPoint(BaseModel):
    date: str
    portfolio_equity: float
    benchmark_equity: float
    portfolio_return: float
    benchmark_return: float
    drawdown: float
    cash_drag: float


class MultiAssetRebalanceEvent(BaseModel):
    date: str
    risky_weights: dict[str, float]
    cash_weight: float
    asset_class_allocations: dict[str, float]
    turnover: float
    cost_incurred: float
    is_feasible: bool
    solver_message: str


class MultiAssetBacktestResponse(BaseModel):
    summary: MultiAssetSummaryMetrics
    benchmark: MultiAssetBenchmarkMetrics
    fx_risk_decomposition: FxRiskDecomposition
    equity_curve: list[MultiAssetEquityPoint]
    rebalance_history: list[MultiAssetRebalanceEvent]
    asset_class_allocation_history: list[dict[str, Any]]
