"""
Integration and security tests for Optimal Execution & Market Impact API (Stage 19).
Covers authentication, tenant isolation, parameter validation, and rebalance impact analysis.
"""

from __future__ import annotations

import io
import numpy as np
import pandas as pd
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
def registered_execution_dataset(auth_headers_user_a):
    """Registers a historical dataset for rebalance impact testing."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    tickers = ["AAPL", "MSFT", "AMZN"]
    prices = {"AAPL": 150.0, "MSFT": 300.0, "AMZN": 120.0}
    dates = pd.date_range("2023-01-02", periods=40, freq="B")

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        for t in tickers:
            ret = float(np.random.normal(0.0005, 0.015))
            prices[t] *= (1.0 + ret)
            p = prices[t]
            lines.append(f"{dt_str},{t},US,USD,{p:.2f},{p*1.01:.2f},{p*0.99:.2f},{p:.2f},500000,{p:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("execution_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


def test_unauthenticated_execution_endpoints_return_401(registered_execution_dataset):
    """Verifies that unauthenticated requests to /api/v1/execution/* return HTTP 401."""
    resp_opt = client.post(
        "/api/v1/execution/optimal-schedule",
        json={
            "order_size": 10000.0,
            "asset_price": 50.0,
            "daily_volume": 1000000.0,
            "daily_volatility": 1.0,
        },
    )
    assert resp_opt.status_code == 401

    resp_reb = client.post(
        "/api/v1/execution/rebalance-impact",
        json={
            "dataset_id": registered_execution_dataset,
            "target_weights": {"AAPL": 0.5, "MSFT": 0.5},
        },
    )
    assert resp_reb.status_code == 401


def test_optimal_schedule_authenticated_success(auth_headers_user_a):
    """Verifies valid optimal schedule execution with Almgren-Chriss, TWAP, and VWAP."""
    payload = {
        "order_size": 200_000.0,
        "asset_price": 75.0,
        "daily_volume": 3_000_000.0,
        "daily_volatility": 1.8,
        "bid_ask_spread": 0.05,
        "horizon_periods": 6,
        "trading_hours": 6.5,
        "risk_aversion": 2.5e-6,
    }
    resp = client.post(
        "/api/v1/execution/optimal-schedule",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert len(data["schedule"]) == 6
    summary = data["summary"]
    assert summary["urgency_parameter"] > 0
    assert summary["expected_cost"] > 0
    assert summary["timing_risk_variance"] > 0
    assert summary["twap_expected_cost"] > 0
    assert "cost_savings_vs_twap" in summary


def test_optimal_schedule_invalid_inputs_422(auth_headers_user_a):
    """Verifies that invalid boundaries return HTTP 422."""
    resp = client.post(
        "/api/v1/execution/optimal-schedule",
        json={
            "order_size": -50.0,  # Invalid
            "asset_price": 50.0,
            "daily_volume": 1_000_000.0,
            "daily_volatility": 1.0,
        },
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 422


def test_cross_tenant_rebalance_impact_access_forbidden(registered_execution_dataset, auth_headers_user_b):
    """Verifies that User B cannot execute rebalance impact analysis on User A's private dataset."""
    resp = client.post(
        "/api/v1/execution/rebalance-impact",
        json={
            "dataset_id": registered_execution_dataset,
            "target_weights": {"AAPL": 0.5, "MSFT": 0.5},
            "portfolio_equity": 5_000_000.0,
        },
        headers=auth_headers_user_b,
    )
    assert resp.status_code in (403, 404)


def test_rebalance_impact_success(registered_execution_dataset, auth_headers_user_a):
    """Verifies rebalance impact analysis under Square-Root Law."""
    payload = {
        "dataset_id": registered_execution_dataset,
        "target_weights": {"AAPL": 0.60, "MSFT": 0.40, "AMZN": 0.0},
        "current_weights": {"AAPL": 0.20, "MSFT": 0.30, "AMZN": 0.50},
        "portfolio_equity": 10_000_000.0,
        "execution_horizon_days": 1.0,
        "impact_model": "square_root",
    }
    resp = client.post(
        "/api/v1/execution/rebalance-impact",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    summary = data["summary"]
    assert summary["total_traded_notional"] > 0
    assert summary["total_impact_cost"] > 0
    assert summary["effective_cost_bps"] > 0
    assert len(data["asset_impacts"]) > 0

    # Ensure assets are sorted descending by traded notional
    notionals = [a["traded_notional"] for a in data["asset_impacts"]]
    assert notionals == sorted(notionals, reverse=True)
