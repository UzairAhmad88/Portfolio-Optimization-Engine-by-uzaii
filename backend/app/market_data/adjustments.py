"""
Deterministic price adjustment engine and total return calculations.

Workstream 31.3:
- Unambiguous semantics for raw OHLCV, provider-adjusted prices, system-derived adjusted series,
  simple price returns, and dividend-inclusive total returns.
- Standard CRSP and backward-ratio adjustment policies for stock splits, reverse splits, and cash dividends.
- Deterministic, traceable, and versioned calculation policies.
- Preserves raw observations and ensures no double-adjustment of events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)


ADJUSTMENT_POLICY_VERSION = "2026.1"


@dataclass(frozen=True)
class AdjustmentPolicy:
    """
    Traceable configuration of the corporate-action adjustment methodology.
    """
    version: str = ADJUSTMENT_POLICY_VERSION
    split_method: str = "backward_proportional"  # P_adj = P_raw / k for dates before split ex-date
    dividend_method: str = "crsp_reinvestment"   # P_adj = P_raw * (1 - D / P_prior)
    round_precision: int = 6                     # Rounding precision for adjustment factors
    allow_unsupported_complex: bool = False      # Rejects spin-offs/mergers unless explicitly handled
    adjust_dividends: bool = True                # If False, dividend factor remains 1.0 (price return series)



def calculate_split_and_dividend_factors(
    dates: list[date],
    raw_close: pd.Series,
    events: list[CorporateActionEvent],
    policy: AdjustmentPolicy = AdjustmentPolicy(),
) -> pd.DataFrame:
    """
    Calculates deterministic cumulative adjustment factor series for a single asset.

    Parameters:
        dates: Sorted list of trading dates in ascending order.
        raw_close: Series of unadjusted daily close prices indexed by date.
        events: Active corporate action events for this asset.
        policy: Adjustment policy configuration.

    Returns:
        DataFrame indexed by date with columns:
        - 'split_factor': Cumulative split factor applied to historical prices (1.0 at latest date).
        - 'dividend_factor': Cumulative dividend factor applied to historical prices (1.0 at latest date).
        - 'total_factor': Combined adjustment factor = split_factor * dividend_factor.
    """
    if not dates:
        return pd.DataFrame(columns=["split_factor", "dividend_factor", "total_factor"])

    sorted_dates = sorted(dates)
    n = len(sorted_dates)
    date_to_idx = {d: i for i, d in enumerate(sorted_dates)}

    # Daily adjustment multipliers at each date (default 1.0)
    split_multiplier = np.ones(n, dtype=float)
    div_multiplier = np.ones(n, dtype=float)

    # Filter active and supported events
    active_events = [e for e in events if e.status == CorporateActionStatus.ACTIVE]
    # Sort events by effective_date ascending
    active_events.sort(key=lambda e: (e.effective_date, e.event_id))

    for ev in active_events:
        if ev.event_type == CorporateActionType.COMPLEX_UNSUPPORTED:
            if not policy.allow_unsupported_complex:
                raise ValueError(
                    f"Complex unsupported corporate action '{ev.event_id}' on {ev.effective_date} "
                    f"cannot be processed by standard split/dividend adjustment policy."
                )

        # Determine effective index in trading dates
        # If effective_date falls between sessions or on weekend, map to the first trading session >= effective_date
        eff_date = ev.effective_date
        target_idx = None
        for i, d in enumerate(sorted_dates):
            if d >= eff_date:
                target_idx = i
                break

        if target_idx is None or target_idx == 0:
            # Event took place after all dates or on the very first date (no prior history to adjust)
            continue

        prior_date = sorted_dates[target_idx - 1]
        prior_close = raw_close.get(prior_date)

        if ev.event_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
            k = float(ev.value)
            if k <= 0:
                raise ValueError(f"Invalid split ratio {k} on {ev.effective_date}")
            # All dates strictly prior to target_idx must be divided by k (multiplied by 1/k)
            # In daily backward multiplier terms: at target_idx, the shift is 1/k
            split_multiplier[:target_idx] *= (1.0 / k)

        elif ev.event_type == CorporateActionType.CASH_DIVIDEND:
            if not policy.adjust_dividends:
                continue
            div_val = float(ev.value)
            if prior_close is None or prior_close <= 0:
                raise ValueError(
                    f"Cannot calculate dividend adjustment on {ev.effective_date}: prior close price missing or non-positive."
                )
            if div_val >= prior_close:
                raise ValueError(
                    f"Cash dividend {div_val} >= prior close {prior_close} on {ev.effective_date}. "
                    f"Standard CRSP factor requires positive net adjusted base."
                )
            # CRSP factor f_t = 1 - (D_t / P_{t-1})
            f_t = 1.0 - (div_val / prior_close)
            div_multiplier[:target_idx] *= f_t

    total_multiplier = split_multiplier * div_multiplier

    return pd.DataFrame(
        {
            "split_factor": split_multiplier,
            "dividend_factor": div_multiplier,
            "total_factor": total_multiplier,
        },
        index=sorted_dates,
    )


def adjust_ohlcv_series(
    raw_df: pd.DataFrame,
    events: list[CorporateActionEvent],
    policy: AdjustmentPolicy = AdjustmentPolicy(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Adjusts raw daily OHLCV dataframe using corporate action events.

    Parameters:
        raw_df: DataFrame containing at least 'date' and 'close', optionally 'open', 'high', 'low', 'volume'.
        events: List of corporate action events.
        policy: AdjustmentPolicy.

    Returns:
        (adjusted_df, factors_df)
    """
    df = raw_df.copy()
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError("raw_df must contain 'date' and 'close' columns.")

    dates = [
        d if isinstance(d, date) else date.fromisoformat(str(d).strip())
        for d in df["date"]
    ]
    df["_date_obj"] = dates
    df = df.sort_values(by="_date_obj").reset_index(drop=True)
    dates_sorted = df["_date_obj"].tolist()

    raw_close_series = pd.Series(df["close"].values, index=dates_sorted)
    factors_df = calculate_split_and_dividend_factors(
        dates=dates_sorted,
        raw_close=raw_close_series,
        events=events,
        policy=policy,
    )

    tot_factor = factors_df["total_factor"].values
    split_factor = factors_df["split_factor"].values

    # Price fields (open, high, low, close) are multiplied by total_factor
    adjusted_df = pd.DataFrame(index=df.index)
    adjusted_df["date"] = df["date"]
    adjusted_df["adj_close"] = df["close"] * tot_factor

    if "open" in df.columns and df["open"].notna().any():
        adjusted_df["adj_open"] = df["open"] * tot_factor
    if "high" in df.columns and df["high"].notna().any():
        adjusted_df["adj_high"] = df["high"] * tot_factor
    if "low" in df.columns and df["low"].notna().any():
        adjusted_df["adj_low"] = df["low"] * tot_factor

    # Volume is adjusted by INVERSE of split factor (shares outstanding multiplied by k, volume multiplied by k)
    # Dividends do NOT alter share volume
    if "volume" in df.columns and df["volume"].notna().any():
        adjusted_df["adj_volume"] = df["volume"] / split_factor

    adjusted_df["split_factor"] = split_factor
    adjusted_df["dividend_factor"] = factors_df["dividend_factor"].values
    adjusted_df["total_factor"] = tot_factor

    return adjusted_df, factors_df


