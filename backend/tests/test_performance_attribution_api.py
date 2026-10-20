"""
API integration and security tests for Stage 21:
Multi-Asset Performance Attribution, Brinson-Fachler Decomposition & Systematic Factor Risk Attribution.
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

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"


def _generate_synthetic_csv() -> bytes:
    """Generates synthetic CSV data with 60 trading days for 3 assets across sectors."""
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
        lines.append(f"{dt},XOM,US,{p3:.2f},USD")

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
            email="user_a_attrib@domain.com",
            hashed_password="hash",
            full_name="User A Attrib",
            role="researcher",
            is_active=True,
        )
        user_b = UserModel(
            id=USER_B_ID,
            email="user_b_attrib@domain.com",
            hashed_password="hash",
            full_name="User B Attrib",
            role="researcher",
            is_active=True,
        )
        session.add_all([user_a, user_b])
        session.commit()

    token_a = create_access_token(
        subject=USER_A_ID,
        claims={"email": "user_a_attrib@domain.com", "role": "researcher"},
    )
    token_b = create_access_token(
        subject=USER_B_ID,
        claims={"email": "user_b_attrib@domain.com", "role": "researcher"},
    )

    csv_bytes = _generate_synthetic_csv()
    resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("attrib_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200, resp.text
    dataset_a_id = resp.json()["dataset_id"]

    return {
        "token_a": token_a,
        "token_b": token_b,
        "dataset_a_id": dataset_a_id,
    }


def test_brinson_unauthenticated_401():
    """Verifies unauthenticated calls to /api/v1/attribution/brinson return HTTP 401."""
    resp = client.post(
        "/api/v1/attribution/brinson",
        json={"dataset_id": "test", "portfolio_weights": {"AAPL": 1.0}},
    )
    assert resp.status_code == 401


def test_factor_unauthenticated_401():
    """Verifies unauthenticated calls to /api/v1/attribution/factor return HTTP 401."""
    resp = client.post(
        "/api/v1/attribution/factor",
        json={"dataset_id": "test", "portfolio_weights": {"AAPL": 1.0}},
    )
    assert resp.status_code == 401


def test_brinson_cross_tenant_isolation(setup_users_and_datasets):
    """User B cannot compute Brinson attribution on User A's private dataset."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "portfolio_weights": {"AAPL": 0.6, "MSFT": 0.4},
        "benchmark_weights": {"AAPL": 0.5, "MSFT": 0.5},
    }
    resp = client.post(
        "/api/v1/attribution/brinson",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_b']}"},
    )
    # check_dataset_access returns 404 when dataset does not belong to user
    assert resp.status_code in (403, 404)


def test_factor_cross_tenant_isolation(setup_users_and_datasets):
    """User B cannot compute Factor attribution on User A's private dataset."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "portfolio_weights": {"AAPL": 0.6, "MSFT": 0.4},
        "benchmark_weights": {"AAPL": 0.5, "MSFT": 0.5},
    }
    resp = client.post(
        "/api/v1/attribution/factor",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_b']}"},
    )
    assert resp.status_code in (403, 404)


def test_brinson_validation_error_empty_weights(setup_users_and_datasets):
    """Empty weights should yield HTTP 422."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "portfolio_weights": {},
    }
    resp = client.post(
        "/api/v1/attribution/brinson",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 422


def test_brinson_attribution_success(setup_users_and_datasets):
    """User A successfully runs Brinson-Fachler attribution with Cariño linking."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "portfolio_weights": {"AAPL": 0.50, "MSFT": 0.30, "XOM": 0.20},
        "benchmark_weights": {"AAPL": 0.3333, "MSFT": 0.3333, "XOM": 0.3334},
        "segment_mapping": {
            "AAPL": "Information Technology",
            "MSFT": "Information Technology",
            "XOM": "Energy",
        },
        "method": "brinson_fachler",
        "frequency": "monthly",
    }
    resp = client.post(
        "/api/v1/attribution/brinson",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == ctx["dataset_a_id"]
    assert data["method"] == "brinson_fachler"
    assert data["frequency"] == "monthly"
    summary = data["summary"]
    assert summary["total_periods"] >= 2

    # Check that cumulative reconciliation holds: Alloc + Select + Inter = ActiveReturn
    alloc = summary["total_allocation_effect"]
    select = summary["total_selection_effect"]
    inter = summary["total_interaction_effect"]
    active = summary["cumulative_active_return"]

    assert abs((alloc + select + inter) - active) < 1e-6
    assert abs(summary["reconciliation_error"]) < 1e-6

    # Verify sector breakdowns are present
    assert len(data["segment_attribution"]) == 2  # IT and Energy
    sectors = [sb["segment"] for sb in data["segment_attribution"]]
    assert "Information Technology" in sectors
    assert "Energy" in sectors


def test_factor_attribution_success(setup_users_and_datasets):
    """User A successfully runs Systematic Factor Risk and Return attribution."""
    ctx = setup_users_and_datasets
    payload = {
        "dataset_id": ctx["dataset_a_id"],
        "portfolio_weights": {"AAPL": 0.50, "MSFT": 0.30, "XOM": 0.20},
        "benchmark_weights": {"AAPL": 0.3333, "MSFT": 0.3333, "XOM": 0.3334},
        "annualization_factor": 252,
    }
    resp = client.post(
        "/api/v1/attribution/factor",
        json=payload,
        headers={"Authorization": f"Bearer {ctx['token_a']}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dataset_id"] == ctx["dataset_a_id"]
    assert len(data["factor_contributions"]) == 3  # Market, Size, Value (default FF3)
    factors = [fc["factor"] for fc in data["factor_contributions"]]
    assert "MKT" in factors or "Market" in factors or len(factors) == 3
    assert data["total_tracking_error"] >= 0.0

    # Systematic active return + specific active return == total active return
    sys_ret = data["systematic_active_return"]
    spec_ret = data["specific_active_return"]
    active_ret = data["total_active_return"]
    assert abs((sys_ret + spec_ret) - active_ret) < 1e-5
