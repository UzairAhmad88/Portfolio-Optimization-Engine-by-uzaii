"""
Comprehensive Unit, Mathematical, Reconciliation, and Anti-Lookahead Test Suite
for Stage 30: Transaction Cost Analysis (TCA) and Slippage Performance Attribution.
"""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd
from pydantic import ValidationError

from app.quant.tca import (
    TradeFill,
    calculate_trade_slippage,
    calculate_opportunity_cost,
    compute_transaction_cost_analysis,
    reconcile_tca_with_backtest_costs,
)
from app.quant.vine_backtest import run_vine_tail_risk_parity_backtest
from app.copula.models import (
    TCACostMetrics,
    TCAEventMetrics,
    TCAProvenance,
    TCAReport,
    VineBacktestResponse,
    VineBacktestStrategyMetrics,
)


# ============================================================================
# 1. Mathematical Unit Tests: Slippage Sign & Price Improvement Conventions
# ============================================================================

def test_trade_slippage_signs_and_price_improvement():
    """
    Verify signed arrival slippage convention:
    Adverse execution produces positive cost.
    Price improvement produces negative cost.
    """
    arrival_p = 100.0
    notional = 50_000.0

    # 1. Buy Order with Adverse Slippage (fill_p > arrival_p)
    buy_adverse = calculate_trade_slippage(
        direction=1.0,
        executed_notional=notional,
        arrival_price=arrival_p,
        fill_price=100.50,  # paid 0.50 more
    )
    assert buy_adverse["signed_slippage_dollars"] > 0
    assert buy_adverse["signed_slippage_dollars"] == pytest.approx(250.0)
    assert buy_adverse["signed_slippage_bps"] == pytest.approx(50.0)

    # 2. Buy Order with Price Improvement (fill_p < arrival_p)
    buy_favorable = calculate_trade_slippage(
        direction=1.0,
        executed_notional=notional,
        arrival_price=arrival_p,
        fill_price=99.80,  # paid 0.20 less
    )
    assert buy_favorable["signed_slippage_dollars"] < 0
    assert buy_favorable["signed_slippage_dollars"] == pytest.approx(-100.0)
    assert buy_favorable["signed_slippage_bps"] == pytest.approx(-20.0)

    # 3. Sell Order with Adverse Slippage (fill_p < arrival_p)
    sell_adverse = calculate_trade_slippage(
        direction=-1.0,
        executed_notional=notional,
        arrival_price=arrival_p,
        fill_price=99.20,  # received 0.80 less
    )
    assert sell_adverse["signed_slippage_dollars"] > 0
    assert sell_adverse["signed_slippage_dollars"] == pytest.approx(400.0)
    assert sell_adverse["signed_slippage_bps"] == pytest.approx(80.0)

    # 4. Sell Order with Price Improvement (fill_p > arrival_p)
    sell_favorable = calculate_trade_slippage(
        direction=-1.0,
        executed_notional=notional,
        arrival_price=arrival_p,
        fill_price=100.30,  # received 0.30 more
    )
    assert sell_favorable["signed_slippage_dollars"] < 0
    assert sell_favorable["signed_slippage_dollars"] == pytest.approx(-150.0)
    assert sell_favorable["signed_slippage_bps"] == pytest.approx(-30.0)

    # 5. Zero notional / boundary case
    zero_slip = calculate_trade_slippage(
        direction=1.0,
        executed_notional=0.0,
        arrival_price=arrival_p,
        fill_price=101.0,
    )
    assert zero_slip["signed_slippage_dollars"] == 0.0
    assert zero_slip["signed_slippage_bps"] == 0.0


# ============================================================================
# 2. Mathematical Unit Tests: Opportunity / Delay Cost on Unexecuted Notional
# ============================================================================

