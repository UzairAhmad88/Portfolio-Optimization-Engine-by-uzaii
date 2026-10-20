"""
Test suite for Session 07: Efficient Frontier & Portfolio Risk Analytics.

Covers:
1. Pure risk metric oracles: Sharpe ratio, Sortino ratio, drawdown, and portfolio risk summary.
2. Numerical verification of target-return optimization against closed-form analytical oracles.
3. Linear programming feasible return bounds and infeasible target handling.
4. Efficient frontier generation, grid spacing, dominance classification, and partial failure reporting.
5. Multi-portfolio comparison consistency across GMV, Maximum Sharpe, and Equal-Weight baselines.
6. Cross-currency safeguard enforcement.
7. API integration for /portfolios/efficient-frontier and /portfolios/compare.
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
    EfficientFrontierRequest,
    InvestmentConstraintsModel,
    PortfolioComparisonRequest,
    PortfolioDefinition,
    WeightBoundsModel,
)
from app.portfolio.optimization_service import (
    execute_efficient_frontier,
    execute_portfolio_comparison,
)
from app.quant.constraints import InvestmentConstraints
from app.quant.optimization import (
    FrontierPoint,
    OptimizationObjective,
    OptimizationStatus,
    calculate_feasible_return_bounds,
    generate_efficient_frontier,
    optimize_portfolio,
    optimize_target_return_min_variance,
)
from app.quant.risk import (
    annual_to_periodic_rate,
    downside_deviation,
    maximum_drawdown,
    portfolio_risk_summary,
    sharpe_ratio,
    sortino_ratio,
)


@pytest.fixture(autouse=True)
def setup_test_registry():
    """Ensure clean registry before and after tests."""
    clear_dataset_registry()
    yield
    clear_dataset_registry()


# =====================================================================
# 1. Standalone Pure Risk Metrics Tests
# =====================================================================

class TestRiskMetrics:
    """Tests for Sharpe ratio, Sortino ratio, Drawdown, and Portfolio Risk Summary."""

    def test_sharpe_ratio_deterministic_oracle(self):
        """Verify Sharpe ratio calculation against known analytical values."""
        # Annualized case: mean=0.15, rf=0.03, vol=0.20 -> Sharpe = (0.15 - 0.03) / 0.20 = 0.60
        sr = sharpe_ratio(returns=0.15, volatility_val=0.20, risk_free_rate=0.03, annualized=True)
        assert sr is not None
        assert math.isclose(sr, 0.60, rel_tol=1e-7)

        # Periodic case: daily mean=0.0005, daily rf=0.0001, daily vol=0.01
        sr_periodic = sharpe_ratio(returns=0.0005, volatility_val=0.01, risk_free_rate=0.0001, annualized=False)
        assert sr_periodic is not None
        assert math.isclose(sr_periodic, 0.04, rel_tol=1e-7)

    def test_sharpe_ratio_zero_and_negligible_volatility(self):
        """Zero or negligible volatility must raise ValueError rather than division-by-zero or inf."""
        with pytest.raises(ValueError, match="zero or numerically negligible"):
            sharpe_ratio(returns=0.10, volatility_val=0.0, risk_free_rate=0.02)
        with pytest.raises(ValueError, match="zero or numerically negligible"):
            sharpe_ratio(returns=0.10, volatility_val=1e-13, risk_free_rate=0.02)
        with pytest.raises(ValueError, match="cannot be negative"):
            sharpe_ratio(returns=0.10, volatility_val=-0.05, risk_free_rate=0.02)

    def test_sharpe_ratio_from_series(self):
        """Calculate Sharpe ratio directly from historical pandas Series."""
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00, 0.01, -0.02, 0.02])
        sr = sharpe_ratio(returns=returns, risk_free_rate=0.0, periods_per_year=252, annualized=True)
        assert sr is not None
        assert isinstance(sr, float)
        assert np.isfinite(sr)

        # Invalid series cases
        with pytest.raises(ValueError, match="requires >= 2"):
            sharpe_ratio(returns=pd.Series([0.05]))

    def test_sortino_ratio_deterministic(self):
        """Verify Sortino ratio calculation using known downside deviation."""
        # Returns: 5 periods. target MAR = 0.0
        # r = [0.04, -0.02, 0.03, -0.04, 0.05]
        # downside deviations below 0.0: [-0.02, -0.04] -> squared: [0.0004, 0.0016]
        # sum of squared = 0.0020
        # sample semi-variance (ddof=1) = 0.0020 / (5 - 1) = 0.0005
        # downside deviation = sqrt(0.0005) = 0.02236067977
        # mean return = (0.04 - 0.02 + 0.03 - 0.04 + 0.05) / 5 = 0.06 / 5 = 0.012
        # Sortino periodic = (0.012 - 0.0) / 0.02236067977 = 0.5366563
        returns = pd.Series([0.04, -0.02, 0.03, -0.04, 0.05])
        dd = float(downside_deviation(returns, threshold=0.0, ddof=1))
        expected_dd = math.sqrt(0.0020 / 4)
        assert math.isclose(dd, expected_dd, rel_tol=1e-7)

        sortino_periodic = sortino_ratio(returns=returns, required_return=0.0, annualized=False, ddof=1)
        assert sortino_periodic is not None
        assert math.isclose(sortino_periodic, 0.012 / expected_dd, rel_tol=1e-6)

    def test_sortino_ratio_zero_downside_deviation(self):
        """When no returns fall below MAR, downside deviation is 0.0 and Sortino raises ValueError."""
        positive_returns = pd.Series([0.02, 0.03, 0.01, 0.04, 0.05])
        dd = float(downside_deviation(positive_returns, threshold=0.0))
        assert dd == 0.0

        with pytest.raises(ValueError, match="Downside deviation is zero or numerically negligible"):
            sortino_ratio(returns=positive_returns, required_return=0.0)

    def test_sortino_does_not_substitute_volatility(self):
        """Ensure Sortino ratio denominator is strictly downside deviation, not total volatility."""
        returns = pd.Series([0.05, -0.01, 0.02, -0.02, 0.04, 0.01])
        total_vol = float(returns.std(ddof=1))
        down_dev = float(downside_deviation(returns, threshold=0.0, ddof=1))
        assert total_vol > down_dev > 0.0

    def test_maximum_drawdown_known_wealth_path(self):
        """Verify maximum drawdown on known wealth path."""
        # Prices: 100 -> 120 (peak) -> 90 -> 110 -> 80 (trough) -> 100
        # Peak before trough is 120, minimum trough is 80 -> Drawdown = (120 - 80) / 120 = 40/120 = 1/3
        prices = [100.0, 120.0, 90.0, 110.0, 80.0, 100.0]
        rets = [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]
        ret_series = pd.Series(rets)

        dd_res = maximum_drawdown(ret_series)
        assert math.isclose(abs(dd_res.max_drawdown), 1.0 / 3.0, rel_tol=1e-6)

    def test_portfolio_risk_summary_comprehensive(self):
        """Verify portfolio_risk_summary returns all required analytical fields correctly."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B").strftime("%Y-%m-%d")
        rets = pd.Series([0.01, -0.015, 0.02, -0.005, 0.012, 0.008, -0.02, 0.015, 0.01, -0.004], index=dates)

        summary = portfolio_risk_summary(
            returns=rets,
            risk_free_rate=0.02,
            required_return=0.0,
            periods_per_year=252,
        )

        assert summary.observation_count == 10
        assert summary.start_date == dates[0]
        assert summary.end_date == dates[-1]
        assert summary.volatility_annualized > 0.0
        assert summary.volatility_periodic > 0.0
        assert summary.variance_periodic > 0.0
        assert summary.max_drawdown <= 0.0
        assert summary.downside_deviation_annualized >= 0.0
        assert summary.sharpe_ratio is not None
        assert summary.sortino_ratio is not None
        assert summary.periods_per_year == 252


