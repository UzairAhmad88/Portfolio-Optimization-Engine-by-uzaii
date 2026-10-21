"""
Immutable dataset snapshot creation, cryptographic replay, and deterministic verification service.

Workstream 32.4 & 32.5:
- Captures transactionally consistent, frozen snapshots of market data and corporate actions.
- Content-addresses every snapshot using Merkle canonical observation manifests.
- Materializes exact normalized observations into immutable frozen payloads.
- Verifies cryptographic integrity prior to replay; fails closed on missing or corrupted content.
- Completely decouples replayed input data from subsequent operational table mutations.
- Preserves point-in-time cutoffs, calendar versions, and return adjustment semantics.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.db.models import (
    CorporateActionModel,
    DatasetModel,
    DatasetSnapshotModel,
    PriceBarModel,
    UserModel,
)
from app.market_data.adjustments import (
    AdjustmentPolicy,
    adjust_ohlcv_series,
)
from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)
from app.market_data.manifest import (
    DEFAULT_MANIFEST_VERSION,
    DatasetManifest,
    build_dataset_manifest,
    deserialize_frozen_payload,
    serialize_frozen_payload,
)
from app.market_data.point_in_time import (
    PointInTimeCutoff,
    filter_point_in_time_actions,
)


class SnapshotError(Exception):
    """Base exception for dataset snapshot operations."""
    pass


class SnapshotNotFoundError(SnapshotError, KeyError):
    """Raised when the requested snapshot does not exist."""
    pass


class SnapshotPermissionError(SnapshotError, PermissionError):
    """Raised when the requesting user is unauthorized to access the snapshot."""
    pass


class SnapshotIntegrityError(SnapshotError, ValueError):
    """Raised when a snapshot's cryptographic manifest or frozen payload fails verification."""
    pass


class SnapshotValidationError(SnapshotError, ValueError):
    """Raised when snapshot parameters or contents violate operational constraints."""
    pass


