"""
Deterministic and analytical test suite for Portfolio Optimization Engine (Session 06).

Validates:
1. Minimum-variance optimization against closed-form analytical solutions.
2. Maximum-Sharpe optimization against closed-form Markowitz tangency portfolio solutions.
3. Equal-weight baseline and constraint-compatibility checks.
4. Numerical safeguards: singular covariance, non-PSD covariance, non-symmetric matrices,
   negative excess returns, and near-zero volatility.
5. Service layer historical price alignment and annualization conventions.
6. API endpoint integration (/api/v1/portfolios/optimize) with FastAPI TestClient.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market_data.service import clear_dataset_registry, register_csv_dataset
from app.portfolio.models import (
    InvestmentConstraintsModel,
    OptimizationRequest,
    PortfolioDefinition,
    WeightBoundsModel,
)
from app.portfolio.optimization_service import execute_portfolio_optimization
from app.quant.constraints import (
    AssetWeightBounds,
    InvestmentConstraints,
)
from app.quant.optimization import (
    OptimizationError,
    OptimizationObjective,
    OptimizationStatus,
    compute_equal_weight_baseline,
    optimize_maximum_sharpe,
    optimize_minimum_variance,
    optimize_portfolio,
    validate_covariance_matrix,
)

client = TestClient(app)

SAMPLE_CSV_DATA = (
    b"date,ticker,market,close,currency,open,high,low,volume\n"
    b"2025-01-02,AAPL,US,100.00,USD,99.0,101.0,98.0,1000\n"
    b"2025-01-03,AAPL,US,102.00,USD,100.0,103.0,99.0,1100\n"
    b"2025-01-06,AAPL,US,101.00,USD,102.0,102.5,100.5,1200\n"
    b"2025-01-07,AAPL,US,104.00,USD,101.0,105.0,100.0,1300\n"
    b"2025-01-08,AAPL,US,106.00,USD,104.0,107.0,103.0,1400\n"
    b"2025-01-02,MSFT,US,200.00,USD,198.0,202.0,197.0,800\n"
    b"2025-01-03,MSFT,US,201.00,USD,200.0,203.0,199.0,850\n"
    b"2025-01-06,MSFT,US,203.00,USD,201.0,204.0,200.0,900\n"
    b"2025-01-07,MSFT,US,202.00,USD,203.0,203.5,201.5,950\n"
    b"2025-01-08,MSFT,US,205.00,USD,202.0,206.0,201.0,1000\n"
    b"2025-01-02,GOOG,US,150.00,USD,149.0,152.0,148.0,600\n"
    b"2025-01-03,GOOG,US,151.00,USD,150.0,153.0,149.0,650\n"
    b"2025-01-06,GOOG,US,149.00,USD,151.0,152.0,148.0,700\n"
    b"2025-01-07,GOOG,US,152.00,USD,149.0,153.0,148.5,750\n"
    b"2025-01-08,GOOG,US,154.00,USD,152.0,155.0,151.0,800\n"
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_dataset_registry()
    yield
    clear_dataset_registry()


# =====================================================================
# 1. MINIMUM-VARIANCE ANALYTICAL & DETERMINISTIC TESTS
# =====================================================================


def test_min_variance_single_asset():
    """Single-asset minimum-variance allocation must be exactly 100% (target_total_weight)."""
    assets = ["ASSET_A"]
    cov = np.array([[0.04]])  # 20% vol
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_minimum_variance(
        assets=assets,
        cov_matrix=cov,
        constraints=constraints,
        expected_returns=np.array([0.10]),
        risk_free_rate=0.02,
    )

    assert res.converged is True
    assert res.is_feasible is True
    assert res.weights["ASSET_A"] == pytest.approx(1.0)
    assert res.variance == pytest.approx(0.04)
    assert res.volatility == pytest.approx(0.20)
    assert res.expected_return == pytest.approx(0.10)
    assert res.sharpe_ratio == pytest.approx((0.10 - 0.02) / 0.20)


def test_min_variance_two_asset_uncorrelated_analytical():
    """
    Two assets with zero correlation:
        w_1* = sigma_2^2 / (sigma_1^2 + sigma_2^2)
        w_2* = sigma_1^2 / (sigma_1^2 + sigma_2^2)
    For sigma_1 = 0.10 (var=0.01), sigma_2 = 0.20 (var=0.04):
        w_1* = 0.04 / 0.05 = 0.80
        w_2* = 0.01 / 0.05 = 0.20
    """
    assets = ["LOW_VOL", "HIGH_VOL"]
    cov = np.array([
        [0.01, 0.00],
        [0.00, 0.04],
    ])
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_minimum_variance(
        assets=assets,
        cov_matrix=cov,
        constraints=constraints,
    )

    assert res.converged is True
    assert res.is_feasible is True
    assert res.weights["LOW_VOL"] == pytest.approx(0.80, abs=1e-5)
    assert res.weights["HIGH_VOL"] == pytest.approx(0.20, abs=1e-5)
    expected_var = (0.80**2 * 0.01) + (0.20**2 * 0.04)
    assert res.variance == pytest.approx(expected_var, abs=1e-6)
    assert res.volatility == pytest.approx(math.sqrt(expected_var), abs=1e-6)


def test_min_variance_two_asset_correlated_analytical():
    """
    Two assets with non-zero correlation:
        sigma_1 = 0.15 (var=0.0225), sigma_2 = 0.25 (var=0.0625), rho = 0.50
        cov_12 = 0.50 * 0.15 * 0.25 = 0.01875
        w_1* = (sigma_2^2 - cov_12) / (sigma_1^2 + sigma_2^2 - 2*cov_12)
             = (0.0625 - 0.01875) / (0.0225 + 0.0625 - 2*0.01875)
             = 0.04375 / 0.0475 = 35 / 38 ~ 0.9210526
        w_2* = 1 - w_1* = 3 / 38 ~ 0.0789474
    """
    assets = ["A", "B"]
    cov = np.array([
        [0.0225, 0.01875],
        [0.01875, 0.0625],
    ])
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_minimum_variance(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.converged is True
    assert res.is_feasible is True
    expected_w1 = 35.0 / 38.0
    expected_w2 = 3.0 / 38.0
    assert res.weights["A"] == pytest.approx(expected_w1, abs=1e-5)
    assert res.weights["B"] == pytest.approx(expected_w2, abs=1e-5)


def test_min_variance_three_asset_equal_variance_uncorrelated():
    """Three identical uncorrelated assets must have equal 1/3 allocations."""
    assets = ["X", "Y", "Z"]
    cov = np.diag([0.04, 0.04, 0.04])
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_minimum_variance(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.converged is True
    for a in assets:
        assert res.weights[a] == pytest.approx(1.0 / 3.0, abs=1e-5)
    assert res.variance == pytest.approx(0.04 / 3.0, abs=1e-6)


def test_min_variance_per_asset_bounds_active():
    """
    Per-asset upper bound forces allocation redistribution away from analytical optimum.
    Unconstrained optimal w_1 would be 0.80, but upper bound on asset 1 is 0.50.
    Optimal bounded solution must be w_1 = 0.50, w_2 = 0.50.
    """
    assets = ["LOW_VOL", "HIGH_VOL"]
    cov = np.array([
        [0.01, 0.00],
        [0.00, 0.04],
    ])
    constraints = InvestmentConstraints(
        default_min_weight=0.0,
        default_max_weight=1.0,
        asset_bounds={"LOW_VOL": AssetWeightBounds(lower=0.0, upper=0.50)},
    )

    res = optimize_minimum_variance(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.converged is True
    assert res.is_feasible is True
    assert res.weights["LOW_VOL"] == pytest.approx(0.50, abs=1e-5)
    assert res.weights["HIGH_VOL"] == pytest.approx(0.50, abs=1e-5)


def test_min_variance_infeasible_constraints():
    """Sum of lower bounds > target weight must be detected and rejected without solving."""
    assets = ["A", "B"]
    cov = np.eye(2) * 0.04
    constraints = InvestmentConstraints(
        default_min_weight=0.60,
        default_max_weight=1.0,
        target_total_weight=1.0,
    )

    res = optimize_minimum_variance(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.converged is False
    assert res.is_feasible is False
    assert res.solver_status == OptimizationStatus.INFEASIBLE
    assert len(res.constraint_violations) > 0
    assert "exceeds target total weight" in res.constraint_violations[0]


def test_min_variance_singular_covariance():
    """Collinear assets (identical returns / zero variance difference) must not crash solver."""
    assets = ["A", "B"]
    # Perfectly collinear: rank 1, determinant 0
    cov = np.array([
        [0.04, 0.04],
        [0.04, 0.04],
    ])
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_minimum_variance(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.converged is True
    assert res.is_feasible is True
    assert sum(res.weights.values()) == pytest.approx(1.0, abs=1e-5)
    assert res.variance == pytest.approx(0.04, abs=1e-6)
    # Ill-conditioned warning present
    assert any("ill-conditioned" in w.lower() or "singular" in w.lower() for w in res.warnings)


def test_min_variance_non_psd_covariance_rejected():
    """Materially non-positive-semidefinite covariance matrix must be rejected."""
    assets = ["A", "B"]
    # Eigenvalues: 1 + 2 = 3 and 1 - 2 = -1 (severely negative)
    bad_cov = np.array([
        [1.0, 2.0],
        [2.0, 1.0],
    ])
    constraints = InvestmentConstraints()

    with pytest.raises(OptimizationError, match="non-positive semi-definite"):
        optimize_minimum_variance(assets=assets, cov_matrix=bad_cov, constraints=constraints)


def test_min_variance_non_symmetric_covariance_rejected():
    """Asymmetric covariance matrix must be rejected."""
    assets = ["A", "B"]
    bad_cov = np.array([
        [0.04, 0.02],
        [0.01, 0.04],
    ])
    constraints = InvestmentConstraints()

    with pytest.raises(OptimizationError, match="not symmetric"):
        optimize_minimum_variance(assets=assets, cov_matrix=bad_cov, constraints=constraints)


# =====================================================================
# 2. MAXIMUM-SHARPE ANALYTICAL & DETERMINISTIC TESTS
# =====================================================================


def test_max_sharpe_analytical_tangency_portfolio():
    """
    Two-asset analytical tangency portfolio with zero correlation:
        mu = [0.12, 0.08], Rf = 0.02
        sigma = [0.20, 0.10] (var = [0.04, 0.01])
        Unscaled weights: w_tilde = Sigma^-1 * (mu - Rf)
            w_tilde_1 = (0.12 - 0.02) / 0.04 = 0.10 / 0.04 = 2.5
            w_tilde_2 = (0.08 - 0.02) / 0.01 = 0.06 / 0.01 = 6.0
        Normalized weights:
            w_1* = 2.5 / 8.5 = 5 / 17 ~ 0.2941176
            w_2* = 6.0 / 8.5 = 12 / 17 ~ 0.7058824
    Both weights are positive, satisfying 0 <= w <= 1.
    """
    assets = ["A", "B"]
    expected_returns = pd.Series([0.12, 0.08], index=assets)
    cov = pd.DataFrame(
        [
            [0.04, 0.00],
            [0.00, 0.01],
        ],
        index=assets,
        columns=assets,
    )
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)
    rf = 0.02

    res = optimize_maximum_sharpe(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov,
        constraints=constraints,
        risk_free_rate=rf,
    )

    assert res.converged is True
    assert res.is_feasible is True
    expected_w1 = 5.0 / 17.0
    expected_w2 = 12.0 / 17.0
    assert res.weights["A"] == pytest.approx(expected_w1, abs=1e-4)
    assert res.weights["B"] == pytest.approx(expected_w2, abs=1e-4)

    # Independent recalculation check
    expected_mu = (expected_w1 * 0.12) + (expected_w2 * 0.08)
    expected_var = (expected_w1**2 * 0.04) + (expected_w2**2 * 0.01)
    expected_vol = math.sqrt(expected_var)
    expected_sharpe = (expected_mu - rf) / expected_vol

    assert res.expected_return == pytest.approx(expected_mu, abs=1e-5)
    assert res.volatility == pytest.approx(expected_vol, abs=1e-5)
    assert res.sharpe_ratio == pytest.approx(expected_sharpe, abs=1e-4)


def test_max_sharpe_non_positive_excess_returns_handled():
    """
    When all expected returns <= Rf, maximizing Sharpe ratio is economically invalid.
    The engine must reject it with NON_POSITIVE_EXCESS_RETURNS status without claiming optimum.
    """
    assets = ["A", "B"]
    expected_returns = np.array([0.02, 0.01])  # both <= Rf=0.03
    cov = np.eye(2) * 0.04
    constraints = InvestmentConstraints()
    rf = 0.03

    res = optimize_maximum_sharpe(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov,
        constraints=constraints,
        risk_free_rate=rf,
    )

    assert res.converged is False
    assert res.is_feasible is False
    assert res.solver_status == OptimizationStatus.NON_POSITIVE_EXCESS_RETURNS
    assert "does not exceed the risk-free rate" in res.solver_message
    assert res.weights == {}


def test_max_sharpe_near_zero_volatility():
    """Zero variance asset leads to undefined Sharpe ratio warning."""
    assets = ["CASH"]
    expected_returns = np.array([0.05])
    cov = np.array([[0.0]])  # zero variance
    constraints = InvestmentConstraints()

    res = optimize_maximum_sharpe(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov,
        constraints=constraints,
        risk_free_rate=0.02,
    )

    assert res.converged is True
    assert res.volatility == pytest.approx(0.0)
    assert res.sharpe_ratio is None
    assert any("near-zero" in w for w in res.warnings)


# =====================================================================
# 3. EQUAL-WEIGHT BASELINE TESTS
# =====================================================================


def test_equal_weight_feasible_configuration():
    """Equal weight must allocate 1/N to each asset and compute all risk/return metrics."""
    assets = ["A", "B", "C", "D"]
    cov = np.eye(4) * 0.04
    ret = pd.Series([0.10, 0.12, 0.08, 0.14], index=assets)
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = compute_equal_weight_baseline(
        assets=assets,
        cov_matrix=cov,
        constraints=constraints,
        expected_returns=ret,
        risk_free_rate=0.02,
    )

    assert res.converged is True
    assert res.is_feasible is True
    assert res.solver_status == OptimizationStatus.FEASIBLE_BASELINE
    for a in assets:
        assert res.weights[a] == pytest.approx(0.25)
    assert res.expected_return == pytest.approx((0.10 + 0.12 + 0.08 + 0.14) / 4.0)
    assert res.variance == pytest.approx(0.04 / 4.0)
    assert res.volatility == pytest.approx(math.sqrt(0.01))
    assert res.sharpe_ratio is not None


def test_equal_weight_invalid_for_constraints():
    """If equal weight violates upper bounds (e.g. 1/3 > 0.25), baseline must report invalid."""
    assets = ["A", "B", "C"]  # 1/3 ~ 0.333333
    cov = np.eye(3) * 0.04
    constraints = InvestmentConstraints(
        default_min_weight=0.0,
        default_max_weight=0.25,  # Caps each asset at 25%, but 1/3 = 33.3%
        target_total_weight=1.0,
    )

    res = compute_equal_weight_baseline(assets=assets, cov_matrix=cov, constraints=constraints)

    assert res.is_feasible is False
    assert res.solver_status == OptimizationStatus.INVALID_FOR_CONSTRAINTS
    assert any("exceeds upper bound" in v for v in res.constraint_violations)


# =====================================================================
# 4. DISPATCHER & VALIDATION SUITE
# =====================================================================


def test_optimize_portfolio_dispatcher():
    assets = ["A", "B"]
    cov = np.eye(2) * 0.04
    constraints = InvestmentConstraints()
    ret = np.array([0.10, 0.12])

    res_min = optimize_portfolio(
        assets=assets, cov_matrix=cov, constraints=constraints, objective="min_variance"
    )
    assert res_min.objective == "min_variance"

    res_max = optimize_portfolio(
        assets=assets,
        cov_matrix=cov,
        constraints=constraints,
        objective="max_sharpe",
        expected_returns=ret,
    )
    assert res_max.objective == "max_sharpe"

    res_eq = optimize_portfolio(
        assets=assets, cov_matrix=cov, constraints=constraints, objective="equal_weight"
    )
    assert res_eq.objective == "equal_weight"

    with pytest.raises(OptimizationError, match="Unsupported optimization objective"):
        optimize_portfolio(assets=assets, cov_matrix=cov, constraints=constraints, objective="unknown")


def test_validate_covariance_matrix_rules():
    # Empty
    with pytest.raises(OptimizationError, match="empty"):
        validate_covariance_matrix(np.zeros((0, 0)))

    # Non-square
    with pytest.raises(OptimizationError, match="2D square"):
        validate_covariance_matrix(np.zeros((2, 3)))

    # Dimension mismatch
    with pytest.raises(OptimizationError, match="dimension"):
        validate_covariance_matrix(np.eye(2), expected_dim=3)

    # NaN / Inf
    with pytest.raises(OptimizationError, match="non-finite"):
        validate_covariance_matrix(np.array([[1.0, np.nan], [np.nan, 1.0]]))


# =====================================================================
# 5. SERVICE LAYER & HISTORICAL ALIGNMENT TESTS
# =====================================================================


def test_service_execute_portfolio_optimization():
    meta = register_csv_dataset(SAMPLE_CSV_DATA, "sample.csv")
    dataset_id = meta["dataset_id"]

    req = OptimizationRequest(
        portfolio=PortfolioDefinition(
            name="Tech 3-Asset Portfolio",
            dataset_id=dataset_id,
            assets=["AAPL", "MSFT", "GOOG"],
            constraints=InvestmentConstraintsModel(
                default_min_weight=0.0,
                default_max_weight=1.0,
                target_total_weight=1.0,
                allow_short=False,
            ),
        ),
        objective="min_variance",
        risk_free_rate=0.02,
        annualized=True,
        periods_per_year=252,
    )

    resp = execute_portfolio_optimization(req)

    assert resp.is_success is True
    assert resp.is_feasible is True
    assert len(resp.weights) == 3
    assert sum(resp.weights.values()) == pytest.approx(1.0, abs=1e-5)
    assert resp.metrics is not None
    assert resp.metrics.volatility > 0.0
    assert resp.metrics.variance > 0.0
    assert resp.date_coverage["common_observation_count"] == 5


def test_service_multi_currency_rejection():
    # Dataset with USD and PKR assets
    mixed_csv = (
        b"date,ticker,market,close,currency\n"
        b"2025-01-02,AAPL,US,150.00,USD\n"
        b"2025-01-03,AAPL,US,155.00,USD\n"
        b"2025-01-02,LUCK,PSX,850.00,PKR\n"
        b"2025-01-03,LUCK,PSX,860.00,PKR\n"
    )
    meta = register_csv_dataset(mixed_csv, "mixed.csv")
    dataset_id = meta["dataset_id"]

    req = OptimizationRequest(
        portfolio=PortfolioDefinition(
            name="Mixed Currency",
            dataset_id=dataset_id,
            assets=["AAPL", "LUCK"],
        ),
        objective="min_variance",
    )

    resp = execute_portfolio_optimization(req)
    assert resp.is_success is False
    assert any("multiple currencies" in err for err in resp.errors)


# =====================================================================
# 6. API ENDPOINT INTEGRATION TESTS (/api/v1/portfolios/optimize)
# =====================================================================


def test_api_optimize_minimum_variance():
    meta = register_csv_dataset(SAMPLE_CSV_DATA, "sample_api.csv")
    dataset_id = meta["dataset_id"]

    payload = {
        "portfolio": {
            "name": "API MinVar",
            "dataset_id": dataset_id,
            "assets": ["AAPL", "MSFT"],
            "constraints": {
                "default_min_weight": 0.0,
                "default_max_weight": 1.0,
                "target_total_weight": 1.0,
                "allow_short": False,
            },
        },
        "objective": "min_variance",
        "risk_free_rate": 0.02,
        "annualized": True,
        "periods_per_year": 252,
    }

    res = client.post("/api/v1/portfolios/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["objective"] == "min_variance"
    assert "AAPL:US" in data["weights"]
    assert "MSFT:US" in data["weights"]
    assert data["metrics"]["is_fully_invested"] is True
    assert data["metrics"]["is_long_only"] is True


def test_api_optimize_maximum_sharpe():
    meta = register_csv_dataset(SAMPLE_CSV_DATA, "sample_sharpe.csv")
    dataset_id = meta["dataset_id"]

    payload = {
        "portfolio": {
            "name": "API MaxSharpe",
            "dataset_id": dataset_id,
            "assets": ["AAPL", "MSFT", "GOOG"],
            "constraints": {
                "default_min_weight": 0.05,
                "default_max_weight": 0.80,
                "target_total_weight": 1.0,
                "allow_short": False,
            },
        },
        "objective": "max_sharpe",
        "risk_free_rate": 0.01,
        "annualized": True,
    }

    res = client.post("/api/v1/portfolios/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["objective"] == "max_sharpe"
    assert data["metrics"]["sharpe_ratio"] is not None
    assert data["solver_diagnostics"]["converged"] is True


def test_api_optimize_equal_weight():
    meta = register_csv_dataset(SAMPLE_CSV_DATA, "sample_eq.csv")
    dataset_id = meta["dataset_id"]

    payload = {
        "portfolio": {
            "name": "API EqualWeight",
            "dataset_id": dataset_id,
            "assets": ["AAPL", "MSFT"],
        },
        "objective": "equal_weight",
    }

    res = client.post("/api/v1/portfolios/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["weights"]["AAPL:US"] == pytest.approx(0.50)
    assert data["weights"]["MSFT:US"] == pytest.approx(0.50)


def test_api_optimize_dataset_not_found_404():
    payload = {
        "portfolio": {
            "name": "Ghost",
            "dataset_id": "00000000-0000-0000-0000-000000000000",
            "assets": ["AAPL"],
        },
        "objective": "min_variance",
    }

    res = client.post("/api/v1/portfolios/optimize", json=payload)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_optimize_infeasible_constraints_422():
    meta = register_csv_dataset(SAMPLE_CSV_DATA, "sample_infeas.csv")
    dataset_id = meta["dataset_id"]

    payload = {
        "portfolio": {
            "name": "Infeasible",
            "dataset_id": dataset_id,
            "assets": ["AAPL", "MSFT"],
            "constraints": {
                "default_min_weight": 0.70,  # 0.70 * 2 = 1.40 > 1.0
                "default_max_weight": 1.0,
                "target_total_weight": 1.0,
            },
        },
        "objective": "min_variance",
    }

    res = client.post("/api/v1/portfolios/optimize", json=payload)
    assert res.status_code == 422
    data = res.json()["detail"]
    assert data["is_success"] is False
    assert any("exceeds target total weight" in err for err in data["errors"])
