"""
Integration and security tests for Factor Investing & Systematic Risk Decomposition API.
Covers authentication, tenant isolation, factor attribution (CAPM/FF3/Carhart4/PCA),
and factor-constrained portfolio optimization.
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
def registered_dataset_user_a(auth_headers_user_a):
    """Registers a 60-bar historical price dataset for 4 assets (AAPL, MSFT, GOOG, AMZN)."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    np.random.seed(42)

    tickers = ["AAPL", "MSFT", "GOOG", "AMZN"]
    prices = {t: 100.0 + i * 50.0 for i, t in enumerate(tickers)}
    dates = pd.date_range("2023-01-02", periods=60, freq="B")

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        for t in tickers:
            ret = float(np.random.normal(0.0005, 0.015))
            prices[t] *= (1.0 + ret)
            p = prices[t]
            lines.append(f"{dt_str},{t},US,USD,{p:.2f},{p*1.01:.2f},{p*0.99:.2f},{p:.2f},1000,{p:.2f}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("factor_test_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


def test_unauthenticated_factor_requests_rejected(registered_dataset_user_a):
    """Verify that unauthenticated requests to /api/v1/factor-investing/* return 401."""
    resp_attr = client.post(
        "/api/v1/factor-investing/attribute",
        json={"dataset_id": registered_dataset_user_a, "factor_model": "capm"},
    )
    assert resp_attr.status_code == 401

    resp_opt = client.post(
        "/api/v1/factor-investing/optimize",
        json={"dataset_id": registered_dataset_user_a, "factor_model": "capm"},
    )
    assert resp_opt.status_code == 401


def test_cross_tenant_dataset_factor_access_rejected(registered_dataset_user_a, auth_headers_user_b):
    """Verify that User B cannot access User A's private dataset for factor analysis."""
    resp_attr = client.post(
        "/api/v1/factor-investing/attribute",
        json={"dataset_id": registered_dataset_user_a, "factor_model": "fama_french_3"},
        headers=auth_headers_user_b,
    )
    assert resp_attr.status_code in (403, 404)

    resp_opt = client.post(
        "/api/v1/factor-investing/optimize",
        json={"dataset_id": registered_dataset_user_a, "factor_model": "fama_french_3"},
        headers=auth_headers_user_b,
    )
    assert resp_opt.status_code in (403, 404)


def test_successful_factor_attribution_capm(registered_dataset_user_a, auth_headers_user_a):
    """Verify CAPM factor attribution through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "capm",
        "custom_weights": {"AAPL": 0.25, "MSFT": 0.25, "GOOG": 0.25, "AMZN": 0.25},
    }
    resp = client.post(
        "/api/v1/factor-investing/attribute",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["factor_model"] == "capm"
    assert data["factors"] == ["MKT"]
    assert len(data["asset_loadings"]) == 4

    decomp = data["risk_decomposition"]
    assert decomp["portfolio_volatility_pct"] > 0
    # Systematic + Specific variance pct should equal ~100
    total_pct = decomp["systematic_variance_pct"] + decomp["specific_variance_pct"]
    assert np.isclose(total_pct, 100.0, atol=0.5)

    # Check that individual asset loadings have MKT
    for asset, report in data["asset_loadings"].items():
        assert "MKT" in report["betas"]
        assert "r_squared" in report
        assert 0.0 <= report["r_squared"] <= 1.0


def test_successful_factor_attribution_carhart4(registered_dataset_user_a, auth_headers_user_a):
    """Verify Carhart 4-factor attribution through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "carhart_4",
    }
    resp = client.post(
        "/api/v1/factor-investing/attribute",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["factor_model"] == "carhart_4"
    assert data["factors"] == ["MKT", "SMB", "HML", "MOM"]
    assert "MKT" in data["portfolio_betas"]
    assert "SMB" in data["portfolio_betas"]
    assert "HML" in data["portfolio_betas"]
    assert "MOM" in data["portfolio_betas"]


def test_successful_factor_attribution_pca(registered_dataset_user_a, auth_headers_user_a):
    """Verify PCA statistical factor attribution through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "pca",
    }
    resp = client.post(
        "/api/v1/factor-investing/attribute",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["factor_model"] == "pca"
    assert len(data["factors"]) == 3  # min(3, n_assets-1)


def test_factor_constrained_optimization(registered_dataset_user_a, auth_headers_user_a):
    """Verify portfolio optimization with factor exposure tilt constraints."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "fama_french_3",
        "objective": "min_variance",
        "target_factor_tilts": {
            "MKT": {"min_beta": 0.8, "max_beta": 1.2},
            "SMB": {"min_beta": -0.5, "max_beta": 0.5},
        },
    }
    resp = client.post(
        "/api/v1/factor-investing/optimize",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["is_success"] is True
    assert np.isclose(sum(data["weights"].values()), 1.0, atol=1e-3)

    # Verify portfolio beta respects constraint
    mkt_beta = data["realized_factor_betas"]["MKT"]
    assert 0.79 <= mkt_beta <= 1.21

    # Check diagnostics
    assert data["diagnostics"]["converged"] is True
    assert "risk_decomposition" in data


def test_factor_api_nonexistent_dataset(auth_headers_user_a):
    """Verify 404 on non-existent dataset ID."""
    resp = client.post(
        "/api/v1/factor-investing/attribute",
        json={"dataset_id": "00000000-0000-0000-0000-000000009999", "factor_model": "capm"},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404


def test_unauthenticated_factor_backtest_rejected(registered_dataset_user_a):
    """Verify that unauthenticated requests to /api/v1/factor-investing/backtest return 401."""
    resp = client.post(
        "/api/v1/factor-investing/backtest",
        json={"dataset_id": registered_dataset_user_a, "factor_model": "carhart4"},
    )
    assert resp.status_code == 401


def test_cross_tenant_factor_backtest_rejected(registered_dataset_user_a, auth_headers_user_b):
    """Verify cross-tenant isolation on /api/v1/factor-investing/backtest."""
    resp = client.post(
        "/api/v1/factor-investing/backtest",
        json={
            "dataset_id": registered_dataset_user_a,
            "factor_model": "carhart4",
            "strategy_type": "factor_tilt",
            "estimation_window": 35,
        },
        headers=auth_headers_user_b,
    )
    assert resp.status_code in (403, 404)


def test_successful_dynamic_factor_backtest_tilt(registered_dataset_user_a, auth_headers_user_a):
    """Verify dynamic factor walk-forward backtest through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "carhart4",
        "strategy_type": "factor_tilt",
        "estimation_window": 35,
        "rebalance_frequency": "weekly",
        "factor_tilts": {"MKT": 1.0, "MOM": 0.5},
        "factor_constraints": {"MKT": {"min_beta": 0.5, "max_beta": 1.5}},
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
        "initial_capital": 100000.0,
    }
    resp = client.post(
        "/api/v1/factor-investing/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["strategy_type"] == "factor_tilt"
    assert data["factor_model"] == "carhart4"
    assert data["estimation_window"] == 35
    assert data["total_rebalances"] >= 2
    assert "summary_metrics" in data
    assert "benchmark_metrics" in data
    assert len(data["equity_curve"]) > 0
    assert len(data["rebalance_history"]) == data["total_rebalances"]
    assert "factor_exposure_series" in data

    # Verify metric keys
    sm = data["summary_metrics"]
    assert "cagr" in sm
    assert "sharpe_ratio" in sm
    assert "max_drawdown" in sm
    assert "total_transaction_costs" in sm
    assert sm["total_transaction_costs"] >= 0.0


def test_successful_dynamic_factor_backtest_momentum_rotation(registered_dataset_user_a, auth_headers_user_a):
    """Verify dynamic factor momentum rotation through the API."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "factor_model": "ff3",
        "strategy_type": "factor_momentum_rotation",
        "top_n_assets": 2,
        "estimation_window": 35,
        "rebalance_frequency": "weekly",
        "factor_tilts": {"MKT": 1.0, "SMB": 0.5},
    }
    resp = client.post(
        "/api/v1/factor-investing/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["strategy_type"] == "factor_momentum_rotation"
    assert data["total_rebalances"] >= 2


def test_dynamic_factor_backtest_insufficient_window(registered_dataset_user_a, auth_headers_user_a):
    """Verify validation error when estimation window exceeds available dataset history."""
    payload = {
        "dataset_id": registered_dataset_user_a,
        "estimation_window": 100,  # dataset only has 60 bars
    }
    resp = client.post(
        "/api/v1/factor-investing/backtest",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 422

