"""
Production Configuration Hardening & Secret Validation Tests (Session 96).

Verifies that the application fails closed when started in production mode with missing,
empty, weak, or known placeholder secrets for BOTH the JWT signing secret and the
PostgreSQL database credentials, while preserving seamless local development and testing workflows.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app.auth.security import (
    DEV_JWT_SECRET_KEY,
    KNOWN_INSECURE_SECRETS,
    get_jwt_secret_key,
    is_production_environment,
    validate_jwt_configuration,
    validate_production_configuration,
)
from app.db.session import (
    KNOWN_INSECURE_DB_PASSWORDS,
    validate_database_configuration,
)
from app.main import app


VALID_SYNTHETIC_JWT = "synthetic_prod_jwt_secret_key_minimum_32_characters_long_entropy"
VALID_SYNTHETIC_DB_PASS = "SyntheticProdPass123!"
VALID_SYNTHETIC_DB_URL = f"postgresql+psycopg://prod_user:{VALID_SYNTHETIC_DB_PASS}@db.internal:5432/prod_db"


@pytest.fixture(autouse=True)
def clean_security_environment(monkeypatch):
    """
    Ensures environment variables modified in tests are cleanly isolated and restored.
    Defaults to non-production development mode.
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield


# ==============================================================================
# 1. Database Configuration Hardening in Production Mode
# ==============================================================================

def test_production_mode_missing_database_url_fails_closed(monkeypatch):
    """Production mode must fail closed if DATABASE_URL is completely missing or empty."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    msg = str(exc_info.value)
    assert "DATABASE_URL environment variable is mandatory" in msg
    assert "APP_ENV=production" in msg


def test_production_mode_sqlite_fails_closed(monkeypatch):
    """Production mode must strictly reject SQLite and require PostgreSQL."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod_fallback.db")

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    msg = str(exc_info.value)
    assert "PostgreSQL is mandatory in production" in msg
    assert "SQLite cannot be used" in msg


def test_production_mode_non_postgres_scheme_fails_closed(monkeypatch):
    """Production mode must reject non-PostgreSQL database schemes."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@host/db")

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    assert "DATABASE_URL must specify a valid PostgreSQL connection in production" in str(exc_info.value)


def test_production_mode_missing_db_password_fails_closed(monkeypatch):
    """Production mode must fail closed if PostgreSQL URL lacks a password."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://quant_user@postgres:5432/quant_portfolio_db")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    assert "PostgreSQL database password is mandatory when APP_ENV=production" in str(exc_info.value)


def test_production_mode_empty_db_password_fails_closed(monkeypatch):
    """Production mode must fail closed if PostgreSQL password is blank or whitespace."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://quant_user:   @postgres:5432/quant_portfolio_db")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    assert "PostgreSQL database password cannot be empty in production" in str(exc_info.value)


@pytest.mark.parametrize("placeholder_pwd", list(KNOWN_INSECURE_DB_PASSWORDS))
def test_production_mode_known_insecure_db_passwords_rejected(monkeypatch, placeholder_pwd):
    """Production mode must reject all known default, example, or placeholder database passwords."""
    monkeypatch.setenv("APP_ENV", "production")
    url = f"postgresql+psycopg://quant_user:{placeholder_pwd}@postgres:5432/quant_portfolio_db"
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    msg = str(exc_info.value)
    assert "cannot use a known default or placeholder secret in production" in msg
    # Verify that the actual secret value is never printed in the error message
    assert placeholder_pwd not in msg or placeholder_pwd in ("password", "secret")


def test_production_mode_short_db_password_fails_closed(monkeypatch):
    """Production mode must enforce a minimum length of 8 characters for database passwords."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:abc@postgres:5432/db")

    with pytest.raises(RuntimeError) as exc_info:
        validate_database_configuration()

    assert "must be at least 8 characters in production" in str(exc_info.value)


def test_production_mode_valid_db_configuration_accepted(monkeypatch):
    """Production mode accepts valid PostgreSQL credentials with sufficient entropy."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", VALID_SYNTHETIC_DB_URL)

    # Should execute without raising any exception
    validate_database_configuration()


# ==============================================================================
# 2. JWT Configuration Hardening in Production Mode
# ==============================================================================

def test_production_mode_missing_jwt_fails_closed(monkeypatch):
    """Production mode must fail closed if JWT_SECRET_KEY is absent."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_configuration()

    assert "JWT_SECRET_KEY environment variable is mandatory when APP_ENV=production" in str(exc_info.value)


@pytest.mark.parametrize("insecure_jwt", list(KNOWN_INSECURE_SECRETS))
def test_production_mode_known_insecure_jwt_rejected(monkeypatch, insecure_jwt):
    """Production mode must reject all known default or placeholder JWT secrets."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", insecure_jwt)

    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_configuration()

    msg = str(exc_info.value)
    assert "JWT_SECRET_KEY cannot use a known default or placeholder secret in production" in msg


def test_production_mode_short_jwt_rejected(monkeypatch):
    """Production mode must require >= 32 characters for JWT secret."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "short_key_20_chars_")

    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_configuration()

    assert "must be at least 32 characters (256 bits) in production" in str(exc_info.value)


def test_production_mode_valid_jwt_accepted(monkeypatch):
    """Production mode accepts valid 256-bit JWT signing secret."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", VALID_SYNTHETIC_JWT)

    validate_jwt_configuration()
    assert get_jwt_secret_key() == VALID_SYNTHETIC_JWT


# ==============================================================================
# 3. Development Mode Compatibility & Fallbacks
# ==============================================================================

def test_development_mode_permits_sqlite_fallback(monkeypatch):
    """Development mode permits SQLite file database without error."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./quant_portfolio.db")

    validate_database_configuration()


def test_development_mode_permits_default_credentials(monkeypatch):
    """Development mode permits default dev credentials for local prototyping."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://quant_user:quant_password@localhost:5432/db")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    validate_database_configuration()
    validate_jwt_configuration()
    validate_production_configuration()


# ==============================================================================
# 4. Startup Lifespan Boundary Verification
# ==============================================================================

def test_unified_production_validation_success(monkeypatch):
    """Unified validate_production_configuration succeeds when both secrets are strong."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", VALID_SYNTHETIC_JWT)
    monkeypatch.setenv("DATABASE_URL", VALID_SYNTHETIC_DB_URL)

    validate_production_configuration()


def test_unified_production_validation_fails_on_insecure_db(monkeypatch):
    """Unified validation fails closed when JWT is valid but database credentials are default."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", VALID_SYNTHETIC_JWT)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://quant_user:quant_password@postgres:5432/quant_portfolio_db")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()

    assert "PostgreSQL database password cannot use a known default or placeholder secret" in str(exc_info.value)


def test_fastapi_lifespan_aborts_on_insecure_production_startup(monkeypatch):
    """FastAPI application lifespan startup must immediately abort if production config is insecure."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./quant_portfolio.db")

    # When lifespan is entered (e.g. TestClient context), it must raise RuntimeError and fail closed
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_safe_error_messages_do_not_leak_secret_values(monkeypatch):
    """Error messages identify the invalid configuration setting without printing the value."""
    secret_value = "super_secret_forbidden_string_12345"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", secret_value[:10])  # too short

    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_configuration()

    err = str(exc_info.value)
    assert secret_value[:10] not in err
    assert "JWT_SECRET_KEY must be at least 32 characters" in err