def create_dataset_snapshot(
    dataset_id: str,
    user: UserModel,
    session: Session,
    tag: str | None = None,
    description: str | None = None,
    snapshot_type: str = "manual",  # "manual", "auto_backtest", "auto_experiment"
    as_of_date: date | str | None = None,
    strict_pit: bool = False,
    calendar_version: str | None = "US-NYSE-2026.1",
    adjustment_policy_version: str | None = "2026.1",
    point_in_time_status: str | None = None,
    manifest_version: str = DEFAULT_MANIFEST_VERSION,
) -> DatasetSnapshotModel:
    """
    Creates an immutable, content-addressed dataset snapshot capturing a frozen view
    of price bars and active corporate actions.

    Idempotency:
        If `tag` is provided and a snapshot already exists with `(dataset_id, tag)`,
        validates whether the existing snapshot has matching manifest digest.
        Returns the existing snapshot if matching, or raises SnapshotValidationError if conflicting.
    """
    # 1. Authorize dataset access
    dataset = check_dataset_access(session, dataset_id, user)

    # 2. Parse as_of_date if provided
    as_of_d: date | None = None
    if as_of_date is not None:
        if isinstance(as_of_date, str):
            as_of_d = date.fromisoformat(as_of_date.strip())
        elif isinstance(as_of_date, date):
            as_of_d = as_of_date

    # 3. Query price bars transactionally
    bars_stmt = select(PriceBarModel).where(PriceBarModel.dataset_id == dataset_id)
    if as_of_d is not None:
        bars_stmt = bars_stmt.where(PriceBarModel.date <= as_of_d)
    bars_stmt = bars_stmt.order_by(PriceBarModel.date.asc(), PriceBarModel.ticker.asc())
    bars_models = list(session.scalars(bars_stmt).all())

    if not bars_models:
        raise SnapshotValidationError(
            f"Dataset '{dataset_id}' contains no historical price observations to snapshot "
            f"(as_of_date={as_of_d})."
        )

    # 4. Query corporate actions for assets present in the dataset
    asset_ids = sorted({b.asset_id for b in bars_models})
    ca_stmt = (
        select(CorporateActionModel)
        .where(
            CorporateActionModel.asset_id.in_(asset_ids),
            (CorporateActionModel.dataset_id == dataset_id)
            | (CorporateActionModel.dataset_id.is_(None)),
        )
        .order_by(CorporateActionModel.effective_date.asc(), CorporateActionModel.id.asc())
    )
    ca_models = list(session.scalars(ca_stmt).all())

    domain_actions: list[CorporateActionEvent] = []
    for m in ca_models:
        domain_actions.append(
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
        )

    # 5. Apply point-in-time filtering if as_of_d is specified
    if as_of_d is not None:
        cutoff = PointInTimeCutoff(as_of_date=as_of_d, strict=strict_pit)
        filtered_actions, pit_audit = filter_point_in_time_actions(domain_actions, cutoff)
    else:
        filtered_actions = [a for a in domain_actions if a.status == CorporateActionStatus.ACTIVE]

    # 6. Resolve authoritative point_in_time_status
    if point_in_time_status is not None:
        effective_pit_status = point_in_time_status
    else:
        # Strict evaluation: verify if dataset corporate actions are certified point-in-time
        if filtered_actions:
            all_verified = all(
                a.is_point_in_time_verified and a.announcement_date is not None
                for a in filtered_actions
            )
            effective_pit_status = "verified_point_in_time" if (all_verified and strict_pit) else "unverified_legacy"
        else:
            effective_pit_status = "verified_point_in_time" if strict_pit else "unverified_legacy"

    # 7. Compute Canonical Manifest and Hierarchical Composite Digest
    manifest: DatasetManifest = build_dataset_manifest(
        dataset_id=dataset_id,
        records=bars_models,
        corporate_actions=filtered_actions,
        as_of_date=as_of_d,
        calendar_version=calendar_version,
        adjustment_policy_version=adjustment_policy_version,
        point_in_time_status=effective_pit_status,
        manifest_version=manifest_version,
    )

    # 8. Check idempotency if tag is specified
    if tag:
        existing_stmt = select(DatasetSnapshotModel).where(
            DatasetSnapshotModel.dataset_id == dataset_id,
            DatasetSnapshotModel.tag == tag,
        )
        existing = session.scalars(existing_stmt).first()
        if existing is not None:
            if existing.manifest_sha256 == manifest.manifest_sha256:
                return existing
            raise SnapshotValidationError(
                f"A snapshot with tag '{tag}' already exists on dataset '{dataset_id}' "
                f"with a different manifest hash ({existing.manifest_sha256} vs {manifest.manifest_sha256})."
            )

    # 9. Materialize frozen payload
    frozen_payload_json = serialize_frozen_payload(bars_models, filtered_actions)

    # 10. Persist DatasetSnapshotModel
    snapshot_id = str(uuid4())
    snapshot = DatasetSnapshotModel(
        id=snapshot_id,
        dataset_id=dataset_id,
        user_id=user.id if user else None,
        tag=tag,
        description=description,
        snapshot_type=snapshot_type,
        manifest_sha256=manifest.manifest_sha256,
        manifest_json=manifest.to_json(),
        frozen_payload_json=frozen_payload_json,
        as_of_date=as_of_d,
        point_in_time_status=effective_pit_status,
        calendar_version=calendar_version,
        adjustment_policy_version=adjustment_policy_version,
        is_frozen=True,
        total_bars_count=manifest.total_bars,
        total_actions_count=manifest.total_actions,
        created_at=datetime.now(timezone.utc),
    )

    session.add(snapshot)
    session.flush()

    return snapshot


