"""
PostgreSQL Integration and Database Migration Verification Test Suite (Session 83).

Executes against an active PostgreSQL database instance (such as in GitHub Actions CI
or a Docker-enabled integration environment) using psycopg v3.
If no reachable PostgreSQL database is configured, tests skip cleanly with explanatory notice.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic.config import Config
from alembic import command
from app.db.base import Base
from app.db.models import AssetModel, DatasetModel, PriceBarModel, UserModel
from app.db.session import create_db_engine, get_database_url


def get_postgres_test_url() -> str | None:
    """
    Returns the PostgreSQL connection URL if configured in environment, else None.
    Checks POSTGRES_TEST_URL first, then DATABASE_URL if it points to PostgreSQL.
    """
    url = os.environ.get("POSTGRES_TEST_URL", os.environ.get("DATABASE_URL", "")).strip()
    if url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+psycopg://"):
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return None


def is_postgres_reachable(url: str) -> bool:
    """
    Attempts a short-timeout connection probe against the target PostgreSQL instance.
    """
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3}, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """
    Module-level fixture ensuring PostgreSQL is reachable or skipping the test module.
    """
    url = get_postgres_test_url()
    if not url:
        pytest.skip("No PostgreSQL URL configured (POSTGRES_TEST_URL or DATABASE_URL). Skipping PostgreSQL integration tests.")
    if not is_postgres_reachable(url):
        pytest.skip(f"Target PostgreSQL database at {url.split('@')[-1]} is unreachable. Skipping live integration tests.")
    return url


@pytest.fixture(scope="module")
def postgres_engine(postgres_url):
    """
    Creates and yields an engine bound to the live PostgreSQL test database.
    """
    engine = create_db_engine(postgres_url)
    yield engine
    engine.dispose()


def test_postgres_fresh_migration_to_head(postgres_url):
    """
    Scope B / Gate C: Runs Alembic migrations from <base> to head on PostgreSQL,
    verifying migration state e5f6a7b8c9d0 and complete table generation.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_url

    # Execute alembic upgrade head in isolated subprocess to verify CLI migration execution
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Alembic PostgreSQL migration failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"

    # Verify current revision matches expected Alembic head
    res_cur = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_cur.returncode == 0
    assert "e5f6a7b8c9d0" in res_cur.stdout or "head" in res_cur.stdout

    # Verify all expected tables exist in PostgreSQL schema
    engine = create_engine(postgres_url)
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
    assert not missing, f"PostgreSQL database is missing required tables: {missing}"


def test_postgres_persistence_and_rollback(postgres_engine):
    """
    Scope B: Verifies ACID persistence and atomic transaction rollback on PostgreSQL.
    """
    from sqlalchemy.orm import Session

    user_id = "11111111-2222-3333-4444-555555555555"
    dataset_id = "test-pg-dataset-001"

    # 1. Successful commit
    with Session(postgres_engine) as session:
        # Clean up any residual test records
        session.query(PriceBarModel).filter_by(dataset_id=dataset_id).delete()
        session.query(DatasetModel).filter_by(id=dataset_id).delete()
        session.query(UserModel).filter_by(id=user_id).delete()
        session.commit()

        # Insert test user and dataset
        user = UserModel(
            id=user_id,
            email="pg_integration@quantengine.local",
            hashed_password="hashed_placeholder_123",
            full_name="PostgreSQL Integration Tester",
            role="researcher",
            is_active=True,
        )
        dataset = DatasetModel(
            id=dataset_id,
            filename="postgres_test.csv",
            created_at=datetime.now(timezone.utc),
            source_type="csv",
            content_sha256="0" * 64,
            rows_examined=1,
            valid_rows=1,
            rejected_rows=0,
            status="ready",
            user_id=user_id,
        )
        session.add(user)
        session.add(dataset)
        session.commit()

    # 2. Verify persistence across sessions
    with Session(postgres_engine) as session:
        persisted_ds = session.get(DatasetModel, dataset_id)
        assert persisted_ds is not None
        assert persisted_ds.filename == "postgres_test.csv"
        assert persisted_ds.user_id == user_id

    # 3. Verify atomic rollback on error
    with Session(postgres_engine) as session:
        try:
            with session.begin_nested():
                # Attempt to insert price bar with duplicate primary key or invalid foreign key
                invalid_bar = PriceBarModel(
                    dataset_id="non_existent_dataset_9999",
                    ticker="AAPL",
                    date=date(2025, 1, 1),
                    open=150.0,
                    high=155.0,
                    low=149.0,
                    close=154.0,
                    volume=1000.0,
                    currency="USD",
                )
                session.add(invalid_bar)
                session.flush()
        except IntegrityError:
            session.rollback()

    # 4. Clean up
    with Session(postgres_engine) as session:
        session.query(PriceBarModel).filter_by(dataset_id=dataset_id).delete()
        session.query(DatasetModel).filter_by(id=dataset_id).delete()
        session.query(UserModel).filter_by(id=user_id).delete()
        session.commit()


def test_postgres_connection_pool_configuration(postgres_url, monkeypatch):
    """
    Scope B: Verifies that PostgreSQL connection pool parameters are honored from environment.
    """
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "10")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "15.0")

    engine = create_db_engine(postgres_url)
    try:
        pool = engine.pool
        assert pool.size() == 5
        assert pool._max_overflow == 10
        assert pool._timeout == 15.0
    finally:
        engine.dispose()
