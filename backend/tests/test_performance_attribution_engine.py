"""
Independent Mathematical Verification Suite for Multi-Asset Performance Attribution,
Brinson-Fachler Decomposition, and Cariño Multi-Period Linking.
"""

import math
import numpy as np
import pytest

from app.quant.performance_attribution import (
    compute_single_period_brinson,
    compute_carino_multi_period_linking,
    compute_multi_period_brinson_attribution,
    compute_factor_attribution,
)


def test_hand_calculated_2_asset_2_period_analytical_benchmark():
    """
    Independent hand-calculated analytical benchmark from docs/SESSION_25_CONTRACTS.md:
    Period 1:
        wp = [0.60, 0.40], wb = [0.50, 0.50]
        Rp = [0.04, 0.01], Rb = [0.03, 0.01]
        R_p = 0.0280, R_b = 0.0200, Delta R = +0.0080
        Equity: Alloc = +0.0010, Select = +0.0050, Interact = +0.0010
        Bonds:  Alloc = +0.0010, Select = 0.0000, Interact = 0.0000
    Period 2:
        wp = [0.70, 0.30], wb = [0.50, 0.50]
        Rp = [-0.02, 0.005], Rb = [-0.01, 0.005]
        R_p = -0.0125, R_b = -0.0025, Delta R = -0.0100
        Equity: Alloc = -0.0015, Select = -0.0050, Interact = -0.0020
        Bonds:  Alloc = -0.0015, Select = 0.0000, Interact = 0.0000
    Multi-Period Compounding:
        R_p_cum = (1.0280)(0.9875) - 1 = +0.015150
        R_b_cum = (1.0200)(0.9975) - 1 = +0.017450
        Delta R_cum = -0.002300
    """
    # 1. Period 1 Single-Period
    p1 = compute_single_period_brinson(
        portfolio_segment_weights={"Equity": 0.60, "Bonds": 0.40},
        benchmark_segment_weights={"Equity": 0.50, "Bonds": 0.50},
        portfolio_segment_returns={"Equity": 0.04, "Bonds": 0.01},
        benchmark_segment_returns={"Equity": 0.03, "Bonds": 0.01},
        method="brinson_fachler",
    )
    assert p1["portfolio_return"] == pytest.approx(0.0280, abs=1e-8)
    assert p1["benchmark_return"] == pytest.approx(0.0200, abs=1e-8)
    assert p1["active_return"] == pytest.approx(0.0080, abs=1e-8)

    eq_p1 = next(s for s in p1["segment_attributions"] if s["segment"] == "Equity")
    bd_p1 = next(s for s in p1["segment_attributions"] if s["segment"] == "Bonds")

    assert eq_p1["allocation_effect"] == pytest.approx(0.0010, abs=1e-8)
    assert eq_p1["selection_effect"] == pytest.approx(0.0050, abs=1e-8)
    assert eq_p1["interaction_effect"] == pytest.approx(0.0010, abs=1e-8)

    assert bd_p1["allocation_effect"] == pytest.approx(0.0010, abs=1e-8)
    assert bd_p1["selection_effect"] == pytest.approx(0.0000, abs=1e-8)
    assert bd_p1["interaction_effect"] == pytest.approx(0.0000, abs=1e-8)

    assert p1["reconciliation_error"] < 1e-12

    # 2. Period 2 Single-Period
    p2 = compute_single_period_brinson(
        portfolio_segment_weights={"Equity": 0.70, "Bonds": 0.30},
        benchmark_segment_weights={"Equity": 0.50, "Bonds": 0.50},
        portfolio_segment_returns={"Equity": -0.02, "Bonds": 0.005},
        benchmark_segment_returns={"Equity": -0.01, "Bonds": 0.005},
        method="brinson_fachler",
    )
    assert p2["portfolio_return"] == pytest.approx(-0.0125, abs=1e-8)
    assert p2["benchmark_return"] == pytest.approx(-0.0025, abs=1e-8)
    assert p2["active_return"] == pytest.approx(-0.0100, abs=1e-8)

    eq_p2 = next(s for s in p2["segment_attributions"] if s["segment"] == "Equity")
    bd_p2 = next(s for s in p2["segment_attributions"] if s["segment"] == "Bonds")

    assert eq_p2["allocation_effect"] == pytest.approx(-0.0015, abs=1e-8)
    assert eq_p2["selection_effect"] == pytest.approx(-0.0050, abs=1e-8)
    assert eq_p2["interaction_effect"] == pytest.approx(-0.0020, abs=1e-8)

    assert bd_p2["allocation_effect"] == pytest.approx(-0.0015, abs=1e-8)
    assert bd_p2["selection_effect"] == pytest.approx(0.0000, abs=1e-8)
    assert bd_p2["interaction_effect"] == pytest.approx(0.0000, abs=1e-8)

    assert p2["reconciliation_error"] < 1e-12

    # 3. Cariño Multi-Period Linking
    linked = compute_carino_multi_period_linking([p1, p2])
    assert linked["cumulative_portfolio_return"] == pytest.approx(0.01515, abs=1e-8)
    assert linked["cumulative_benchmark_return"] == pytest.approx(0.01745, abs=1e-8)
    assert linked["cumulative_active_return"] == pytest.approx(-0.00230, abs=1e-8)

    # Reconciles exactly to cumulative active return
    assert linked["reconciliation_error"] < 1e-12


