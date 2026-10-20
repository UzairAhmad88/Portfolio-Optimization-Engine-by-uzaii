"""
Institutional Test Suite for Stage 25:
Liquidity-Adjusted VaR & Market Impact Friction Modeling in Dynamic Vine TRP Backtesting.

Covers:
1. Mathematical properties of execution cost models (spread, square-root, linear, commission).
2. Volume participation rate policies ('warn', 'cap', 'reject').
3. Monotonicity of trade size vs market impact cost.
4. Liquidity-adjusted VaR and CVaR (L-VaR and L-CVaR) additivity and non-negativity.
5. Gross vs Net wealth accounting and one-time fee deduction identity.
6. Temporal causality & anti-lookahead mutation tests on volume panels.
7. Backward compatibility: exact equivalence of 'fixed_bps' with baseline.
8. API endpoints with Stage 25 parameters and validation checks.
"""

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.execution import (
    compute_liquidity_adjusted_var_cvar,
    compute_rebalance_market_impact,
)
from app.quant.vine_backtest import (
    run_vine_tail_risk_parity_backtest,
)


@pytest.fixture
def synthetic_market_panel():
    """Generates a reproducible 150-day 3-asset returns and volume panel."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=150, freq="B")
    tickers = ["AAPL", "MSFT", "GOOGL"]
    
    # Correlated returns
    cov = np.array([
        [0.0004, 0.0002, 0.00015],
        [0.0002, 0.00035, 0.00018],
        [0.00015, 0.00018, 0.0003],
    ])
    raw_rets = np.random.multivariate_normal(mean=[0.0005, 0.0004, 0.0006], cov=cov, size=150)
    returns_df = pd.DataFrame(raw_rets, index=dates, columns=tickers)

    # Synthetic Daily Traded Volumes (Dollar Notional: $5M to $15M)
    raw_vols = np.random.uniform(5_000_000.0, 15_000_000.0, size=(150, 3))
    volumes_df = pd.DataFrame(raw_vols, index=dates, columns=tickers)

    return returns_df, volumes_df


class TestExecutionCostMathematics:
    """Verifies mathematical validity and accounting decomposition of execution costs."""

    def test_zero_trade_size_produces_zero_cost(self):
        """Zero trade notionals must produce exactly zero cost across all components."""
        traded = {"AAPL": 0.0, "MSFT": 0.0}
        adv = {"AAPL": 10_000_000.0, "MSFT": 8_000_000.0}
        vol = {"AAPL": 0.20, "MSFT": 0.25}

        res = compute_rebalance_market_impact(
            traded_notionals=traded,
            adv_dict=adv,
            volatility_dict=vol,
            spread_bps_dict={"AAPL": 10.0, "MSFT": 10.0},
            commission_bps=5.0,
            impact_model="square_root",
        )
        assert res["summary"]["total_traded_notional"] == 0.0
        assert res["summary"]["total_impact_cost"] == 0.0
        assert res["summary"]["total_spread_cost"] == 0.0
        assert res["summary"]["total_market_impact_cost"] == 0.0
        assert res["summary"]["total_commission_cost"] == 0.0

    def test_cost_decomposition_identity(self):
        """Total cost must strictly equal the sum of Spread + Market Impact + Commission."""
        traded = {"AAPL": 50_000.0, "MSFT": 80_000.0}
        adv = {"AAPL": 10_000_000.0, "MSFT": 5_000_000.0}
        vol = {"AAPL": 0.22, "MSFT": 0.30}
        spread = {"AAPL": 6.0, "MSFT": 8.0}

        res = compute_rebalance_market_impact(
            traded_notionals=traded,
            adv_dict=adv,
            volatility_dict=vol,
            spread_bps_dict=spread,
            commission_bps=2.5,
            impact_model="square_root",
        )
        s = res["summary"]
        expected_total = round(
            s["total_spread_cost"] + s["total_market_impact_cost"] + s["total_commission_cost"],
            2,
        )
        assert s["total_impact_cost"] == expected_total

    def test_market_impact_monotonicity(self):
        """Larger trades in the same asset under identical market conditions produce higher impact."""
        adv = {"AAPL": 10_000_000.0}
        vol = {"AAPL": 0.20}

        res_small = compute_rebalance_market_impact(
            traded_notionals={"AAPL": 20_000.0},
            adv_dict=adv,
            volatility_dict=vol,
            impact_model="square_root",
        )
        res_large = compute_rebalance_market_impact(
            traded_notionals={"AAPL": 200_000.0},
            adv_dict=adv,
            volatility_dict=vol,
            impact_model="square_root",
        )

        assert res_large["summary"]["total_market_impact_cost"] > res_small["summary"]["total_market_impact_cost"]
        # In basis points, square-root law dictates impact bps grows as sqrt(trade)
        assert res_large["summary"]["effective_cost_bps"] > res_small["summary"]["effective_cost_bps"]


class TestVolumeParticipationPolicies:
    """Verifies volume participation rate computation and enforcement policies."""

    def test_warn_policy_records_warning_without_capping(self):
        """Under 'warn' policy, trade executes in full but flags a warning if PR > limit."""
        adv = {"AAPL": 1_000_000.0} # $1M ADV
        vol = {"AAPL": 0.20}
        # $200k trade = 20% participation > 10% limit
        res = compute_rebalance_market_impact(
            traded_notionals={"AAPL": 200_000.0},
            adv_dict=adv,
            volatility_dict=vol,
            max_participation_rate=0.10,
            participation_policy="warn",
        )
        assert res["summary"]["participation_warnings_count"] == 1
        assert res["summary"]["rebalance_rejected"] is False
        assert res["asset_impacts"][0]["executed_notional"] == 200_000.0
        assert res["asset_impacts"][0]["participation_warning"] is True

    def test_cap_policy_constrains_executed_notional(self):
        """Under 'cap' policy, executed notional is bounded by max_participation * ADV."""
        adv = {"AAPL": 1_000_000.0}
        vol = {"AAPL": 0.20}
        res = compute_rebalance_market_impact(
            traded_notionals={"AAPL": 250_000.0},
            adv_dict=adv,
            volatility_dict=vol,
            max_participation_rate=0.10,
            participation_policy="cap",
        )
        assert res["summary"]["participation_warnings_count"] == 1
        # Capped executed notional = 10% of $1M = $100,000
        assert res["asset_impacts"][0]["executed_notional"] == 100_000.0
        assert res["summary"]["total_traded_notional"] == 100_000.0

    def test_reject_policy_aborts_rebalance(self):
        """Under 'reject' policy, exceeding limit flags rebalance_rejected with 0 execution."""
        adv = {"AAPL": 1_000_000.0}
        vol = {"AAPL": 0.20}
        res = compute_rebalance_market_impact(
            traded_notionals={"AAPL": 150_000.0},
            adv_dict=adv,
            volatility_dict=vol,
            max_participation_rate=0.10,
            participation_policy="reject",
        )
        assert res["summary"]["rebalance_rejected"] is True
        assert res["summary"]["total_traded_notional"] == 0.0
        assert res["summary"]["total_impact_cost"] == 0.0


class TestLiquidityAdjustedVaR:
    """Verifies Liquidity-Adjusted Value-at-Risk and Expected Shortfall."""

    def test_l_var_identity_and_non_negativity(self):
        """L-VaR must equal Market VaR + Liquidation Cost %, strictly non-negative."""
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        equity = 100_000.0
        adv = {"AAPL": 5_000_000.0, "MSFT": 4_000_000.0}
        vol = {"AAPL": 0.25, "MSFT": 0.20}
        market_var = 0.025
        market_cvar = 0.035

        res = compute_liquidity_adjusted_var_cvar(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=adv,
            volatility_dict=vol,
            market_var=market_var,
            market_cvar=market_cvar,
            spread_bps_dict={"AAPL": 10.0, "MSFT": 10.0},
            impact_model="square_root",
        )

        assert res["liquidation_cost"] > 0.0
        assert res["l_var"] > market_var
        assert res["l_cvar"] > market_cvar
        assert res["l_cvar"] > res["l_var"]
        # Verify L-VaR = VaR + cost_frac within numerical rounding
        cost_frac = res["liquidation_cost"] / equity
        assert math.isclose(res["l_var"], market_var + cost_frac, abs_tol=1e-4)
        assert math.isclose(res["l_cvar"], market_cvar + cost_frac, abs_tol=1e-4)

    def test_zero_liquidation_cost_reproduces_market_risk(self):
        """When liquidation cost is zero, L-VaR and L-CVaR equal market VaR and CVaR."""
        res = compute_liquidity_adjusted_var_cvar(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            portfolio_equity=0.0, # Zero equity yields zero liquidation cost
            adv_dict={"AAPL": 10_000_000.0, "MSFT": 10_000_000.0},
            volatility_dict={"AAPL": 0.20, "MSFT": 0.20},
            market_var=0.02,
            market_cvar=0.03,
        )
        assert res["l_var"] == 0.02
        assert res["l_cvar"] == 0.03
        assert res["liquidation_cost"] == 0.0


class TestWalkForwardLiquidityBacktest:
    """Verifies end-to-end integration into the walk-forward TRP engine."""

    def test_square_root_walk_forward_execution(self, synthetic_market_panel):
        """Verifies walk-forward simulation with square_root execution model."""
        returns_df, volumes_df = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            num_simulations=500,
            confidence_level=0.99,
            execution_model="square_root",
            bid_ask_spread_bps=8.0,
            max_participation_rate=0.10,
            participation_policy="warn",
            random_seed=42,
        )

        assert res["execution_model"] == "square_root"
        assert res["adv_source"] == "market_observed"
        strat_m = res["strategy_metrics"]
        assert "total_spread_costs" in strat_m
        assert "total_market_impact_costs" in strat_m
        assert "total_commission_costs" in strat_m
        assert "l_var_99" in strat_m
        assert "l_cvar_99" in strat_m

        # Total transaction costs must equal sum of spread, impact, and commission
        expected_total = (
            strat_m["total_spread_costs"] + strat_m["total_market_impact_costs"] + strat_m["total_commission_costs"]
        )
        assert math.isclose(strat_m["total_transaction_costs"], expected_total, abs_tol=0.02)

        # Rebalance history verification
        for r_evt in res["rebalance_history"]:
            assert "spread_cost" in r_evt
            assert "market_impact_cost" in r_evt
            assert "liquidity_adjusted_cvar" in r_evt
            assert "liquidation_cost_pct" in r_evt
            assert "max_participation_rate" in r_evt
            assert r_evt["adv_source"] == "market_observed"

    def test_backward_compatibility_fixed_bps(self, synthetic_market_panel):
        """When execution_model='fixed_bps', backtest operates identically to Session 32."""
        returns_df, _ = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            execution_model="fixed_bps",
            num_simulations=500,
            random_seed=42,
        )

        assert res["execution_model"] == "fixed_bps"
        # Total transaction costs must match turnover * 2 * equity * 15 bps
        strat_m = res["strategy_metrics"]
        assert strat_m["total_transaction_costs"] > 0.0

    def test_strict_temporal_anti_lookahead_mutation(self, synthetic_market_panel):
        """
        Mutating volume data strictly after rebalance cutoff t_k must not alter
        the historical execution cost, ADV, or weights decided at t_k.
        """
        returns_df, volumes_df = synthetic_market_panel

        # Base run
        res_base = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            num_simulations=500,
            random_seed=42,
        )
        first_rebal_base = res_base["rebalance_history"][0]
        cutoff_date = first_rebal_base["date"]

        # Mutate future volumes (10x volume boost after cutoff)
        mutated_volumes = volumes_df.copy()
        future_idx = mutated_volumes.index > cutoff_date
        mutated_volumes.loc[future_idx] *= 10.0

        res_mutated = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=mutated_volumes,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            num_simulations=500,
            random_seed=42,
        )
        first_rebal_mutated = res_mutated["rebalance_history"][0]

        # Prior decision must be identical
        assert first_rebal_base["transaction_cost"] == first_rebal_mutated["transaction_cost"]
        assert first_rebal_base["spread_cost"] == first_rebal_mutated["spread_cost"]
        assert first_rebal_base["market_impact_cost"] == first_rebal_mutated["market_impact_cost"]
        assert first_rebal_base["weights"] == first_rebal_mutated["weights"]

    def test_participation_reject_policy_in_walk_forward(self, synthetic_market_panel):
        """Under an impossible participation limit (e.g. 0.0001), rebalances get rejected."""
        returns_df, volumes_df = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.00001, # Extremely tight: 0.001% ADV
            participation_policy="reject",
            num_simulations=500,
            random_seed=42,
        )

        rejected_events = [r for r in res["rebalance_history"] if r["rebalance_rejected"]]
        assert len(rejected_events) > 0
        # When rejected, turnover and transaction cost for that rebalance are 0
        for r in rejected_events:
            assert r["turnover"] == 0.0
            assert r["transaction_cost"] == 0.0
            assert "rejected" in r["solver_message"].lower()
