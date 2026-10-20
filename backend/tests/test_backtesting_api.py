"""
Integration and security test suite for the backtesting API endpoints.

Validates:
1. End-to-end backtest execution via POST /api/v1/backtests.
2. Summary metrics, equity curve, and rebalance event contracts.
3. Dataset ownership enforcement (cross-user dataset rejected with 403/404).
4. Cross-user backtest result isolation (User B cannot read/delete User A's backtests).
5. User-scoped listing (GET /api/v1/backtests).
6. Input validation (negative capital, negative costs, inverted dates).
7. Unauthenticated request rejection (401 Unauthorized).
8. Persistent backtest deletion lifecycle.
"""

from __future__ import annotations

from io import BytesIO
import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.auth.service import register_user
from app.db.models import UserModel
from app.db.session import get_db_session
from app.main import app

SAMPLE_CSV = b"""date,ticker,market,close,adjusted_close,currency
2025-01-02,AAPL,US,150.0,150.0,USD
2025-01-02,MSFT,US,300.0,300.0,USD
2025-01-03,AAPL,US,153.0,153.0,USD
2025-01-03,MSFT,US,306.0,306.0,USD
2025-01-06,AAPL,US,151.0,151.0,USD
2025-01-06,MSFT,US,303.0,303.0,USD
2025-01-07,AAPL,US,155.0,155.0,USD
2025-01-07,MSFT,US,310.0,310.0,USD
2025-02-03,AAPL,US,158.0,158.0,USD
2025-02-03,MSFT,US,315.0,315.0,USD
"""


@pytest.fixture
def test_client():
    client = TestClient(app)
    client.cookies.clear()
    return client


@pytest.fixture
def auth_users():
    from uuid import uuid4
    from app.auth.security import hash_password

    user_a_id = str(uuid4())
    user_b_id = str(uuid4())

    with get_db_session() as session:
        user_a = UserModel(
            id=user_a_id,
            email=f"bt_user_a_{user_a_id[:8]}@example.com",
            hashed_password=hash_password("Password123!"),
            full_name="Backtest User A",
            role="researcher",
            is_active=True,
        )
        user_b = UserModel(
            id=user_b_id,
            email=f"bt_user_b_{user_b_id[:8]}@example.com",
            hashed_password=hash_password("Password123!"),
            full_name="Backtest User B",
            role="researcher",
            is_active=True,
        )
        session.add(user_a)
        session.add(user_b)
        session.commit()

        token_a = create_access_token(subject=user_a.id, claims={"email": user_a.email, "role": user_a.role})
        token_b = create_access_token(subject=user_b.id, claims={"email": user_b.email, "role": user_b.role})

    yield {
        "user_a": user_a,
        "token_a": token_a,
        "user_b": user_b,
        "token_b": token_b,
    }

    with get_db_session() as session:
        u_a = session.get(UserModel, user_a_id)
        if u_a:
            session.delete(u_a)
        u_b = session.get(UserModel, user_b_id)
        if u_b:
            session.delete(u_b)
        session.commit()



