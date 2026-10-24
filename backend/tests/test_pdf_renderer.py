"""
Unit and integration test suite for Stage 34 Gate D Headless Chromium PDF Rendering Pipeline.
Tests:
- Chromium browser binary discovery
- HTML to PDF conversion with sandboxed browser flags
- Exact physical page count verification using pypdf
  * Fact Sheet = exactly 1 page
  * Tear Sheet = exactly 2 pages
  * Research Annex = exactly 1 page
  * Unified Dossier (with Annex) = exactly 3 pages
  * Unified Dossier (without Annex) = exactly 2 pages
- Quantitative non-coercion preservation (None -> '—', zero -> '0.00%')
- XSS and HTML injection escaping
- Temporary file cleanup and bounded resource handling
"""

from __future__ import annotations

import io
import json
import os
from datetime import date, datetime, timezone
from uuid import uuid4
import pypdf
import pytest

from app.db.models import (
    BacktestRunModel,
    DatasetModel,
    DatasetSnapshotModel,
    PerformanceReportModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.db.session import get_db_session
from app.reports.assembler import ReportAssemblerService
from app.reports.contracts import (
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
)
from app.reports.pdf_templates import (
    fmt_bps,
    fmt_currency,
    fmt_date,
    fmt_percent,
    fmt_ratio,
    render_fact_sheet_html,
    render_research_annex_html,
    render_tear_sheet_html,
    render_unified_report_html,
)
from app.reports.renderer import (
    count_pdf_pages,
    get_chromium_executable,
    render_html_to_pdf,
)

USER_1_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def seed_test_user():
    with get_db_session() as session:
        u = session.get(UserModel, USER_1_ID)
        if not u:
            u = UserModel(
                id=USER_1_ID,
                email="user1_renderer@quant.local",
                hashed_password="hash",
                full_name="User 1 Renderer",
                role="researcher",
                is_active=True,
            )
            session.add(u)
            session.commit()
    return UserModel(
        id=USER_1_ID,
        email="user1_renderer@quant.local",
        hashed_password="hash",
        full_name="User 1 Renderer",
        role="researcher",
        is_active=True,
    )


@pytest.fixture
def seed_test_backtest(seed_test_user):
    user = seed_test_user
    dataset_id = str(uuid4())
    snapshot_id = str(uuid4())
    backtest_id = str(uuid4())

    with get_db_session() as session:
        ds = DatasetModel(
            id=dataset_id,
            user_id=user.id,
            filename="us_equities_renderer.csv",
            content_sha256="d" * 64,
            rows_examined=252,
            valid_rows=252,
            rejected_rows=0,
            status="completed",
        )
        session.add(ds)

        snap = DatasetSnapshotModel(
            id=snapshot_id,
            dataset_id=dataset_id,
            user_id=user.id,
            tag="v1.0-renderer-certified",
            manifest_sha256="m" * 64,
            manifest_json=json.dumps({"total_rows": 252}),
            is_frozen=True,
        )
        session.add(snap)

        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 11)]
        equity_curve = []
        val_net = 100000.0
        val_gross = 100000.0
        bm_val = 100000.0
        for i, d in enumerate(dates):
            r = 0.001 * (1.0 if i % 2 == 0 else -0.5)
            val_net *= (1.0 + r)
            val_gross *= (1.0 + r + 0.0001)
            bm_val *= (1.0 + r * 0.9)
            equity_curve.append({
                "date": d,
                "portfolio_value_net": val_net,
                "portfolio_value_gross": val_gross,
                "return_net": r,
                "return_gross": r + 0.0001,
                "drawdown_net": 0.0,
                "drawdown_gross": 0.0,
                "benchmark_value": bm_val,
            })

        summary = {
            "cumulative_return_net": 0.2000,
            "cumulative_return_gross": 0.2250,
            "annualized_return_net": 0.2000,
            "annualized_return_gross": 0.2250,
            "cagr_net": 0.2000,
            "cagr_gross": 0.2250,
            "sharpe_ratio_net": 1.5000,
            "sharpe_ratio_gross": 1.6500,
            "sortino_ratio_net": 2.1000,
            "sortino_ratio_gross": 2.2500,
            "max_drawdown_net": 0.0400,
            "max_drawdown_gross": 0.0380,
            "volatility_annualized_net": 0.1250,
            "downside_deviation_net": 0.0800,
            "win_rate": 0.58,
            "profit_factor": 1.85,
            "total_turnover": 2.50,
            "total_transaction_costs": 250.0,
            "total_slippage_costs": 125.0,
            "total_friction_costs": 375.0,
        }

        strat_cfg = {
            "assets": ["AAPL", "MSFT"],
            "weights": {"AAPL": 0.60, "MSFT": 0.40},
            "strategy_type": "target_weights",
            "rebalance_frequency": "monthly",
            "initial_capital": 100000.0,
            "transaction_cost_bps": 10.0,
            "slippage_bps": 5.0,
            "benchmark_symbol": "SPY",
        }

        bt = BacktestRunModel(
            id=backtest_id,
            user_id=user.id,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            name="Renderer Test Strategy",
            strategy_type="target_weights",
            rebalance_frequency="monthly",
            initial_capital=100000.0,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 2, 10),
            status="completed",
            strategy_config_json=json.dumps(strat_cfg),
            summary_metrics_json=json.dumps(summary),
            equity_curve_json=json.dumps(equity_curve),
            rebalance_events_json=json.dumps([]),
        )
        session.add(bt)
        session.commit()

    return user, backtest_id