def resolve_snapshot_price_panel(
    snapshot_id: str,
    user: UserModel,
    session: Session,
    requested_assets: list[str] | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    adjustment_type: str = "total",  # "total", "split_only", "unadjusted"
    min_required_observations: int = 2,
) -> tuple[pd.DataFrame, list[str], str, int, dict[str, Any]]:
    """
    Reconstructs the frozen historical input panel using ONLY the snapshot's captured
    materialized data and verifies cryptographic composite manifest integrity.

    Guarantees:
    - Never falls back to mutable current operational tables.
    - Fails closed with SnapshotIntegrityError if the payload was altered or corrupted.
    - Fully decoupled from subsequent operational price updates, additions, or deletes.
    - Returns synchronized pd.DataFrame with attached snapshot provenance metadata.
    """
    # 1. Fetch snapshot record
    snapshot = session.get(DatasetSnapshotModel, snapshot_id)
    if snapshot is None:
        raise SnapshotNotFoundError(f"Dataset snapshot '{snapshot_id}' not found.")

    # 2. Authorization check
    if user.role != "admin" and snapshot.user_id and snapshot.user_id != user.id:
        ds = session.get(DatasetModel, snapshot.dataset_id)
        if not (ds and (ds.is_shared or ds.user_id == user.id or ds.user_id is None)):
            raise SnapshotPermissionError(
                f"User '{user.id}' is not authorized to access snapshot '{snapshot_id}'."
            )

    # 3. Fail closed if frozen payload is missing
    if not snapshot.frozen_payload_json:
        raise SnapshotIntegrityError(
            f"Snapshot '{snapshot_id}' lacks frozen payload. "
            f"Silent fallback to mutable operational data is strictly prohibited."
        )

    # 4. Parse frozen payload
    try:
        frozen_bars, frozen_actions = deserialize_frozen_payload(snapshot.frozen_payload_json)
    except Exception as exc:
        raise SnapshotIntegrityError(
            f"Failed to deserialize frozen payload for snapshot '{snapshot_id}': {exc}"
        ) from exc

    if not frozen_bars:
        raise SnapshotIntegrityError(
            f"Snapshot '{snapshot_id}' frozen payload contains no price bars."
        )

    # 5. Cryptographic integrity verification against canonical manifest
    manifest_meta = snapshot.get_manifest()
    m_version = manifest_meta.get("manifest_version", DEFAULT_MANIFEST_VERSION)

    recomputed = build_dataset_manifest(
        dataset_id=snapshot.dataset_id,
        records=frozen_bars,
        corporate_actions=frozen_actions,
        as_of_date=snapshot.as_of_date,
        calendar_version=snapshot.calendar_version,
        adjustment_policy_version=snapshot.adjustment_policy_version,
        point_in_time_status=snapshot.point_in_time_status,
        manifest_version=m_version,
    )

    if recomputed.manifest_sha256 != snapshot.manifest_sha256:
        raise SnapshotIntegrityError(
            f"Cryptographic integrity verification failed for snapshot '{snapshot_id}'. "
            f"Expected SHA-256 '{snapshot.manifest_sha256}', computed '{recomputed.manifest_sha256}'."
        )

    if (
        recomputed.bars_digest != snapshot.get_manifest().get("bars_digest")
        or recomputed.actions_digest != snapshot.get_manifest().get("actions_digest")
    ):
        raise SnapshotIntegrityError(
            f"Sub-component composite digest mismatch in snapshot '{snapshot_id}'."
        )

    # 6. Parse date bounds
    start_d: date | None = None
    if start_date is not None:
        start_d = date.fromisoformat(start_date.strip()) if isinstance(start_date, str) else start_date

    end_d: date | None = None
    if end_date is not None:
        end_d = date.fromisoformat(end_date.strip()) if isinstance(end_date, str) else end_date

    # 7. Asset mapping from frozen observations
    composite_map: dict[str, list[dict[str, Any]]] = {}
    ticker_to_composites: dict[str, set[str]] = {}
    currencies: set[str] = set()
    markets: set[str] = set()

    for b in frozen_bars:
        t = b["ticker"]
        m = b["market"]
        cid = f"{t}:{m}"
        composite_map.setdefault(cid, []).append(b)
        ticker_to_composites.setdefault(t, set()).add(cid)
        currencies.add(b["currency"])
        markets.add(m)

    # Resolve requested assets
    resolved_asset_ids: list[str] = []
    if requested_assets:
        for raw_asset in requested_assets:
            sel = str(raw_asset).strip().upper()
            if sel in composite_map:
                resolved_asset_ids.append(sel)
            elif sel in ticker_to_composites and len(ticker_to_composites[sel]) == 1:
                resolved_asset_ids.append(next(iter(ticker_to_composites[sel])))
            else:
                raise SnapshotValidationError(
                    f"Requested asset '{raw_asset}' is not present or ambiguous in snapshot '{snapshot_id}'."
                )
    else:
        resolved_asset_ids = sorted(composite_map.keys())

    # 8. Currency homogeneity validation
    if len(currencies) > 1:
        raise SnapshotValidationError(
            f"Multi-currency observations detected in snapshot '{snapshot_id}': {sorted(currencies)}."
        )
    currency = next(iter(currencies)) if currencies else "USD"
    periods_per_year = 250 if "PSX" in markets else 252

    # 9. Corporate action mapping by asset
    actions_by_asset: dict[str, list[CorporateActionEvent]] = {}
    for a in frozen_actions:
        aid = a["asset_id"]
        ev = CorporateActionEvent(
            event_id=a["event_id"],
            asset_id=aid,
            ticker=a["ticker"],
            market=a["market"],
            event_type=CorporateActionType(a["event_type"]),
            effective_date=date.fromisoformat(a["effective_date"]) if isinstance(a["effective_date"], str) else a["effective_date"],
            value=float(a["value"]),
            currency=a["currency"],
            source=a.get("source", "system"),
            announcement_date=date.fromisoformat(a["announcement_date"]) if a.get("announcement_date") else None,
            ex_date=date.fromisoformat(a["ex_date"]) if a.get("ex_date") else None,
            record_date=date.fromisoformat(a["record_date"]) if a.get("record_date") else None,
            payment_date=date.fromisoformat(a["payment_date"]) if a.get("payment_date") else None,
            revision_id=a.get("revision_id"),
            status=CorporateActionStatus(a.get("status", "active")),
            is_point_in_time_verified=bool(a.get("is_point_in_time_verified", False)),
        )
        actions_by_asset.setdefault(aid, []).append(ev)

    # 10. Reconstruct and adjust individual asset series
    asset_price_series: dict[str, pd.Series] = {}

    for aid in resolved_asset_ids:
        bars = composite_map[aid]
        # Filter dates
        filtered_bars = []
        for b in bars:
            d = date.fromisoformat(b["date"]) if isinstance(b["date"], str) else b["date"]
            if start_d and d < start_d:
                continue
            if end_d and d > end_d:
                continue
            filtered_bars.append(b)

        if not filtered_bars:
            continue

        raw_df = pd.DataFrame(filtered_bars)
        raw_df["date"] = pd.to_datetime(raw_df["date"]).dt.date

        if adjustment_type == "unadjusted":
            # Raw unadjusted close
            s = pd.Series(raw_df["close"].values, index=raw_df["date"].apply(lambda d: d.isoformat()))
            asset_price_series[aid] = s
        else:
            # Deterministic adjustment via adjustments.py
            asset_events = actions_by_asset.get(aid, [])
            if adjustment_type == "split_only":
                asset_events = [
                    ev for ev in asset_events
                    if ev.event_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT)
                ]
                policy = AdjustmentPolicy(adjust_dividends=False)
            else:  # "total"
                policy = AdjustmentPolicy(adjust_dividends=True)

            adj_df, _ = adjust_ohlcv_series(raw_df, asset_events, policy=policy)
            s = pd.Series(adj_df["adj_close"].values, index=raw_df["date"].apply(lambda d: d.isoformat()))
            asset_price_series[aid] = s

    # 11. Synchronize into single price matrix
    if not asset_price_series:
        raise SnapshotValidationError(
            f"No observations remain in snapshot '{snapshot_id}' after date filtering."
        )

    matrix_df = pd.DataFrame(asset_price_series)
    clean_price_df = matrix_df.dropna(how="any").astype(float)
    clean_price_df.sort_index(inplace=True)

    if len(clean_price_df) < min_required_observations:
        raise SnapshotValidationError(
            f"Snapshot '{snapshot_id}' resolved to only {len(clean_price_df)} synchronized observations; "
            f"minimum required is {min_required_observations}."
        )

    # 12. Attach provenance metadata
    provenance_metadata = {
        "snapshot_id": snapshot.id,
        "dataset_id": snapshot.dataset_id,
        "tag": snapshot.tag,
        "snapshot_type": snapshot.snapshot_type,
        "manifest_sha256": snapshot.manifest_sha256,
        "manifest_version": m_version,
        "as_of_date": snapshot.as_of_date.isoformat() if snapshot.as_of_date else None,
        "point_in_time_status": snapshot.point_in_time_status,
        "calendar_version": snapshot.calendar_version,
        "adjustment_policy_version": snapshot.adjustment_policy_version,
        "adjustment_type": adjustment_type,
        "is_frozen": snapshot.is_frozen,
        "verified_replay": True,
        "replayed_at": datetime.now(timezone.utc).isoformat(),
        "total_bars_in_snapshot": snapshot.total_bars_count,
        "replayed_bars_count": len(clean_price_df),
        "replayed_assets": resolved_asset_ids,
        "currency": currency,
    }

    clean_price_df.attrs["snapshot_provenance"] = provenance_metadata

    return clean_price_df, resolved_asset_ids, currency, periods_per_year, provenance_metadata


