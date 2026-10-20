"""
Unit, Mathematical, and Anti-Look-Ahead Test Suite for Dynamic Walk-Forward
Vine Copula Tail Risk Parity (TRP) Backtesting Engine.
"""

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.vine_backtest import (
    run_vine_tail_risk_parity_backtest,
    _is_rebalance_trigger,
)


@pytest.fixture
def synthetic_returns_df() -> pd.DataFrame:
    """Generates 180 days of realistic synthetic correlated equity returns for 3 assets."""
    rng = np.random.default_rng(101)
    T, d = 180, 3
    dates = pd.date_range("2024-01-01", periods=T, freq="B")
    corr = np.array([
        [1.0, 0.6, 0.3],
        [0.6, 1.0, 0.4],
        [0.3, 0.4, 1.0],
    ])
    chol = np.linalg.cholesky(corr)
    raw_rets = (rng.normal(0.0005, 0.015, size=(T, d)) @ chol.T)
    return pd.DataFrame(raw_rets, index=dates, columns=["AAPL", "MSFT", "GOOGL"])


def test_anti_lookahead_future_data_mutation(synthetic_returns_df):
    """
    STRICT CHRONOLOGICAL INVARIANCE TEST:
    Verifies that mutating market returns strictly AFTER a historical rebalance cutoff
    does NOT alter past allocations, weights, turnover, or tail risk estimates.
    """
    df_clean = synthetic_returns_df.copy()
    W = 60

    # 1. Run baseline backtest
    res_clean = run_vine_tail_risk_parity_backtest(
        returns_df=df_clean,
        vine_type="c_vine",
        estimation_window=W,
        rebalance_frequency="monthly",
        num_simulations=1000,
        random_seed=42,
    )

    rebal_history = res_clean["rebalance_history"]
    assert len(rebal_history) >= 3, "Expected at least 3 rebalances in 180 days"

    # Select the second rebalance date as the cutoff
    cutoff_idx = 1
    cutoff_rebal = rebal_history[cutoff_idx]
    cutoff_date = cutoff_rebal["date"]

    # 2. Mutate returns strictly AFTER the cutoff date
    df_mutated = df_clean.copy()
    future_mask = df_mutated.index > pd.to_datetime(cutoff_date)
    # Add large shocks to all assets after cutoff date
    df_mutated.loc[future_mask, :] = df_mutated.loc[future_mask, :] * 4.0 - 0.05

    # 3. Rerun backtest with identical seed and parameters
    res_mutated = run_vine_tail_risk_parity_backtest(
        returns_df=df_mutated,
        vine_type="c_vine",
        estimation_window=W,
        rebalance_frequency="monthly",
        num_simulations=1000,
        random_seed=42,
    )

    mut_history = res_mutated["rebalance_history"]

    # Assert all rebalances AT or BEFORE cutoff date are numerically identical
    for k in range(cutoff_idx + 1):
        clean_event = rebal_history[k]
        mut_event = mut_history[k]

        assert clean_event["date"] == mut_event["date"]
        assert clean_event["training_window_start"] == mut_event["training_window_start"]
        assert clean_event["training_window_end"] == mut_event["training_window_end"]

        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            w_clean = clean_event["weights"][ticker]
            w_mut = mut_event["weights"][ticker]
            assert abs(w_clean - w_mut) < 1e-6, (
                f"Look-ahead violation at rebalance {k} on {clean_event['date']}: "
                f"clean={w_clean}, mut={w_mut}"
            )

        assert abs(clean_event["turnover"] - mut_event["turnover"]) < 1e-6
        assert abs(clean_event["portfolio_cvar"] - mut_event["portfolio_cvar"]) < 1e-6

    # Realized equity curve AFTER cutoff date must diverge due to mutated market returns
    equity_clean = [pt["strategy_equity"] for pt in res_clean["equity_curve"]]
    equity_mut = [pt["strategy_equity"] for pt in res_mutated["equity_curve"]]
    assert equity_clean[-1] != equity_mut[-1], "Future mutations should alter realized future equity"


def test_training_window_chronological_boundaries(synthetic_returns_df):
    """
    Verifies that for every rebalance event, the training window strictly ends
    on the day prior to the rebalance decision date.
    """
    W = 60
    res = run_vine_tail_risk_parity_backtest(
        returns_df=synthetic_returns_df,
        vine_type="d_vine",
        estimation_window=W,
        rebalance_frequency="monthly",
        num_simulations=1000,
        random_seed=42,
    )

    dates_series = list(synthetic_returns_df.index)

    for event in res["rebalance_history"]:
        rebal_dt = pd.to_datetime(event["date"])
        train_start_dt = pd.to_datetime(event["training_window_start"])
        train_end_dt = pd.to_datetime(event["training_window_end"])

        # Strict ordering: start < end < rebal
        assert train_start_dt < train_end_dt < rebal_dt
        # Rebalance date cannot equal or be before training end date
        assert train_end_dt < rebal_dt

        # Count days between start and end
        window_days = [d for d in dates_series if train_start_dt <= d <= train_end_dt]
        assert len(window_days) == W, f"Expected exactly {W} trading days in estimation window, got {len(window_days)}"


