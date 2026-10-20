"""
Comprehensive test suite for Authentication, Authorization, Role-Based Access Control,
and Dataset Tenant Isolation (Session 11).

All tests in this module run against real database records and real cryptographic JWTs
without dependency mocks.
"""

from __future__ import annotations

import io
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password, rate_limiter, verify_password
from app.db.models import DatasetModel, UserModel
from app.db.session import get_db_session
from app.main import app

client = TestClient(app)

SAMPLE_CSV = b"""date,ticker,market,close,currency
2024-01-02,AAPL,US,185.64,USD
2024-01-03,AAPL,US,184.25,USD
2024-01-02,MSFT,US,370.87,USD
2024-01-03,MSFT,US,370.60,USD
"""


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_cookies():
    from app.market_data.service import clear_dataset_registry

    clear_dataset_registry()
    rate_limiter.clear_all()
    client.cookies.clear()
    with get_db_session() as session:
        session.query(DatasetModel).delete()
        session.query(UserModel).filter(
            UserModel.id != "00000000-0000-0000-0000-000000000001"
        ).delete()
    yield
    clear_dataset_registry()
    rate_limiter.clear_all()
    client.cookies.clear()


# ============================================================================
# 1. USER REGISTRATION & PASSWORD HASHING TESTS
# ============================================================================