# =====================================================================
# 2. Target-Return Optimization & Feasibility Tests
# =====================================================================

class TestTargetReturnOptimization:
    """Tests for target-return minimum-variance solver against analytical mathematical oracles."""

    @pytest.fixture
    def two_asset_system(self):
        """
        Uncorrelated 2-asset universe with known closed-form analytical solution:
            Asset 1: mu_1 = 0.10, var_1 = 0.04 (vol=0.20)
            Asset 2: mu_2 = 0.20, var_2 = 0.09 (vol=0.30)
            Covariance = 0.0
        """
        assets = ["ASSET_A", "ASSET_B"]
        exp_returns = pd.Series([0.10, 0.20], index=assets)
        cov = pd.DataFrame(
            [[0.04, 0.00],
             [0.00, 0.09]],
            index=assets,
            columns=assets,
        )
        constraints = InvestmentConstraints(
            default_min_weight=0.0,
            default_max_weight=1.0,
            target_total_weight=1.0,
            allow_short=False,
        )
        return assets, exp_returns, cov, constraints

    def test_two_asset_analytical_oracle(self, two_asset_system):
        """
        In a 2-asset universe, for any target return R_target in [0.10, 0.20],
        w_1 * 0.10 + w_2 * 0.20 = R_target and w_1 + w_2 = 1.0.
        Exact analytical weights:
            w_2 = (R_target - 0.10) / 0.10
            w_1 = 1.0 - w_2
        """
        assets, exp_returns, cov, constraints = two_asset_system

        target_ret = 0.14
        expected_w2 = (0.14 - 0.10) / 0.10  # 0.40
        expected_w1 = 0.60

        res = optimize_target_return_min_variance(
            assets=assets,
            expected_returns=exp_returns,
            cov_matrix=cov,
            constraints=constraints,
            target_return=target_ret,
        )

        assert res.converged
        assert res.is_feasible
        assert res.solver_status == OptimizationStatus.CONVERGED
        assert math.isclose(res.weights["ASSET_A"], expected_w1, abs_tol=1e-5)
        assert math.isclose(res.weights["ASSET_B"], expected_w2, abs_tol=1e-5)
        assert math.isclose(res.expected_return, target_ret, abs_tol=1e-5)
        assert abs(res.expected_return - target_ret) <= 1e-4

        expected_var = (0.60**2) * 0.04 + (0.40**2) * 0.09
        assert math.isclose(res.variance, expected_var, abs_tol=1e-5)

    def test_feasible_return_bounds_linprog(self, two_asset_system):
        """Verify calculate_feasible_return_bounds returns exact LP extreme endpoints."""
        assets, exp_returns, _, constraints = two_asset_system
        min_ret, max_ret, w_min, w_max = calculate_feasible_return_bounds(
            assets=assets,
            expected_returns=exp_returns,
            constraints=constraints,
        )
        assert math.isclose(min_ret, 0.10, abs_tol=1e-6)
        assert math.isclose(max_ret, 0.20, abs_tol=1e-6)
        assert math.isclose(w_min[0], 1.0, abs_tol=1e-6)
        assert math.isclose(w_max[1], 1.0, abs_tol=1e-6)

    def test_infeasible_target_return_handling(self, two_asset_system):
        """Targets outside the mathematically feasible range must fail explicitly with INFEASIBLE status."""
        assets, exp_returns, cov, constraints = two_asset_system

        res_high = optimize_target_return_min_variance(
            assets=assets,
            expected_returns=exp_returns,
            cov_matrix=cov,
            constraints=constraints,
            target_return=0.25,
        )
        assert not res_high.is_feasible
        assert not res_high.converged
        assert res_high.solver_status == OptimizationStatus.INFEASIBLE
        assert res_high.weights == {}
        assert any("infeasible" in v.lower() for v in res_high.constraint_violations)

        res_low = optimize_target_return_min_variance(
            assets=assets,
            expected_returns=exp_returns,
            cov_matrix=cov,
            constraints=constraints,
            target_return=0.05,
        )
        assert not res_low.is_feasible
        assert not res_low.converged
        assert res_low.solver_status == OptimizationStatus.INFEASIBLE
        assert res_low.weights == {}

    def test_dispatcher_target_return(self, two_asset_system):
        """Test primary optimize_portfolio dispatcher with TARGET_RETURN objective."""
        assets, exp_returns, cov, constraints = two_asset_system
        res = optimize_portfolio(
            assets=assets,
            cov_matrix=cov,
            constraints=constraints,
            objective=OptimizationObjective.TARGET_RETURN,
            expected_returns=exp_returns,
            target_return=0.15,
        )
        assert res.converged
        assert res.is_feasible
        assert math.isclose(res.expected_return, 0.15, abs_tol=1e-4)


