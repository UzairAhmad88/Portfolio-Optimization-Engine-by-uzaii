import concurrent.futures
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market_data.service import (
    clear_dataset_registry,
    get_dataset_rows,
    query_dataset,
    register_csv_dataset,
)

client = TestClient(app)

SYNTHETIC_CSV_DATA = (
    b"date,ticker,market,close,currency\n"
    b"2025-01-02,AAPL,US,150.00,USD\n"
    b"2025-01-03,AAPL,US,152.00,USD\n"
    b"2025-01-06,AAPL,US,151.00,USD\n"
    b"2025-01-07,AAPL,US,153.50,USD\n"
    b"2025-01-08,AAPL,US,155.00,USD\n"
    b"2025-01-02,MSFT,US,300.00,USD\n"
    b"2025-01-03,MSFT,US,302.00,USD\n"
    b"2025-01-06,MSFT,US,301.00,USD\n"
    b"2025-01-07,MSFT,US,304.00,USD\n"
    b"2025-01-08,MSFT,US,305.50,USD\n"
    b"2025-01-02,GOOG,US,140.00,USD\n"
    b"2025-01-03,GOOG,US,141.00,USD\n"
    b"2025-01-06,GOOG,US,139.50,USD\n"
    b"2025-01-07,GOOG,US,142.00,USD\n"
    b"2025-01-08,GOOG,US,143.00,USD\n"
)

MIXED_CURRENCY_CSV = (
    b"date,ticker,market,close,currency\n"
    b"2025-01-02,AAPL,US,150.00,USD\n"
    b"2025-01-03,AAPL,US,152.00,USD\n"
    b"2025-01-02,LUCK,PSX,850.00,PKR\n"
    b"2025-01-03,LUCK,PSX,855.00,PKR\n"
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_dataset_registry()
    yield
    clear_dataset_registry()


def test_end_to_end_successful_lifecycle():
    """
    Verifies complete end-to-end research workflow across all public API boundaries:
    Preview -> Upload -> Asset Discovery -> Portfolio Validation ->
    Optimization -> Efficient Frontier -> Multi-Portfolio Comparison.
    """
    # 1. Preview CSV
    prev_resp = client.post(
        "/api/v1/market-data/preview",
        files={"file": ("tech.csv", SYNTHETIC_CSV_DATA, "text/csv")},
    )
    assert prev_resp.status_code == 200
    prev_body = prev_resp.json()
    assert prev_body["valid_rows"] == 15
    assert prev_body["rejected_rows"] == 0
    assert len(prev_body["errors"]) == 0

    # 2. Upload and Register Dataset
    upload_resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech.csv", SYNTHETIC_CSV_DATA, "text/csv")},
    )
    assert upload_resp.status_code == 200
    meta = upload_resp.json()
    dataset_id = meta["dataset_id"]
    assert meta["valid_rows"] == 15
    assert meta["filename"] == "tech.csv"

    # 3. Discover Available Assets
    assets_resp = client.get(f"/api/v1/market-data/datasets/{dataset_id}/assets")
    assert assets_resp.status_code == 200
    assets_body = assets_resp.json()
    assert assets_body["asset_count"] == 3
    tickers = [a["ticker"] for a in assets_body["assets"]]
    assert sorted(tickers) == ["AAPL", "GOOG", "MSFT"]
    assert all(a["currency"] == "USD" for a in assets_body["assets"])

    # 4. Validate Portfolio Definition
    port_def = {
        "name": "Core Tech Allocation",
        "dataset_id": dataset_id,
        "assets": ["AAPL", "MSFT", "GOOG"],
        "constraints": {
            "default_min_weight": 0.05,
            "default_max_weight": 0.80,
            "target_total_weight": 1.0,
            "allow_short": False,
        },
    }
    val_resp = client.post("/api/v1/portfolios/validate", json=port_def)
    assert val_resp.status_code == 200
    val_body = val_resp.json()
    assert val_body["is_valid"] is True
    assert val_body["date_coverage"]["common_observation_count"] == 5
    assert val_body["feasibility"]["is_feasible"] is True

    # 5. Optimize Minimum Variance Portfolio
    opt_req = {
        "portfolio": port_def,
        "objective": "min_variance",
        "annualized": True,
        "periods_per_year": 252,
    }
    opt_resp = client.post("/api/v1/portfolios/optimize", json=opt_req)
    assert opt_resp.status_code == 200
    opt_body = opt_resp.json()
    assert opt_body["is_success"] is True
    assert opt_body["currency"] == "USD"
    assert opt_body["dataset_id"] == dataset_id
    assert pytest.approx(sum(opt_body["weights"].values()), abs=1e-5) == 1.0
    assert opt_body["metrics"]["is_long_only"] is True
    assert opt_body["solver_diagnostics"]["converged"] is True

    # 6. Generate Efficient Frontier
    ef_req = {
        "portfolio": port_def,
        "target_count": 5,
        "annualized": True,
        "periods_per_year": 252,
    }
    ef_resp = client.post("/api/v1/portfolios/efficient-frontier", json=ef_req)
    assert ef_resp.status_code == 200
    ef_body = ef_resp.json()
    assert ef_body["is_success"] is True
    assert ef_body["currency"] == "USD"
    assert ef_body["requested_count"] == 5
    assert len(ef_body["points"]) == 5
    assert ef_body["global_minimum_variance"] is not None

    # 7. Compare Portfolios on Identical Data
    comp_req = {
        "portfolio": port_def,
        "include_gmv": True,
        "include_max_sharpe": True,
        "include_equal_weight": True,
        "custom_portfolios": {
            "Custom 50-30-20": {
                "AAPL:US": 0.50,
                "MSFT:US": 0.30,
                "GOOG:US": 0.20,
            }
        },
        "annualized": True,
        "periods_per_year": 252,
    }
    comp_resp = client.post("/api/v1/portfolios/compare", json=comp_req)
    assert comp_resp.status_code == 200
    comp_body = comp_resp.json()
    assert comp_body["is_success"] is True
    assert comp_body["currency"] == "USD"
    assert len(comp_body["portfolios"]) == 4
    names = [p["name"] for p in comp_body["portfolios"]]
    assert "Global Minimum Variance" in names
    assert "Equal Weight" in names
    assert "Custom 50-30-20" in names
    # Verify provenance and observation consistency
    assert comp_body["date_coverage"]["common_observation_count"] == 5


