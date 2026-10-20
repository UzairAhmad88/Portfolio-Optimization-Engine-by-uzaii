from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_CSV = b"date,ticker,market,close,currency,volume\n2025-01-02,AAPL,US,100,USD,1000\n2025-01-03,AAPL,US,101,USD,1200\n"
INVALID_CSV = b"date,ticker,market,close,currency\n2025-01-02,AAPL,US,-5,USD\n"


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_preview_valid_csv():
    response = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("prices.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["valid_rows"] == 2


def test_upload_and_query_inclusive_dates():
    upload = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("prices.csv", VALID_CSV, "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["dataset_id"]

    query = client.post(
        "/api/v1/market-data/datasets/query",
        json={
            "dataset_id": dataset_id,
            "start_date": "2025-01-02",
            "end_date": "2025-01-02",
            "tickers": ["AAPL"],
            "market": "US",
        },
    )
    assert query.status_code == 200
    assert query.json()["row_count"] == 1


def test_invalid_price_is_reported_and_excluded():
    response = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("bad.csv", INVALID_CSV, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid_rows"] == 0
    assert any(
        "positive" in reason for issue in body["errors"] for reason in issue["reasons"]
    )


def test_missing_required_column_rejected():
    response = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("bad.csv", b"date,ticker\n2025-01-01,AAPL\n", "text/csv")},
    )
    assert response.status_code == 400


def test_preview_and_query_with_sparse_optional_columns():
    csv_data = (
        b"date,ticker,market,close,currency,adjusted_close,volume\n"
        b"2025-01-02,AAPL,US,240.00,USD,240.00,1000000\n"
        b"2025-01-03,AAPL,US,245.00,USD,,1200000\n"
    )
    preview = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("prices.csv", csv_data, "text/csv")},
    )
    assert preview.status_code == 200
    preview_data = preview.json()["valid_data"]
    assert len(preview_data) == 2
    assert preview_data[0]["adjusted_close"] == 240.0
    assert preview_data[1]["adjusted_close"] is None

    upload = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("prices.csv", csv_data, "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["dataset_id"]

    query = client.post(
        "/api/v1/market-data/datasets/query",
        json={
            "dataset_id": dataset_id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-05",
        },
    )
    assert query.status_code == 200
    query_rows = query.json()["data"]
    assert len(query_rows) == 2
    assert query_rows[1]["adjusted_close"] is None


def test_query_missing_dataset_returns_404():
    response = client.post(
        "/api/v1/market-data/datasets/query",
        json={
            "dataset_id": "non-existent-id",
            "start_date": "2025-01-01",
            "end_date": "2025-01-05",
        },
    )
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_query_invalid_date_range_returns_422():
    response = client.post(
        "/api/v1/market-data/datasets/query",
        json={
            "dataset_id": "any-id",
            "start_date": "2025-01-10",
            "end_date": "2025-01-01",
        },
    )
    assert response.status_code == 422
    assert "start_date must be on or before end_date" in response.json()["detail"]
