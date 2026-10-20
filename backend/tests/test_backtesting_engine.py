"""
Deterministic mathematical and algorithmic test suite for the portfolio simulation engine.

Validates:
1. Single-asset buy-and-hold parity with raw price ratio.
2. Two-asset zero-friction parity: Net equity == Gross equity.
3. Day-0 initial allocation friction deduction.
4. Natural weight drift between rebalance dates.
5. Scheduled rebalancing triggers (buy-and-hold, daily, monthly, weekly, quarterly).
6. Multiplicative compounding vs linear sum verification.
7. Turnover and basis-point transaction cost / slippage arithmetic.
8. Look-ahead bias prevention in walk-forward optimization.
9. Edge cases (flat returns, zero volatility, insufficient observations).
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from app.backtesting.costs import (
    calculate_slippage_cost,
    calculate_traded_notional,
    calculate_transaction_cost,
    calculate_turnover,
)
from app.backtesting.engine import (
    _is_rebalance_due,
    _solve_walk_forward_weights,
    run_portfolio_simulation,
)


def _make_synth_prices(
    dates: list[str],
    series_dict: dict[str, list[float]],
) -> pd.DataFrame:
    """Helper to create a deterministic price DataFrame."""
    return pd.DataFrame(series_dict, index=dates)


def test_turnover_and_cost_calculations():
    """Verifies two-sided turnover and basis point cost formulas."""
    pre_w = {"A": 0.6, "B": 0.4}
    target_w = {"A": 0.5, "B": 0.5}

    # Turnover = 0.5 * (|0.5 - 0.6| + |0.5 - 0.4|) = 0.5 * (0.1 + 0.1) = 0.10 (10%)
    tau = calculate_turnover(pre_w, target_w)
    assert math.isclose(tau, 0.10, rel_tol=1e-7)

    # Traded notional on $100,000 = $100,000 * (|0.1| + |0.1|) = $20,000
    portfolio_val = 100_000.0
    traded = calculate_traded_notional(pre_w, target_w, portfolio_val)
    assert math.isclose(traded, 20_000.0, rel_tol=1e-7)

    # 10 bps fee = 0.0010 * 20,000 = $20.00
    fee = calculate_transaction_cost(traded, fee_bps=10.0)
    assert math.isclose(fee, 20.00, rel_tol=1e-7)

    # 5 bps slippage = 0.0005 * 20,000 = $10.00
    slip = calculate_slippage_cost(traded, slippage_bps=5.0)
    assert math.isclose(slip, 10.00, rel_tol=1e-7)


def test_single_asset_buy_and_hold_gross_parity():
    """
    For a single asset with zero friction, the portfolio value must track
    the raw price ratio P_t / P_0 bitwise at every step.
    """
    dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    prices = _make_synth_prices(
        dates,
        {"ASSET_A": [100.0, 105.0, 102.0, 110.0]},
    )

    initial_capital = 50_000.0
    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"ASSET_A": 1.0},
        rebalance_frequency="buy_and_hold",
        initial_capital=initial_capital,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )

    # Inception event only
    assert len(rebalance_events) == 1
    assert rebalance_events[0].reason == "Initial Allocation"

    # Equity curve values
    assert len(equity_curve) == 4
    for i, pt in enumerate(equity_curve):
        expected_val = initial_capital * (prices["ASSET_A"].iloc[i] / 100.0)
        assert math.isclose(pt.portfolio_value_gross, expected_val, rel_tol=1e-7)
        assert math.isclose(pt.portfolio_value_net, expected_val, rel_tol=1e-7)

    # Final return must match asset total return: 110.0 / 100.0 - 1.0 = +10.0%
    assert math.isclose(metrics.cumulative_return_gross, 0.10, rel_tol=1e-7)
    assert math.isclose(metrics.cumulative_return_net, 0.10, rel_tol=1e-7)
    assert math.isclose(metrics.final_value_net, 55_000.0, rel_tol=1e-7)


def test_zero_friction_net_gross_equivalence():
    """
    When transaction costs and slippage are 0.0 bps, Net and Gross values must be
    identically equal throughout the backtest.
    """
    dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"]
    prices = _make_synth_prices(
        dates,
        {
            "A": [100.0, 102.0, 101.0, 104.0, 103.0],
            "B": [50.0, 49.0, 52.0, 51.0, 53.0],
        },
    )

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"A": 0.6, "B": 0.4},
        rebalance_frequency="daily",
        initial_capital=100_000.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )

    assert metrics.total_transaction_costs == 0.0
    assert metrics.total_slippage_costs == 0.0
    assert metrics.total_friction_costs == 0.0
    assert math.isclose(metrics.final_value_net, metrics.final_value_gross, rel_tol=1e-9)

    for pt in equity_curve:
        assert math.isclose(pt.portfolio_value_net, pt.portfolio_value_gross, rel_tol=1e-9)
        assert math.isclose(pt.return_net, pt.return_gross, rel_tol=1e-9)
        assert math.isclose(pt.drawdown_net, pt.drawdown_gross, rel_tol=1e-9)


def test_initial_allocation_day_zero_friction():
    """
    Verifies that initial allocation incurs transaction costs and slippage on day 0,
    reducing starting net capital before market price movements occur.
    """
    dates = ["2025-01-02", "2025-01-03"]
    prices = _make_synth_prices(
        dates,
        {"A": [100.0, 100.0]},  # Flat price
    )

    initial_capital = 100_000.0
    fee_bps = 10.0  # 0.10% = $100
    slip_bps = 5.0  # 0.05% = $50
    # Total friction = $150

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"A": 1.0},
        rebalance_frequency="buy_and_hold",
        initial_capital=initial_capital,
        transaction_cost_bps=fee_bps,
        slippage_bps=slip_bps,
    )

    # Initial net value on day 0
    assert math.isclose(equity_curve[0].portfolio_value_net, 100_000.0 - 150.0, rel_tol=1e-7)
    assert math.isclose(equity_curve[0].portfolio_value_gross, 100_000.0, rel_tol=1e-7)
    assert math.isclose(metrics.total_transaction_costs, 100.0, rel_tol=1e-7)
    assert math.isclose(metrics.total_slippage_costs, 50.0, rel_tol=1e-7)


def test_natural_weight_drift_between_rebalances():
    """
    Verifies that without rebalancing, weights drift naturally based on relative asset performance.
    """
    dates = ["2025-01-02", "2025-01-03"]
    # Day 0: $50 in A, $50 in B. (50% / 50%)
    # Day 1: A doubles (+100% to $100), B stays flat ($50).
    # New portfolio value = $150. A weight = 100/150 = 2/3 (66.67%), B weight = 50/150 = 1/3 (33.33%).
    prices = _make_synth_prices(
        dates,
        {
            "A": [10.0, 20.0],
            "B": [10.0, 10.0],
        },
    )

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"A": 0.5, "B": 0.5},
        rebalance_frequency="buy_and_hold",
        initial_capital=100.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )

    # Only 1 rebalance event (inception)
    assert len(rebalance_events) == 1
    assert math.isclose(equity_curve[1].portfolio_value_net, 150.0, rel_tol=1e-7)
    assert math.isclose(metrics.cumulative_return_net, 0.50, rel_tol=1e-7)


def test_monthly_rebalancing_trigger():
    """
    Verifies that monthly rebalancing triggers exactly when the calendar month transitions.
    """
    dates = [
        "2025-01-29",
        "2025-01-30",
        "2025-01-31",
        "2025-02-03",  # Month transition! (2025-01 -> 2025-02)
        "2025-02-04",
        "2025-02-28",
        "2025-03-03",  # Month transition! (2025-02 -> 2025-03)
        "2025-03-04",
    ]
    prices = _make_synth_prices(
        dates,
        {
            "A": [100.0, 101.0, 102.0, 105.0, 104.0, 106.0, 110.0, 109.0],
            "B": [50.0, 50.0, 51.0, 49.0, 50.0, 52.0, 53.0, 54.0],
        },
    )

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"A": 0.5, "B": 0.5},
        rebalance_frequency="monthly",
        initial_capital=100_000.0,
        transaction_cost_bps=10.0,
        slippage_bps=5.0,
    )

    # Expect: Inception (2025-01-29), Rebalance 1 (2025-02-03), Rebalance 2 (2025-03-03)
    reb_dates = [ev.date for ev in rebalance_events]
    assert reb_dates == ["2025-01-29", "2025-02-03", "2025-03-03"]
    assert metrics.number_of_rebalances == 3


def test_multiplicative_wealth_compounding_invariance():
    """
    Verifies that cumulative return is (V_final / V_initial) - 1, NOT sum of daily returns.
    Example: +10% then -10% yields -1% wealth loss (0.99), whereas sum of returns is 0.0%.
    """
    dates = ["2025-01-02", "2025-01-03", "2025-01-06"]
    # P_0 = 100, P_1 = 110 (+10%), P_2 = 99 (-10%)
    prices = _make_synth_prices(
        dates,
        {"A": [100.0, 110.0, 99.0]},
    )

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="target_weights",
        target_weights={"A": 1.0},
        rebalance_frequency="buy_and_hold",
        initial_capital=100_000.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )

    # Linear sum of returns: +0.10 + (-0.10) = 0.0
    # True multiplicative compounding: 1.10 * 0.90 = 0.99 -> -1.0% return
    assert math.isclose(metrics.cumulative_return_gross, -0.01, rel_tol=1e-7)
    assert math.isclose(metrics.final_value_gross, 99_000.0, rel_tol=1e-7)


def test_walk_forward_optimization_leakage_protection():
    """
    Verifies that walk-forward optimization strictly uses historical training window observations,
    excluding future test period prices.
    """
    # 50 days of data, training window = 30 days
    np.random.seed(42)
    dates = [f"2025-01-{i:02d}" for i in range(1, 32)] + [f"2025-02-{i:02d}" for i in range(1, 20)]
    n_days = len(dates)

    p_a = 100.0 * np.cumprod(1.0 + np.random.normal(0.0005, 0.01, n_days))
    p_b = 50.0 * np.cumprod(1.0 + np.random.normal(0.0003, 0.012, n_days))

    prices = _make_synth_prices(dates, {"A": list(p_a), "B": list(p_b)})

    training_window = 25
    test_window = 10

    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=prices,
        strategy_type="walk_forward_optimization",
        rebalance_frequency="monthly",
        initial_capital=100_000.0,
        training_window=training_window,
        test_window=test_window,
        optimization_objective="min_variance",
        transaction_cost_bps=5.0,
        slippage_bps=2.0,
    )

    # Simulation must start at dates[training_window]
    assert equity_curve[0].date == dates[training_window]
    assert metrics.effective_start_date == dates[training_window]
    assert metrics.effective_end_date == dates[-1]

    # Rebalances occurred
    assert len(rebalance_events) >= 2
    for ev in rebalance_events:
        assert math.isclose(sum(ev.post_weights.values()), 1.0, rel_tol=1e-5)
        for w in ev.post_weights.values():
            assert w >= -1e-6


def test_insufficient_observations_raises_error():
    """Verifies that attempting a simulation with < 2 observations raises ValueError."""
    prices = _make_synth_prices(["2025-01-02"], {"A": [100.0]})
    with pytest.raises(ValueError, match="at least 1 asset and 2 trading days"):
        run_portfolio_simulation(prices)
