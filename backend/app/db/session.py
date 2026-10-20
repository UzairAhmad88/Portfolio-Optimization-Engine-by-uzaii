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


# Automatically create tables on engine creation
init_db(engine)


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
