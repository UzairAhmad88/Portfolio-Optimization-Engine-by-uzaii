"""
Comprehensive contract test suite for Stage 34 reporting domain models,
metric registries, analytical fixtures, and cross-layer schema integrity.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.reports.contracts import (
    CommonReportEnvelope,
    ExecutiveKPIs,
    BenchmarkRelativeMetrics,
    AssetAllocationItem,
    TimeSeriesPoint,
    MonthlyReturnCell,
    FrictionAndExecutionMetrics,
    StrategyMandate,
    ReportWarning,
    StrategyFactSheetPayload,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    InstitutionalReportResponse,
)
from app.reports.metric_registry import (
    CANONICAL_METRIC_REGISTRY,
    get_metric_definition,
    list_registered_metrics,
)
from tests.fixtures.reporting_fixtures import (
    create_sample_envelope,
    create_sample_kpis,
    create_sample_mandate,
    create_sample_benchmark_metrics,
    create_sample_allocation,
    create_sample_friction,
    create_sample_timeseries,
    create_sample_monthly_returns,
    create_sample_research_annex,
    get_fixture_1_valid_backtest_with_benchmark,
    get_fixture_2_dual_gross_and_net_backtest,
    get_fixture_3_no_benchmark,
    get_fixture_4_undefined_metrics,
    get_fixture_5_incomplete_period_warning,
    get_fixture_6_currency_mismatch_warning,
    get_fixture_7_snapshot_provenance,
    get_fixture_8_partial_tca_no_slippage,
    get_fixture_9_research_with_valid_diagnostics,
    get_fixture_10_research_with_undefined_diagnostics,
    get_fixture_12_empty_allocation_portfolio,
)


class TestCommonReportEnvelope:
    """Verifies CommonReportEnvelope validation, date sequencing, and provenance metadata."""

    def test_valid_envelope_construction(self):
        env = create_sample_envelope()
        assert env.contract_version == "1.0"
        assert env.report_type == "tear_sheet"
        assert env.base_currency == "USD"
        assert env.reporting_start_date == "2023-01-03"
        assert env.reporting_end_date == "2023-12-29"
        assert env.snapshot_id == "snap-audit-2023-certified"
        assert env.is_hypothetical is True
        assert "institutional research" in env.regulatory_disclaimer.lower()

    def test_invalid_date_ordering_raises_validation_error(self):
        with pytest.raises(ValidationError, match="reporting_start_date .* cannot be after reporting_end_date"):
            CommonReportEnvelope(
                contract_version="1.0",
                report_type="tear_sheet",
                report_title="Invalid Date Order",
                reporting_start_date="2023-12-31",
                reporting_end_date="2023-01-01",  # Invalid: end before start
                dataset_id="ds-test",
            )

    def test_provenance_and_snapshot_digest_preservation(self):
        env = create_sample_envelope(
            snapshot_id="snap-prod-1234",
            snapshot_manifest_digest="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        )
        assert env.snapshot_id == "snap-prod-1234"
        assert len(env.snapshot_manifest_digest) == 64

    def test_structured_warnings_serialization(self):
        warn = ReportWarning(
            code="WARN_DATA_TRIMMING",
            severity="warning",
            message="Date alignment trimmed 25 non-overlapping trading days.",
            affected_metric="cagr_net",
            provenance_ref="ds-us-equities",
        )
        env = create_sample_envelope(warnings=[warn])
        data = json.loads(env.model_dump_json())
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["code"] == "WARN_DATA_TRIMMING"
        assert data["warnings"][0]["severity"] == "warning"
        assert data["warnings"][0]["affected_metric"] == "cagr_net"


class TestExecutiveKPIsAndGrossNetSeparation:
    """Verifies strict separation between gross and net returns and undefined metric behavior."""

    def test_dual_gross_and_net_representation(self):
        kpis = create_sample_kpis(has_gross=True)
        assert kpis.cumulative_return_net == 0.2450
        assert kpis.cumulative_return_gross == 0.2580
        assert kpis.cagr_net == 0.2450
        assert kpis.cagr_gross == 0.2580
        assert kpis.sharpe_ratio_net == 1.4155
        assert kpis.sharpe_ratio_gross == 1.5053
        # Gross Sharpe must strictly exceed Net Sharpe when friction exists
        assert kpis.sharpe_ratio_gross > kpis.sharpe_ratio_net

    def test_net_only_representation_when_gross_unavailable(self):
        kpis = create_sample_kpis(has_gross=False)
        assert kpis.cumulative_return_net == 0.2450
        assert kpis.cumulative_return_gross is None
        assert kpis.sharpe_ratio_gross is None

    def test_undefined_calmar_ratio_when_drawdown_is_zero(self):
        """When max drawdown is zero, Calmar ratio is mathematically undefined (None, never 0.0)."""
        kpis = create_sample_kpis(undefined_calmar=True)
        assert kpis.max_drawdown_net == 0.0
        assert kpis.calmar_ratio_net is None
        assert kpis.calmar_ratio_gross is None

    def test_undefined_sharpe_and_sortino_when_volatility_is_zero(self):
        """When volatility is zero, Sharpe and Sortino are undefined (None)."""
        kpis = create_sample_kpis(zero_vol=True)
        assert kpis.sharpe_ratio_net is None
        assert kpis.sortino_ratio_net is None


class TestBenchmarkRelativeMetrics:
    """Verifies benchmark attribution and active return metrics."""

    def test_valid_benchmark_attribution(self):
        bm = create_sample_benchmark_metrics()
        assert bm.benchmark_id == "SPY:US"
        assert bm.arithmetic_active_return == 0.0630
        assert bm.information_ratio == 1.0222
        assert bm.beta == 0.9250
        assert bm.alpha_annualized == 0.0520

    def test_undefined_information_ratio_when_tracking_error_is_zero(self):
        """When tracking error is zero (identical portfolio/benchmark), IR is undefined (None)."""
        bm = create_sample_benchmark_metrics(has_zero_te=True)
        assert bm.information_ratio is None


class TestStrategyFactSheetContract:
    """Verifies Strategy Fact Sheet 1-page payload contract."""

    def test_fact_sheet_payload_integrity(self):
        fs = get_fixture_3_no_benchmark()
        assert fs.envelope.report_type == "fact_sheet"
        assert fs.benchmark_metrics is None
        assert len(fs.mandate.investment_universe) == 5
        assert len(fs.top_holdings) == 3
        assert len(fs.compact_wealth_curve) == 3
        assert len(fs.monthly_returns) == 3

    def test_fact_sheet_serialization_round_trip(self):
        fs = get_fixture_7_snapshot_provenance()
        json_str = fs.model_dump_json()
        data = json.loads(json_str)
        assert data["envelope"]["snapshot_id"] == "snap-certified-8899"
        assert data["mandate"]["strategy_type"] == "walk_forward_optimization"
        assert data["kpis"]["cumulative_return_net"] == 0.2450


class TestInstitutionalTearSheetContract:
    """Verifies Institutional Tear Sheet 2-page payload contract."""

    def test_tear_sheet_payload_integrity(self):
        ts = get_fixture_1_valid_backtest_with_benchmark()
        assert ts.envelope.report_type == "tear_sheet"
        assert ts.mandate.initial_capital == 100000.0
        assert len(ts.asset_allocation) == 4
        assert ts.friction_and_execution is not None
        assert ts.friction_and_execution.transaction_cost_bps == 10.0
        assert ts.friction_and_execution.slippage_bps == 5.0
        assert len(ts.equity_curve) == 5
        assert len(ts.monthly_returns_table) == 3

    def test_tear_sheet_friction_partial_tca_fixture(self):
        ts = get_fixture_8_partial_tca_no_slippage()
        assert ts.friction_and_execution.slippage_bps == 0.0
        assert ts.friction_and_execution.total_slippage_costs == 0.0
        assert ts.friction_and_execution.total_friction_costs == 245.0

    def test_tear_sheet_empty_allocation_portfolio(self):
        ts = get_fixture_12_empty_allocation_portfolio()
        assert len(ts.asset_allocation) == 0
        assert len(ts.envelope.warnings) == 1
        assert ts.envelope.warnings[0].code == "INFO_SINGLE_ASSET_BENCHMARK_ONLY"


class TestResearchDiagnosticsAnnexContract:
    """Verifies Stage 33 Overfitting Diagnostics Annex payload contract."""

    def test_research_annex_valid_alpha_diagnostics(self):
        annex = get_fixture_9_research_with_valid_diagnostics()
        assert annex.envelope.report_type == "research_diagnostics"
        assert annex.evaluated_runs_count == 20
        assert annex.pbo == 0.125
        assert annex.pbo_risk_level == "low"
        assert annex.deflated_sharpe_ratio == 0.975
        assert annex.is_statistically_significant is True
        assert annex.min_backtest_length_years == 1.85
        assert annex.degradation_regression.slope == 0.65

    def test_research_annex_undefined_min_btl_preserved(self):
        """When strategy fails to exceed expected maximum Sharpe, MinBTL is None, never 0.0."""
        annex = get_fixture_10_research_with_undefined_diagnostics()
        assert annex.pbo == 0.685
        assert annex.pbo_risk_level == "severe"
        assert annex.min_backtest_length_years is None
        assert annex.is_statistically_significant is False
        assert annex.degradation_regression.slope == -0.12


class TestUnifiedReportContainer:
    """Verifies unified multi-report response container."""

    def test_unified_report_response_container(self):
        env = create_sample_envelope(report_type="unified_tear_sheet")
        fs = get_fixture_3_no_benchmark()
        ts = get_fixture_1_valid_backtest_with_benchmark()
        annex = get_fixture_9_research_with_valid_diagnostics()

        unified = InstitutionalReportResponse(
            envelope=env,
            fact_sheet=fs,
            tear_sheet=ts,
            research_annex=annex,
        )
        assert unified.envelope.report_type == "unified_tear_sheet"
        assert unified.fact_sheet is not None
        assert unified.tear_sheet is not None
        assert unified.research_annex is not None

        # Verify serialization round trip
        json_data = json.loads(unified.model_dump_json())
        assert json_data["fact_sheet"]["mandate"]["strategy_type"] == "walk_forward_optimization"
        assert json_data["research_annex"]["pbo_risk_level"] == "low"


class TestMetricRegistryIntegrity:
    """Verifies canonical Metric Registry entries, formulas, units, and undefined rules."""

    def test_registry_contains_core_metrics(self):
        metrics = list_registered_metrics()
        assert len(metrics) >= 15
        ids = {m.canonical_id for m in metrics}
        assert "cumulative_return" in ids
        assert "cagr" in ids
        assert "sharpe_ratio" in ids
        assert "sortino_ratio" in ids
        assert "max_drawdown" in ids
        assert "calmar_ratio" in ids
        assert "tracking_error" in ids
        assert "information_ratio" in ids
        assert "beta" in ids
        assert "alpha" in ids
        assert "menchero_attribution" in ids
        assert "pbo" in ids
        assert "deflated_sharpe_ratio" in ids
        assert "min_backtest_length" in ids

    def test_sharpe_and_cagr_annualization_metadata(self):
        sr = get_metric_definition("sharpe_ratio")
        assert sr is not None
        assert sr.annualized is True
        assert sr.periods_per_year == 252
        assert "r_f" in sr.mathematical_formula
        assert "sigma_ann" in sr.undefined_condition

        cagr = get_metric_definition("cagr")
        assert cagr is not None
        assert cagr.annualized is True
        assert "periods_per_year / T" in cagr.mathematical_formula

    def test_information_ratio_benchmark_requirement(self):
        ir = get_metric_definition("information_ratio")
        assert ir is not None
        assert ir.requires_benchmark is True
        assert ir.return_convention == "net_only"
        assert "TE <= 1e-12" in ir.undefined_condition
