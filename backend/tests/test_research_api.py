"""
Integration and security tests for Portfolio Research Experiments and Strategy Comparison API.
Covers authentication, tenant isolation, execution lifecycle, non-destructive reruns,
reproducibility audit, and multi-run comparison rules.
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
    lines = ["date,ticker,market,currency,open,high,low,close,volume,adjusted_close"]
    aapl_prices = [150.0, 152.0, 151.0, 153.0, 155.0, 154.0, 156.0, 158.0, 157.0, 160.0]
    msft_prices = [240.0, 242.0, 241.0, 243.0, 245.0, 244.0, 246.0, 248.0, 247.0, 250.0]
    spy_prices = [390.0, 392.0, 391.0, 393.0, 394.0, 393.5, 395.0, 397.0, 396.0, 399.0]

    for day_idx in range(1, 11):
        dt_str = f"2023-01-{day_idx:02d}"
        p_a = aapl_prices[day_idx - 1]
        p_m = msft_prices[day_idx - 1]
        p_s = spy_prices[day_idx - 1]
        lines.append(f"{dt_str},AAPL,US,USD,{p_a},{p_a+1},{p_a-1},{p_a},1000,{p_a}")
        lines.append(f"{dt_str},MSFT,US,USD,{p_m},{p_m+1},{p_m-1},{p_m},1000,{p_m}")
        lines.append(f"{dt_str},SPY,US,USD,{p_s},{p_s+1},{p_s-1},{p_s},5000,{p_s}")

    csv_content = "\n".join(lines) + "\n"
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech_spy_research.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    return resp.json()["dataset_id"]


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_cookies():
    from app.auth.security import rate_limiter
    from app.market_data.service import clear_dataset_registry

    clear_dataset_registry()
    rate_limiter.clear_all()
    client.cookies.clear()


def test_unauthenticated_research_endpoints_rejected():
    """All research experiment endpoints reject unauthenticated access with 401."""
    dummy_payload = {
        "name": "Test",
        "strategy_type": "equal_weight",
        "dataset_id": "dummy-dataset-id",
        "config": {"assets": ["AAPL:US"]},
    }
    assert client.post("/api/v1/research/experiments", json=dummy_payload).status_code == 401
    assert client.get("/api/v1/research/experiments").status_code == 401
    assert client.get("/api/v1/research/experiments/test-id").status_code == 401
    assert client.patch("/api/v1/research/experiments/test-id", json={"name": "New"}).status_code == 401
    assert client.delete("/api/v1/research/experiments/test-id").status_code == 401
    assert client.post("/api/v1/research/experiments/test-id/runs").status_code == 401
    assert client.get("/api/v1/research/experiments/test-id/runs").status_code == 401
    assert client.get("/api/v1/research/runs/test-id").status_code == 401
    assert client.post("/api/v1/research/comparisons", json={"run_ids": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"]}).status_code == 401


def test_create_and_list_research_experiment(auth_headers_user_a, registered_dataset_user_a):
    """User A creates an equal-weight research experiment and lists it."""
    dataset_id = registered_dataset_user_a
    payload = {
        "name": "Tech Momentum Equal Weight",
        "description": "Baseline hypothesis comparing equal weight to market benchmark",
        "strategy_type": "equal_weight",
        "dataset_id": dataset_id,
        "config": {
            "assets": ["AAPL:US", "MSFT:US"],
            "rebalance_frequency": "monthly",
            "transaction_cost_bps": 10.0,
            "slippage_bps": 5.0,
        },
    }
    resp = client.post("/api/v1/research/experiments", json=payload, headers=auth_headers_user_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Tech Momentum Equal Weight"
    assert data["strategy_type"] == "equal_weight"
    assert data["version"] == 1
    assert len(data["config_fingerprint"]) == 64
    exp_id = data["id"]

    # List experiments
    list_resp = client.get("/api/v1/research/experiments", headers=auth_headers_user_a)
    assert list_resp.status_code == 200
    experiments = list_resp.json()
    assert any(e["id"] == exp_id for e in experiments)


def test_cross_tenant_experiment_isolation(auth_headers_user_a, auth_headers_user_b, registered_dataset_user_a):
    """User B cannot view, edit, execute, or delete User A's experiment."""
    dataset_id = registered_dataset_user_a
    # Create experiment as User A
    exp_resp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "User A Private Strategy",
            "strategy_type": "equal_weight",
            "dataset_id": dataset_id,
            "config": {"assets": ["AAPL:US", "MSFT:US"]},
        },
        headers=auth_headers_user_a,
    ).json()
    exp_id = exp_resp["id"]

    # User B attempts GET
    assert client.get(f"/api/v1/research/experiments/{exp_id}", headers=auth_headers_user_b).status_code == 404

    # User B attempts PATCH
    assert client.patch(
        f"/api/v1/research/experiments/{exp_id}",
        json={"name": "Hacked Name"},
        headers=auth_headers_user_b,
    ).status_code == 404

    # User B attempts POST run
    assert client.post(
        f"/api/v1/research/experiments/{exp_id}/runs",
        headers=auth_headers_user_b,
    ).status_code == 404

    # User B attempts DELETE
    assert client.delete(
        f"/api/v1/research/experiments/{exp_id}",
        headers=auth_headers_user_b,
    ).status_code == 404

    # User B attempts to create experiment referencing User A's private dataset
    assert client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Unauthorized Dataset Experiment",
            "strategy_type": "equal_weight",
            "dataset_id": dataset_id,
            "config": {"assets": ["AAPL:US", "MSFT:US"]},
        },
        headers=auth_headers_user_b,
    ).status_code in (403, 404)


