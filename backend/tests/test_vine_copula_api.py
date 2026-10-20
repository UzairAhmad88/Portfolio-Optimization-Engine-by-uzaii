"""
API Integration and Security Test Suite for Stage 23:
Regular Vine Copula Architecture, Pair-Copula Decomposition & Vine Tail Risk Parity.
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

USER_A_ID = "55555555-5555-5555-5555-555555555555"
USER_B_ID = "66666666-6666-6666-6666-666666666666"


def _generate_synthetic_csv() -> bytes:
    """Generates synthetic CSV data with 60 trading days for 3 assets."""
    lines = ["date,ticker,market,close,currency"]
    import numpy as np

    rng = np.random.default_rng(101)
    p1 = 150.0
    p2 = 100.0
    p3 = 80.0

    for i in range(60):
        month = (i // 25) + 1
        day = (i % 25) + 1
        dt = f"2024-{month:02d}-{day:02d}"

        r1 = rng.normal(0.0008, 0.012)
        r2 = rng.normal(0.0004, 0.010)
        r3 = rng.normal(-0.0002, 0.015)
        p1 *= (1.0 + r1)
        p2 *= (1.0 + r2)
        p3 *= (1.0 + r3)

        lines.append(f"{dt},AAPL,US,{p1:.2f},USD")
        lines.append(f"{dt},MSFT,US,{p2:.2f},USD")
        lines.append(f"{dt},GOOGL,US,{p3:.2f},USD")

    return "\n".join(lines).encode("utf-8")


@pytest.fixture
def setup_vine_test_env():
    """Sets up User A (with private dataset) and User B."""
    with get_db_session() as session:
        session.query(DatasetModel).delete()
        session.query(UserModel).filter(
            UserModel.id.in_([USER_A_ID, USER_B_ID])
        ).delete()

        user_a = UserModel(
            id=USER_A_ID,
            email="user_a_vine@domain.com",
            hashed_password="hash",
            full_name="User A Vine",
            role="researcher",
            is_active=True,
        )
        user_b = UserModel(
            id=USER_B_ID,
            email="user_b_vine@domain.com",
            hashed_password="hash",
            full_name="User B Vine",
            role="researcher",
            is_active=True,
        )
        session.add_all([user_a, user_b])
        session.commit()

    token_a = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user_a_vine@domain.com", "role": "researcher"},
    )
    token_b = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user_b_vine@domain.com", "role": "researcher"},
    )

    csv_bytes = _generate_synthetic_csv()
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("vine_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200, resp.text
    dataset_a_id = resp.json()["dataset_id"]

    return {
        "token_a": token_a,
        "token_b": token_b,
        "dataset_a_id": dataset_a_id,
    }


def test_vine_unauthenticated_401():
    """Verifies unauthenticated calls to all vine endpoints return HTTP 401."""
    resp1 = client.post("/api/v1/copula/vine/fit", json={"dataset_id": "dummy"})
    assert resp1.status_code == 401

    resp2 = client.post("/api/v1/copula/vine/simulate", json={"dataset_id": "dummy"})
    assert resp2.status_code == 401

    resp3 = client.post("/api/v1/copula/vine/tail-risk-parity", json={"dataset_id": "dummy"})
    assert resp3.status_code == 401


def test_vine_cross_tenant_isolation(setup_vine_test_env):
    """User B cannot access User A's private dataset for vine copula analysis."""
    ctx = setup_vine_test_env
    payload = {"dataset_id": ctx["dataset_a_id"], "vine_type": "c_vine"}
    resp = client.post(
        "/api/v1/copula/vine/fit",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_b']}"},
    )
    assert resp.status_code in (403, 404)


