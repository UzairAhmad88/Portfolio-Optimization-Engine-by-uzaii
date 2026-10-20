"""
Integration and security tests for Risk Parity and Hierarchical Risk Parity (HRP) API.
Covers authentication, tenant isolation, ERC and HRP optimization, and chronological backtesting.
"""

from __future__ import annotations

import io
import numpy as np
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
    token = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user.a@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b():
    token = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user.b@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_users():
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
def registered_dataset_user_a(auth_headers_user_a):
    """Registers a 60-bar historical price dataset for 3 assets (AAPL, MSFT, GOOG)."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    p_aapl = 150.0
    p_msft = 250.0
    p_goog = 100.0

    import pandas as pd
    dates = pd.date_range("2023-01-02", periods=60, freq="B")

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        ret_a = float(np.random.normal(0.001, 0.015))
        ret_m = float(np.random.normal(0.001, 0.010))
        ret_g = float(np.random.normal(0.001, 0.020))

        p_aapl *= 1.0 + ret_a
        p_msft *= 1.0 + ret_m
        p_goog *= 1.0 + ret_g

        lines.append(f"{dt_str},AAPL,US,USD,{p_aapl:.2f},{p_aapl*1.01:.2f},{p_aapl*0.99:.2f},{p_aapl:.2f},1000,{p_aapl:.2f}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_msft:.2f},{p_msft*1.01:.2f},{p_msft*0.99:.2f},{p_msft:.2f},1000,{p_msft:.2f}")
        lines.append(f"{dt_str},GOOG,US,USD,{p_goog:.2f},{p_goog*1.01:.2f},{p_goog*0.99:.2f},{p_goog:.2f},1000,{p_goog:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("risk_parity_test_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


def test_unauthenticated_requests_rejected(registered_dataset_user_a):
    """Verify that unauthenticated requests to /api/v1/risk-parity/* return 401."""
    resp_opt = client.post(
        "/api/v1/risk-parity/optimize",
        json={"dataset_id": registered_dataset_user_a, "method": "erc"},
    )
    assert resp_opt.status_code == 401

    resp_bt = client.post(
        "/api/v1/risk-parity/backtest",
        json={
            "dataset_id": registered_dataset_user_a,
            "method": "erc",
            "split_date": "2023-01-25",
        },
    )
    assert resp_bt.status_code == 401


def test_cross_tenant_dataset_access_rejected(registered_dataset_user_a, auth_headers_user_b):
    """Verify that User B cannot optimize or backtest on User A's private dataset."""
    resp = client.post(
        "/api/v1/risk-parity/optimize",
        json={"dataset_id": registered_dataset_user_a, "method": "erc"},
        headers=auth_headers_user_b,
    )
    assert resp.status_code in (403, 404)

    resp_bt = client.post(
        "/api/v1/risk-parity/backtest",
        json={
            "dataset_id": registered_dataset_user_a,
            "method": "erc",
            "split_date": "2023-01-25",
        },
        headers=auth_headers_user_b,
    )
    assert resp_bt.status_code in (403, 404)


def test_successful_erc_optimization_api(registered_dataset_user_a, auth_headers_user_a):
    """Verify Equal Risk Contribution optimization through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "method": "erc",
    }
    resp = client.post(
        "/api/v1/risk-parity/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["method"] == "erc"
    assert data["is_feasible"] is True
    assert data["solver_status"] == "optimal"

    weights = data["weights"]
    prc = data["percentage_risk_contributions"]

    # All 3 assets should sum to 1.0
    assert np.isclose(sum(weights.values()), 1.0, atol=1e-5)
    # Risk contributions should be approximately equal (~33.3% each)
    for v in prc.values():
        assert np.isclose(v, 1.0 / 3.0, atol=1e-3)

    assert data["risk_gini_coefficient"] <= 0.05
    assert data["effective_number_of_bets"] >= 2.9
    assert data["diversification_ratio"] >= 1.0


def test_successful_hrp_optimization_api(registered_dataset_user_a, auth_headers_user_a):
    """Verify Hierarchical Risk Parity (HRP) optimization through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "method": "hrp",
        "linkage_method": "single",
    }
    resp = client.post(
        "/api/v1/risk-parity/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["method"] == "hrp"
    assert data["is_feasible"] is True
    assert data["reordered_indices"] is not None
    assert len(data["reordered_indices"]) == 3
    assert np.isclose(sum(data["weights"].values()), 1.0, atol=1e-5)


def test_successful_risk_parity_backtest_api(registered_dataset_user_a, auth_headers_user_a):
    """Verify out-of-sample chronological backtest comparing ERC vs Equal Weight."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "method": "erc",
        "split_date": "2023-02-15",
        "rebalance_frequency": "monthly",
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }
    resp = client.post(
        "/api/v1/risk-parity/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == registered_dataset_user_a
    assert data["method"] == "erc"
    assert "strategy_metrics" in data
    assert "equal_weight_benchmark_metrics" in data
    assert len(data["equity_curve"]) > 0
    assert len(data["drawdown_curve"]) > 0

    # Ensure equity points have proper keys
    pt = data["equity_curve"][0]
    assert "date" in pt
    assert "strategy" in pt
    assert "benchmark" in pt


def test_invalid_inputs_api(registered_dataset_user_a, auth_headers_user_a):
    """Verify validation and error handling for bad inputs."""
    # Bad split date with too few out-of-sample observations
    resp = client.post(
        "/api/v1/risk-parity/backtest",
        json={
            "dataset_id": registered_dataset_user_a,
            "method": "erc",
            "split_date": "2023-03-20",  # near last day => < 10 out-of-sample bars
        },
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 422
