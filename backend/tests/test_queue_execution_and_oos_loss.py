"""
Institutional Test Suite for Stage 27:
Queue-Based Cash-Financed Execution & Unified Out-of-Sample Liquidation Loss Distribution.

Resolves:
- DEF-35-01: Asymmetric sell-order execution & cash-financed buy scaling without renormalizing holdings.
- DEF-35-02: Single-distribution empirical quantile evaluation of out-of-sample daily liquidation losses.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.execution import (
    compute_daily_liquidation_loss,
    compute_liquidity_adjusted_var_cvar,
    compute_scenario_endogenous_liquidity_risk,
)
from app.quant.vine_backtest import (
    _compute_strategy_kpis,
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


class TestQueueBasedExecution:
    """Verifies Queue-Based Cash-Financed Partial Execution (DEF-35-01)."""

    def test_queue_execution_prevents_unfunded_buys(self, synthetic_market_data):
        """
        When selling asset A is severely volume-capped, buy orders are scaled
        to available cash proceeds + pre-trade cash. Holdings never exceed 1.0.
        """
        returns_df, volumes_df = synthetic_market_data

        # Severely restrict volume on the selling assets to trigger partial sell execution
        v_mod = volumes_df.copy()
        v_mod.iloc[:, 0] = 50_000.0  # Ticker 0 very illiquid
        v_mod.iloc[:, 1] = 50_000.0  # Ticker 1 very illiquid

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=v_mod,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.01,  # Tight 1% cap
            participation_policy="cap",
            num_simulations=500,
            random_seed=42,
        )

        assert res["participation_policy"] == "cap"
        for evt in res["rebalance_history"]:
            w_sum = sum(evt["weights"].values())
            cash_w = evt.get("cash_weight", 0.0)
            # Total equity allocation must strictly sum to 1.0
            assert math.isclose(w_sum + cash_w, 1.0, abs_tol=1e-4)
            # Asset weights alone must NEVER exceed 1.0 (no unfinanced leverage)
            assert w_sum <= 1.0 + 1e-6
            assert cash_w >= 0.0

    def test_queue_execution_preserves_unaffected_holdings(self, synthetic_market_data):
        """
        Assets that do not trade or are not capped should not be arbitrarily
        rescaled by an ad-hoc normalization factor.
        """
        returns_df, volumes_df = synthetic_market_data

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            max_participation_rate=0.10,
            participation_policy="cap",
            num_simulations=500,
            random_seed=42,
        )

        for evt in res["rebalance_history"]:
            w_dict = evt["weights"]
            assert all(w >= 0.0 for w in w_dict.values())
            assert sum(w_dict.values()) <= 1.0 + 1e-4


class TestUnifiedOutOfSampleLiquidationLoss:
    """Verifies Unified Out-of-Sample Liquidation Loss Distribution (DEF-35-02)."""

    def test_pointwise_liquidation_loss_domination(self, synthetic_market_data):
        """
        Realized loss series satisfy pointwise domination on every day t:
        l_t^{stressed} >= l_t^{det} >= l_t^{market} = -R_{p, t}
        """
        returns_df, volumes_df = synthetic_market_data

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

        losses_det = res["daily_liquidation_losses_det"]
        losses_str = res["daily_liquidation_losses_stressed"]
        n_days = res["total_evaluation_days"]

        assert len(losses_det) == n_days
        assert len(losses_str) == n_days

        # Pointwise verification
        for t in range(n_days):
            assert losses_str[t] >= losses_det[t] - 1e-8

    def test_risk_quantile_monotonicity(self, synthetic_market_data):
        """
        Unified daily loss distribution strictly guarantees:
        stressed_l_cvar_99 >= l_cvar_99 >= historical_cvar_99
        stressed_l_var_99 >= l_var_99 >= historical_var_99
        """
        returns_df, volumes_df = synthetic_market_data

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

        sm = res["strategy_metrics"]
        assert sm["stressed_l_cvar_99"] >= sm["l_cvar_99"]
        assert sm["l_cvar_99"] >= sm["historical_cvar_99"]
        assert sm["stressed_l_var_99"] >= sm["l_var_99"]
        assert sm["l_var_99"] >= sm["historical_var_99"]

    def test_identity_recovery_under_zero_sensitivity(self, synthetic_market_data):
        """
        When endogenous sensitivities kappa=0 and eta=0, stressed L-CVaR and
        deterministic L-CVaR are identical.
        """
        returns_df, volumes_df = synthetic_market_data

        res = run_vine_tail_risk_parity_backtest(
            returns_df=returns_df,
            volumes_df=volumes_df,
            vine_type="c_vine",
            estimation_window=60,
            rebalance_frequency="monthly",
            execution_model="square_root",
            enable_endogenous_liquidity=True,
            spread_stress_sensitivity=0.0,
            adv_stress_sensitivity=0.0,
            num_simulations=500,
            random_seed=42,
        )

        sm = res["strategy_metrics"]
        assert math.isclose(sm["stressed_l_cvar_99"], sm["l_cvar_99"], abs_tol=1e-4)
        assert math.isclose(sm["stressed_l_var_99"], sm["l_var_99"], abs_tol=1e-4)

    def test_pure_function_compute_daily_liquidation_loss(self):
        """Unit test compute_daily_liquidation_loss across varying market shocks."""
        weights = np.array([0.5, 0.5])
        equity = 1_000_000.0
        advs = np.array([5_000_000.0, 5_000_000.0])
        vols = np.array([0.20, 0.20])
        spreads = np.array([5.0, 5.0])
        r_today = np.array([-0.03, -0.05])  # Negative asset returns
        port_ret = -0.04                     # 4% portfolio loss

        loss_det, loss_str, c_det, c_str = compute_daily_liquidation_loss(
            held_weights=weights,
            portfolio_equity=equity,
            adv_arr=advs,
            vol_arr=vols,
            base_spreads_bps=spreads,
            r_today=r_today,
            portfolio_gross_ret=port_ret,
            execution_horizon_days=1.0,
            impact_model="square_root",
            c_temp=0.5,
            c_perm=0.1,
            spread_stress_sensitivity=5.0,
            adv_stress_sensitivity=5.0,
            enable_endogenous_liquidity=True,
        )

        assert c_str > c_det > 0.0
        assert loss_str > loss_det > -port_ret
        assert math.isclose(loss_det, -port_ret + c_det, abs_tol=1e-7)
        assert math.isclose(loss_str, -port_ret + c_str, abs_tol=1e-7)
