from __future__ import annotations

import json
import math
import threading
import time
from collections import OrderedDict
from datetime import UTC, date, datetime
from hashlib import sha256
from io import BytesIO
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy import select

from app.db.models import DatasetModel, PriceBarModel
from app.db.session import get_db_session
from app.market_data import repository

REQUIRED_COLUMNS = {"date", "ticker", "market", "close", "currency"}
OPTIONAL_COLUMNS = {"open", "high", "low", "adjusted_close", "volume"}
PRICE_COLUMNS = {"close", "open", "high", "low", "adjusted_close"}
OPTIONAL_PRICE_COLUMNS = {"open", "high", "low", "adjusted_close"}
MAX_ROWS = 250_000
CACHE_TTL_SECONDS = 60
CACHE_MAX_ENTRIES = 64
DEFAULT_DATASET_CAPACITY = 100

_dataset_capacity: int = DEFAULT_DATASET_CAPACITY
_DATASETS_LOCK = threading.RLock()
_DATASETS: OrderedDict[str, dict] = OrderedDict()

_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict]] = {}


class DatasetNotFoundError(KeyError):
    pass


def get_dataset_registry_capacity() -> int:
    with _DATASETS_LOCK:
        return _dataset_capacity


def set_dataset_registry_capacity(capacity: int) -> None:
    global _dataset_capacity
    evicted_ids: list[str] = []
    with _DATASETS_LOCK:
        if capacity < 1:
            raise ValueError("Registry capacity must be at least 1.")
        _dataset_capacity = capacity
        while len(_DATASETS) > _dataset_capacity:
            ev_id, _ = _DATASETS.popitem(last=False)
            evicted_ids.append(ev_id)

    if evicted_ids:
        with get_db_session() as session:
            for ev_id in evicted_ids:
                ds = repository.get_dataset_by_id(session, ev_id)
                if ds is not None:
                    session.delete(ds)


def get_dataset_registry_size() -> int:
    with _DATASETS_LOCK:
        return len(_DATASETS)


def clear_dataset_registry() -> None:
    with _DATASETS_LOCK:
        _DATASETS.clear()
    with _CACHE_LOCK:
        _CACHE.clear()
    try:
        with get_db_session() as session:
            repository.clear_all_datasets(session)
    except Exception:
        pass


def _cache_get(key: str) -> dict | None:
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            _CACHE.pop(key, None)
            return None
        res = dict(value)
        if "valid_data" in res and res["valid_data"] is not None:
            res["valid_data"] = [dict(r) for r in res["valid_data"]]
        if "data" in res and res["data"] is not None:
            res["data"] = [dict(r) for r in res["data"]]
        if "errors" in res:
            res["errors"] = [dict(e) for e in res["errors"]]
        if "warnings" in res:
            res["warnings"] = [dict(w) for w in res["warnings"]]
        return res


def _cache_set(key: str, value: dict) -> None:
    with _CACHE_LOCK:
        now = time.monotonic()
        for old_key, (expires_at, _) in list(_CACHE.items()):
            if expires_at <= now:
                _CACHE.pop(old_key, None)
        while len(_CACHE) >= CACHE_MAX_ENTRIES:
            oldest = next(iter(_CACHE), None)
            if oldest is None:
                break
            _CACHE.pop(oldest, None)
        _CACHE[key] = (now + CACHE_TTL_SECONDS, value)


def _load_csv(raw: bytes) -> pd.DataFrame:
    if not raw or not raw.strip():
        raise ValueError("Uploaded file is empty.")
    try:
        frame = pd.read_csv(BytesIO(raw))
    except Exception as exc:
        raise ValueError(
            "Could not parse CSV. Check the file encoding and CSV format."
        ) from exc
    if frame.empty and len(frame.columns) == 0:
        raise ValueError("Uploaded file is empty.")
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
    if len(frame) > MAX_ROWS:
        raise ValueError(f"CSV has more than the {MAX_ROWS:,} row limit.")
    return frame


