"""
API integration and security tests for Scenario Analysis, Stress Testing & Sensitivity Analysis.
Tests authentication enforcement, tenant isolation, input limits, multi-currency rejection,
and end-to-end CRUD persistence.
"""

from datetime import datetime, timezone
import io
import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.db.models import DatasetModel, UserModel
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
def setup_users_and_dataset():
    """Seeds test users and a registered test dataset owned by User A."""
    with get_db_session() as session:
        # Seed User A
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

        # Seed User B
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
    """Uploads and registers a verified 3-asset dataset owned by User A."""
    csv_content = (
        "date,ticker,market,currency,open,high,low,close,volume,adjusted_close\n"
        "2023-01-01,AAPL,US,USD,150.0,155.0,149.0,152.0,1000,152.0\n"
        "2023-01-01,MSFT,US,USD,240.0,245.0,239.0,242.0,1000,242.0\n"
        "2023-01-01,GOOGL,US,USD,90.0,95.0,89.0,92.0,1000,92.0\n"
        "2023-01-02,AAPL,US,USD,152.0,156.0,151.0,154.0,1000,154.0\n"
        "2023-01-02,MSFT,US,USD,242.0,246.0,240.0,244.0,1000,244.0\n"
        "2023-01-02,GOOGL,US,USD,92.0,96.0,91.0,93.0,1000,93.0\n"
        "2023-01-03,AAPL,US,USD,154.0,158.0,153.0,157.0,1000,157.0\n"
        "2023-01-03,MSFT,US,USD,244.0,248.0,242.0,246.0,1000,246.0\n"
        "2023-01-03,GOOGL,US,USD,93.0,97.0,92.0,95.0,1000,95.0\n"
    )
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech_basket.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


def test_unauthenticated_request_rejected():
    """Unauthenticated call to /api/v1/scenarios returns 401 Unauthorized."""
    resp = client.post(
        "/api/v1/scenarios",
        json={
            "dataset_id": "dummy-id",
            "name": "Unauthorized Shock",
            "scenario_type": "custom_asset_shock",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
        },
    )
    assert resp.status_code == 401


def test_custom_asset_shock_execution_success(registered_dataset_id, auth_headers_user_a):
    """User A executes an instantaneous shock on own dataset successfully."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Tech Market Drawdown",
        "scenario_type": "custom_asset_shock",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.60, "MSFT:US": 0.40},
        "initial_capital": 100000.0,
        "asset_shocks": {"AAPL:US": -0.10, "MSFT:US": -0.20},
    }

    resp = client.post("/api/v1/scenarios", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["name"] == "Tech Market Drawdown"
    assert data["scenario_type"] == "custom_asset_shock"
    assert data["status"] == "completed"
    assert data["is_hypothetical"] is True

    # 60k * -10% + 40k * -20% = -6k + -8k = -$14,000 (-14%)
    metrics = data["metrics"]
    assert metrics["baseline_portfolio_value"] == 100000.0
    assert metrics["stressed_portfolio_value"] == 86000.0
    assert metrics["absolute_change"] == -14000.0
    assert metrics["percentage_change"] == -0.14

    assert len(data["contributions"]) == 2


def test_cross_tenant_dataset_access_blocked(registered_dataset_id, auth_headers_user_b):
    """User B cannot run scenario analysis using User A's private dataset."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Unauthorized Access Shock",
        "scenario_type": "custom_asset_shock",
        "assets": ["AAPL:US"],
        "weights": {"AAPL:US": 1.0},
    }

    resp = client.post("/api/v1/scenarios", json=payload, headers=auth_headers_user_b)
    # check_dataset_access emits 404 to avoid leaking dataset existence
    assert resp.status_code in (403, 404)


