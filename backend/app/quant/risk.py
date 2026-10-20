"""
Risk metrics calculation module.

Provides mathematically rigorous, reproducible calculations of variance, volatility,
annualized volatility, drawdown metrics, downside deviation (semi-deviation), and
effective risk-free rate compounding conversions.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DrawdownResult:
    """
    Structured result for maximum drawdown analysis.

    Attributes:
        max_drawdown: Maximum peak-to-trough decline expressed as a signed negative float
                      (e.g., -0.25 represents a -25.0% drop). In an uninterrupted uptrend
                      with no decline, this is 0.0.
        peak_date: Date or index label of the wealth peak preceding the maximum drawdown.
        trough_date: Date or index label of the wealth valley at the maximum drawdown.
        recovery_date: Date or index label where wealth restored to or exceeded peak_date wealth,
                       or None if the asset has not recovered by the end of the series.
        drawdown_series: pandas Series of the periodic drawdown percentage at each point in time,
                         where values are <= 0.0.
    """

    max_drawdown: float
    peak_date: Any
    trough_date: Any
    recovery_date: Any
    drawdown_series: pd.Series


def _clean_return_series(returns: pd.Series) -> pd.Series:
    """
    Cleans and validates a return series:
    - Drops leading/trailing NaNs.
    - Validates finite values (rejects inf/-inf).
    - Checks that discrete returns are >= -1.0 (-100%).
    """
    if not isinstance(returns, pd.Series):
        raise TypeError(f"Expected pandas Series, received {type(returns).__name__}.")

    valid = returns.dropna()
    if valid.empty:
        raise ValueError("Return series contains no valid non-null observations.")

    arr = valid.to_numpy(dtype=float)
    if np.isinf(arr).any():
        raise ValueError("Return series contains non-finite values (infinity).")
    if (arr < -1.0).any():
        raise ValueError("Simple returns cannot be less than -1.0 (-100% total loss).")

    return valid.astype(float)


def variance(
    returns: pd.Series | pd.DataFrame,
    ddof: int = 1,
) -> float | pd.Series:
    """
    Calculates sample or population return variance:
        s^2 = (1 / (N - ddof)) * sum_{i=1}^N (r_i - mean(r))^2

    Parameters:
        returns: pandas Series or DataFrame of periodic returns.
        ddof: Degrees of freedom delta:
              - ddof=1: Sample variance (unbiased estimator for unknown population mean).
              - ddof=0: Population variance (maximum likelihood estimator).

    Returns:
        float (for Series) or pd.Series (for DataFrame).

    Requirements:
        Requires at least (ddof + 1) valid observations.
    """
    if ddof not in (0, 1):
        raise ValueError(f"ddof must be 0 (population) or 1 (sample), got {ddof}.")

    min_obs = ddof + 1

    if isinstance(returns, pd.Series):
        clean = _clean_return_series(returns)
        n = len(clean)
        if n < min_obs:
            raise ValueError(
                f"Insufficient observations for variance with ddof={ddof}: requires at least {min_obs}, got {n}."
            )
        return float(clean.var(ddof=ddof))

    elif isinstance(returns, pd.DataFrame):
        if returns.empty:
            raise ValueError("Return DataFrame is empty.")
        res: dict[str, float] = {}
        for col in returns.columns:
            res[col] = float(variance(returns[col], ddof=ddof))
        return pd.Series(res, name=f"variance_ddof_{ddof}")

    else:
        raise TypeError(
            f"Expected pandas Series or DataFrame, received {type(returns).__name__}."
        )


def volatility(
    returns: pd.Series | pd.DataFrame,
    ddof: int = 1,
) -> float | pd.Series:
    """
    Calculates periodic return volatility (standard deviation):
        s = sqrt(variance)

    Parameters:
        returns: pandas Series or DataFrame of periodic returns.
        ddof: Degrees of freedom delta (1 for sample, 0 for population).

    Returns:
        float (for Series) or pd.Series (for DataFrame).
    """
    var_res = variance(returns, ddof=ddof)
    if isinstance(var_res, pd.Series):
        return np.sqrt(var_res).rename(f"volatility_ddof_{ddof}")
    return float(np.sqrt(var_res))


def annualized_volatility(
    returns: pd.Series | pd.DataFrame,
    periods_per_year: int = 252,
    ddof: int = 1,
) -> float | pd.Series:
    """
    Calculates annualized volatility using square-root-of-time scaling:
        sigma_ann = sigma_periodic * sqrt(periods_per_year)

    Parameters:
        returns: pandas Series or DataFrame of periodic returns.
        periods_per_year: Observation frequency scale factor (e.g. 252 for US equities,
                          250 for PSX equities, 52 for weekly, 12 for monthly).
        ddof: Degrees of freedom delta (1 for sample, 0 for population).

    Returns:
        float (for Series) or pd.Series (for DataFrame).

    Notes:
        Square-root scaling assumes identically and independently distributed (i.i.d.)
        returns across periods. If serial autocorrelation is present, actual multi-period
        volatility may diverge from square-root estimates.
    """
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}.")

    vol = volatility(returns, ddof=ddof)
    scale = np.sqrt(float(periods_per_year))
    if isinstance(vol, pd.Series):
        return (vol * scale).rename(f"annualized_volatility_{periods_per_year}")
    return float(vol * scale)


def drawdown_series(returns: pd.Series) -> pd.Series:
    """
    Computes the percentage drawdown series from a sequence of simple returns:
        W_t = prod_{i=1}^t (1 + r_i)  (Wealth index starting at 1.0)
        M_t = max_{0 <= tau <= t} W_tau (Cumulative peak wealth)
        DD_t = (W_t - M_t) / M_t <= 0.0

    Parameters:
        returns: pandas Series of simple returns. Leading NaNs are preserved.

    Returns:
        pandas Series of drawdown values in [-1.0, 0.0] matching the input index.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError(f"Expected pandas Series, received {type(returns).__name__}.")

    if returns.empty:
        raise ValueError("Return series is empty.")

    clean = returns.dropna()
    if clean.empty:
        raise ValueError("Return series contains no valid observations.")
    if np.isinf(clean.to_numpy(dtype=float)).any():
        raise ValueError("Return series contains non-finite values.")
    if (clean.to_numpy(dtype=float) < -1.0).any():
        raise ValueError("Simple returns cannot be less than -1.0 (-100%).")

    wealth = (1.0 + clean.astype(float)).cumprod()
    peaks = wealth.cummax()
    dd = (wealth - peaks) / peaks

    # Reindex back to original series to preserve leading NaNs or original dates
    return dd.reindex(returns.index)