def test_analytical_turnover_and_transaction_cost_benchmark():
    """
    Hand-calculated benchmark:
    Let w_pre = [0.5, 0.5] and w_target = [0.7, 0.3].
    Turnover = 0.5 * (|0.7 - 0.5| + |0.3 - 0.5|) = 0.5 * (0.2 + 0.2) = 0.20 (20%).
    With V = 100,000, bps = 15.0 (0.0015):
    Traded notional = 2 * 0.20 * 100,000 = 40,000.
    Cost = 40,000 * 0.0015 = 60.00.
    Post-trade equity = 99,940.00.
    """
    w_pre = np.array([0.5, 0.5])
    w_target = np.array([0.7, 0.3])
    equity = 100000.0
    friction_rate = 15.0 / 10000.0

    turnover = float(0.5 * np.sum(np.abs(w_target - w_pre)))
    assert turnover == pytest.approx(0.20, abs=1e-8)

    traded_notional = 2.0 * turnover * equity
    assert traded_notional == pytest.approx(40000.0, abs=1e-8)

    cost = traded_notional * friction_rate
    assert cost == pytest.approx(60.00, abs=1e-8)

    post_eq = equity - cost
    assert post_eq == pytest.approx(99940.00, abs=1e-8)


def test_zero_friction_vs_positive_friction(synthetic_returns_df):
    """
    Verifies that zero friction yields zero costs and higher final equity
    than positive transaction costs.
    """
    res_zero = run_vine_tail_risk_parity_backtest(
        returns_df=synthetic_returns_df,
        vine_type="c_vine",
        estimation_window=60,
        rebalance_frequency="monthly",
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        num_simulations=1000,
        random_seed=42,
    )
    assert res_zero["strategy_metrics"]["total_transaction_costs"] == 0.0

    res_fric = run_vine_tail_risk_parity_backtest(
        returns_df=synthetic_returns_df,
        vine_type="c_vine",
        estimation_window=60,
        rebalance_frequency="monthly",
        transaction_cost_bps=20.0,
        slippage_bps=10.0,
        num_simulations=1000,
        random_seed=42,
    )
    assert res_fric["strategy_metrics"]["total_transaction_costs"] > 0.0
    assert res_fric["strategy_metrics"]["total_return"] < res_zero["strategy_metrics"]["total_return"]


def test_gross_vs_net_performance_metrics_accounting(synthetic_returns_df):
    """
    Verifies DEF-47-01: Gross vs Net performance metrics are distinct,
    properly computed, and economically consistent when friction is positive.
    """
    res = run_vine_tail_risk_parity_backtest(
        returns_df=synthetic_returns_df,
        vine_type="c_vine",
        estimation_window=60,
        rebalance_frequency="monthly",
        transaction_cost_bps=25.0,
        slippage_bps=15.0,
        num_simulations=1000,
        random_seed=42,
    )
    m = res["strategy_metrics"]
    
    # 1. Verification of field existence
    assert "total_return_gross" in m
    assert "total_return_net" in m
    assert "cagr_gross" in m
    assert "cagr_net" in m
    assert "annualized_volatility_gross" in m
    assert "annualized_volatility_net" in m
    assert "sharpe_ratio_gross" in m
    assert "sharpe_ratio_net" in m

    # 2. Under positive friction, gross return strictly exceeds net return
    assert m["total_return_gross"] > m["total_return_net"]
    assert m["cagr_gross"] > m["cagr_net"]

    # 3. Backward-compatible fields match net total return and CAGR
    assert m["total_return"] == m["total_return_net"]
    assert m["cagr"] == m["cagr_net"]

    # 4. Under positive friction, gross Sharpe strictly exceeds net Sharpe
    assert m["sharpe_ratio_gross"] > m["sharpe_ratio_net"]
    assert m["sharpe_ratio"] == m["sharpe_ratio_gross"]

    # 5. Volatilities are finite positive numbers
    assert m["annualized_volatility_gross"] > 0.0
    assert m["annualized_volatility_net"] > 0.0


def test_c_vine_and_d_vine_both_execute(synthetic_returns_df):
    """
    Verifies that both C-Vine and D-Vine backtesting modes execute cleanly
    and produce complete metrics and equity curves.
    """
    for vtype in ["c_vine", "d_vine"]:
        res = run_vine_tail_risk_parity_backtest(
            returns_df=synthetic_returns_df,
            vine_type=vtype,
            estimation_window=50,
            rebalance_frequency="monthly",
            num_simulations=1000,
            random_seed=42,
        )
        assert res["vine_type"] == vtype
        assert res["total_evaluation_days"] == 180 - 50
        assert res["total_rebalances"] >= 3
        assert len(res["equity_curve"]) == 180 - 50
        assert "sharpe_ratio" in res["strategy_metrics"]
        assert "cagr" in res["strategy_metrics"]
        assert "max_drawdown" in res["strategy_metrics"]


def test_validation_and_boundary_rejection(synthetic_returns_df):
    """
    Verifies that the backtest engine rejects invalid window lengths,
    insufficient total history, or single-asset inputs.
    """
    # 1. Single asset
    single_asset_df = synthetic_returns_df[["AAPL"]]
    with pytest.raises(ValueError, match="at least 2 distinct assets"):
        run_vine_tail_risk_parity_backtest(returns_df=single_asset_df, estimation_window=60)

    # 2. Window < 30
    with pytest.raises(ValueError, match="at least 30 trading days"):
        run_vine_tail_risk_parity_backtest(returns_df=synthetic_returns_df, estimation_window=20)

    # 3. Insufficient history
    short_df = synthetic_returns_df.iloc[:50]
    with pytest.raises(ValueError, match="too short for estimation window"):
        run_vine_tail_risk_parity_backtest(returns_df=short_df, estimation_window=50)
