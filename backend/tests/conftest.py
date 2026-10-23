"""
Pytest configuration and test fixtures for Quant Portfolio Optimization Engine.
Provides database initialization and authentication dependency overrides for legacy tests.
"""

from __future__ import annotations

import pytest
from app.auth.dependencies import get_current_active_user, get_current_user
from app.auth.security import hash_password
from app.db.models import UserModel
from app.db.session import get_db_session, init_db
from app.main import app

# System default test user representation for legacy regression suites
TEST_RESEARCHER_ID = "00000000-0000-0000-0000-000000000001"
TEST_RESEARCHER_USER = UserModel(
    id=TEST_RESEARCHER_ID,
    email="test.researcher@quantengine.local",
    hashed_password="",
    full_name="Default Test Researcher",
    role="researcher",
    is_active=True,
)


@pytest.fixture(autouse=True)
def configure_auth_for_tests(request: pytest.FixtureRequest):
    """
    Automatically configures authentication dependency injection for tests:
    - In auth-specific security tests (test_auth_*), overrides are disabled to test
      real JWT verification, password hashes, and database-backed access control.
    - In existing mathematical, optimization, and API reliability tests, overrides
      provide an authenticated researcher session to preserve verified test contracts.
    """
    init_db()

    # Seed the test researcher user in DB so foreign key constraints on datasets pass cleanly
    with get_db_session() as session:
        user = session.get(UserModel, TEST_RESEARCHER_ID)
        if user is None:
            user = UserModel(
                id=TEST_RESEARCHER_ID,
                email="test.researcher@quantengine.local",
                hashed_password=hash_password("DevTestPass123!"),
                full_name="Default Test Researcher",
                role="researcher",
                is_active=True,
            )
            session.add(user)
            session.commit()

    # Do not mock authentication in security test suites
    if (
        "test_auth" in request.node.nodeid
        or "test_backtesting_api" in request.node.nodeid
        or "test_scenario_api" in request.node.nodeid
        or "test_risk_simulation_api" in request.node.nodeid
        or "test_performance_api" in request.node.nodeid
        or "test_research_api" in request.node.nodeid
        or "test_robust_api" in request.node.nodeid
        or "test_black_litterman_api" in request.node.nodeid
        or "test_risk_parity_api" in request.node.nodeid
        or "test_factor_api" in request.node.nodeid
        or "test_multi_asset_api" in request.node.nodeid
        or "test_execution_api" in request.node.nodeid
        or "test_regime_switching_api" in request.node.nodeid
        or "test_performance_attribution_api" in request.node.nodeid
        or "test_copula_tail_risk_api" in request.node.nodeid
        or "test_vine_copula_api" in request.node.nodeid
        or "test_overfitting_api" in request.node.nodeid
        or "test_reporting_api" in request.node.nodeid
        or "test_reporting_export_api" in request.node.nodeid
    ):
        app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        yield
        return

    app.dependency_overrides[get_current_user] = lambda: TEST_RESEARCHER_USER
    app.dependency_overrides[get_current_active_user] = lambda: TEST_RESEARCHER_USER

    yield

    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_current_user, None)
