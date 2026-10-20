"""
Unit tests and analytical mathematical benchmarks for Stage 20:
Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.quant.regime_switching import (
    GaussianHMM,
    blend_regime_covariance,
    compute_volatility_target_allocation,
    run_regime_switching_walk_forward_backtest,
)


def test_hmm_hand_calculated_analytical_benchmark():
    """
    Verifies the closed-form 2-state HMM benchmark specified in docs/SESSION_24_CONTRACTS.md:
    - pi = [0.80, 0.20]
    - A = [[0.90, 0.10], [0.20, 0.80]]
    - mu = [0.0010, -0.0020]
    - sigma = [0.0100, 0.0300]
    - r1 = +0.0050, r2 = -0.0350

    Analytical solutions:
    - alpha1_scaled = [0.91924471, 0.08075529]
    - alpha2_scaled = [0.04343425, 0.95656575]
    - k1 = 0.49099744
    - k2 = 0.21415503
    """
    hmm = GaussianHMM(num_states=2)
    hmm.pi_ = np.array([0.80, 0.20], dtype=np.float64)
    hmm.A_ = np.array([[0.90, 0.10], [0.20, 0.80]], dtype=np.float64)
    hmm.means_ = np.array([[0.0010], [-0.0020]], dtype=np.float64)
    hmm.covs_ = np.array([[[0.0100**2]], [[0.0300**2]]], dtype=np.float64)
    hmm.is_fitted_ = True

    r = np.array([0.0050, -0.0350], dtype=np.float64)
    filtered_probs = hmm.predict_proba(r, causal=True)

    # 1. Verify filtered probabilities at t=1
    np.testing.assert_allclose(filtered_probs[0, 0], 0.91924471, atol=1e-6)
    np.testing.assert_allclose(filtered_probs[0, 1], 0.08075529, atol=1e-6)

    # 2. Verify filtered probabilities at t=2
    np.testing.assert_allclose(filtered_probs[1, 0], 0.04343425, atol=1e-6)
    np.testing.assert_allclose(filtered_probs[1, 1], 0.95656575, atol=1e-6)

    # 3. Verify volatility targeting scaling factors
    vol1_daily = math.sqrt(filtered_probs[0, 0] * 0.01**2 + filtered_probs[0, 1] * 0.03**2)
    vol1_ann = vol1_daily * math.sqrt(252.0)
    k1 = min(1.50, 0.10 / vol1_ann)
    np.testing.assert_allclose(k1, 0.49099744, atol=1e-6)

    vol2_daily = math.sqrt(filtered_probs[1, 0] * 0.01**2 + filtered_probs[1, 1] * 0.03**2)
    vol2_ann = vol2_daily * math.sqrt(252.0)
    k2 = min(1.50, 0.10 / vol2_ann)
    np.testing.assert_allclose(k2, 0.21415503, atol=1e-6)


def test_hmm_viterbi_state_decoding():
    """Verifies that Viterbi decoding correctly captures regimes across calm and crisis periods."""
    hmm = GaussianHMM(num_states=2)
    hmm.pi_ = np.array([0.90, 0.10], dtype=np.float64)
    hmm.A_ = np.array([[0.95, 0.05], [0.10, 0.90]], dtype=np.float64)
    hmm.means_ = np.array([[0.001], [-0.003]], dtype=np.float64)
    hmm.covs_ = np.array([[[0.008**2]], [[0.035**2]]], dtype=np.float64)
    hmm.is_fitted_ = True

    # Calm sequence followed by severe crash sequence
    calm = np.full(10, 0.001)
    crash = np.full(10, -0.040)
    series = np.concatenate([calm, crash])

    states = hmm.predict(series)
    # First 10 days should decode as State 0 (Calm)
    assert np.all(states[:10] == 0)
    # Next 10 days should decode as State 1 (Crash)
    assert np.all(states[10:] == 1)


def test_hmm_label_switching_resolution_by_volatility_ordering():
    """
    Verifies that after EM fitting, states are deterministically sorted such that
    State 0 always has lower variance than State 1 (resolving the label-switching issue).
    """
    rng = np.random.default_rng(123)
    # Generate 200 synthetic returns: 100 calm (vol 0.01) + 100 turbulent (vol 0.04)
    rets_calm = rng.normal(0.001, 0.01, size=100)
    rets_turb = rng.normal(-0.002, 0.04, size=100)
    rets = np.concatenate([rets_calm, rets_turb])

    hmm = GaussianHMM(num_states=2, random_state=42)
    hmm.fit(rets)

    # State 0 variance MUST be strictly less than State 1 variance
    var_0 = float(np.trace(hmm.covs_[0]))
    var_1 = float(np.trace(hmm.covs_[1]))
    assert var_0 < var_1


def test_regime_covariance_blending_mathematics():
    """
    Verifies that regime-conditioned covariance blending correctly combines
    state covariances and cross-regime mean dispersion.
    """
    cov_1 = np.array([[0.04, 0.01], [0.01, 0.09]], dtype=np.float64)
    cov_2 = np.array([[0.16, 0.05], [0.05, 0.25]], dtype=np.float64)
    mu_1 = np.array([0.08, 0.12], dtype=np.float64)
    mu_2 = np.array([-0.04, -0.06], dtype=np.float64)
    probs = np.array([0.70, 0.30], dtype=np.float64)

    blended_mu, blended_cov = blend_regime_covariance([cov_1, cov_2], [mu_1, mu_2], probs)

    # Mean check: 0.7 * [0.08, 0.12] + 0.3 * [-0.04, -0.06] = [0.056 - 0.012, 0.084 - 0.018] = [0.044, 0.066]
    np.testing.assert_allclose(blended_mu, [0.044, 0.066], atol=1e-6)

    # Symmetry check
    np.testing.assert_allclose(blended_cov, blended_cov.T, atol=1e-12)

    # Positive definiteness
    eigs = np.linalg.eigvalsh(blended_cov)
    assert np.all(eigs > 0)


def test_volatility_targeting_bounds_and_leverage():
    """Verifies that dynamic volatility targeting scales correctly and respects leverage limits."""
    cov = np.array([[0.04 / 252.0]], dtype=np.float64)  # 20% annual vol
    w = np.array([1.0], dtype=np.float64)

    # Target 10% ann vol with 20% realized vol -> k = 10% / 20% = 0.5
    res_derisk = compute_volatility_target_allocation(w, cov, target_volatility_annual=0.10, max_leverage=1.5)
    np.testing.assert_allclose(res_derisk["scaling_factor"], 0.50, atol=1e-4)
    np.testing.assert_allclose(res_derisk["cash_weight"], 0.50, atol=1e-4)

    # Target 40% ann vol with 20% realized vol and max leverage 1.5 -> k capped at 1.5
    res_lever = compute_volatility_target_allocation(w, cov, target_volatility_annual=0.40, max_leverage=1.5)
    np.testing.assert_allclose(res_lever["scaling_factor"], 1.50, atol=1e-4)
    np.testing.assert_allclose(res_lever["cash_weight"], -0.50, atol=1e-4)


def test_regime_walk_forward_zero_look_ahead_bias():
    """
    Verifies strict zero look-ahead bias:
    Changing future price bars strictly after rebalance date t_k must not change
    allocations, regime states, or leverage at or before t_k.
    """
    T, N = 350, 2
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.015, size=(T, N))
    prices_base = 100.0 * np.exp(np.cumsum(rets, axis=0))
    dates = [f"2024-{(i//25)+1:02d}-{(i%25)+1:02d}" for i in range(T)]
    tickers = ["ASSET_A", "ASSET_B"]

    res_base = run_regime_switching_walk_forward_backtest(
        price_df=prices_base,
        dates=dates,
        tickers=tickers,
        num_states=2,
        lookback_window=100,
        rebalance_frequency_days=20,
    )

    # Perturb prices strictly in the final 30 days
    prices_mutated = prices_base.copy()
    prices_mutated[-30:] *= 1.80  # massive future price shock

    res_mutated = run_regime_switching_walk_forward_backtest(
        price_df=prices_mutated,
        dates=dates,
        tickers=tickers,
        num_states=2,
        lookback_window=100,
        rebalance_frequency_days=20,
    )

    # Prior rebalances before the perturbation date must be bitwise identical
    base_events = res_base["rebalance_events"]
    mut_events = res_mutated["rebalance_events"]

    # Compare all rebalance events occurring before t = T - 30
    cutoff_date = dates[T - 30]
    for b_ev, m_ev in zip(base_events, mut_events):
        if b_ev["date"] < cutoff_date:
            assert b_ev["regime_state"] == m_ev["regime_state"]
            assert b_ev["scaling_factor"] == m_ev["scaling_factor"]
            assert b_ev["cash_weight"] == m_ev["cash_weight"]
            assert b_ev["turnover"] == m_ev["turnover"]
