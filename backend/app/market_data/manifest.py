"""
Canonical observation manifest generation and cryptographic hashing engine.

Workstream 32.1 & 32.3:
- Provides deterministic, permutation-invariant content-addressing for financial datasets.
- Eliminates formatting, row-ordering, and whitespace fragility of raw file digests.
- Computes hierarchical Merkle digests for normalized price bars and corporate actions.
- Seals point-in-time cutoff, exchange calendar, and adjustment policy versions.
- Preserves 8-decimal numerical precision for financial price calculations and corporate split fractions.
- Supports canonical frozen payload serialization and deserialization for immutable snapshot replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import hashlib
import json
from typing import Any, Iterable

from app.market_data.corporate_actions import CorporateActionEvent, CorporateActionStatus, CorporateActionType

DEFAULT_MANIFEST_VERSION = "1.1"


@dataclass(frozen=True)
class CanonicalAssetSummary:
    asset_id: str
    ticker: str
    market: str
    currency: str
    start_date: str
    end_date: str
    observation_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetManifest:
    manifest_version: str
    dataset_id: str
    as_of_date: str | None
    calendar_version: str | None
    adjustment_policy_version: str | None
    point_in_time_status: str
    bars_digest: str
    actions_digest: str
    manifest_sha256: str
    total_bars: int
    total_actions: int
    assets: dict[str, dict[str, Any]]
    action_event_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _format_float(val: float | None, precision: int = 8) -> str:
    if val is None:
        return "null"
    return f"{float(val):.{precision}f}"


def _format_date(val: Any) -> str:
    if val is None:
        return "null"
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def compute_price_bars_digest(
    records: Iterable[dict[str, Any] | Any],
    manifest_version: str = DEFAULT_MANIFEST_VERSION,
) -> tuple[str, int, dict[str, CanonicalAssetSummary]]:
    """
    Computes a deterministic, permutation-invariant SHA-256 digest of normalized price bars.

    Sorts rows lexicographically by (ticker ASC, market ASC, date ASC) to ensure that
    shuffled row ordering produces an identical digest.

    Precision policy:
    - manifest_version == "1.0": 6 decimal places for price, 2 for volume.
    - manifest_version >= "1.1": 8 decimal places for price, 4 for volume (preserves penny fractions and sub-penny assets).
    """
    price_prec = 6 if manifest_version == "1.0" else 8
    vol_prec = 2 if manifest_version == "1.0" else 4

    # 1. Normalize individual records
    normalized_bars: list[tuple[str, str, str, str]] = []
    asset_accum: dict[str, dict[str, Any]] = {}

    for r in records:
        ticker = str(_get_val(r, "ticker", "")).strip().upper()
        market = str(_get_val(r, "market", "")).strip().upper()
        currency = str(_get_val(r, "currency", "USD")).strip().upper()
        composite_id = f"{ticker}:{market}"

        d_str = _format_date(_get_val(r, "date"))
        op_str = _format_float(_get_val(r, "open"), price_prec)
        hi_str = _format_float(_get_val(r, "high"), price_prec)
        lo_str = _format_float(_get_val(r, "low"), price_prec)
        cl_str = _format_float(_get_val(r, "close"), price_prec)

        adj_val = _get_val(r, "adjusted_close")
        if adj_val is None:
            adj_val = _get_val(r, "adj_close")
        adj_str = _format_float(adj_val, price_prec)
        vol_str = _format_float(_get_val(r, "volume"), vol_prec)

        # Canonical bar line: TICKER|MARKET|DATE|OPEN|HIGH|LOW|CLOSE|ADJ_CLOSE|VOLUME
        bar_line = f"{ticker}|{market}|{d_str}|{op_str}|{hi_str}|{lo_str}|{cl_str}|{adj_str}|{vol_str}"
        normalized_bars.append((ticker, market, d_str, bar_line))

        # Accumulate asset boundary statistics
        if composite_id not in asset_accum:
            asset_accum[composite_id] = {
                "asset_id": composite_id,
                "ticker": ticker,
                "market": market,
                "currency": currency,
                "start_date": d_str,
                "end_date": d_str,
                "count": 0,
            }
        cur = asset_accum[composite_id]
        if d_str < cur["start_date"]:
            cur["start_date"] = d_str
        if d_str > cur["end_date"]:
            cur["end_date"] = d_str
        cur["count"] += 1

    # 2. Sort deterministically by (ticker, market, date)
    normalized_bars.sort(key=lambda item: (item[0], item[1], item[2]))

    # 3. Stream through SHA-256
    hasher = hashlib.sha256()
    for _, _, _, line in normalized_bars:
        hasher.update(line.encode("utf-8"))
        hasher.update(b"\n")

    bars_digest = hasher.hexdigest()
    total_bars = len(normalized_bars)

    assets_summary: dict[str, CanonicalAssetSummary] = {
        aid: CanonicalAssetSummary(
            asset_id=aid,
            ticker=v["ticker"],
            market=v["market"],
            currency=v["currency"],
            start_date=v["start_date"],
            end_date=v["end_date"],
            observation_count=v["count"],
        )
        for aid, v in sorted(asset_accum.items())
    }

    return bars_digest, total_bars, assets_summary


def compute_corporate_actions_digest(
    actions: Iterable[CorporateActionEvent | dict[str, Any] | Any],
    manifest_version: str = DEFAULT_MANIFEST_VERSION,
) -> tuple[str, int, list[str]]:
    """
    Computes a deterministic, permutation-invariant SHA-256 digest of active corporate actions.
    Precision policy:
    - manifest_version == "1.0": 6 decimal places for value.
    - manifest_version >= "1.1": 8 decimal places for value.
    """
    val_prec = 6 if manifest_version == "1.0" else 8
    normalized_actions: list[tuple[str, str, str, str]] = []

    for ev in actions:
        eff_d = _format_date(_get_val(ev, "effective_date"))
        ann_d = _format_date(_get_val(ev, "announcement_date"))
        t = str(_get_val(ev, "ticker", "")).strip().upper()
        m = str(_get_val(ev, "market", "")).strip().upper()

        ev_type_raw = _get_val(ev, "event_type", "")
        ev_type = str(ev_type_raw.value if hasattr(ev_type_raw, "value") else ev_type_raw)
        v_str = _format_float(_get_val(ev, "value"), val_prec)
        curr = str(_get_val(ev, "currency", "USD")).strip().upper()

        st_raw = _get_val(ev, "status", "active")
        st = str(st_raw.value if hasattr(st_raw, "value") else st_raw)
        rev = str(_get_val(ev, "revision_id") or "null").strip()
        ev_id = str(_get_val(ev, "event_id") or _get_val(ev, "id") or "")

        # Canonical action line: EFF_DATE|TICKER|MARKET|EVENT_ID|TYPE|ANN_DATE|VAL|CURR|STATUS|REV
        line = f"{eff_d}|{t}|{m}|{ev_id}|{ev_type}|{ann_d}|{v_str}|{curr}|{st}|{rev}"
        normalized_actions.append((eff_d, t, ev_id, line))

    # Sort deterministically by (effective_date, ticker, event_id)
    normalized_actions.sort(key=lambda item: (item[0], item[1], item[2]))

    hasher = hashlib.sha256()
    action_ids: list[str] = []
    for _, _, ev_id, line in normalized_actions:
        hasher.update(line.encode("utf-8"))
        hasher.update(b"\n")
        action_ids.append(ev_id)

    actions_digest = hasher.hexdigest()
    total_actions = len(normalized_actions)

    return actions_digest, total_actions, action_ids


def build_dataset_manifest(
    dataset_id: str,
    records: Iterable[dict[str, Any] | Any],
    corporate_actions: Iterable[CorporateActionEvent | dict[str, Any] | Any] = (),
    as_of_date: date | str | None = None,
    calendar_version: str | None = "US-NYSE-2026.1",
    adjustment_policy_version: str | None = "2026.1",
    point_in_time_status: str = "unverified_legacy",
    manifest_version: str = DEFAULT_MANIFEST_VERSION,
) -> DatasetManifest:
    """
    Builds the authoritative canonical DatasetManifest with hierarchical composite hashing.
    Supports versioned manifest schema ("1.0" or "1.1").
    """
    bars_digest, total_bars, assets_summary = compute_price_bars_digest(records, manifest_version=manifest_version)
    actions_digest, total_actions, action_event_ids = compute_corporate_actions_digest(corporate_actions, manifest_version=manifest_version)

    as_of_str = _format_date(as_of_date) if as_of_date is not None else None
    cal_v = str(calendar_version).strip() if calendar_version else "null"
    adj_v = str(adjustment_policy_version).strip() if adjustment_policy_version else "null"
    pit_st = str(point_in_time_status).strip()

    # Merkle composite manifest digest
    version_tag = "v1" if manifest_version == "1.0" else f"v{manifest_version}"
    composite_payload = (
        f"DATASET_MANIFEST:{version_tag}:{dataset_id}:{bars_digest}:{actions_digest}:"
        f"{cal_v}:{adj_v}:{as_of_str}:{pit_st}"
    )
    manifest_sha256 = hashlib.sha256(composite_payload.encode("utf-8")).hexdigest()

    return DatasetManifest(
        manifest_version=manifest_version,
        dataset_id=dataset_id,
        as_of_date=as_of_str,
        calendar_version=calendar_version,
        adjustment_policy_version=adjustment_policy_version,
        point_in_time_status=pit_st,
        bars_digest=bars_digest,
        actions_digest=actions_digest,
        manifest_sha256=manifest_sha256,
        total_bars=total_bars,
        total_actions=total_actions,
        assets={aid: a.to_dict() for aid, a in assets_summary.items()},
        action_event_ids=action_event_ids,
    )


def serialize_frozen_payload(
    records: Iterable[dict[str, Any] | Any],
    corporate_actions: Iterable[CorporateActionEvent | dict[str, Any] | Any] = (),
) -> str:
    """
    Deterministically serializes the raw normalized observations and corporate actions
    into a canonical frozen JSON payload.
    """
    clean_bars: list[dict[str, Any]] = []
    for r in records:
        adj = _get_val(r, "adjusted_close")
        if adj is None:
            adj = _get_val(r, "adj_close")

        clean_bars.append({
            "ticker": str(_get_val(r, "ticker", "")).strip().upper(),
            "market": str(_get_val(r, "market", "")).strip().upper(),
            "currency": str(_get_val(r, "currency", "USD")).strip().upper(),
            "date": _format_date(_get_val(r, "date")),
            "open": float(_get_val(r, "open")) if _get_val(r, "open") is not None else None,
            "high": float(_get_val(r, "high")) if _get_val(r, "high") is not None else None,
            "low": float(_get_val(r, "low")) if _get_val(r, "low") is not None else None,
            "close": float(_get_val(r, "close")),
            "adj_close": float(adj) if adj is not None else None,
            "volume": float(_get_val(r, "volume")) if _get_val(r, "volume") is not None else None,
        })

    # Sort deterministically
    clean_bars.sort(key=lambda b: (b["ticker"], b["market"], b["date"]))

    clean_actions: list[dict[str, Any]] = []
    for ev in corporate_actions:
        ev_type_raw = _get_val(ev, "event_type", "")
        ev_type = str(ev_type_raw.value if hasattr(ev_type_raw, "value") else ev_type_raw)
        st_raw = _get_val(ev, "status", "active")
        st = str(st_raw.value if hasattr(st_raw, "value") else st_raw)
        ev_id = str(_get_val(ev, "event_id") or _get_val(ev, "id") or "")
        created_at_val = _get_val(ev, "created_at")

        clean_actions.append({
            "event_id": ev_id,
            "asset_id": str(_get_val(ev, "asset_id", "")).strip().upper(),
            "ticker": str(_get_val(ev, "ticker", "")).strip().upper(),
            "market": str(_get_val(ev, "market", "")).strip().upper(),
            "event_type": ev_type,
            "effective_date": _format_date(_get_val(ev, "effective_date")),
            "announcement_date": _format_date(_get_val(ev, "announcement_date")) if _get_val(ev, "announcement_date") else None,
            "ex_date": _format_date(_get_val(ev, "ex_date")) if _get_val(ev, "ex_date") else None,
            "record_date": _format_date(_get_val(ev, "record_date")) if _get_val(ev, "record_date") else None,
            "payment_date": _format_date(_get_val(ev, "payment_date")) if _get_val(ev, "payment_date") else None,
            "value": float(_get_val(ev, "value")),
            "currency": str(_get_val(ev, "currency", "USD")).strip().upper(),
            "source": str(_get_val(ev, "source", "system")),
            "revision_id": str(_get_val(ev, "revision_id")) if _get_val(ev, "revision_id") else None,
            "status": st,
            "is_point_in_time_verified": bool(_get_val(ev, "is_point_in_time_verified", False)),
            "created_at": created_at_val.isoformat() if isinstance(created_at_val, (date, datetime)) else str(created_at_val or ""),
        })

    clean_actions.sort(key=lambda a: (a["effective_date"], a["ticker"], a["event_id"]))

    payload = {
        "price_bars": clean_bars,
        "corporate_actions": clean_actions,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_frozen_payload(payload_json: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Deserializes a frozen JSON payload into (price_bars, corporate_actions).
    """
    if not payload_json:
        return [], []
    data = json.loads(payload_json)
    return data.get("price_bars", []), data.get("corporate_actions", [])
