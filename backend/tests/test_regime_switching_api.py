"""
API integration and security tests for Stage 20:
Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting.
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.db.models import DatasetModel, UserModel
from app.db.session import get_db_session
from app.main import app

client = TestClient(app)

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"


def _generate_synthetic_csv() -> bytes:
    """Generates synthetic CSV data with 120 trading days for 2 assets."""
    lines = ["date,ticker,market,close,currency"]
    import numpy as np

    rng = np.random.default_rng(42)
    p1 = 100.0
    p2 = 50.0

    for i in range(120):
        # Month, day formatting
        month = (i // 25) + 1
        day = (i % 25) + 1
        dt = f"2024-{month:02d}-{day:02d}"

        r1 = rng.normal(0.0005, 0.015)
        r2 = rng.normal(0.0002, 0.020)
        p1 *= (1.0 + r1)
        p2 *= (1.0 + r2)

        lines.append(f"{dt},AAPL,US,{p1:.2f},USD")
        lines.append(f"{dt},MSFT,US,{p2:.2f},USD")

    return "\n".join(lines).encode("utf-8")


@pytest.fixture
def setup_users_and_datasets():
    """Sets up User A (with private dataset) and User B."""
    with get_db_session() as session:
        session.query(DatasetModel).delete()
        session.query(UserModel).filter(
            UserModel.id.in_([USER_A_ID, USER_B_ID])
        ).delete()

        user_a = UserModel(
            id=USER_A_ID,
            email="user_a_regime@domain.com",
            hashed_password="hash",
            full_name="User A",
            role="researcher",
            is_active=True,
        )
        user_b = UserModel(
            id=USER_B_ID,
            email="user_b_regime@domain.com",
            hashed_password="hash",
            full_name="User B",
            role="researcher",
            is_active=True,
        )
        session.add_all([user_a, user_b])
        session.commit()

    token_a = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user_a_regime@domain.com", "role": "researcher"},
    )
    token_b = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user_b_regime@domain.com", "role": "researcher"},
    )

    # Upload dataset for User A
    csv_bytes = _generate_synthetic_csv()
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("regime_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200, resp.text
    dataset_a_id = resp.json()["dataset_id"]

    return {
        "token_a": token_a,
        "token_b": token_b,
        "dataset_a_id": dataset_a_id,
    }


def test_regime_detect_unauthenticated_401():
    """Verifies unauthenticated calls to /api/v1/regime-switching/detect return HTTP 401."""
    resp = client.post(
        "/api/v1/regime-switching/detect",
        json={"dataset_id": "any-dataset-id", "num_states": 2},
    )
    assert resp.status_code == 401


def test_regime_backtest_unauthenticated_401():
    """Verifies unauthenticated calls to /api/v1/regime-switching/backtest return HTTP 401."""
    resp = client.post(
        "/api/v1/regime-switching/backtest",
        json={"dataset_id": "any-dataset-id"},
    )
    assert resp.status_code == 401


def test_regime_cross_tenant_forbidden_403_or_404(setup_users_and_datasets):
    """Verifies that User B cannot access User A's private dataset for regime detection or backtesting."""
    data = setup_users_and_datasets
    token_b = data["token_b"]
    dataset_a_id = data["dataset_a_id"]

    # 1. Detect
    resp_detect = client.post(
        "/api/v1/regime-switching/detect",
        json={"dataset_id": dataset_a_id, "num_states": 2},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_detect.status_code in (403, 404)

    # 2. Backtest
    resp_backtest = client.post(
        "/api/v1/regime-switching/backtest",
        json={"dataset_id": dataset_a_id, "lookback_window": 60},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_backtest.status_code in (403, 404)


def test_regime_invalid_inputs_boundary_422(setup_users_and_datasets):
    """Verifies that out-of-boundary parameters trigger HTTP 422 Unprocessable Content."""
    data = setup_users_and_datasets
    token_a = data["token_a"]
    dataset_a_id = data["dataset_a_id"]

    # num_states = 5 (allowed: 2 or 3)
    resp = client.post(
        "/api/v1/regime-switching/detect",
        json={"dataset_id": dataset_a_id, "num_states": 5},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422


def test_regime_detection_success(setup_users_and_datasets):
    """Verifies successful HMM regime detection for an authorized user."""
    data = setup_users_and_datasets
    token_a = data["token_a"]
    dataset_a_id = data["dataset_a_id"]

    resp = client.post(
        "/api/v1/regime-switching/detect",
        json={"dataset_id": dataset_a_id, "num_states": 2},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    res = resp.json()

    assert res["num_states"] == 2
    assert len(res["state_labels"]) == 2
    assert len(res["transition_matrix"]) == 2
    assert len(res["state_volatilities_annual"]) == 2
    # Volatility ordering: state 0 vol < state 1 vol
    assert res["state_volatilities_annual"][0] <= res["state_volatilities_annual"][1]
    assert len(res["timeline"]) > 50


def test_regime_backtest_success(setup_users_and_datasets):
    """Verifies successful walk-forward backtesting with volatility targeting for authorized user."""
    data = setup_users_and_datasets
    token_a = data["token_a"]
    dataset_a_id = data["dataset_a_id"]

    resp = client.post(
        "/api/v1/regime-switching/backtest",
        json={
            "dataset_id": dataset_a_id,
            "lookback_window": 60,
            "target_volatility": 0.12,
            "max_leverage": 1.5,
            "rebalance_frequency": "weekly",
            "transaction_cost_bps": 10.0,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    res = resp.json()

    assert "summary" in res
    assert res["summary"]["initial_equity"] == 100_000.0
    assert res["summary"]["final_equity"] > 0
    assert len(res["equity_curve"]) > 10
    assert len(res["rebalance_events"]) > 0
