"""
Integration and security tests for Multi-Asset Class Allocation & FX Hedging API.
Covers authentication, tenant isolation, hierarchical optimization, and walk-forward backtesting.
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
def registered_multi_asset_dataset(auth_headers_user_a):
    """Registers a 70-bar historical price dataset with Equities and Bonds."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    tickers = ["SPY", "QQQ", "BND", "GLD"]
    prices = {"SPY": 400.0, "QQQ": 300.0, "BND": 75.0, "GLD": 180.0}
    dates = pd.date_range("2023-01-02", periods=70, freq="B")

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        for t in tickers:
            ret = float(np.random.normal(0.0005, 0.012))
            prices[t] *= (1.0 + ret)
            p = prices[t]
            lines.append(f"{dt_str},{t},US,USD,{p:.2f},{p*1.01:.2f},{p*0.99:.2f},{p:.2f},1000,{p:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("multi_asset_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


def test_unauthenticated_multi_asset_requests_rejected(registered_multi_asset_dataset):
    """Verifies that unauthenticated requests to /api/v1/multi-asset/* return HTTP 401."""
    resp_opt = client.post(
        "/api/v1/multi-asset/optimize",
        json={"dataset_id": registered_multi_asset_dataset},
    )
    assert resp_opt.status_code == 401

    resp_bt = client.post(
        "/api/v1/multi-asset/backtest",
        json={"dataset_id": registered_multi_asset_dataset},
    )
    assert resp_bt.status_code == 401


def test_cross_tenant_multi_asset_access_rejected(registered_multi_asset_dataset, auth_headers_user_b):
    """Verifies that User B cannot access User A's private dataset."""
    resp = client.post(
        "/api/v1/multi-asset/optimize",
        json={"dataset_id": registered_multi_asset_dataset},
        headers=auth_headers_user_b,
    )
    assert resp.status_code in [403, 404]


def test_multi_asset_optimization_valid(registered_multi_asset_dataset, auth_headers_user_a):
    """Verifies valid multi-asset optimization under asset class limits."""
    payload = {
        "dataset_id": registered_multi_asset_dataset,
        "base_currency": "USD",
        "assets_metadata": [
            {"ticker": "SPY", "asset_class": "Equity", "currency": "USD"},
            {"ticker": "QQQ", "asset_class": "Equity", "currency": "USD"},
            {"ticker": "BND", "asset_class": "Fixed Income", "currency": "USD"},
            {"ticker": "GLD", "asset_class": "Commodity", "currency": "USD"},
        ],
        "asset_class_limits": {
            "Equity": {"min_weight": 0.30, "max_weight": 0.60},
            "Fixed Income": {"min_weight": 0.15, "max_weight": 0.40},
            "Commodity": {"min_weight": 0.05, "max_weight": 0.20},
        },
        "min_cash_weight": 0.05,
        "max_cash_weight": 0.15,
        "objective": "max_sharpe",
    }
    resp = client.post(
        "/api/v1/multi-asset/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["is_feasible"]
    assert "risky_weights" in data
    assert 0.05 <= data["cash_weight"] <= 0.15

    # Budget invariant: sum(risky_weights) + cash_weight == 1.0
    tot_weight = sum(data["risky_weights"].values()) + data["cash_weight"]
    np.testing.assert_allclose(tot_weight, 1.0, atol=1e-4)

    # Asset class allocations
    allocs = data["asset_class_allocations"]
    assert "Equity" in allocs
    assert "Fixed Income" in allocs
    assert "Commodity" in allocs
    assert "Cash" in allocs
    assert allocs["Equity"] >= 0.29
    assert allocs["Fixed Income"] >= 0.14


def test_multi_asset_backtest_valid(registered_multi_asset_dataset, auth_headers_user_a):
    """Verifies walk-forward multi-asset backtest execution."""
    payload = {
        "dataset_id": registered_multi_asset_dataset,
        "base_currency": "USD",
        "assets_metadata": [
            {"ticker": "SPY", "asset_class": "Equity", "currency": "USD"},
            {"ticker": "QQQ", "asset_class": "Equity", "currency": "USD"},
            {"ticker": "BND", "asset_class": "Fixed Income", "currency": "USD"},
            {"ticker": "GLD", "asset_class": "Commodity", "currency": "USD"},
        ],
        "asset_class_limits": {
            "Equity": {"min_weight": 0.20, "max_weight": 0.60},
            "Fixed Income": {"min_weight": 0.10, "max_weight": 0.40},
        },
        "min_cash_weight": 0.05,
        "max_cash_weight": 0.20,
        "rebalance_frequency": "monthly",
        "estimation_window": 30,
        "objective": "min_variance",
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }
    resp = client.post(
        "/api/v1/multi-asset/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "summary" in data
    assert "benchmark" in data
    assert "equity_curve" in data
    assert "rebalance_history" in data
    assert len(data["equity_curve"]) > 0
    assert data["summary"]["total_rebalances"] >= 1


def test_multi_asset_insufficient_history_422(registered_multi_asset_dataset, auth_headers_user_a):
    """Verifies that an estimation window exceeding the dataset length returns 422."""
    payload = {
        "dataset_id": registered_multi_asset_dataset,
        "estimation_window": 100,  # dataset only has 70 rows
    }
    resp = client.post(
        "/api/v1/multi-asset/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 422