@pytest.fixture
def seed_test_experiment(seed_test_user, seed_test_backtest):
    user, backtest_id = seed_test_backtest
    experiment_id = str(uuid4())
    bt_2_id = str(uuid4())
    run_1_id = str(uuid4())
    run_2_id = str(uuid4())

    with get_db_session() as session:
        bt_1 = session.get(BacktestRunModel, backtest_id)
        curve = bt_1.get_equity_curve()

        # Create second backtest for run 2 with slightly perturbed returns
        curve_2 = []
        val_2 = 100000.0
        for pt in curve:
            r = pt["return_net"] * 0.9
            val_2 *= (1.0 + r)
            curve_2.append({
                "date": pt["date"],
                "portfolio_value_net": val_2,
                "portfolio_value_gross": val_2,
                "return_net": r,
                "return_gross": r,
                "drawdown_net": 0.0,
                "drawdown_gross": 0.0,
            })

        bt_2 = BacktestRunModel(
            id=bt_2_id,
            user_id=user.id,
            dataset_id=bt_1.dataset_id,
            snapshot_id=bt_1.snapshot_id,
            name="Renderer Test Strategy 2",
            strategy_type="target_weights",
            rebalance_frequency="monthly",
            initial_capital=100000.0,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            start_date=bt_1.start_date,
            end_date=bt_1.end_date,
            status="completed",
            strategy_config_json=bt_1.strategy_config_json,
            summary_metrics_json=bt_1.summary_metrics_json,
            equity_curve_json=json.dumps(curve_2),
            rebalance_events_json=json.dumps([]),
        )
        session.add(bt_2)

        exp = ResearchExperimentModel(
            id=experiment_id,
            user_id=user.id,
            dataset_id=bt_1.dataset_id,
            name="CSCV Renderer Experiment",
            description="Testing server-side PDF generation for research annex",
            strategy_type="target_weights",
            config_json=json.dumps({"strategy_type": "target_weights"}),
            config_fingerprint="f" * 64,
            version=1,
            created_at=datetime.now(timezone.utc),
        )
        session.add(exp)

        run1 = ResearchExperimentRunModel(
            id=run_1_id,
            experiment_id=experiment_id,
            user_id=user.id,
            run_number=1,
            status="succeeded",
            backtest_id=backtest_id,
            snapshot_id=bt_1.snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        run2 = ResearchExperimentRunModel(
            id=run_2_id,
            experiment_id=experiment_id,
            user_id=user.id,
            run_number=2,
            status="succeeded",
            backtest_id=bt_2_id,
            snapshot_id=bt_1.snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([run1, run2])
        session.commit()

    return user, experiment_id, backtest_id


def test_chromium_executable_discovery():
    """
    Verifies that an authorized headless Chromium browser binary is located on this system.
    """
    path = get_chromium_executable()
    assert os.path.isfile(path), f"Discovered Chromium path is not a file: {path}"


def test_count_pdf_pages_validation():
    """
    Verifies that count_pdf_pages properly rejects malformed bytes and validates magic headers.
    """
    with pytest.raises(ValueError, match="Missing %PDF- magic signature"):
        count_pdf_pages(b"not a pdf")

    with pytest.raises(ValueError, match="Missing %PDF- magic signature"):
        count_pdf_pages(b"")


def test_render_html_to_pdf_basic():
    """
    Verifies that a minimal HTML string is converted to a valid 1-page PDF artifact.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page { size: letter; margin: 10mm; }
            body { font-family: sans-serif; }
        </style>
    </head>
    <body>
        <h1>Institutional Fact Sheet Test</h1>
        <p>Testing deterministic Chromium PDF generation pipeline.</p>
    </body>
    </html>
    """
    pdf_bytes = render_html_to_pdf(html_content, timeout_seconds=30.0)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    pages = count_pdf_pages(pdf_bytes)
    assert pages == 1


def test_formatters_non_coercion_rules():
    """
    Verifies that numerical formatters preserve None / NaN / Inf without coercing to zero.
    """
    assert fmt_percent(None) == "—"
    assert fmt_percent(float("nan")) == "—"
    assert fmt_percent(float("inf")) == "—"
    assert fmt_percent(0.0) == "0.00%"
    assert fmt_percent(0.1234, decimals=2) == "12.34%"
    assert fmt_percent(0.1234, decimals=2, sign=True) == "+12.34%"
    assert fmt_percent(-0.052, decimals=1, sign=True) == "-5.2%"

    assert fmt_ratio(None) == "—"
    assert fmt_ratio(float("nan")) == "—"
    assert fmt_ratio(0.0) == "0.00"
    assert fmt_ratio(1.856) == "1.86"

    assert fmt_bps(None) == "—"
    assert fmt_bps(0.0) == "0.0 bps"
    assert fmt_bps(15.42) == "15.4 bps"

    assert fmt_currency(None) == "—"
    assert fmt_currency(0.0) == "$0"
    assert fmt_currency(1250000.0) == "$1,250,000"

    assert fmt_date(None) == "—"
    assert fmt_date("2025-01-02T12:00:00Z") == "2025-01-02"


def test_html_escaping_prevents_script_injection():
    """
    Verifies that malicious script tags in strategy names, mandates, or warnings are escaped.
    """
    class DummyMandate:
        strategy_type = "<script>alert('xss-attack')</script>"
        investment_universe = ["SPY"]
        rebalance_frequency = "monthly"
        initial_capital = 100000.0

    class DummyEnvelope:
        warnings = []
        base_currency = "USD"
        reporting_start_date = "2024-01-01"
        reporting_end_date = "2024-12-31"
        generated_at = "2024-12-31T23:59:59Z"
        snapshot_id = "test-snap"
        snapshot_manifest_digest = "test-sha"
        regulatory_disclaimer = "Hypothetical performance."

    class DummyPerf:
        cumulative_return_net = 0.15
        cumulative_return_gross = 0.16
        cagr_net = 0.15
        cagr_gross = 0.16
        sharpe_ratio_net = 1.2
        sharpe_ratio_gross = 1.3
        sortino_ratio_net = 1.5
        max_drawdown_net = 0.08
        calmar_ratio_net = 1.875
        annualized_volatility_net = 0.12

    class DummyPayload:
        envelope = DummyEnvelope()
        mandate = DummyMandate()
        kpis = DummyPerf()
        benchmark_metrics = None
        top_holdings = []
        compact_wealth_curve = []
        monthly_returns = []

    html_out = render_fact_sheet_html(DummyPayload())  # type: ignore
    assert "<script>alert('xss-attack')</script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;xss-attack&#x27;)&lt;/script&gt;" in html_out or "&lt;script&gt;alert('xss-attack')&lt;/script&gt;" in html_out


def test_render_strategy_fact_sheet_pdf_exact_page_count(seed_test_backtest):
    """
    Assembles a real Strategy Fact Sheet and verifies it renders to exactly 1 physical PDF page.
    """
    user, backtest_id = seed_test_backtest

    with get_db_session() as session:
        payload = ReportAssemblerService.assemble_fact_sheet(
            backtest_id=backtest_id,
            current_user=user,
            db=session,
        )

    html_doc = render_fact_sheet_html(payload)
    pdf_bytes = render_html_to_pdf(html_doc)

    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 1, f"Expected Strategy Fact Sheet to be exactly 1 page, got {pages}"


def test_render_institutional_tear_sheet_pdf_exact_page_count(seed_test_backtest):
    """
    Assembles an Institutional Tear Sheet and verifies it renders to exactly 2 physical PDF pages.
    """
    user, backtest_id = seed_test_backtest

    with get_db_session() as session:
        payload = ReportAssemblerService.assemble_tear_sheet(
            backtest_id=backtest_id,
            current_user=user,
            db=session,
        )

    html_doc = render_tear_sheet_html(payload)
    pdf_bytes = render_html_to_pdf(html_doc)

    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 2, f"Expected Institutional Tear Sheet to be exactly 2 pages, got {pages}"


def test_render_research_diagnostics_annex_pdf_exact_page_count(seed_test_experiment):
    """
    Assembles a Research Diagnostics Annex and verifies it renders to exactly 1 physical PDF page.
    """
    user, experiment_id, _ = seed_test_experiment

    with get_db_session() as session:
        payload = ReportAssemblerService.assemble_research_annex(
            experiment_id=experiment_id,
            current_user=user,
            db=session,
        )

    html_doc = render_research_annex_html(payload)
    pdf_bytes = render_html_to_pdf(html_doc)

    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 1, f"Expected Research Diagnostics Annex to be exactly 1 page, got {pages}"


def test_render_unified_report_pdf_exact_page_counts(seed_test_experiment):
    """
    Verifies that the Unified Institutional Report renders:
    - Exactly 2 pages when research annex is not linked.
    - Exactly 3 pages when research annex is bundled.
    """
    user, experiment_id, backtest_id = seed_test_experiment

    # Create a standalone backtest not linked to any research experiment run
    standalone_id = str(uuid4())
    with get_db_session() as session:
        bt_linked = session.get(BacktestRunModel, backtest_id)
        standalone = BacktestRunModel(
            id=standalone_id,
            user_id=user.id,
            dataset_id=bt_linked.dataset_id,
            snapshot_id=bt_linked.snapshot_id,
            name="Standalone Unified Mandate",
            strategy_type=bt_linked.strategy_type,
            rebalance_frequency=bt_linked.rebalance_frequency,
            initial_capital=bt_linked.initial_capital,
            transaction_cost_bps=bt_linked.transaction_cost_bps,
            slippage_bps=bt_linked.slippage_bps,
            start_date=bt_linked.start_date,
            end_date=bt_linked.end_date,
            status="completed",
            strategy_config_json=bt_linked.strategy_config_json,
            summary_metrics_json=bt_linked.summary_metrics_json,
            equity_curve_json=bt_linked.equity_curve_json,
            rebalance_events_json=json.dumps([]),
        )
        session.add(standalone)
        session.commit()

    # 1. Without Annex (2 pages)
    with get_db_session() as session:
        report_no_annex = ReportAssemblerService.assemble_unified_report(
            backtest_id=standalone_id,
            current_user=user,
            db=session,
            experiment_id=None,
        )

    html_no_annex = render_unified_report_html(report_no_annex)
    pdf_no_annex = render_html_to_pdf(html_no_annex)
    pages_no_annex = count_pdf_pages(pdf_no_annex)
    assert pages_no_annex == 2, f"Expected Unified Report without annex to be 2 pages, got {pages_no_annex}"

    # 2. With Annex (3 pages)
    with get_db_session() as session:
        report_with_annex = ReportAssemblerService.assemble_unified_report(
            backtest_id=backtest_id,
            current_user=user,
            db=session,
            experiment_id=experiment_id,
        )

    html_with_annex = render_unified_report_html(report_with_annex)
    pdf_with_annex = render_html_to_pdf(html_with_annex)
    pages_with_annex = count_pdf_pages(pdf_with_annex)
    assert pages_with_annex == 3, f"Expected Unified Report with annex to be 3 pages, got {pages_with_annex}"
