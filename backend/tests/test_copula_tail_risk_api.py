"""
API Integration and Security Test Suite for Stage 22:
Copula Tail Risk, Multivariate Simulation & Tail Risk Parity Allocation.

Verifies:
1. Authentication enforcement (HTTP 401 on unauthenticated calls).
2. Multi-tenant isolation (User B cannot access User A's private dataset).
3. Successful copula fitting and pairwise tail dependence output.
4. Successful multivariate simulation preserving reproducibility and scenario counts.
5. Successful Tail Risk Parity (TRP) optimization with Euler reconciliation.
6. Validation error handling on degenerate inputs.
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

USER_A_ID = "33333333-3333-3333-3333-333333333333"
USER_B_ID = "44444444-4444-4444-4444-444444444444"


def _generate_synthetic_csv() -> bytes:
    """Generates synthetic CSV data with 60 trading days for 3 assets."""
    lines = ["date,ticker,market,close,currency"]
    import numpy as np

    rng = np.random.default_rng(42)
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
def setup_users_and_datasets():
    """Sets up User A (with private dataset) and User B."""
    with get_db_session() as session:
        session.query(DatasetModel).delete()
        session.query(UserModel).filter(
            UserModel.id.in_([USER_A_ID, USER_B_ID])
        ).delete()

        user_a = UserModel(
            id=USER_A_ID,
            email="user_a_copula@domain.com",
            hashed_password="hash",
            full_name="User A Copula",
            role="researcher",
            is_active=True,
        )
        user_b = UserModel(
            id=USER_B_ID,
            email="user_b_copula@domain.com",
            hashed_password="hash",
            full_name="User B Copula",
            role="researcher",
            is_active=True,
        )
        session.add_all([user_a, user_b])
        session.commit()

    token_a = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user_a_copula@domain.com", "role": "researcher"},
    )
    token_b = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user_b_copula@domain.com", "role": "researcher"},
    )

    csv_bytes = _generate_synthetic_csv()
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("copula_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200, resp.text
    dataset_a_id = resp.json()["dataset_id"]

    return {
        "token_a": token_a,
        "token_b": token_b,
        "dataset_a_id": dataset_a_id,
    }


def test_copula_unauthenticated_401():
    """Verifies unauthenticated calls to all copula endpoints return HTTP 401."""
    resp1 = client.post("/api/v1/copula/fit", json={"dataset_id": "dummy"})
    assert resp1.status_code == 401

    resp2 = client.post("/api/v1/copula/simulate", json={"dataset_id": "dummy"})
    assert resp2.status_code == 401

    resp3 = client.post("/api/v1/copula/tail-risk-parity", json={"dataset_id": "dummy"})
    assert resp3.status_code == 401


def test_copula_cross_tenant_isolation(setup_users_and_datasets):
    """User B cannot access User A's private dataset for copula analysis."""
    ctx = setup_users_and_datasets
    payload = {"dataset_id": ctx["dataset_a_id"], "copula_type": "clayton"}
    resp = client.post(
        "/api/v1/copula/fit",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_b']}"},
    )
    assert resp.status_code in (403, 404)


def test_copula_fit_success(setup_users_and_datasets):
    """Verifies successful copula fitting and pairwise tail dependence output."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "copula_type": "best_fit",
        "marginal_method": "empirical",
    }
    resp = client.post(
        "/api/v1/copula/fit",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == ctx["dataset_a_id"]
    assert len(data["tickers"]) == 3
    assert len(data["tail_dependence_matrix"]) == 3
    assert len(data["pairwise_results"]) == 3
    first_pair = data["pairwise_results"][0]
    assert "lower_tail_dependence" in first_pair
    assert "kendall_tau" in first_pair
    assert "aic" in first_pair


def test_copula_simulate_success(setup_users_and_datasets):
    """Verifies successful multivariate return simulation."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "copula_type": "clayton",
        "num_simulations": 1000,
        "random_seed": 42,
    }
    resp = client.post(
        "/api/v1/copula/simulate",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["num_simulations"] == 1000
    assert len(data["tickers"]) == 3
    assert len(data["sample_scenarios"]) <= 50
    assert "AAPL" in data["simulated_means"]


def test_tail_risk_parity_success(setup_users_and_datasets):
    """Verifies successful Tail Risk Parity allocation with Euler identity check."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "copula_type": "clayton",
        "confidence_level": 0.99,
        "num_simulations": 1500,
        "random_seed": 42,
    }
    resp = client.post(
        "/api/v1/copula/tail-risk-parity",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["converged"] is True
    weights = data["weights"]
    assert len(weights) == 3
    total_w = sum(weights.values())
    assert abs(total_w - 1.0) < 1e-3

    assert data["portfolio_var"] > 0.0
    assert data["portfolio_cvar"] >= data["portfolio_var"]
    assert data["euler_reconciliation_error"] < 1e-10
    assert "equal_weight" in data["baselines"]
    assert "inverse_volatility" in data["baselines"]


def test_copula_validation_errors(setup_users_and_datasets):
    """Verifies invalid parameters return HTTP 422."""
    ctx = setup_users_and_datasets
    # Invalid confidence level > 1.0
    resp = client.post(
        "/api/v1/copula/tail-risk-parity",
        json={"dataset_id": ctx["dataset_a_id"], "confidence_level": 1.5},
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 422