def test_opportunity_cost_calculation():
    """Verify signed opportunity cost on unexecuted/deferred order notional."""
    # 1. Buy Order: unexecuted notional = 40,000, asset rises +2.5%
    # Portfolio missed upside -> adverse opportunity cost > 0
    buy_missed_gain = calculate_opportunity_cost(
        direction=1.0,
        requested_notional=100_000.0,
        executed_notional=60_000.0,
        realized_asset_return=0.025,
    )
    assert buy_missed_gain["unexecuted_notional"] == 40_000.0
    assert buy_missed_gain["opportunity_cost_dollars"] == pytest.approx(1000.0)
    assert buy_missed_gain["opportunity_cost_bps"] == pytest.approx(250.0)

    # 2. Buy Order: asset falls -2.5%
    # Portfolio avoided downside -> opportunity cost < 0
    buy_avoided_loss = calculate_opportunity_cost(
        direction=1.0,
        requested_notional=100_000.0,
        executed_notional=60_000.0,
        realized_asset_return=-0.025,
    )
    assert buy_avoided_loss["opportunity_cost_dollars"] == pytest.approx(-1000.0)

    # 3. Sell Order: unexecuted notional = 30,000, asset falls -3.0%
    # Unliquidated holding depreciated -> adverse delay cost > 0
    sell_missed_drop = calculate_opportunity_cost(
        direction=-1.0,
        requested_notional=100_000.0,
        executed_notional=70_000.0,
        realized_asset_return=-0.03,
    )
    assert sell_missed_drop["unexecuted_notional"] == 30_000.0
    assert sell_missed_drop["opportunity_cost_dollars"] == pytest.approx(900.0)
    assert sell_missed_drop["opportunity_cost_bps"] == pytest.approx(300.0)

    # 4. Fully executed order -> zero opportunity cost
    full_exec = calculate_opportunity_cost(
        direction=1.0,
        requested_notional=50_000.0,
        executed_notional=50_000.0,
        realized_asset_return=0.05,
    )
    assert full_exec["opportunity_cost_dollars"] == 0.0
    assert full_exec["unexecuted_notional"] == 0.0


# ============================================================================
# 3. Accounting Identity: Exact Friction Reconciliation & Residual
# ============================================================================

def test_component_cost_decomposition_exact_reconciliation():
    """Verify that Total Cost == Spread + Temp Impact + Perm Impact + Commission exactly."""
    fills = [
        TradeFill(
            date="2024-01-15",
            ticker="AAPL",
            direction=1.0,
            requested_notional=100_000.0,
            executed_notional=100_000.0,
            arrival_price=100.0,
            fill_price=100.055,
            spread_cost=25.0,
            temp_impact_cost=15.0,
            perm_impact_cost=5.0,
            commission_cost=10.0,
            total_cost=55.0,
            realized_asset_return=0.01,
            regime_state=0,
            scheduling_mode="twap",
        ),
        TradeFill(
            date="2024-01-15",
            ticker="MSFT",
            direction=-1.0,
            requested_notional=80_000.0,
            executed_notional=80_000.0,
            arrival_price=200.0,
            fill_price=199.90,
            spread_cost=20.0,
            temp_impact_cost=12.0,
            perm_impact_cost=4.0,
            commission_cost=8.0,
            total_cost=44.0,
            realized_asset_return=-0.005,
            regime_state=0,
            scheduling_mode="twap",
        ),
    ]

    report = compute_transaction_cost_analysis(fills, initial_capital=200_000.0)
    summary = report["summary"]

    assert summary["fill_count"] == 2
    assert summary["total_executed_notional"] == 180_000.0
    assert summary["spread_cost"] == 45.0
    assert summary["temporary_impact_cost"] == 27.0
    assert summary["permanent_impact_cost"] == 9.0
    assert summary["market_impact_cost"] == 36.0
    assert summary["commission_cost"] == 18.0
    assert summary["total_cost"] == 99.0

    # Invariant: Unattributed cost is strictly zero
    assert summary["unattributed_cost"] == pytest.approx(0.0)
    assert report["provenance"]["reconciliation_status"] == "exact_modeled_identity_verified"
    assert report["provenance"]["decomposition_type"] == "structural_modeled_identity"
    assert report["provenance"]["permanent_impact_status"] == "modeled_linear_adv_ratio"
    assert summary["realized_slippage"] == pytest.approx(95.0)
    assert summary["realized_slippage_bps"] == pytest.approx(5.2778, abs=0.01)


# ============================================================================
# 4. Mathematical Weighting: Notional-Weighted Basis Points vs Naive Average
# ============================================================================

