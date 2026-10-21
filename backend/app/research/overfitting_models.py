"""
Pydantic domain models and API contracts for backtest overfitting diagnostics,
Deflated Sharpe Ratio (DSR), Combinatorially Symmetric Cross-Validation (CSCV),
Probability of Backtest Overfitting (PBO), and Minimum Backtest Length (MinBTL).

Independent of database persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


PBORiskLevel = Literal["low", "moderate", "high", "severe"]


def classify_pbo_risk(pbo: float) -> PBORiskLevel:
    """
    Classifies the empirical Probability of Backtest Overfitting (PBO)
    into standard institutional risk tiers.
    """
    if pbo <= 0.15:
        return "low"
    elif pbo <= 0.35:
        return "moderate"
    elif pbo <= 0.50:
        return "high"
    else:
        return "severe"


class OverfittingDiagnosticsRequest(BaseModel):
    """
    Request payload to compute on-demand backtest overfitting diagnostics
    across runs of a research experiment.
    """
    experiment_id: str = Field(
        description="UUID of the parent research experiment containing multiple strategy runs."
    )
    run_ids: list[str] | None = Field(
        default=None,
        description="Optional explicit subset of run UUIDs to evaluate. If omitted, all succeeded runs with backtests are analyzed.",
    )
    n_slices: int = Field(
        default=16,
        ge=4,
        le=16,
        description="Number of equal-length contiguous time slices for CSCV partitioning. Must be an even integer (e.g. 8, 10, 12, 14, 16).",
    )
    significance_level: float = Field(
        default=0.05,
        gt=0.0,
        lt=0.5,
        description="Statistical significance threshold alpha for hypothesis testing (typically 0.05 or 0.01).",
    )
    annualization_factor: int = Field(
        default=252,
        ge=1,
        le=365,
        description="Trading periods per year (252 for daily, 52 for weekly, 12 for monthly).",
    )

    @model_validator(mode="after")
    def validate_even_slices(self) -> OverfittingDiagnosticsRequest:
        if self.n_slices % 2 != 0:
            raise ValueError(f"n_slices must be an even integer for CSCV partitioning, got {self.n_slices}.")
        if self.run_ids is not None:
            cleaned = [r.strip() for r in self.run_ids if r.strip()]
            if len(cleaned) < 2:
                raise ValueError("When run_ids is specified, at least 2 distinct run IDs are required for cross-validation.")
            if len(cleaned) != len(set(cleaned)):
                raise ValueError("run_ids contains duplicate entries.")
            self.run_ids = cleaned
        return self


class DegradationRegression(BaseModel):
    """
    Ordinary Least Squares (OLS) regression metrics of Out-of-Sample (OOS) Sharpe
    on In-Sample (IS) Sharpe across all CSCV combinations.
    """
    slope: float = Field(description="Degradation slope beta (IS to OOS translation). Values near 1 indicate robust persistence; <= 0 indicate severe overfitting.")
    intercept: float = Field(description="OLS regression intercept alpha.")
    r_squared: float = Field(ge=0.0, le=1.0, description="Coefficient of determination R^2.")
    p_value: float | None = Field(default=None, ge=0.0, le=1.0, description="Two-sided p-value for hypothesis that slope is zero.")
    std_err: float | None = Field(default=None, ge=0.0, description="Standard error of the estimated regression slope.")


class CSCVCombinationsPoint(BaseModel):
    """
    Summary observation for a single CSCV combination split.
    """
    combination_id: int = Field(description="Zero-based index of the combinatorial partition split.")
    selected_run_id: str = Field(description="UUID of the strategy that achieved maximum In-Sample Sharpe in this split.")
    is_sharpe: float = Field(description="Annualized Sharpe ratio of the selected strategy In-Sample.")
    oos_sharpe: float = Field(description="Annualized Sharpe ratio of the selected strategy Out-of-Sample.")
    oos_rank: int = Field(ge=1, description="1-based ascending rank of the selected strategy in OOS (1 = worst, N = best).")
    relative_rank: float = Field(ge=0.0, le=1.0, description="Normalized relative rank omega_bar = oos_rank / (N + 1).")
    is_overfitted: bool = Field(description="True if relative_rank <= 0.5 (below-median out-of-sample performance).")


class CSCVHistogramBin(BaseModel):
    """
    Binned frequency distribution of CSCV Out-of-Sample relative ranks.
    """
    bin_start: float = Field(ge=0.0, le=1.0, description="Inclusive lower bound of relative rank.")
    bin_end: float = Field(ge=0.0, le=1.0, description="Inclusive upper bound of relative rank.")
    count: int = Field(ge=0, description="Number of combinations falling in this relative rank bin.")
    relative_frequency: float = Field(ge=0.0, le=1.0, description="Fraction of combinations in this bin.")


class RunOverfittingSummary(BaseModel):
    """
    Per-strategy summary within the evaluated multi-trial experiment.
    """
    run_id: str = Field(description="UUID of the research experiment run.")
    run_number: int = Field(ge=1, description="Human-readable run index.")
    nominal_sharpe: float = Field(description="Full-sample annualized nominal Sharpe ratio.")
    selection_frequency_is: float = Field(ge=0.0, le=1.0, description="Proportion of CSCV combinations where this run was chosen as the in-sample best.")
    mean_oos_sharpe_when_selected: float | None = Field(default=None, description="Average OOS Sharpe ratio when this strategy was selected as IS best.")
    mean_oos_rank_when_selected: float | None = Field(default=None, description="Average OOS relative rank when this strategy was selected as IS best.")


class OverfittingDiagnosticsResponse(BaseModel):
    """
    Comprehensive backtest overfitting diagnostics report.
    """
    experiment_id: str = Field(description="Parent experiment UUID.")
    experiment_name: str = Field(description="Experiment display name.")
    strategy_type: str = Field(description="Strategy archetype.")
    dataset_id: str = Field(description="Underlying market dataset UUID.")
    snapshot_id: str | None = Field(default=None, description="Immutable dataset snapshot UUID (if bound).")
    
    # Sample dimensions
    evaluated_runs_count: int = Field(ge=1, description="Number of strategy trials N evaluated.")
    aligned_observations_count: int = Field(ge=1, description="Number of synchronized daily observations T across all runs.")
    n_slices: int = Field(ge=4, le=16, description="Number of contiguous temporal partitions S.")
    total_combinations_count: int = Field(ge=1, description="Combinatorial split count C = binom(S, S/2).")
    
    # Overfitting Metrics
    pbo: float = Field(ge=0.0, le=1.0, description="Probability of Backtest Overfitting (fraction of splits with OOS rank <= median).")
    pbo_risk_level: PBORiskLevel = Field(description="Institutional risk classification: 'low', 'moderate', 'high', or 'severe'.")
    
    # Statistical Deflation
    best_run_id: str = Field(description="UUID of the strategy with the highest full-sample nominal Sharpe ratio.")
    best_run_number: int = Field(ge=1, description="Run number of the best performing strategy.")
    best_nominal_sharpe: float = Field(description="Highest observed annualized nominal Sharpe ratio across all trials.")
    expected_max_sharpe: float = Field(description="Expected maximum Sharpe ratio SR* under the null hypothesis of selection bias.")
    deflated_sharpe_ratio: float = Field(ge=0.0, le=1.0, description="Deflated Sharpe Ratio (DSR), probability that SR > SR* after multiple-testing correction.")
    is_statistically_significant: bool = Field(description="True if DSR >= (1 - significance_level), e.g. DSR >= 0.95 for alpha = 0.05.")
    
    # Track Record & Higher Moments
    min_backtest_length_years: float | None = Field(default=None, description="Minimum Backtest Length (MinBTL) in years required to reject false discovery. None if unreachable.")
    actual_backtest_length_years: float = Field(description="Observed track record length in years (T / annualization_factor).")
    skewness: float = Field(description="Sample skewness of the selected best strategy's daily returns.")
    kurtosis: float = Field(description="Sample Pearson kurtosis of the selected best strategy's daily returns (normal = 3.0).")
    
    # Empirical Cross-Validation Analytics
    degradation_regression: DegradationRegression = Field(description="Linear degradation regression metrics (OOS Sharpe on IS Sharpe).")
    combinations_sample: list[CSCVCombinationsPoint] = Field(description="Sample of combinatorial points for interactive IS vs OOS scatter plot.")
    rank_distribution: list[CSCVHistogramBin] = Field(description="Histogram distribution of OOS relative ranks.")
    runs_summary: list[RunOverfittingSummary] = Field(description="Per-run selection and performance statistics.")
    
    warnings: list[str] = Field(default_factory=list, description="Advisory warnings (e.g. low trial count, severe degradation, date overlap trimming).")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of analytical report generation.")