def test_user_registration_success():
    """POST /api/v1/auth/register creates user with hashed password and returns clean profile."""
    payload = {
        "email": "QuantResearcher1@domain.com",
        "password": "SecurePassword123!",
        "full_name": "Senior Quant Researcher",
        "role": "researcher",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["email"] == "quantresearcher1@domain.com"
    assert data["full_name"] == "Senior Quant Researcher"
    assert data["role"] == "researcher"
    assert data["is_active"] is True
    assert "id" in data
    # Plaintext password and password hash must never be in API response
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify database persistence and bcrypt hash
    with get_db_session() as session:
        user = session.get(UserModel, data["id"])
        assert user is not None
        assert user.email == "quantresearcher1@domain.com"
        assert user.hashed_password != "SecurePassword123!"
        assert user.hashed_password.startswith("$2b$")
        assert verify_password("SecurePassword123!", user.hashed_password)


def test_user_registration_duplicate_email_rejected():
    """POST /api/v1/auth/register returns 409 Conflict when email is already registered."""
    payload = {
        "email": "duplicate.test@domain.com",
        "password": "Password123!",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Attempt registration with mixed-case variation of same email
    payload_dup = {
        "email": "DUPLICATE.TEST@domain.com",
        "password": "AnotherPassword456!",
    }
    resp2 = client.post("/api/v1/auth/register", json=payload_dup)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"].lower()


@pytest.mark.parametrize(
    "invalid_password,reason",
    [
        ("short1A", "at least 8 characters"),
        ("nouppercase123", "uppercase letter"),
        ("NOLOWERCASE123", "lowercase letter"),
        ("NoDigitsInPassword!", "numeric digit"),
    ],
)
def test_user_registration_password_complexity_enforced(invalid_password, reason):
    """POST /api/v1/auth/register enforces strict password complexity rules."""
    payload = {
        "email": f"pwcheck_{invalid_password}@domain.com",
        "password": invalid_password,
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


def test_user_registration_invalid_email_format():
    """POST /api/v1/auth/register rejects malformed email formats."""
    payload = {
        "email": "not-an-email",
        "password": "ValidPassword123!",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


# ============================================================================
# 2. AUTHENTICATION (LOGIN, LOGOUT, RATE LIMITING) TESTS
# ============================================================================

def test_login_success_sets_cookie_and_returns_bearer_token():
    """POST /api/v1/auth/login returns JWT bearer token and sets HttpOnly cookie."""
    reg_payload = {
        "email": "login.success@domain.com",
        "password": "LoginPass123!",
        "full_name": "Login Tester",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login.success@domain.com", "password": "LoginPass123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login.success@domain.com"

    # Verify HttpOnly session cookie
    assert "access_token" in login_resp.cookies
    cookie = login_resp.cookies["access_token"]
    assert cookie == data["access_token"]


def test_login_invalid_credentials_returns_generic_401():
    """POST /api/v1/auth/login returns generic 401 error preventing account enumeration."""
    # 1. Non-existent email
    resp1 = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost.user@domain.com", "password": "AnyPassword123!"},
    )
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Invalid email or password."

    # 2. Existing email with incorrect password
    client.post(
        "/api/v1/auth/register",
        json={"email": "real.user@domain.com", "password": "RealPassword123!"},
    )
    resp2 = client.post(
        "/api/v1/auth/login",
        json={"email": "real.user@domain.com", "password": "WrongPassword999!"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["detail"] == "Invalid email or password."


def test_login_rate_limiting_locks_out_after_max_failures():
    """POST /api/v1/auth/login enforces temporary lockout after 5 consecutive failures."""
    target_email = "bruteforce.target@domain.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": target_email, "password": "TargetPass123!"},
    )

    # Trigger 5 failed login attempts
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": target_email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 401

    # 6th attempt must be rejected with 429 Too Many Requests
    lockout_resp = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "TargetPass123!"},
    )
    assert lockout_resp.status_code == 429
    assert "temporarily locked" in lockout_resp.json()["detail"].lower()


def test_disabled_account_login_and_access_rejected():
    """Disabled accounts cannot log in or access protected resources (HTTP 403)."""
    reg_payload = {
        "email": "disabled.user@domain.com",
        "password": "DisabledPass123!",
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    user_id = reg_resp.json()["id"]

    # Deactivate account in database
    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        user.is_active = False
        session.commit()

    # Login attempt must return 403
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled.user@domain.com", "password": "DisabledPass123!"},
    )
    assert login_resp.status_code == 403
    assert "disabled" in login_resp.json()["detail"].lower()

    # Pre-existing token presentation must also return 403
    disabled_token = create_access_token(subject=user_id, claims={"role": "researcher"})
    me_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {disabled_token}"}
    )
    assert me_resp.status_code == 403


def test_logout_clears_cookie():
    """POST /api/v1/auth/logout deletes the access_token session cookie."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Successfully logged out."
    # Cookie should be expired/empty
    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "Max-Age=0" in set_cookie or 'expires=' in set_cookie.lower()


# ============================================================================
# 3. JWT TOKEN VERIFICATION & /me PROFILE TESTS
# ============================================================================

def test_auth_me_with_bearer_header_and_cookie():
    """GET /api/v1/auth/me resolves identity via both Bearer header and HttpOnly cookie."""
    reg_payload = {
        "email": "profile.check@domain.com",
        "password": "ProfilePass123!",
        "full_name": "Profile Owner",
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    user_id = reg_resp.json()["id"]

    token = create_access_token(subject=user_id, claims={"role": "researcher"})

    # 1. Access via Authorization Bearer Header
    header_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert header_resp.status_code == 200
    assert header_resp.json()["email"] == "profile.check@domain.com"

    # 2. Access via access_token Cookie
    cookie_resp = client.get("/api/v1/auth/me", cookies={"access_token": token})
    assert cookie_resp.status_code == 200
    assert cookie_resp.json()["email"] == "profile.check@domain.com"


def test_auth_me_without_token_returns_401():
    """GET /api/v1/auth/me returns 401 when no token is provided."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_auth_me_with_expired_token_returns_401():
    """GET /api/v1/auth/me returns 401 with explicit expired message."""
    token = create_access_token(
        subject="some-user-id", expires_delta=timedelta(seconds=-10)
    )
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_auth_me_with_tampered_token_returns_401():
    """GET /api/v1/auth/me returns 401 when token signature is tampered."""
    valid_token = create_access_token(subject="some-user-id")
    # Tamper with the signature portion
    tampered_token = valid_token[:-5] + "XXXXX"

    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


# ============================================================================
# 4. PROTECTED RESEARCH APIS & TENANT ISOLATION TESTS
# ============================================================================

def test_unauthenticated_research_apis_return_401():
    """All protected research APIs reject unauthenticated requests with 401."""
    endpoints = [
        ("GET", "/api/v1/market-data/datasets"),
        ("POST", "/api/v1/market-data/preview"),
        ("POST", "/api/v1/market-data/uploads"),
        ("POST", "/api/v1/market-data/datasets/query"),
        ("GET", "/api/v1/market-data/datasets/00000000-0000-0000-0000-000000000000"),
        ("GET", "/api/v1/market-data/datasets/00000000-0000-0000-0000-000000000000/assets"),
        ("POST", "/api/v1/portfolios/validate"),
        ("POST", "/api/v1/portfolios/optimize"),
        ("POST", "/api/v1/portfolios/efficient-frontier"),
        ("POST", "/api/v1/portfolios/compare"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json={})
        assert resp.status_code == 401, f"Expected 401 on {method} {path}, got {resp.status_code}"


def test_dataset_tenant_isolation_cross_user_rejection():
    """
    Critical security test:
    - User A registers a private dataset.
    - User A can access, query, optimize, and list their dataset.
    - User B CANNOT access, query, optimize, or list User A's dataset (HTTP 403).
    - Admin CAN access User A's dataset.
    """
    # 1. Register User A (Researcher)
    user_a_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "usera@domain.com", "password": "UserAPass123!", "role": "researcher"},
    ).json()
    token_a = create_access_token(subject=user_a_reg["id"], claims={"role": "researcher"})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register User B (Researcher)
    user_b_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "userb@domain.com", "password": "UserBPass123!", "role": "researcher"},
    ).json()
    token_b = create_access_token(subject=user_b_reg["id"], claims={"role": "researcher"})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Register Admin User
    admin_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "admin@domain.com", "password": "AdminPass123!", "role": "admin"},
    ).json()
    token_admin = create_access_token(subject=admin_reg["id"], claims={"role": "admin"})
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # 4. User A uploads private dataset
    upload_resp = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("usera_data.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers_a,
    )
    assert upload_resp.status_code == 200
    dataset_a_id = upload_resp.json()["dataset_id"]
    assert upload_resp.json()["user_id"] == user_a_reg["id"]

    # 5. User A can query their dataset
    query_payload = {
        "dataset_id": dataset_a_id,
        "start_date": "2024-01-02",
        "end_date": "2024-01-03",
    }
    q_resp_a = client.post(
        "/api/v1/market-data/datasets/query", json=query_payload, headers=headers_a
    )
    assert q_resp_a.status_code == 200
    assert q_resp_a.json()["row_count"] == 4

    # 6. User B attempts to query User A's dataset -> HTTP 403 Forbidden
    q_resp_b = client.post(
        "/api/v1/market-data/datasets/query", json=query_payload, headers=headers_b
    )
    assert q_resp_b.status_code == 403
    assert "do not have permission" in q_resp_b.json()["detail"].lower()

    # 7. User B attempts to inspect User A's dataset metadata -> HTTP 403 Forbidden
    meta_resp_b = client.get(
        f"/api/v1/market-data/datasets/{dataset_a_id}", headers=headers_b
    )
    assert meta_resp_b.status_code == 403

    # 8. User B attempts to inspect User A's dataset assets -> HTTP 403 Forbidden
    assets_resp_b = client.get(
        f"/api/v1/market-data/datasets/{dataset_a_id}/assets", headers=headers_b
    )
    assert assets_resp_b.status_code == 403

    # 9. User B attempts to run optimization referencing User A's dataset -> HTTP 403 Forbidden
    opt_payload = {
        "portfolio": {
            "name": "Stolen Portfolio",
            "dataset_id": dataset_a_id,
            "assets": ["AAPL:US", "MSFT:US"],
        },
        "objective": "min_variance",
    }
    opt_resp_b = client.post(
        "/api/v1/portfolios/optimize", json=opt_payload, headers=headers_b
    )
    assert opt_resp_b.status_code == 403

    # 10. User B attempts to run efficient frontier referencing User A's dataset -> HTTP 403 Forbidden
    front_payload = {
        "portfolio": {
            "name": "Stolen Frontier",
            "dataset_id": dataset_a_id,
            "assets": ["AAPL:US", "MSFT:US"],
        },
        "target_count": 5,
    }
    front_resp_b = client.post(
        "/api/v1/portfolios/efficient-frontier", json=front_payload, headers=headers_b
    )
    assert front_resp_b.status_code == 403

    # 11. User B's dataset listing does NOT contain User A's private dataset
    list_b = client.get("/api/v1/market-data/datasets", headers=headers_b).json()
    b_dataset_ids = [d["dataset_id"] for d in list_b]
    assert dataset_a_id not in b_dataset_ids

    # 12. Admin CAN query User A's dataset
    q_resp_admin = client.post(
        "/api/v1/market-data/datasets/query", json=query_payload, headers=headers_admin
    )
    assert q_resp_admin.status_code == 200

    # 13. Admin dataset listing contains User A's dataset
    list_admin = client.get("/api/v1/market-data/datasets", headers=headers_admin).json()
    admin_dataset_ids = [d["dataset_id"] for d in list_admin]
    assert dataset_a_id in admin_dataset_ids