def _parse_numeric_field(
    raw_val: Any, is_price: bool = True
) -> tuple[float | None, str | None]:
    if raw_val is None or (isinstance(raw_val, float) and math.isnan(raw_val)):
        return None, None
    s = str(raw_val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None, None
    try:
        val = float(s)
    except (ValueError, TypeError):
        return None, "must be a valid number when provided."
    if math.isinf(val) or math.isnan(val):
        return None, "must be a finite number."
    if is_price and val <= 0:
        return None, "must be positive when provided."
    if (not is_price) and val < 0:
        return None, "must be non-negative."
    return val, None


def validate_csv(raw: bytes) -> dict:
    digest = sha256(raw).hexdigest()
    cache_key = f"preview:{digest}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    frame = _load_csv(raw)
    original_rows = len(frame)
    frame = frame.copy()
    frame["_source_row"] = range(2, original_rows + 2)
    errors: list[dict] = []
    warnings: list[dict] = []

    parsed_records: list[dict] = []

    for idx, row in frame.iterrows():
        row_num = int(row["_source_row"])
        row_reasons: list[str] = []

        # Validate Date
        raw_date = row.get("date")
        parsed_date_str = None
        if pd.isna(raw_date) or str(raw_date).strip() == "":
            row_reasons.append("Invalid or missing date.")
        else:
            try:
                dt = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
                parsed_date_str = dt.isoformat()
            except ValueError:
                row_reasons.append("Invalid or missing date.")

        # Validate Ticker
        raw_ticker = row.get("ticker")
        ticker = None
        if pd.isna(raw_ticker) or str(raw_ticker).strip() == "":
            row_reasons.append("Missing required ticker field.")
        else:
            ticker = str(raw_ticker).strip().upper()

        # Validate Market
        raw_market = row.get("market")
        market = None
        if pd.isna(raw_market) or str(raw_market).strip() == "":
            row_reasons.append("Market must be US or PSX.")
        else:
            m = str(raw_market).strip().upper()
            if m not in ("US", "PSX"):
                row_reasons.append("Market must be US or PSX.")
            else:
                market = m

        # Validate Currency
        raw_currency = row.get("currency")
        currency = None
        if pd.isna(raw_currency) or str(raw_currency).strip() == "":
            row_reasons.append("Missing required currency field.")
        else:
            c = str(raw_currency).strip().upper()
            if len(c) != 3 or not c.isalpha():
                row_reasons.append(
                    f"Invalid currency code '{raw_currency}'; must be 3 alphabetic letters."
                )
            else:
                currency = c

        # Validate Close Price
        raw_close = row.get("close")
        close_val = None
        if pd.isna(raw_close) or str(raw_close).strip() == "":
            row_reasons.append("Close must be a positive number.")
        else:
            val, err = _parse_numeric_field(raw_close, is_price=True)
            if err:
                row_reasons.append("Close must be a positive number.")
            else:
                close_val = val

        # Validate Optional Prices
        opt_prices: dict[str, float | None] = {}
        for col in OPTIONAL_PRICE_COLUMNS:
            if col in frame.columns:
                raw_v = row.get(col)
                val, err = _parse_numeric_field(raw_v, is_price=True)
                if err:
                    if "finite" in err:
                        row_reasons.append(f"{col} must be a finite number.")
                    elif "valid number" in err:
                        row_reasons.append(f"{col} must be a valid number when provided.")
                    else:
                        row_reasons.append(f"{col} {err}")
                else:
                    opt_prices[col] = val

        # High/Low consistency
        hi = opt_prices.get("high")
        lo = opt_prices.get("low")
        op = opt_prices.get("open")
        if hi is not None and lo is not None and hi < lo:
            row_reasons.append("High cannot be lower than low.")
        if hi is not None and close_val is not None and hi < close_val:
            row_reasons.append("High cannot be lower than close.")
        if hi is not None and op is not None and hi < op:
            row_reasons.append("High cannot be lower than open.")
        if lo is not None and close_val is not None and lo > close_val:
            row_reasons.append("Low cannot be higher than close.")
        if lo is not None and op is not None and lo > op:
            row_reasons.append("Low cannot be higher than open.")

        # Validate Volume
        volume_val = None
        if "volume" in frame.columns:
            raw_vol = row.get("volume")
            val, err = _parse_numeric_field(raw_vol, is_price=False)
            if err:
                if "finite" in err:
                    row_reasons.append("Volume must be a finite number.")
                elif "non-negative" in err:
                    row_reasons.append("Volume must be non-negative.")
                elif "valid number" in err:
                    row_reasons.append("volume must be a valid number when provided.")
                else:
                    row_reasons.append(f"Volume {err}")
            else:
                volume_val = val

        if row_reasons:
            errors.append({"row": row_num, "reasons": row_reasons})
        else:
            cleaned_row = {
                "date": parsed_date_str,
                "ticker": ticker,
                "market": market,
                "currency": currency,
                "close": close_val,
                "_source_row": row_num,
            }
            for col, v in opt_prices.items():
                cleaned_row[col] = v
            if "volume" in frame.columns:
                cleaned_row["volume"] = volume_val

            for col in frame.columns:
                if col not in cleaned_row and col != "_source_row":
                    cleaned_row[col] = None if pd.isna(row[col]) else row[col]
            parsed_records.append(cleaned_row)

    valid_frame = pd.DataFrame(parsed_records) if parsed_records else pd.DataFrame()
    if not valid_frame.empty:
        duplicate_mask = valid_frame.duplicated(
            subset=["date", "market", "ticker"], keep=False
        )
        for idx in valid_frame.index[duplicate_mask]:
            errors.append(
                {
                    "row": int(valid_frame.loc[idx, "_source_row"]),
                    "reasons": ["Duplicate date/market/ticker key; row excluded."],
                }
            )
        valid_frame = valid_frame.loc[~duplicate_mask].copy()

    errors.sort(key=lambda x: x["row"])

    for col in OPTIONAL_COLUMNS:
        if col not in frame.columns:
            warnings.append({"message": f"Optional column '{col}' is not present."})
    if valid_frame.empty:
        warnings.append({"message": "No valid rows remain after validation."})

    if not valid_frame.empty:
        valid_frame = valid_frame.drop(columns=["_source_row"], errors="ignore")
        valid_rows = [
            {k: (None if pd.isna(v) else v) for k, v in row.items()}
            for row in valid_frame.to_dict(orient="records")
        ]
    else:
        valid_rows = []

    report = {
        "content_sha256": digest,
        "rows_examined": original_rows,
        "valid_rows": len(valid_rows),
        "rejected_rows": original_rows - len(valid_rows),
        "errors": errors,
        "warnings": warnings,
        "valid_data": valid_rows,
    }
    _cache_set(cache_key, report)
    return report


def _build_metadata_from_model(model: DatasetModel) -> dict:
    created = model.created_at.isoformat() if hasattr(model.created_at, "isoformat") else str(model.created_at)
    return {
        "dataset_id": str(model.id),
        "filename": str(model.filename),
        "created_at": created,
        "content_sha256": str(model.content_sha256),
        "rows_examined": int(model.rows_examined),
        "valid_rows": int(model.valid_rows),
        "rejected_rows": int(model.rejected_rows),
        "errors": model.get_errors(),
        "warnings": model.get_warnings(),
        "user_id": str(model.user_id) if model.user_id else None,
        "is_shared": bool(model.is_shared) if hasattr(model, "is_shared") else False,
    }


def register_csv_dataset(
    raw: bytes,
    filename: str,
    user_id: str | None = None,
    is_shared: bool = False,
) -> dict:
    """
    Validates CSV, checks for duplicates via SHA-256 digest, and atomically
    persists dataset metadata, asset summaries, and clean price bars in the database.
    Associates the registered dataset with the user_id if provided.
    """
    report = validate_csv(raw)
    if report["valid_rows"] == 0:
        return report

    content_sha256 = report["content_sha256"]

    with get_db_session() as session:
        # Check duplicate registration policy scoped to user or shared datasets
        existing = repository.find_dataset_by_sha256(session, content_sha256, user_id=user_id)
        if existing is not None:
            if filename and filename != existing.filename:
                existing.filename = filename
                session.flush()
            metadata = _build_metadata_from_model(existing)
            # Synchronize in-memory cache
            with _DATASETS_LOCK:
                _DATASETS[existing.id] = {
                    "metadata": metadata,
                    "rows": [dict(r) for r in report["valid_data"]],
                }
                _DATASETS.move_to_end(existing.id)
            return metadata

        # Create new persistent dataset with user ownership
        dataset_id = str(uuid4())
        created_dataset = repository.create_dataset_with_records(
            session=session,
            dataset_id=dataset_id,
            filename=filename,
            content_sha256=content_sha256,
            rows_examined=report["rows_examined"],
            valid_rows=report["valid_rows"],
            rejected_rows=report["rejected_rows"],
            errors=report["errors"],
            warnings=report["warnings"],
            valid_records=report["valid_data"],
            user_id=user_id,
            is_shared=is_shared,
        )
        metadata = _build_metadata_from_model(created_dataset)

    # Update in-memory registry cache and evict from DB if capacity exceeded
    evicted_ids: list[str] = []
    with _DATASETS_LOCK:
        while len(_DATASETS) >= _dataset_capacity:
            ev_id, _ = _DATASETS.popitem(last=False)
            evicted_ids.append(ev_id)
        _DATASETS[dataset_id] = {
            "metadata": metadata,
            "rows": [dict(r) for r in report["valid_data"]],
        }
        _DATASETS.move_to_end(dataset_id)

    if evicted_ids:
        with get_db_session() as session:
            for ev_id in evicted_ids:
                ds = repository.get_dataset_by_id(session, ev_id)
                if ds is not None:
                    session.delete(ds)

    return metadata


def list_all_datasets(
    limit: int = 100,
    offset: int = 0,
    user_id: str | None = None,
    is_admin: bool = False,
) -> list[dict]:
    """
    Retrieves list of persistent datasets, filtered by access rights.
    """
    with get_db_session() as session:
        records = repository.list_datasets(
            session, limit=limit, offset=offset, user_id=user_id, is_admin=is_admin
        )
        return [_build_metadata_from_model(m) for m in records]


def get_dataset_metadata(dataset_id: str) -> dict:
    """
    Retrieves metadata for a dataset ID from cache or persistent database.
    """
    with _DATASETS_LOCK:
        if dataset_id in _DATASETS:
            _DATASETS.move_to_end(dataset_id)
            return _DATASETS[dataset_id]["metadata"].copy()

    with get_db_session() as session:
        model = repository.get_dataset_by_id(session, dataset_id)
        if model is None:
            raise DatasetNotFoundError(
                f"Dataset '{dataset_id}' was not found in persistent storage or registry."
            )
        metadata = _build_metadata_from_model(model)

    # Populate cache
    with _DATASETS_LOCK:
        if dataset_id not in _DATASETS:
            _DATASETS[dataset_id] = {"metadata": metadata, "rows": []}
            _DATASETS.move_to_end(dataset_id)

    return metadata


def get_dataset_rows(dataset_id: str) -> list[dict]:
    """
    Returns verified price bars for the dataset ID, retrieving from database if not cached.
    """
    with _DATASETS_LOCK:
        if dataset_id in _DATASETS and _DATASETS[dataset_id].get("rows"):
            _DATASETS.move_to_end(dataset_id)
            return [dict(r) for r in _DATASETS[dataset_id]["rows"]]

    with get_db_session() as session:
        model = repository.get_dataset_by_id(session, dataset_id)
        if model is None:
            raise DatasetNotFoundError(
                f"Dataset '{dataset_id}' was not found in persistent storage or registry."
            )
        metadata = _build_metadata_from_model(model)
        
        bars = session.scalars(
            select(PriceBarModel)
            .where(PriceBarModel.dataset_id == dataset_id)
            .order_by(PriceBarModel.date.asc(), PriceBarModel.ticker.asc())
        ).all()

        rows = [
            {
                "date": b.date.isoformat(),
                "ticker": b.ticker,
                "market": b.market,
                "currency": b.currency,
                "close": b.close,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "adj_close": b.adj_close,
                "adjusted_close": b.adj_close,
                "volume": b.volume,
            }
            for b in bars
        ]

    with _DATASETS_LOCK:
        _DATASETS[dataset_id] = {"metadata": metadata, "rows": rows}
        _DATASETS.move_to_end(dataset_id)

    return [dict(r) for r in rows]


def query_dataset(
    dataset_id: str,
    start_date: date,
    end_date: date,
    tickers: list[str] | None = None,
    market: str | None = None,
) -> dict:
    """
    Filters a registered dataset by inclusive date range, optional ticker list, and market identifier.
    Uses indexed database queries and bounded result caching.
    """
    norm_tickers = sorted([t.strip().upper() for t in tickers]) if tickers else None
    norm_market = market.strip().upper() if market else None

    with _DATASETS_LOCK:
        if dataset_id in _DATASETS:
            _DATASETS.move_to_end(dataset_id)

    cache_key = (
        "query:"
        + sha256(
            json.dumps(
                {
                    "dataset_id": dataset_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "tickers": norm_tickers,
                    "market": norm_market,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    with get_db_session() as session:
        # Check if dataset exists
        model = repository.get_dataset_by_id(session, dataset_id)
        if model is None:
            # Fallback check in memory for mock tests
            with _DATASETS_LOCK:
                if dataset_id not in _DATASETS:
                    raise DatasetNotFoundError(
                        f"Dataset '{dataset_id}' was not found in persistent storage or registry."
                    )
                in_mem_rows = [dict(r) for r in _DATASETS[dataset_id]["rows"]]
            
            ticker_set = set(norm_tickers) if norm_tickers else None
            filtered = []
            for row in in_mem_rows:
                row_date = date.fromisoformat(row["date"])
                if not (start_date <= row_date <= end_date):
                    continue
                if ticker_set and row["ticker"] not in ticker_set:
                    continue
                if norm_market and row["market"] != norm_market:
                    continue
                filtered.append(dict(row))
        else:
            bars = repository.query_price_bars(
                session=session,
                dataset_id=dataset_id,
                start_date=start_date,
                end_date=end_date,
                tickers=norm_tickers,
                market=norm_market,
            )
            filtered = [
                {
                    "date": b.date.isoformat(),
                    "ticker": b.ticker,
                    "market": b.market,
                    "currency": b.currency,
                    "close": b.close,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "adj_close": b.adj_close,
                    "adjusted_close": b.adj_close,
                    "volume": b.volume,
                }
                for b in bars
            ]

    result = {
        "dataset_id": dataset_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "row_count": len(filtered),
        "data": filtered,
    }
    _cache_set(cache_key, result)
    return {
        **result,
        "data": [dict(r) for r in filtered],
    }
