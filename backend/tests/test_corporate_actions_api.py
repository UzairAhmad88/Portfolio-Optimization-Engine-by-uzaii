"""
Integration tests for Corporate Actions, Data Quality Audit, and Calendar APIs (Workstream 31.6).
"""

from datetime import date
import io
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.market_data import repository
from app.db.session import get_db_session


@pytest.fixture
def auth_client():
    client = TestClient(app)
    # Register/login user to obtain JWT
    email = "ca_tester@domain.com"
    pwd = "CaTestPassword123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "full_name": "CA Tester"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client


def test_calendar_sessions_api(auth_client):
    resp = auth_client.get(
        "/api/v1/market-data/calendars/US/sessions",
        params={"start_date": "2024-06-10", "end_date": "2024-06-21"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["market"] == "US"
    assert "2024-06-19" not in data["sessions"]  # Juneteenth holiday
    assert any(h["date"] == "2024-06-19" for h in data["holidays"])


def test_corporate_actions_lifecycle_api(auth_client):
    # 1. Register corporate actions
    payload = [
        {
            "asset_id": "TEST_API:US",
            "ticker": "TEST_API",
            "market": "US",
            "event_type": "stock_split",
            "effective_date": "2024-07-01",
            "announcement_date": "2024-06-15",
            "value": 2.0,
            "currency": "USD",
            "source": "api_test",
            "is_point_in_time_verified": True,
        }
    ]
    create_resp = auth_client.post("/api/v1/market-data/corporate-actions", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert len(created) == 1
    assert created[0]["ticker"] == "TEST_API"
    assert created[0]["value"] == 2.0

    # 2. Query corporate actions with PIT cutoff before announcement
    query_before = auth_client.get(
        "/api/v1/market-data/corporate-actions",
        params={
            "asset_id": "TEST_API:US",
            "as_of_date": "2024-06-01",
            "strict_pit": True,
        },
    )
    assert query_before.status_code == 200
    assert len(query_before.json()) == 0  # Future announcement excluded!

    # 3. Query corporate actions with PIT cutoff after announcement
    query_after = auth_client.get(
        "/api/v1/market-data/corporate-actions",
        params={
            "asset_id": "TEST_API:US",
            "as_of_date": "2024-06-20",
            "strict_pit": True,
        },
    )
    assert query_after.status_code == 200
    assert len(query_after.json()) == 1


def test_dataset_quality_audit_api(auth_client):
    # Upload sample CSV
    csv_content = (
        "date,ticker,market,close,currency\n"
        "2024-01-02,QA_TICKER,US,100.0,USD\n"
        "2024-01-03,QA_TICKER,US,102.0,USD\n"
        "2024-01-04,QA_TICKER,US,101.5,USD\n"
    )
    upload_resp = auth_client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("qa_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
    )
    assert upload_resp.status_code == 200
    dataset_id = upload_resp.json()["dataset_id"]

    # Run quality audit
    audit_resp = auth_client.post(f"/api/v1/market-data/datasets/{dataset_id}/quality-audit")
    assert audit_resp.status_code == 200
    report = audit_resp.json()
    assert report["is_valid"] is True
    assert "findings" in report
