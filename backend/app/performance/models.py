"""
Pydantic schemas and domain models for portfolio performance attribution and benchmark evaluation.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PerformanceAnalysisRequest(BaseModel):
    dataset_id: str = Field(description="UUID of the authoritative persistent market dataset.")
    backtest_id: str | None = Field(
        default=None,
        description="Optional UUID of a completed saved backtest to evaluate.",
    )
    name: str = Field(
        default="Portfolio Performance Attribution",
        min_length=1,
        max_length=150,
        description="User-facing label for the performance report.",
    )
    benchmark_asset: str = Field(
        description="Asset identifier in dataset to serve as benchmark (e.g. 'SPY:US' or 'SPY').",
    )
    assets: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Asset identifiers for portfolio if not derived from a saved backtest.",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description="Portfolio target weights if not derived from a saved backtest.",
    )
    risk_free_rate: float = Field(
        default=0.0,
        ge=-0.1,
        le=0.5,
        description="Annualized risk-free interest rate for Sharpe, Sortino, Alpha, and Treynor metrics.",
    )
    start_date: date | None = Field(
        default=None,
        description="Optional inclusive evaluation start date (YYYY-MM-DD).",
    )
    end_date: date | None = Field(
        default=None,
        description="Optional inclusive evaluation end date (YYYY-MM-DD).",
    )
    save_report: bool = Field(
        default=True,
        description="Whether to persist the performance analysis report for later retrieval.",
    )

    @model_validator(mode="after")
    def validate_request_integrity(self) -> PerformanceAnalysisRequest:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(f"start_date ({self.start_date}) cannot be after end_date ({self.end_date}).")

        self.benchmark_asset = self.benchmark_asset.strip().upper()
        if not self.benchmark_asset:
            raise ValueError("benchmark_asset identifier cannot be empty.")

        # If backtest_id is not provided, assets and weights must be supplied
        if not self.backtest_id:
            if not self.assets or len(self.assets) == 0:
                raise ValueError("Must provide either a valid backtest_id or an explicit list of portfolio assets.")
            self.assets = [a.strip().upper() for a in self.assets]
            if len(self.assets) != len(set(self.assets)):
                raise ValueError("Asset list contains duplicate tickers.")

            if self.weights is None:
                n = len(self.assets)
                self.weights = {a: 1.0 / n for a in self.assets}
            else:
                norm_w = {k.strip().upper(): float(v) for k, v in self.weights.items()}
                total_w = sum(norm_w.values())
                if abs(total_w - 1.0) > 1e-4:
                    raise ValueError(f"Portfolio weights must sum to 1.0 (current sum: {total_w:.6f}).")
                self.weights = norm_w
        return self


class AssetContribution(BaseModel):
    asset: str
    weight: float
    cumulative_return: float
    total_contribution: float
    share_of_return: float


class PerformanceTimeseriesPoint(BaseModel):
    date: str
    portfolio_return: float
    benchmark_return: float
    active_return: float
    portfolio_cumulative: float
    benchmark_cumulative: float
    active_cumulative: float
    drawdown_portfolio: float
    drawdown_benchmark: float


class PerformanceSummaryMetrics(BaseModel):
    observation_count: int
    periods_per_year: int
    start_date: str | None
    end_date: str | None

    # Standalone Portfolio
    portfolio_cumulative_return: float
    portfolio_annualized_return: float
    portfolio_annualized_volatility: float
    portfolio_sharpe_ratio: float | None
    portfolio_sortino_ratio: float | None
    portfolio_max_drawdown: float

    # Standalone Benchmark
    benchmark_cumulative_return: float
    benchmark_annualized_return: float
    benchmark_annualized_volatility: float
    benchmark_sharpe_ratio: float | None
    benchmark_sortino_ratio: float | None
    benchmark_max_drawdown: float

    # Active / Comparative
    arithmetic_active_return: float
    geometric_excess_return: float
    annualized_active_return: float
    tracking_error: float
    information_ratio: float | None
    beta: float | None
    alpha_annualized: float | None
    treynor_ratio: float | None
    up_capture_ratio: float | None
    down_capture_ratio: float | None


class PerformanceResponse(BaseModel):
    id: str
    name: str
    dataset_id: str
    backtest_id: str | None
    benchmark_asset: str
    risk_free_rate: float
    start_date: str | None
    end_date: str | None
    status: str
    metrics: PerformanceSummaryMetrics
    contributions: list[AssetContribution]
    timeseries: list[PerformanceTimeseriesPoint]
    warnings: list[str] = Field(default_factory=list)
    is_hypothetical: bool = True
    disclaimer: str = (
        "Performance attribution and benchmark comparison metrics are historical research diagnostics. "
        "They do not guarantee future profitability or constitute investment recommendations."
    )
    created_at: str


class PerformanceReportListItem(BaseModel):
    id: str
    name: str
    dataset_id: str
    backtest_id: str | None
    benchmark_asset: str
    portfolio_cumulative_return: float
    benchmark_cumulative_return: float
    arithmetic_active_return: float
    information_ratio: float | None
    beta: float | None
    alpha_annualized: float | None
    status: str
    created_at: str
