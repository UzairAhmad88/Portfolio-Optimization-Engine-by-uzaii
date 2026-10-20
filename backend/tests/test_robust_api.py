"""
Integration and security tests for Robust Portfolio Optimization API.
Covers authentication, tenant isolation, baseline vs robust optimization,
constraint sensitivity sweeps, and out-of-sample backtesting validation.
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
    """Registers a 25-bar historical price dataset for 3 assets (AAPL, MSFT, GOOG)."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    # Generate synthetic price series with 25 dates
    p_aapl = 150.0
    p_msft = 250.0
    p_goog = 100.0

    for day in range(1, 26):
        dt_str = f"2023-01-{day:02d}"
        ret_a = float(np.random.normal(0.004, 0.005))
        ret_m = float(np.random.normal(0.003, 0.004))
        ret_g = float(np.random.normal(0.002, 0.003))

        p_aapl *= 1.0 + ret_a
        p_msft *= 1.0 + ret_m
        p_goog *= 1.0 + ret_g

        lines.append(f"{dt_str},AAPL,US,USD,{p_aapl:.2f},{p_aapl*1.01:.2f},{p_aapl*0.99:.2f},{p_aapl:.2f},1000,{p_aapl:.2f}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_msft:.2f},{p_msft*1.01:.2f},{p_msft*0.99:.2f},{p_msft:.2f},1000,{p_msft:.2f}")
        lines.append(f"{dt_str},GOOG,US,USD,{p_goog:.2f},{p_goog*1.01:.2f},{p_goog*0.99:.2f},{p_goog:.2f},1000,{p_goog:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("robust_test_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


def test_unauthenticated_requests_rejected():
    """Verifies that all robust optimization endpoints reject unauthenticated calls with HTTP 401."""
    # 1. Optimize
    resp1 = client.post("/api/v1/robust-optimization/optimize", json={"dataset_id": "none", "assets": ["A", "B"]})
    assert resp1.status_code == 401

    # 2. Sensitivity
    resp2 = client.post("/api/v1/robust-optimization/sensitivity", json={"dataset_id": "none", "assets": ["A", "B"]})
    assert resp2.status_code == 401

    # 3. Backtest
    resp3 = client.post("/api/v1/robust-optimization/backtest", json={"dataset_id": "none", "assets": ["A", "B"], "train_end_date": "2023-01-15"})
    assert resp3.status_code == 401


def test_cross_tenant_dataset_access_rejected(registered_dataset_user_a, auth_headers_user_b):
    """Verifies User B cannot execute robust optimization on User A's private dataset."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "objective": "max_sharpe",
    }
    resp = client.post(
        "/api/v1/robust-optimization/optimize",
        json=payload,
        headers=auth_headers_user_b,
    )
    assert resp.status_code in (403, 404)


def test_successful_robust_optimization(registered_dataset_user_a, auth_headers_user_a):
    """Verifies successful baseline vs robust optimization with Box uncertainty and Diagonal shrinkage."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "objective": "max_sharpe",
        "uncertainty": {
            "model": "box",
            "confidence_level": 1.5,
        },
        "shrinkage": {
            "target": "diagonal",
            "intensity": 0.25,
        },
        "constraints": {
            "default_min_weight": 0.05,
            "default_max_weight": 0.70,
        },
        "risk_free_rate": 0.02,
    }

    resp = client.post(
        "/api/v1/robust-optimization/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["objective"] == "max_sharpe"
    assert data["is_feasible"] is True
    assert len(data["weights"]) == 3

    # Check weights sum to 1.0 within tolerance
    rob_weights = data["robust_weights"]
    assert sum(rob_weights.values()) == pytest.approx(1.0, abs=1e-4)

    # Check constraints respected
    for w in rob_weights.values():
        assert w >= 0.05 - 1e-4
        assert w <= 0.70 + 1e-4

    # Check diagnostics
    diag = data["diagnostics"]
    assert diag["uncertainty_applied"] is True
    assert diag["shrinkage_applied"] is True
    assert diag["weight_distance_d1"] >= 0.0
    assert diag["robust_hhi"] > 0.0
    assert diag["effective_assets_robust"] > 1.0


def test_robust_minimum_variance(registered_dataset_user_a, auth_headers_user_a):
    """Verifies robust minimum variance with constant correlation shrinkage."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "objective": "min_variance",
        "uncertainty": {
            "model": "none",
        },
        "shrinkage": {
            "target": "constant_correlation",
            "intensity": 0.30,
        },
        "constraints": {
            "default_min_weight": 0.0,
            "default_max_weight": 1.0,
        },
    }

    resp = client.post(
        "/api/v1/robust-optimization/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_feasible"] is True
    assert data["solver_status"] in ("converged", "feasible_baseline")


def test_sensitivity_sweep_api(registered_dataset_user_a, auth_headers_user_a):
    """Verifies parameter sensitivity sweep endpoint."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "parameter_to_sweep": "max_weight",
        "grid_min": 0.25,
        "grid_max": 0.90,
        "num_steps": 6,
        "objective": "max_sharpe",
    }

    resp = client.post(
        "/api/v1/robust-optimization/sensitivity",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["parameter_name"] == "max_weight"
    assert len(data["points"]) == 6
    assert data["total_evaluations"] == 6
    # 0.25 * 3 = 0.75 < 1.0 -> first point is infeasible
    assert data["infeasible_evaluations"] >= 1


def test_out_of_sample_backtest_api(registered_dataset_user_a, auth_headers_user_a):
    """Verifies chronological out-of-sample backtest comparing baseline vs robust portfolio."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "train_end_date": "2023-01-16",
        "objective": "max_sharpe",
        "uncertainty": {
            "model": "box",
            "confidence_level": 1.0,
        },
        "shrinkage": {
            "target": "diagonal",
            "intensity": 0.20,
        },
        "rebalance_frequency": "buy_and_hold",
        "cost_bps": 10.0,
        "slippage_bps": 5.0,
    }

    resp = client.post(
        "/api/v1/robust-optimization/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "baseline_kpis" in data
    assert "robust_kpis" in data
    assert "out_of_sample_comparison" in data
    assert len(data["equity_curves"]) > 0

    assert "cumulative_return" in data["baseline_kpis"]
    assert "cumulative_return" in data["robust_kpis"]
    assert "delta_cumulative_return" in data["out_of_sample_comparison"]
