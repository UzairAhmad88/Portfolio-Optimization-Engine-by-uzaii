"""
Integration, security, and numerical verification suite for Stage 33 Gate D
Overfitting Diagnostics REST API endpoint.

Tests:
- API contract, parameter boundaries, and JSON serialization.
- Experiment and run selection, membership, and deterministic ordering.
- Deterministic date alignment (inner join, missing dates, duplicate dates, non-finite values).
- Numerical agreement with core engine (PBO, DSR, MinBTL, expected max Sharpe).
- Security, tenant isolation, and computational resource limits.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics.overfitting import compute_overfitting_diagnostics
from app.auth.security import create_access_token, hash_password
from app.db.models import (
    BacktestRunModel,
    DatasetModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.db.session import get_db_session
from app.main import app
from app.research.fingerprint import canonical_json_dumps, compute_config_fingerprint
from tests.fixtures.overfitting_fixtures import generate_synthetic_white_noise_panel

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
def setup_test_users():
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

        # Base dataset for experiments
        ds = session.get(DatasetModel, "dataset-overfitting-test")
        if not ds:
            ds = DatasetModel(
                id="dataset-overfitting-test",
                user_id=USER_A_ID,
                filename="test_dataset.csv",
                content_sha256="d" * 64,
                rows_examined=100,
                valid_rows=100,
                rejected_rows=0,
                status="completed",
            )
            session.add(ds)

        session.commit()
    client.cookies.clear()


def create_experiment_helper(
    user_id: str,
    name: str = "Test Experiment",
    strategy_type: str = "target_weights",
    dataset_id: str = "dataset-overfitting-test",
) -> str:
    """Helper to create a persistent research experiment in the database."""
    config = {
        "strategy_type": strategy_type,
        "dataset_id": dataset_id,
        "assets": ["AAPL:US", "MSFT:US"],
        "rebalance_frequency": "monthly",
    }
    fingerprint = compute_config_fingerprint(config)
    exp_id = str(uuid4())

    with get_db_session() as session:
        exp = ResearchExperimentModel(
            id=exp_id,
            user_id=user_id,
            dataset_id=dataset_id,
            name=name,
            strategy_type=strategy_type,
            config_json=canonical_json_dumps(config),
            config_fingerprint=fingerprint,
            version=1,
        )
        session.add(exp)
        session.commit()
    return exp_id


def create_run_with_backtest_helper(
    user_id: str,
    experiment_id: str,
    run_number: int,
    dates: list[str],
    returns: list[float],
    status: str = "succeeded",
    dataset_id: str = "dataset-overfitting-test",
    snapshot_id: str | None = None,
    attach_backtest: bool = True,
) -> str:
    """Helper to create a run record with attached backtest equity curve."""
    with get_db_session() as session:
        bt_id = None
        if attach_backtest:
            bt_id = str(uuid4())
            portfolio_val = 100000.0
            curve = []
            for d, r in zip(dates, returns):
                portfolio_val *= (1.0 + r)
                curve.append({
                    "date": d,
                    "portfolio_value_net": portfolio_val,
                    "portfolio_value_gross": portfolio_val,
                    "return_net": r,
                    "return_gross": r,
                    "drawdown_net": 0.0,
                    "drawdown_gross": 0.0,
                })
            bt = BacktestRunModel(
                id=bt_id,
                user_id=user_id,
                dataset_id=dataset_id,
                name=f"Run #{run_number} Backtest",
                strategy_type="target_weights",
                rebalance_frequency="daily",
                initial_capital=100000.0,
                status="completed",
                equity_curve_json=json.dumps(curve),
                snapshot_id=snapshot_id,
            )
            session.add(bt)

        run_id = str(uuid4())
        run = ResearchExperimentRunModel(
            id=run_id,
            experiment_id=experiment_id,
            user_id=user_id,
            run_number=run_number,
            status=status,
            backtest_id=bt_id,
            snapshot_id=snapshot_id,
            config_fingerprint="f" * 64,
        )
        session.add(run)
        session.commit()
    return run_id


class TestOverfittingAPIContracts:
    """A. API Contract, Payload Validation & Response Serialization Tests."""

    def test_overfitting_api_valid_request_and_response(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Valid Diagnostics Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        T = len(dates)  # 50 days

        # Seed 3 runs with synthetic returns
        np.random.seed(101)
        for r_num in range(1, 4):
            rets = np.random.normal(0.0005 * r_num, 0.01, size=T).tolist()
            create_run_with_backtest_helper(USER_A_ID, exp_id, r_num, dates, rets)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 8, "significance_level": 0.05, "annualization_factor": 252},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["experiment_id"] == exp_id
        assert data["evaluated_runs_count"] == 3
        assert data["aligned_observations_count"] == 50
        assert data["n_slices"] == 8
        assert data["total_combinations_count"] == 70  # binom(8, 4) = 70
        assert 0.0 <= data["pbo"] <= 1.0
        assert data["pbo_risk_level"] in ("low", "moderate", "high", "severe")
        assert 0.0 <= data["deflated_sharpe_ratio"] <= 1.0
        assert isinstance(data["is_statistically_significant"], bool)
        assert data["best_run_id"] is not None
        assert data["best_run_number"] in (1, 2, 3)
        assert len(data["rank_distribution"]) == 10
        assert len(data["runs_summary"]) == 3
        assert len(data["combinations_sample"]) == 70

    def test_overfitting_api_optional_run_selection(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Selective Runs Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        T = len(dates)

        np.random.seed(102)
        run_ids = []
        for r_num in range(1, 5):
            rets = np.random.normal(0.0005, 0.01, size=T).tolist()
            rid = create_run_with_backtest_helper(USER_A_ID, exp_id, r_num, dates, rets)
            run_ids.append(rid)

        # Select only runs 1 and 3
        selected = [run_ids[0], run_ids[2]]
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"run_ids": selected, "n_slices": 8},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated_runs_count"] == 2
        returned_run_ids = {r["run_id"] for r in data["runs_summary"]}
        assert returned_run_ids == set(selected)

    def test_overfitting_api_invalid_request_fields(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Validation Exp")

        # Odd n_slices
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 7},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "even integer" in resp.text

        # Out-of-bounds n_slices (too small < 4)
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 2},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422

        # Out-of-bounds n_slices (too large > 16)
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 18},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422

        # Invalid alpha <= 0.0
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"significance_level": 0.0},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422

        # Invalid alpha >= 0.5
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"significance_level": 0.55},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422

    def test_overfitting_api_empty_body_uses_defaults(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Default Payload Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        T = len(dates)

        np.random.seed(103)
        for r_num in range(1, 3):
            rets = np.random.normal(0.0005, 0.01, size=T).tolist()
            create_run_with_backtest_helper(USER_A_ID, exp_id, r_num, dates, rets)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_slices"] == 16


class TestOverfittingAPIExperimentAndRunSelection:
    """B. Experiment & Run Selection, Membership & Ordering Tests."""

    def test_unknown_experiment_returns_404(self, auth_headers_user_a):
        resp = client.post(
            f"/api/v1/research/experiments/{uuid4()}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 404

    def test_unknown_run_returns_404(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Missing Run Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        r1 = create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * len(dates))

        missing_id = str(uuid4())
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"run_ids": [r1, missing_id]},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 404
        assert missing_id in resp.text

    def test_run_belonging_to_another_experiment_rejected(self, auth_headers_user_a):
        exp_a = create_experiment_helper(USER_A_ID, "Exp A")
        exp_b = create_experiment_helper(USER_A_ID, "Exp B")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]

        r_a1 = create_run_with_backtest_helper(USER_A_ID, exp_a, 1, dates, [0.001] * len(dates))
        r_b1 = create_run_with_backtest_helper(USER_A_ID, exp_b, 1, dates, [0.001] * len(dates))

        # Attempt to analyze exp_a with a run from exp_b
        resp = client.post(
            f"/api/v1/research/experiments/{exp_a}/overfitting-diagnostics",
            json={"run_ids": [r_a1, r_b1]},
            headers=auth_headers_user_a,
        )
        assert resp.status_code in (404, 422)

    def test_duplicate_run_ids_rejected(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Duplicate Run Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        r1 = create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * len(dates))

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"run_ids": [r1, r1]},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "duplicate" in resp.text.lower()

    def test_insufficient_eligible_runs_rejected(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Single Run Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * len(dates))

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "at least 2" in resp.text.lower()

    def test_failed_runs_and_runs_without_backtest_filtered(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Filtered Runs Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]

        # 1 valid run, 1 failed run, 1 run with no backtest
        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * len(dates), status="succeeded")
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates, [0.001] * len(dates), status="failed")
        create_run_with_backtest_helper(USER_A_ID, exp_id, 3, dates, [0.001] * len(dates), status="succeeded", attach_backtest=False)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "at least 2" in resp.text.lower()


class TestOverfittingAPIDataAlignment:
    """C. Deterministic Historical Return Data Alignment & Validation Tests."""

    def test_missing_dates_synchronized_via_inner_join(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Date Alignment Exp")
        # Run 1: Days 1 to 50
        dates_1 = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        # Run 2: Days 11 to 60 (overlapping on Days 11 to 50 = 40 days)
        dates_2 = [f"2023-01-{i:02d}" for i in range(11, 31)] + [f"2023-02-{i:02d}" for i in range(1, 31)]

        rets_1 = [0.001] * len(dates_1)
        rets_2 = [0.002] * len(dates_2)

        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates_1, rets_1)
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates_2, rets_2)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 8},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["aligned_observations_count"] == 40  # 20 from Jan + 20 from Feb

    def test_duplicate_dates_rejected(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Duplicate Date Exp")
        dates_valid = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        dates_dup = dates_valid.copy()
        dates_dup[5] = dates_dup[4]  # duplicate date!

        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates_valid, [0.001] * len(dates_valid))
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates_dup, [0.001] * len(dates_dup))

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "duplicate observation dates" in resp.text.lower()

    def test_non_finite_returns_rejected(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Non Finite Returns Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        rets_valid = [0.001] * len(dates)
        rets_nan = [0.001] * len(dates)
        rets_nan[10] = float("nan")

        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, rets_valid)
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates, rets_nan)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "non-finite" in resp.text.lower()

    def test_insufficient_aligned_observations_rejected(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Too Short Exp")
        # Only 10 observations, but n_slices=16 requires at least 32 observations (2 * 16)
        dates = [f"2023-01-{i:02d}" for i in range(1, 11)]

        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * 10)
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates, [0.001] * 10)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 16},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "insufficient synchronized observation dates" in resp.text.lower()


class TestOverfittingAPINumericalIntegration:
    """D. Numerical Engine Agreement & Leakage-Free Optimization Tests."""

    def test_numerical_agreement_with_core_engine(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Numerical Agreement Exp")
        T = 100
        N = 5
        dates = [f"2023-{i//30 + 1:02d}-{i%30 + 1:02d}" for i in range(T)]

        np.random.seed(42)
        panel = np.random.normal(0.0005, 0.012, size=(T, N))

        run_ids = []
        for j in range(N):
            rid = create_run_with_backtest_helper(
                USER_A_ID, exp_id, j + 1, dates, panel[:, j].tolist()
            )
            run_ids.append(rid)

        # 1. Direct engine execution
        run_meta = [{"run_id": rid, "run_number": j + 1} for j, rid in enumerate(run_ids)]
        expected = compute_overfitting_diagnostics(
            returns_matrix=panel,
            run_metadata=run_meta,
            n_slices=8,
            alpha=0.05,
            annualization_factor=252,
            experiment_id=exp_id,
        )

        # 2. REST API call
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 8, "significance_level": 0.05, "annualization_factor": 252},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        actual = resp.json()

        # Strict mathematical agreement
        assert actual["evaluated_runs_count"] == N
        assert actual["aligned_observations_count"] == T
        assert actual["total_combinations_count"] == expected.total_combinations_count
        assert abs(actual["pbo"] - expected.pbo) < 1e-12
        assert actual["pbo_risk_level"] == expected.pbo_risk_level
        assert actual["best_run_id"] == expected.best_run_id
        assert actual["best_run_number"] == expected.best_run_number
        assert abs(actual["best_nominal_sharpe"] - expected.best_nominal_sharpe) < 1e-10
        assert abs(actual["expected_max_sharpe"] - expected.expected_max_sharpe) < 1e-10
        assert abs(actual["deflated_sharpe_ratio"] - expected.deflated_sharpe_ratio) < 1e-10
        assert actual["is_statistically_significant"] == expected.is_statistically_significant

        # Regression slope agreement
        assert abs(actual["degradation_regression"]["slope"] - expected.degradation_regression.slope) < 1e-10
        assert abs(actual["degradation_regression"]["intercept"] - expected.degradation_regression.intercept) < 1e-10

    def test_run_metadata_and_provenance_preserved(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Provenance Exp")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        T = len(dates)

        # Run 2 has significantly superior alpha
        r1 = create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.0001] * T)
        r2 = create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates, [0.005] * T)

        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"n_slices": 4},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["best_run_id"] == r2
        assert data["best_run_number"] == 2


class TestOverfittingAPISecurityAndResourceLimits:
    """E. Authentication, Authorization & Resource Controls Tests."""

    def test_unauthenticated_request_rejected(self):
        resp = client.post(
            f"/api/v1/research/experiments/{uuid4()}/overfitting-diagnostics",
            json={},
        )
        assert resp.status_code == 401

    def test_cross_tenant_isolation_enforced(self, auth_headers_user_a, auth_headers_user_b):
        # User A owns experiment
        exp_id = create_experiment_helper(USER_A_ID, "User A Secret Strategy")
        dates = [f"2023-01-{i:02d}" for i in range(1, 31)] + [f"2023-02-{i:02d}" for i in range(1, 21)]
        create_run_with_backtest_helper(USER_A_ID, exp_id, 1, dates, [0.001] * len(dates))
        create_run_with_backtest_helper(USER_A_ID, exp_id, 2, dates, [0.001] * len(dates))

        # User B attempts to access User A's experiment diagnostics -> 404 (prevents leakage)
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={},
            headers=auth_headers_user_b,
        )
        assert resp.status_code == 404

    def test_maximum_run_count_resource_limit(self, auth_headers_user_a):
        exp_id = create_experiment_helper(USER_A_ID, "Resource Limit Exp")
        # Request with 101 run IDs
        fake_run_ids = [str(uuid4()) for _ in range(101)]
        resp = client.post(
            f"/api/v1/research/experiments/{exp_id}/overfitting-diagnostics",
            json={"run_ids": fake_run_ids},
            headers=auth_headers_user_a,
        )
        assert resp.status_code == 422
        assert "Maximum number of candidate strategies" in resp.text
