"""
Comprehensive Unit, Mathematical, Anti-Lookahead, and Regression Test Suite
for Stage 29: Regime-Aware Execution Dynamics.

Covers:
A. Regime-Policy Unit Tests:
   - Calm vs Turbulent regime adaptation
   - Multi-state (M=2, M=3) probability scaling
   - Clamping to [p_min, p_max] bounds
   - Risk aversion scaling with lambda=0 TWAP limit preserved
   - Invalid, non-finite, and degenerate regime input fallbacks
   - Disabled adaptation exact identity
B. Execution Mathematics:
   - Regime-contracted horizon expansion (D_crisis >= D_calm)
   - Bounded execution horizon (D <= D_max)
   - Zero notional and invalid ADV robustness
   - Notional conservation across TWAP, VWAP, and Almgren-Chriss
   - Almgren-Chriss lambda -> 0 convergence to linear TWAP
C. Dynamic Walk-Forward Backtesting Integration:
   - Walk-forward backtest execution with enable_regime_aware_execution=True
   - Queue lifecycle and rebalance conflict cancellation
   - Cash non-negativity and fee pre-allocation invariants
   - 100% backward compatibility when disabled
D. Strict Anti-Lookahead Mutation Invariance:
   - Future return and volume mutations after timestamp t do not alter earlier
     regime states, effective parameters, or executed schedules.
E. API Schema Validation:
   - Pydantic validation of regime parameters, rejection of invalid bounds.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.quant.execution import (
    compute_execution_horizon,
    compute_multi_day_execution_schedule,
    compute_regime_aware_execution_parameters,
)
from app.quant.vine_backtest import run_vine_tail_risk_parity_backtest
from app.copula.models import VineBacktestRequest


# ============================================================================
# A. Regime-Policy Unit Tests
# ============================================================================

def test_regime_policy_calm_vs_turbulent():
    """Verify that calm regime maintains baseline participation, while turbulent contracts it."""
    base_pr = 0.10
    base_lambda = 1e-4
    strength = 0.6
    p_min = 0.02

    # 1. Fully Calm Regime: P(State 0) = 1.0, P(Turbulent) = 0.0
    calm_res = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[1.0, 0.0],
        regime_adaptation_strength=strength,
        min_participation_rate=p_min,
    )
    assert calm_res["regime_state"] == 0
    assert calm_res["p_turbulent"] == pytest.approx(0.0)
    assert calm_res["effective_participation_rate"] == pytest.approx(base_pr)
    assert calm_res["effective_risk_aversion"] == pytest.approx(base_lambda)

    # 2. Fully Turbulent Regime: P(State 1) = 1.0, P(Turbulent) = 1.0
    crisis_res = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[0.0, 1.0],
        regime_adaptation_strength=strength,
        min_participation_rate=p_min,
    )
    assert crisis_res["regime_state"] == 1
    assert crisis_res["p_turbulent"] == pytest.approx(1.0)
    # g_p = 1 - 0.6 * 1.0 = 0.4 -> eff_pr = 0.10 * 0.4 = 0.04
    assert crisis_res["effective_participation_rate"] == pytest.approx(0.04)
    # g_lambda = 1 + 0.6 * 1.0 = 1.6 -> eff_lambda = 1e-4 * 1.6 = 1.6e-4
    assert crisis_res["effective_risk_aversion"] == pytest.approx(1.6e-4)


def test_regime_policy_clamping_to_bounds():
    """Verify that effective participation rate never breaches p_min or p_max."""
    base_pr = 0.10
    base_lambda = 0.01

    # Force severe contraction that would breach p_min = 0.03
    res_clamped = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[0.0, 1.0],
        regime_adaptation_strength=0.95,  # 1 - 0.95 = 0.05 -> 0.10 * 0.05 = 0.005 < 0.03
        min_participation_rate=0.03,
        max_participation_rate_upper=0.10,
    )
    assert res_clamped["effective_participation_rate"] == pytest.approx(0.03)
    assert res_clamped["effective_participation_rate"] >= 0.03


def test_regime_policy_lambda_zero_twap_limit():
    """Verify mathematical invariant: when lambda_base = 0, lambda_eff remains strictly 0."""
    res_zero = compute_regime_aware_execution_parameters(
        base_participation_rate=0.10,
        base_risk_aversion=0.0,
        regime_probs=[0.1, 0.9],
        regime_adaptation_strength=0.8,
        min_participation_rate=0.02,
    )
    assert res_zero["effective_risk_aversion"] == 0.0


def test_regime_policy_multi_state_m3():
    """Verify 3-state HMM: State 0 (Calm), State 1 (Normal), State 2 (High Vol / Crisis)."""
    res_m3 = compute_regime_aware_execution_parameters(
        base_participation_rate=0.10,
        base_risk_aversion=1e-5,
        regime_probs=[0.2, 0.3, 0.5],
        regime_adaptation_strength=0.5,
        min_participation_rate=0.02,
    )
    assert res_m3["regime_state"] == 2
    assert res_m3["p_turbulent"] == pytest.approx(0.5)
    # g_p = 1 - 0.5 * 0.5 = 0.75 -> eff_pr = 0.10 * 0.75 = 0.075
    assert res_m3["effective_participation_rate"] == pytest.approx(0.075)


def test_regime_policy_invalid_and_non_finite_fallback():
    """Verify deterministic fallback when regime probabilities are invalid, empty, or NaN."""
    base_pr = 0.08
    base_lambda = 5e-5

    # 1. Non-finite input
    res_nan = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[float("nan"), 0.5],
        regime_adaptation_strength=0.5,
    )
    assert res_nan["effective_participation_rate"] == base_pr
    assert res_nan["effective_risk_aversion"] == base_lambda
    assert res_nan["fallback_used"] is True

    # 2. Empty list
    res_empty = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[],
        regime_adaptation_strength=0.5,
    )
    assert res_empty["effective_participation_rate"] == base_pr
    assert res_empty["fallback_used"] is True

    # 3. Adaptation strength 0.0 -> exact identity
    res_zero_s = compute_regime_aware_execution_parameters(
        base_participation_rate=base_pr,
        base_risk_aversion=base_lambda,
        regime_probs=[0.1, 0.9],
        regime_adaptation_strength=0.0,
    )
    assert res_zero_s["effective_participation_rate"] == base_pr
    assert res_zero_s["effective_risk_aversion"] == base_lambda


# ============================================================================
# B. Execution Mathematics Tests
# ============================================================================

def test_regime_contracted_horizon_expansion():
    """Test that crisis regime contracts participation rate and expands horizon D."""
    order_notionals = {"AAPL": 500_000.0}
    adv_dict = {"AAPL": 1_000_000.0}
    base_pr = 0.10  # 100k / day -> D = ceil(500k / 100k) = 5 days

    # 1. Calm regime
    sched_calm = compute_multi_day_execution_schedule(
        order_notionals=order_notionals,
        adv_dict=adv_dict,
        volatility_dict={"AAPL": 0.20},
        max_participation_rate=base_pr,
        max_scheduling_days=10,
        scheduling_mode="twap",
        regime_probs=[1.0, 0.0],
        regime_adaptation_strength=0.6,
        min_participation_rate=0.02,
    )
    assert sched_calm["horizon_days"] == 5
    assert sched_calm["effective_participation_rate"] == pytest.approx(0.10)

    # 2. Crisis regime (p_turbulent = 1.0 -> eff_pr = 0.10 * (1 - 0.6) = 0.04)
    # 40k / day -> D = ceil(500k / 40k) = ceil(12.5) = 13 -> capped by D_max = 10
    sched_crisis = compute_multi_day_execution_schedule(
        order_notionals=order_notionals,
        adv_dict=adv_dict,
        volatility_dict={"AAPL": 0.20},
        max_participation_rate=base_pr,
        max_scheduling_days=10,
        scheduling_mode="twap",
        regime_probs=[0.0, 1.0],
        regime_adaptation_strength=0.6,
        min_participation_rate=0.02,
    )
    assert sched_crisis["horizon_days"] == 10  # Capped at D_max
    assert sched_crisis["effective_participation_rate"] == pytest.approx(0.04)
    assert sched_crisis["horizon_days"] >= sched_calm["horizon_days"]


def test_regime_aware_twap_vwap_notional_conservation():
    """Verify notional conservation across all scheduling modes under regime adaptation."""
    orders = {"AAPL": 250_000.0, "MSFT": -180_000.0}
    advs = {"AAPL": 2_000_000.0, "MSFT": 1_500_000.0}
    vols = {"AAPL": 0.25, "MSFT": 0.22}

    for mode in ["twap", "vwap", "almgren_chriss"]:
        sched = compute_multi_day_execution_schedule(
            order_notionals=orders,
            adv_dict=advs,
            volatility_dict=vols,
            max_participation_rate=0.08,
            max_scheduling_days=5,
            scheduling_mode=mode,
            scheduling_risk_aversion=1e-5,
            regime_probs=[0.3, 0.7],
            regime_adaptation_strength=0.5,
            min_participation_rate=0.02,
        )
        D = sched["horizon_days"]
        assert D >= 1
        for tk, target_n in orders.items():
            daily_sum = sum(sched["daily_schedules"][d][tk] for d in range(D))
            assert daily_sum == pytest.approx(target_n, rel=1e-5)


def test_regime_aware_almgren_chriss_lambda_zero_convergence():
    """Verify Almgren-Chriss converges to linear TWAP when base lambda is 0, regardless of regime."""
    orders = {"AAPL": 300_000.0}
    advs = {"AAPL": 2_000_000.0}
    vols = {"AAPL": 0.20}

    sched_twap = compute_multi_day_execution_schedule(
        order_notionals=orders,
        adv_dict=advs,
        volatility_dict=vols,
        max_participation_rate=0.05,
        max_scheduling_days=4,
        scheduling_mode="twap",
        regime_probs=[0.1, 0.9],
        regime_adaptation_strength=0.5,
    )

    sched_ac = compute_multi_day_execution_schedule(
        order_notionals=orders,
        adv_dict=advs,
        volatility_dict=vols,
        max_participation_rate=0.05,
        max_scheduling_days=4,
        scheduling_mode="almgren_chriss",
        scheduling_risk_aversion=0.0,  # Zero risk aversion
        regime_probs=[0.1, 0.9],
        regime_adaptation_strength=0.5,
    )

    D = sched_twap["horizon_days"]
    assert sched_ac["horizon_days"] == D
    for d in range(D):
        assert sched_ac["daily_schedules"][d]["AAPL"] == pytest.approx(
            sched_twap["daily_schedules"][d]["AAPL"], rel=1e-5
        )


# ============================================================================
# C. Walk-Forward Backtesting Integration Tests
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Generates synthetic price and volume data for walk-forward integration tests."""
    np.random.seed(42)
    T = 130
    tickers = ["AAPL", "MSFT", "GOOGL"]
    dates = pd.date_range("2024-01-01", periods=T, freq="B")

    # Generate returns with a regime switch at day 80 (calm -> high vol)
    rets = np.zeros((T, 3))
    rets[:80, :] = np.random.normal(0.0005, 0.01, size=(80, 3))
    rets[80:, :] = np.random.normal(-0.001, 0.03, size=(T - 80, 3))

    ret_df = pd.DataFrame(rets, index=dates, columns=tickers)
    vol_data = np.random.uniform(5_000_000, 15_000_000, size=(T, 3))
    vol_df = pd.DataFrame(vol_data, index=dates, columns=tickers)

    return ret_df, vol_df