def test_vine_fit_success(setup_vine_test_env):
    """Verifies successful vine copula fitting and tree decomposition output."""
    ctx = setup_vine_test_env
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "vine_type": "c_vine",
        "marginal_method": "empirical",
    }
    resp = client.post(
        "/api/v1/copula/vine/fit",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == ctx["dataset_a_id"]
    assert data["vine_type"] == "c_vine"
    assert data["dimension"] == 3
    assert len(data["trees"]) == 2  # d - 1 trees
    # Tree 1 has 2 edges, Tree 2 has 1 edge
    assert len(data["trees"][0]) == 2
    assert len(data["trees"][1]) == 1


def test_vine_simulate_success(setup_vine_test_env):
    """Verifies successful vine copula simulation."""
    ctx = setup_vine_test_env
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "vine_type": "c_vine",
        "num_simulations": 1000,
        "random_seed": 777,
    }
    resp = client.post(
        "/api/v1/copula/vine/simulate",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["num_simulations"] == 1000
    assert len(data["tickers"]) == 3
    assert len(data["sample_scenarios"]) == 50
    assert len(data["sample_correlation_matrix"]) == 3


def test_vine_tail_risk_parity_success(setup_vine_test_env):
    """Verifies successful TRP optimization under vine copula simulation."""
    ctx = setup_vine_test_env
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "vine_type": "c_vine",
        "confidence_level": 0.99,
        "num_simulations": 1000,
        "random_seed": 42,
    }
    resp = client.post(
        "/api/v1/copula/vine/tail-risk-parity",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["converged"] is True
    weights = data["weights"]
    assert len(weights) == 3
    assert pytest.approx(sum(weights.values()), abs=1e-3) == 1.0
    assert "baselines" in data


# ============================================================================
# Stage 24: Dynamic Walk-Forward Vine Backtest API Tests
# ============================================================================

def test_vine_backtest_unauthenticated_401():
    """Unauthenticated call to /vine/backtest returns HTTP 401."""
    resp = client.post("/api/v1/copula/vine/backtest", json={"dataset_id": "dummy"})
    assert resp.status_code == 401


def test_vine_backtest_cross_tenant_isolation(setup_vine_test_env):
    """User B cannot run backtests on User A's private dataset."""
    ctx = setup_vine_test_env
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "vine_type": "c_vine",
        "estimation_window": 35,
        "rebalance_frequency": "monthly",
    }
    resp = client.post(
        "/api/v1/copula/vine/backtest",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_b']}"},
    )
    assert resp.status_code in (403, 404)


def test_vine_backtest_success(setup_vine_test_env):
    """Verifies successful walk-forward vine backtest execution via REST API."""
    ctx = setup_vine_test_env
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "vine_type": "c_vine",
        "estimation_window": 35,
        "rebalance_frequency": "monthly",
        "num_simulations": 1000,
        "confidence_level": 0.99,
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
        "random_seed": 42,
    }
    resp = client.post(
        "/api/v1/copula/vine/backtest",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == ctx["dataset_a_id"]
    assert data["vine_type"] == "c_vine"
    assert data["estimation_window"] == 35
    assert data["total_evaluation_days"] > 0
    assert data["total_rebalances"] >= 1

    # Check metrics structure
    for kpi_key in ["strategy_metrics", "benchmark_metrics", "static_trp_metrics"]:
        metrics = data[kpi_key]
        assert "total_return" in metrics
        assert "annualized_volatility" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "total_turnover" in metrics
        assert "total_transaction_costs" in metrics

    # Check equity curve points
    assert len(data["equity_curve"]) == data["total_evaluation_days"]
    first_pt = data["equity_curve"][0]
    assert "date" in first_pt
    assert "strategy_equity" in first_pt
    assert "benchmark_equity" in first_pt
    assert "static_trp_equity" in first_pt
    assert "drawdown" in first_pt

    # Check rebalance history
    assert len(data["rebalance_history"]) == data["total_rebalances"]
    first_rebal = data["rebalance_history"][0]
    assert "rebalance_index" in first_rebal
    assert "training_window_start" in first_rebal
    assert "training_window_end" in first_rebal
    assert "weights" in first_rebal
    assert len(first_rebal["weights"]) == 3


def test_vine_backtest_validation_errors(setup_vine_test_env):
    """Verifies that invalid window lengths are rejected with HTTP 422."""
    ctx = setup_vine_test_env
    # estimation_window < 30 rejected by schema
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "estimation_window": 20,
    }
    resp = client.post(
        "/api/v1/copula/vine/backtest",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 422

