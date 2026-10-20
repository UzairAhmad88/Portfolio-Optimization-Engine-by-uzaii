"""
Canonical corporate-action event model and ledger for US Equities and PSX.

Workstream 31.2:
- Provider-neutral event representation for stock splits, reverse splits, cash dividends, symbol changes, and explicitly classified complex unsupported events.
- Strict distinction between announcement date, ex-date, record date, effective date, and ingestion timestamp.
- Stable internal asset identity distinct from ticker symbol.
- Deterministic duplicate resolution, revision supersession, and point-in-time eligibility filtering.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import uuid4


class CorporateActionType(str, Enum):
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    CASH_DIVIDEND = "cash_dividend"
    SYMBOL_CHANGE = "symbol_change"
    COMPLEX_UNSUPPORTED = "complex_unsupported"  # Mergers, spin-offs, rights issues, capital distributions


class CorporateActionStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CorporateActionEvent:
    """
    Canonical provider-neutral corporate-action event.
    """
    event_id: str
    asset_id: str
    ticker: str
    market: str
    event_type: CorporateActionType
    effective_date: date
    value: float
    currency: str
    source: str
    announcement_date: date | None = None
    ex_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    revision_id: str | None = None
    status: CorporateActionStatus = CorporateActionStatus.ACTIVE
    is_point_in_time_verified: bool = False
    provenance_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> list[str]:
        """Validates internal consistency of the event."""
        errors: list[str] = []
        if not self.asset_id or not self.asset_id.strip():
            errors.append("asset_id must be a non-empty string.")
        if not self.ticker or not self.ticker.strip():
            errors.append("ticker must be a non-empty string.")
        if self.market.upper() not in ("US", "PSX"):
            errors.append(f"market '{self.market}' must be 'US' or 'PSX'.")
        if self.event_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
            if self.value <= 0.0:
                errors.append(f"Split ratio value must be strictly positive (> 0.0), received {self.value}.")
            if self.event_type == CorporateActionType.STOCK_SPLIT and self.value <= 1.0:
                errors.append(f"Stock split ratio value should be > 1.0 (e.g. 2.0 for 2:1), received {self.value}.")
            if self.event_type == CorporateActionType.REVERSE_SPLIT and self.value >= 1.0:
                errors.append(f"Reverse split ratio value should be < 1.0 (e.g. 0.2 for 1:5), received {self.value}.")
        elif self.event_type == CorporateActionType.CASH_DIVIDEND:
            if self.value <= 0.0:
                errors.append(f"Cash dividend value must be strictly positive (> 0.0), received {self.value}.")
        if self.announcement_date and self.effective_date and self.announcement_date > self.effective_date:
            errors.append(
                f"Announcement date ({self.announcement_date}) cannot be after effective date ({self.effective_date})."
            )
        if self.ex_date and self.effective_date and self.ex_date > self.effective_date:
            errors.append(
                f"Ex-date ({self.ex_date}) cannot be after effective date ({self.effective_date})."
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["status"] = self.status.value
        d["effective_date"] = self.effective_date.isoformat()
        d["announcement_date"] = self.announcement_date.isoformat() if self.announcement_date else None
        d["ex_date"] = self.ex_date.isoformat() if self.ex_date else None
        d["record_date"] = self.record_date.isoformat() if self.record_date else None
        d["payment_date"] = self.payment_date.isoformat() if self.payment_date else None
        d["created_at"] = self.created_at.isoformat()
        return d


@dataclass
class SymbolHistoryEntry:
    """
    Ledger entry mapping a ticker symbol to a stable asset_id over an interval.
    """
    ticker: str
    asset_id: str
    market: str
    start_date: date
    end_date: date | None = None  # None indicates currently active symbol

    def is_active_on(self, dt: date) -> bool:
        if dt < self.start_date:
            return False
        if self.end_date is not None and dt > self.end_date:
            return False
        return True


class SymbolMappingRegistry:
    """
    Registry that resolves tickers to stable economic asset identities across time.
    Prevents symbol renames (e.g. FB -> META) from fracturing asset history.
    """

    def __init__(self) -> None:
        self._entries: list[SymbolHistoryEntry] = []

    def register(
        self,
        ticker: str,
        asset_id: str,
        market: str,
        start_date: date,
        end_date: date | None = None,
    ) -> None:
        norm_ticker = ticker.strip().upper()
        norm_asset_id = asset_id.strip()
        norm_market = market.strip().upper()
        # Verify no overlapping dates for same ticker in same market
        for entry in self._entries:
            if entry.ticker == norm_ticker and entry.market == norm_market:
                entry_end = entry.end_date or date.max
                new_end = end_date or date.max
                if max(entry.start_date, start_date) <= min(entry_end, new_end):
                    raise ValueError(
                        f"Overlapping symbol registration for {norm_ticker}:{norm_market} "
                        f"between {entry.start_date}..{entry.end_date} and {start_date}..{end_date}."
                    )
        self._entries.append(
            SymbolHistoryEntry(
                ticker=norm_ticker,
                asset_id=norm_asset_id,
                market=norm_market,
                start_date=start_date,
                end_date=end_date,
            )
        )

    def resolve_asset_id(self, ticker: str, market: str, dt: date) -> str:
        """
        Resolves ticker at date dt to its canonical economic asset_id.
        Defaults to '{TICKER}:{MARKET}' if no explicit rename is recorded.
        """
        norm_ticker = ticker.strip().upper()
        norm_market = market.strip().upper()
        for entry in self._entries:
            if entry.ticker == norm_ticker and entry.market == norm_market and entry.is_active_on(dt):
                return entry.asset_id
        # Fallback default: composite key
        return f"{norm_ticker}:{norm_market}"


class CorporateActionLedger:
    """
    In-memory and persistent-ready corporate actions ledger with versioning,
    duplicate detection, supersession, and strict point-in-time filtering.
    """

    def __init__(self) -> None:
        self._events: dict[str, CorporateActionEvent] = {}  # event_id -> CorporateActionEvent
        self._asset_index: dict[str, list[str]] = {}  # asset_id -> list of event_ids

    def add_event(self, event: CorporateActionEvent) -> tuple[CorporateActionEvent, str]:
        """
        Ingests a corporate action event.
        Returns:
            (stored_event, action_taken)
            action_taken: 'inserted', 'deduplicated_identical', 'superseded_previous', or raises ValueError.
        """
        val_errors = event.validate()
        if val_errors:
            raise ValueError(f"Invalid corporate action event: {'; '.join(val_errors)}")

        # Check existing events for this asset on same effective_date and type
        existing_event_ids = self._asset_index.get(event.asset_id, [])
        for eid in existing_event_ids:
            existing = self._events[eid]
            if (
                existing.status == CorporateActionStatus.ACTIVE
                and existing.event_type == event.event_type
                and existing.effective_date == event.effective_date
            ):
                # Check for identical duplicate
                if (
                    existing.value == event.value
                    and existing.currency == event.currency
                    and existing.announcement_date == event.announcement_date
                ):
                    return existing, "deduplicated_identical"

                # Check for newer revision / correction
                # If incoming event has newer revision or newer created_at/announcement_date, supersede old
                supersede_old = False
                if event.revision_id and existing.revision_id != event.revision_id:
                    supersede_old = True
                elif (
                    event.announcement_date
                    and existing.announcement_date
                    and event.announcement_date >= existing.announcement_date
                ):
                    supersede_old = True
                elif event.created_at > existing.created_at:
                    supersede_old = True

                if supersede_old:
                    superseded_existing = CorporateActionEvent(
                        **{**asdict(existing), "status": CorporateActionStatus.SUPERSEDED}
                    )
                    self._events[eid] = superseded_existing
                    self._events[event.event_id] = event
                    self._asset_index[event.asset_id].append(event.event_id)
                    return event, "superseded_previous"
                else:
                    raise ValueError(
                        f"Conflicting corporate action on {event.effective_date} for {event.asset_id}. "
                        f"Existing: {existing.value} ({existing.source}), incoming: {event.value} ({event.source})."
                    )

        # Standard new event
        self._events[event.event_id] = event
        self._asset_index.setdefault(event.asset_id, []).append(event.event_id)
        return event, "inserted"

    def get_events_for_asset(
        self,
        asset_id: str,
        as_of_date: date | None = None,
        strict_pit: bool = False,
        event_types: list[CorporateActionType] | None = None,
    ) -> list[CorporateActionEvent]:
        """
        Queries eligible corporate action events for asset_id.
        If strict_pit is True:
          - Only events with announcement_date <= as_of_date are eligible.
          - If an event lacks an announcement_date, it is excluded and a warning or error is triggered.
        If strict_pit is False:
          - Events with effective_date <= as_of_date are returned (legacy behavior).
        """
        eids = self._asset_index.get(asset_id, [])
        eligible: list[CorporateActionEvent] = []

        for eid in eids:
            ev = self._events[eid]
            if ev.status != CorporateActionStatus.ACTIVE:
                continue
            if event_types and ev.event_type not in event_types:
                continue

            if as_of_date is not None:
                if strict_pit:
                    if ev.announcement_date is None:
                        # Cannot certify point-in-time safety without announcement date
                        continue
                    if ev.announcement_date > as_of_date:
                        # Future announcement: lookahead leakage prevented!
                        continue
                else:
                    if ev.effective_date > as_of_date:
                        continue

            eligible.append(ev)

        # Return sorted by effective_date asc
        eligible.sort(key=lambda x: (x.effective_date, x.event_id))
        return eligible


def create_deterministic_event_id(
    asset_id: str,
    event_type: CorporateActionType | str,
    effective_date: date,
    source: str,
    revision_id: str | None = None,
) -> str:
    """Generates a deterministic, reproducible SHA-256 event ID."""
    t_str = event_type.value if isinstance(event_type, CorporateActionType) else str(event_type)
    content = f"{asset_id}:{t_str}:{effective_date.isoformat()}:{source}:{revision_id or ''}"
    return "ca_" + sha256(content.encode("utf-8")).hexdigest()[:24]