def _upload_dataset(client: TestClient, token: str) -> str:
    """Helper to upload a test dataset for a user."""
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test_market_data.csv", BytesIO(SAMPLE_CSV), "text/csv")}
    resp = client.post("/api/v1/market-data/uploads", files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


def test_unauthenticated_backtest_rejected(test_client):
    """Verifies that unauthenticated backtest requests are rejected with 401."""
    test_client.cookies.clear()
    resp = test_client.post(
        "/api/v1/backtests",
        json={
            "dataset_id": "any-dataset",
            "name": "Test",
            "assets": ["AAPL"],
        },
    )
    assert resp.status_code == 401


def test_execute_backtest_success(test_client, auth_users):
    """Verifies successful backtest execution, metrics calculation, and equity curve."""
    token = auth_users["token_a"]
    dataset_id = _upload_dataset(test_client, token)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "dataset_id": dataset_id,
        "name": "Tech 60/40 Monthly",
        "strategy_type": "target_weights",
        "assets": ["AAPL", "MSFT"],
        "weights": {"AAPL": 0.6, "MSFT": 0.4},
        "rebalance_frequency": "monthly",
        "initial_capital": 100_000.0,
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }

    resp = test_client.post("/api/v1/backtests", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["name"] == "Tech 60/40 Monthly"
    assert data["status"] == "completed"
    assert data["dataset_id"] == dataset_id
    assert "metrics" in data
    assert "equity_curve" in data
    assert "rebalance_events" in data

    metrics = data["metrics"]
    assert metrics["initial_value"] == 100_000.0
    assert metrics["final_value_net"] > 0.0
    assert metrics["observation_count"] == 5
    assert metrics["total_friction_costs"] > 0.0
    assert metrics["number_of_rebalances"] >= 1

    # Inception rebalance event must exist
    reb_events = data["rebalance_events"]
    assert len(reb_events) >= 1
    assert reb_events[0]["reason"] == "Initial Allocation"


def test_backtest_tenant_isolation_dataset_protection(test_client, auth_users):
    """
    Verifies that User B cannot execute a backtest against User A's private dataset.
    """
    token_a = auth_users["token_a"]
    token_b = auth_users["token_b"]

    dataset_a_id = _upload_dataset(test_client, token_a)

    # User B attempts to backtest on User A's dataset
    headers_b = {"Authorization": f"Bearer {token_b}"}
    payload = {
        "dataset_id": dataset_a_id,
        "name": "Unauthorized Backtest",
        "strategy_type": "equal_weight",
        "assets": ["AAPL", "MSFT"],
    }

    resp = test_client.post("/api/v1/backtests", json=payload, headers=headers_b)
    assert resp.status_code in (403, 404)


def test_backtest_cross_user_result_isolation(test_client, auth_users):
    """
    Verifies that User B cannot retrieve or delete User A's backtest run.
    """
    token_a = auth_users["token_a"]
    token_b = auth_users["token_b"]

    dataset_id = _upload_dataset(test_client, token_a)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    payload = {
        "dataset_id": dataset_id,
        "name": "User A Run",
        "strategy_type": "equal_weight",
        "assets": ["AAPL", "MSFT"],
    }
    create_resp = test_client.post("/api/v1/backtests", json=payload, headers=headers_a)
    assert create_resp.status_code == 201
    backtest_id = create_resp.json()["id"]

    # User A can retrieve it
    resp_a = test_client.get(f"/api/v1/backtests/{backtest_id}", headers=headers_a)
    assert resp_a.status_code == 200

    # User B cannot retrieve it
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = test_client.get(f"/api/v1/backtests/{backtest_id}", headers=headers_b)
    assert resp_b.status_code == 403

    # User B cannot delete it
    del_b = test_client.delete(f"/api/v1/backtests/{backtest_id}", headers=headers_b)
    assert del_b.status_code == 403


def test_list_user_backtests_scoping(test_client, auth_users):
    """
    Verifies that GET /api/v1/backtests returns only runs belonging to the caller.
    """
    token_a = auth_users["token_a"]
    token_b = auth_users["token_b"]

    dataset_id = _upload_dataset(test_client, token_a)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    payload = {
        "dataset_id": dataset_id,
        "name": "Scoped Run A",
        "strategy_type": "equal_weight",
        "assets": ["AAPL", "MSFT"],
    }
    test_client.post("/api/v1/backtests", json=payload, headers=headers_a)

    # User A lists runs
    resp_a = test_client.get("/api/v1/backtests", headers=headers_a)
    assert resp_a.status_code == 200
    runs_a = resp_a.json()
    assert any(r["name"] == "Scoped Run A" for r in runs_a)

    # User B lists runs - should not see Scoped Run A
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = test_client.get("/api/v1/backtests", headers=headers_b)
    assert resp_b.status_code == 200
    runs_b = resp_b.json()
    assert not any(r["name"] == "Scoped Run A" for r in runs_b)


def test_backtest_input_validation(test_client, auth_users):
    """Verifies that invalid request bounds produce 422 Unprocessable Entity."""
    token = auth_users["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # Negative capital
    resp = test_client.post(
        "/api/v1/backtests",
        json={"dataset_id": "test", "assets": ["AAPL"], "initial_capital": -1000.0},
        headers=headers,
    )
    assert resp.status_code == 422

    # Negative transaction cost bps
    resp = test_client.post(
        "/api/v1/backtests",
        json={"dataset_id": "test", "assets": ["AAPL"], "transaction_cost_bps": -5.0},
        headers=headers,
    )
    assert resp.status_code == 422

    # Inverted dates
    resp = test_client.post(
        "/api/v1/backtests",
        json={
            "dataset_id": "test",
            "assets": ["AAPL"],
            "start_date": "2025-05-01",
            "end_date": "2025-01-01",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_delete_backtest_lifecycle(test_client, auth_users):
    """Verifies complete deletion lifecycle for a persistent backtest run."""
    token = auth_users["token_a"]
    dataset_id = _upload_dataset(test_client, token)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "dataset_id": dataset_id,
        "name": "To Be Deleted",
        "strategy_type": "equal_weight",
        "assets": ["AAPL", "MSFT"],
    }
    create_resp = test_client.post("/api/v1/backtests", json=payload, headers=headers)
    backtest_id = create_resp.json()["id"]

    # Delete
    del_resp = test_client.delete(f"/api/v1/backtests/{backtest_id}", headers=headers)
    assert del_resp.status_code == 200

    # Retrieve again -> 404
    get_resp = test_client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)
    assert get_resp.status_code == 404