def test_notional_weighted_aggregation_across_regimes_and_modes():
    """Verify that aggregate basis points are notional-weighted rather than an arithmetic average."""
    fills = [
        # Small trade with low bps
        TradeFill(
            date="2024-02-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=10_000.0,
            executed_notional=10_000.0,
            arrival_price=100.0,
            fill_price=100.01,
            spread_cost=1.0,
            temp_impact_cost=0.0,
            perm_impact_cost=0.0,
            commission_cost=0.0,
            total_cost=1.0,  # 10 bps
            realized_asset_return=0.0,
            regime_state=0,
            scheduling_mode="single_day",
        ),
        # Large trade with high bps (in turbulent regime)
        TradeFill(
            date="2024-02-01",
            ticker="MSFT",
            direction=1.0,
            requested_notional=90_000.0,
            executed_notional=90_000.0,
            arrival_price=200.0,
            fill_price=200.20,
            spread_cost=45.0,
            temp_impact_cost=30.0,
            perm_impact_cost=15.0,
            commission_cost=0.0,
            total_cost=90.0,  # 100 bps
            realized_asset_return=0.0,
            regime_state=1,
            scheduling_mode="almgren_chriss",
        ),
    ]

    report = compute_transaction_cost_analysis(fills)
    summary = report["summary"]

    # Naive arithmetic average of bps would be (1.0 + 10.0) / 2 = 5.5 bps
    # True notional-weighted bps is: 10^4 * (1.0 + 90.0) / (10,000 + 90,000) = 9.1 bps
    assert summary["effective_bps"] == pytest.approx(9.1)
    assert summary["effective_bps"] != 5.5

    # Regime breakdown isolation
    calm_regime = report["by_regime"]["State 0 (Calm)"]
    assert calm_regime["total_executed_notional"] == 10_000.0
    assert calm_regime["effective_bps"] == pytest.approx(1.0)

    turb_regime = report["by_regime"]["State 1 (Turbulent)"]
    assert turb_regime["total_executed_notional"] == 90_000.0
    assert turb_regime["effective_bps"] == pytest.approx(10.0)


