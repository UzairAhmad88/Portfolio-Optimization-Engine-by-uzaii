"""
Pydantic v2 schemas for Regime-Switching HMM State Detection and Walk-Forward Backtesting.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class RegimeDetectionRequest(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")
    tickers: list[str] | None = Field(default=None, description="Optional subset of tickers; defaults to all assets")
    num_states: int = Field(default=2, ge=2, le=3, description="Number of latent regimes (2 or 3)")
    max_iter: int = Field(default=100, ge=10, le=500, description="Maximum Baum-Welch EM iterations")
    tolerance: float = Field(default=1e-4, ge=1e-8, le=1e-2, description="Convergence tolerance")


class RegimeTimelinePoint(BaseModel):
    date: str
    return_val: float
    state: int
    state_label: str
    filtered_prob: list[float]
    smoothed_prob: list[float]


class RegimeDetectionResponse(BaseModel):
    dataset_id: str
    num_states: int
    state_labels: list[str]
    transition_matrix: list[list[float]]
    state_means: list[float]
    state_volatilities_annual: list[float]
    current_state: int
    current_state_label: str
    current_regime_probabilities: list[float]
    timeline: list[RegimeTimelinePoint]


class RegimeBacktestRequest(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")
    tickers: list[str] | None = Field(default=None, description="Assets included in backtest universe")
    num_states: int = Field(default=2, ge=2, le=3, description="Number of latent regimes (2 or 3)")
    target_volatility: float = Field(default=0.10, ge=0.01, le=1.0, description="Target annualized volatility (e.g. 0.10 for 10%)")
    max_leverage: float = Field(default=1.5, ge=1.0, le=2.5, description="Maximum gross leverage cap")
    rebalance_frequency: Literal["daily", "weekly", "monthly"] = Field(default="monthly", description="Rebalancing schedule")
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=500.0, description="Transaction fee in basis points")
    lookback_window: int = Field(default=252, ge=60, le=1000, description="Rolling estimation window in trading days")
    risk_free_rate: float = Field(default=0.04, ge=0.0, le=0.20, description="Annualized risk-free rate")


class RegimeEquityPoint(BaseModel):
    date: str
    portfolio_equity: float
    benchmark_equity: float
    cash_weight: float
    leverage: float
    regime_state: int


class RegimeRebalanceEvent(BaseModel):
    date: str
    regime_state: int
    regime_probs: list[float]
    scaling_factor: float
    cash_weight: float
    turnover: float
    fee_deducted: float


class RegimeBacktestSummary(BaseModel):
    initial_equity: float
    final_equity: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    benchmark_cagr: float
    benchmark_volatility: float
    benchmark_sharpe: float
    target_volatility: float
    max_leverage: float
    total_rebalances: int


class RegimeBacktestResponse(BaseModel):
    dataset_id: str
    summary: RegimeBacktestSummary
    equity_curve: list[RegimeEquityPoint]
    rebalance_events: list[RegimeRebalanceEvent]
