"""
API integration and security tests for Monte Carlo Simulation, Probabilistic Risk Analysis, VaR & CVaR.
Tests authentication enforcement, tenant isolation, input limits, multi-estimator comparisons, and CRUD.
"""

from __future__ import annotations

import io
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
    """Generates valid JWT auth header for User A."""
    token = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user.a@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b():
    """Generates valid JWT auth header for User B."""
    token = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user.b@quant.local", "role": "researcher"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_users():
    """Seeds test users A and B in database."""
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
def registered_dataset_id(auth_headers_user_a):
    """Uploads and registers a verified 2-asset dataset owned by User A with 10 days of prices."""
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    aapl_prices = [150.0, 152.0, 151.0, 153.0, 155.0, 154.0, 156.0, 158.0, 157.0, 160.0]
    msft_prices = [240.0, 242.0, 241.0, 243.0, 245.0, 244.0, 246.0, 248.0, 247.0, 250.0]

    for day_idx in range(1, 11):
        dt_str = f"2023-01-{day_idx:02d}"
        p_aapl = aapl_prices[day_idx - 1]
        p_msft = msft_prices[day_idx - 1]
        lines.append(f"{dt_str},AAPL,US,USD,{p_aapl},{p_aapl+1},{p_aapl-1},{p_aapl},1000,{p_aapl}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_msft},{p_msft+1},{p_msft-1},{p_msft},1000,{p_msft}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech_prices_10d.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


def test_unauthenticated_simulation_rejected():
    """Unauthenticated POST /api/v1/risk-simulations returns 401 Unauthorized."""
    resp = client.post(
        "/api/v1/risk-simulations",
        json={
            "dataset_id": "dummy",
            "name": "Test Sim",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
        },
    )
    assert resp.status_code == 401


def test_unauthenticated_var_cvar_rejected():
    """Unauthenticated POST /api/v1/risk-simulations/var-cvar returns 401 Unauthorized."""
    resp = client.post(
        "/api/v1/risk-simulations/var-cvar",
        json={
            "dataset_id": "dummy",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
        },
    )
    assert resp.status_code == 401


def test_authenticated_monte_carlo_simulation_normal(registered_dataset_id, auth_headers_user_a):
    """Executes a 10-day 500-path Multivariate Normal simulation and verifies complete response."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Tech 10D Monte Carlo",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.6, "MSFT:US": 0.4},
        "initial_capital": 100000.0,
        "horizon_days": 10,
        "num_paths": 500,
        "confidence_levels": [0.95, 0.99],
        "distribution": "multivariate_normal",
        "rebalance_policy": "buy_and_hold",
        "seed": 42,
    }

    resp = client.post("/api/v1/risk-simulations", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"].startswith("sim-")
    assert data["dataset_id"] == registered_dataset_id
    assert data["num_paths"] == 500
    assert data["horizon_days"] == 10
    assert data["seed"] == 42
    assert data["is_hypothetical"] is True

    summary = data["summary"]
    assert summary["initial_capital"] == 100000.0
    assert summary["expected_terminal_value"] > 0.0
    assert 0.0 <= summary["prob_negative_return"] <= 1.0
    assert "p5" in summary["terminal_quantiles"]
    assert "p95" in summary["terminal_quantiles"]

    # VaR & CVaR metrics
    assert len(summary["var_cvar_metrics"]) == 2
    for m in summary["var_cvar_metrics"]:
        assert m["cvar_absolute"] >= m["var_absolute"]
        assert m["cvar_percentage"] >= m["var_percentage"]

    # Multi-estimator comparisons
    assert len(summary["estimator_comparisons"]) == 2
    for comp in summary["estimator_comparisons"]:
        assert isinstance(comp["monte_carlo_var"], float)
        assert isinstance(comp["parametric_var"], float)
        assert comp["monte_carlo_cvar"] >= comp["monte_carlo_var"]
        assert comp["parametric_cvar"] >= comp["parametric_var"]

    # Histogram & Trajectory
    assert len(data["distribution_bins"]) == 30
    assert len(data["trajectory"]) == 11  # day 0 to day 10
    assert data["trajectory"][0]["median_value"] == 100000.0


def test_authenticated_monte_carlo_simulation_student_t(registered_dataset_id, auth_headers_user_a):
    """Executes a Multivariate Student-t simulation and verifies degrees of freedom validation."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Tech Student-t Sim",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
        "initial_capital": 50000.0,
        "horizon_days": 5,
        "num_paths": 250,
        "confidence_levels": [0.95],
        "distribution": "multivariate_student_t",
        "degrees_of_freedom": 4.0,
        "seed": 999,
    }

    resp = client.post("/api/v1/risk-simulations", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["distribution"] == "multivariate_student_t"
    assert data["summary"]["expected_terminal_value"] > 0.0


def test_cross_tenant_dataset_access_blocked(registered_dataset_id, auth_headers_user_b):
    """User B cannot execute a simulation against User A's private dataset."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Unauthorized Sim",
        "assets": ["AAPL:US"],
        "weights": {"AAPL:US": 1.0},
    }

    resp = client.post("/api/v1/risk-simulations", json=payload, headers=auth_headers_user_b)
    # Blocked by check_dataset_access: returns 403 Forbidden or 404
    assert resp.status_code in (403, 404)


def test_simulation_resource_limits_enforced(registered_dataset_id, auth_headers_user_a):
    """Rejects excessive paths (> 10,000) or excessive horizon (> 252 days)."""
    # Exceed paths
    resp1 = client.post(
        "/api/v1/risk-simulations",
        json={
            "dataset_id": registered_dataset_id,
            "name": "Excessive Paths",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
            "num_paths": 20000,
        },
        headers=auth_headers_user_a,
    )
    assert resp1.status_code == 422

    # Exceed horizon
    resp2 = client.post(
        "/api/v1/risk-simulations",
        json={
            "dataset_id": registered_dataset_id,
            "name": "Excessive Horizon",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
            "horizon_days": 500,
        },
        headers=auth_headers_user_a,
    )
    assert resp2.status_code == 422


def test_simulation_crud_and_tenant_isolation(registered_dataset_id, auth_headers_user_a, auth_headers_user_b):
    """Verifies listing, retrieving, and deleting simulation runs, and enforces cross-tenant protection."""
    # User A creates a run
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "User A Run to Test CRUD",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
        "num_paths": 200,
        "horizon_days": 5,
    }
    create_resp = client.post("/api/v1/risk-simulations", json=payload, headers=auth_headers_user_a)
    assert create_resp.status_code == 200
    run_id = create_resp.json()["id"]

    # 1. User A lists runs: run_id present
    list_resp = client.get("/api/v1/risk-simulations", headers=auth_headers_user_a)
    assert list_resp.status_code == 200
    runs = list_resp.json()
    assert any(r["id"] == run_id for r in runs)

    # 2. User B lists runs: run_id NOT present
    b_list_resp = client.get("/api/v1/risk-simulations", headers=auth_headers_user_b)
    assert b_list_resp.status_code == 200
    assert not any(r["id"] == run_id for r in b_list_resp.json())

    # 3. User B cannot retrieve User A's run
    b_get_resp = client.get(f"/api/v1/risk-simulations/{run_id}", headers=auth_headers_user_b)
    assert b_get_resp.status_code == 404

    # 4. User B cannot delete User A's run
    b_del_resp = client.delete(f"/api/v1/risk-simulations/{run_id}", headers=auth_headers_user_b)
    assert b_del_resp.status_code == 404

    # 5. User A retrieves run successfully
    a_get_resp = client.get(f"/api/v1/risk-simulations/{run_id}", headers=auth_headers_user_a)
    assert a_get_resp.status_code == 200
    assert a_get_resp.json()["id"] == run_id

    # 6. User A deletes run successfully
    a_del_resp = client.delete(f"/api/v1/risk-simulations/{run_id}", headers=auth_headers_user_a)
    assert a_del_resp.status_code == 200

    # 7. Subsequent retrieval returns 404
    assert client.get(f"/api/v1/risk-simulations/{run_id}", headers=auth_headers_user_a).status_code == 404


def test_standalone_var_cvar_endpoint(registered_dataset_id, auth_headers_user_a):
    """Verifies that POST /api/v1/risk-simulations/var-cvar returns parametric & historical comparisons."""
    payload = {
        "dataset_id": registered_dataset_id,
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.6, "MSFT:US": 0.4},
        "initial_capital": 100000.0,
        "horizon_days": 1,
        "confidence_levels": [0.95, 0.99],
    }
    resp = client.post("/api/v1/risk-simulations/var-cvar", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["parametric_var"] > 0.0
    assert data[0]["parametric_cvar"] >= data[0]["parametric_var"]