def test_deduplication_isolation_between_tenants():
    """
    Uploading identical CSV content by User B creates a separate isolated dataset record
    and does not leak User A's dataset reference.
    """
    user_a = client.post(
        "/api/v1/auth/register",
        json={"email": "dedup.a@domain.com", "password": "DedupPassword123!"},
    ).json()
    headers_a = {"Authorization": f"Bearer {create_access_token(subject=user_a['id'])}"}

    user_b = client.post(
        "/api/v1/auth/register",
        json={"email": "dedup.b@domain.com", "password": "DedupPassword123!"},
    ).json()
    headers_b = {"Authorization": f"Bearer {create_access_token(subject=user_b['id'])}"}

    # User A uploads
    up_a = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("dedup_test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers_a,
    ).json()

    # User B uploads identical file
    up_b = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("dedup_test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers_b,
    ).json()

    # User B gets their own dataset instance
    assert up_a["dataset_id"] != up_b["dataset_id"]
    assert up_a["user_id"] == user_a["id"]
    assert up_b["user_id"] == user_b["id"]

    # If User A uploads again, User A reuses their own dataset
    up_a_again = client.post(
        "/api/v1/market-data/uploads",
        files={"file": ("dedup_test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers_a,
    ).json()
    assert up_a_again["dataset_id"] == up_a["dataset_id"]


def test_public_health_endpoint_remains_open():
    """GET /api/v1/health is public and includes security response headers."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["stage"] in (
        "secure-access-control",
        "backtesting-engine",
        "scenario-analysis",
        "probabilistic-risk",
        "performance-attribution",
        "portfolio-research",
        "robust-portfolio-optimization",
        "black-litterman-optimization",
        "risk-parity-optimization",
        "factor-investing",
        "multi-asset",
        "execution",
        "regime_switching",
        "attribution",
        "copula_tail_risk",
    )

    # Security headers
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
