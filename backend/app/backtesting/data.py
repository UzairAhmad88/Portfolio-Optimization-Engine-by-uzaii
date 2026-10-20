"""
Historical data extraction and price panel preparation for backtesting simulations.
Enforces dataset access, currency homogeneity, adjusted-close prioritization,
and trading date synchronization.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.db.models import UserModel
from app.market_data.service import DatasetNotFoundError, get_dataset_rows
from app.portfolio.models import AssetMetadata
from app.portfolio.service import get_dataset_assets


def prepare_backtest_data(
    dataset_id: str,
    requested_assets: list[str],
    start_date: date | None,
    end_date: date | None,
    user: UserModel,
    session: Session,
    min_required_observations: int = 2,
) -> tuple[pd.DataFrame, list[str], str, int, list[str]]:
    """
    Retrieves, validates, and synchronizes historical price panels for backtesting.

    Returns:
        tuple containing:
        - clean_price_df: pd.DataFrame with date index (ISO str) and asset_id columns.
        - resolved_asset_ids: list of canonical asset identifiers.
        - currency: trading currency code (e.g. USD, PKR).
        - periods_per_year: annualization factor (252 for US, 250 for PSX).
        - warnings: list of actionable audit notices.

    Raises:
        ValueError on unresolvable assets, cross-currency conflicts, or insufficient observations.
        HTTPException (403/404) on unauthorized dataset access.
    """
    # 1. Enforce dataset ownership / authorization
    check_dataset_access(session, dataset_id, user)

    # 2. Retrieve asset metadata
    available_assets = get_dataset_assets(dataset_id)
    raw_rows = get_dataset_rows(dataset_id)

    asset_by_id: dict[str, AssetMetadata] = {a.asset_id: a for a in available_assets}
    assets_by_ticker: dict[str, list[AssetMetadata]] = defaultdict(list)
    for a in available_assets:
        assets_by_ticker[a.ticker].append(a)

    resolved_asset_ids: list[str] = []
    resolved_meta: list[AssetMetadata] = []

    for raw_sel in requested_assets:
        sel = str(raw_sel).strip().upper()
        if sel in asset_by_id:
            meta = asset_by_id[sel]
        elif sel in assets_by_ticker and len(assets_by_ticker[sel]) == 1:
            meta = assets_by_ticker[sel][0]
        else:
            raise ValueError(
                f"Asset '{raw_sel}' could not be uniquely resolved in dataset '{dataset_id}'."
            )
        resolved_asset_ids.append(meta.asset_id)
        resolved_meta.append(meta)

    # 3. Currency and market validation
    currencies = {m.currency for m in resolved_meta}
    if len(currencies) > 1:
        raise ValueError(
            f"Multi-currency portfolios are not supported without explicit FX conversion: found {sorted(currencies)}."
        )
    currency = list(currencies)[0] if currencies else "USD"

    markets = {m.market for m in resolved_meta}
    periods_per_year = 250 if "PSX" in markets else 252

    warnings: list[str] = []
    used_unadjusted: set[str] = set()

    # 4. Construct price matrix
    prices_by_date_asset: dict[tuple[str, str], float] = {}
    for r in raw_rows:
        row_asset_id = f"{r['ticker']}:{r['market']}"
        if row_asset_id not in resolved_asset_ids:
            continue

        d_str = r.get("date")
        if not d_str:
            continue

        row_d = date.fromisoformat(d_str)
        if start_date and row_d < start_date:
            continue
        if end_date and row_d > end_date:
            continue

        p_val = r.get("adjusted_close")
        if p_val is not None and isinstance(p_val, (int, float)) and float(p_val) > 0.0:
            price = float(p_val)
        else:
            price = float(r["close"])
            used_unadjusted.add(row_asset_id)

        prices_by_date_asset[(d_str, row_asset_id)] = price

    if used_unadjusted:
        warnings.append(
            f"Unadjusted close used for assets: {sorted(used_unadjusted)}; "
            "returns may not account for corporate splits or dividend payouts."
        )

    all_dates = sorted({d for d, _ in prices_by_date_asset.keys()})
    price_data: dict[str, list[float | None]] = {aid: [] for aid in resolved_asset_ids}

    for d in all_dates:
        for aid in resolved_asset_ids:
            price_data[aid].append(prices_by_date_asset.get((d, aid)))

    raw_price_df = pd.DataFrame(price_data, index=all_dates)
    clean_price_df = raw_price_df.dropna(how="any").astype(float)
    common_obs = len(clean_price_df)

    if common_obs < min_required_observations:
        raise ValueError(
            f"Selected assets share only {common_obs} common trading observations. "
            f"At least {min_required_observations} synchronized observations are required."
        )

    return clean_price_df, resolved_asset_ids, currency, periods_per_year, warnings
