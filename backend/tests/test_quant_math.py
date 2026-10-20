"""
Deterministic unit and numerical tests for Quant Financial Mathematics Core.

Every test validates calculations against independently hand-calculated or
analytically exact mathematical test oracles.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.covariance import correlation_matrix, covariance_matrix
from app.quant.portfolio import (
    normalize_weights,
    portfolio_expected_return,
    portfolio_returns,
    portfolio_variance,
    portfolio_volatility,
    summarize_weights,
    validate_weights,
)
from app.quant.returns import (
    annualized_return,
    cumulative_returns,
    log_returns,
    simple_returns,
)
from app.quant.risk import (
    annual_to_periodic_rate,
    annualized_volatility,
    downside_deviation,
    maximum_drawdown,
    variance,
    volatility,
)

# =====================================================================
# 1. RETURN CALCULATION TESTS
# =====================================================================


def test_simple_returns_hand_calculated_series():
    """
    Test simple returns against an exact hand-calculated price sequence:
    P = [100.0, 105.0, 99.75, 104.7375]
    r1 = 105 / 100 - 1 = +0.05 (+5%)
    r2 = 99.75 / 105 - 1 = -0.05 (-5%)
    r3 = 104.7375 / 99.75 - 1 = +0.05 (+5%)
    """
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    prices = pd.Series([100.0, 105.0, 99.75, 104.7375], index=dates, name="AAPL")

    ret = simple_returns(prices)

    assert pd.isna(ret.iloc[0]), "First observation must be NaN"
    assert np.isclose(ret.iloc[1], 0.05, atol=1e-12)
    assert np.isclose(ret.iloc[2], -0.05, atol=1e-12)
    assert np.isclose(ret.iloc[3], 0.05, atol=1e-12)
    assert (ret.index == dates).all(), "Index must be strictly preserved"


def test_simple_returns_dataframe_multiact():
    """Test simple returns on multi-asset DataFrame preserves column names and index."""
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "AAPL": [100.0, 110.0, 121.0],
            "MSFT": [200.0, 190.0, 190.0],
        },
        index=dates,
    )

    ret = simple_returns(df)
    assert isinstance(ret, pd.DataFrame)
    assert list(ret.columns) == ["AAPL", "MSFT"]
    assert pd.isna(ret.loc[dates[0], "AAPL"])
    assert np.isclose(ret.loc[dates[1], "AAPL"], 0.10)
    assert np.isclose(ret.loc[dates[2], "AAPL"], 0.10)
    assert np.isclose(ret.loc[dates[1], "MSFT"], -0.05)
    assert np.isclose(ret.loc[dates[2], "MSFT"], 0.00)


def test_log_returns_hand_calculated():
    """
    Test log returns:
    P = [100.0, 110.0, 121.0]
    r_log_1 = ln(1.1) = 0.09531017980432493
    r_log_2 = ln(1.1) = 0.09531017980432493
    Total log return = r_log_1 + r_log_2 = ln(1.21) = 0.1906203596086499
    """
    prices = pd.Series([100.0, 110.0, 121.0])
    l_ret = log_returns(prices)

    assert pd.isna(l_ret.iloc[0])
    expected_log = np.log(1.1)
    assert np.isclose(l_ret.iloc[1], expected_log, atol=1e-12)
    assert np.isclose(l_ret.iloc[2], expected_log, atol=1e-12)
    assert np.isclose(l_ret.dropna().sum(), np.log(1.21), atol=1e-12)


def test_cumulative_returns():
    """
    Test cumulative returns:
    r = [0.10, -0.10, 0.20]
    growth = (1.10) * (0.90) * (1.20) = 0.99 * 1.20 = 1.188
    R_cum = 1.188 - 1 = 0.188 (+18.8%)
    """
    r_series = pd.Series([0.10, -0.10, 0.20])
    cum = cumulative_returns(r_series, as_wealth_index=False)
    wealth = cumulative_returns(r_series, as_wealth_index=True)

    assert np.isclose(cum.iloc[0], 0.10, atol=1e-12)
    assert np.isclose(cum.iloc[1], -0.01, atol=1e-12)
    assert np.isclose(cum.iloc[2], 0.188, atol=1e-12)

    assert np.isclose(wealth.iloc[0], 1.10, atol=1e-12)
    assert np.isclose(wealth.iloc[1], 0.99, atol=1e-12)
    assert np.isclose(wealth.iloc[2], 1.188, atol=1e-12)


def test_annualized_return_geometric_and_arithmetic():
    """
    Test geometric CAGR vs arithmetic annualized return with known analytical solutions:
    Two periods of 10% returns: r = [0.10, 0.10], periods_per_year=2.
    - Geometric: ( (1.1)*(1.1) )^(2/2) - 1 = 1.21 - 1 = 0.21 (+21.0%)
    - Arithmetic: mean(r) * 2 = 0.10 * 2 = 0.20 (+20.0%)
    """
    r_series = pd.Series([0.10, 0.10])

    cagr = annualized_return(r_series, periods_per_year=2, method="geometric")
    arith = annualized_return(r_series, periods_per_year=2, method="arithmetic")

    assert np.isclose(cagr, 0.21, atol=1e-12)
    assert np.isclose(arith, 0.20, atol=1e-12)


def test_returns_invalid_inputs():
    """Test validation errors for empty, non-positive, and infinite prices."""
    with pytest.raises(ValueError, match="empty"):
        simple_returns(pd.Series([], dtype=float))

    with pytest.raises(ValueError, match="strictly positive"):
        simple_returns(pd.Series([10.0, 0.0, 12.0]))

    with pytest.raises(ValueError, match="strictly positive"):
        log_returns(pd.Series([10.0, -5.0, 12.0]))

    with pytest.raises(ValueError, match="non-finite"):
        simple_returns(pd.Series([10.0, np.inf, 12.0]))


# =====================================================================
# 2. RISK METRICS TESTS
# =====================================================================


def test_variance_sample_and_population():
    """
    Analytical variance verification:
    Returns: [0.01, 0.02, 0.03, 0.04, 0.05]
    N = 5, Mean = 0.03
    Deviations: [-0.02, -0.01, 0.0, 0.01, 0.02]
    SS = 0.0004 + 0.0001 + 0 + 0.0001 + 0.0004 = 0.0010
    Sample variance (ddof=1) = 0.0010 / 4 = 0.00025
    Population variance (ddof=0) = 0.0010 / 5 = 0.00020
    """
    r = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])

    s_var = variance(r, ddof=1)
    p_var = variance(r, ddof=0)

    assert np.isclose(s_var, 0.00025, atol=1e-12)
    assert np.isclose(p_var, 0.00020, atol=1e-12)


def test_volatility_and_annualized_volatility():
    """
    Test volatility and square-root-of-time scaling:
    s_var = 0.00025 -> s_vol = sqrt(0.00025) = 0.015811388300841896
    annualized with 252 days: s_vol * sqrt(252)
    annualized with 250 days: s_vol * sqrt(250) (PSX standard)
    """
    r = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    vol = volatility(r, ddof=1)
    expected_vol = np.sqrt(0.00025)
    assert np.isclose(vol, expected_vol, atol=1e-12)

    ann_us = annualized_volatility(r, periods_per_year=252, ddof=1)
    ann_psx = annualized_volatility(r, periods_per_year=250, ddof=1)

    assert np.isclose(ann_us, expected_vol * np.sqrt(252), atol=1e-12)
    assert np.isclose(ann_psx, expected_vol * np.sqrt(250), atol=1e-12)


def test_maximum_drawdown_hand_calculated():
    """
    Test drawdown with known price and return sequence:
    Prices: [100.0, 120.0, 90.0, 80.0, 110.0, 130.0]
    Returns: [NaN, 0.20, -0.25, -0.11111111111111116, 0.375, 0.18181818181818188]
    Wealth: [1.0, 1.20, 0.90, 0.80, 1.10, 1.30]
    Peak = 1.20 on Day 1
    Trough = 0.80 on Day 3
    Max Drawdown = (0.80 - 1.20) / 1.20 = -0.40 / 1.20 = -1/3 = -0.3333333333333333
    Recovery occurs on Day 5 (wealth = 1.30 >= 1.20)
    """
    dates = pd.date_range("2025-01-01", periods=6, freq="D")
    prices = pd.Series([100.0, 120.0, 90.0, 80.0, 110.0, 130.0], index=dates)
    ret = simple_returns(prices)

    dd_res = maximum_drawdown(ret)

    assert np.isclose(dd_res.max_drawdown, -1.0 / 3.0, atol=1e-12)
    assert dd_res.peak_date == dates[1]
    assert dd_res.trough_date == dates[3]
    assert dd_res.recovery_date == dates[5]

    # Verify monotonic case (zero drawdown)
    mono_prices = pd.Series([100.0, 105.0, 110.0], index=dates[:3])
    mono_res = maximum_drawdown(simple_returns(mono_prices))
    assert np.isclose(mono_res.max_drawdown, 0.0, atol=1e-12)


def test_downside_deviation_hand_calculated():
    """
    Analytical downside deviation:
    Returns: [-0.04, -0.02, 0.01, 0.03, 0.05]
    Threshold = 0.0
    Negative shortfall diffs: [-0.04, -0.02, 0.0, 0.0, 0.0]
    Squared: [0.0016, 0.0004, 0, 0, 0] -> sum = 0.0020
    Sortino convention (ddof=0, N=5): semi_var = 0.0020 / 5 = 0.0004 -> semi_dev = 0.02 (2.0%)
    Sample convention (ddof=1, N=5): semi_var = 0.0020 / 4 = 0.0005 -> semi_dev = sqrt(0.0005)
    """
    r = pd.Series([-0.04, -0.02, 0.01, 0.03, 0.05])

    dd_sortino = downside_deviation(r, threshold=0.0, ddof=0)
    dd_sample = downside_deviation(r, threshold=0.0, ddof=1)

    assert np.isclose(dd_sortino, 0.02, atol=1e-12)
    assert np.isclose(dd_sample, np.sqrt(0.0005), atol=1e-12)


def test_annual_to_periodic_rate():
    """
    Test compound interest effective rate conversion:
    r_ann = 0.10 (10.0% effective annual rate)
    m = 12 (monthly): r_p = (1.10)^(1/12) - 1 = 0.007974140428903764
    Verify exact compounding back to annual: (1 + r_p)^12 - 1 == 0.10
    """
    r_monthly = annual_to_periodic_rate(0.10, periods_per_year=12)
    expected_m = (1.10) ** (1.0 / 12.0) - 1.0
    assert np.isclose(r_monthly, expected_m, atol=1e-12)
    assert np.isclose((1.0 + r_monthly) ** 12 - 1.0, 0.10, atol=1e-12)

    # Rejection of invalid rates
    with pytest.raises(ValueError, match="strictly greater than -1.0"):
        annual_to_periodic_rate(-1.0, periods_per_year=252)


# =====================================================================
# 3. COVARIANCE AND CORRELATION TESTS
# =====================================================================


def test_covariance_and_correlation_analytical_two_assets():
    """
    Analytical covariance and correlation between 2 perfectly aligned assets:
    Asset A: [0.01, 0.02, 0.03]  (mean = 0.02, var_sample = 0.0001)
    Asset B: [0.02, 0.04, 0.06]  (exact 2x A; mean = 0.04, var_sample = 0.0004)
    Cov(A, B) = sum((r_A - mean_A)*(r_B - mean_B)) / 2
              = [(-0.01)*(-0.02) + 0 + (0.01)*(0.02)] / 2 = 0.0004 / 2 = 0.0002
    Correlation = Cov(A, B) / (std_A * std_B) = 0.0002 / (0.01 * 0.02) = 1.0
    """
    df = pd.DataFrame(
        {
            "A": [0.01, 0.02, 0.03],
            "B": [0.02, 0.04, 0.06],
        }
    )

    cov = covariance_matrix(df, ddof=1)
    corr = correlation_matrix(df, ddof=1)

    assert list(cov.columns) == ["A", "B"]
    assert list(cov.index) == ["A", "B"]
    assert np.isclose(cov.loc["A", "A"], 0.0001, atol=1e-12)
    assert np.isclose(cov.loc["B", "B"], 0.0004, atol=1e-12)
    assert np.isclose(cov.loc["A", "B"], 0.0002, atol=1e-12)
    assert np.isclose(cov.loc["B", "A"], 0.0002, atol=1e-12)

    # Correlation checks
    assert np.isclose(corr.loc["A", "A"], 1.0, atol=1e-12)
    assert np.isclose(corr.loc["B", "B"], 1.0, atol=1e-12)
    assert np.isclose(corr.loc["A", "B"], 1.0, atol=1e-12)
    assert np.isclose(corr.loc["B", "A"], 1.0, atol=1e-12)


def test_covariance_symmetry_and_diagonal_consistency():
    """Verify covariance symmetry and diagonal matching individual variance on random data."""
    np.random.seed(42)
    data = np.random.normal(0.001, 0.02, size=(50, 4))
    cols = ["Asset1", "Asset2", "Asset3", "Asset4"]
    df = pd.DataFrame(data, columns=cols)

    cov = covariance_matrix(df, ddof=1)

    # Symmetry check
    cov_mat = cov.to_numpy()
    assert np.allclose(cov_mat, cov_mat.T, atol=1e-12)

    # Diagonal consistency
    for c in cols:
        indiv_var = variance(df[c], ddof=1)
        assert np.isclose(cov.loc[c, c], indiv_var, atol=1e-12)


def test_covariance_missing_data_alignment():
    """Verify listwise deletion vs pairwise deletion on missing data."""
    df = pd.DataFrame(
        {
            "A": [0.01, 0.02, np.nan, 0.04, 0.05],
            "B": [0.03, 0.01, 0.02, 0.05, np.nan],
        }
    )

    # drop_any should keep only rows 0, 1, 3 (3 observations)
    cov_clean = covariance_matrix(df, ddof=1, handle_na="drop_any")
    assert cov_clean.shape == (2, 2)
    assert not np.isnan(cov_clean.to_numpy()).any()


# =====================================================================
# 4. PORTFOLIO RETURN AND RISK TESTS
# =====================================================================


def test_portfolio_weights_validation_and_summaries():
    """Test weight validation, long-only detection, short detection, and normalization."""
    weights = {"AAPL": 0.60, "MSFT": 0.40}
    w_series = validate_weights(weights, expected_assets=["AAPL", "MSFT"])
    assert list(w_series.index) == ["AAPL", "MSFT"]
    assert np.isclose(w_series["AAPL"], 0.60)

    summary = summarize_weights(weights)
    assert summary.asset_count == 2
    assert summary.is_fully_invested is True
    assert summary.is_long_only is True
    assert summary.has_short_positions is False

    # Short position
    short_w = {"AAPL": 1.20, "MSFT": -0.20}
    short_summary = summarize_weights(short_w)
    assert short_summary.is_long_only is False
    assert short_summary.has_short_positions is True
    assert np.isclose(short_summary.gross_exposure, 1.40)
    assert np.isclose(short_summary.net_exposure, 1.00)

    # Normalization
    unnorm = {"AAPL": 3.0, "MSFT": 1.0}
    normed = normalize_weights(unnorm)
    assert np.isclose(normed["AAPL"], 0.75)
    assert np.isclose(normed["MSFT"], 0.25)


def test_portfolio_returns_and_expected_return():
    """
    Test portfolio periodic returns and expected returns:
    Returns:
    T1: AAPL = +0.05, MSFT = +0.10
    T2: AAPL = -0.02, MSFT = +0.04
    Weights: w = [0.60, 0.40]
    r_p,1 = 0.60 * 0.05 + 0.40 * 0.10 = 0.03 + 0.04 = 0.07 (+7.0%)
    r_p,2 = 0.60 * (-0.02) + 0.40 * 0.04 = -0.012 + 0.016 = 0.004 (+0.4%)
    Mean r_p = (0.07 + 0.004) / 2 = 0.037 (3.7%)
    """
    df = pd.DataFrame(
        {
            "AAPL": [0.05, -0.02],
            "MSFT": [0.10, 0.04],
        }
    )
    w = {"AAPL": 0.60, "MSFT": 0.40}

    p_ret = portfolio_returns(df, w)
    assert np.isclose(p_ret.iloc[0], 0.07, atol=1e-12)
    assert np.isclose(p_ret.iloc[1], 0.004, atol=1e-12)

    mu_p = portfolio_expected_return(df, w, annualized=False)
    assert np.isclose(mu_p, 0.037, atol=1e-12)

    mu_p_ann = portfolio_expected_return(df, w, annualized=True, periods_per_year=252)
    assert np.isclose(mu_p_ann, 0.037 * 252, atol=1e-12)


def test_portfolio_variance_and_volatility_analytical():
    """
    Exact analytical portfolio variance for 2 assets:
    w = [0.5, 0.5]^T
    Sigma = [[0.04, 0.012],
             [0.012, 0.09]]
    w^T * Sigma * w = 0.25*(0.04) + 2*(0.25)*(0.012) + 0.25*(0.09)
                    = 0.010 + 0.006 + 0.0225 = 0.0385
    sigma_p = sqrt(0.0385) = 0.19621416870348583
    """
    cov = pd.DataFrame(
        [[0.04, 0.012], [0.012, 0.09]],
        index=["A", "B"],
        columns=["A", "B"],
    )
    w = {"A": 0.5, "B": 0.5}

    p_var = portfolio_variance(w, cov)
    p_vol = portfolio_volatility(w, cov)

    assert np.isclose(p_var, 0.0385, atol=1e-12)
    assert np.isclose(p_vol, np.sqrt(0.0385), atol=1e-12)


def test_portfolio_variance_numerical_tolerance_and_rejection():
    """
    Test tiny negative variance is clamped to 0.0 within tolerance,
    while materially negative variance raises ValueError.
    """
    # 1. Tiny negative variance within tolerance (-1e-14 >= -1e-12)
    # Construct a 1x1 matrix with tiny negative value
    cov_tiny_neg = np.array([[-5e-13]])
    var_clamped = portfolio_variance([1.0], cov_tiny_neg, tolerance=1e-12)
    assert var_clamped == 0.0

    # 2. Materially negative variance (< -1e-12)
    cov_mat_neg = np.array([[-0.01]])
    with pytest.raises(ValueError, match="materially negative"):
        portfolio_variance([1.0], cov_mat_neg, tolerance=1e-12)


def test_portfolio_weight_mismatch_raises():
    """Verify error raised when weights do not match covariance assets."""
    cov = pd.DataFrame(
        [[0.04, 0.0], [0.0, 0.09]],
        index=["AAPL", "MSFT"],
        columns=["AAPL", "MSFT"],
    )
    with pytest.raises(ValueError, match="Missing: {'MSFT'}"):
        portfolio_variance({"AAPL": 1.0, "GOOG": 0.0}, cov)


# =====================================================================
# 5. ADDITIONAL EDGE CASE AND VALIDATION TESTS
# =====================================================================


def test_downside_deviation_insufficient_obs_and_invalid_ddof():
    """Verify downside deviation raises on insufficient observations or invalid ddof."""
    with pytest.raises(ValueError, match="ddof must be 0 or 1"):
        downside_deviation(pd.Series([0.01, 0.02]), ddof=2)

    with pytest.raises(ValueError, match="Insufficient observations"):
        downside_deviation(pd.Series([0.01]), ddof=1)


def test_covariance_insufficient_obs_raises():
    """Verify covariance raises ValueError when observations are fewer than ddof + 1."""
    df = pd.DataFrame({"A": [0.01], "B": [0.02]})
    with pytest.raises(ValueError, match="Insufficient aligned observations"):
        covariance_matrix(df, ddof=1)


def test_correlation_zero_variance_raises():
    """Verify correlation matrix raises ValueError when an asset has zero variance (constant returns)."""
    df = pd.DataFrame(
        {
            "A": [0.01, 0.01, 0.01],  # Zero variance
            "B": [0.01, 0.02, 0.03],
        }
    )
    with pytest.raises(ValueError, match="have non-positive variance"):
        correlation_matrix(df, ddof=1)


def test_validate_weights_invalid_values():
    """Verify weight validation rejects None, NaNs, infinities, and zero-sum normalization."""
    with pytest.raises(ValueError, match="cannot be None"):
        validate_weights(None)

    with pytest.raises(ValueError, match="NaN"):
        validate_weights([0.5, np.nan])

    with pytest.raises(ValueError, match="infinite"):
        validate_weights([0.5, np.inf])

    with pytest.raises(ValueError, match="zero sum"):
        normalize_weights([0.5, -0.5])


def test_cumulative_returns_below_minus_100_percent():
    """Verify cumulative returns rejects returns below -100%."""
    with pytest.raises(ValueError, match="less than -100%"):
        cumulative_returns(pd.Series([-1.05]))


def test_annualized_return_invalid_growth():
    """Verify annualized return rejects returns below -100% or total loss."""
    with pytest.raises(ValueError, match="Cumulative wealth is non-positive"):
        annualized_return(pd.Series([-1.0]), periods_per_year=252, method="geometric")


def test_risk_dataframe_multiasset():
    """Verify variance, volatility, and downside deviation on multi-asset DataFrame."""
    df = pd.DataFrame(
        {
            "A": [0.01, 0.02, 0.03, 0.04, 0.05],
            "B": [-0.01, 0.00, 0.01, 0.02, 0.03],
        }
    )
    var_df = variance(df, ddof=1)
    assert isinstance(var_df, pd.Series)
    assert list(var_df.index) == ["A", "B"]
    assert np.isclose(var_df["A"], 0.00025, atol=1e-12)

    vol_df = volatility(df, ddof=1)
    assert isinstance(vol_df, pd.Series)
    assert np.isclose(vol_df["A"], np.sqrt(0.00025), atol=1e-12)

    dd_df = downside_deviation(df, threshold=0.0, ddof=0)
    assert isinstance(dd_df, pd.Series)
    assert list(dd_df.index) == ["A", "B"]
