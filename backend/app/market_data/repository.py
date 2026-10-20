"""
Persistent database repository for datasets, asset metadata, and price bars.
Provides atomicity, indexed query execution, and deterministic deduplication.
"""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssetModel, CorporateActionModel, DatasetModel, PriceBarModel


def find_dataset_by_sha256(
    session: Session, content_sha256: str, user_id: str | None = None
) -> DatasetModel | None:
    """
    Finds a previously registered dataset with identical SHA-256 cryptographic digest.
    If user_id is provided, checks if the user owns the dataset or if it is shared,
    preventing private datasets from being exposed to other tenants via deduplication.
    """
    stmt = select(DatasetModel).where(
        DatasetModel.content_sha256 == content_sha256,
        DatasetModel.status == "completed",
    )
    if user_id:
        stmt = stmt.where(
            (DatasetModel.user_id == user_id) | (DatasetModel.is_shared == True)
        )
    stmt = stmt.order_by(DatasetModel.created_at.desc())
    return session.scalars(stmt).first()


def get_dataset_by_id(session: Session, dataset_id: str) -> DatasetModel | None:
    """
    Retrieves dataset metadata by unique UUID identifier.
    """
    return session.get(DatasetModel, dataset_id)


def list_datasets(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    user_id: str | None = None,
    is_admin: bool = False,
) -> list[DatasetModel]:
    """
    Returns registered datasets ordered by registration timestamp descending.
    Filters by owner if user_id is supplied and user is not admin.
    """
    stmt = select(DatasetModel).where(DatasetModel.status == "completed")
    if user_id and not is_admin:
        stmt = stmt.where(
            (DatasetModel.user_id == user_id)
            | (DatasetModel.is_shared == True)
            | (DatasetModel.user_id == None)
        )
    stmt = stmt.order_by(DatasetModel.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


def get_dataset_assets(session: Session, dataset_id: str) -> list[AssetModel]:
    """
    Retrieves all asset metadata records for a dataset.
    """
    stmt = (
        select(AssetModel)
        .where(AssetModel.dataset_id == dataset_id)
        .order_by(AssetModel.ticker.asc())
    )
    return list(session.scalars(stmt).all())


def query_price_bars(
    session: Session,
    dataset_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    tickers: list[str] | None = None,
    market: str | None = None,
) -> list[PriceBarModel]:
    """
    Queries historical price bars with optional date filters, optional ticker filter, and market.
    Guarantees deterministic ordering by date asc, ticker asc.
    """
    stmt = select(PriceBarModel).where(PriceBarModel.dataset_id == dataset_id)
    if start_date is not None:
        stmt = stmt.where(PriceBarModel.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(PriceBarModel.date <= end_date)
    if tickers:
        upper_tickers = [t.upper() for t in tickers]
        stmt = stmt.where(PriceBarModel.ticker.in_(upper_tickers))
    if market:
        stmt = stmt.where(PriceBarModel.market == market.upper())

    stmt = stmt.order_by(PriceBarModel.date.asc(), PriceBarModel.ticker.asc())
    return list(session.scalars(stmt).all())


def create_dataset_with_records(
    session: Session,
    dataset_id: str,
    filename: str,
    content_sha256: str,
    rows_examined: int,
    valid_rows: int,
    rejected_rows: int,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    valid_records: list[dict[str, Any]],
    user_id: str | None = None,
    is_shared: bool = False,
) -> DatasetModel:
    """
    Atomically persists a dataset record, its computed asset metadata,
    and its full set of normalized price bars within the current database transaction.
    Associates the dataset with an owner user_id if provided.
    """
    dataset = DatasetModel(
        id=dataset_id,
        user_id=user_id,
        is_shared=is_shared,
        filename=filename,
        source_type="csv_upload",
        content_sha256=content_sha256,
        rows_examined=rows_examined,
        valid_rows=valid_rows,
        rejected_rows=rejected_rows,
        status="completed",
        errors_json=json.dumps(errors),
        warnings_json=json.dumps(warnings),
    )
    session.add(dataset)
    session.flush()

    if not valid_records:
        return dataset

    # 1. Compute asset metadata summaries from valid records
    asset_map: dict[str, dict[str, Any]] = {}
    price_bar_objects: list[PriceBarModel] = []

    for r in valid_records:
        ticker = str(r["ticker"]).strip().upper()
        market = str(r["market"]).strip().upper()
        currency = str(r["currency"]).strip().upper()
        composite_id = f"{ticker}:{market}"

        raw_date = r["date"]
        if isinstance(raw_date, str):
            obs_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        elif isinstance(raw_date, datetime):
            obs_date = raw_date.date()
        else:
            obs_date = raw_date

        if composite_id not in asset_map:
            asset_map[composite_id] = {
                "asset_id": composite_id,
                "ticker": ticker,
                "market": market,
                "currency": currency,
                "start_date": obs_date,
                "end_date": obs_date,
                "observation_count": 0,
            }

        cur = asset_map[composite_id]
        if obs_date < cur["start_date"]:
            cur["start_date"] = obs_date
        if obs_date > cur["end_date"]:
            cur["end_date"] = obs_date
        cur["observation_count"] += 1

        price_bar_objects.append(
            PriceBarModel(
                dataset_id=dataset_id,
                asset_id=composite_id,
                ticker=ticker,
                market=market,
                currency=currency,
                date=obs_date,
                open=float(r["open"]) if r.get("open") is not None else None,
                high=float(r["high"]) if r.get("high") is not None else None,
                low=float(r["low"]) if r.get("low") is not None else None,
                close=float(r["close"]),
                adj_close=float(r["adj_close"]) if r.get("adj_close") is not None else None,
                volume=float(r["volume"]) if r.get("volume") is not None else None,
            )
        )

    # Add AssetModel objects
    for meta in asset_map.values():
        asset_obj = AssetModel(
            dataset_id=dataset_id,
            asset_id=meta["asset_id"],
            ticker=meta["ticker"],
            market=meta["market"],
            currency=meta["currency"],
            start_date=meta["start_date"],
            end_date=meta["end_date"],
            observation_count=meta["observation_count"],
        )
        session.add(asset_obj)

    # Batch add PriceBarModel objects
    session.add_all(price_bar_objects)
    session.flush()

    return dataset


def get_dataset_price_matrix_dataframe(
    session: Session,
    dataset_id: str,
    assets: list[str],
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[pd.DataFrame, str]:
    """
    Extracts a clean, synchronous price DataFrame (date index, asset columns)
    and verifies single-currency homogeneity.
    """
    stmt = select(PriceBarModel).where(PriceBarModel.dataset_id == dataset_id)
    if start_date:
        stmt = stmt.where(PriceBarModel.date >= start_date)
    if end_date:
        stmt = stmt.where(PriceBarModel.date <= end_date)

    # Match tickers or composite identifiers
    upper_assets = [a.upper() for a in assets]
    # Check if user provided composite tickers (e.g. AAPL:US) or raw tickers (AAPL)
    is_composite = any(":" in a for a in upper_assets)
    if is_composite:
        stmt = stmt.where(PriceBarModel.asset_id.in_(upper_assets))
    else:
        stmt = stmt.where(PriceBarModel.ticker.in_(upper_assets))

    stmt = stmt.order_by(PriceBarModel.date.asc(), PriceBarModel.ticker.asc())
    bars = list(session.scalars(stmt).all())

    if not bars:
        raise ValueError("No historical price observations found for requested portfolio.")

    currencies = {b.currency for b in bars}
    if len(currencies) > 1:
        raise ValueError(
            f"Multi-currency portfolios are not supported. Currencies present: {sorted(currencies)}"
        )
    currency = next(iter(currencies))

    records = [
        {
            "date": b.date,
            "asset_key": b.asset_id if is_composite else b.ticker,
            "price": b.adj_close if b.adj_close is not None else b.close,
        }
        for b in bars
    ]

    df = pd.DataFrame(records)
    pivot_df = df.pivot(index="date", columns="asset_key", values="price").sort_index()

    # Reindex columns to match the exact vector order of assets
    # Case-insensitive column matching
    col_map = {str(c).upper(): c for c in pivot_df.columns}
    ordered_cols = [col_map[a.upper()] for a in assets if a.upper() in col_map]
    
    if len(ordered_cols) != len(assets):
        missing = [a for a in assets if a.upper() not in col_map]
        raise ValueError(f"Missing historical price data for assets: {missing}")

    pivot_df = pivot_df[ordered_cols]
    pivot_df.columns = assets

    # Drop non-overlapping dates to yield strictly synchronized returns
    clean_df = pivot_df.dropna()
    return clean_df, currency


def save_corporate_actions(
    session: Session,
    actions: list[dict[str, Any]],
    dataset_id: str | None = None,
) -> list[CorporateActionModel]:
    """
    Persists corporate actions idempotently. Deduplicates matching actions.
    """
    models = []
    for a in actions:
        ev_id = a.get("event_id") or a.get("id")
        existing = session.get(CorporateActionModel, ev_id) if ev_id else None
        if existing:
            continue
        m = CorporateActionModel(
            id=ev_id,
            dataset_id=dataset_id,
            asset_id=a["asset_id"],
            ticker=a["ticker"],
            market=a["market"],
            event_type=a["event_type"],
            effective_date=a["effective_date"] if isinstance(a["effective_date"], date) else date.fromisoformat(str(a["effective_date"])),
            announcement_date=a.get("announcement_date") if isinstance(a.get("announcement_date"), (date, type(None))) else date.fromisoformat(str(a["announcement_date"])),
            ex_date=a.get("ex_date") if isinstance(a.get("ex_date"), (date, type(None))) else date.fromisoformat(str(a["ex_date"])),
            record_date=a.get("record_date") if isinstance(a.get("record_date"), (date, type(None))) else date.fromisoformat(str(a["record_date"])),
            payment_date=a.get("payment_date") if isinstance(a.get("payment_date"), (date, type(None))) else date.fromisoformat(str(a["payment_date"])),
            value=float(a["value"]),
            currency=a["currency"],
            source=a.get("source", "system"),
            revision_id=a.get("revision_id"),
            status=a.get("status", "active"),
            is_point_in_time_verified=bool(a.get("is_point_in_time_verified", False)),
            provenance_json=json.dumps(a.get("provenance_metadata", {})) if a.get("provenance_metadata") else None,
        )
        session.add(m)
        models.append(m)
    session.flush()
    return models


def query_corporate_actions(
    session: Session,
    asset_id: str | None = None,
    dataset_id: str | None = None,
    as_of_date: date | None = None,
    strict_pit: bool = False,
) -> list[CorporateActionModel]:
    """
    Queries corporate action records with deterministic sorting and optional PIT cutoff.
    """
    stmt = select(CorporateActionModel)
    if dataset_id:
        stmt = stmt.where(CorporateActionModel.dataset_id == dataset_id)
    if asset_id:
        stmt = stmt.where(CorporateActionModel.asset_id == asset_id)
    if as_of_date:
        if strict_pit:
            # Under strict PIT, announcement_date must exist and be <= as_of_date
            stmt = stmt.where(
                CorporateActionModel.announcement_date != None,
                CorporateActionModel.announcement_date <= as_of_date,
            )
        else:
            stmt = stmt.where(CorporateActionModel.effective_date <= as_of_date)

    stmt = stmt.order_by(CorporateActionModel.effective_date.asc(), CorporateActionModel.id.asc())
    return list(session.scalars(stmt).all())


def clear_all_datasets(session: Session) -> None:
    """
    Clears all datasets, assets, price bars, and corporate actions from the database.
    Used for test isolation and administrative resets.
    """
    session.query(CorporateActionModel).delete()
    session.query(PriceBarModel).delete()
    session.query(AssetModel).delete()
    session.query(DatasetModel).delete()
    session.commit()


# Convenience aliases
create_dataset = create_dataset_with_records
get_assets_by_dataset = get_dataset_assets
