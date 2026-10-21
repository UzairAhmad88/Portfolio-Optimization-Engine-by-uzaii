"""
Canonical observation manifest generation and cryptographic hashing engine.

Workstream 32.1 & 32.3:
- Provides deterministic, permutation-invariant content-addressing for financial datasets.
- Eliminates formatting, row-ordering, and whitespace fragility of raw file digests.
- Computes hierarchical Merkle digests for normalized price bars and corporate actions.
- Seals point-in-time cutoff, exchange calendar, and adjustment policy versions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import hashlib
import json
from typing import Any, Iterable

from app.market_data.corporate_actions import CorporateActionEvent, CorporateActionStatus


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


def _format_float(val: float | None, precision: int = 6) -> str:
    if val is None:
        return "null"
    return f"{float(val):.{precision}f}"


def _format_date(val: Any) -> str:
    if val is None:
        return "null"
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def compute_price_bars_digest(
    records: Iterable[dict[str, Any]],
) -> tuple[str, int, dict[str, CanonicalAssetSummary]]:
    """
    Computes a deterministic, permutation-invariant SHA-256 digest of normalized price bars.

    Sorts rows lexicographically by (ticker ASC, market ASC, date ASC) to ensure that
    shuffled row ordering produces an identical digest.
    """
    # 1. Normalize individual records
    normalized_bars: list[tuple[str, str, str, str]] = []
    asset_accum: dict[str, dict[str, Any]] = {}

    for r in records:
        ticker = str(r.get("ticker", "")).strip().upper()
        market = str(r.get("market", "")).strip().upper()
        currency = str(r.get("currency", "USD")).strip().upper()
        composite_id = f"{ticker}:{market}"

        d_str = _format_date(r.get("date"))
        op_str = _format_float(r.get("open"), 6)
        hi_str = _format_float(r.get("high"), 6)
        lo_str = _format_float(r.get("low"), 6)
        cl_str = _format_float(r.get("close"), 6)
        adj_str = _format_float(r.get("adjusted_close") if r.get("adjusted_close") is not None else r.get("adj_close"), 6)
        vol_str = _format_float(r.get("volume"), 2)

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
    actions: Iterable[CorporateActionEvent],
) -> tuple[str, int, list[str]]:
    """
    Computes a deterministic, permutation-invariant SHA-256 digest of active corporate actions.
    """
    normalized_actions: list[tuple[str, str, str, str]] = []

    for ev in actions:
        eff_d = _format_date(ev.effective_date)
        ann_d = _format_date(ev.announcement_date)
        t = ev.ticker.strip().upper()
        m = ev.market.strip().upper()
        ev_type = str(ev.event_type.value if hasattr(ev.event_type, "value") else ev.event_type)
        v_str = _format_float(ev.value, 6)
        curr = ev.currency.strip().upper()
        st = str(ev.status.value if hasattr(ev.status, "value") else ev.status)
        rev = str(ev.revision_id or "null").strip()

        # Canonical action line: EFF_DATE|TICKER|MARKET|EVENT_ID|TYPE|ANN_DATE|VAL|CURR|STATUS|REV
        line = f"{eff_d}|{t}|{m}|{ev.event_id}|{ev_type}|{ann_d}|{v_str}|{curr}|{st}|{rev}"
        normalized_actions.append((eff_d, t, ev.event_id, line))

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
    records: Iterable[dict[str, Any]],
    corporate_actions: Iterable[CorporateActionEvent] = (),
    as_of_date: date | str | None = None,
    calendar_version: str | None = "US-NYSE-2026.1",
    adjustment_policy_version: str | None = "2026.1",
    point_in_time_status: str = "unverified_legacy",
) -> DatasetManifest:
    """
    Builds the authoritative canonical DatasetManifest with hierarchical composite hashing.
    """
    bars_digest, total_bars, assets_summary = compute_price_bars_digest(records)
    actions_digest, total_actions, action_event_ids = compute_corporate_actions_digest(corporate_actions)

    as_of_str = _format_date(as_of_date) if as_of_date is not None else None
    cal_v = str(calendar_version).strip() if calendar_version else "null"
    adj_v = str(adjustment_policy_version).strip() if adjustment_policy_version else "null"
    pit_st = str(point_in_time_status).strip()

    # Merkle composite manifest digest
    composite_payload = (
        f"DATASET_MANIFEST:v1:{dataset_id}:{bars_digest}:{actions_digest}:"
        f"{cal_v}:{adj_v}:{as_of_str}:{pit_st}"
    )
    manifest_sha256 = hashlib.sha256(composite_payload.encode("utf-8")).hexdigest()

    return DatasetManifest(
        manifest_version="1.0",
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