def test_update_experiment_increments_version_on_semantic_change(auth_headers_user_a, registered_dataset_user_a):
    """Non-semantic updates keep version unchanged; semantic updates increment version and fingerprint."""
    dataset_id = registered_dataset_user_a
    exp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Initial Name",
            "strategy_type": "target_weights",
            "dataset_id": dataset_id,
            "config": {
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
                "transaction_cost_bps": 10.0,
            },
        },
        headers=auth_headers_user_a,
    ).json()
    exp_id = exp["id"]
    initial_fp = exp["config_fingerprint"]
    assert exp["version"] == 1

    # 1. Update name only (non-semantic)
    patch_name_resp = client.patch(
        f"/api/v1/research/experiments/{exp_id}",
        json={"name": "Updated Display Name"},
        headers=auth_headers_user_a,
    )
    assert patch_name_resp.status_code == 200
    patched_name = patch_name_resp.json()
    assert patched_name["name"] == "Updated Display Name"
    assert patched_name["version"] == 1
    assert patched_name["config_fingerprint"] == initial_fp

    # 2. Update config weights (semantic)
    patch_cfg_resp = client.patch(
        f"/api/v1/research/experiments/{exp_id}",
        json={
            "config": {
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.8, "MSFT:US": 0.2},
                "transaction_cost_bps": 10.0,
            }
        },
        headers=auth_headers_user_a,
    )
    assert patch_cfg_resp.status_code == 200
    patched_cfg = patch_cfg_resp.json()
    assert patched_cfg["version"] == 2
    assert patched_cfg["config_fingerprint"] != initial_fp


def test_execute_experiment_run_and_rerun_non_destructive(auth_headers_user_a, registered_dataset_user_a):
    """Execution persists results. Reruns increment run_number without destroying previous records."""
    dataset_id = registered_dataset_user_a
    exp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Target Weights Backtest",
            "strategy_type": "target_weights",
            "dataset_id": dataset_id,
            "config": {
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.6, "MSFT:US": 0.4},
                "rebalance_frequency": "daily",
                "transaction_cost_bps": 5.0,
                "slippage_bps": 2.0,
            },
        },
        headers=auth_headers_user_a,
    ).json()
    exp_id = exp["id"]

    # First Execution Run
    run_1_resp = client.post(
        f"/api/v1/research/experiments/{exp_id}/runs",
        headers=auth_headers_user_a,
    )
    assert run_1_resp.status_code == 201
    run_1 = run_1_resp.json()
    assert run_1["run_number"] == 1
    assert run_1["status"] == "succeeded"
    assert run_1["backtest_id"] is not None
    assert run_1["is_reproducible"] is True
    assert run_1["summary_kpis"]["cumulative_return"] is not None
    assert run_1["summary_kpis"]["sharpe_ratio"] is not None

    # Rerun Execution (Non-destructive)
    run_2_resp = client.post(
        f"/api/v1/research/experiments/{exp_id}/runs",
        headers=auth_headers_user_a,
    )
    assert run_2_resp.status_code == 201
    run_2 = run_2_resp.json()
    assert run_2["run_number"] == 2
    assert run_2["status"] == "succeeded"
    assert run_2["id"] != run_1["id"]

    # Verify run list contains BOTH runs
    runs_list_resp = client.get(
        f"/api/v1/research/experiments/{exp_id}/runs",
        headers=auth_headers_user_a,
    )
    assert runs_list_resp.status_code == 200
    runs = runs_list_resp.json()
    assert len(runs) == 2
    run_numbers = [r["run_number"] for r in runs]
    assert 1 in run_numbers and 2 in run_numbers