# =====================================================================
# 3. Efficient Frontier Engine Tests
# =====================================================================

class TestEfficientFrontierEngine:
    """Tests for efficient frontier grid generation, dominance, and failure tracking."""

    @pytest.fixture
    def three_asset_market(self):
        assets = ["EQ1", "EQ2", "EQ3"]
        exp_returns = pd.Series([0.08, 0.15, 0.22], index=assets)
        cov = pd.DataFrame(
            [[0.04, 0.01, 0.005],
             [0.01, 0.09, 0.02],
             [0.005, 0.02, 0.16]],
            index=assets,
            columns=assets,
        )
        constraints = InvestmentConstraints(
            default_min_weight=0.0,
            default_max_weight=1.0,
            target_total_weight=1.0,
            allow_short=False,
        )
        return assets, exp_returns, cov, constraints

    def test_generate_efficient_frontier_grid(self, three_asset_market):
        """Generate grid of frontier points and verify properties."""
        assets, exp_returns, cov, constraints = three_asset_market
        frontier = generate_efficient_frontier(
            assets=assets,
            cov_matrix=cov,
            expected_returns=exp_returns,
            constraints=constraints,
            target_count=10,
        )

        assert frontier.is_complete
        assert frontier.requested_count == 10
        assert frontier.successful_count == 10
        assert frontier.failed_count == 0
        assert len(frontier.points) == 10
        assert frontier.global_minimum_variance is not None
        assert frontier.global_minimum_variance.is_feasible

        targets = [p.target_return for p in frontier.points]
        assert targets == sorted(targets)

        for p in frontier.points:
            assert p.is_feasible
            assert p.status == OptimizationStatus.CONVERGED
            assert p.target_residual <= 1e-4
            assert math.isclose(sum(p.weights.values()), 1.0, abs_tol=1e-5)

    def test_dominance_classification(self, three_asset_market):
        """Verify points below GMV return are classified as dominated_inefficient, and above as efficient."""
        assets, exp_returns, cov, constraints = three_asset_market
        frontier = generate_efficient_frontier(
            assets=assets,
            cov_matrix=cov,
            expected_returns=exp_returns,
            constraints=constraints,
            target_count=15,
        )

        gmv_return = frontier.global_minimum_variance.expected_return

        for p in frontier.points:
            if p.actual_return < gmv_return - 1e-5:
                assert p.classification == "dominated_inefficient"
            else:
                assert p.classification == "efficient"

    def test_partial_infeasible_targets_reported_without_fabrication(self, three_asset_market):
        """User-requested targets outside feasible range must be explicitly reported as infeasible."""
        assets, exp_returns, cov, constraints = three_asset_market
        custom_targets = [0.05, 0.10, 0.15, 0.20, 0.30]

        frontier = generate_efficient_frontier(
            assets=assets,
            cov_matrix=cov,
            expected_returns=exp_returns,
            constraints=constraints,
            target_returns=custom_targets,
        )

        assert frontier.requested_count == 5
        assert frontier.successful_count == 3
        assert frontier.failed_count == 2
        assert not frontier.is_complete

        p_low = frontier.points[0]
        assert p_low.target_return == 0.05
        assert not p_low.is_feasible
        assert p_low.classification == "infeasible"
        assert p_low.weights == {}

        p_high = frontier.points[4]
        assert p_high.target_return == 0.30
        assert not p_high.is_feasible
        assert p_high.classification == "infeasible"
        assert p_high.weights == {}

        assert frontier.points[1].is_feasible
        assert len(frontier.points[1].weights) == 3


