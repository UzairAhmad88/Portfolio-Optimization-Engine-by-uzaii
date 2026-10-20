"""
API integration and security tests for Performance Attribution and Benchmark Analysis.
Tests authentication enforcement, tenant isolation, backtest integration, and report CRUD.
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.db.models import UserModel
from app.db.session import get_db_session
from app.main import app

client = TestClient(app)

USER_A_ID = "00000000-0000-0000-0000-00000000000a"
USER_B_ID = "00000000-0000-0000-0000-00000000000b"


@pytest.fixture
def auth_headers_user_a():
    """Generates valid JWT auth header for User A."""
    token = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user.a@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b():
    """Generates valid JWT auth header for User B."""
    token = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user.b@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_users():
    """Seeds test users A and B in database."""
    with get_db_session() as session:
        u_a = session.get(UserModel, USER_A_ID)
        if not u_a:
            u_a = UserModel(
                id=USER_A_ID,
                email="user.a@quant.local",
                hashed_password=hash_password("Password123!"),
                full_name="Researcher A",
                role="researcher",
                is_active=True,
            )
            session.add(u_a)

        u_b = session.get(UserModel, USER_B_ID)
        if not u_b:
            u_b = UserModel(
                id=USER_B_ID,
                email="user.b@quant.local",
                hashed_password=hash_password("Password123!"),
                full_name="Researcher B",
                role="researcher",
                is_active=True,
            )
            session.add(u_b)
        session.commit()


@pytest.fixture
def registered_dataset_with_benchmark(auth_headers_user_a):
    """Uploads and registers a verified dataset owned by User A with AAPL, MSFT, and SPY."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    aapl_prices = [150.0, 152.0, 151.0, 153.0, 155.0, 154.0, 156.0, 158.0, 157.0, 160.0]
    msft_prices = [240.0, 242.0, 241.0, 243.0, 245.0, 244.0, 246.0, 248.0, 247.0, 250.0]
    spy_prices = [390.0, 392.0, 391.0, 393.0, 394.0, 393.5, 395.0, 397.0, 396.0, 399.0]

    for day_idx in range(1, 11):
        dt_str = f"2023-01-{day_idx:02d}"
        p_a = aapl_prices[day_idx - 1]
        p_m = msft_prices[day_idx - 1]
        p_s = spy_prices[day_idx - 1]
        lines.append(f"{dt_str},AAPL,US,USD,{p_a},{p_a+1},{p_a-1},{p_a},1000,{p_a}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_m},{p_m+1},{p_m-1},{p_m},1000,{p_m}")
        lines.append(f"{dt_str},SPY,US,USD,{p_s},{p_s+1},{p_s-1},{p_s},5000,{p_s}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech_and_spy_10d.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


def test_unauthenticated_performance_analyze_rejected():
    """Unauthenticated POST /api/v1/performance/analyze returns 401 Unauthorized."""
    resp = client.post(
        "/api/v1/performance/analyze",
        json={
            "dataset_id": "dummy-id",
            "benchmark_asset": "SPY:US",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
        },
    )
    assert resp.status_code == 401


def test_unauthenticated_backtest_performance_rejected():
    """Unauthenticated GET /api/v1/performance/backtests/{id} returns 401 Unauthorized."""
    resp = client.get(
        "/api/v1/performance/backtests/dummy-id?benchmark_asset=SPY:US",
    )
    assert resp.status_code == 401


def test_authenticated_performance_analysis_custom_portfolio(auth_headers_user_a, registered_dataset_with_benchmark):
    """User A analyzes performance of AAPL+MSFT portfolio against SPY benchmark."""
    dataset_id = registered_dataset_with_benchmark
    payload = {
        "dataset_id": dataset_id,
        "name": "Tech Duo vs SPY",
        "benchmark_asset": "SPY:US",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.6, "MSFT:US": 0.4},
        "risk_free_rate": 0.02,
        "save_report": True,
    }

    resp = client.post("/api/v1/performance/analyze", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["name"] == "Tech Duo vs SPY"
    assert data["benchmark_asset"] == "SPY:US"
    assert "metrics" in data
    m = data["metrics"]
    assert m["observation_count"] == 9  # 10 price bars -> 9 daily returns
    assert m["portfolio_cumulative_return"] is not None
    assert m["benchmark_cumulative_return"] is not None
    assert m["arithmetic_active_return"] is not None
    assert m["tracking_error"] >= 0.0

    # Verify asset contributions
    assert len(data["contributions"]) == 2
    contrib_assets = {c["asset"] for c in data["contributions"]}
    assert "AAPL:US" in contrib_assets
    assert "MSFT:US" in contrib_assets

    # Verify timeseries points
    assert len(data["timeseries"]) == 9
    first_pt = data["timeseries"][0]
    assert "portfolio_return" in first_pt
    assert "benchmark_return" in first_pt
    assert "active_return" in first_pt


def test_cross_tenant_dataset_access_blocked(auth_headers_user_b, registered_dataset_with_benchmark):
    """User B cannot run performance analysis on User A's private dataset."""
    dataset_id = registered_dataset_with_benchmark
    payload = {
        "dataset_id": dataset_id,
        "name": "Unauthorized Analysis",
        "benchmark_asset": "SPY:US",
        "assets": ["AAPL:US"],
        "weights": {"AAPL:US": 1.0},
    }

    resp = client.post("/api/v1/performance/analyze", json=payload, headers=auth_headers_user_b)
    assert resp.status_code in (403, 404)


def test_backtest_performance_evaluation_endpoint(auth_headers_user_a, registered_dataset_with_benchmark):
    """User A runs a backtest and evaluates its performance against benchmark via GET /performance/backtests/{id}."""
    dataset_id = registered_dataset_with_benchmark

    # 1. Run backtest
    bt_payload = {
        "dataset_id": dataset_id,
        "name": "Backtest For Attribution",
        "strategy_type": "target_weights",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
        "rebalance_frequency": "monthly",
        "initial_capital": 100000.0,
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }
    bt_resp = client.post("/api/v1/backtests", json=bt_payload, headers=auth_headers_user_a)
    assert bt_resp.status_code in (200, 201)
    backtest_id = bt_resp.json()["id"]

    # 2. Evaluate performance of backtest vs SPY
    eval_resp = client.get(
        f"/api/v1/performance/backtests/{backtest_id}?benchmark_asset=SPY:US&risk_free_rate=0.01&save_report=true",
        headers=auth_headers_user_a,
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()

    assert eval_data["backtest_id"] == backtest_id
    assert eval_data["benchmark_asset"] == "SPY:US"
    assert eval_data["metrics"]["portfolio_cumulative_return"] is not None
    assert eval_data["metrics"]["benchmark_cumulative_return"] is not None


def test_cross_tenant_backtest_evaluation_blocked(auth_headers_user_a, auth_headers_user_b, registered_dataset_with_benchmark):
    """User B cannot evaluate performance of User A's saved backtest."""
    dataset_id = registered_dataset_with_benchmark

    bt_payload = {
        "dataset_id": dataset_id,
        "name": "User A Private Backtest",
        "strategy_type": "target_weights",
        "assets": ["AAPL:US"],
        "weights": {"AAPL:US": 1.0},
        "rebalance_frequency": "monthly",
    }
    bt_resp = client.post("/api/v1/backtests", json=bt_payload, headers=auth_headers_user_a)
    assert bt_resp.status_code in (200, 201)
    backtest_id = bt_resp.json()["id"]

    # User B attempts to evaluate User A's backtest
    eval_resp = client.get(
        f"/api/v1/performance/backtests/{backtest_id}?benchmark_asset=SPY:US",
        headers=auth_headers_user_b,
    )
    assert eval_resp.status_code in (403, 404)


def test_saved_performance_reports_crud_and_tenant_isolation(auth_headers_user_a, auth_headers_user_b, registered_dataset_with_benchmark):
    """Verify saved performance report CRUD operations and tenant isolation."""
    dataset_id = registered_dataset_with_benchmark

    # 1. User A saves a report
    payload = {
        "dataset_id": dataset_id,
        "name": "Persisted Tech vs SPY",
        "benchmark_asset": "SPY:US",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
        "save_report": True,
    }
    create_resp = client.post("/api/v1/performance/analyze", json=payload, headers=auth_headers_user_a)
    assert create_resp.status_code == 200
    report_id = create_resp.json()["id"]

    # 2. User A lists reports -> includes report_id
    list_resp_a = client.get("/api/v1/performance/reports", headers=auth_headers_user_a)
    assert list_resp_a.status_code == 200
    ids_a = [r["id"] for r in list_resp_a.json()]
    assert report_id in ids_a

    # 3. User B lists reports -> does NOT include report_id
    list_resp_b = client.get("/api/v1/performance/reports", headers=auth_headers_user_b)
    assert list_resp_b.status_code == 200
    ids_b = [r["id"] for r in list_resp_b.json()]
    assert report_id not in ids_b

    # 4. User B cannot get User A's report
    get_resp_b = client.get(f"/api/v1/performance/reports/{report_id}", headers=auth_headers_user_b)
    assert get_resp_b.status_code == 404

    # 5. User B cannot delete User A's report
    del_resp_b = client.delete(f"/api/v1/performance/reports/{report_id}", headers=auth_headers_user_b)
    assert del_resp_b.status_code == 404

    # 6. User A gets the report
    get_resp_a = client.get(f"/api/v1/performance/reports/{report_id}", headers=auth_headers_user_a)
    assert get_resp_a.status_code == 200
    assert get_resp_a.json()["id"] == report_id

    # 7. User A deletes the report
    del_resp_a = client.delete(f"/api/v1/performance/reports/{report_id}", headers=auth_headers_user_a)
    assert del_resp_a.status_code == 204

    # 8. Report no longer exists
    get_after_del = client.get(f"/api/v1/performance/reports/{report_id}", headers=auth_headers_user_a)
    assert get_after_del.status_code == 404


def test_missing_benchmark_asset_returns_404(auth_headers_user_a, registered_dataset_with_benchmark):
    """Request specifying non-existent benchmark asset returns 404 with actionable error."""
    dataset_id = registered_dataset_with_benchmark
    payload = {
        "dataset_id": dataset_id,
        "name": "Invalid Benchmark Run",
        "benchmark_asset": "NON_EXISTENT_BENCHMARK:US",
        "assets": ["AAPL:US"],
        "weights": {"AAPL:US": 1.0},
    }

    resp = client.post("/api/v1/performance/analyze", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "errors" in detail
    assert any("NON_EXISTENT_BENCHMARK" in err for err in detail["errors"])