def get_snapshot_by_id(session: Session, snapshot_id: str) -> DatasetSnapshotModel | None:
    """Retrieves snapshot model by primary key."""
    return session.get(DatasetSnapshotModel, snapshot_id)


def list_dataset_snapshots(
    session: Session,
    dataset_id: str,
    user: UserModel | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DatasetSnapshotModel]:
    """Lists snapshots for a dataset ordered by creation timestamp descending."""
    stmt = (
        select(DatasetSnapshotModel)
        .where(DatasetSnapshotModel.dataset_id == dataset_id)
        .order_by(DatasetSnapshotModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt).all())


def verify_snapshot_integrity(snapshot_id: str, session: Session) -> bool:
    """
    Independently verifies whether a snapshot's frozen payload matches its manifest digest.
    Returns True if verified; raises SnapshotIntegrityError on any tampering or corruption.
    """
    snapshot = session.get(DatasetSnapshotModel, snapshot_id)
    if not snapshot:
        raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' not found.")

    if not snapshot.frozen_payload_json:
        raise SnapshotIntegrityError(f"Snapshot '{snapshot_id}' lacks frozen payload.")

    try:
        frozen_bars, frozen_actions = deserialize_frozen_payload(snapshot.frozen_payload_json)
    except Exception as exc:
        raise SnapshotIntegrityError(
            f"Failed to deserialize frozen payload for snapshot '{snapshot_id}': {exc}"
        ) from exc

    if not frozen_bars:
        raise SnapshotIntegrityError(
            f"Snapshot '{snapshot_id}' frozen payload contains no price bars."
        )

    manifest_meta = snapshot.get_manifest()
    m_version = manifest_meta.get("manifest_version", DEFAULT_MANIFEST_VERSION)

    recomputed = build_dataset_manifest(
        dataset_id=snapshot.dataset_id,
        records=frozen_bars,
        corporate_actions=frozen_actions,
        as_of_date=snapshot.as_of_date,
        calendar_version=snapshot.calendar_version,
        adjustment_policy_version=snapshot.adjustment_policy_version,
        point_in_time_status=snapshot.point_in_time_status,
        manifest_version=m_version,
    )

    if recomputed.manifest_sha256 != snapshot.manifest_sha256:
        raise SnapshotIntegrityError(
            f"Digest mismatch in snapshot '{snapshot_id}': "
            f"Expected {snapshot.manifest_sha256}, computed {recomputed.manifest_sha256}."
        )

    return True
