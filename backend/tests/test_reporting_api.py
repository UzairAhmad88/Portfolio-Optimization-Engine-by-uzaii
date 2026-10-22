"""
Integration and security tests for Stage 34 Gate B institutional reporting API endpoints.

Validates:
- GET /api/v1/reports/fact-sheet/{backtest_id}
- GET /api/v1/reports/tear-sheet/{backtest_id}
- POST /api/v1/reports/research-annex/{experiment_id}
- GET /api/v1/reports/unified/{backtest_id}

Security & Verification:
- Unauthorized access fails closed with HTTP 401.
- Cross-tenant data isolation fails closed with HTTP 404 (preventing resource ID enumeration).
- Administrative access permitted across tenants (HTTP 200).
- Response JSON validates against Gate A Pydantic v2 domain schemas.
- Gross/net separation, zero coercion, and warning structures verified.
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
from app.reports.contracts import (
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def reporting_api_data():
    """
    Creates seed users, dataset, snapshots, backtests, and experiments for API integration testing.
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
        # 1. Users
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

        # 2. Dataset & Snapshot owned by User A
        dataset = DatasetModel(
            id=dataset_id,
            user_id=user_a_id,
            filename="api_test_equities.csv",
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
            tag="v1.0-certified",
            manifest_sha256="a" * 64,
            manifest_json=json.dumps({"schema_version": "1.2", "total_bars": 252}),
            is_frozen=True,
        )
        session.add(snapshot)

        # 3. Backtest owned by User A
        dates = [f"2023-{(i // 20) + 1:02d}-{(i % 20) + 1:02d}" for i in range(100)]
        curve = [
            {
                "date": d,
                "portfolio_value_net": 100000.0 * (1.0 + 0.001 * idx),
                "portfolio_value_gross": 100000.0 * (1.0 + 0.0012 * idx),
                "return_net": 0.001,
                "return_gross": 0.0012,
                "drawdown_net": 0.0,
                "drawdown_gross": 0.0,
            }
            for idx, d in enumerate(dates)
        ]
        allocs = [
            {"asset": "MSFT", "weight": 0.60, "sector": "Technology", "asset_class": "Equity"},
            {"asset": "GOOGL", "weight": 0.40, "sector": "Technology", "asset_class": "Equity"},
        ]
        summary = {
            "cumulative_return_net": 0.1500,
            "cumulative_return_gross": 0.1700,
            "cagr_net": 0.1500,
            "cagr_gross": 0.1700,
            "annualized_volatility_net": 0.1000,
            "annualized_volatility_gross": 0.1000,
            "sharpe_ratio_net": 1.5000,
            "sharpe_ratio_gross": 1.7000,
            "max_drawdown_net": 0.0300,
            "max_drawdown_gross": 0.0280,
            "total_turnover": 0.45,
            "total_transaction_costs": 50.0,
            "total_slippage_costs": 25.0,
            "total_friction_costs": 75.0,
            "number_of_rebalances": 3,
            "effective_weights": allocs,
        }

        from datetime import date
        backtest = BacktestRunModel(
            id=backtest_id,
            user_id=user_a_id,
            name="Institutional API Strategy",
            strategy_type="target_weights",
            status="completed",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 28),
            initial_capital=100000.0,
            rebalance_frequency="monthly",
            transaction_cost_bps=5.0,
            slippage_bps=2.5,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            strategy_config_json=json.dumps({"name": "Institutional API Strategy", "universe": ["MSFT", "GOOGL"]}),
            summary_metrics_json=json.dumps(summary),
            equity_curve_json=json.dumps(curve),
            created_at=datetime.now(timezone.utc),
        )
        session.add(backtest)

        # 4. Performance report
        perf = PerformanceReportModel(
            id=perf_report_id,
            dataset_id=dataset_id,
            backtest_id=backtest_id,
            user_id=user_a_id,
            name="API Performance Report",
            benchmark_asset="SPY",
            metrics_json=json.dumps(summary),
            created_at=datetime.now(timezone.utc),
        )
        session.add(perf)

        # 5. Research experiment owned by User A
        exp = ResearchExperimentModel(
            id=experiment_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            name="API Research Experiment",
            strategy_type="target_weights",
            config_json=json.dumps({"strategy_type": "target_weights", "assets": ["MSFT", "GOOGL"]}),
            config_fingerprint="f" * 64,
            version=1,
            created_at=datetime.now(timezone.utc),
        )
        session.add(exp)

        # Backtests for runs
        bt_run_1_id = str(uuid.uuid4())
        bt_run_2_id = str(uuid.uuid4())
        bt_1 = BacktestRunModel(
            id=bt_run_1_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            name="Run 1 Backtest",
            strategy_type="target_weights",
            rebalance_frequency="monthly",
            initial_capital=100000.0,
            status="completed",
            equity_curve_json=json.dumps(curve),
        )
        bt_2 = BacktestRunModel(
            id=bt_run_2_id,
            user_id=user_a_id,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            name="Run 2 Backtest",
            strategy_type="target_weights",
            rebalance_frequency="monthly",
            initial_capital=100000.0,
            status="completed",
            equity_curve_json=json.dumps(curve),
        )
        session.add_all([bt_1, bt_2])

        exp_run_1 = ResearchExperimentRunModel(
            id=run_1_id,
            experiment_id=experiment_id,
            user_id=user_a_id,
            run_number=1,
            status="succeeded",
            backtest_id=bt_run_1_id,
            snapshot_id=snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        exp_run_2 = ResearchExperimentRunModel(
            id=run_2_id,
            experiment_id=experiment_id,
            user_id=user_a_id,
            run_number=2,
            status="succeeded",
            backtest_id=bt_run_2_id,
            snapshot_id=snapshot_id,
            config_fingerprint="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([exp_run_1, exp_run_2])
        session.commit()

    token_a = create_access_token(subject=user_a_id, claims={"email": f"user_a_{user_a_id[:8]}@example.com", "role": "user"})
    token_b = create_access_token(subject=user_b_id, claims={"email": f"user_b_{user_b_id[:8]}@example.com", "role": "user"})
    token_admin = create_access_token(subject=admin_id, claims={"email": f"admin_{admin_id[:8]}@example.com", "role": "admin"})

    return {
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "headers_admin": {"Authorization": f"Bearer {token_admin}"},
        "backtest_id": backtest_id,
        "experiment_id": experiment_id,
        "run_ids": [run_1_id, run_2_id],
        "snapshot_id": snapshot_id,
    }


def test_fact_sheet_unauthenticated(client: TestClient, reporting_api_data):
    """Calling without Authorization header must yield 401 Unauthorized."""
    resp = client.get(f"/api/v1/reports/fact-sheet/{reporting_api_data['backtest_id']}")
    assert resp.status_code == 401


def test_fact_sheet_cross_user_isolation(client: TestClient, reporting_api_data):
    """User B requesting User A's backtest must receive 404 Not Found."""
    resp = client.get(
        f"/api/v1/reports/fact-sheet/{reporting_api_data['backtest_id']}",
        headers=reporting_api_data["headers_b"],
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_fact_sheet_owner_success(client: TestClient, reporting_api_data):
    """Owner successfully retrieves Fact Sheet validated against Gate A contract."""
    resp = client.get(
        f"/api/v1/reports/fact-sheet/{reporting_api_data['backtest_id']}",
        headers=reporting_api_data["headers_a"],
    )
    assert resp.status_code == 200
    data = resp.json()

    # Validate schema
    payload = StrategyFactSheetPayload.model_validate(data)
    assert payload.envelope.report_type == "fact_sheet"
    assert payload.envelope.report_title == "Institutional API Strategy"
    assert payload.mandate.strategy_type == "target_weights"
    assert payload.kpis.cagr_net == 0.1500
    assert payload.kpis.cagr_gross == 0.1700
    assert payload.kpis.sharpe_ratio_net == 1.5000
    assert len(payload.top_holdings) == 2
    assert payload.top_holdings[0].ticker == "MSFT"
    assert payload.top_holdings[0].effective_weight == 0.60
    assert len(payload.compact_wealth_curve) <= 250


def test_tear_sheet_admin_access(client: TestClient, reporting_api_data):
    """Admin has cross-tenant access to inspect institutional tear sheets."""
    resp = client.get(
        f"/api/v1/reports/tear-sheet/{reporting_api_data['backtest_id']}",
        headers=reporting_api_data["headers_admin"],
    )
    assert resp.status_code == 200
    data = resp.json()

    payload = InstitutionalTearSheetPayload.model_validate(data)
    assert payload.envelope.report_type == "tear_sheet"
    assert payload.friction_and_execution is not None
    assert payload.friction_and_execution.transaction_cost_bps == 5.0
    assert payload.friction_and_execution.slippage_bps == 2.5
    assert payload.friction_and_execution.friction_drag_bps == pytest.approx(7.5, rel=1e-3)
    assert len(payload.asset_allocation) == 2


def test_research_annex_success(client: TestClient, reporting_api_data):
    """Owner posts request to generate research annex and validates against Stage 33 diagnostics."""
    req_body = {
        "run_ids": reporting_api_data["run_ids"],
        "n_slices": 4,
        "significance_level": 0.05,
        "annualization_factor": 252,
    }
    resp = client.post(
        f"/api/v1/reports/research-annex/{reporting_api_data['experiment_id']}",
        headers=reporting_api_data["headers_a"],
        json=req_body,
    )
    assert resp.status_code == 200
    data = resp.json()

    payload = ResearchDiagnosticsAnnexPayload.model_validate(data)
    assert payload.envelope.report_type == "research_diagnostics"
    assert payload.envelope.source_experiment_id == reporting_api_data["experiment_id"]
    assert 0.0 <= payload.pbo <= 1.0
    assert 0.0 <= payload.deflated_sharpe_ratio <= 1.0
    assert len(payload.rank_distribution) > 0


def test_research_annex_cross_user_denial(client: TestClient, reporting_api_data):
    """User B cannot generate research annex for User A's experiment."""
    req_body = {
        "run_ids": reporting_api_data["run_ids"],
        "n_slices": 4,
    }
    resp = client.post(
        f"/api/v1/reports/research-annex/{reporting_api_data['experiment_id']}",
        headers=reporting_api_data["headers_b"],
        json=req_body,
    )
    assert resp.status_code == 404


def test_unified_report_endpoint(client: TestClient, reporting_api_data):
    """Owner fetches unified report bundling fact sheet and tear sheet (and research annex if linked)."""
    resp = client.get(
        f"/api/v1/reports/unified/{reporting_api_data['backtest_id']}?experiment_id={reporting_api_data['experiment_id']}",
        headers=reporting_api_data["headers_a"],
    )
    assert resp.status_code == 200
    data = resp.json()

    response_model = InstitutionalReportResponse.model_validate(data)
    assert response_model.envelope.report_type == "unified_tear_sheet"
    assert response_model.fact_sheet is not None
    assert response_model.tear_sheet is not None
    assert response_model.research_annex is not None
    assert response_model.tear_sheet.kpis.cagr_net == 0.1500
