import concurrent.futures
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db_session, init_db
from app.db.models import DatasetModel, AssetModel, PriceBarModel
from app.market_data.repository import (
    create_dataset,
    get_dataset_by_id,
    list_datasets,
    get_assets_by_dataset,
    query_price_bars,
    find_dataset_by_sha256,
    clear_all_datasets,
)
from app.market_data.service import (
    register_csv_dataset,
    get_dataset_metadata,
    query_dataset,
    clear_dataset_registry,
    _DATASETS,
    DatasetNotFoundError,
)
from app.portfolio.service import get_dataset_assets
from app.main import app

client = TestClient(app)

SAMPLE_CSV_VALID = (
    b"date,ticker,market,close,currency,open,high,low,volume\n"
    b"2025-01-02,AAPL,US,150.0,USD,149.0,151.0,148.5,1000\n"
    b"2025-01-03,AAPL,US,152.5,USD,150.5,153.0,150.0,1200\n"
    b"2025-01-02,MSFT,US,300.0,USD,298.0,302.0,297.0,800\n"
    b"2025-01-03,MSFT,US,305.0,USD,301.0,306.0,300.0,950\n"
)

SAMPLE_CSV_ANOTHER = (
    b"date,ticker,market,close,currency\n"
    b"2025-01-02,GOOG,US,140.0,USD\n"
    b"2025-01-03,GOOG,US,142.0,USD\n"
)


@pytest.fixture(autouse=True)
def setup_database_clean():
    init_db()
    clear_dataset_registry()
    yield
    clear_dataset_registry()


def test_database_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "stage" in data


def test_dataset_registration_and_persistence():
    meta = register_csv_dataset(SAMPLE_CSV_VALID, "tech_stocks.csv")
    dataset_id = meta["dataset_id"]
    assert dataset_id is not None
    assert meta["filename"] == "tech_stocks.csv"
    assert meta["valid_rows"] == 4
    assert meta["rejected_rows"] == 0
    assert meta["content_sha256"] is not None

    # Verify directly in Database
    with get_db_session() as session:
        db_dataset = get_dataset_by_id(session, dataset_id)
        assert db_dataset is not None
        assert db_dataset.filename == "tech_stocks.csv"
        assert db_dataset.status == "completed"

        assets = get_assets_by_dataset(session, dataset_id)
        assert len(assets) == 2
        asset_tickers = {a.ticker for a in assets}
        assert asset_tickers == {"AAPL", "MSFT"}

        bars = query_price_bars(session, dataset_id)
        assert len(bars) == 4


def test_restart_survivability_with_cleared_cache():
    """Verify that after backend process restart (cache wiped), data is reliably fetched from DB."""
    meta = register_csv_dataset(SAMPLE_CSV_VALID, "tech_stocks.csv")
    dataset_id = meta["dataset_id"]

    # Emulate backend restart by forcefully wiping in-memory cache
    _DATASETS.clear()
    assert len(_DATASETS) == 0

    # Retrieve dataset metadata, assets, and historical query - should re-populate and succeed from DB
    reloaded_meta = get_dataset_metadata(dataset_id)
    assert reloaded_meta["dataset_id"] == dataset_id
    assert reloaded_meta["filename"] == "tech_stocks.csv"
    assert reloaded_meta["valid_rows"] == 4

    assets_res = get_dataset_assets(dataset_id)
    assert len(assets_res) == 2

    query_res = query_dataset(
        dataset_id=dataset_id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 5),
        tickers=["AAPL"],
        market="US",
    )
    assert query_res["row_count"] == 2
    assert all(r["ticker"] == "AAPL" for r in query_res["data"])


def test_sha256_deduplication_policy():
    """Identical CSV upload should resolve to the existing dataset without duplicating rows."""
    meta1 = register_csv_dataset(SAMPLE_CSV_VALID, "upload_1.csv")
    meta2 = register_csv_dataset(SAMPLE_CSV_VALID, "upload_2_duplicate.csv")

    assert meta1["dataset_id"] == meta2["dataset_id"]
    assert meta1["content_sha256"] == meta2["content_sha256"]

    # Verify that in database, only 1 dataset record exists with that hash
    with get_db_session() as session:
        matching = session.query(DatasetModel).filter_by(content_sha256=meta1["content_sha256"]).all()
        assert len(matching) == 1

        bars = query_price_bars(session, meta1["dataset_id"])
        assert len(bars) == 4  # Exactly 4 bars, not 8


