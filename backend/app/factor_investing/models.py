"""
Pydantic Request and Response Models for Advanced Factor Investing & Systematic Risk Attribution.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class FactorBetaMetric(BaseModel):
    beta: float
    stderr: float
    tstat: float
    pvalue: float


class AssetFactorProfile(BaseModel):
    alpha_annualized: float
    alpha_stderr: float
    alpha_tstat: float
    alpha_pvalue: float
    betas: dict[str, FactorBetaMetric]
    r_squared: float
    r_squared_adj: float
    specific_variance_annualized: float
    specific_volatility_annualized: float


class FactorContributionDetail(BaseModel):
    exposure: float
    marginal_contrib: float
    total_variance_contrib: float
    pct_of_systematic_risk: float


class PortfolioRiskDecomposition(BaseModel):
    total_volatility: float
    systematic_volatility: float
    idiosyncratic_volatility: float
    systematic_variance: float
    idiosyncratic_variance: float
    total_variance: float
    systematic_share_pct: float
    idiosyncratic_share_pct: float
    systematic_variance_pct: float = 0.0
    specific_variance_pct: float = 0.0
    portfolio_volatility_pct: float = 0.0
    portfolio_betas: dict[str, float] = Field(default_factory=dict)
    factor_contributions: dict[str, FactorContributionDetail] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_synonyms(self) -> PortfolioRiskDecomposition:
        if self.systematic_variance_pct == 0.0 and self.systematic_share_pct != 0.0:
            self.systematic_variance_pct = self.systematic_share_pct
        if self.specific_variance_pct == 0.0 and self.idiosyncratic_share_pct != 0.0:
            self.specific_variance_pct = self.idiosyncratic_share_pct
        if self.portfolio_volatility_pct == 0.0 and self.total_volatility != 0.0:
            self.portfolio_volatility_pct = round(self.total_volatility * 100.0, 4)
        return self


class FactorAttributionRequest(BaseModel):
    dataset_id: str = Field(..., description="Target persistent dataset ID.")
    factor_model: Literal["capm", "ff3", "fama_french_3", "carhart4", "carhart_4", "pca"] = Field(
        "carhart4",
        description="Factor model archetype: 'capm', 'ff3' / 'fama_french_3', 'carhart4' / 'carhart_4', or 'pca'.",
    )
    num_pca_factors: int = Field(3, ge=1, le=10, description="Number of principal component factors when using PCA.")
    weights: dict[str, float] | None = Field(
        None,
        description="Optional portfolio weights mapping.",
    )
    custom_weights: dict[str, float] | None = Field(
        None,
        description="Alias for weights.",
    )
    risk_free_rate: float = Field(0.02, ge=-0.05, le=0.50, description="Annualized risk-free rate.")
    start_date: str | None = Field(None, description="Optional start date filter (YYYY-MM-DD).")
    end_date: str | None = Field(None, description="Optional end date filter (YYYY-MM-DD).")

    @model_validator(mode="after")
    def unify_weights(self) -> FactorAttributionRequest:
        if not self.weights and self.custom_weights:
            self.weights = self.custom_weights
        return self


class FactorAttributionResponse(BaseModel):
    dataset_id: str
    factor_model: str
    factors: list[str]
    assets: list[str]
    weights: dict[str, float]
    asset_profiles: dict[str, AssetFactorProfile]
    asset_loadings: dict[str, AssetFactorProfile] = Field(default_factory=dict)
    portfolio_betas: dict[str, float] = Field(default_factory=dict)
    risk_decomposition: PortfolioRiskDecomposition
    factor_covariance: list[list[float]]

    @model_validator(mode="after")
    def populate_aliases(self) -> FactorAttributionResponse:
        if not self.asset_loadings:
            self.asset_loadings = self.asset_profiles
        if not self.portfolio_betas and self.risk_decomposition:
            self.portfolio_betas = self.risk_decomposition.portfolio_betas
        return self


class FactorConstraintBound(BaseModel):
    min_beta: float | None = Field(None, description="Minimum allowable portfolio factor exposure.")
    max_beta: float | None = Field(None, description="Maximum allowable portfolio factor exposure.")


class FactorConstrainedOptimizeRequest(BaseModel):
    dataset_id: str = Field(..., description="Target persistent dataset ID.")
    factor_model: Literal["capm", "ff3", "fama_french_3", "carhart4", "carhart_4", "pca"] = Field("carhart4")
    num_pca_factors: int = Field(3, ge=1, le=10)
    objective: Literal["min_variance", "max_sharpe", "max_utility"] = Field(
        "min_variance",
        description="Optimization objective.",
    )
    risk_aversion: float = Field(2.5, gt=0.0, le=100.0)
    risk_free_rate: float = Field(0.02, ge=-0.05, le=0.50)
    min_weight: float = Field(0.0, ge=0.0, le=1.0)
    max_weight: float = Field(1.0, ge=0.0, le=1.0)
    factor_constraints: dict[str, FactorConstraintBound] | None = Field(
        None,
        description="Dictionary mapping factor name to min/max beta limits.",
    )
    target_factor_tilts: dict[str, FactorConstraintBound] | None = Field(
        None,
        description="Alias for factor_constraints.",
    )

    @model_validator(mode="after")
    def unify_constraints(self) -> FactorConstrainedOptimizeRequest:
        if not self.factor_constraints and self.target_factor_tilts:
            self.factor_constraints = self.target_factor_tilts
        return self


class FactorConstrainedOptimizeResponse(BaseModel):
    dataset_id: str
    factor_model: str
    objective: str
    assets: list[str]
    weights: dict[str, float]
    portfolio_betas: dict[str, float]
    realized_factor_betas: dict[str, float] = Field(default_factory=dict)
    risk_decomposition: PortfolioRiskDecomposition
    is_success: bool = True
    is_feasible: bool = True
    solver_status: str = "Optimal"
    solver_message: str = "Converged successfully."
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_fields(self) -> FactorConstrainedOptimizeResponse:
        if not self.realized_factor_betas and self.portfolio_betas:
            self.realized_factor_betas = self.portfolio_betas
        self.is_success = self.is_feasible
        if not self.diagnostics:
            self.diagnostics = {
                "converged": self.is_feasible,
                "solver_status": self.solver_status,
                "message": self.solver_message,
            }
        return self


class DynamicFactorSummaryMetrics(BaseModel):
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    active_return: float
    tracking_error: float
    information_ratio: float
    average_turnover: float
    total_transaction_costs: float


class DynamicFactorBenchmarkMetrics(BaseModel):
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float


class DynamicFactorEquityPoint(BaseModel):
    date: str
    strategy_equity: float
    benchmark_equity: float
    drawdown: float


class DynamicFactorRebalanceEvent(BaseModel):
    date: str
    weights: dict[str, float]
    portfolio_betas: dict[str, float]
    systematic_volatility: float
    idiosyncratic_volatility: float
    systematic_share_pct: float
    turnover: float
    cost_incurred: float
    is_feasible: bool = True
    solver_message: str = "Optimization converged."


class DynamicFactorExposureSeries(BaseModel):
    dates: list[str]
    exposures: dict[str, list[float]]


class DynamicFactorBacktestRequest(BaseModel):
    dataset_id: str = Field(..., description="Target persistent dataset ID.")
    factor_model: Literal["capm", "ff3", "fama_french_3", "carhart4", "carhart_4", "pca"] = Field(
        "carhart4",
        description="Factor model archetype: 'capm', 'ff3', 'carhart4', or 'pca'.",
    )
    num_pca_factors: int = Field(3, ge=1, le=10)
    strategy_type: Literal["factor_tilt", "factor_min_variance", "factor_momentum_rotation"] = Field(
        "factor_tilt",
        description="Strategy archetype: 'factor_tilt', 'factor_min_variance', or 'factor_momentum_rotation'.",
    )
    estimation_window: int = Field(60, ge=30, le=500, description="Rolling lookback window in trading days.")
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = Field("monthly")
    factor_tilts: dict[str, float] | None = Field(None, description="Multi-factor tilt score mappings.")
    factor_constraints: dict[str, FactorConstraintBound] | None = Field(
        None, description="Factor beta exposure bounds."
    )
    top_n_assets: int = Field(5, ge=1, le=50, description="Top N assets for factor momentum rotation.")
    risk_aversion: float = Field(2.5, gt=0.0, le=100.0)
    turnover_penalty: float = Field(0.0, ge=0.0, le=1.0)
    min_weight: float = Field(0.0, ge=0.0, le=1.0)
    max_weight: float = Field(1.0, ge=0.0, le=1.0)
    transaction_cost_bps: float = Field(10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(5.0, ge=0.0, le=500.0)
    initial_capital: float = Field(100000.0, gt=0.0)
    risk_free_rate: float = Field(0.02, ge=-0.05, le=0.50)
    start_date: str | None = Field(None)
    end_date: str | None = Field(None)


class DynamicFactorBacktestResponse(BaseModel):
    dataset_id: str
    strategy_type: str
    factor_model: str
    estimation_window: int
    rebalance_frequency: str
    total_rebalances: int
    summary_metrics: DynamicFactorSummaryMetrics
    benchmark_metrics: DynamicFactorBenchmarkMetrics
    equity_curve: list[DynamicFactorEquityPoint]
    rebalance_history: list[DynamicFactorRebalanceEvent]
    factor_exposure_series: DynamicFactorExposureSeries

