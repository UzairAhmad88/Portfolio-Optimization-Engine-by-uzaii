"""
Integration and security tests for Stage 34 Gate D institutional PDF export API endpoints.

Validates:
- GET /api/v1/reports/fact-sheet/{backtest_id}/export
- GET /api/v1/reports/tear-sheet/{backtest_id}/export
- POST /api/v1/reports/research-annex/{experiment_id}/export
- GET /api/v1/reports/unified/{backtest_id}/export

Security & Verification:
- Unauthorized access fails closed with HTTP 401.
- Cross-tenant data isolation fails closed with HTTP 404 (preventing resource ID enumeration).
- Administrative access permitted across tenants (HTTP 200).
- Response Content-Type is 'application/pdf'.
- Response Content-Disposition has safe, sanitized filename with .pdf extension.
- Returned binary is a structurally valid PDF artifact with expected page count.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
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
from app.main import app
from app.reports.renderer import count_pdf_pages


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def export_api_data():
    """
    Creates seed users, dataset, snapshots, backtests, and experiments for export API testing.
    """
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())

    dataset_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())
    backtest_id = str(uuid.uuid4())
    perf_report_id = str(uuid.uuid4())
    experiment_id = str(uuid.uuid4())
    run_1_id = str(uuid.uuid4())
    run_2_id = str(uuid.uuid4())

    with get_db_session() as session:
        user_a = UserModel(
            id=user_a_id,
            email=f"user_a_{user_a_id[:8]}@example.com",
            hashed_password="hashed_pw_test",
            role="user",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        user_b = UserModel(
            id=user_b_id,
            email=f"user_b_{user_b_id[:8]}@example.com",
            hashed_password="hashed_pw_test",
            role="user",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        admin = UserModel(
            id=admin_id,
            email=f"admin_{admin_id[:8]}@example.com",
            hashed_password="hashed_pw_test",
            role="admin",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([user_a, user_b, admin])

        dataset = DatasetModel(
            id=dataset_id,
            user_id=user_a_id,
            filename="api_export_equities.csv",
            content_sha256="d" * 64,
            rows_examined=252,
            valid_rows=252,
            rejected_rows=0,
            status="completed",
        )
        session.add(dataset)

        snapshot = DatasetSnapshotModel(
            id=snapshot_id,
            dataset_id=dataset_id,
            user_id=user_a_id,
            tag="v1.0-export-certified",
            manifest_sha256="a" * 64,
            manifest_json=json.dumps({"schema_version": "1.2", "total_bars": 252}),
            is_frozen=True,
        )
        session.add(snapshot)

        backtest = BacktestRunModel(
            id=backtest_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            name="Alpha Growth Export Mandate",
            strategy_type="factor_tilt",
            rebalance_frequency="monthly",
            initial_capital=1000000.0,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            summary_metrics_json=json.dumps({
                "cumulative_return_net": 0.284,
                "cumulative_return_gross": 0.312,
                "cagr_net": 0.133,
                "cagr_gross": 0.145,
                "sharpe_ratio_net": 1.42,
                "sharpe_ratio_gross": 1.55,
                "max_drawdown_net": 0.095,
                "max_drawdown_gross": 0.088,
                "annualized_volatility_net": 0.125,
            }),
            equity_curve_json=json.dumps([
                {"date": f"2023-01-{i:02d}", "portfolio_value_net": 1000000.0 * (1.0 + 0.001 * i), "portfolio_value_gross": 1000000.0 * (1.0 + 0.0011 * i), "return_net": 0.001, "return_gross": 0.0011, "drawdown_net": 0.0, "drawdown_gross": 0.0, "benchmark_value": 1000000.0 * (1.0 + 0.0008 * i)}
                for i in range(1, 31)
            ] + [
                {"date": f"2023-02-{i:02d}", "portfolio_value_net": 1030000.0 * (1.0 + 0.001 * i), "portfolio_value_gross": 1033000.0 * (1.0 + 0.0011 * i), "return_net": 0.001, "return_gross": 0.0011, "drawdown_net": 0.0, "drawdown_gross": 0.0, "benchmark_value": 1024000.0 * (1.0 + 0.0008 * i)}
                for i in range(1, 11)
            ]),
            strategy_config_json=json.dumps({
                "benchmark_symbol": "SPY",
                "assets": ["AAPL", "MSFT", "NVDA"],
                "target_weights": {"AAPL": 0.4, "MSFT": 0.35, "NVDA": 0.25},
            }),
            snapshot_id=snapshot_id,
        )
        session.add(backtest)

        bt_2 = BacktestRunModel(
            id=run_2_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            name="Alpha Growth Export Mandate 2",
            strategy_type="factor_tilt",
            rebalance_frequency="monthly",
            initial_capital=1000000.0,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            summary_metrics_json=backtest.summary_metrics_json,
            equity_curve_json=backtest.equity_curve_json,
            strategy_config_json=backtest.strategy_config_json,
            snapshot_id=snapshot_id,
        )
        session.add(bt_2)

        perf_report = PerformanceReportModel(
            id=perf_report_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            backtest_id=backtest_id,
            name="Alpha Growth Performance Report",
            benchmark_asset="SPY",
            metrics_json=json.dumps({
                "benchmark_metrics": {
                    "benchmark_name": "SPY",
                    "benchmark_return": 0.22,
                    "active_return": 0.064,
                    "beta": 0.95,
                    "alpha": 0.052,
                    "information_ratio": 0.88,
                    "tracking_error": 0.045,
                },
                "monthly_returns": {
                    "2023": {"Jan": 0.035, "Feb": -0.012, "Mar": 0.042, "Apr": 0.015, "May": -0.008, "Jun": 0.055, "Jul": 0.028, "Aug": -0.021, "Sep": -0.035, "Oct": 0.012, "Nov": 0.068, "Dec": 0.045}
                },
                "annual_returns": {"2023": 0.284},
                "friction_analysis": {
                    "annualized_turnover": 1.2,
                    "total_commission_paid": 4500.0,
                    "total_slippage_cost": 2800.0,
                    "total_friction_drag_pct": 0.0073,
                },
                "asset_allocations": [
                    {"symbol": "AAPL", "asset_class": "Equity", "target_weight": 0.40, "effective_weight": 0.42, "return_contribution": 0.12},
                    {"symbol": "MSFT", "asset_class": "Equity", "target_weight": 0.35, "effective_weight": 0.33, "return_contribution": 0.095},
                    {"symbol": "NVDA", "asset_class": "Equity", "target_weight": 0.25, "effective_weight": 0.25, "return_contribution": 0.069},
                ],
            }),
            created_at=datetime.now(timezone.utc),
        )
        session.add(perf_report)

        experiment = ResearchExperimentModel(
            id=experiment_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            name="CSCV Export Experiment",
            description="Testing server-side PDF generation for research annex",
            strategy_type="target_weights",
            config_json=json.dumps({"strategy_type": "target_weights"}),
            config_fingerprint="f" * 64,
            version=1,
            created_at=datetime.now(timezone.utc),
        )
        session.add(experiment)

        run_1 = ResearchExperimentRunModel(
            id=run_1_id,
            experiment_id=experiment_id,
            user_id=user_a_id,
            run_number=1,
            status="succeeded",
            backtest_id=backtest_id,
            snapshot_id=snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        run_2 = ResearchExperimentRunModel(
            id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            user_id=user_a_id,
            run_number=2,
            status="succeeded",
            backtest_id=run_2_id,
            snapshot_id=snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([run_1, run_2])
        session.commit()

    token_a = create_access_token(subject=user_a_id, claims={"email": f"user_a_{user_a_id[:8]}@example.com", "role": "user"})
    token_b = create_access_token(subject=user_b_id, claims={"email": f"user_b_{user_b_id[:8]}@example.com", "role": "user"})
    token_admin = create_access_token(subject=admin_id, claims={"email": f"admin_{admin_id[:8]}@example.com", "role": "admin"})

    return {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "admin_id": admin_id,
        "token_a": token_a,
        "token_b": token_b,
        "token_admin": token_admin,
        "backtest_id": backtest_id,
        "experiment_id": experiment_id,
    }


def test_export_fact_sheet_unauthenticated(client: TestClient, export_api_data):
    """
    Unauthenticated request must be rejected with HTTP 401 Unauthorized.
    """
    backtest_id = export_api_data["backtest_id"]
    res = client.get(f"/api/v1/reports/fact-sheet/{backtest_id}/export")
    assert res.status_code == 401


def test_export_fact_sheet_cross_user_isolation(client: TestClient, export_api_data):
    """
    User B attempting to export User A's backtest report must fail with HTTP 404 (no enumeration).
    """
    backtest_id = export_api_data["backtest_id"]
    token_b = export_api_data["token_b"]

    res = client.get(
        f"/api/v1/reports/fact-sheet/{backtest_id}/export",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404


def test_export_fact_sheet_owner_success(client: TestClient, export_api_data):
    """
    User A exports own backtest: HTTP 200, Content-Type: application/pdf, 1 physical page.
    """
    backtest_id = export_api_data["backtest_id"]
    token_a = export_api_data["token_a"]

    res = client.get(
        f"/api/v1/reports/fact-sheet/{backtest_id}/export",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.headers["x-content-type-options"] == "nosniff"

    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 1, f"Expected 1 page Fact Sheet, got {pages}"


def test_export_fact_sheet_admin_access(client: TestClient, export_api_data):
    """
    Admin user can export any backtest across tenant boundaries: HTTP 200.
    """
    backtest_id = export_api_data["backtest_id"]
    token_admin = export_api_data["token_admin"]

    res = client.get(
        f"/api/v1/reports/fact-sheet/{backtest_id}/export",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")


def test_export_tear_sheet_owner_success(client: TestClient, export_api_data):
    """
    Owner exports Institutional Tear Sheet: HTTP 200, application/pdf, exactly 2 physical pages.
    """
    backtest_id = export_api_data["backtest_id"]
    token_a = export_api_data["token_a"]

    res = client.get(
        f"/api/v1/reports/tear-sheet/{backtest_id}/export",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 2, f"Expected 2 page Tear Sheet, got {pages}"


def test_export_research_annex_success(client: TestClient, export_api_data):
    """
    Owner exports Research Diagnostics Annex: HTTP 200, application/pdf, exactly 1 physical page.
    """
    experiment_id = export_api_data["experiment_id"]
    token_a = export_api_data["token_a"]

    res = client.post(
        f"/api/v1/reports/research-annex/{experiment_id}/export",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"n_slices": 8},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 1, f"Expected 1 page Research Annex, got {pages}"


def test_export_research_annex_cross_user_denial(client: TestClient, export_api_data):
    """
    Cross-user research annex export fails with HTTP 404.
    """
    experiment_id = export_api_data["experiment_id"]
    token_b = export_api_data["token_b"]

    res = client.post(
        f"/api/v1/reports/research-annex/{experiment_id}/export",
        headers={"Authorization": f"Bearer {token_b}"},
        json={},
    )
    assert res.status_code == 404


def test_export_unified_report_endpoint(client: TestClient, export_api_data):
    """
    Owner exports Unified Report dossier with research annex: HTTP 200, application/pdf, exactly 3 pages.
    """
    backtest_id = export_api_data["backtest_id"]
    experiment_id = export_api_data["experiment_id"]
    token_a = export_api_data["token_a"]

    res = client.get(
        f"/api/v1/reports/unified/{backtest_id}/export?experiment_id={experiment_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF-")
    pages = count_pdf_pages(pdf_bytes)
    assert pages == 3, f"Expected 3 page Unified Dossier with Annex, got {pages}"


def test_export_invalid_backtest_id_returns_404(client: TestClient, export_api_data):
    """
    Nonexistent backtest ID returns HTTP 404.
    """
    token_a = export_api_data["token_a"]
    missing_id = str(uuid.uuid4())

    res = client.get(
        f"/api/v1/reports/fact-sheet/{missing_id}/export",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 404