# =====================================================================
# 4. Portfolio Comparison & Cross-Currency Safeguard Tests
# =====================================================================

class TestPortfolioComparisonAndSafeguards:
    """Tests for multi-portfolio comparison and currency isolation."""

    @pytest.fixture
    def registered_us_dataset(self):
        """Register valid 3-asset US equity dataset."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
        csv_lines = ["date,ticker,market,close,currency,open,high,low,volume"]
        tickers = ["AAPL", "MSFT", "GOOGL"]
        base_prices = {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 140.0}

        for d_idx, d in enumerate(dates):
            for t in tickers:
                p = base_prices[t] + d_idx * 1.5
                csv_lines.append(f"{d},{t},US,{p},USD,{p-1},{p+2},{p-2},1000000")

        csv_bytes = "\n".join(csv_lines).encode("utf-8")
        meta = register_csv_dataset(csv_bytes, "US_Equities_Test.csv")
        return meta["dataset_id"]

    @pytest.fixture
    def registered_mixed_dataset(self):
        """Register dataset with both US and PSX equities."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
        csv_lines = ["date,ticker,market,close,currency,open,high,low,volume"]

        for d_idx, d in enumerate(dates):
            p_us = 100.0 + d_idx
            p_pk = 50.0 + d_idx
            csv_lines.append(f"{d},AAPL,US,{p_us},USD,{p_us-1},{p_us+1},{p_us-1},100000")
            csv_lines.append(f"{d},OGDC,PSX,{p_pk},PKR,{p_pk-1},{p_pk+1},{p_pk-1},100000")

        csv_bytes = "\n".join(csv_lines).encode("utf-8")
        meta = register_csv_dataset(csv_bytes, "Mixed_Currency_Test.csv")
        return meta["dataset_id"]

    def test_portfolio_comparison_execution(self, registered_us_dataset):
        """Compare GMV, Max Sharpe, and Equal-Weight on identical historical dataset."""
        portfolio = PortfolioDefinition(
            name="US Tech Trio",
            dataset_id=registered_us_dataset,
            assets=["AAPL:US", "MSFT:US", "GOOGL:US"],
            constraints=InvestmentConstraintsModel(),
        )

        req = PortfolioComparisonRequest(
            portfolio=portfolio,
            include_gmv=True,
            include_max_sharpe=True,
            include_equal_weight=True,
            custom_portfolios={"Custom 50-30-20": {"AAPL:US": 0.5, "MSFT:US": 0.3, "GOOGL:US": 0.2}},
        )

        resp = execute_portfolio_comparison(req)
        assert resp.is_success
        assert len(resp.portfolios) == 4

        names = [p.name for p in resp.portfolios]
        assert "Global Minimum Variance" in names
        assert "Maximum Sharpe Ratio" in names
        assert "Equal Weight" in names
        assert "Custom 50-30-20" in names

        for p in resp.portfolios:
            assert p.is_feasible
            assert p.metrics.is_fully_invested
            assert p.risk_summary is not None
            assert p.risk_summary.observation_count == resp.date_coverage["common_observation_count"] - 1

    def test_cross_currency_safeguard_rejection(self, registered_mixed_dataset):
        """Multi-currency portfolio must be rejected cleanly without fabrication or mock FX."""
        portfolio = PortfolioDefinition(
            name="Cross Currency Test",
            dataset_id=registered_mixed_dataset,
            assets=["AAPL:US", "OGDC:PSX"],
            constraints=InvestmentConstraintsModel(),
        )

        frontier_req = EfficientFrontierRequest(portfolio=portfolio)
        resp_frontier = execute_efficient_frontier(frontier_req)
        assert not resp_frontier.is_success
        assert any("cross-currency" in err.lower() for err in resp_frontier.errors)

        comp_req = PortfolioComparisonRequest(portfolio=portfolio)
        resp_comp = execute_portfolio_comparison(comp_req)
        assert not resp_comp.is_success
        assert any("cross-currency" in err.lower() for err in resp_comp.errors)