def maximum_drawdown(returns: pd.Series) -> DrawdownResult:
    """
    Computes maximum peak-to-trough decline (Maximum Drawdown) and identifies
    exact peak, trough, and recovery dates.

    Parameters:
        returns: pandas Series of simple returns.

    Returns:
        DrawdownResult dataclass with max_drawdown, peak_date, trough_date,
        recovery_date, and full drawdown_series.

    Notes:
        - If prices only increase, maximum drawdown is 0.0.
        - max_drawdown is returned as a non-positive float (e.g. -0.22 for a 22% drop).
    """
    dd = drawdown_series(returns)
    clean_dd = dd.dropna()
    if clean_dd.empty:
        raise ValueError("Insufficient data to compute maximum drawdown.")

    # Find the minimum drawdown point (trough)
    trough_val = float(clean_dd.min())
    if trough_val >= 0.0 or np.isclose(trough_val, 0.0):
        # Monotonically increasing wealth: no drawdown occurred
        first_idx = clean_dd.index[0]
        return DrawdownResult(
            max_drawdown=0.0,
            peak_date=first_idx,
            trough_date=first_idx,
            recovery_date=first_idx,
            drawdown_series=dd,
        )

    trough_date = clean_dd.idxmin()

    # Peak date is the date of peak wealth prior to or at the trough date
    clean_returns = returns.dropna().astype(float)
    wealth = (1.0 + clean_returns).cumprod()

    # Look at wealth up to the trough date to find peak
    wealth_to_trough = wealth.loc[:trough_date]
    peak_date = wealth_to_trough.idxmax()
    peak_wealth = float(wealth.loc[peak_date])

    # Check recovery: first date after trough where wealth >= peak_wealth
    wealth_after_trough = wealth.loc[trough_date:]
    recovered_points = wealth_after_trough[wealth_after_trough >= peak_wealth]
    recovery_date = recovered_points.index[0] if not recovered_points.empty else None

    return DrawdownResult(
        max_drawdown=trough_val,
        peak_date=peak_date,
        trough_date=trough_date,
        recovery_date=recovery_date,
        drawdown_series=dd,
    )


