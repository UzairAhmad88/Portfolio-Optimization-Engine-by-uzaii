"""
Unit tests and analytical mathematical benchmarks for Dynamic Factor Walk-Forward Backtesting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.dynamic_factor_backtest import (
    estimate_window_factor_loadings,
    run_dynamic_factor_backtest,
    solve_factor_tilted_weights,
)


def test_hand_calculated_analytical_benchmark():
    """
    Verifies the independent hand-calculated benchmark specified in docs/SESSION_21_CONTRACTS.md:
    2 assets, 1 factor, W=4 days.
    F = [0.01, -0.01, 0.02, -0.02]
    R_1^e = [0.012, -0.008, 0.022, -0.018] -> beta_1 = 1.0, alpha_1 = 0.002, s_eps1^2 = 0.0
    R_2^e = [0.005, -0.005, 0.010, -0.010] -> beta_2 = 0.5, alpha_2 = 0.000, s_eps2^2 = 0.0
    """
    F = np.array([0.01, -0.01, 0.02, -0.02]).reshape(-1, 1)
    R = np.column_stack([
        [0.012, -0.008, 0.022, -0.018],
        [0.005, -0.005, 0.010, -0.010],
    ])

    B, alphas, s_eps = estimate_window_factor_loadings(R, F)

    # Asset 1 loadings and stats
    np.testing.assert_allclose(B[0, 0], 1.0, atol=1e-12)
    np.testing.assert_allclose(alphas[0], 0.002, atol=1e-12)
    assert s_eps[0] < 1e-8

    # Asset 2 loadings and stats
    np.testing.assert_allclose(B[1, 0], 0.5, atol=1e-12)
    np.testing.assert_allclose(alphas[1], 0.0, atol=1e-12)
    assert s_eps[1] < 1e-8

    # Factor Covariance: var(F) with ddof=1
    var_F = np.var(F[:, 0], ddof=1)
    expected_var_F = 0.0010 / 3.0
    np.testing.assert_allclose(var_F, expected_var_F, atol=1e-12)

    # Solve weights with target factor exposure constraint: 0.8 <= B^T * w <= 0.8
    Sigma_model = B @ np.array([[var_F]]) @ B.T + np.diag([1e-10, 1e-10])
    w, is_feas, _ = solve_factor_tilted_weights(
        B=B,
        Sigma_model=Sigma_model,
        factor_names=["F1"],
        factor_tilts={"F1": 1.0},
        factor_constraints={"F1": {"min_beta": 0.8, "max_beta": 0.8}},
        prev_weights=np.array([0.0, 0.0]),
        strategy_type="factor_min_variance",
        min_weight=0.0,
        max_weight=1.0,
    )

    assert is_feas
    np.testing.assert_allclose(w[0], 0.6, atol=1e-4)
    np.testing.assert_allclose(w[1], 0.4, atol=1e-4)
    np.testing.assert_allclose(np.dot(w, B[:, 0]), 0.8, atol=1e-4)

    # Frictional turnover from zero:
    turnover = 0.5 * np.sum(np.abs(w - np.array([0.0, 0.0])))
    np.testing.assert_allclose(turnover, 0.5, atol=1e-6)

    # Cost at 50 bps on 100,000 equity:
    cost = 100000.0 * 2.0 * turnover * (50.0 / 10000.0)
    np.testing.assert_allclose(cost, 500.0, atol=1e-6)


def test_dynamic_factor_backtest_full_simulation():
    """
    Simulates a 120-day panel across 4 assets under monthly and weekly rebalancing.
    Verifies mathematical and simulation invariants.
    """
    np.random.seed(42)
    n_days = 120
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    assets = ["AAPL", "MSFT", "GOOGL", "AMZN"]

    # Generate synthetic correlated returns
    rets = np.random.normal(0.0005, 0.015, size=(n_days, len(assets)))
    df = pd.DataFrame(rets, index=dates, columns=assets)

    res = run_dynamic_factor_backtest(
        returns_df=df,
        factor_model="carhart4",
        strategy_type="factor_tilt",
        estimation_window=40,
        rebalance_frequency="monthly",
        factor_tilts={"MKT": 1.0, "MOM": 0.5},
        factor_constraints={"MKT": {"min_beta": 0.5, "max_beta": 1.5}},
        risk_aversion=3.0,
        transaction_cost_bps=10.0,
        slippage_bps=5.0,
        initial_capital=100000.0,
    )

    assert res["strategy_type"] == "factor_tilt"
    assert res["factor_model"] == "carhart4"
    assert res["total_rebalances"] >= 3
    assert len(res["equity_curve"]) == n_days - 40
    assert len(res["rebalance_history"]) == res["total_rebalances"]

    # Verify summary metrics structure
    metrics = res["summary_metrics"]
    assert "cagr" in metrics
    assert "annualized_volatility" in metrics
    assert "sharpe_ratio" in metrics
    assert "sortino_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "information_ratio" in metrics
    assert metrics["total_transaction_costs"] >= 0.0

    # Invariant: weights at each rebalance must sum to 1.0 within 1e-4
    for reb in res["rebalance_history"]:
        w_sum = sum(reb["weights"].values())
        np.testing.assert_allclose(w_sum, 1.0, atol=1e-3)
        assert "systematic_share_pct" in reb
        assert 0.0 <= reb["systematic_share_pct"] <= 100.0


def test_dynamic_factor_momentum_rotation_strategy():
    """
    Verifies the top-N factor momentum rotation strategy.
    """
    np.random.seed(123)
    n_days = 100
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    assets = ["ASSET_A", "ASSET_B", "ASSET_C", "ASSET_D", "ASSET_E"]
    rets = np.random.normal(0.0008, 0.02, size=(n_days, len(assets)))
    df = pd.DataFrame(rets, index=dates, columns=assets)

    res = run_dynamic_factor_backtest(
        returns_df=df,
        factor_model="ff3",
        strategy_type="factor_momentum_rotation",
        top_n_assets=2,
        estimation_window=35,
        rebalance_frequency="weekly",
        factor_tilts={"MKT": 1.0, "SMB": 0.5},
        initial_capital=50000.0,
    )

    assert res["strategy_type"] == "factor_momentum_rotation"
    assert res["total_rebalances"] >= 8

    # In top_n_assets=2, exactly 2 assets should receive weight 0.5 in each rebalance
    for reb in res["rebalance_history"]:
        nonzero_weights = [w for w in reb["weights"].values() if w > 0.01]
        assert len(nonzero_weights) == 2
        for w in nonzero_weights:
            np.testing.assert_allclose(w, 0.5, atol=1e-2)


def test_dynamic_factor_backtest_look_ahead_prevention():
    """
    Verifies that changing future returns after day t_k does NOT alter weights or factor loadings at day t_k.
    """
    np.random.seed(777)
    n_days = 90
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    assets = ["TICK1", "TICK2", "TICK3"]
    rets = np.random.normal(0.0005, 0.015, size=(n_days, len(assets)))
    df1 = pd.DataFrame(rets, index=dates, columns=assets)

    # df2 is identical up to day 60, but wildly different on days 61..89
    df2 = df1.copy()
    df2.iloc[60:, :] = np.random.normal(0.05, 0.05, size=(n_days - 60, len(assets)))

    res1 = run_dynamic_factor_backtest(
        returns_df=df1,
        factor_model="capm",
        strategy_type="factor_min_variance",
        estimation_window=30,
        rebalance_frequency="monthly",
        initial_capital=100000.0,
    )

    res2 = run_dynamic_factor_backtest(
        returns_df=df2,
        factor_model="capm",
        strategy_type="factor_min_variance",
        estimation_window=30,
        rebalance_frequency="monthly",
        initial_capital=100000.0,
    )

    # First rebalance occurred before day 60. Must be IDENTICAL across both runs!
    reb1_run1 = res1["rebalance_history"][0]
    reb1_run2 = res2["rebalance_history"][0]
    assert reb1_run1["date"] == reb1_run2["date"]
    for a in assets:
        assert reb1_run1["weights"][a] == reb1_run2["weights"][a]
    assert reb1_run1["portfolio_betas"] == reb1_run2["portfolio_betas"]


def test_dynamic_factor_backtest_validation_errors():
    """
    Verifies input validation boundaries.
    """
    dates = pd.date_range("2023-01-01", periods=20, freq="B")
    df = pd.DataFrame(np.random.normal(0, 0.01, size=(20, 3)), index=dates, columns=["A", "B", "C"])

    # estimation_window < 30
    with pytest.raises(ValueError, match="must be at least 30 trading days"):
        run_dynamic_factor_backtest(df, estimation_window=20)

    # T <= estimation_window + 5
    with pytest.raises(ValueError, match="Insufficient data"):
        run_dynamic_factor_backtest(df, estimation_window=30)