def test_execute_benchmark_attribution_experiment(auth_headers_user_a, registered_dataset_user_a):
    """Attribution experiment execution records tracking error, active return, and beta."""
    dataset_id = registered_dataset_user_a
    exp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Attribution vs SPY",
            "strategy_type": "benchmark_attribution",
            "dataset_id": dataset_id,
            "config": {
                "benchmark_asset": "SPY:US",
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
            },
        },
        headers=auth_headers_user_a,
    ).json()

    run_resp = client.post(
        f"/api/v1/research/experiments/{exp['id']}/runs",
        headers=auth_headers_user_a,
    )
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["status"] == "succeeded"
    assert run_data["performance_report_id"] is not None
    kpis = run_data["summary_kpis"]
    assert kpis["tracking_error"] is not None
    assert kpis["active_return"] is not None
    assert kpis["beta"] is not None


def test_execute_monte_carlo_risk_experiment(auth_headers_user_a, registered_dataset_user_a):
    """Monte Carlo risk experiment records VaR, CVaR, and seed provenance."""
    dataset_id = registered_dataset_user_a
    exp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Probabilistic Risk Sim",
            "strategy_type": "monte_carlo_risk",
            "dataset_id": dataset_id,
            "config": {
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.5, "MSFT:US": 0.5},
                "num_paths": 200,
                "horizon_days": 10,
                "seed": 99999,
            },
        },
        headers=auth_headers_user_a,
    ).json()

    run_resp = client.post(
        f"/api/v1/research/experiments/{exp['id']}/runs",
        headers=auth_headers_user_a,
    )
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["status"] == "succeeded"
    assert run_data["risk_simulation_id"] is not None
    kpis = run_data["summary_kpis"]
    assert kpis["var_95"] is not None
    assert kpis["cvar_95"] is not None
    assert kpis["seed"] == 99999


def test_compare_experiment_runs_success(auth_headers_user_a, registered_dataset_user_a):
    """Comparing compatible completed runs returns structured KPI side-by-side."""
    dataset_id = registered_dataset_user_a
    # Create Experiment 1
    exp1 = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Strategy Alpha",
            "strategy_type": "equal_weight",
            "dataset_id": dataset_id,
            "config": {"assets": ["AAPL:US", "MSFT:US"]},
        },
        headers=auth_headers_user_a,
    ).json()
    run1 = client.post(f"/api/v1/research/experiments/{exp1['id']}/runs", headers=auth_headers_user_a).json()

    # Create Experiment 2
    exp2 = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Strategy Beta",
            "strategy_type": "target_weights",
            "dataset_id": dataset_id,
            "config": {
                "assets": ["AAPL:US", "MSFT:US"],
                "weights": {"AAPL:US": 0.9, "MSFT:US": 0.1},
                "transaction_cost_bps": 20.0,
            },
        },
        headers=auth_headers_user_a,
    ).json()
    run2 = client.post(f"/api/v1/research/experiments/{exp2['id']}/runs", headers=auth_headers_user_a).json()

    # Compare
    comp_resp = client.post(
        "/api/v1/research/comparisons",
        json={"run_ids": [run1["id"], run2["id"]]},
        headers=auth_headers_user_a,
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert len(comp_data["runs"]) == 2
    assert comp_data["common_currency"] == "USD"
    run_names = [r["experiment_name"] for r in comp_data["runs"]]
    assert "Strategy Alpha" in run_names
    assert "Strategy Beta" in run_names


def test_delete_experiment_cascades_runs(auth_headers_user_a, registered_dataset_user_a):
    """Deleting an experiment deletes the experiment and its associated execution runs."""
    dataset_id = registered_dataset_user_a
    exp = client.post(
        "/api/v1/research/experiments",
        json={
            "name": "Disposable Experiment",
            "strategy_type": "equal_weight",
            "dataset_id": dataset_id,
            "config": {"assets": ["AAPL:US", "MSFT:US"]},
        },
        headers=auth_headers_user_a,
    ).json()
    exp_id = exp["id"]

    run = client.post(f"/api/v1/research/experiments/{exp_id}/runs", headers=auth_headers_user_a).json()
    run_id = run["id"]

    # Verify run exists
    assert client.get(f"/api/v1/research/runs/{run_id}", headers=auth_headers_user_a).status_code == 200

    # Delete experiment
    del_resp = client.delete(f"/api/v1/research/experiments/{exp_id}", headers=auth_headers_user_a)
    assert del_resp.status_code == 204

    # Both experiment and run are now 404
    assert client.get(f"/api/v1/research/experiments/{exp_id}", headers=auth_headers_user_a).status_code == 404
    assert client.get(f"/api/v1/research/runs/{run_id}", headers=auth_headers_user_a).status_code == 404