def downside_deviation(
    returns: pd.Series | pd.DataFrame,
    threshold: float = 0.0,
    ddof: int = 0,
    annualized: bool = False,
    periods_per_year: int = 252,
) -> float | pd.Series:
    """
    Calculates downside deviation (semi-deviation below a minimum acceptable return):
        d_t = min(r_t - threshold, 0.0)
        DownsideDev = sqrt( (1 / (N - ddof)) * sum_{t=1}^N d_t^2 )

    Parameters:
        returns: pandas Series or DataFrame of periodic returns.
        threshold: Periodic Minimum Acceptable Return (MAR). Default is 0.0.
        ddof: Degrees of freedom (default 0 as standard in Sortino & Price (1994);
              set to 1 for sample bias correction).
        annualized: If True, scales by sqrt(periods_per_year).
        periods_per_year: Periods per year for annualization (default 252).

    Returns:
        float (for Series) or pd.Series (for DataFrame).

    Notes:
        In standard financial literature (Sortino & van der Meer, 1991; Sortino & Price, 1994),
        the denominator uses all observations N (not merely downside observations),
        measuring the probability-weighted downside shortfall relative to the full sample.
    """
    if ddof not in (0, 1):
        raise ValueError(f"ddof must be 0 or 1, got {ddof}.")
    if annualized and periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}.")

    min_obs = ddof + 1

    if isinstance(returns, pd.Series):
        clean = _clean_return_series(returns)
        n = len(clean)
        if n < min_obs:
            raise ValueError(
                f"Insufficient observations for downside deviation: requires >= {min_obs}, got {n}."
            )

        underperformance = clean - threshold
        downside_diff = np.minimum(underperformance.to_numpy(), 0.0)
        squared_downside = np.sum(downside_diff**2)

        denom = float(n - ddof)
        if denom <= 0:
            raise ValueError(
                f"Effective denominator (N - ddof) must be positive, got {denom}."
            )

        semi_var = squared_downside / denom
        semi_dev = float(np.sqrt(semi_var))

        if annualized:
            semi_dev *= np.sqrt(float(periods_per_year))

        return semi_dev

    elif isinstance(returns, pd.DataFrame):
        if returns.empty:
            raise ValueError("Return DataFrame is empty.")
        res: dict[str, float] = {}
        for col in returns.columns:
            res[col] = float(
                downside_deviation(
                    returns[col],
                    threshold=threshold,
                    ddof=ddof,
                    annualized=annualized,
                    periods_per_year=periods_per_year,
                )
            )
        col_name = f"downside_deviation_mar_{threshold}"
        if annualized:
            col_name += f"_ann_{periods_per_year}"
        return pd.Series(res, name=col_name)

    else:
        raise TypeError(
            f"Expected pandas Series or DataFrame, received {type(returns).__name__}."
        )


def annual_to_periodic_rate(
    annual_rate: float,
    periods_per_year: int = 252,
) -> float:
    """
    Converts an annual effective risk-free rate to an equivalent periodic effective rate:
        r_periodic = (1 + r_annual)^(1 / periods_per_year) - 1

    Parameters:
        annual_rate: Annual effective rate as a decimal (e.g. 0.05 for 5.0%). Must be > -1.0.
        periods_per_year: Number of compounding periods per year (e.g. 252 for US daily,
                          250 for PSX daily, 52 for weekly, 12 for monthly). Must be >= 1.

    Returns:
        Periodic effective rate as a float.

    Notes:
        This conversion uses exact compound interest equivalence:
            (1 + r_periodic)^periods_per_year = 1 + r_annual
        It is NOT a simple linear division (annual_rate / periods_per_year).
    """
    if annual_rate <= -1.0:
        raise ValueError(
            f"Annual rate must be strictly greater than -1.0 (-100%), got {annual_rate}."
        )
    if periods_per_year < 1:
        raise ValueError(
            f"periods_per_year must be an integer >= 1, got {periods_per_year}."
        )

    return float((1.0 + annual_rate) ** (1.0 / periods_per_year) - 1.0)


