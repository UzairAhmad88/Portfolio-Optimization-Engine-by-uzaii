"""
Pydantic schemas and domain models for portfolio research experiments,
reproducible run execution, and multi-strategy comparison.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


StrategyType = Literal[
    "target_weights",
    "equal_weight",
    "walk_forward_optimization",
    "benchmark_attribution",
    "monte_carlo_risk",
]

RunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class ExperimentConfig(BaseModel):
    """
    Validated configuration payload for research experiments.
    """
    strategy_type: StrategyType = Field(
        description="The analytical workflow: target_weights, equal_weight, walk_forward_optimization, benchmark_attribution, or monte_carlo_risk.",
    )
    dataset_id: str = Field(description="UUID of the underlying market dataset.")
    assets: list[str] = Field(min_length=1, max_length=50, description="Asset identifiers in universe.")
    weights: dict[str, float] | None = Field(default=None, description="Target weights (if applicable).")
    rebalance_frequency: str | None = Field(default="monthly", description="Rebalancing schedule.")
    transaction_cost_bps: float = Field(default=0.0, ge=0.0, le=1000.0, description="Cost per rebalance in basis points.")
    slippage_bps: float = Field(default=0.0, ge=0.0, le=500.0, description="Slippage per rebalance in basis points.")
    objective: str | None = Field(default=None, description="Optimization objective (min_variance or max_sharpe).")
    constraints: dict[str, Any] | None = Field(default=None, description="Optimization weight/sector constraints.")
    training_window: int = Field(default=252, ge=20, le=2520, description="Estimation window for rolling optimization.")
    benchmark_asset: str | None = Field(default=None, description="Benchmark identifier for attribution.")
    risk_free_rate: float = Field(default=0.0, ge=-0.1, le=0.5, description="Annualized risk-free rate.")
    distribution: str = Field(default="normal", description="Return distribution for Monte Carlo (normal or student_t).")
    degrees_of_freedom: float = Field(default=5.0, ge=3.0, le=30.0, description="Student-t degrees of freedom.")
    horizon_days: int = Field(default=21, ge=1, le=252, description="Simulation horizon in days.")
    num_paths: int = Field(default=1000, ge=100, le=5000, description="Simulation path count.")
    initial_capital: float = Field(default=100000.0, ge=1000.0, description="Portfolio initial capital.")
    rebalance_policy: str = Field(default="none", description="Monte Carlo rebalance policy (none or periodic).")
    seed: int | None = Field(default=None, ge=0, le=2147483647, description="Deterministic random seed.")
    start_date: date | None = Field(default=None, description="Inclusive evaluation start date.")
    end_date: date | None = Field(default=None, description="Inclusive evaluation end date.")

    @model_validator(mode="after")
    def validate_strategy_specific_requirements(self) -> ExperimentConfig:
        self.assets = [a.strip().upper() for a in self.assets]
        if len(self.assets) != len(set(self.assets)):
            raise ValueError("Assets list contains duplicate tickers.")

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(f"start_date ({self.start_date}) cannot be after end_date ({self.end_date}).")

        if self.strategy_type == "target_weights":
            if not self.weights:
                raise ValueError("strategy_type 'target_weights' requires 'weights' dictionary.")
            norm_w = {k.strip().upper(): float(v) for k, v in self.weights.items()}
            total_w = sum(norm_w.values())
            if abs(total_w - 1.0) > 1e-4:
                raise ValueError(f"Portfolio weights must sum to 1.0 (got {total_w:.6f}).")
            self.weights = norm_w

        elif self.strategy_type == "equal_weight":
            n = len(self.assets)
            self.weights = {a: round(1.0 / n, 8) for a in self.assets}

        elif self.strategy_type == "walk_forward_optimization":
            if not self.objective:
                self.objective = "max_sharpe"
            if self.objective not in ("min_variance", "max_sharpe"):
                raise ValueError(f"Unsupported optimization objective '{self.objective}'. Supported: min_variance, max_sharpe.")

        elif self.strategy_type == "benchmark_attribution":
            if not self.benchmark_asset:
                raise ValueError("strategy_type 'benchmark_attribution' requires 'benchmark_asset'.")
            self.benchmark_asset = self.benchmark_asset.strip().upper()
            if not self.weights:
                n = len(self.assets)
                self.weights = {a: round(1.0 / n, 8) for a in self.assets}
            else:
                norm_w = {k.strip().upper(): float(v) for k, v in self.weights.items()}
                total_w = sum(norm_w.values())
                if abs(total_w - 1.0) > 1e-4:
                    raise ValueError(f"Portfolio weights must sum to 1.0 (got {total_w:.6f}).")
                self.weights = norm_w

        elif self.strategy_type == "monte_carlo_risk":
            if not self.weights:
                n = len(self.assets)
                self.weights = {a: round(1.0 / n, 8) for a in self.assets}
            else:
                norm_w = {k.strip().upper(): float(v) for k, v in self.weights.items()}
                total_w = sum(norm_w.values())
                if abs(total_w - 1.0) > 1e-4:
                    raise ValueError(f"Portfolio weights must sum to 1.0 (got {total_w:.6f}).")
                self.weights = norm_w

        return self


class ExperimentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150, description="Experiment display name.")
    description: str | None = Field(default=None, max_length=1000, description="Hypothesis or notes.")
    strategy_type: StrategyType = Field(description="Strategy archetype.")
    dataset_id: str = Field(description="Target dataset UUID.")
    config: dict[str, Any] = Field(description="Strategy configuration parameters.")


class ExperimentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    config: dict[str, Any] | None = Field(default=None, description="Updated configuration (creates a new version).")


class ExperimentResponse(BaseModel):
    id: str
    user_id: str | None
    dataset_id: str
    name: str
    description: str | None
    strategy_type: str
    config: dict[str, Any]
    config_fingerprint: str
    version: int
    created_at: datetime
    updated_at: datetime
    latest_run_status: str | None = None
    latest_run_number: int | None = None
    total_runs_count: int = 0


class ExperimentListItem(BaseModel):
    id: str
    name: str
    description: str | None
    strategy_type: str
    dataset_id: str
    version: int
    config_fingerprint: str
    latest_run_status: str | None = None
    latest_run_number: int | None = None
    total_runs_count: int = 0
    created_at: datetime
    updated_at: datetime


class ExperimentRunResponse(BaseModel):
    id: str
    experiment_id: str
    run_number: int
    status: str
    dataset_version_hash: str | None
    snapshot_id: str | None = None
    config_fingerprint: str
    execution_duration_ms: int | None
    backtest_id: str | None
    performance_report_id: str | None
    risk_simulation_id: str | None
    summary_kpis: dict[str, Any] | None
    error_message: str | None
    is_reproducible: bool
    reproducibility_notes: list[str]
    created_at: datetime
    completed_at: datetime | None


class ExperimentRunListItem(BaseModel):
    id: str
    experiment_id: str
    run_number: int
    status: str
    snapshot_id: str | None = None
    config_fingerprint: str
    execution_duration_ms: int | None
    is_reproducible: bool
    created_at: datetime
    completed_at: datetime | None
    summary_kpis: dict[str, Any] | None


class ComparisonRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=10, description="List of 2 to 10 run IDs to compare.")


class ComparisonRunMetricItem(BaseModel):
    run_id: str
    experiment_id: str
    experiment_name: str
    strategy_type: str
    run_number: int
    status: str
    dataset_id: str
    dataset_version_hash: str | None
    config_fingerprint: str
    currency: str
    is_reproducible: bool
    execution_date: str
    start_date: str | None
    end_date: str | None
    observations_count: int | None
    metrics: dict[str, Any]
    config_summary: dict[str, Any]


class ComparisonResponse(BaseModel):
    runs: list[ComparisonRunMetricItem]
    common_currency: str
    has_period_divergence: bool
    has_provenance_divergence: bool
    warnings: list[str]
