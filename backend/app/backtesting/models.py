"""
Pydantic schemas and domain models for backtesting simulation requests and responses.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

StrategyType = Literal["target_weights", "equal_weight", "walk_forward_optimization"]
RebalanceFrequency = Literal["buy_and_hold", "daily", "weekly", "monthly", "quarterly"]
OptimizationObjective = Literal["min_variance", "max_sharpe"]


class BacktestRequest(BaseModel):
    dataset_id: str = Field(description="UUID of the authoritative persistent market dataset.")
    name: str = Field(default="Portfolio Backtest", min_length=1, max_length=150)
    strategy_type: StrategyType = Field(
        default="target_weights",
        description="Strategy archetype: 'target_weights', 'equal_weight', or 'walk_forward_optimization'.",
    )
    assets: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Asset identifiers (tickers or composite TICKER:MARKET) in portfolio universe.",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description="Target portfolio weights for 'target_weights' strategy. Must sum to 1.0.",
    )
    rebalance_frequency: RebalanceFrequency = Field(
        default="monthly",
        description="Rebalancing schedule: 'buy_and_hold', 'daily', 'weekly', 'monthly', or 'quarterly'.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0.0,
        description="Starting portfolio equity in dataset currency.",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        le=1000.0,
        description="Brokerage/commission fee in basis points applied to traded notional (10 bps = 0.1%).",
    )
    slippage_bps: float = Field(
        default=5.0,
        ge=0.0,
        le=1000.0,
        description="Execution price slippage drag in basis points applied to traded notional (5 bps = 0.05%).",
    )
    start_date: date | None = Field(
        default=None,
        description="Inclusive start date for backtest period (ISO format YYYY-MM-DD).",
    )
    end_date: date | None = Field(
        default=None,
        description="Inclusive end date for backtest period (ISO format YYYY-MM-DD).",
    )
    training_window: int = Field(
        default=126,
        ge=20,
        le=2520,
        description="Lookback training window in trading days for walk-forward optimization.",
    )
    test_window: int = Field(
        default=21,
        ge=1,
        le=252,
        description="Out-of-sample holding window in trading days before re-optimizing.",
    )
    optimization_objective: OptimizationObjective = Field(
        default="max_sharpe",
        description="Optimization objective for walk-forward model: 'min_variance' or 'max_sharpe'.",
    )
    risk_free_rate: float = Field(
        default=0.02,
        ge=-0.1,
        le=1.0,
        description="Annualized risk-free benchmark rate for Sharpe ratio calculation.",
    )
    use_point_in_time: bool = Field(
        default=False,
        description="When True, dynamically resolves corporate actions under point-in-time cutoffs.",
    )
    as_of_date: date | None = Field(
        default=None,
        description="Point-in-time information availability cutoff date for corporate actions.",
    )
    strict_pit: bool = Field(
        default=False,
        description="When True, fails closed if any corporate action lacks verified announcement date.",
    )
    adjustment_type: str = Field(
        default="total",
        description="Adjustment return type: 'total' (dividend-inclusive) or 'price' (price-only).",
    )
    snapshot_id: str | None = Field(
        default=None,
        description="Optional UUID of an immutable dataset snapshot to replay. Guarantees deterministic input data.",
    )
    auto_snapshot: bool = Field(
        default=False,
        description="When True and snapshot_id is omitted, automatically captures an immutable dataset snapshot prior to execution.",
    )


    @model_validator(mode="after")
    def validate_request_bounds(self) -> BacktestRequest:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) cannot be after end_date ({self.end_date})."
            )

        # Normalize asset identifiers
        self.assets = [a.strip().upper() for a in self.assets]
        if len(self.assets) != len(set(self.assets)):
            raise ValueError("Asset list contains duplicate tickers.")

        # Normalize and validate weights for target_weights
        if self.strategy_type == "target_weights":
            if self.weights is None:
                # Default to equal weight if omitted
                n = len(self.assets)
                self.weights = {a: 1.0 / n for a in self.assets}
            else:
                norm_w = {k.strip().upper(): float(v) for k, v in self.weights.items()}
                # Verify that all weights are positive
                for k, v in norm_w.items():
                    if v < 0.0:
                        raise ValueError(f"Target weight for asset '{k}' cannot be negative ({v}).")
                # Verify sum
                total_w = sum(norm_w.values())
                if abs(total_w - 1.0) > 1e-4:
                    raise ValueError(
                        f"Target weights must sum to 1.0 (current sum: {total_w:.6f})."
                    )
                self.weights = norm_w
        elif self.strategy_type == "equal_weight":
            n = len(self.assets)
            self.weights = {a: 1.0 / n for a in self.assets}
        elif self.strategy_type == "walk_forward_optimization":
            # Initial weights start as equal weight
            n = len(self.assets)
            if self.weights is None:
                self.weights = {a: 1.0 / n for a in self.assets}

        return self


class EquityPoint(BaseModel):
    date: str
    portfolio_value_net: float
    portfolio_value_gross: float
    return_net: float
    return_gross: float
    drawdown_net: float
    drawdown_gross: float


class RebalanceEvent(BaseModel):
    date: str
    reason: str
    turnover: float
    traded_notional: float
    transaction_cost: float
    slippage_cost: float
    portfolio_value_before: float
    portfolio_value_after: float
    pre_weights: dict[str, float]
    post_weights: dict[str, float]


class BacktestSummaryMetrics(BaseModel):
    initial_value: float
    final_value_net: float
    final_value_gross: float
    cumulative_return_net: float
    cumulative_return_gross: float
    cagr_net: float
    cagr_gross: float
    annualized_return_net: float
    annualized_return_gross: float
    volatility_annualized_net: float
    volatility_annualized_gross: float
    sharpe_ratio_net: float | None
    sharpe_ratio_gross: float | None
    sortino_ratio_net: float | None
    sortino_ratio_gross: float | None
    max_drawdown_net: float
    max_drawdown_gross: float
    drawdown_peak_date: str | None
    drawdown_trough_date: str | None
    total_turnover: float
    total_transaction_costs: float
    total_slippage_costs: float
    total_friction_costs: float
    number_of_rebalances: int
    observation_count: int
    periods_per_year: int
    effective_start_date: str
    effective_end_date: str


class BacktestResponse(BaseModel):
    id: str
    dataset_id: str
    snapshot_id: str | None = Field(
        default=None,
        description="UUID of the immutable dataset snapshot linked to this backtest run.",
    )
    user_id: str | None
    name: str
    strategy_type: str
    rebalance_frequency: str
    initial_capital: float
    transaction_cost_bps: float
    slippage_bps: float
    status: str
    created_at: str
    metrics: BacktestSummaryMetrics
    equity_curve: list[EquityPoint]
    rebalance_events: list[RebalanceEvent]
    warnings: list[str] = Field(default_factory=list)
    point_in_time_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Reproducibility metadata for point-in-time corporate action adjustments.",
    )
    snapshot_provenance: dict[str, Any] | None = Field(
        default=None,
        description="Provenance and cryptographic verification metadata of the replayed dataset snapshot.",
    )



class BacktestListItem(BaseModel):
    id: str
    dataset_id: str
    snapshot_id: str | None = None
    user_id: str | None
    name: str
    strategy_type: str
    rebalance_frequency: str
    initial_capital: float
    final_value_net: float
    cumulative_return_net: float
    cagr_net: float
    sharpe_ratio_net: float | None
    max_drawdown_net: float
    status: str
    created_at: str
