"""
Integration and security tests for Black-Litterman Portfolio Optimization API.
Covers authentication, tenant isolation, relative and absolute views,
Bayesian prior/posterior dynamics, and chronological out-of-sample backtesting.
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
    """Registers a 30-bar historical price dataset for 3 assets (AAPL, MSFT, GOOG)."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    p_aapl = 150.0
    p_msft = 250.0
    p_goog = 100.0

    for day in range(1, 31):
        dt_str = f"2023-01-{day:02d}"
        ret_a = float(np.random.normal(0.003, 0.008))
        ret_m = float(np.random.normal(0.002, 0.007))
        ret_g = float(np.random.normal(0.002, 0.006))

        p_aapl *= 1.0 + ret_a
        p_msft *= 1.0 + ret_m
        p_goog *= 1.0 + ret_g

        lines.append(f"{dt_str},AAPL,US,USD,{p_aapl:.2f},{p_aapl*1.01:.2f},{p_aapl*0.99:.2f},{p_aapl:.2f},1000,{p_aapl:.2f}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_msft:.2f},{p_msft*1.01:.2f},{p_msft*0.99:.2f},{p_msft:.2f},1000,{p_msft:.2f}")
        lines.append(f"{dt_str},GOOG,US,USD,{p_goog:.2f},{p_goog*1.01:.2f},{p_goog*0.99:.2f},{p_goog:.2f},1000,{p_goog:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("bl_test_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


def test_unauthenticated_requests_rejected():
    """Verifies that Black-Litterman endpoints reject unauthenticated calls with HTTP 401."""
    # 1. Optimize
    resp1 = client.post(
        "/api/v1/black-litterman/optimize",
        json={"dataset_id": "none", "assets": ["A", "B"]},
    )
    assert resp1.status_code == 401

    # 2. Backtest
    resp2 = client.post(
        "/api/v1/black-litterman/backtest",
        json={"dataset_id": "none", "assets": ["A", "B"], "train_end_date": "2023-01-20"},
    )
    assert resp2.status_code == 401


def test_cross_tenant_dataset_access_rejected(registered_dataset_user_a, auth_headers_user_b):
    """Verifies User B cannot execute Black-Litterman optimization on User A's private dataset."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "objective": "max_sharpe",
    }
    resp = client.post(
        "/api/v1/black-litterman/optimize",
        json=payload,
        headers=auth_headers_user_b,
    )
    assert resp.status_code in (403, 404)


def test_successful_black_litterman_relative_view(registered_dataset_user_a, auth_headers_user_a):
    """Verifies successful Black-Litterman optimization with a relative view (AAPL > MSFT by 3%)."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "tau": 0.05,
        "risk_aversion": 2.5,
        "views": [
            {
                "view_type": "relative",
                "assets": ["AAPL", "MSFT"],
                "weights": [1.0, -1.0],
                "target_return": 0.03,
                "confidence": 0.70,
            }
        ],
        "objective": "max_sharpe",
        "constraints": {
            "default_min_weight": 0.05,
            "default_max_weight": 0.80,
        },
    }

    resp = client.post(
        "/api/v1/black-litterman/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_feasible"] is True
    assert len(data["assets"]) == 3
    assert any("AAPL" in k for k in data["optimal_weights"])
    assert any("MSFT" in k for k in data["optimal_weights"])
    assert any("GOOG" in k for k in data["optimal_weights"])

    # Weight sum = 1
    total_weight = sum(data["optimal_weights"].values())
    assert total_weight == pytest.approx(1.0, abs=1e-4)

    # Active tilt: relative view (AAPL > MSFT) should produce tilt(AAPL) > tilt(MSFT)
    aapl_key = [k for k in data["active_tilts"] if "AAPL" in k][0]
    msft_key = [k for k in data["active_tilts"] if "MSFT" in k][0]
    assert data["active_tilts"][aapl_key] > data["active_tilts"][msft_key]

    # Diagnostics check
    assert len(data["views_summary"]) == 1
    assert data["views_summary"][0]["confidence"] == 0.70
    assert data["diagnostics"]["weight_distance_d1"] > 0.0
    assert data["diagnostics"]["effective_assets_optimal"] > 1.0


def test_successful_black_litterman_absolute_view(registered_dataset_user_a, auth_headers_user_a):
    """Verifies successful Black-Litterman optimization with an absolute view."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "tau": 0.025,
        "risk_aversion": 3.0,
        "views": [
            {
                "view_type": "absolute",
                "assets": ["GOOG"],
                "weights": [1.0],
                "target_return": 0.12,
                "confidence": 0.85,
            }
        ],
        "objective": "mean_variance_utility",
        "constraints": {
            "default_min_weight": 0.0,
            "default_max_weight": 0.60,
        },
    }

    resp = client.post(
        "/api/v1/black-litterman/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_feasible"] is True
    assert sum(data["optimal_weights"].values()) == pytest.approx(1.0, abs=1e-4)
    # Bounds respected
    for w in data["optimal_weights"].values():
        assert w >= 0.0 - 1e-4
        assert w <= 0.60 + 1e-4


def test_black_litterman_zero_views_recovers_prior(registered_dataset_user_a, auth_headers_user_a):
    """Verifies that 0 views yields posterior returns equal to implied equilibrium returns."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "tau": 0.05,
        "risk_aversion": 2.5,
        "views": [],
        "objective": "mean_variance_utility",
    }

    resp = client.post(
        "/api/v1/black-litterman/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_feasible"] is True
    for asset in data["assets"]:
        assert data["posterior_returns"][asset] == pytest.approx(data["equilibrium_returns"][asset], abs=1e-6)
        assert data["active_tilts"][asset] == pytest.approx(0.0, abs=1e-2)


def test_black_litterman_out_of_sample_backtest(registered_dataset_user_a, auth_headers_user_a):
    """Verifies chronological out-of-sample backtest with walk-forward simulation."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "train_end_date": "2023-01-20",
        "tau": 0.05,
        "risk_aversion": 2.5,
        "views": [
            {
                "view_type": "relative",
                "assets": ["AAPL", "MSFT"],
                "weights": [1.0, -1.0],
                "target_return": 0.04,
                "confidence": 0.60,
            }
        ],
        "objective": "max_sharpe",
    }

    resp = client.post(
        "/api/v1/black-litterman/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["equity_curves"]) > 0
    assert "start" in data["train_period"]
    assert "start" in data["test_period"]
    assert "date" in data["equity_curves"][0]
    assert "black_litterman_portfolio_value" in data["equity_curves"][0]

    # Metrics present
    bl_metrics = data["black_litterman_kpis"]
    eq_metrics = data["equilibrium_kpis"]
    assert "sharpe_ratio" in bl_metrics
    assert "cumulative_return" in bl_metrics
    assert "max_drawdown" in bl_metrics
    assert "annualized_volatility" in bl_metrics
    assert "sharpe_ratio" in eq_metrics
