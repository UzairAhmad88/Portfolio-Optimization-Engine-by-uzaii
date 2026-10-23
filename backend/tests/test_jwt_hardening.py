"""
Production JWT Secret Key & Security Configuration Hardening Tests (Session 83).

Verifies that the application fails closed when started in production mode with a missing,
short, or known placeholder secret, while preserving seamless local development and testing workflows.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
import pytest
import jwt

from app.auth.security import (
    DEV_JWT_SECRET_KEY,
    KNOWN_INSECURE_SECRETS,
    create_access_token,
    decode_access_token,
    get_jwt_secret_key,
    is_production_environment,
    validate_jwt_configuration,
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """
    Ensures environment variables modified in tests are cleanly restored.
    """
    # Default to development mode unless explicitly altered by a test
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    yield


def test_is_production_environment(monkeypatch):
    """Verifies environment classification across various case variations."""
    monkeypatch.setenv("APP_ENV", "production")
    assert is_production_environment() is True

    monkeypatch.setenv("APP_ENV", "PRODUCTION")
    assert is_production_environment() is True

    monkeypatch.setenv("APP_ENV", "prod")
    assert is_production_environment() is True

    monkeypatch.setenv("APP_ENV", "development")
    assert is_production_environment() is False

    monkeypatch.setenv("APP_ENV", "test")
    assert is_production_environment() is False

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert is_production_environment() is True


def test_production_mode_missing_secret_fails_closed(monkeypatch):
    """Production mode must fail closed if JWT_SECRET_KEY is absent."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret_key()

    assert "mandatory when APP_ENV=production" in str(exc_info.value)


def test_production_mode_empty_secret_fails_closed(monkeypatch):
    """Production mode must fail closed if JWT_SECRET_KEY is whitespace or empty."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "   ")

    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret_key()

    assert "mandatory when APP_ENV=production" in str(exc_info.value)


@pytest.mark.parametrize("bad_secret", list(KNOWN_INSECURE_SECRETS))
def test_production_mode_known_insecure_defaults_rejected(monkeypatch, bad_secret):
    """Production mode must reject all known dev and example placeholder secrets."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", bad_secret)

    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret_key()

    assert "cannot use a known default or placeholder secret" in str(exc_info.value)


def test_production_mode_short_secret_rejected(monkeypatch):
    """Production mode must enforce a minimum secret length of 32 characters (256 bits)."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "only_28_characters_long_key_")

    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret_key()

    assert "must be at least 32 characters (256 bits)" in str(exc_info.value)


def test_production_mode_valid_secret_accepted(monkeypatch):
    """Production mode accepts an explicitly configured secret with >= 32 characters."""
    valid_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", valid_key)

    secret = get_jwt_secret_key()
    assert secret == valid_key

    # Confirm token creation and roundtrip validation succeed with this production key
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_development_mode_default_fallback_allowed(monkeypatch):
    """Non-production mode uses DEV_JWT_SECRET_KEY when JWT_SECRET_KEY is omitted."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    secret = get_jwt_secret_key()
    assert secret == DEV_JWT_SECRET_KEY

    token = create_access_token(subject="dev-user")
    payload = decode_access_token(token)
    assert payload["sub"] == "dev-user"


def test_development_mode_custom_secret_honored(monkeypatch):
    """Non-production mode honors an explicitly configured custom key."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "custom_test_key_123")

    secret = get_jwt_secret_key()
    assert secret == "custom_test_key_123"


def test_startup_validation_fails_closed_in_production(monkeypatch):
    """Application startup validation (validate_jwt_configuration) fails closed in production without key."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError):
        validate_jwt_configuration()


def test_algorithm_confusion_prevention():
    """Confirms token validation strictly enforces HS256 and rejects 'none' or unauthorized algorithms."""
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "attacker", "iss": "quant-portfolio-engine", "exp": 9999999999, "iat": 1000000000}).encode()).rstrip(b"=").decode()
    forged_token = f"{header}.{payload}."

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(forged_token)