# =====================================================================
# 5. API Route Integration Tests
# =====================================================================

class TestAPIRouteIntegration:
    """HTTP endpoint integration tests for efficient frontier and comparison routes."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def us_dataset_id(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
        csv_lines = ["date,ticker,market,close,currency,open,high,low,volume"]
        prices = {
            "AAPL": [100.0, 102.0, 101.0, 104.0, 106.0, 105.0, 108.0, 110.0, 109.0, 112.0],
            "MSFT": [200.0, 201.0, 203.0, 202.0, 205.0, 207.0, 206.0, 209.0, 211.0, 215.0],
        }
        for d_idx, d in enumerate(dates):
            for t in ["AAPL", "MSFT"]:
                p = prices[t][d_idx]
                csv_lines.append(f"{d},{t},US,{p},USD,{p-1},{p+1},{p-1},100000")
        meta = register_csv_dataset("\n".join(csv_lines).encode("utf-8"), "API_Test_DS.csv")
        return meta["dataset_id"]

    def test_api_efficient_frontier_success(self, client, us_dataset_id):
        """POST /api/v1/portfolios/efficient-frontier returns 200 with typed response."""
        payload = {
            "portfolio": {
                "name": "API Frontier Portfolio",
                "dataset_id": us_dataset_id,
                "assets": ["AAPL:US", "MSFT:US"],
                "constraints": {
                    "default_min_weight": 0.0,
                    "default_max_weight": 1.0,
                    "target_total_weight": 1.0,
                },
            },
            "target_count": 5,
            "risk_free_rate": 0.02,
        }

        resp = client.post("/api/v1/portfolios/efficient-frontier", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_success"]
        assert len(data["points"]) == 5
        assert data["global_minimum_variance"] is not None
        assert data["currency"] == "USD"

    def test_api_efficient_frontier_dataset_not_found(self, client):
        """POST /api/v1/portfolios/efficient-frontier with missing dataset returns 404."""
        payload = {
            "portfolio": {
                "name": "Ghost Portfolio",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
                "assets": ["AAPL:US", "MSFT:US"],
            },
            "target_count": 5,
        }
        resp = client.post("/api/v1/portfolios/efficient-frontier", json=payload)
        assert resp.status_code == 404

    def test_api_portfolio_comparison_success(self, client, us_dataset_id):
        """POST /api/v1/portfolios/compare returns 200 with comparative analysis."""
        payload = {
            "portfolio": {
                "name": "API Comparison Portfolio",
                "dataset_id": us_dataset_id,
                "assets": ["AAPL:US", "MSFT:US"],
            },
            "include_gmv": True,
            "include_equal_weight": True,
        }

        resp = client.post("/api/v1/portfolios/compare", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_success"]
        assert len(data["portfolios"]) >= 2