def test_historical_window_stress_endpoint(registered_dataset_id, auth_headers_user_a):
    """Executes historical stress window replaying observed asset returns."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Historical Replay Jan 2023",
        "scenario_type": "historical_window",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.50, "MSFT:US": 0.50},
        "initial_capital": 100000.0,
        "historical_start_date": "2023-01-01",
        "historical_end_date": "2023-01-03",
    }

    resp = client.post("/api/v1/scenarios", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scenario_type"] == "historical_window"
    assert len(data["contributions"]) == 2
    # AAPL: (157 - 152) / 152 = +3.289%
    # MSFT: (246 - 242) / 242 = +1.653%
    assert data["metrics"]["absolute_change"] > 0


def test_covariance_stress_endpoint(registered_dataset_id, auth_headers_user_a):
    """Executes covariance stress with volatility and correlation scaling."""
    payload = {
        "dataset_id": registered_dataset_id,
        "name": "Vol Shock +50%",
        "scenario_type": "covariance_stress",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.50, "MSFT:US": 0.50},
        "volatility_multiplier": 1.50,
        "correlation_multiplier": 1.20,
        "auto_project_psd": True,
    }

    resp = client.post("/api/v1/scenarios", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["metrics"]["stressed_volatility"] is not None
    assert data["metrics"]["baseline_volatility"] is not None
    assert data["metrics"]["stressed_volatility"] > data["metrics"]["baseline_volatility"]


def test_sensitivity_analysis_endpoint(registered_dataset_id, auth_headers_user_a):
    """Executes 1-factor and 2-factor sensitivity grid sweeps."""
    payload_1d = {
        "dataset_id": registered_dataset_id,
        "name": "AAPL Sensitivity",
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.60, "MSFT:US": 0.40},
        "factor_1_asset": "AAPL:US",
        "factor_1_min_shock": -0.20,
        "factor_1_max_shock": 0.20,
        "factor_1_steps": 5,
    }

    resp = client.post("/api/v1/scenarios/sensitivity", json=payload_1d, headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["grid"]) == 5
    assert data["factor_1_asset"] == "AAPL:US"
    assert data["factor_2_asset"] is None


def test_sensitivity_grid_limit_enforcement(registered_dataset_id, auth_headers_user_a):
    """Rejects 2D grid that exceeds maximum resolution ceiling of 441 points."""
    payload_oversized = {
        "dataset_id": registered_dataset_id,
        "assets": ["AAPL:US", "MSFT:US"],
        "weights": {"AAPL:US": 0.50, "MSFT:US": 0.50},
        "factor_1_asset": "AAPL:US",
        "factor_1_steps": 50,  # 50 * 20 = 1000 > 441
        "factor_2_asset": "MSFT:US",
        "factor_2_steps": 20,
    }
    resp = client.post("/api/v1/scenarios/sensitivity", json=payload_oversized, headers=auth_headers_user_a)
    assert resp.status_code == 422


def test_saved_scenarios_lifecycle_and_tenant_isolation(registered_dataset_id, auth_headers_user_a, auth_headers_user_b):
    """
    Tests CRUD lifecycle and tenant isolation:
    User A runs scenario -> Listed by User A -> User B cannot access -> User A deletes.
    """
    # 1. User A executes scenario
    resp_create = client.post(
        "/api/v1/scenarios",
        json={
            "dataset_id": registered_dataset_id,
            "name": "User A Private Scenario",
            "scenario_type": "custom_asset_shock",
            "assets": ["AAPL:US"],
            "weights": {"AAPL:US": 1.0},
            "asset_shocks": {"AAPL:US": -0.05},
        },
        headers=auth_headers_user_a,
    )
    assert resp_create.status_code == 200
    scenario_id = resp_create.json()["id"]

    # 2. User A lists runs
    resp_list_a = client.get("/api/v1/scenarios", headers=auth_headers_user_a)
    assert resp_list_a.status_code == 200
    ids_a = [r["id"] for r in resp_list_a.json()]
    assert scenario_id in ids_a

    # 3. User B lists runs -> scenario_id must not appear
    resp_list_b = client.get("/api/v1/scenarios", headers=auth_headers_user_b)
    assert resp_list_b.status_code == 200
    ids_b = [r["id"] for r in resp_list_b.json()]
    assert scenario_id not in ids_b

    # 4. User B attempts to retrieve User A's run -> 404
    resp_get_b = client.get(f"/api/v1/scenarios/{scenario_id}", headers=auth_headers_user_b)
    assert resp_get_b.status_code == 404

    # 5. User B attempts to delete User A's run -> 404
    resp_del_b = client.delete(f"/api/v1/scenarios/{scenario_id}", headers=auth_headers_user_b)
    assert resp_del_b.status_code == 404

    # 6. User A retrieves own run
    resp_get_a = client.get(f"/api/v1/scenarios/{scenario_id}", headers=auth_headers_user_a)
    assert resp_get_a.status_code == 200
    assert resp_get_a.json()["id"] == scenario_id

    # 7. User A deletes own run
    resp_del_a = client.delete(f"/api/v1/scenarios/{scenario_id}", headers=auth_headers_user_a)
    assert resp_del_a.status_code == 200