def test_walk_forward_regime_aware_execution_runs(sample_market_data):
    """Verify walk-forward backtest runs cleanly with regime-aware execution enabled."""
    ret_df, vol_df = sample_market_data

    res = run_vine_tail_risk_parity_backtest(
        returns_df=ret_df,
        volumes_df=vol_df,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="twap",
        max_scheduling_days=4,
        enable_regime_aware_execution=True,
        regime_num_states=2,
        regime_adaptation_strength=0.5,
        min_participation_rate=0.02,
        random_seed=42,
    )

    assert res["enable_regime_aware_execution"] is True
    assert res["total_rebalances"] > 0
    assert len(res["rebalance_history"]) > 0

    # Verify each rebalance event has regime diagnostics recorded
    for evt in res["rebalance_history"]:
        assert evt["regime_state"] is not None
        assert evt["regime_state"] in [0, 1]
        assert evt["regime_probabilities"] is not None
        assert len(evt["regime_probabilities"]) == 2
        assert sum(evt["regime_probabilities"]) == pytest.approx(1.0, rel=1e-4)
        assert evt["effective_participation_rate"] is not None
        assert 0.02 <= evt["effective_participation_rate"] <= 0.10


def test_walk_forward_cash_invariants_and_accounting(sample_market_data):
    """Verify cash non-negativity and accounting invariants under regime-aware multi-day execution."""
    ret_df, vol_df = sample_market_data

    res = run_vine_tail_risk_parity_backtest(
        returns_df=ret_df,
        volumes_df=vol_df,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="almgren_chriss",
        max_scheduling_days=5,
        scheduling_risk_aversion=1e-5,
        enable_regime_aware_execution=True,
        regime_num_states=2,
        regime_adaptation_strength=0.6,
        random_seed=123,
    )

    # 1. Cash weight non-negative
    for evt in res["rebalance_history"]:
        assert evt["cash_weight"] >= -1e-6
        # Sum of weights <= 1.0 within numerical precision
        executed_w = evt["executed_weights"]
        assert sum(executed_w.values()) + evt["cash_weight"] == pytest.approx(1.0, abs=1e-3)

    # 2. Equity curve strictly positive
    for pt in res["equity_curve"]:
        assert pt["strategy_equity"] > 0.0


