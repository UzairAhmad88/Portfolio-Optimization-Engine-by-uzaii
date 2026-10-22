"""
Canonical Metric Registry for institutional portfolio reporting and tear sheets.
Documents exact mathematical definitions, annualization conventions, units,
gross vs net semantics, benchmark dependencies, and conditions under which metrics are undefined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MetricCategory = Literal["performance", "risk", "benchmark_relative", "attribution", "tca_execution", "overfitting"]
ReturnConvention = Literal["net_only", "gross_only", "both_distinct", "not_applicable"]


@dataclass(frozen=True)
class MetricDefinition:
    canonical_id: str
    display_name: str
    category: MetricCategory
    unit: str
    display_format: str
    return_convention: ReturnConvention
    requires_benchmark: bool
    annualized: bool
    periods_per_year: int | None
    mathematical_formula: str
    undefined_condition: str
    source_service: str
    description: str


CANONICAL_METRIC_REGISTRY: dict[str, MetricDefinition] = {
    # 1. Performance Metrics
    "cumulative_return": MetricDefinition(
        canonical_id="cumulative_return",
        display_name="Cumulative Total Return",
        category="performance",
        unit="percentage",
        display_format="{:+.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="R = V_T / V_0 - 1.0 = prod(1 + r_t) - 1.0",
        undefined_condition="V_0 <= 0 or missing equity series",
        source_service="app.quant.returns / BacktestRunModel",
        description="Total percentage change in portfolio equity over the full evaluated track record.",
    ),
    "cagr": MetricDefinition(
        canonical_id="cagr",
        display_name="Compound Annual Growth Rate (CAGR)",
        category="performance",
        unit="percentage",
        display_format="{:+.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="CAGR = (V_T / V_0) ** (periods_per_year / T) - 1.0",
        undefined_condition="V_T <= 0 or V_0 <= 0 or T < 2",
        source_service="app.quant.performance / BacktestSummaryMetrics",
        description="Geometric annualized growth rate of equity over multi-year track records.",
    ),
    "annualized_return": MetricDefinition(
        canonical_id="annualized_return",
        display_name="Annualized Arithmetic Mean Return",
        category="performance",
        unit="percentage",
        display_format="{:+.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="mu_ann = mean(r_t) * periods_per_year",
        undefined_condition="T < 1 or non-finite returns",
        source_service="app.quant.returns",
        description="Arithmetic mean daily return scaled by annual trading periods.",
    ),
    "annualized_volatility": MetricDefinition(
        canonical_id="annualized_volatility",
        display_name="Annualized Volatility (Standard Deviation)",
        category="risk",
        unit="percentage",
        display_format="{:.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="sigma_ann = std(r_t, ddof=1) * sqrt(periods_per_year)",
        undefined_condition="T < 2 or variance <= 0",
        source_service="app.quant.risk",
        description="Sample standard deviation of daily simple returns scaled by square root of annualization factor.",
    ),
    "sharpe_ratio": MetricDefinition(
        canonical_id="sharpe_ratio",
        display_name="Sharpe Ratio",
        category="performance",
        unit="ratio",
        display_format="{:.2f}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="SR = (mu_ann - r_f) / sigma_ann",
        undefined_condition="sigma_ann <= 1e-12 or T < 2",
        source_service="app.quant.performance",
        description="Excess return per unit of total risk against the annualized risk-free rate.",
    ),
    "sortino_ratio": MetricDefinition(
        canonical_id="sortino_ratio",
        display_name="Sortino Ratio",
        category="performance",
        unit="ratio",
        display_format="{:.2f}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="Sortino = (mu_ann - r_f) / (downside_std * sqrt(periods_per_year))",
        undefined_condition="downside_std <= 1e-12 or zero negative returns",
        source_service="app.quant.performance",
        description="Excess return per unit of downside risk below the risk-free rate threshold.",
    ),
    "max_drawdown": MetricDefinition(
        canonical_id="max_drawdown",
        display_name="Maximum Drawdown (Peak-to-Trough)",
        category="risk",
        unit="percentage",
        display_format="{:.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="MDD = max_t (Peak_t - V_t) / Peak_t",
        undefined_condition="T < 1 or all Peak_t <= 0",
        source_service="app.quant.performance / BacktestSummaryMetrics",
        description="Greatest percentage decline experienced from a historical portfolio equity peak to a subsequent trough.",
    ),
    "calmar_ratio": MetricDefinition(
        canonical_id="calmar_ratio",
        display_name="Calmar Ratio",
        category="performance",
        unit="ratio",
        display_format="{:.2f}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="Calmar = CAGR / MaxDrawdown",
        undefined_condition="MaxDrawdown <= 1e-6 or CAGR is undefined",
        source_service="app.quant.performance",
        description="Ratio of annualized compound growth rate to maximum historical drawdown.",
    ),

    # 2. Benchmark Relative & Attribution Metrics
    "tracking_error": MetricDefinition(
        canonical_id="tracking_error",
        display_name="Tracking Error",
        category="benchmark_relative",
        unit="percentage",
        display_format="{:.2%}",
        return_convention="net_only",
        requires_benchmark=True,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="TE = std(r_p,t - r_b,t, ddof=1) * sqrt(periods_per_year)",
        undefined_condition="T < 2 or benchmark return series missing",
        source_service="app.performance.service",
        description="Annualized volatility of excess returns between the portfolio and its benchmark.",
    ),
    "information_ratio": MetricDefinition(
        canonical_id="information_ratio",
        display_name="Information Ratio",
        category="benchmark_relative",
        unit="ratio",
        display_format="{:.2f}",
        return_convention="net_only",
        requires_benchmark=True,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="IR = (annualized_active_return) / TE",
        undefined_condition="TE <= 1e-12 or benchmark missing",
        source_service="app.performance.service",
        description="Active excess return generated per unit of active benchmark tracking risk.",
    ),
    "beta": MetricDefinition(
        canonical_id="beta",
        display_name="Market Beta (Systematic Risk)",
        category="benchmark_relative",
        unit="ratio",
        display_format="{:.2f}",
        return_convention="net_only",
        requires_benchmark=True,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="Beta = Cov(r_p, r_b) / Var(r_b)",
        undefined_condition="Var(r_b) <= 1e-12 or T < 2",
        source_service="app.performance.service",
        description="Sensitivity of portfolio returns relative to benchmark market movements.",
    ),
    "alpha": MetricDefinition(
        canonical_id="alpha",
        display_name="Jensen's Alpha (Annualized)",
        category="benchmark_relative",
        unit="percentage",
        display_format="{:+.2%}",
        return_convention="net_only",
        requires_benchmark=True,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="Alpha = (mu_p - r_f) - Beta * (mu_b - r_f)",
        undefined_condition="Beta is undefined or benchmark missing",
        source_service="app.performance.service",
        description="Annualized excess return generated over that expected by the Capital Asset Pricing Model (CAPM).",
    ),
    "menchero_attribution": MetricDefinition(
        canonical_id="menchero_attribution",
        display_name="Menchero Multi-Period Return Contribution",
        category="attribution",
        unit="percentage",
        display_format="{:+.2%}",
        return_convention="both_distinct",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="C_i = sum_t (w_i,t-1 * r_i,t * A_t) where A_t = ln(1+R_p)/(R_p) * (1+r_p,t)/(ln(1+r_p,t))",
        undefined_condition="Cumulative return R_p <= -1.0 or weights missing",
        source_service="app.performance.service",
        description="Mathematically exact geometric linking decomposing portfolio total return into additive asset-level contributions.",
    ),

    # 3. Transaction Costs & Friction Drag
    "portfolio_turnover": MetricDefinition(
        canonical_id="portfolio_turnover",
        display_name="Portfolio Turnover",
        category="tca_execution",
        unit="ratio",
        display_format="{:.2f}x",
        return_convention="not_applicable",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="Turnover = 0.5 * sum_t sum_i |w_i,t - w_i,t-|, annualized by periods_per_year/T",
        undefined_condition="No rebalance event logs found",
        source_service="app.backtesting.engine",
        description="Average rate at which portfolio constituent weights are turned over per year.",
    ),
    "friction_drag_bps": MetricDefinition(
        canonical_id="friction_drag_bps",
        display_name="Friction Drag (Total Trading Costs)",
        category="tca_execution",
        unit="basis_points",
        display_format="{:.1f} bps",
        return_convention="not_applicable",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="Drag = (Total_Fees + Total_Slippage) / Initial_Capital * 10,000",
        undefined_condition="Initial_Capital <= 0",
        source_service="app.backtesting.engine",
        description="Aggregate cost drag of brokerage fees and execution slippage expressed in basis points.",
    ),

    # 4. Research Lab & Overfitting Diagnostics (Stage 33)
    "pbo": MetricDefinition(
        canonical_id="pbo",
        display_name="Probability of Backtest Overfitting (PBO)",
        category="overfitting",
        unit="percentage",
        display_format="{:.1%}",
        return_convention="net_only",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=None,
        mathematical_formula="PBO = (1/C) * sum_c 1(omega_bar_c <= 0.50)",
        undefined_condition="N < 2 strategies or T < 20 observations",
        source_service="app.analytics.overfitting",
        description="Empirical probability that the in-sample optimal strategy underperforms out-of-sample median performance across CSCV partitions.",
    ),
    "deflated_sharpe_ratio": MetricDefinition(
        canonical_id="deflated_sharpe_ratio",
        display_name="Deflated Sharpe Ratio (DSR)",
        category="overfitting",
        unit="probability",
        display_format="{:.3f}",
        return_convention="net_only",
        requires_benchmark=False,
        annualized=False,
        periods_per_year=252,
        mathematical_formula="DSR = Phi((s_p - s_star_p) * sqrt(T-1) / sqrt(1 - gamma3*s_p + ((gamma4-1)/4)*s_p^2))",
        undefined_condition="N < 2 or non-finite trial moments",
        source_service="app.analytics.overfitting",
        description="Probability that observed Sharpe exceeds the expected maximum Sharpe under selection bias and non-Gaussian returns.",
    ),
    "min_backtest_length": MetricDefinition(
        canonical_id="min_backtest_length",
        display_name="Minimum Backtest Length (MinBTL)",
        category="overfitting",
        unit="years",
        display_format="{:.2f} yrs",
        return_convention="net_only",
        requires_benchmark=False,
        annualized=True,
        periods_per_year=252,
        mathematical_formula="MinBTL_years = (1 + [1 - gamma3*s_p + ((gamma4-1)/4)*s_p^2] * (Z_alpha / (s_p - s_star_p))^2) / 252",
        undefined_condition="Observed Sharpe s_p <= Expected Max Sharpe s_star_p",
        source_service="app.analytics.overfitting",
        description="Minimum sample length in years required to reject false discovery under multi-trial selection bias at level alpha.",
    ),
}


def get_metric_definition(metric_id: str) -> MetricDefinition | None:
    """Retrieves definition and mathematical metadata for a canonical financial metric."""
    return CANONICAL_METRIC_REGISTRY.get(metric_id)


def list_registered_metrics() -> list[MetricDefinition]:
    """Returns all canonically registered reporting metrics."""
    return list(CANONICAL_METRIC_REGISTRY.values())