def calculate_discrete_returns(
    raw_df: pd.DataFrame,
    events: list[CorporateActionEvent],
    return_type: str = "total",  # 'total' (dividend-inclusive) or 'price' (price-only, split-adjusted)
    policy: AdjustmentPolicy = AdjustmentPolicy(),
) -> pd.Series:
    """
    Calculates discrete simple returns with exact financial distinction between:
    - 'total': Dividend-inclusive return: r_t = (P_t + D_t - P_{t-1}/k) / (P_{t-1}/k)
    - 'price': Price return (split-adjusted, dividend-exclusive): r_t = (P_t - P_{t-1}/k) / (P_{t-1}/k)

    Parameters:
        raw_df: DataFrame with 'date' and 'close'.
        events: List of corporate action events.
        return_type: 'total' or 'price'.
        policy: AdjustmentPolicy.

    Returns:
        Series of daily returns indexed by date (first date is NaN).
    """
    if return_type not in ("total", "price"):
        raise ValueError(f"return_type must be 'total' or 'price', received '{return_type}'.")

    df = raw_df.copy()
    dates = [
        d if isinstance(d, date) else date.fromisoformat(str(d).strip())
        for d in df["date"]
    ]
    df["_date_obj"] = dates
    df = df.sort_values(by="_date_obj").reset_index(drop=True)
    dates_sorted = df["_date_obj"].tolist()

    if len(dates_sorted) < 2:
        return pd.Series([np.nan] * len(dates_sorted), index=df["date"])

    # Map events to effective dates
    split_map: dict[date, float] = {}
    div_map: dict[date, float] = {}

    for ev in events:
        if ev.status != CorporateActionStatus.ACTIVE:
            continue
        if ev.event_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
            split_map[ev.effective_date] = float(ev.value)
        elif ev.event_type == CorporateActionType.CASH_DIVIDEND:
            div_map[ev.effective_date] = float(ev.value)

    returns = [np.nan]
    closes = df["close"].values

    for i in range(1, len(dates_sorted)):
        cur_date = dates_sorted[i]
        p_t = closes[i]
        p_prev = closes[i - 1]

        # Check if split occurred on cur_date
        k = split_map.get(cur_date, 1.0)
        # Previous close expressed in current share denomination:
        p_prev_split_adj = p_prev / k

        if return_type == "total":
            d_t = div_map.get(cur_date, 0.0)
            r = ((p_t + d_t) - p_prev_split_adj) / p_prev_split_adj
        else:
            # price return ignores dividend
            r = (p_t - p_prev_split_adj) / p_prev_split_adj

        returns.append(r)

    return pd.Series(returns, index=df["date"])