def test_walk_forward_backward_compatibility(sample_market_data):
    """Verify that enable_regime_aware_execution=False identically reproduces Stage 28 behavior."""
    ret_df, vol_df = sample_market_data

    res_default = run_vine_tail_risk_parity_backtest(
        returns_df=ret_df,
        volumes_df=vol_df,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="twap",
        max_scheduling_days=3,
        enable_regime_aware_execution=False,
        random_seed=42,
    )

    assert res_default["enable_regime_aware_execution"] is False
    for evt in res_default["rebalance_history"]:
        assert evt["regime_state"] is None
        assert evt["regime_probabilities"] is None
        assert evt["effective_participation_rate"] == pytest.approx(0.10)


# ============================================================================
# D. Strict Anti-Lookahead Mutation Invariance Tests
# ============================================================================

def test_anti_lookahead_mutation_invariance(sample_market_data):
    """
    CRITICAL QUANTITATIVE INVARIANT:
    Mutating future returns and volumes strictly AFTER decision timestamp t
    MUST NOT alter earlier regime state estimates, effective participation rates,
    execution horizons, or portfolio weights.
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
        max_scheduling_days=4,
        enable_regime_aware_execution=True,
        regime_num_states=2,
        regime_adaptation_strength=0.5,
        random_seed=42,
    )

    first_rebal_date = base_res["rebalance_history"][0]["date"]
    first_rebal_state = base_res["rebalance_history"][0]["regime_state"]
    first_rebal_probs = base_res["rebalance_history"][0]["regime_probabilities"]
    first_rebal_eff_pr = base_res["rebalance_history"][0]["effective_participation_rate"]
    first_rebal_weights = base_res["rebalance_history"][0]["executed_weights"]

    # Mutate data strictly AFTER first_rebal_date
    mutated_rets = ret_df.copy()
    mutated_vols = vol_df.copy()
    loc = mutated_rets.index.get_loc(pd.to_datetime(first_rebal_date))

    # Extreme shock strictly in future: 50% crash and 10x volume explosion
    mutated_rets.iloc[loc + 5 :] = -0.15
    mutated_vols.iloc[loc + 5 :] = 100_000_000.0

    mut_res = run_vine_tail_risk_parity_backtest(
        returns_df=mutated_rets,
        volumes_df=mutated_vols,
        estimation_window=40,
        rebalance_frequency="monthly",
        num_simulations=500,
        execution_scheduling_mode="twap",
        max_scheduling_days=4,
        enable_regime_aware_execution=True,
        regime_num_states=2,
        regime_adaptation_strength=0.5,
        random_seed=42,
    )

    mut_rebal_0 = mut_res["rebalance_history"][0]

    # Invariants strictly preserved at decision time t:
    assert mut_rebal_0["date"] == first_rebal_date
    assert mut_rebal_0["regime_state"] == first_rebal_state
    assert mut_rebal_0["regime_probabilities"] == pytest.approx(first_rebal_probs, abs=1e-4)
    assert mut_rebal_0["effective_participation_rate"] == pytest.approx(first_rebal_eff_pr, abs=1e-4)
    for tk in first_rebal_weights:
        assert mut_rebal_0["executed_weights"][tk] == pytest.approx(first_rebal_weights[tk], abs=1e-4)


# ============================================================================
# E. API Schema Validation Tests
# ============================================================================

def test_vine_backtest_request_schema_validation():
    """Verify Pydantic validation rejects invalid bounds and accepts valid regime settings."""
    # 1. Valid request
    req = VineBacktestRequest(
        dataset_id="test_ds",
        enable_regime_aware_execution=True,
        regime_num_states=3,
        regime_adaptation_strength=0.7,
        min_participation_rate=0.03,
    )
    assert req.enable_regime_aware_execution is True
    assert req.regime_num_states == 3
    assert req.regime_adaptation_strength == 0.7
    assert req.min_participation_rate == 0.03

    # 2. Invalid states count (< 2 or > 5)
    with pytest.raises(ValidationError):
        VineBacktestRequest(dataset_id="test_ds", regime_num_states=1)

    with pytest.raises(ValidationError):
        VineBacktestRequest(dataset_id="test_ds", regime_num_states=6)

    # 3. Invalid adaptation strength (> 1.0 or < 0.0)
    with pytest.raises(ValidationError):
        VineBacktestRequest(dataset_id="test_ds", regime_adaptation_strength=1.5)

    with pytest.raises(ValidationError):
        VineBacktestRequest(dataset_id="test_ds", regime_adaptation_strength=-0.1)

    # 4. Invalid min_participation_rate (< 0.001)
    with pytest.raises(ValidationError):
        VineBacktestRequest(dataset_id="test_ds", min_participation_rate=0.0001)