def test_brinson_fachler_vs_hood_beebower():
    """Verifies that BF and BHB share identical selection and interaction effects,
    differing solely in the benchmark return offset of the allocation effect."""
    weights_p = {"Tech": 0.6, "Energy": 0.4}
    weights_b = {"Tech": 0.4, "Energy": 0.6}
    rets_p = {"Tech": 0.10, "Energy": 0.02}
    rets_b = {"Tech": 0.08, "Energy": 0.01}

    bf = compute_single_period_brinson(weights_p, weights_b, rets_p, rets_b, method="brinson_fachler")
    bhb = compute_single_period_brinson(weights_p, weights_b, rets_p, rets_b, method="brinson_hood_beebower")

    # Both reconcile to active return
    assert bf["reconciliation_error"] < 1e-12
    assert bhb["reconciliation_error"] < 1e-12

    # Selection & interaction are identical
    assert bf["total_selection_effect"] == pytest.approx(bhb["total_selection_effect"], abs=1e-12)
    assert bf["total_interaction_effect"] == pytest.approx(bhb["total_interaction_effect"], abs=1e-12)


def test_identical_portfolio_and_benchmark_zero_active():
    """Identical weights and returns must yield strictly zero active return and zero effects."""
    w = {"A": 0.5, "B": 0.5}
    r = {"A": 0.05, "B": -0.02}

    res = compute_single_period_brinson(w, w, r, r)
    assert res["active_return"] == 0.0
    assert res["total_allocation_effect"] == 0.0
    assert res["total_selection_effect"] == 0.0
    assert res["total_interaction_effect"] == 0.0
    assert res["reconciliation_error"] == 0.0


def test_multi_period_brinson_attribution_pipeline():
    """Verifies the end-to-end multi-period pipeline from prices to linked segment tables."""
    rng = np.random.default_rng(42)
    T = 60
    tickers = ["AAPL", "MSFT", "XOM", "CVX"]
    dates = [f"2024-01-{i+1:02d}" for i in range(T)]

    # Generate geometric Brownian motion prices
    p = np.zeros((T, 4))
    p[0] = [150.0, 300.0, 100.0, 140.0]
    for t in range(1, T):
        p[t] = p[t - 1] * (1.0 + rng.normal(0.0005, 0.015, size=4))

    pw = {"AAPL": 0.4, "MSFT": 0.3, "XOM": 0.15, "CVX": 0.15}
    bw = {"AAPL": 0.25, "MSFT": 0.25, "XOM": 0.25, "CVX": 0.25}
    mapping = {"AAPL": "Tech", "MSFT": "Tech", "XOM": "Energy", "CVX": "Energy"}

    res = compute_multi_period_brinson_attribution(
        price_matrix=p,
        dates=dates,
        tickers=tickers,
        portfolio_weights=pw,
        benchmark_weights=bw,
        segment_mapping=mapping,
        frequency="monthly",
    )

    assert res["summary"]["total_periods"] > 1
    assert res["summary"]["reconciliation_error"] < 1e-10
    assert len(res["segment_attribution"]) == 2  # Tech, Energy
    assert len(res["time_series"]) == res["summary"]["total_periods"]


def test_factor_attribution_decomposition():
    """Verifies Barra systematic active return and tracking error risk decomposition."""
    rng = np.random.default_rng(101)
    T = 250
    N = 3

    # Generate 2 synthetic factors: Market (MKT), Value (HML)
    factor_rets = rng.normal(0.0003, 0.01, size=(T, 2))
    factor_names = ["MKT", "HML"]

    # Asset loadings
    true_betas = np.array([
        [1.2, 0.5],
        [0.8, -0.4],
        [1.0, 0.1],
    ])
    noise = rng.normal(0.0, 0.005, size=(T, N))
    asset_rets = factor_rets @ true_betas.T + noise

    tickers = ["A", "B", "C"]
    wp = {"A": 0.6, "B": 0.2, "C": 0.2}
    bw = {"A": 0.33, "B": 0.33, "C": 0.34}

    res = compute_factor_attribution(
        portfolio_weights=wp,
        benchmark_weights=bw,
        asset_returns=asset_rets,
        factor_returns=factor_rets,
        factor_names=factor_names,
    )

    # Active return = systematic + specific
    assert res["total_active_return"] == pytest.approx(
        res["systematic_active_return"] + res["specific_active_return"], abs=1e-8
    )

    # Active risk shares sum to 100%
    assert res["systematic_risk_percent"] + res["specific_risk_percent"] == pytest.approx(100.0, abs=1e-2)
    assert len(res["factor_contributions"]) == 2
