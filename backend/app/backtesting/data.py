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
    use_point_in_time: bool = False,
    as_of_date: date | None = None,
    strict_pit: bool = False,
    adjustment_type: str = "total",
) -> tuple[pd.DataFrame, list[str], str, int, list[str]]:
    """
    Retrieves, validates, and synchronizes historical price panels for backtesting.

    Supports:
    - Legacy mode (use_point_in_time=False): Preserves existing behavior using provider
      adjusted_close where present, with unadjusted close fallback and warning.
    - Strict Point-in-Time mode (use_point_in_time=True): Dynamically resolves corporate
      actions from the persistent ledger, strictly filtering by announcement date cutoff,
      preventing look-ahead leakage, resolving revisions, and deriving traceable adjusted series.

    Returns:
        tuple containing:
        - clean_price_df: pd.DataFrame with date index (ISO str) and asset_id columns.
          In PIT mode, clean_price_df.attrs["pit_metadata"] contains full reproducibility metadata.
        - resolved_asset_ids: list of canonical asset identifiers.
        - currency: trading currency code (e.g. USD, PKR).
        - periods_per_year: annualization factor (252 for US, 250 for PSX).
        - warnings: list of actionable audit notices (including PIT status when enabled).

    Raises:
        ValueError on unresolvable assets, cross-currency conflicts, insufficient observations,
        or fail-closed strict point-in-time verification failure.
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

    # 4. Construct price matrix (Legacy vs Point-in-Time Mode)
    if not use_point_in_time:
        # Legacy path: preserve existing behavior identically
        used_unadjusted: set[str] = set()
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

    # =========================================================================
    # Strict Point-in-Time Dynamic Adjustment Path
    # =========================================================================
    from sqlalchemy import select
    from app.db.models import CorporateActionModel
    from app.market_data.corporate_actions import (
        CorporateActionEvent,
        CorporateActionStatus,
        CorporateActionType,
    )
    from app.market_data.point_in_time import (
        PointInTimeCutoff,
        PointInTimeStatus,
        filter_point_in_time_actions,
    )
    from app.market_data.adjustments import (
        AdjustmentPolicy,
        adjust_ohlcv_series,
    )

    # Determine cutoff date for point-in-time filtering
    all_observed_dates = [
        date.fromisoformat(r["date"]) for r in raw_rows if r.get("date")
    ]
    max_dataset_date = max(all_observed_dates) if all_observed_dates else date.today()
    cutoff_d = as_of_date or end_date or max_dataset_date

    # Query persisted corporate actions for resolved assets
    stmt = (
        select(CorporateActionModel)
        .where(
            CorporateActionModel.asset_id.in_(resolved_asset_ids),
            (CorporateActionModel.dataset_id == dataset_id)
            | (CorporateActionModel.dataset_id.is_(None)),
        )
        .order_by(
            CorporateActionModel.effective_date.asc(),
            CorporateActionModel.id.asc(),
        )
    )
    ca_models = list(session.scalars(stmt).all())
    domain_events = [
        CorporateActionEvent(
            event_id=m.id,
            asset_id=m.asset_id,
            ticker=m.ticker,
            market=m.market,
            event_type=CorporateActionType(m.event_type),
            effective_date=m.effective_date,
            value=m.value,
            currency=m.currency,
            source=m.source,
            announcement_date=m.announcement_date,
            ex_date=m.ex_date,
            record_date=m.record_date,
            payment_date=m.payment_date,
            revision_id=m.revision_id,
            status=CorporateActionStatus(m.status),
            is_point_in_time_verified=m.is_point_in_time_verified,
            created_at=m.created_at,
        )
        for m in ca_models
    ]

    cutoff = PointInTimeCutoff(as_of_date=cutoff_d, strict=strict_pit)
    eligible_events, pit_audit = filter_point_in_time_actions(domain_events, cutoff)

    if strict_pit and pit_audit.status == PointInTimeStatus.FAILED_CLOSED:
        raise ValueError(
            f"Strict Point-in-Time verification failed: {'; '.join(pit_audit.reasons)}"
        )

    # Index eligible events by asset_id
    eligible_by_asset: dict[str, list[CorporateActionEvent]] = defaultdict(list)
    for ev in eligible_events:
        eligible_by_asset[ev.asset_id].append(ev)

    # Group raw observations by asset and detect unverified provider adjusted_close divergence
    asset_raw_bars: dict[str, list[dict[str, Any]]] = {aid: [] for aid in resolved_asset_ids}
    divergent_assets: set[str] = set()

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

        raw_c = float(r["close"])
        prov_adj = r.get("adjusted_close")
        if prov_adj is not None and isinstance(prov_adj, (int, float)) and float(prov_adj) > 0.0:
            if abs(float(prov_adj) - raw_c) > 1e-4:
                divergent_assets.add(row_asset_id)

        asset_raw_bars[row_asset_id].append({
            "date": row_d,
            "date_str": d_str,
            "close": raw_c,
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "volume": r.get("volume"),
        })

    # Validate provider divergence vs corporate action ledger
    for aid in divergent_assets:
        if not eligible_by_asset.get(aid):
            if strict_pit:
                raise ValueError(
                    f"Asset '{aid}' contains provider adjusted_close that diverges from raw close, "
                    "but lacks verified corporate action records in repository. "
                    "Strict point-in-time provenance cannot be established."
                )
            else:
                warnings.append(
                    f"Asset '{aid}' contains provider adjusted_close diverging from raw close; "
                    "raw prices used with unverified corporate action status."
                )

    # Apply corporate action adjustments per asset on raw prices (never double-adjusting)
    adjusted_prices_by_date_asset: dict[tuple[str, str], float] = {}
    policy = AdjustmentPolicy(adjust_dividends=(adjustment_type == "total"))

    for aid in resolved_asset_ids:
        bars = sorted(asset_raw_bars[aid], key=lambda x: x["date"])
        if not bars:
            continue

        ev_list = eligible_by_asset.get(aid, [])
        if ev_list:
            raw_df = pd.DataFrame({
                "date": [b["date"] for b in bars],
                "close": [b["close"] for b in bars],
            })
            adj_df, _ = adjust_ohlcv_series(raw_df, ev_list, policy=policy)
            adj_closes = adj_df["adj_close"].values
            for b, ac in zip(bars, adj_closes):
                adjusted_prices_by_date_asset[(b["date_str"], aid)] = float(ac)
        else:
            for b in bars:
                adjusted_prices_by_date_asset[(b["date_str"], aid)] = b["close"]

    all_dates = sorted({d for d, _ in adjusted_prices_by_date_asset.keys()})
    price_data = {aid: [] for aid in resolved_asset_ids}

    for d in all_dates:
        for aid in resolved_asset_ids:
            price_data[aid].append(adjusted_prices_by_date_asset.get((d, aid)))

    raw_price_df = pd.DataFrame(price_data, index=all_dates)
    clean_price_df = raw_price_df.dropna(how="any").astype(float)
    common_obs = len(clean_price_df)

    if common_obs < min_required_observations:
        raise ValueError(
            f"Selected assets share only {common_obs} common trading observations. "
            f"At least {min_required_observations} synchronized observations are required."
        )

    # Attach reproducibility metadata to DataFrame attributes
    clean_price_df.attrs["pit_metadata"] = {
        "dataset_id": dataset_id,
        "as_of_date": cutoff_d.isoformat(),
        "strict_pit": strict_pit,
        "adjustment_type": adjustment_type,
        "status": pit_audit.status.value,
        "is_certified_pit_safe": pit_audit.is_certified_pit_safe,
        "policy_version": pit_audit.details.get("policy_version", "2026.1"),
        "calendar_version": "PSX-KHI-2026.1" if "PSX" in markets else "US-NYSE-2026.1",
        "eligible_actions_count": len(eligible_events),
        "excluded_future_actions_count": pit_audit.excluded_future_actions_count,
        "unverified_actions_count": pit_audit.unverified_actions_count,
        "applied_actions": [
            {
                "event_id": e.event_id,
                "asset_id": e.asset_id,
                "event_type": e.event_type.value,
                "effective_date": e.effective_date.isoformat(),
                "announcement_date": e.announcement_date.isoformat() if e.announcement_date else None,
                "value": e.value,
            }
            for e in eligible_events
        ],
    }

    warnings.append(
        f"PIT_STATUS: {pit_audit.status.value.upper()} (as_of_date: {cutoff_d.isoformat()}, strict: {strict_pit}, actions_applied: {len(eligible_events)})"
    )
    return clean_price_df, resolved_asset_ids, currency, periods_per_year, warnings
