"""
Deterministic analytical test fixtures for Stage 34 institutional reporting contracts.
Covers normal, edge, unavailable-data, undefined-metric, and research annex scenarios.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.reports.contracts import (
    AssetAllocationItem,
    BenchmarkRelativeMetrics,
    CommonReportEnvelope,
    ExecutiveKPIs,
    FrictionAndExecutionMetrics,
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    MonthlyReturnCell,
    ReportWarning,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
    StrategyMandate,
    TimeSeriesPoint,
)
from app.research.overfitting_models import (
    CSCVCombinationsPoint,
    CSCVHistogramBin,
    DegradationRegression,
    RunOverfittingSummary,
)


def create_sample_envelope(
    report_type: str = "tear_sheet",
    start_date: str = "2023-01-03",
    end_date: str = "2023-12-29",
    snapshot_id: str | None = "snap-audit-2023-certified",
    snapshot_manifest_digest: str | None = "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
    warnings: list[ReportWarning] | None = None,
) -> CommonReportEnvelope:
    return CommonReportEnvelope(
        contract_version="1.0",
        report_type=report_type,  # type: ignore
        report_title="US Large-Cap Multi-Factor Strategy",
        generated_at=datetime(2026, 10, 23, 0, 0, 0, tzinfo=timezone.utc),
        base_currency="USD",
        reporting_start_date=start_date,
        reporting_end_date=end_date,
        dataset_id="ds-us-equities-2023",
        dataset_filename="us_large_cap_prices.csv",
        snapshot_id=snapshot_id,
        snapshot_manifest_digest=snapshot_manifest_digest,
        source_backtest_id="bt-sample-run-001",
        source_experiment_id="exp-sample-001",
        calculation_version="1.0",
        warnings=warnings or [],
        is_hypothetical=True,
    )


def create_sample_mandate(universe: list[str] | None = None) -> StrategyMandate:
    return StrategyMandate(
        strategy_type="walk_forward_optimization",
        investment_universe=universe or ["AAPL", "MSFT", "AMZN", "GOOGL", "NVDA"],
        rebalance_frequency="monthly",
        optimization_objective="max_sharpe",
        initial_capital=100000.0,
        risk_free_rate=0.02,
        constraints_summary=[
            "Long-only (0.0 <= w_i <= 0.30)",
            "Fully invested (sum(w_i) = 1.0)",
            "Maximum monthly turnover: 50%",
        ],
    )


def create_sample_kpis(
    has_gross: bool = True,
    undefined_calmar: bool = False,
    zero_vol: bool = False,
) -> ExecutiveKPIs:
    return ExecutiveKPIs(
        cumulative_return_net=0.2450,
        cumulative_return_gross=0.2580 if has_gross else None,
        cagr_net=0.2450,
        cagr_gross=0.2580 if has_gross else None,
        annualized_return_net=0.2210,
        annualized_return_gross=0.2330 if has_gross else None,
        annualized_volatility_net=0.00001 if zero_vol else 0.1420,
        annualized_volatility_gross=0.1415 if has_gross else None,
        sharpe_ratio_net=None if zero_vol else 1.4155,
        sharpe_ratio_gross=1.5053 if (has_gross and not zero_vol) else None,
        sortino_ratio_net=None if zero_vol else 2.1240,
        sortino_ratio_gross=2.2510 if (has_gross and not zero_vol) else None,
        max_drawdown_net=0.0 if undefined_calmar else 0.0845,
        max_drawdown_gross=0.0 if undefined_calmar else 0.0820,
        calmar_ratio_net=None if undefined_calmar else 2.8994,
        calmar_ratio_gross=None if undefined_calmar else 3.1463,
        drawdown_peak_date="2023-07-18",
        drawdown_trough_date="2023-08-25",
        drawdown_recovery_date="2023-10-12",
        drawdown_duration_days=38,
        positive_periods_count=138,
        negative_periods_count=112,
        win_rate=0.552,
        profit_loss_ratio=1.285,
        observation_count=250,
        periods_per_year=252,
    )


def create_sample_benchmark_metrics(has_zero_te: bool = False) -> BenchmarkRelativeMetrics:
    return BenchmarkRelativeMetrics(
        benchmark_id="SPY:US",
        benchmark_name="S&P 500 ETF Trust",
        benchmark_cumulative_return=0.1820,
        benchmark_annualized_return=0.1750,
        benchmark_annualized_volatility=0.1310,
        benchmark_sharpe_ratio=1.1832,
        benchmark_max_drawdown=0.1020,
        arithmetic_active_return=0.0630,
        geometric_excess_return=0.0533,
        annualized_active_return=0.0460,
        tracking_error=0.000001 if has_zero_te else 0.0450,
        information_ratio=None if has_zero_te else 1.0222,
        beta=0.9250,
        alpha_annualized=0.0520,
        treynor_ratio=0.2173,
        up_capture_ratio=1.1200,
        down_capture_ratio=0.8850,
        correlation=0.9420,
    )


def create_sample_allocation() -> list[AssetAllocationItem]:
    return [
        AssetAllocationItem(
            asset_id="AAPL:US",
            ticker="AAPL",
            market="US",
            name="Apple Inc.",
            target_weight=0.25,
            effective_weight=0.27,
            asset_cumulative_return=0.3200,
            total_contribution=0.0815,
            share_of_return=0.3326,
        ),
        AssetAllocationItem(
            asset_id="MSFT:US",
            ticker="MSFT",
            market="US",
            name="Microsoft Corp.",
            target_weight=0.25,
            effective_weight=0.26,
            asset_cumulative_return=0.2850,
            total_contribution=0.0725,
            share_of_return=0.2959,
        ),
        AssetAllocationItem(
            asset_id="AMZN:US",
            ticker="AMZN",
            market="US",
            name="Amazon.com Inc.",
            target_weight=0.20,
            effective_weight=0.19,
            asset_cumulative_return=0.1840,
            total_contribution=0.0360,
            share_of_return=0.1469,
        ),
        AssetAllocationItem(
            asset_id="NVDA:US",
            ticker="NVDA",
            market="US",
            name="NVIDIA Corp.",
            target_weight=0.30,
            effective_weight=0.28,
            asset_cumulative_return=0.1980,
            total_contribution=0.0550,
            share_of_return=0.2245,
        ),
    ]


def create_sample_friction(has_slippage: bool = True) -> FrictionAndExecutionMetrics:
    return FrictionAndExecutionMetrics(
        total_turnover=2.45,
        annualized_turnover=2.45,
        transaction_cost_bps=10.0,
        slippage_bps=5.0 if has_slippage else 0.0,
        total_transaction_costs=245.0,
        total_slippage_costs=122.5 if has_slippage else 0.0,
        total_friction_costs=367.5 if has_slippage else 245.0,
        friction_drag_bps=36.75 if has_slippage else 24.50,
        number_of_rebalances=12,
    )


def create_sample_timeseries(n_days: int = 5) -> list[TimeSeriesPoint]:
    pts = []
    base_val = 100000.0
    for i in range(n_days):
        day_str = f"2023-01-{i+3:02d}"
        ret_net = 0.002 * (i + 1)
        val_net = base_val * (1.0 + ret_net)
        pts.append(
            TimeSeriesPoint(
                date=day_str,
                portfolio_value_net=val_net,
                portfolio_value_gross=val_net * 1.0005,
                return_net=ret_net,
                return_gross=ret_net + 0.0002,
                drawdown_net=0.01 * (i % 3),
                drawdown_gross=0.009 * (i % 3),
                benchmark_value=base_val * (1.0 + 0.0015 * (i + 1)),
                benchmark_return=0.0015,
                benchmark_drawdown=0.008 * (i % 3),
            )
        )
    return pts


def create_sample_monthly_returns() -> list[MonthlyReturnCell]:
    return [
        MonthlyReturnCell(year=2023, month=1, return_net=0.032, return_gross=0.034, benchmark_return=0.025),
        MonthlyReturnCell(year=2023, month=2, return_net=-0.015, return_gross=-0.013, benchmark_return=-0.021),
        MonthlyReturnCell(year=2023, month=3, return_net=0.028, return_gross=0.030, benchmark_return=0.019),
    ]


def create_sample_research_annex(
    is_overfitted: bool = False,
    undefined_min_btl: bool = False,
) -> ResearchDiagnosticsAnnexPayload:
    envelope = create_sample_envelope(report_type="research_diagnostics")
    return ResearchDiagnosticsAnnexPayload(
        envelope=envelope,
        evaluated_runs_count=20,
        aligned_observations_count=756,
        n_slices=16,
        total_combinations_count=12870,
        pbo=0.685 if is_overfitted else 0.125,
        pbo_risk_level="severe" if is_overfitted else "low",
        best_run_id="run-best-001",
        best_run_number=3,
        best_nominal_sharpe=1.92,
        expected_max_sharpe=1.45,
        deflated_sharpe_ratio=0.420 if is_overfitted else 0.975,
        is_statistically_significant=False if is_overfitted else True,
        min_backtest_length_years=None if (is_overfitted or undefined_min_btl) else 1.85,
        actual_backtest_length_years=3.0,
        skewness=-0.35,
        kurtosis=3.85,
        degradation_regression=DegradationRegression(
            slope=-0.12 if is_overfitted else 0.65,
            intercept=0.25,
            r_squared=0.02 if is_overfitted else 0.45,
            p_value=0.45 if is_overfitted else 0.001,
            std_err=0.08,
        ),
        combinations_sample=[
            CSCVCombinationsPoint(
                combination_id=0,
                selected_run_id="run-best-001",
                is_sharpe=2.10,
                oos_sharpe=0.85 if is_overfitted else 1.95,
                oos_rank=5 if is_overfitted else 19,
                relative_rank=0.238 if is_overfitted else 0.905,
                is_overfitted=is_overfitted,
            )
        ],
        rank_distribution=[
            CSCVHistogramBin(bin_start=0.0, bin_end=0.1, count=100, relative_frequency=100 / 12870),
            CSCVHistogramBin(bin_start=0.4, bin_end=0.5, count=500, relative_frequency=500 / 12870),
            CSCVHistogramBin(bin_start=0.5, bin_end=0.6, count=600, relative_frequency=600 / 12870),
        ],
        runs_summary=[
            RunOverfittingSummary(
                run_id="run-best-001",
                run_number=3,
                nominal_sharpe=1.92,
                selection_frequency_is=0.45,
                mean_oos_sharpe_when_selected=1.55,
                mean_oos_rank_when_selected=0.72,
            )
        ],
    )


# 15 Deterministic Analytical Fixtures Required by Gate A Specification:

def get_fixture_1_valid_backtest_with_benchmark() -> InstitutionalTearSheetPayload:
    """Fixture 1: Valid backtest with net returns and benchmark."""
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(has_gross=False),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_2_dual_gross_and_net_backtest() -> InstitutionalTearSheetPayload:
    """Fixture 2: Backtest with distinct gross and net returns."""
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(has_gross=True),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_3_no_benchmark() -> StrategyFactSheetPayload:
    """Fixture 3: Report without benchmark."""
    return StrategyFactSheetPayload(
        envelope=create_sample_envelope(report_type="fact_sheet"),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(has_gross=False),
        benchmark_metrics=None,
        top_holdings=create_sample_allocation()[:3],
        compact_wealth_curve=create_sample_timeseries(n_days=3),
        monthly_returns=create_sample_monthly_returns(),
    )


def get_fixture_4_undefined_metrics() -> InstitutionalTearSheetPayload:
    """Fixture 4: Zero drawdown (Calmar undefined) and zero tracking error (IR undefined)."""
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(undefined_calmar=True),
        benchmark_metrics=create_sample_benchmark_metrics(has_zero_te=True),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_5_incomplete_period_warning() -> InstitutionalTearSheetPayload:
    """Fixture 5: Incomplete period triggering advisory warning."""
    warn = ReportWarning(
        code="WARN_INCOMPLETE_CALENDAR_YEAR",
        severity="info",
        message="Reporting period covers partial year (180 days). Annualized figures are scaled.",
        affected_metric="cagr_net",
    )
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(warnings=[warn]),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_6_currency_mismatch_warning() -> InstitutionalTearSheetPayload:
    """Fixture 6: Currency mismatch between asset and portfolio base currency."""
    warn = ReportWarning(
        code="WARN_CURRENCY_CONVERSION_UNSUPPORTED",
        severity="warning",
        message="Constituent assets trade in mixed currencies (USD and PKR) without live FX conversion rates.",
        provenance_ref="ds-us-equities-2023",
    )
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(warnings=[warn]),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_7_snapshot_provenance() -> StrategyFactSheetPayload:
    """Fixture 7: Certified dataset snapshot provenance."""
    envelope = create_sample_envelope(
        report_type="fact_sheet",
        snapshot_id="snap-certified-8899",
        snapshot_manifest_digest="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    )
    return StrategyFactSheetPayload(
        envelope=envelope,
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(),
        benchmark_metrics=create_sample_benchmark_metrics(),
        top_holdings=create_sample_allocation(),
        compact_wealth_curve=create_sample_timeseries(),
        monthly_returns=create_sample_monthly_returns(),
    )


def get_fixture_8_partial_tca_no_slippage() -> InstitutionalTearSheetPayload:
    """Fixture 8: Transaction costs without slippage modeling."""
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(),
        mandate=create_sample_mandate(),
        kpis=create_sample_kpis(),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=create_sample_allocation(),
        friction_and_execution=create_sample_friction(has_slippage=False),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )


def get_fixture_9_research_with_valid_diagnostics() -> ResearchDiagnosticsAnnexPayload:
    """Fixture 9: Research experiment with low PBO and significant DSR."""
    return create_sample_research_annex(is_overfitted=False)


def get_fixture_10_research_with_undefined_diagnostics() -> ResearchDiagnosticsAnnexPayload:
    """Fixture 10: Research experiment with severe overfitting and undefined MinBTL."""
    return create_sample_research_annex(is_overfitted=True, undefined_min_btl=True)


def get_fixture_11_large_timeseries_payload(n_obs: int = 1260) -> list[TimeSeriesPoint]:
    """Fixture 11: 5-year daily observation payload (1,260 days) to test pagination limits."""
    return create_sample_timeseries(n_days=n_obs)


def get_fixture_12_empty_allocation_portfolio() -> InstitutionalTearSheetPayload:
    """Fixture 12: Empty asset allocation for cash-only or single-benchmark portfolio."""
    warn = ReportWarning(
        code="INFO_SINGLE_ASSET_BENCHMARK_ONLY",
        severity="info",
        message="Portfolio is benchmark-only index tracker; individual constituent weights are omitted.",
    )
    return InstitutionalTearSheetPayload(
        envelope=create_sample_envelope(warnings=[warn]),
        mandate=create_sample_mandate(universe=["SPY"]),
        kpis=create_sample_kpis(),
        benchmark_metrics=create_sample_benchmark_metrics(),
        asset_allocation=[],
        friction_and_execution=create_sample_friction(),
        equity_curve=create_sample_timeseries(),
        monthly_returns_table=create_sample_monthly_returns(),
    )