def sharpe_ratio(
    returns: pd.Series | Sequence[float] | float,
    risk_free_rate: float = 0.0,
    volatility_val: float | None = None,
    annualized: bool = True,
    periods_per_year: int = 252,
    ddof: int = 1,
) -> float:
    """
    Calculates the Sharpe ratio:
        S = (R_p - R_f) / sigma_p

    Parameters:
        returns: Historical return series, sequence of returns, or a scalar portfolio return.
        risk_free_rate: Risk-free rate (annual effective rate if annualized=True, else periodic).
        volatility_val: Volatility of portfolio. Required if returns is a scalar float.
        annualized: Whether returns and volatility are expressed on an annualized basis.
        periods_per_year: Compounding scale factor for annualization (e.g. 252 for US, 250 for PSX).
        ddof: Degrees of freedom for sample standard deviation (default 1).

    Returns:
        float Sharpe ratio.

    Raises:
        ValueError: If observations < 2, or if volatility is zero or numerically negligible.
    """
    if isinstance(returns, (int, float)):
        if volatility_val is None:
            raise ValueError(
                "volatility_val must be provided when returns is passed as a scalar expected return."
            )
        vol = float(volatility_val)
        if vol < 0.0:
            raise ValueError(f"Volatility cannot be negative, got {vol}.")
        if vol <= 1e-12:
            raise ValueError(
                f"Volatility is zero or numerically negligible ({vol:.3e}); Sharpe ratio cannot be computed."
            )
        return float((float(returns) - risk_free_rate) / vol)

    s = returns if isinstance(returns, pd.Series) else pd.Series(list(returns), dtype=float)
    clean = _clean_return_series(s)
    if len(clean) < 2:
        raise ValueError(
            f"Insufficient observations for Sharpe ratio calculation: requires >= 2, got {len(clean)}."
        )

    if annualized:
        exp_ret = float(clean.mean()) * float(periods_per_year)
        vol = float(annualized_volatility(clean, periods_per_year=periods_per_year, ddof=ddof))
        rf = float(risk_free_rate)
    else:
        exp_ret = float(clean.mean())
        vol = float(volatility(clean, ddof=ddof))
        rf = float(risk_free_rate)

    if vol <= 1e-12:
        raise ValueError(
            f"Volatility is zero or numerically negligible ({vol:.3e}); Sharpe ratio cannot be computed."
        )

    return float((exp_ret - rf) / vol)


def sortino_ratio(
    returns: pd.Series | Sequence[float] | float,
    required_return: float = 0.0,
    downside_dev_val: float | None = None,
    annualized: bool = True,
    periods_per_year: int = 252,
    ddof: int = 0,
) -> float:
    """
    Calculates the Sortino ratio:
        Sortino = (R_p - MAR) / sigma_downside

    Where MAR is the Minimum Acceptable Return (threshold).

    Parameters:
        returns: Historical return series, sequence of returns, or a scalar portfolio return.
        required_return: Minimum Acceptable Return (MAR). Expressed on same basis as returns.
        downside_dev_val: Downside deviation. Required if returns is a scalar float.
        annualized: Whether returns and downside deviation are expressed on an annualized basis.
        periods_per_year: Scale factor for annualization (e.g. 252 for US, 250 for PSX).
        ddof: Degrees of freedom (default 0 per Sortino & Price 1994 literature standard).

    Returns:
        float Sortino ratio.

    Raises:
        ValueError: If observations < 2, or if downside deviation is zero or negligible.
    """
    if isinstance(returns, (int, float)):
        if downside_dev_val is None:
            raise ValueError(
                "downside_dev_val must be provided when returns is passed as a scalar expected return."
            )
        d_dev = float(downside_dev_val)
        if d_dev < 0.0:
            raise ValueError(f"Downside deviation cannot be negative, got {d_dev}.")
        if d_dev <= 1e-12:
            raise ValueError(
                f"Downside deviation is zero or numerically negligible ({d_dev:.3e}); Sortino ratio cannot be computed."
            )
        return float((float(returns) - required_return) / d_dev)

    s = returns if isinstance(returns, pd.Series) else pd.Series(list(returns), dtype=float)
    clean = _clean_return_series(s)
    if len(clean) < 2:
        raise ValueError(
            f"Insufficient observations for Sortino ratio calculation: requires >= 2, got {len(clean)}."
        )

    if annualized:
        exp_ret = float(clean.mean()) * float(periods_per_year)
        mar_periodic = (
            annual_to_periodic_rate(required_return, periods_per_year)
            if required_return != 0.0
            else 0.0
        )
        d_dev = float(
            downside_deviation(
                clean,
                threshold=mar_periodic,
                ddof=ddof,
                annualized=True,
                periods_per_year=periods_per_year,
            )
        )
        mar = float(required_return)
    else:
        exp_ret = float(clean.mean())
        d_dev = float(
            downside_deviation(
                clean,
                threshold=required_return,
                ddof=ddof,
                annualized=False,
            )
        )
        mar = float(required_return)

    if d_dev <= 1e-12:
        raise ValueError(
            f"Downside deviation is zero or numerically negligible ({d_dev:.3e}); Sortino ratio cannot be computed."
        )

    return float((exp_ret - mar) / d_dev)


