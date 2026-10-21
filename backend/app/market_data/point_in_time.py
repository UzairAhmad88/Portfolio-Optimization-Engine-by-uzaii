"""
Strict point-in-time (PIT) information availability and anti-leakage module.

Workstream 31.5:
- Enforces explicit temporal cutoffs preventing look-ahead bias in quant research and backtesting.
- Distinguishes:
  * Economic effective date
  * Announcement / publication date
  * Ingestion / availability timestamp
- Fail-closed semantics: If strict PIT verification is requested and required announcement provenance is missing,
  the workflow explicitly fails closed or marks the dataset unverified.
- Prevents future announcements or post-hoc corrections from leaking into historical simulation decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from app.market_data.corporate_actions import CorporateActionEvent, CorporateActionStatus


class PointInTimeStatus(str, Enum):
    VERIFIED_PASS = "verified_pass"
    UNVERIFIED_LEGACY = "unverified_legacy"
    FAILED_CLOSED = "failed_closed"


@dataclass(frozen=True)
class PointInTimeCutoff:
    """
    Temporal cutoff specification for historical simulation or research query.
    """
    as_of_date: date
    as_of_timestamp: datetime | None = None
    strict: bool = True
    policy_version: str = "2026.1"


@dataclass(frozen=True)
class PointInTimeAuditResult:
    """
    Audit result certifying whether a dataset or research run satisfies point-in-time integrity.
    """
    status: PointInTimeStatus
    as_of_date: str
    is_certified_pit_safe: bool
    reasons: list[str]
    examined_actions_count: int
    eligible_actions_count: int
    excluded_future_actions_count: int
    unverified_actions_count: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def filter_point_in_time_actions(
    actions: list[CorporateActionEvent],
    cutoff: PointInTimeCutoff,
) -> tuple[list[CorporateActionEvent], PointInTimeAuditResult]:
    """
    Filters corporate action events according to the specified point-in-time cutoff.

    In strict mode:
    - Events announced AFTER cutoff.as_of_date are excluded (future leakage prevented).
    - Events lacking an announcement_date cannot be certified as PIT safe; they trigger fail-closed or unverified status.
    - Post-hoc corrections/supersessions announced after cutoff are ignored in favor of the active state at cutoff.

    In legacy (non-strict) mode:
    - Events are filtered purely on effective_date <= cutoff.as_of_date.
    - Status is marked UNVERIFIED_LEGACY.
    """
    eligible: list[CorporateActionEvent] = []
    reasons: list[str] = []

    examined = len(actions)
    future_count = 0
    unverified_count = 0

    as_of_d = cutoff.as_of_date

    candidates: list[CorporateActionEvent] = []

    for ev in actions:
        if ev.status == CorporateActionStatus.CANCELLED:
            # If cancellation was announced on or prior to cutoff, it is cancelled as of cutoff
            if cutoff.strict and ev.announcement_date and ev.announcement_date <= as_of_d:
                continue
            elif not cutoff.strict and ev.effective_date <= as_of_d:
                continue

        if cutoff.strict:
            if ev.announcement_date is None:
                unverified_count += 1
                reasons.append(
                    f"Event '{ev.event_id}' ({ev.ticker}:{ev.market}) lacks authoritative announcement date."
                )
                continue

            if ev.announcement_date > as_of_d:
                # Announced in the future relative to cutoff: exclude to prevent leakage!
                future_count += 1
                continue

            # If announcement_date <= as_of_d, information was known at decision time!
            candidates.append(ev)

        else:
            # Legacy non-strict mode: check effective_date
            if ev.effective_date <= as_of_d:
                candidates.append(ev)
            else:
                future_count += 1

    # Revision resolution: if multiple events share (asset_id, event_type, effective_date),
    # select the latest revision known as of the cutoff date to prevent double-counting
    # and guarantee that future corrections do not distort the view known at earlier cutoffs.
    grouped_by_key: dict[tuple[str, str, date], list[CorporateActionEvent]] = {}
    for ev in candidates:
        key = (ev.asset_id, ev.event_type.value, ev.effective_date)
        grouped_by_key.setdefault(key, []).append(ev)

    eligible: list[CorporateActionEvent] = []
    for key, ev_list in grouped_by_key.items():
        if len(ev_list) == 1:
            eligible.append(ev_list[0])
        else:
            ev_list.sort(
                key=lambda x: (
                    x.announcement_date or x.effective_date,
                    x.created_at,
                    x.revision_id or "",
                )
            )
            eligible.append(ev_list[-1])

    if cutoff.strict:
        if unverified_count > 0:
            status = PointInTimeStatus.FAILED_CLOSED
            is_certified = False
            reasons.append(
                f"Strict PIT verification failed: {unverified_count} event(s) lack required announcement timestamp provenance."
            )
        else:
            status = PointInTimeStatus.VERIFIED_PASS
            is_certified = True
    else:
        status = PointInTimeStatus.UNVERIFIED_LEGACY
        is_certified = False
        reasons.append(
            "Workflow executed in legacy non-strict mode; corporate actions filtered by effective date without announcement verification."
        )

    # Sort eligible events by effective_date
    eligible.sort(key=lambda e: (e.effective_date, e.event_id))

    audit = PointInTimeAuditResult(
        status=status,
        as_of_date=as_of_d.isoformat(),
        is_certified_pit_safe=is_certified,
        reasons=reasons,
        examined_actions_count=examined,
        eligible_actions_count=len(eligible),
        excluded_future_actions_count=future_count,
        unverified_actions_count=unverified_count,
        details={
            "strict_mode": cutoff.strict,
            "policy_version": cutoff.policy_version,
        },
    )

    return eligible, audit
