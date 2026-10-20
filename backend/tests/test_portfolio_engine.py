"""
Unit, integration, and contract tests for Portfolio Definition, Asset Selection,
and Investment Constraints (Session 05).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market_data.service import clear_dataset_registry, register_csv_dataset
from app.portfolio.models import (
    InvestmentConstraintsModel,
    PortfolioDefinition,
)
from app.portfolio.service import (
    get_dataset_assets,
    validate_portfolio_definition,
)
from app.quant.constraints import (
    AssetWeightBounds,
    ConstraintInfeasibleError,
    InvestmentConstraints,
    check_constraint_feasibility,
    resolve_asset_bounds,
    validate_weights_against_constraints,
)

client = TestClient(app)

SAMPLE_US_CSV = (
    b"date,ticker,market,close,currency,open,high,low,volume\n"
    b"2025-01-02,AAPL,US,150.00,USD,149.00,152.00,148.00,1000000\n"
    b"2025-01-03,AAPL,US,155.00,USD,151.00,156.00,150.00,1100000\n"
    b"2025-01-06,AAPL,US,160.00,USD,156.00,161.00,155.00,1200000\n"
    b"2025-01-02,MSFT,US,400.00,USD,398.00,402.00,397.00,800000\n"
    b"2025-01-03,MSFT,US,405.00,USD,401.00,407.00,400.00,850000\n"
    b"2025-01-06,MSFT,US,410.00,USD,406.00,412.00,405.00,900000\n"
)

SAMPLE_PSX_CSV = (
    b"date,ticker,market,close,currency\n"
    b"2025-01-02,LUCK,PSX,850.00,PKR\n"
    b"2025-01-03,LUCK,PSX,860.00,PKR\n"
    b"2025-01-06,LUCK,PSX,870.00,PKR\n"
    b"2025-01-02,OGDC,PSX,140.00,PKR\n"
    b"2025-01-03,OGDC,PSX,142.00,PKR\n"
    b"2025-01-06,OGDC,PSX,145.00,PKR\n"
)

SAMPLE_MIXED_CURRENCY_CSV = (
    b"date,ticker,market,close,currency\n"
    b"2025-01-02,AAPL,US,150.00,USD\n"
    b"2025-01-03,AAPL,US,155.00,USD\n"
    b"2025-01-02,LUCK,PSX,850.00,PKR\n"
    b"2025-01-03,LUCK,PSX,860.00,PKR\n"
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_dataset_registry()
    yield
    clear_dataset_registry()


# =====================================================================
# 1. ASSET DISCOVERY & SELECTION TESTS
# =====================================================================


def test_get_dataset_assets_us_universe():
    meta = register_csv_dataset(SAMPLE_US_CSV, "us_tech.csv")
    dataset_id = meta["dataset_id"]

    assets = get_dataset_assets(dataset_id)
    assert len(assets) == 2
    assert assets[0].ticker == "AAPL"
    assert assets[0].market == "US"
    assert assets[0].currency == "USD"
    assert assets[0].observation_count == 3
    assert assets[0].start_date == "2025-01-02"
    assert assets[0].end_date == "2025-01-06"

    assert assets[1].ticker == "MSFT"
    assert assets[1].market == "US"
    assert assets[1].currency == "USD"
    assert assets[1].observation_count == 3


def test_asset_selection_deduplication_and_validation():
    # Empty selection rejected
    with pytest.raises(ValueError, match="at least 1 item"):
        PortfolioDefinition(
            name="Empty",
            dataset_id="test-id",
            assets=[],
        )

    # Duplicates rejected
    with pytest.raises(ValueError, match="Duplicate asset selections"):
        PortfolioDefinition(
            name="Dupes",
            dataset_id="test-id",
            assets=["AAPL", "MSFT", "AAPL"],
        )


# =====================================================================
# 2. CONSTRAINT FEASIBILITY & BOUND TESTS
# =====================================================================


def test_valid_constraint_bounds_feasibility():
    """Test valid long-only bounds where sum(l_i) <= 1.0 <= sum(u_i)."""
    constraints = InvestmentConstraints(
        default_min_weight=0.0,
        default_max_weight=0.70,
        target_total_weight=1.0,
        allow_short=False,
    )
    assets = ["AAPL", "MSFT"]
    report = check_constraint_feasibility(assets, constraints)

    assert report.is_feasible is True
    assert report.sum_lower_bounds == 0.0
    assert report.sum_upper_bounds == 1.40
    assert len(report.messages) == 0


def test_infeasible_sum_lower_bounds_exceeds_target():
    """Sum of lower bounds > target weight (e.g. 0.60 + 0.50 = 1.10 > 1.0)."""
    constraints = InvestmentConstraints(
        asset_bounds={
            "AAPL": AssetWeightBounds(lower=0.60, upper=0.80),
            "MSFT": AssetWeightBounds(lower=0.50, upper=0.80),
        },
        target_total_weight=1.0,
    )
    report = check_constraint_feasibility(["AAPL", "MSFT"], constraints)

    assert report.is_feasible is False
    assert any(
        "sum of lower bounds (1.1000) exceeds target" in m for m in report.messages
    )


def test_infeasible_sum_upper_bounds_below_target():
    """Sum of upper bounds < target weight (e.g. 0.40 + 0.40 = 0.80 < 1.0)."""
    constraints = InvestmentConstraints(
        default_min_weight=0.0,
        default_max_weight=0.40,
        target_total_weight=1.0,
    )
    report = check_constraint_feasibility(["AAPL", "MSFT"], constraints)

    assert report.is_feasible is False
    assert any(
        "sum of upper bounds (0.8000) is less than target" in m for m in report.messages
    )


def test_individual_lower_bound_exceeds_upper_bound():
    """l_i > u_i raises ConstraintInfeasibleError."""
    with pytest.raises(ConstraintInfeasibleError, match="cannot exceed upper bound"):
        AssetWeightBounds(lower=0.60, upper=0.40)


def test_negative_bound_when_short_disallowed():
    """Negative bound when allow_short=False raises error."""
    constraints = InvestmentConstraints(
        asset_bounds={"AAPL": AssetWeightBounds(lower=-0.10, upper=0.50)},
        allow_short=False,
    )
    with pytest.raises(ConstraintInfeasibleError, match="allow_short is False"):
        resolve_asset_bounds(["AAPL"], constraints)


def test_included_and_excluded_asset_rules():
    """Test inclusion and exclusion constraint rules."""
    constraints = InvestmentConstraints(
        default_min_weight=0.0,
        default_max_weight=1.0,
        included_assets=["AAPL"],
        excluded_assets=["GOOG"],
    )
    assets = ["AAPL", "MSFT", "GOOG"]
    bounds = resolve_asset_bounds(assets, constraints)

    # Excluded asset has forced lower=0, upper=0
    assert bounds["GOOG"].lower == 0.0
    assert bounds["GOOG"].upper == 0.0

    # Included asset has positive lower bound
    assert bounds["AAPL"].lower > 0.0

    # Overlapping inclusion and exclusion raises
    bad_constraints = InvestmentConstraints(
        included_assets=["AAPL"],
        excluded_assets=["AAPL"],
    )
    with pytest.raises(
        ConstraintInfeasibleError, match="simultaneously included and excluded"
    ):
        resolve_asset_bounds(["AAPL"], bad_constraints)


# =====================================================================
# 3. WEIGHT VALIDATION AGAINST CONSTRAINTS
# =====================================================================


def test_weights_satisfying_constraints():
    constraints = InvestmentConstraints(
        default_min_weight=0.10,
        default_max_weight=0.80,
        target_total_weight=1.0,
    )
    assets = ["AAPL", "MSFT"]
    weights = {"AAPL": 0.60, "MSFT": 0.40}

    violations = validate_weights_against_constraints(weights, assets, constraints)
    assert len(violations) == 0


def test_weights_violating_bounds_and_total():
    constraints = InvestmentConstraints(
        default_min_weight=0.20,
        default_max_weight=0.50,
        target_total_weight=1.0,
    )
    assets = ["AAPL", "MSFT"]
    # AAPL exceeds 0.50 max; MSFT is below 0.20 min; sum = 1.05 != 1.0
    weights = {"AAPL": 0.90, "MSFT": 0.15}

    violations = validate_weights_against_constraints(weights, assets, constraints)
    assert len(violations) >= 3
    assert any("exceeds upper bound" in v for v in violations)
    assert any("below lower bound" in v for v in violations)
    assert any("does not match target" in v for v in violations)


def test_long_short_weights_validation():
    # Long-short portfolio: +130% long, -30% short, net = 100%, gross = 160%
    constraints = InvestmentConstraints(
        allow_short=True,
        default_min_weight=-0.50,
        default_max_weight=1.50,
        target_total_weight=1.0,
        max_gross_exposure=1.60,
    )
    assets = ["AAPL", "MSFT"]
    weights = {"AAPL": 1.30, "MSFT": -0.30}

    violations = validate_weights_against_constraints(weights, assets, constraints)
    assert len(violations) == 0

    # Violating gross exposure (> 1.60)
    overleveraged = {"AAPL": 1.40, "MSFT": -0.40}  # gross = 1.80
    v_gross = validate_weights_against_constraints(overleveraged, assets, constraints)
    assert any(
        "Gross exposure (1.800000) exceeds maximum allowed (1.600000)" in v
        for v in v_gross
    )


# =====================================================================
# 4. PORTFOLIO SERVICE END-TO-END VALIDATION
# =====================================================================


def test_validate_portfolio_definition_success():
    meta = register_csv_dataset(SAMPLE_US_CSV, "tech.csv")
    dataset_id = meta["dataset_id"]

    portfolio = PortfolioDefinition(
        name="Valid US Tech",
        dataset_id=dataset_id,
        assets=["AAPL", "MSFT"],
        weights={"AAPL": 0.60, "MSFT": 0.40},
        constraints=InvestmentConstraintsModel(
            default_min_weight=0.10,
            default_max_weight=0.80,
            target_total_weight=1.0,
        ),
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 6),
    )

    report = validate_portfolio_definition(portfolio)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.asset_details[0].ticker == "AAPL"
    assert report.asset_details[1].ticker == "MSFT"
    assert report.currency_policy["is_multi_currency"] is False
    assert report.date_coverage["common_observation_count"] == 3
    assert report.weight_summary is not None
    assert report.weight_summary["is_fully_invested"] is True


def test_validate_portfolio_missing_dataset_returns_invalid():
    portfolio = PortfolioDefinition(
        name="Orphan Portfolio",
        dataset_id="non-existent-uuid",
        assets=["AAPL"],
    )
    report = validate_portfolio_definition(portfolio)
    assert report.is_valid is False
    assert any("not found" in err for err in report.errors)


def test_validate_portfolio_unknown_asset_in_dataset():
    meta = register_csv_dataset(SAMPLE_US_CSV, "tech.csv")
    dataset_id = meta["dataset_id"]

    portfolio = PortfolioDefinition(
        name="Unknown Asset",
        dataset_id=dataset_id,
        assets=["AAPL", "TSLA"],  # TSLA not in dataset
    )
    report = validate_portfolio_definition(portfolio)
    assert report.is_valid is False
    assert any("TSLA' does not exist in dataset" in err for err in report.errors)


def test_validate_portfolio_mixed_currency_rejected():
    meta = register_csv_dataset(SAMPLE_MIXED_CURRENCY_CSV, "mixed.csv")
    dataset_id = meta["dataset_id"]

    portfolio = PortfolioDefinition(
        name="Mixed US & PSX",
        dataset_id=dataset_id,
        assets=["AAPL", "LUCK"],
    )
    report = validate_portfolio_definition(portfolio)
    assert report.is_valid is False
    assert report.currency_policy["is_multi_currency"] is True
    assert any("span multiple currencies (PKR, USD)" in err for err in report.errors)


def test_validate_portfolio_insufficient_common_dates():
    # Only 1 common date between assets
    single_date_csv = (
        b"date,ticker,market,close,currency\n"
        b"2025-01-02,AAPL,US,100,USD\n"
        b"2025-01-02,MSFT,US,200,USD\n"
    )
    meta = register_csv_dataset(single_date_csv, "single.csv")
    dataset_id = meta["dataset_id"]

    portfolio = PortfolioDefinition(
        name="Too Few Observations",
        dataset_id=dataset_id,
        assets=["AAPL", "MSFT"],
    )
    report = validate_portfolio_definition(portfolio)
    assert report.is_valid is False
    assert any(
        "At least 2 synchronized observations are required" in err
        for err in report.errors
    )


# =====================================================================
# 5. API ENDPOINT CONTRACT TESTS
# =====================================================================


def test_api_list_dataset_assets_success():
    meta = register_csv_dataset(SAMPLE_US_CSV, "tech.csv")
    dataset_id = meta["dataset_id"]

    response = client.get(f"/api/v1/market-data/datasets/{dataset_id}/assets")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == dataset_id
    assert body["asset_count"] == 2
    tickers = [a["ticker"] for a in body["assets"]]
    assert tickers == ["AAPL", "MSFT"]


def test_api_list_dataset_assets_404():
    response = client.get(
        "/api/v1/market-data/datasets/00000000-0000-0000-0000-000000000000/assets"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_validate_portfolio_endpoint():
    meta = register_csv_dataset(SAMPLE_US_CSV, "tech.csv")
    dataset_id = meta["dataset_id"]

    payload = {
        "name": "API Portfolio",
        "dataset_id": dataset_id,
        "assets": ["AAPL", "MSFT"],
        "weights": {"AAPL": 0.50, "MSFT": 0.50},
        "constraints": {
            "default_min_weight": 0.0,
            "default_max_weight": 1.0,
            "target_total_weight": 1.0,
            "allow_short": False,
        },
    }

    response = client.post("/api/v1/portfolios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["portfolio_name"] == "API Portfolio"
    assert data["dataset_id"] == dataset_id
    assert data["feasibility"]["is_feasible"] is True
    assert data["weight_summary"]["is_fully_invested"] is True