@dataclass(frozen=True)
class PortfolioRiskSummary:
    """
    Comprehensive, verified portfolio risk and return analytics summary.
    """

    observation_count: int
    start_date: Any
    end_date: Any
    periods_per_year: int
    is_annualized: bool
    mean_return_periodic: float
    expected_return_annualized: float
    cumulative_return: float
    variance_periodic: float
    variance_annualized: float
    volatility_periodic: float
    volatility_annualized: float
    max_drawdown: float
    drawdown_peak_date: Any
    drawdown_trough_date: Any
    drawdown_recovery_date: Any
    downside_deviation_periodic: float
    downside_deviation_annualized: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    risk_free_rate_annual: float
    mar_annual: float


def portfolio_risk_summary(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    required_return: float = 0.0,
    periods_per_year: int = 252,
    ddof: int = 1,
) -> PortfolioRiskSummary:
    """
    Computes a comprehensive risk and return analytics summary for a historical portfolio return series.

    Parameters:
        returns: pandas Series of periodic portfolio returns.
        risk_free_rate: Annual effective risk-free rate.
        required_return: Annual effective Minimum Acceptable Return (MAR).
        periods_per_year: Compounding periods per year (e.g. 252 for US, 250 for PSX).
        ddof: Degrees of freedom for sample variance/volatility.

    Returns:
        PortfolioRiskSummary dataclass.
    """
    clean = _clean_return_series(returns)
    n = len(clean)
    if n < 2:
        raise ValueError(
            f"Insufficient observations for portfolio risk summary: requires >= 2, got {n}."
        )

    start_idx = clean.index[0] if hasattr(clean, "index") and len(clean.index) > 0 else None
    end_idx = clean.index[-1] if hasattr(clean, "index") and len(clean.index) > 0 else None

    mean_periodic = float(clean.mean())
    exp_ret_ann = mean_periodic * float(periods_per_year)

    # Cumulative wealth return: prod(1 + r) - 1
    cum_ret = float(np.prod(1.0 + clean.to_numpy(dtype=float)) - 1.0)

    var_periodic = float(variance(clean, ddof=ddof))
    var_ann = var_periodic * float(periods_per_year)

    vol_periodic = float(volatility(clean, ddof=ddof))
    vol_ann = float(annualized_volatility(clean, periods_per_year=periods_per_year, ddof=ddof))

    dd_res = maximum_drawdown(clean)

    mar_periodic = (
        annual_to_periodic_rate(required_return, periods_per_year)
        if required_return != 0.0
        else 0.0
    )
    downside_periodic = float(downside_deviation(clean, threshold=0.0, ddof=0, annualized=False))
    downside_ann = float(
        downside_deviation(
            clean,
            threshold=mar_periodic,
            ddof=0,
            annualized=True,
            periods_per_year=periods_per_year,
        )
    )

    try:
        sharpe_val: float | None = sharpe_ratio(
            clean,
            risk_free_rate=risk_free_rate,
            annualized=True,
            periods_per_year=periods_per_year,
            ddof=ddof,
        )
    except ValueError:
        sharpe_val = None

    try:
        sortino_val: float | None = sortino_ratio(
            clean,
            required_return=required_return,
            annualized=True,
            periods_per_year=periods_per_year,
            ddof=0,
        )
    except ValueError:
        sortino_val = None

    return PortfolioRiskSummary(
        observation_count=n,
        start_date=start_idx,
        end_date=end_idx,
        periods_per_year=periods_per_year,
        is_annualized=True,
        mean_return_periodic=mean_periodic,
        expected_return_annualized=exp_ret_ann,
        cumulative_return=cum_ret,
        variance_periodic=var_periodic,
        variance_annualized=var_ann,
        volatility_periodic=vol_periodic,
        volatility_annualized=vol_ann,
        max_drawdown=dd_res.max_drawdown,
        drawdown_peak_date=dd_res.peak_date,
        drawdown_trough_date=dd_res.trough_date,
        drawdown_recovery_date=dd_res.recovery_date,
        downside_deviation_periodic=downside_periodic,
        downside_deviation_annualized=downside_ann,
        sharpe_ratio=sharpe_val,
        sortino_ratio=sortino_val,
        risk_free_rate_annual=float(risk_free_rate),
        mar_annual=float(required_return),
    )

