from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_CSV = (
    b"date,ticker,market,close,currency,open,high,low,volume\n"
    b"2025-01-02,AAPL,US,150.00,USD,149.00,152.00,148.00,1000000\n"
)


def test_openapi_schema_contains_typed_response_models():
    schema = app.openapi()
    paths = schema["paths"]

    # Verify Health
    health_resp = paths["/api/v1/health"]["get"]["responses"]["200"]
    assert (
        health_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/HealthResponse"
    )

    # Verify Preview
    preview_resp = paths["/api/v1/market-data/preview"]["post"]["responses"]["200"]
    assert (
        preview_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ValidationReportResponse"
    )

    # Verify Uploads
    upload_resp = paths["/api/v1/market-data/uploads"]["post"]["responses"]["200"]
    assert (
        upload_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/DatasetMetadataResponse"
    )

    # Verify Query
    query_resp = paths["/api/v1/market-data/datasets/query"]["post"]["responses"]["200"]
    assert (
        query_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/DatasetQueryResponse"
    )

    # Verify Metadata
    meta_resp = paths["/api/v1/market-data/datasets/{dataset_id}"]["get"]["responses"][
        "200"
    ]
    assert (
        meta_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/DatasetMetadataResponse"
    )

    # Verify Assets Discovery
    assets_resp = paths["/api/v1/market-data/datasets/{dataset_id}/assets"]["get"][
        "responses"
    ]["200"]
    assert (
        assets_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/DatasetAssetsResponse"
    )

    # Verify Portfolio Validation
    port_val_resp = paths["/api/v1/portfolios/validate"]["post"]["responses"]["200"]
    assert (
        port_val_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/PortfolioValidationReport"
    )

    # Verify Portfolio Optimization
    opt_resp = paths["/api/v1/portfolios/optimize"]["post"]["responses"]["200"]
    assert (
        opt_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/OptimizationResponse"
    )

    # Verify Efficient Frontier
    frontier_resp = paths["/api/v1/portfolios/efficient-frontier"]["post"]["responses"]["200"]
    assert (
        frontier_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/EfficientFrontierResponse"
    )

    # Verify Portfolio Comparison
    compare_resp = paths["/api/v1/portfolios/compare"]["post"]["responses"]["200"]
    assert (
        compare_resp["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/PortfolioComparisonResponse"
    )


def test_preview_endpoint_invokes_threadpool():
    with patch(
        "app.api.v1.routes.run_in_threadpool",
        wraps=lambda f, *args, **kwargs: f(*args, **kwargs),
    ) as mock_pool:
        response = client.post(
            "/api/v1/market-data/preview",
            files={"file": ("prices.csv", VALID_CSV, "text/csv")},
        )
        assert response.status_code == 200
        assert mock_pool.called
        assert response.json()["valid_rows"] == 1


def test_upload_endpoint_invokes_threadpool():
    with patch(
        "app.api.v1.routes.run_in_threadpool",
        wraps=lambda f, *args, **kwargs: f(*args, **kwargs),
    ) as mock_pool:
        response = client.post(
            "/api/v1/market-data/uploads",
            files={"file": ("prices.csv", VALID_CSV, "text/csv")},
        )
        assert response.status_code == 200
        assert mock_pool.called
        assert "dataset_id" in response.json()


def test_upload_non_csv_extension_returns_415():
    response = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("prices.txt", VALID_CSV, "text/plain")},
    )
    assert response.status_code == 415
    assert "Upload a .csv file" in response.json()["detail"]


def test_upload_file_exceeding_10mb_returns_413():
    # 10 MB + 10 bytes
    oversized = b"a" * (10 * 1024 * 1024 + 10)
    response = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("huge.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413
    assert "10 MB upload limit" in response.json()["detail"]


def test_dataset_metadata_endpoint_retrieves_registered_data():
    upload = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("prices.csv", VALID_CSV, "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["dataset_id"]

    meta_resp = client.get(f"/api/v1/market-data/datasets/{dataset_id}")
    assert meta_resp.status_code == 200
    body = meta_resp.json()
    assert body["dataset_id"] == dataset_id
    assert body["filename"] == "prices.csv"
    assert body["valid_rows"] == 1
