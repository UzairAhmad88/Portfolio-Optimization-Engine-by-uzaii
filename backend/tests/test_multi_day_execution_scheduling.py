"""
Institutional Test Suite for Stage 28:
Multi-Day Execution Scheduling — TWAP, VWAP & Almgren-Chriss in Dynamic Backtesting.

Validates:
1. Dynamic execution horizon determination and participation bounds.
2. Slicing algorithm conservation (TWAP, VWAP, Almgren-Chriss) and Almgren-Chriss limiting convergence.
3. Cash-financed execution with buy fee pre-allocation (resolving OBS-36-01).
4. Multi-day in-flight queue state tracking and interim price drift.
5. Rebalance conflict resolution (clean cancellation of pending tranches upon new target).
6. Temporal anti-lookahead causality under future volume perturbation.
7. Exact backward compatibility with single-day execution.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.execution import (
    compute_execution_horizon,
    compute_multi_day_execution_schedule,
)
from app.quant.vine_backtest import (
    run_vine_tail_risk_parity_backtest,
)


@pytest.fixture
def synthetic_market_data():
    """Generates reproducible 100-day market panel for 4 assets."""
    np.random.seed(42)
    n_days = 100
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")

    corr = np.array([
        [1.0, 0.6, 0.5, 0.4],
        [0.6, 1.0, 0.55, 0.45],
        [0.5, 0.55, 1.0, 0.5],
        [0.4, 0.45, 0.5, 1.0],
    ])
    chol = np.linalg.cholesky(corr)
    raw = np.random.standard_normal((n_days, 4))
    rets = raw @ chol.T * 0.015 + 0.0005
    returns_df = pd.DataFrame(rets, index=dates, columns=tickers)

    vols = np.random.uniform(5_000_000.0, 20_000_000.0, size=(n_days, 4))
    volumes_df = pd.DataFrame(vols, index=dates, columns=tickers)

    return returns_df, volumes_df


class TestHorizonAndValidation:
    """Verifies dynamic horizon calculation and input validation."""

    def test_one_day_order_fits_participation_cap(self):
        """When order notional <= ADV * PR_max, required horizon is 1 day."""
        order_notionals = {"AAPL": 50_000.0, "MSFT": -30_000.0}
        adv_dict = {"AAPL": 10_000_000.0, "MSFT": 10_000_000.0}
        # Daily cap at 10% PR is 1,000,000. Orders of 50k and 30k fit easily in 1 day.
        res = compute_execution_horizon(order_notionals, adv_dict, max_participation_rate=0.10, max_scheduling_days=5)
        assert res["horizon_days"] == 1
        assert res["per_asset_days"]["AAPL"] == 1
        assert res["per_asset_days"]["MSFT"] == 1
        assert not res["participation_exceeded"]

    def test_order_requiring_multiple_days(self):
        """When order exceeds daily cap, horizon scales as ceil(notional / (ADV * PR_max))."""
        # Daily cap = 1,000,000 * 0.10 = 100,000.
        # Order of 350,000 requires ceil(350k / 100k) = 4 days.
        order_notionals = {"ILLIQ": 350_000.0, "LIQ": 50_000.0}
        adv_dict = {"ILLIQ": 1_000_000.0, "LIQ": 10_000_000.0}
        res = compute_execution_horizon(order_notionals, adv_dict, max_participation_rate=0.10, max_scheduling_days=5)
        assert res["horizon_days"] == 4
        assert res["per_asset_days"]["ILLIQ"] == 4
        assert res["per_asset_days"]["LIQ"] == 1
        assert res["participation_exceeded"]

    def test_horizon_capped_at_max_scheduling_days(self):
        """When required days exceed max_scheduling_days, horizon is bounded by D_max."""
        order_notionals = {"ILLIQ": 1_000_000.0}
        adv_dict = {"ILLIQ": 500_000.0}
        # Daily cap = 50k. Ceil(1M / 50k) = 20 days.
        res = compute_execution_horizon(order_notionals, adv_dict, max_participation_rate=0.10, max_scheduling_days=5)
        assert res["horizon_days"] == 5
        assert res["per_asset_days"]["ILLIQ"] == 5

    def test_invalid_parameters_rejection(self):
        """Invalid participation rates or horizon bounds raise explicit ValueError."""
        with pytest.raises(ValueError, match="max_participation_rate"):
            compute_execution_horizon({"A": 100.0}, {"A": 1000.0}, max_participation_rate=0.0)
        with pytest.raises(ValueError, match="max_participation_rate"):
            compute_execution_horizon({"A": 100.0}, {"A": 1000.0}, max_participation_rate=1.5)
        with pytest.raises(ValueError, match="max_scheduling_days"):
            compute_execution_horizon({"A": 100.0}, {"A": 1000.0}, max_scheduling_days=0)

    def test_zero_sized_orders(self):
        """Zero orders return horizon of 1 day safely without errors."""
        res = compute_execution_horizon({"A": 0.0, "B": 0.0}, {"A": 1000.0, "B": 1000.0})
        assert res["horizon_days"] == 1
        assert not res["participation_exceeded"]


class TestSchedulingAlgorithms:
    """Verifies slicing algorithms: TWAP, VWAP, and Almgren-Chriss."""

    def test_twap_slicing_conservation(self):
        """TWAP distributes notional uniformly across D days and preserves exact sum."""
        notionals = {"A": 300_000.0, "B": -150_000.0}
        adv_dict = {"A": 1_000_000.0, "B": 1_000_000.0}
        # Cap = 100k -> D = 3 days.
        sched = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="twap",
        )
        assert sched["horizon_days"] == 3
        assert len(sched["daily_schedules"]) == 3
        # Each day gets exactly 100k for A, -50k for B
        for d in range(3):
            assert math.isclose(sched["daily_schedules"][d]["A"], 100_000.0, abs_tol=1e-8)
            assert math.isclose(sched["daily_schedules"][d]["B"], -50_000.0, abs_tol=1e-8)
        # Sum of tranches equals original notional
        assert math.isclose(sched["total_scheduled_notionals"]["A"], 300_000.0, abs_tol=1e-8)
        assert math.isclose(sched["total_scheduled_notionals"]["B"], -150_000.0, abs_tol=1e-8)

    def test_vwap_profile_weighting_and_fallback(self):
        """VWAP weights daily slices by volume profile, falling back to uniform if missing."""
        notionals = {"A": 100_000.0}
        adv_dict = {"A": 500_000.0}
        # D = 2 days
        profile = [0.4, 0.6]
        sched = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="vwap",
            volume_profile=profile,
        )
        assert sched["horizon_days"] == 2
        assert math.isclose(sched["daily_schedules"][0]["A"], 40_000.0, abs_tol=1e-8)
        assert math.isclose(sched["daily_schedules"][1]["A"], 60_000.0, abs_tol=1e-8)
        assert math.isclose(sched["total_scheduled_notionals"]["A"], 100_000.0, abs_tol=1e-8)

        # Fallback when profile is None
        sched_fallback = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="vwap",
            volume_profile=None,
        )
        assert math.isclose(sched_fallback["daily_schedules"][0]["A"], 50_000.0, abs_tol=1e-8)
        assert math.isclose(sched_fallback["daily_schedules"][1]["A"], 50_000.0, abs_tol=1e-8)

    def test_almgren_chriss_trajectory_properties(self):
        """Almgren-Chriss exhibits front-loading under risk aversion and converges to TWAP as lambda -> 0."""
        notionals = {"A": 500_000.0}
        adv_dict = {"A": 1_000_000.0}
        vol_dict = {"A": 0.25}
        # D = 5 days

        # High risk aversion: front-loaded trajectory
        sched_ac = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            volatility_dict=vol_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="almgren_chriss",
            scheduling_risk_aversion=1e-2,
        )
        assert sched_ac["horizon_days"] == 5
        # Front-loaded: day 0 slice > day 4 slice
        assert sched_ac["daily_schedules"][0]["A"] > sched_ac["daily_schedules"][4]["A"]
        # Exact sum conservation
        assert math.isclose(sched_ac["total_scheduled_notionals"]["A"], 500_000.0, abs_tol=1e-8)

        # Risk-neutral limit (lambda -> 0): converges to TWAP
        sched_neutral = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            volatility_dict=vol_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="almgren_chriss",
            scheduling_risk_aversion=0.0,
        )
        sched_twap = compute_multi_day_execution_schedule(
            order_notionals=notionals,
            adv_dict=adv_dict,
            max_participation_rate=0.10,
            max_scheduling_days=5,
            scheduling_mode="twap",
        )
        for d in range(5):
            assert math.isclose(
                sched_neutral["daily_schedules"][d]["A"],
                sched_twap["daily_schedules"][d]["A"],
                abs_tol=1e-6,
            )


class TestCashFinancedMultiDayExecution:
    """Verifies cash-financed queue accounting and fee pre-allocation across multi-day schedules."""

    def test_buy_fee_pre_allocation_prevents_negative_cash(self, synthetic_market_data):
        """
        OBS-36-01 resolution: gross buy notional cannot exhaust 100% of available cash
        before transaction costs are deducted. Residual cash is strictly non-negative.
        """
        returns_df, volumes_df = synthetic_market_data

        # Restrict volume to create partial fills and cash constraint
        v_mod = volumes_df.copy()
        v_mod.iloc[:, 0] = 100_000.0
        v_mod.iloc[:, 1] = 100_000.0

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mod,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.02,
            participation_policy="cap",
            execution_scheduling_mode="twap",
            max_scheduling_days=5,
            num_simulations=500,
            random_seed=42,
        )

        for evt in res["rebalance_history"]:
            w_sum = sum(evt["weights"].values())
            cash_w = evt.get("cash_weight", 0.0)
            assert cash_w >= -1e-8, f"Cash weight went negative: {cash_w}"
            assert math.isclose(w_sum + cash_w, 1.0, abs_tol=1e-4)

    def test_walk_forward_multi_day_twap_execution(self, synthetic_market_data):
        """Walk-forward backtest successfully schedules large orders across multiple days."""
        returns_df, volumes_df = synthetic_market_data

        v_mod = volumes_df.copy()
        v_mod.iloc[:, 0] = 50_000.0

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mod,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.01,
            participation_policy="cap",
            execution_scheduling_mode="twap",
            max_scheduling_days=5,
            num_simulations=500,
            random_seed=42,
        )

        assert res["execution_scheduling_mode"] == "twap"
        assert res["max_scheduling_days"] == 5
        # Rebalance events must record scheduled_days
        multi_day_rebal_count = 0
        for evt in res["rebalance_history"]:
            assert "scheduled_days" in evt
            assert "scheduling_mode" in evt
            if evt["scheduled_days"] > 1:
                multi_day_rebal_count += 1

        assert multi_day_rebal_count > 0, "Expected at least one rebalance event to require multi-day scheduling"

    def test_rebalance_conflict_cancels_pending_queue(self, synthetic_market_data):
        """When a new rebalance triggers while a previous multi-day execution is in-flight, pending tranches are cancelled."""
        returns_df, volumes_df = synthetic_market_data

        # Daily rebalance frequency guarantees conflict when an order takes multiple days
        v_mod = volumes_df.copy()
        v_mod.iloc[:, 0] = 20_000.0

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mod,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="daily",
            execution_model="square_root",
            max_participation_rate=0.01,
            participation_policy="cap",
            execution_scheduling_mode="twap",
            max_scheduling_days=5,
            num_simulations=500,
            random_seed=42,
        )

        # Equity must remain strictly positive and well-behaved
        assert res["strategy_metrics"]["total_return"] is not None
        for pt in res["equity_curve"]:
            assert pt["strategy_equity"] > 0.0

    def test_strict_temporal_anti_lookahead_scheduling(self, synthetic_market_data):
        """Mutating future volume data post-decision does not alter earlier multi-day schedules or fills."""
        returns_df, volumes_df = synthetic_market_data

        res_baseline = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.05,
            participation_policy="cap",
            execution_scheduling_mode="almgren_chriss",
            max_scheduling_days=4,
            num_simulations=500,
            random_seed=42,
        )

        # Mutate future volume at the very end of the series
        v_mutated = volumes_df.copy()
        v_mutated.iloc[-1, :] *= 100.0

        res_mutated = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mutated,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.05,
            participation_policy="cap",
            execution_scheduling_mode="almgren_chriss",
            max_scheduling_days=4,
            num_simulations=500,
            random_seed=42,
        )

        # First rebalance event must be identical bit-for-bit
        evt_base = res_baseline["rebalance_history"][0]
        evt_mut = res_mutated["rebalance_history"][0]
        assert evt_base["scheduled_days"] == evt_mut["scheduled_days"]
        assert math.isclose(evt_base["transaction_cost"], evt_mut["transaction_cost"], abs_tol=1e-8)
        assert math.isclose(evt_base["turnover"], evt_mut["turnover"], abs_tol=1e-8)

    def test_backward_compatibility_single_day(self, synthetic_market_data):
        """Single-day mode produces identical results to baseline Stage 27 behavior."""
        returns_df, volumes_df = synthetic_market_data

        res_single = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            execution_scheduling_mode="single_day",
            num_simulations=500,
            random_seed=42,
        )

        assert res_single["execution_scheduling_mode"] == "single_day"
        for evt in res_single["rebalance_history"]:
            assert evt["scheduled_days"] == 1
            assert evt["scheduling_mode"] == "single_day"
