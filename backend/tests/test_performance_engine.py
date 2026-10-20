"""
Mathematical tests for portfolio performance attribution, active risk,
benchmark metrics, and Menchero multi-period contribution linking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.performance import (
    align_return_series,
    calculate_active_returns,
    calculate_beta,
    calculate_capture_ratios,
    calculate_information_ratio,
    calculate_jensens_alpha,
    calculate_multi_period_contributions,
    calculate_single_period_contributions,
    calculate_tracking_error,
    calculate_treynor_ratio,
    evaluate_comparative_performance,
)


def test_align_return_series_inner_join():
    """Verify that return series are synchronized on exact overlapping dates."""
    dates_p = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    dates_b = ["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]

    s_p = pd.Series([0.01, 0.02, -0.01, 0.03], index=dates_p)
    s_b = pd.Series([0.005, 0.015, -0.005, 0.02], index=dates_b)

    aligned_p, aligned_b = align_return_series(s_p, s_b)

    assert len(aligned_p) == 3
    assert len(aligned_b) == 3
    assert list(aligned_p.index) == ["2026-01-02", "2026-01-03", "2026-01-04"]
    assert aligned_p.iloc[0] == 0.02
    assert aligned_b.iloc[0] == 0.005


def test_align_return_series_rejects_empty_overlap():
    """Verify that disjoint dates raise ValueError without fabricating data."""
    s_p = pd.Series([0.01, 0.02], index=["2026-01-01", "2026-01-02"])
    s_b = pd.Series([0.01, 0.02], index=["2026-02-01", "2026-02-02"])

    with pytest.raises(ValueError, match="zero overlapping trading dates"):
        align_return_series(s_p, s_b)


def test_calculate_active_returns():
    """Verify periodic active return: a_t = r_{p,t} - r_{b,t}."""
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    s_p = pd.Series([0.02, -0.01, 0.04], index=dates)
    s_b = pd.Series([0.01, -0.02, 0.01], index=dates)

    active = calculate_active_returns(s_p, s_b)
    np.testing.assert_allclose(active.to_numpy(), [0.01, 0.01, 0.03], atol=1e-12)


def test_tracking_error_and_information_ratio_hand_calculation():
    """
    Independent hand-calculation test for Tracking Error and Information Ratio:
    Active returns a = [0.01, -0.01, 0.02, 0.00]
    mean(a) = 0.005
    sample variance = ( (0.005)^2 + (-0.015)^2 + (0.015)^2 + (-0.005)^2 ) / 3
                    = ( 0.000025 + 0.000225 + 0.000225 + 0.000025 ) / 3
                    = 0.0005 / 3 = 0.000166666667
    sample std = sqrt(0.0005 / 3) = 0.012909944
    annualized TE (m=252) = 0.012909944 * sqrt(252) = 0.012909944 * 15.87450787 = 0.2049390
    Information Ratio = (0.005 * 252) / 0.2049390 = 1.26 / 0.2049390 = 6.14817
    """
    active_series = pd.Series([0.01, -0.01, 0.02, 0.00], index=["D1", "D2", "D3", "D4"])

    te = calculate_tracking_error(active_series, periods_per_year=252)
    expected_te = np.sqrt(0.0005 / 3) * np.sqrt(252)
    assert pytest.approx(te, rel=1e-5) == expected_te

    ir = calculate_information_ratio(active_series, periods_per_year=252)
    expected_ir = (0.005 * 252) / expected_te
    assert ir is not None
    assert pytest.approx(ir, rel=1e-5) == expected_ir


def test_zero_tracking_error_handling():
    """Verify that identical portfolio and benchmark returns produce TE=0 and IR=None."""
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    s_p = pd.Series([0.01, 0.02, 0.03], index=dates)
    active = calculate_active_returns(s_p, s_p)

    te = calculate_tracking_error(active)
    assert te == 0.0

    ir = calculate_information_ratio(active)
    assert ir is None


def test_beta_calculation_hand_calculated():
    """
    Independent hand calculation of Beta:
    r_b = [0.01, 0.02, 0.03] -> mean = 0.02
    r_p = [0.02, 0.04, 0.06] -> mean = 0.04
    Here r_p = 2 * r_b, so Beta must be exactly 2.0.
    """
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    s_b = pd.Series([0.01, 0.02, 0.03], index=dates)
    s_p = pd.Series([0.02, 0.04, 0.06], index=dates)

    beta = calculate_beta(s_p, s_b)
    assert beta is not None
    assert pytest.approx(beta, abs=1e-6) == 2.0


def test_jensens_alpha_and_treynor_ratio():
    """
    Independent verification of Jensen's Alpha and Treynor Ratio:
    r_b = [0.01, 0.02, 0.03] -> mean = 0.02
    r_p = [0.02, 0.04, 0.06] -> mean = 0.04, beta = 2.0
    r_f_annual = 0.0 -> r_f_periodic = 0.0
    periodic alpha = 0.04 - 2.0 * 0.02 = 0.0
    annualized alpha = 0.0 * 252 = 0.0
    Treynor = (0.04 * 252) / 2.0 = 5.04
    """
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    s_b = pd.Series([0.01, 0.02, 0.03], index=dates)
    s_p = pd.Series([0.02, 0.04, 0.06], index=dates)

    alpha = calculate_jensens_alpha(s_p, s_b, risk_free_rate_annual=0.0, periods_per_year=252)
    assert alpha is not None
    assert pytest.approx(alpha, abs=1e-6) == 0.0

    beta = calculate_beta(s_p, s_b)
    treynor = calculate_treynor_ratio(s_p, beta, risk_free_rate_annual=0.0, periods_per_year=252)
    assert treynor is not None
    assert pytest.approx(treynor, abs=1e-6) == 5.04


def test_capture_ratios():
    """
    Test Up-Capture and Down-Capture ratios:
    Day 1: r_b = 0.02 (>0), r_p = 0.03 -> Up-period
    Day 2: r_b = -0.01 (<0), r_p = -0.005 -> Down-period
    Day 3: r_b = 0.01 (>0), r_p = 0.02 -> Up-period
    Up-period benchmark return: (1.02)*(1.01) - 1 = 1.0302 - 1 = 0.0302
    Up-period portfolio return: (1.03)*(1.02) - 1 = 1.0506 - 1 = 0.0506
    Up-Capture = 0.0506 / 0.0302 = 1.6754967
    Down-period benchmark return = -0.01
    Down-period portfolio return = -0.005
    Down-Capture = -0.005 / -0.01 = 0.5
    """
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    s_b = pd.Series([0.02, -0.01, 0.01], index=dates)
    s_p = pd.Series([0.03, -0.005, 0.02], index=dates)

    up_cap, down_cap = calculate_capture_ratios(s_p, s_b)
    assert up_cap is not None
    assert pytest.approx(up_cap, rel=1e-4) == 0.0506 / 0.0302
    assert down_cap is not None
    assert pytest.approx(down_cap, rel=1e-4) == 0.5


def test_single_period_contributions():
    """Verify single period asset contribution: c_i = w_i * r_i."""
    weights = {"AAPL": 0.6, "MSFT": 0.4}
    returns = {"AAPL": 0.05, "MSFT": -0.02}

    contrib = calculate_single_period_contributions(weights, returns)
    assert pytest.approx(contrib["AAPL"], abs=1e-9) == 0.03
    assert pytest.approx(contrib["MSFT"], abs=1e-9) == -0.008
    assert pytest.approx(sum(contrib.values()), abs=1e-9) == 0.022


def test_multi_period_contributions_menchero_exact_reconciliation():
    """
    Test Menchero (2000) Logarithmic Linking:
    Verify that sum of linked contributions across all assets exactly reconciles
    to the compounded cumulative portfolio return (sum C_i == R_p).
    """
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    asset_ret_data = {
        "AAPL": [0.02, -0.01, 0.03, 0.015],
        "MSFT": [0.01, 0.015, -0.02, 0.005],
        "GOOG": [0.03, -0.005, 0.01, 0.02],
    }
    df_ret = pd.DataFrame(asset_ret_data, index=dates)
    weights = {"AAPL": 0.5, "MSFT": 0.3, "GOOG": 0.2}

    # True daily portfolio returns and compounded cumulative return
    daily_port_ret = (df_ret * pd.Series(weights)).sum(axis=1)
    true_cum_ret = float(np.prod(1.0 + daily_port_ret) - 1.0)

    linked_contributions = calculate_multi_period_contributions(df_ret, weights)

    assert set(linked_contributions.keys()) == {"AAPL", "MSFT", "GOOG"}
    sum_contributions = sum(linked_contributions.values())

    # Exact reconciliation to cumulative portfolio return within 10^-6
    assert pytest.approx(sum_contributions, abs=1e-6) == true_cum_ret


def test_evaluate_comparative_performance_full_suite():
    """
    Verify complete evaluation pipeline outputs expected types, valid numbers,
    and reconciles cumulative returns.
    """
    np.random.seed(42)
    n = 252
    dates = pd.date_range("2025-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()

    r_b = pd.Series(np.random.normal(0.0004, 0.01, n), index=dates)
    # Portfolio with positive alpha and beta ~ 1.2
    r_p = pd.Series(0.0002 + 1.2 * r_b + np.random.normal(0.0, 0.005, n), index=dates)

    res = evaluate_comparative_performance(r_p, r_b, risk_free_rate_annual=0.03, periods_per_year=252)

    assert res.observation_count == n
    assert res.start_date == dates[0]
    assert res.end_date == dates[-1]
    assert np.isfinite(res.portfolio_cumulative_return)
    assert np.isfinite(res.benchmark_cumulative_return)
    assert pytest.approx(res.arithmetic_active_return, abs=1e-6) == (
        res.portfolio_cumulative_return - res.benchmark_cumulative_return
    )
    assert res.beta is not None
    assert pytest.approx(res.beta, abs=0.2) == 1.2
    assert res.alpha_annualized is not None
    assert res.tracking_error > 0.0
    assert res.information_ratio is not None
    assert res.up_capture_ratio is not None
    assert res.down_capture_ratio is not None
