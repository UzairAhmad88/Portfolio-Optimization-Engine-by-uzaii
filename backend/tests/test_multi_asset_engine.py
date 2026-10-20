"""
Unit tests and analytical mathematical benchmarks for Multi-Asset Class Allocation,
Cash Drag Modeling, and Multi-Currency FX Hedging.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.multi_asset import (
    convert_local_returns_to_base,
    decompose_multi_asset_fx_risk,
    run_multi_asset_walk_forward_backtest,
    solve_multi_asset_allocation,
)


def test_multi_asset_hand_calculated_analytical_benchmark():
    """
    Verifies the independent hand-calculated benchmark specified in docs/SESSION_22_CONTRACTS.md:
    - 2 assets, 1 cash, 2 currencies (USD and EUR).
    - Asset 1 (Equity, USD): R_loc = [0.02, -0.01, 0.03, -0.02]
    - Asset 2 (Bond, EUR): R_loc = [0.005, 0.002, -0.001, 0.004]
    - Spot FX (EUR/USD): R_fx = [0.010, -0.015, 0.020, -0.005]
    - Carry EUR: (0.04 - 0.02) / 252 = 0.02 / 252
    - Cash: w_cash = 0.20, r_f = 0.03 -> R_cash = 0.03 / 252
    - w = [0.50, 0.30], w_cash = 0.20
    """
    R_loc = np.column_stack([
        [0.02, -0.01, 0.03, -0.02],
        [0.005, 0.002, -0.001, 0.004],
    ])
    fx_dict = {"EUR": np.array([0.010, -0.015, 0.020, -0.005], dtype=np.float64)}
    carry_dict = {"EUR": 0.02}

    # 1. Fully Hedged (h = 1.0)
    base_hedged, base_unhedged = convert_local_returns_to_base(
        local_returns=R_loc,
        asset_currencies=["USD", "EUR"],
        base_currency="USD",
        fx_returns=fx_dict,
        hedge_ratios={"EUR": 1.0},
        carry_rates=carry_dict,
    )

    # Asset 1 base return is identical to local USD return
    np.testing.assert_allclose(base_unhedged[0, 0], 0.020000, atol=1e-12)
    np.testing.assert_allclose(base_hedged[0, 0], 0.020000, atol=1e-12)

    # Asset 2 Period 1 Unhedged: (1 + 0.005)*(1 + 0.010) - 1 = 0.015050
    np.testing.assert_allclose(base_unhedged[0, 1], 0.015050, atol=1e-12)

    # Asset 2 Period 1 Hedged: 0.015050 - 1.0 * (0.010 - 0.02/252) = 0.005129365079...
    expected_carry = 0.02 / 252.0
    expected_hedged_2 = 0.015050 - (0.010 - expected_carry)
    np.testing.assert_allclose(base_hedged[0, 1], expected_hedged_2, atol=1e-12)

    # Portfolio Period 1 Return (Hedged vs Unhedged)
    r_cash_1 = 0.03 / 252.0
    w_risky = np.array([0.50, 0.30])
    w_cash = 0.20

    # Unhedged portfolio return at t=0
    port_unhedged_1 = float(np.dot(w_risky, base_unhedged[0, :])) + w_cash * r_cash_1
    expected_unhedged_1 = 0.50 * 0.020000 + 0.30 * 0.015050 + 0.20 * r_cash_1
    np.testing.assert_allclose(port_unhedged_1, expected_unhedged_1, atol=1e-12)

    # Hedged portfolio return at t=0
    port_hedged_1 = float(np.dot(w_risky, base_hedged[0, :])) + w_cash * r_cash_1
    expected_hedged_1 = 0.50 * 0.020000 + 0.30 * expected_hedged_2 + 0.20 * r_cash_1
    np.testing.assert_allclose(port_hedged_1, expected_hedged_1, atol=1e-12)

    # Cash drag on return
    fully_invested_ret = (0.50 * 0.02 + 0.30 * 0.015050) / 0.80
    expected_drag_1 = w_cash * (fully_invested_ret - r_cash_1)
    np.testing.assert_allclose(expected_drag_1, 0.00360494047619, atol=1e-10)


def test_multi_asset_fx_risk_decomposition():
    """
    Verifies that unhedged base variance decomposes into local asset variance,
    FX variance, and cross-covariance, summing exactly to 100%.
    """
    np.random.seed(42)
    T = 60
    r_loc = np.random.normal(0.0005, 0.01, size=(T, 2))
    fx_dict = {"EUR": np.random.normal(0.0001, 0.008, size=T)}

    _, base_unhedged = convert_local_returns_to_base(
        local_returns=r_loc,
        asset_currencies=["USD", "EUR"],
        base_currency="USD",
        fx_returns=fx_dict,
        hedge_ratios={"EUR": 0.0},
    )

    w = np.array([0.6, 0.4])
    decomp = decompose_multi_asset_fx_risk(
        weights=w,
        local_returns=r_loc,
        unhedged_base_returns=base_unhedged,
        asset_currencies=["USD", "EUR"],
        base_currency="USD",
        fx_returns=fx_dict,
        annualization_factor=252,
    )

    # Total variance must match analytical sum
    total_var = decomp["total_unhedged_variance"]
    sum_components = (
        decomp["asset_local_variance"]
        + decomp["fx_currency_variance"]
        + decomp["cross_covariance"]
    )
    np.testing.assert_allclose(total_var, sum_components, atol=1e-10)
    assert decomp["asset_risk_share_pct"] + decomp["fx_risk_share_pct"] == pytest.approx(100.0, abs=1e-2)


def test_multi_asset_hierarchical_optimization_solver():
    """
    Verifies multi-asset optimization under explicit asset class limits and cash bounds.
    """
    expected_returns = np.array([0.12, 0.10, 0.05, 0.04])  # 2 Equities, 2 Bonds
    cov_matrix = np.array([
        [0.04, 0.02, 0.005, 0.002],
        [0.02, 0.05, 0.004, 0.003],
        [0.005, 0.004, 0.01, 0.005],
        [0.002, 0.003, 0.005, 0.012],
    ])
    asset_classes = ["Equity", "Equity", "Fixed Income", "Fixed Income"]

    class_limits = {
        "Equity": {"min_weight": 0.30, "max_weight": 0.60},
        "Fixed Income": {"min_weight": 0.20, "max_weight": 0.50},
    }

    w_risky, w_cash, is_feas, _ = solve_multi_asset_allocation(
        expected_returns=expected_returns,
        covariance_matrix=cov_matrix,
        asset_classes=asset_classes,
        asset_class_limits=class_limits,
        min_cash_weight=0.05,
        max_cash_weight=0.20,
        risk_free_rate=0.03,
        objective="max_sharpe",
    )

    assert is_feas
    # Budget invariant: sum(w_risky) + w_cash == 1.0
    total_budget = float(np.sum(w_risky) + w_cash)
    np.testing.assert_allclose(total_budget, 1.0, atol=1e-6)

    # Cash bounds
    assert 0.05 - 1e-6 <= w_cash <= 0.20 + 1e-6

    # Asset class group constraints
    equity_sum = float(w_risky[0] + w_risky[1])
    fi_sum = float(w_risky[2] + w_risky[3])

    assert 0.30 - 1e-5 <= equity_sum <= 0.60 + 1e-5
    assert 0.20 - 1e-5 <= fi_sum <= 0.50 + 1e-5


def test_multi_asset_walk_forward_simulation_and_lookahead_bias():
    """
    Executes walk-forward simulation across 100 days.
    Verifies that mutating out-of-sample data does not change in-sample allocations.
    """
    np.random.seed(123)
    T = 90
    dates = pd.date_range("2023-01-01", periods=T, freq="B")
    tickers = ["SPY", "QQQ", "TLT", "AGG"]
    asset_classes = ["Equity", "Equity", "Fixed Income", "Fixed Income"]
    asset_currencies = ["USD", "USD", "USD", "USD"]

    rets = np.random.normal(0.0004, 0.012, size=(T, 4))
    df_clean = pd.DataFrame(rets, index=dates, columns=tickers)

    res_1 = run_multi_asset_walk_forward_backtest(
        local_returns_df=df_clean,
        asset_classes=asset_classes,
        asset_currencies=asset_currencies,
        base_currency="USD",
        estimation_window=30,
        rebalance_frequency="monthly",
        min_cash_weight=0.05,
        max_cash_weight=0.15,
        objective="min_variance",
    )

    assert res_1["summary"]["total_rebalances"] >= 2
    assert res_1["summary"]["final_equity"] > 0
    assert len(res_1["equity_curve"]) == T - 30

    # Mutate out-of-sample data (the very last 10 days)
    df_mutated = df_clean.copy()
    df_mutated.iloc[-10:, :] += 0.05

    res_2 = run_multi_asset_walk_forward_backtest(
        local_returns_df=df_mutated,
        asset_classes=asset_classes,
        asset_currencies=asset_currencies,
        base_currency="USD",
        estimation_window=30,
        rebalance_frequency="monthly",
        min_cash_weight=0.05,
        max_cash_weight=0.15,
        objective="min_variance",
    )

    # Compare first rebalance weights (they MUST be identical!)
    first_rebal_1 = res_1["rebalance_history"][0]["risky_weights"]
    first_rebal_2 = res_2["rebalance_history"][0]["risky_weights"]

    for tkr in tickers:
        np.testing.assert_allclose(first_rebal_1[tkr], first_rebal_2[tkr], atol=1e-12)


def test_multi_asset_insufficient_history_rejection():
    """Verifies that estimation window < 20 or insufficient data raises ValueError."""
    df = pd.DataFrame(np.random.normal(0, 0.01, size=(25, 2)), columns=["A", "B"])
    with pytest.raises(ValueError, match="must be at least 20"):
        run_multi_asset_walk_forward_backtest(
            local_returns_df=df,
            asset_classes=["Equity", "Bond"],
            asset_currencies=["USD", "USD"],
            estimation_window=10,
        )

    with pytest.raises(ValueError, match="Insufficient history"):
        run_multi_asset_walk_forward_backtest(
            local_returns_df=df,
            asset_classes=["Equity", "Bond"],
            asset_currencies=["USD", "USD"],
            estimation_window=22,
        )