# ============================================================================
# 5. Integration: Walk-Forward Backtesting TCA Reconciliation
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Generates synthetic price and volume data for walk-forward integration tests."""
    np.random.seed(42)
    T = 130
    tickers = ["AAPL", "MSFT", "GOOGL"]
    dates = pd.date_range("2024-01-01", periods=T, freq="B")

    rets = np.zeros((T, 3))
    rets[:70, :] = np.random.normal(0.0005, 0.01, size=(70, 3))
    rets[70:, :] = np.random.normal(-0.001, 0.025, size=(T - 70, 3))

    ret_df = pd.DataFrame(rets, index=dates, columns=tickers)
    vol_df = pd.DataFrame(np.random.uniform(5_000_000, 15_000_000, size=(T, 3)), index=dates, columns=tickers)
    return ret_df, vol_df


def test_walk_forward_backtest_tca_integration_and_identity(sample_market_data):
    """
    CRITICAL QUANTITATIVE INVARIANT:
    TCA total cost must reconcile identically with strat_total_costs deducted from portfolio equity.
    """
    ret_df, vol_df = sample_market_data

    res = run_vine_tail_risk_parity_backtest(
        returns_df=ret_df,
        volumes_df=vol_df,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="almgren_chriss",
        max_scheduling_days=3,
        scheduling_risk_aversion=1e-5,
        enable_regime_aware_execution=True,
        regime_num_states=2,
        regime_adaptation_strength=0.5,
        random_seed=42,
    )

    assert "tca_report" in res
    tca = res["tca_report"]
    summary = tca["summary"]

    # 1. Reconciliation against Strategy Total Transaction Costs
    bt_costs = res["strategy_metrics"]["total_transaction_costs"]
    assert reconcile_tca_with_backtest_costs(summary, bt_costs, tolerance=0.05)
    assert summary["unattributed_cost"] == pytest.approx(0.0, abs=1e-3)

    # 2. Multi-dimensional breakdowns are populated
    assert len(tca["by_regime"]) > 0
    assert len(tca["by_asset"]) == 3
    for tk in ["AAPL", "MSFT", "GOOGL"]:
        assert tk in tca["by_asset"]
        assert tca["by_asset"][tk]["total_executed_notional"] > 0

    # 3. Event breakdown matches rebalance history count
    assert len(tca["by_event"]) == res["total_rebalances"]
    assert summary["fill_count"] > 0


# ============================================================================
# 6. Strict Anti-Lookahead Mutation Invariance for TCA
# ============================================================================

def test_anti_lookahead_mutation_invariance_for_tca(sample_market_data):
    """
    Verify that mutating future data strictly AFTER decision timestamp t
    does not alter earlier TCA fills, notionals, costs, or regime attribution.
    """
    ret_df, vol_df = sample_market_data

    # Baseline run
    base_res = run_vine_tail_risk_parity_backtest(
        returns_df=ret_df,
        volumes_df=vol_df,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="twap",
        max_scheduling_days=3,
        enable_regime_aware_execution=True,
        random_seed=42,
    )

    first_event_tca = base_res["tca_report"]["by_event"][0]
    first_event_date = first_event_tca["date"]

    # Mutate data strictly 5 days AFTER first rebalance
    mutated_rets = ret_df.copy()
    mutated_vols = vol_df.copy()
    loc = mutated_rets.index.get_loc(pd.to_datetime(first_event_date))
    mutated_rets.iloc[loc + 5 :] = -0.20
    mutated_vols.iloc[loc + 5 :] = 100_000_000.0

    mut_res = run_vine_tail_risk_parity_backtest(
        returns_df=mutated_rets,
        volumes_df=mutated_vols,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="twap",
        max_scheduling_days=3,
        enable_regime_aware_execution=True,
        random_seed=42,
    )

    mut_event_tca = mut_res["tca_report"]["by_event"][0]

    assert mut_event_tca["date"] == first_event_date
    assert mut_event_tca["total_cost"] == pytest.approx(first_event_tca["total_cost"], abs=1e-4)
    assert mut_event_tca["effective_bps"] == pytest.approx(first_event_tca["effective_bps"], abs=1e-4)
    assert mut_event_tca["total_executed_notional"] == pytest.approx(first_event_tca["total_executed_notional"], abs=1e-4)
    assert mut_event_tca["regime_state"] == first_event_tca["regime_state"]


# ============================================================================
# 7. Pydantic Schema Validation & Backward Compatibility
# ============================================================================

def test_pydantic_schema_validation_and_backward_compatibility():
    """Verify that VineBacktestResponse parses with and without tca_report."""
    # 1. Valid TCAReport construction
    report = TCAReport(
        summary=TCACostMetrics(total_cost=100.0, effective_bps=12.5),
        by_regime={"State 0": TCACostMetrics(total_cost=100.0)},
        provenance=TCAProvenance(),
    )
    assert report.summary.total_cost == 100.0
    assert report.provenance.currency_basis == "USD"

    # 2. VineBacktestResponse with tca_report
    dummy_metrics = VineBacktestStrategyMetrics(
        total_return=0.10,
        cagr=0.10,
        annualized_volatility=0.15,
        sharpe_ratio=1.2,
        max_drawdown=-0.05,
        calmar_ratio=2.0,
        historical_var_99=0.03,
        historical_cvar_99=0.04,
        total_turnover=0.5,
        total_transaction_costs=100.0,
    )
    resp = VineBacktestResponse(
        dataset_id="test_ds",
        vine_type="c_vine",
        estimation_window=40,
        rebalance_frequency="monthly",
        confidence_level=0.99,
        num_simulations=500,
        marginal_method="empirical",
        evaluation_start_date="2024-02-01",
        evaluation_end_date="2024-06-01",
        total_evaluation_days=80,
        total_rebalances=4,
        fallback_rebalances=0,
        strategy_metrics=dummy_metrics,
        benchmark_metrics=dummy_metrics,
        static_trp_metrics=dummy_metrics,
        equity_curve=[],
        rebalance_history=[],
        tca_report=report,
    )
    assert resp.tca_report is not None
    assert resp.tca_report.summary.effective_bps == 12.5

    # 3. Backward compatibility: tca_report=None
    resp_compat = VineBacktestResponse(
        dataset_id="test_ds",
        vine_type="c_vine",
        estimation_window=40,
        rebalance_frequency="monthly",
        confidence_level=0.99,
        num_simulations=500,
        marginal_method="empirical",
        evaluation_start_date="2024-02-01",
        evaluation_end_date="2024-06-01",
        total_evaluation_days=80,
        total_rebalances=4,
        fallback_rebalances=0,
        strategy_metrics=dummy_metrics,
        benchmark_metrics=dummy_metrics,
        static_trp_metrics=dummy_metrics,
        equity_curve=[],
        rebalance_history=[],
    )
    assert resp_compat.tca_report is None


# ============================================================================
# 8. Session 43 Remediation Regression Tests (DEF-42-01 through DEF-42-06)
# ============================================================================

def test_multiday_queue_requested_notional_accounting():
    """
    Verify DEF-42-02: Multi-day queue requested notional accounting across all 8 scenarios:
    1. One-day order fully filled: requested == executed, fill rate = 100%.
    2. Multi-day order fully filled across tranches: sum of tranche requested == total executed, fill rate = 100%.
    3. Multi-day order partially filled: unexecuted notional captured, fill rate = exec / req.
    4. Multi-day order left partially outstanding at horizon: expired zero-fills emitted.
    5. Cancelled or interrupted queue order: cancelled zero-fills emitted.
    6. Multiple independent orders for same instrument across rebalances tracked by order_id.
    7. Multi-instrument rebalance with different execution horizons.
    8. Zero requested notional: empty summary returned cleanly.
    """
    # Scenario 1: One-day order fully filled
    fill_s1 = [
        TradeFill(
            date="2024-03-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=50_000.0,
            executed_notional=50_000.0,
            arrival_price=100.0,
            fill_price=100.05,
            spread_cost=10.0,
            temp_impact_cost=15.0,
            total_cost=25.0,
            realized_asset_return=0.01,
            scheduling_mode="single_day",
            scheduled_horizon_days=1,
            tranche_day_index=0,
            parent_order_notional=50_000.0,
            order_id="ORD_1_AAPL",
        )
    ]
    rep_s1 = compute_transaction_cost_analysis(fill_s1)["summary"]
    assert rep_s1["total_requested_notional"] == 50_000.0
    assert rep_s1["total_executed_notional"] == 50_000.0
    assert rep_s1["total_unexecuted_notional"] == 0.0
    assert rep_s1["fill_rate_pct"] == 100.0

    # Scenario 2: Multi-day order fully filled across 3 tranches (e.g. $90k total = 3 x $30k)
    fills_s2 = [
        TradeFill(
            date=f"2024-03-0{d}",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=30_000.0,
            arrival_price=100.0,
            fill_price=100.04,
            spread_cost=5.0,
            temp_impact_cost=7.0,
            total_cost=12.0,
            realized_asset_return=0.005,
            scheduling_mode="twap",
            scheduled_horizon_days=3,
            tranche_day_index=d - 1,
            parent_order_notional=90_000.0,
            order_id="REBAL_1_AAPL",
        )
        for d in [1, 2, 3]
    ]
    rep_s2 = compute_transaction_cost_analysis(fills_s2)["summary"]
    # Key fix: Tranche requests sum to $90k, not $150k
    assert rep_s2["total_requested_notional"] == 90_000.0
    assert rep_s2["total_executed_notional"] == 90_000.0
    assert rep_s2["total_unexecuted_notional"] == 0.0
    assert rep_s2["fill_rate_pct"] == 100.0

    # Scenario 3: Multi-day order partially filled (Day 2 clipped by volume cap)
    fills_s3 = [
        TradeFill(
            date="2024-03-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=30_000.0,
            arrival_price=100.0,
            fill_price=100.04,
            spread_cost=5.0,
            temp_impact_cost=7.0,
            total_cost=12.0,
            realized_asset_return=0.005,
            scheduling_mode="twap",
            scheduled_horizon_days=2,
            tranche_day_index=0,
            parent_order_notional=60_000.0,
            order_id="REBAL_1_AAPL",
        ),
        TradeFill(
            date="2024-03-02",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=20_000.0,  # $10k unexecuted
            arrival_price=100.0,
            fill_price=100.03,
            spread_cost=3.0,
            temp_impact_cost=5.0,
            total_cost=8.0,
            realized_asset_return=0.002,
            scheduling_mode="twap",
            scheduled_horizon_days=2,
            tranche_day_index=1,
            parent_order_notional=60_000.0,
            order_id="REBAL_1_AAPL",
        ),
    ]
    rep_s3 = compute_transaction_cost_analysis(fills_s3)["summary"]
    assert rep_s3["total_requested_notional"] == 60_000.0
    assert rep_s3["total_executed_notional"] == 50_000.0
    assert rep_s3["total_unexecuted_notional"] == 10_000.0
    assert rep_s3["fill_rate_pct"] == pytest.approx(83.33, abs=0.01)

    # Scenario 4: Multi-day order left partially outstanding at horizon (expired fill)
    fills_s4 = [
        TradeFill(
            date="2024-03-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=30_000.0,
            arrival_price=100.0,
            fill_price=100.04,
            spread_cost=5.0,
            temp_impact_cost=7.0,
            total_cost=12.0,
            realized_asset_return=0.005,
            scheduling_mode="twap",
            scheduled_horizon_days=2,
            tranche_day_index=0,
            parent_order_notional=60_000.0,
            order_id="REBAL_1_AAPL",
        ),
        TradeFill(
            date="2024-03-02",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=0.0,
            arrival_price=100.0,
            fill_price=100.0,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            total_cost=0.0,
            realized_asset_return=0.0,
            scheduling_mode="expired",
            scheduled_horizon_days=2,
            tranche_day_index=1,
            parent_order_notional=60_000.0,
            order_id="EXPIRED_AAPL",
        ),
    ]
    rep_s4 = compute_transaction_cost_analysis(fills_s4)["summary"]
    assert rep_s4["total_requested_notional"] == 60_000.0
    assert rep_s4["total_executed_notional"] == 30_000.0
    assert rep_s4["total_unexecuted_notional"] == 30_000.0
    assert rep_s4["fill_rate_pct"] == 50.0

    # Scenario 5: Cancelled or interrupted queue order
    fills_s5 = [
        TradeFill(
            date="2024-03-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=30_000.0,
            executed_notional=30_000.0,
            arrival_price=100.0,
            fill_price=100.04,
            spread_cost=5.0,
            temp_impact_cost=7.0,
            total_cost=12.0,
            realized_asset_return=0.005,
            scheduling_mode="twap",
            scheduled_horizon_days=3,
            tranche_day_index=0,
            parent_order_notional=90_000.0,
            order_id="REBAL_1_AAPL",
        ),
        TradeFill(
            date="2024-03-02",
            ticker="AAPL",
            direction=1.0,
            requested_notional=60_000.0,  # 2 remaining tranches cancelled
            executed_notional=0.0,
            arrival_price=100.0,
            fill_price=100.0,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            total_cost=0.0,
            realized_asset_return=0.0,
            scheduling_mode="cancelled",
            scheduled_horizon_days=3,
            tranche_day_index=1,
            parent_order_notional=90_000.0,
            order_id="CANCELLED_AAPL",
        ),
    ]
    rep_s5 = compute_transaction_cost_analysis(fills_s5)
    assert rep_s5["summary"]["total_unexecuted_notional"] == 60_000.0
    assert "cancelled" in rep_s5["by_mode"]
    assert rep_s5["by_mode"]["cancelled"]["total_unexecuted_notional"] == 60_000.0

    # Scenario 6: Multiple independent orders for same instrument across rebalances
    fills_s6 = [
        TradeFill(
            date="2024-01-15",
            ticker="MSFT",
            direction=1.0,
            requested_notional=40_000.0,
            executed_notional=40_000.0,
            arrival_price=200.0,
            fill_price=200.10,
            spread_cost=8.0,
            temp_impact_cost=12.0,
            total_cost=20.0,
            realized_asset_return=0.01,
            parent_order_notional=40_000.0,
            order_id="REBAL_1_MSFT",
        ),
        TradeFill(
            date="2024-02-15",
            ticker="MSFT",
            direction=-1.0,
            requested_notional=30_000.0,
            executed_notional=30_000.0,
            arrival_price=210.0,
            fill_price=209.90,
            spread_cost=6.0,
            temp_impact_cost=9.0,
            total_cost=15.0,
            realized_asset_return=-0.005,
            parent_order_notional=30_000.0,
            order_id="REBAL_2_MSFT",
        ),
    ]
    rep_s6 = compute_transaction_cost_analysis(fills_s6)
    assert rep_s6["by_asset"]["MSFT"]["total_executed_notional"] == 70_000.0
    assert rep_s6["by_asset"]["MSFT"]["fill_count"] == 2

    # Scenario 7: Multi-instrument rebalance with different execution horizons
    fills_s7 = [
        TradeFill(
            date="2024-03-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=50_000.0,
            executed_notional=50_000.0,
            arrival_price=100.0,
            fill_price=100.05,
            spread_cost=10.0,
            temp_impact_cost=15.0,
            total_cost=25.0,
            realized_asset_return=0.01,
            scheduling_mode="single_day",
            scheduled_horizon_days=1,
        ),
        TradeFill(
            date="2024-03-01",
            ticker="GOOGL",
            direction=1.0,
            requested_notional=25_000.0,
            executed_notional=25_000.0,
            arrival_price=150.0,
            fill_price=150.03,
            spread_cost=5.0,
            temp_impact_cost=7.5,
            total_cost=12.5,
            realized_asset_return=0.008,
            scheduling_mode="almgren_chriss",
            scheduled_horizon_days=3,
        ),
    ]
    rep_s7 = compute_transaction_cost_analysis(fills_s7)
    assert rep_s7["summary"]["total_executed_notional"] == 75_000.0
    assert "single_day" in rep_s7["by_mode"]
    assert "almgren_chriss" in rep_s7["by_mode"]

    # Scenario 8: Zero requested notional / empty fills
    rep_s8 = compute_transaction_cost_analysis([])
    assert rep_s8["summary"]["fill_count"] == 0
    assert rep_s8["summary"]["total_requested_notional"] == 0.0
    assert rep_s8["summary"]["total_executed_notional"] == 0.0
    assert rep_s8["summary"]["total_unexecuted_notional"] == 0.0
    assert rep_s8["summary"]["fill_rate_pct"] == 100.0
    assert rep_s8["provenance"]["reconciliation_status"] == "exact_modeled_identity_verified"


def test_rebalance_rejection_opportunity_cost():
    """
    Verify DEF-42-05: When participation policy rejects a rebalance:
    - Zero-fill TradeFill records are emitted.
    - executed_notional == 0.0, total_cost == 0.0.
    - unexecuted notional equals requested notional.
    - Opportunity cost captures missed drift without deducting cash or equity.
    """
    rejected_fills = [
        TradeFill(
            date="2024-04-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=100_000.0,
            executed_notional=0.0,
            arrival_price=100.0,
            fill_price=100.0,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            perm_impact_cost=0.0,
            commission_cost=0.0,
            total_cost=0.0,
            realized_asset_return=0.02,  # Missed +2% gain on buy order
            scheduling_mode="rejected",
            scheduled_horizon_days=1,
            tranche_day_index=0,
            parent_order_notional=100_000.0,
            order_id="REJECTED_REBAL_1_AAPL",
        )
    ]

    report = compute_transaction_cost_analysis(rejected_fills, initial_capital=200_000.0)
    summary = report["summary"]

    assert summary["fill_count"] == 1
    assert summary["total_requested_notional"] == 100_000.0
    assert summary["total_executed_notional"] == 0.0
    assert summary["total_unexecuted_notional"] == 100_000.0
    assert summary["fill_rate_pct"] == 0.0
    assert summary["total_cost"] == 0.0
    assert summary["effective_bps"] == 0.0

    # Opportunity cost on missed buy with positive return = +$2,000 adverse delay cost
    assert summary["opportunity_cost"] == pytest.approx(2_000.0)
    # Opportunity bps is normalized by requested notional when executed is 0
    assert summary["opportunity_bps"] == pytest.approx(200.0)

    # Invariant: rejected mode is categorized
    assert "rejected" in report["by_mode"]
    assert report["by_mode"]["rejected"]["total_unexecuted_notional"] == 100_000.0


def test_signed_realized_slippage_aggregation():
    """
    Verify DEF-42-04: compute_transaction_cost_analysis properly integrates
    calculate_trade_slippage() into summary realized_slippage and realized_slippage_bps.
    """
    fills = [
        # Buy with adverse fill: arrival $100, fill $100.10 -> +$100 adverse slippage
        TradeFill(
            date="2024-05-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=100_000.0,
            executed_notional=100_000.0,
            arrival_price=100.0,
            fill_price=100.10,
            spread_cost=40.0,
            temp_impact_cost=60.0,
            total_cost=100.0,
            realized_asset_return=0.01,
        ),
        # Sell with favorable fill (price improvement): arrival $200, fill $200.20 -> -$100 negative slippage
        TradeFill(
            date="2024-05-01",
            ticker="MSFT",
            direction=-1.0,
            requested_notional=100_000.0,
            executed_notional=100_000.0,
            arrival_price=200.0,
            fill_price=200.20,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            total_cost=-100.0,
            realized_asset_return=-0.005,
        ),
    ]

    report = compute_transaction_cost_analysis(fills, initial_capital=200_000.0)
    summary = report["summary"]

    # Buy slippage = +$100, Sell slippage = -$100 -> Net realized slippage = $0.0
    assert summary["realized_slippage"] == pytest.approx(0.0)
    assert summary["realized_slippage_bps"] == pytest.approx(0.0)


def test_zero_cost_and_edge_cases_tca():
    """
    Verify DEF-42-03: Zero-cost fills, single-component costs, and residual warning logic.
    """
    # 1. Zero-cost fill
    zero_fill = [
        TradeFill(
            date="2024-06-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=50_000.0,
            executed_notional=50_000.0,
            arrival_price=100.0,
            fill_price=100.0,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            perm_impact_cost=0.0,
            commission_cost=0.0,
            total_cost=0.0,
            realized_asset_return=0.0,
        )
    ]
    rep_zero = compute_transaction_cost_analysis(zero_fill)
    assert rep_zero["summary"]["total_cost"] == 0.0
    assert rep_zero["summary"]["effective_bps"] == 0.0
    assert rep_zero["provenance"]["reconciliation_status"] == "exact_modeled_identity_verified"
    assert rep_zero["provenance"]["permanent_impact_status"] == "not_modeled_zero"

    # 2. Single-component cost (only commission)
    comm_fill = [
        TradeFill(
            date="2024-06-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=50_000.0,
            executed_notional=50_000.0,
            arrival_price=100.0,
            fill_price=100.01,
            spread_cost=0.0,
            temp_impact_cost=0.0,
            perm_impact_cost=0.0,
            commission_cost=5.0,
            total_cost=5.0,
            realized_asset_return=0.0,
        )
    ]
    rep_comm = compute_transaction_cost_analysis(comm_fill)
    assert rep_comm["summary"]["commission_cost"] == 5.0
    assert rep_comm["summary"]["total_cost"] == 5.0
    assert rep_comm["summary"]["unattributed_cost"] == pytest.approx(0.0)
    assert rep_comm["provenance"]["reconciliation_status"] == "exact_modeled_identity_verified"

    # 3. Discrepancy / residual warning triggering
    disc_fill = [
        TradeFill(
            date="2024-06-01",
            ticker="AAPL",
            direction=1.0,
            requested_notional=50_000.0,
            executed_notional=50_000.0,
            arrival_price=100.0,
            fill_price=100.05,
            spread_cost=10.0,
            temp_impact_cost=10.0,
            perm_impact_cost=0.0,
            commission_cost=0.0,
            total_cost=25.0,  # $5.0 discrepancy from 10+10
            realized_asset_return=0.0,
        )
    ]
    rep_disc = compute_transaction_cost_analysis(disc_fill)
    assert rep_disc["summary"]["unattributed_cost"] == pytest.approx(5.0)
    assert rep_disc["provenance"]["reconciliation_status"] == "residual_warning"
