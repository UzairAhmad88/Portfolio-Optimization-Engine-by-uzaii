"""
Database engine configuration, connection pooling, and session management.
Supports PostgreSQL (production target via psycopg) and SQLite (testing and fallback).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.db.models  # noqa: F401

DEFAULT_DB_URL = "sqlite:///./quant_portfolio.db"

# Blacklist of known default or example database passwords
KNOWN_INSECURE_DB_PASSWORDS: frozenset[str] = frozenset([
    "quant_password",
    "quant_password_change_in_production",
    "quant_ci_test_password_not_for_production",
    "password",
    "postgres",
    "admin",
    "root",
    "changeme",
    "change_me",
    "123456",
    "secret",
    "dev_password",
    "test_password",
    "qwerty",
])


def get_database_url() -> str:
    """
    Extracts and normalizes the database URL from the environment.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL).strip()
    if url.startswith("postgres://"):
        # Normalize legacy Heroku/AWS style postgres:// to standard postgresql+psycopg://
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        # Use psycopg v3 driver if not explicitly specified
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def validate_database_configuration(db_url: str | None = None) -> None:
    """
    Validates PostgreSQL database connection and credentials for production environments.

    Security & Fail-Closed Rules:
    - Non-Production Mode (APP_ENV != production):
      Permits SQLite fallback and local development credentials.
    - Production Mode (APP_ENV=production|prod):
      1. DATABASE_URL is mandatory.
      2. DATABASE_URL must specify a PostgreSQL engine (SQLite is rejected).
      3. PostgreSQL password is mandatory (extracted from URL or POSTGRES_PASSWORD).
      4. PostgreSQL password cannot be empty or whitespace-only.
      5. PostgreSQL password cannot match known insecure defaults or placeholder strings.
      6. PostgreSQL password must be at least 8 characters in length.
    """
    from app.auth.security import is_production_environment
    if not is_production_environment():
        return

    url_str = (db_url or os.environ.get("DATABASE_URL", "")).strip()

    if not url_str:
        raise RuntimeError(
            "Production configuration error: DATABASE_URL environment variable is mandatory when APP_ENV=production."
        )

    if url_str.startswith("sqlite"):
        raise RuntimeError(
            "Production configuration error: PostgreSQL is mandatory in production; SQLite cannot be used when APP_ENV=production."
        )

    if not (url_str.startswith("postgresql://") or url_str.startswith("postgresql+") or url_str.startswith("postgres://")):
        raise RuntimeError(
            "Production configuration error: DATABASE_URL must specify a valid PostgreSQL connection in production."
        )

    from sqlalchemy.engine import make_url
    try:
        parsed = make_url(url_str)
        password = parsed.password
    except Exception as exc:
        raise RuntimeError(
            f"Production configuration error: Malformed DATABASE_URL connection string: {exc}"
        ) from exc

    if not password:
        password = os.environ.get("POSTGRES_PASSWORD", "").strip()

    if not password:
        raise RuntimeError(
            "Production configuration error: PostgreSQL database password is mandatory when APP_ENV=production."
        )

    if not password.strip():
        raise RuntimeError(
            "Production configuration error: PostgreSQL database password cannot be empty in production."
        )

    if password in KNOWN_INSECURE_DB_PASSWORDS or password.lower() in KNOWN_INSECURE_DB_PASSWORDS:
        raise RuntimeError(
            "Production configuration error: PostgreSQL database password cannot use a known default or placeholder secret in production."
        )

    if len(password) < 8:
        raise RuntimeError(
            "Production configuration error: PostgreSQL database password must be at least 8 characters in production."
        )


def create_db_engine(db_url: str | None = None) -> Engine:
    """
    Creates a SQLAlchemy Engine with appropriate pooling settings.
    """
    url = db_url or get_database_url()
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    else:
        return create_engine(
            url,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
            pool_timeout=float(os.environ.get("DB_POOL_TIMEOUT", "30.0")),
            pool_pre_ping=True,
            echo=False,
        )


from sqlalchemy import create_engine, event
from sqlite3 import Connection as SQLite3Connection


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine | None = None) -> None:
    """
    Initializes database schema. Useful for test environments and direct startup.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)





def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session(session_factory: sessionmaker[Session] | None = None) -> Generator[Session, None, None]:
    """
    Context manager providing safe transaction boundaries: commits on success,
    rolls back on error, and guarantees connection return to pool.
    """
    factory = session_factory or SessionLocal
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