def test_dataset_row_immutability_defensive_copies():
    """
    Verifies that caller mutations of query results or dataset rows
    cannot mutate the stored in-memory dataset bars or cached entries.
    """
    meta = register_csv_dataset(SYNTHETIC_CSV_DATA, "data.csv")
    dataset_id = meta["dataset_id"]

    # 1. Mutating get_dataset_rows result
    rows1 = get_dataset_rows(dataset_id)
    original_close = rows1[0]["close"]
    rows1[0]["close"] = 9999999.0
    rows1[0]["ticker"] = "CORRUPTED"

    rows2 = get_dataset_rows(dataset_id)
    assert rows2[0]["close"] == original_close
    assert rows2[0]["ticker"] == "AAPL"

    # 2. Mutating query_dataset result
    from datetime import date

    q1 = query_dataset(
        dataset_id=dataset_id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    assert q1["data"][0]["close"] == original_close
    q1["data"][0]["close"] = 8888888.0

    # Query again (should hit cache or registry and still be unmutated)
    q2 = query_dataset(
        dataset_id=dataset_id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    assert q2["data"][0]["close"] == original_close


def test_multithreaded_concurrency_and_race_safety():
    """
    Verifies that concurrent reads, queries, validations, optimizations,
    and registrations execute safely across multiple threads without deadlocks or race conditions.
    """
    meta = register_csv_dataset(SYNTHETIC_CSV_DATA, "concurrent.csv")
    dataset_id = meta["dataset_id"]

    def run_query():
        resp = client.post(
            "/api/v1/market-data/datasets/query",
            json={
                "dataset_id": dataset_id,
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "tickers": ["AAPL", "MSFT"],
            },
        )
        assert resp.status_code == 200
        return resp.json()["row_count"]

    def run_assets():
        resp = client.get(f"/api/v1/market-data/datasets/{dataset_id}/assets")
        assert resp.status_code == 200
        return resp.json()["asset_count"]

    def run_optimization():
        payload = {
            "portfolio": {
                "name": "Concurrent Portfolio",
                "dataset_id": dataset_id,
                "assets": ["AAPL", "MSFT"],
            },
            "objective": "min_variance",
        }
        resp = client.post("/api/v1/portfolios/optimize", json=payload)
        assert resp.status_code == 200
        return resp.json()["is_success"]

    def run_registration():
        resp = client.post(
            "/api/v1/market-data/uploads",
            files={"file": ("tech2.csv", SYNTHETIC_CSV_DATA, "text/csv")},
        )
        assert resp.status_code == 200
        return resp.json()["dataset_id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for _ in range(5):
            futures.append(executor.submit(run_query))
            futures.append(executor.submit(run_assets))
            futures.append(executor.submit(run_optimization))
        futures.append(executor.submit(run_registration))

        results = [f.result(timeout=10.0) for f in futures]
        assert len(results) == 16


def test_input_boundaries_and_security_limits():
    """
    Verifies input boundaries:
    - Excess assets rejected (> 100)
    - Excess periods per year (> 365) rejected
    - Path traversal in filenames sanitized
    """
    meta = register_csv_dataset(SYNTHETIC_CSV_DATA, "bounds.csv")
    dataset_id = meta["dataset_id"]

    # 1. More than 100 assets
    excess_assets = [f"ASSET_{i}" for i in range(101)]
    resp = client.post(
        "/api/v1/portfolios/validate",
        json={
            "name": "Too Many Assets",
            "dataset_id": dataset_id,
            "assets": excess_assets,
        },
    )
    assert resp.status_code == 422
    assert "at most 100 items" in str(resp.json())

    # 2. Periods per year > 365 in OptimizationRequest
    resp_opt = client.post(
        "/api/v1/portfolios/optimize",
        json={
            "portfolio": {
                "name": "High Periods",
                "dataset_id": dataset_id,
                "assets": ["AAPL", "MSFT"],
            },
            "periods_per_year": 500,  # exceeds 365
        },
    )
    assert resp_opt.status_code == 422
    assert "less than or equal to 365" in str(resp_opt.json())

    # 3. Path traversal in upload filename sanitized
    traversal_resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("../../etc/shadow.csv", SYNTHETIC_CSV_DATA, "text/csv")},
    )
    assert traversal_resp.status_code == 200
    assert traversal_resp.json()["filename"] == "shadow.csv"


def test_cross_market_currency_isolation_safeguard():
    """
    Verifies that multi-currency portfolios (e.g. USD + PKR) cannot be aggregated
    or optimized without explicit FX conversion.
    """
    meta = register_csv_dataset(MIXED_CURRENCY_CSV, "mixed.csv")
    dataset_id = meta["dataset_id"]

    # Validate portfolio
    val_resp = client.post(
        "/api/v1/portfolios/validate",
        json={
            "name": "Cross Currency",
            "dataset_id": dataset_id,
            "assets": ["AAPL", "LUCK"],
        },
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is False
    assert val_data["currency_policy"]["is_multi_currency"] is True
    assert any("multiple currencies" in err for err in val_data["errors"])

    # Optimize fails with 422
    opt_resp = client.post(
        "/api/v1/portfolios/optimize",
        json={
            "portfolio": {
                "name": "Cross Currency",
                "dataset_id": dataset_id,
                "assets": ["AAPL", "LUCK"],
            },
            "objective": "min_variance",
        },
    )
    assert opt_resp.status_code == 422
    opt_data = opt_resp.json()["detail"]
    assert opt_data["is_success"] is False
    assert any("multiple currencies" in err for err in opt_data["errors"])


def test_numerical_error_propagation_no_fabrication():
    """
    Verifies that numerical errors and infeasibilities return domain diagnostics
    without fabricating fallback weights.
    """
    meta = register_csv_dataset(SYNTHETIC_CSV_DATA, "fail_prop.csv")
    dataset_id = meta["dataset_id"]

    # Infeasible constraints: min weights 0.60 each for 2 assets (sum 1.20 > 1.0)
    opt_resp = client.post(
        "/api/v1/portfolios/optimize",
        json={
            "portfolio": {
                "name": "Infeasible",
                "dataset_id": dataset_id,
                "assets": ["AAPL", "MSFT"],
                "constraints": {
                    "default_min_weight": 0.60,
                    "target_total_weight": 1.0,
                },
            },
            "objective": "min_variance",
        },
    )
    assert opt_resp.status_code == 422
    opt_data = opt_resp.json()["detail"]
    assert opt_data["is_success"] is False
    assert opt_data["weights"] == {}
    assert opt_data["metrics"] is None

    # Missing dataset ID
    missing_resp = client.post(
        "/api/v1/portfolios/optimize",
        json={
            "portfolio": {
                "name": "Missing",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
                "assets": ["AAPL", "MSFT"],
            },
        },
    )
    assert missing_resp.status_code == 404
    assert "not found" in missing_resp.json()["detail"].lower()


def test_global_unhandled_exception_does_not_leak_internals():
    """
    Verifies that unhandled internal server exceptions return HTTP 500
    without leaking internal code paths, stack traces, or secrets.
    """
    client_no_raise = TestClient(app, raise_server_exceptions=False)
    with patch(
        "app.api.v1.routes.validate_csv",
        side_effect=RuntimeError("Internal database crash at /secret/db/path"),
    ):
        resp = client_no_raise.post(
            "/api/v1/market-data/preview",
            files={"file": ("tech.csv", SYNTHETIC_CSV_DATA, "text/csv")},
        )
        assert resp.status_code == 500
        assert "/secret/db/path" not in resp.text
        assert resp.json()["detail"] == "An unexpected internal server error occurred."