def test_atomic_rollback_on_failed_registration(monkeypatch):
    """A failed registration must not leave partial datasets or orphan price bars."""
    def fail_flush(*args, **kwargs):
        raise RuntimeError("Simulated DB transaction failure during registration")

    with monkeypatch.context() as m:
        m.setattr("app.market_data.repository.Session.flush", fail_flush)
        with pytest.raises(RuntimeError):
            register_csv_dataset(SAMPLE_CSV_VALID, "failing.csv")

    with get_db_session() as session:
        datasets = session.query(DatasetModel).all()
        assert len(datasets) == 0
        bars = session.query(PriceBarModel).all()
        assert len(bars) == 0


def test_dataset_listing_api():
    """GET /api/v1/market-data/datasets returns all persistently registered datasets."""
    # Initially empty
    resp = client.get("/api/v1/market-data/datasets")
    assert resp.status_code == 200
    assert resp.json() == []

    # Upload two distinct datasets
    res1 = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("tech.csv", SAMPLE_CSV_VALID, "text/csv")},
    )
    assert res1.status_code == 200
    id1 = res1.json()["dataset_id"]

    res2 = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("goog.csv", SAMPLE_CSV_ANOTHER, "text/csv")},
    )
    assert res2.status_code == 200
    id2 = res2.json()["dataset_id"]

    # Verify listing contains both
    list_resp = client.get("/api/v1/market-data/datasets")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 2
    listed_ids = {d["dataset_id"] for d in items}
    assert id1 in listed_ids
    assert id2 in listed_ids


def test_cascade_delete_integrity():
    """Deleting a dataset removes associated assets and price bars without orphan rows."""
    meta = register_csv_dataset(SAMPLE_CSV_VALID, "cascade_test.csv")
    dataset_id = meta["dataset_id"]

    with get_db_session() as session:
        ds = get_dataset_by_id(session, dataset_id)
        assert ds is not None
        session.delete(ds)
        session.commit()

    with get_db_session() as session:
        assert get_dataset_by_id(session, dataset_id) is None
        remaining_assets = session.query(AssetModel).filter_by(dataset_id=dataset_id).all()
        assert len(remaining_assets) == 0
        remaining_bars = session.query(PriceBarModel).filter_by(dataset_id=dataset_id).all()
        assert len(remaining_bars) == 0


def test_concurrent_dataset_queries():
    """Multiple concurrent queries against the same persisted dataset execute safely."""
    meta = register_csv_dataset(SAMPLE_CSV_VALID, "concurrent.csv")
    dataset_id = meta["dataset_id"]

    def run_query(i):
        return query_dataset(
            dataset_id=dataset_id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            tickers=["AAPL"],
            market="US",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_query, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10
    for res in results:
        assert res["row_count"] == 2
        assert res["data"][0]["ticker"] == "AAPL"


def test_alembic_fresh_database_migration_to_head():
    """
    Regression test for DEF-82-01:
    Verifies that a fresh database can be migrated from <base> to Alembic head without
    duplicate table collisions or pre-empted DDL from module-level imports.
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile
    from sqlalchemy import create_engine, inspect

    temp_dir = tempfile.mkdtemp(prefix="quant_alembic_test_")
    try:
        test_db = os.path.join(temp_dir, "migrated.db").replace("\\", "/")
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{test_db}"

        # Execute alembic upgrade head in isolated subprocess
        res = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Alembic upgrade head failed: {res.stderr}\n{res.stdout}"

        # Verify current revision is head
        res_cur = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert res_cur.returncode == 0
        assert "e5f6a7b8c9d0" in res_cur.stdout or "head" in res_cur.stdout

        # Verify all essential tables are created
        engine = create_engine(f"sqlite:///{test_db}")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        required_tables = {
            "alembic_version",
            "users",
            "datasets",
            "dataset_assets",
            "price_bars",
            "backtest_runs",
            "scenario_runs",
            "risk_simulation_runs",
            "performance_reports",
            "research_experiments",
            "research_experiment_runs",
            "corporate_actions",
            "dataset_snapshots",
        }
        missing = required_tables - tables
        assert not missing, f"Migrated database is missing expected tables: {missing}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
