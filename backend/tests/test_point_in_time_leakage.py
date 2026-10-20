"""
Negative tests and leakage verification for Workstream 31.5 (Strict Point-in-Time Integrity).
Proves that future information and later revisions cannot alter historical decisions.
"""

from datetime import date
import pytest

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


def test_future_announced_corporate_action_cannot_influence_earlier_cutoff():
    """
    Negative Leakage Test 1:
    Event effective on 2024-06-01, announced on 2024-05-15.
    If backtest decision cutoff is 2024-05-01:
    The event MUST NOT be eligible, because it was not known on 2024-05-01.
    """
    ev = CorporateActionEvent(
        event_id="ca_future_split",
        asset_id="XYZ:US",
        ticker="XYZ",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 6, 1),
        announcement_date=date(2024, 5, 15),
        value=2.0,
        currency="USD",
        source="sec_filing",
        is_point_in_time_verified=True,
    )

    cutoff_before_ann = PointInTimeCutoff(as_of_date=date(2024, 5, 1), strict=True)
    eligible, audit = filter_point_in_time_actions([ev], cutoff_before_ann)

    assert len(eligible) == 0
    assert audit.is_certified_pit_safe is True
    assert audit.status == PointInTimeStatus.VERIFIED_PASS
    assert audit.excluded_future_actions_count == 1


def test_action_eligible_only_after_announcement_date():
    """
    Negative Leakage Test 2:
    Same event, but cutoff is 2024-05-20 (after announcement date of 2024-05-15).
    Event MUST now be included in the known information set.
    """
    ev = CorporateActionEvent(
        event_id="ca_future_split",
        asset_id="XYZ:US",
        ticker="XYZ",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 6, 1),
        announcement_date=date(2024, 5, 15),
        value=2.0,
        currency="USD",
        source="sec_filing",
        is_point_in_time_verified=True,
    )

    cutoff_after_ann = PointInTimeCutoff(as_of_date=date(2024, 5, 20), strict=True)
    eligible, audit = filter_point_in_time_actions([ev], cutoff_after_ann)

    assert len(eligible) == 1
    assert eligible[0].event_id == "ca_future_split"
    assert audit.is_certified_pit_safe is True


def test_missing_announcement_date_fails_closed_in_strict_mode():
    """
    Negative Leakage Test 3:
    Event without an announcement date cannot prove absence of lookahead bias.
    Strict PIT workflow MUST fail closed (status FAILED_CLOSED, certified False).
    """
    ev_unverified = CorporateActionEvent(
        event_id="ca_no_ann",
        asset_id="ABC:US",
        ticker="ABC",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 4, 1),
        announcement_date=None,  # Missing announcement date
        value=1.50,
        currency="USD",
        source="unverified_feed",
        is_point_in_time_verified=False,
    )

    cutoff = PointInTimeCutoff(as_of_date=date(2024, 5, 1), strict=True)
    eligible, audit = filter_point_in_time_actions([ev_unverified], cutoff)

    assert len(eligible) == 0  # Excluded from eligible actions
    assert audit.status == PointInTimeStatus.FAILED_CLOSED
    assert audit.is_certified_pit_safe is False
    assert audit.unverified_actions_count == 1
    assert any("Strict PIT verification failed" in r for r in audit.reasons)


def test_legacy_workflow_explicitly_labeled_unverified():
    """
    Negative Leakage Test 4:
    Legacy non-strict workflow processes actions by effective date,
    but is explicitly labeled UNVERIFIED_LEGACY so researchers are never misled.
    """
    ev = CorporateActionEvent(
        event_id="ca_legacy",
        asset_id="ABC:US",
        ticker="ABC",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 4, 1),
        announcement_date=None,
        value=1.50,
        currency="USD",
        source="legacy_feed",
    )

    cutoff_legacy = PointInTimeCutoff(as_of_date=date(2024, 5, 1), strict=False)
    eligible, audit = filter_point_in_time_actions([ev], cutoff_legacy)

    assert len(eligible) == 1
    assert audit.status == PointInTimeStatus.UNVERIFIED_LEGACY
    assert audit.is_certified_pit_safe is False
