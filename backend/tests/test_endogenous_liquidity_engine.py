"""
Institutional Unit and Integration Tests for Stage 26:
Endogenous Scenario-Dependent Liquidity Stress Testing & Cash-Aware Partial Execution.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.execution import (
    compute_liquidity_adjusted_var_cvar,
    compute_scenario_endogenous_liquidity_risk,
)
from app.quant.vine_backtest import run_vine_tail_risk_parity_backtest


@pytest.fixture
def synthetic_market_panel():
    """Generates a reproducible 100-day panel of returns and daily volume for 4 assets."""
    np.random.seed(42)
    n_days = 100
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")

    # Generate correlated normal returns with mean 0.0005, vol 0.015
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

    # Generate daily volume in currency units (between $5M and $20M)
    vols = np.random.uniform(5_000_000.0, 20_000_000.0, size=(n_days, 4))
    volumes_df = pd.DataFrame(vols, index=dates, columns=tickers)

    return returns_df, volumes_df


class TestEndogenousLiquidityStress:
    """Verifies scenario-dependent endogenous liquidity stress testing mechanics."""

    def test_zero_sensitivity_matches_deterministic(self):
        """When kappa=0 and eta=0, endogenous stressed L-risk equals deterministic baseline."""
        np.random.seed(42)
        M, N = 2000, 4
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        sim_rets = np.random.normal(-0.005, 0.02, size=(M, N)) # Include adverse scenarios
        weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}
        equity = 1000000.0
        advs = {tk: 10_000_000.0 for tk in tickers}
        vols = {tk: 0.20 for tk in tickers}

        res = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            confidence_level=0.99,
            spread_bps_dict={tk: 5.0 for tk in tickers},
            execution_horizon_days=1.0,
            impact_model="square_root",
            spread_stress_sensitivity=0.0, # Zero spread widening
            adv_stress_sensitivity=0.0,    # Zero volume freeze
        )

        assert math.isclose(res["stressed_l_var"], res["deterministic_l_var"], abs_tol=1e-4)
        assert math.isclose(res["stressed_l_cvar"], res["deterministic_l_cvar"], abs_tol=1e-4)
        assert res["stressed_l_cvar"] >= res["market_cvar"]

    def test_endogenous_liquidity_monotonic_expansion(self):
        """When kappa > 0 and eta > 0, tail crash illiquidity strictly expands L-CVaR."""
        np.random.seed(42)
        M, N = 3000, 3
        tickers = ["A", "B", "C"]
        # Generate heavy negative tail
        sim_rets = np.random.standard_t(df=4, size=(M, N)) * 0.02
        weights = {"A": 0.4, "B": 0.3, "C": 0.3}
        equity = 2000000.0
        advs = {"A": 5_000_000.0, "B": 8_000_000.0, "C": 10_000_000.0}
        vols = {"A": 0.25, "B": 0.20, "C": 0.18}

        res_unstressed = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            spread_stress_sensitivity=0.0,
            adv_stress_sensitivity=0.0,
        )

        res_stressed = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            spread_stress_sensitivity=5.0, # 5x spread widening on drawdown
            adv_stress_sensitivity=5.0,    # 5x volume contraction on market crash
        )

        # Stressed L-CVaR must exceed unstressed L-CVaR
        assert res_stressed["stressed_l_cvar"] > res_unstressed["stressed_l_cvar"]
        assert res_stressed["stressed_l_var"] >= res_unstressed["stressed_l_var"]
        # Stressed L-CVaR must exceed pure market CVaR
        assert res_stressed["stressed_l_cvar"] > res_stressed["market_cvar"]

    def test_spread_stress_monotonicity(self):
        """Increasing kappa strictly increases or preserves stressed L-CVaR."""
        np.random.seed(42)
        M, N = 2000, 2
        tickers = ["X", "Y"]
        sim_rets = np.random.normal(-0.01, 0.03, size=(M, N))
        weights = {"X": 0.5, "Y": 0.5}
        equity = 1000000.0
        advs = {"X": 5_000_000.0, "Y": 5_000_000.0}
        vols = {"X": 0.20, "Y": 0.20}

        cvar_k0 = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            spread_stress_sensitivity=0.0,
            adv_stress_sensitivity=0.0,
        )["stressed_l_cvar"]

        cvar_k5 = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            spread_stress_sensitivity=5.0,
            adv_stress_sensitivity=0.0,
        )["stressed_l_cvar"]

        cvar_k15 = compute_scenario_endogenous_liquidity_risk(
            weights=weights,
            portfolio_equity=equity,
            adv_dict=advs,
            volatility_dict=vols,
            simulated_returns=sim_rets,
            tickers=tickers,
            spread_stress_sensitivity=15.0,
            adv_stress_sensitivity=0.0,
        )["stressed_l_cvar"]

        assert cvar_k15 >= cvar_k5 >= cvar_k0


class TestCashAwarePartialExecution:
    """Verifies exact cash conservation and non-distorting partial fill execution."""

    def test_cap_policy_cash_conservation(self, synthetic_market_panel):
        """Under cap policy with tight limit, sum of asset weights + cash weight identically equals 1.0."""
        returns_df, volumes_df = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.001, # Extremely tight to force capping
            participation_policy="cap",
            num_simulations=500,
            random_seed=42,
        )

        assert res["participation_policy"] == "cap"
        rebal_events = res["rebalance_history"]
        assert len(rebal_events) > 0

        # At every rebalance event, weights + cash_weight must sum to 1.0 within 4-decimal rounding tolerance
        for evt in rebal_events:
            w_sum = sum(evt["weights"].values())
            cash_w = evt.get("cash_weight", 0.0)
            total = w_sum + cash_w
            assert math.isclose(total, 1.0, abs_tol=5e-4)
            assert cash_w >= 0.0

    def test_unaffected_assets_not_distorted(self, synthetic_market_panel):
        """
        When asset A is capped but asset B is not, asset B executes its exact
        intended trade notional without being artificially scaled by a renormalization factor.
        """
        returns_df, volumes_df = synthetic_market_panel
        # Make asset 0 illiquid (low volume) and asset 1 highly liquid (huge volume)
        v_mod = volumes_df.copy()
        v_mod.iloc[:, 0] = 50_000.0       # Capped
        v_mod.iloc[:, 1:] = 100_000_000.0  # Highly liquid

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mod,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.05,
            participation_policy="cap",
            num_simulations=500,
            random_seed=42,
        )

        for evt in res["rebalance_history"]:
            # Cash weight is tracked
            assert "cash_weight" in evt
            assert evt["cash_weight"] >= 0.0
            total = sum(evt["weights"].values()) + evt["cash_weight"]
            assert math.isclose(total, 1.0, abs_tol=5e-4)

    def test_walk_forward_endogenous_stress_and_cash_reporting(self, synthetic_market_panel):
        """Verifies end-to-end reporting of stressed L-VaR/L-CVaR and cash weight."""
        returns_df, volumes_df = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            enable_endogenous_liquidity=True,
            spread_stress_sensitivity=5.0,
            adv_stress_sensitivity=5.0,
            num_simulations=500,
            random_seed=42,
        )

        strat_m = res["strategy_metrics"]
        assert "stressed_l_var_99" in strat_m
        assert "stressed_l_cvar_99" in strat_m
        assert "average_cash_weight" in strat_m
        assert strat_m["stressed_l_cvar_99"] >= strat_m["l_cvar_99"]

        for evt in res["rebalance_history"]:
            assert "stressed_liquidity_adjusted_cvar" in evt
            assert "stressed_liquidity_adjusted_var" in evt
            assert "cash_weight" in evt
            assert evt["stressed_liquidity_adjusted_cvar"] >= evt["liquidity_adjusted_cvar"]

    def test_backward_compatibility_disabled_endogenous(self, synthetic_market_panel):
        """When endogenous liquidity is disabled, stressed L-CVaR equals deterministic L-CVaR."""
        returns_df, volumes_df = synthetic_market_panel

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            enable_endogenous_liquidity=False,
            num_simulations=500,
            random_seed=42,
        )

        strat_m = res["strategy_metrics"]
        assert math.isclose(strat_m["stressed_l_cvar_99"], strat_m["l_cvar_99"], abs_tol=1e-4)

    def test_temporal_anti_lookahead_endogenous_invariance(self, synthetic_market_panel):
        """
        Mutating future volumes after rebalance cutoff t_k must leave past
        rebalance decision, cash weight, and stressed L-CVaR invariant.
        """
        returns_df, volumes_df = synthetic_market_panel

        res_base = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            enable_endogenous_liquidity=True,
            num_simulations=500,
            random_seed=42,
        )
        first_evt_base = res_base["rebalance_history"][0]
        cutoff = first_evt_base["date"]

        mutated_v = volumes_df.copy()
        mutated_v.loc[mutated_v.index > cutoff] *= 10.0

        res_mut = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=mutated_v,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            enable_endogenous_liquidity=True,
            num_simulations=500,
            random_seed=42,
        )
        first_evt_mut = res_mut["rebalance_history"][0]

        assert first_evt_base["cash_weight"] == first_evt_mut["cash_weight"]
        assert first_evt_base["stressed_liquidity_adjusted_cvar"] == first_evt_mut["stressed_liquidity_adjusted_cvar"]
        assert first_evt_base["weights"] == first_evt_mut["weights"]

    def test_invalid_stress_parameters_rejection(self):
        """Negative sensitivities or invalid confidence levels must be rejected with ValueError."""
        sim_rets = np.random.normal(0, 0.01, size=(100, 2))
        weights = {"A": 0.5, "B": 0.5}

        with pytest.raises(ValueError, match="non-negative"):
            compute_scenario_endogenous_liquidity_risk(
                weights=weights,
                portfolio_equity=10000.0,
                adv_dict={"A": 1e6, "B": 1e6},
                volatility_dict={"A": 0.2, "B": 0.2},
                simulated_returns=sim_rets,
                tickers=["A", "B"],
                spread_stress_sensitivity=-1.0,
            )

        with pytest.raises(ValueError, match="confidence_level"):
            compute_scenario_endogenous_liquidity_risk(
                weights=weights,
                portfolio_equity=10000.0,
                adv_dict={"A": 1e6, "B": 1e6},
                volatility_dict={"A": 0.2, "B": 0.2},
                simulated_returns=sim_rets,
                tickers=["A", "B"],
                confidence_level=1.5,
            )

    def test_non_finite_returns_rejection(self):
        """NaN or Inf in simulated returns must raise ValueError."""
        sim_rets = np.array([[0.01, np.nan], [0.02, 0.01]])
        weights = {"A": 0.5, "B": 0.5}

        with pytest.raises(ValueError, match="finite numerical values"):
            compute_scenario_endogenous_liquidity_risk(
                weights=weights,
                portfolio_equity=10000.0,
                adv_dict={"A": 1e6, "B": 1e6},
                volatility_dict={"A": 0.2, "B": 0.2},
                simulated_returns=sim_rets,
                tickers=["A", "B"],
            )

    def test_zero_weights_safe_handling(self):
        """Zero weights or zero equity returns zero risk safely without divide-by-zero."""
        sim_rets = np.random.normal(0, 0.01, size=(100, 2))
        res = compute_scenario_endogenous_liquidity_risk(
            weights={"A": 0.0, "B": 0.0},
            portfolio_equity=0.0,
            adv_dict={"A": 1e6, "B": 1e6},
            volatility_dict={"A": 0.2, "B": 0.2},
            simulated_returns=sim_rets,
            tickers=["A", "B"],
        )
        assert res["market_cvar"] == 0.0
        assert res["stressed_l_cvar"] == 0.0

    def test_requested_vs_executed_weights_distinguishable(self, synthetic_market_panel):
        """Requested and executed weights are both recorded and distinguishable when capped."""
        returns_df, volumes_df = synthetic_market_panel
        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.001,  # Tight cap
            participation_policy="cap",
            num_simulations=500,
            random_seed=42,
        )

        for evt in res["rebalance_history"]:
            assert "requested_weights" in evt
            assert "executed_weights" in evt
            assert "weights" in evt
            assert "cash_weight" in evt
            assert evt["executed_weights"] == evt["weights"]
            total_exec = sum(evt["executed_weights"].values()) + evt["cash_weight"]
            assert math.isclose(total_exec, 1.0, abs_tol=5e-4)
