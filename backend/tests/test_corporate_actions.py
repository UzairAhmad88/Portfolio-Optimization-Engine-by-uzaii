"""
Unit tests for Corporate Action Event Model and Ledger (Workstream 31.2).
"""

from datetime import date
import pytest

from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionLedger,
    CorporateActionStatus,
    CorporateActionType,
    SymbolMappingRegistry,
    create_deterministic_event_id,
)


def test_corporate_action_event_validation_success():
    event = CorporateActionEvent(
        event_id="ca_test_001",
        asset_id="AAPL:US",
        ticker="AAPL",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2020, 8, 31),
        announcement_date=date(2020, 7, 30),
        value=4.0,  # 4:1 split
        currency="USD",
        source="sec_edgar_10q",
        is_point_in_time_verified=True,
    )
    errors = event.validate()
    assert errors == []
    d = event.to_dict()
    assert d["event_type"] == "stock_split"
    assert d["status"] == "active"
    assert d["effective_date"] == "2020-08-31"


def test_corporate_action_event_validation_failure():
    # Negative value
    ev_neg = CorporateActionEvent(
        event_id="ca_bad_1",
        asset_id="TEST:US",
        ticker="TEST",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 1, 10),
        value=-0.5,
        currency="USD",
        source="test",
    )
    assert any("strictly positive" in err for err in ev_neg.validate())

    # Announcement date after effective date
    ev_bad_date = CorporateActionEvent(
        event_id="ca_bad_2",
        asset_id="TEST:US",
        ticker="TEST",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 1, 10),
        announcement_date=date(2024, 1, 15),
        value=2.0,
        currency="USD",
        source="test",
    )
    assert any("Announcement date" in err for err in ev_bad_date.validate())


def test_ledger_duplicate_deduplication():
    ledger = CorporateActionLedger()
    ev1 = CorporateActionEvent(
        event_id="ca_dup_1",
        asset_id="MSFT:US",
        ticker="MSFT",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 2, 14),
        announcement_date=date(2023, 11, 28),
        value=0.75,
        currency="USD",
        source="vendor_a",
    )
    ev2 = CorporateActionEvent(
        event_id="ca_dup_2",
        asset_id="MSFT:US",
        ticker="MSFT",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 2, 14),
        announcement_date=date(2023, 11, 28),
        value=0.75,
        currency="USD",
        source="vendor_b",
    )

    stored1, action1 = ledger.add_event(ev1)
    assert action1 == "inserted"

    stored2, action2 = ledger.add_event(ev2)
    assert action2 == "deduplicated_identical"
    assert stored2.event_id == "ca_dup_1"


def test_ledger_revision_supersession():
    ledger = CorporateActionLedger()
    ev_orig = CorporateActionEvent(
        event_id="ca_rev_1",
        asset_id="OGDC:PSX",
        ticker="OGDC",
        market="PSX",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 3, 20),
        announcement_date=date(2024, 2, 20),
        value=2.50,
        currency="PKR",
        source="psx_notice",
        revision_id="rev_1",
    )
    ev_corrected = CorporateActionEvent(
        event_id="ca_rev_2",
        asset_id="OGDC:PSX",
        ticker="OGDC",
        market="PSX",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 3, 20),
        announcement_date=date(2024, 2, 21),
        value=2.75,  # Company corrected dividend amount
        currency="PKR",
        source="psx_corrigendum",
        revision_id="rev_2",
    )

    ledger.add_event(ev_orig)
    stored2, action2 = ledger.add_event(ev_corrected)
    assert action2 == "superseded_previous"

    # Query active events
    active_events = ledger.get_events_for_asset("OGDC:PSX")
    assert len(active_events) == 1
    assert active_events[0].event_id == "ca_rev_2"
    assert active_events[0].value == 2.75


def test_point_in_time_filtering_prevents_leakage():
    ledger = CorporateActionLedger()
    # Event announced on 2024-05-15, effective on 2024-06-01
    ev = CorporateActionEvent(
        event_id="ca_nvda_split",
        asset_id="NVDA:US",
        ticker="NVDA",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        announcement_date=date(2024, 5, 22),
        effective_date=date(2024, 6, 10),
        value=10.0,
        currency="USD",
        source="sec_8k",
        is_point_in_time_verified=True,
    )
    ledger.add_event(ev)

    # 1. As of 2024-05-01 (before announcement): Strict PIT MUST NOT return the split
    events_before_ann = ledger.get_events_for_asset(
        asset_id="NVDA:US",
        as_of_date=date(2024, 5, 1),
        strict_pit=True,
    )
    assert len(events_before_ann) == 0  # Lookahead leakage prevented!

    # 2. As of 2024-05-25 (after announcement, before effective): strict PIT returns event
    events_after_ann = ledger.get_events_for_asset(
        asset_id="NVDA:US",
        as_of_date=date(2024, 5, 25),
        strict_pit=True,
    )
    assert len(events_after_ann) == 1
    assert events_after_ann[0].value == 10.0

    # 3. Unverified event lacking announcement date fails closed under strict_pit
    ev_unverified = CorporateActionEvent(
        event_id="ca_unverified",
        asset_id="XYZ:US",
        ticker="XYZ",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 4, 1),
        announcement_date=None,  # Missing announcement date
        value=1.0,
        currency="USD",
        source="unverified_source",
        is_point_in_time_verified=False,
    )
    ledger.add_event(ev_unverified)

    # In strict PIT mode, event lacking announcement date is excluded
    strict_res = ledger.get_events_for_asset("XYZ:US", as_of_date=date(2024, 5, 1), strict_pit=True)
    assert len(strict_res) == 0

    # In legacy non-strict mode, returns event based on effective_date
    legacy_res = ledger.get_events_for_asset("XYZ:US", as_of_date=date(2024, 5, 1), strict_pit=False)
    assert len(legacy_res) == 1


def test_symbol_mapping_registry():
    registry = SymbolMappingRegistry()
    # FB was renamed to META on 2022-06-09
    registry.register(
        ticker="FB",
        asset_id="META_INC_STABLE_ID",
        market="US",
        start_date=date(2012, 5, 18),
        end_date=date(2022, 6, 8),
    )
    registry.register(
        ticker="META",
        asset_id="META_INC_STABLE_ID",
        market="US",
        start_date=date(2022, 6, 9),
        end_date=None,
    )

    # Date in 2020 should resolve FB to META_INC_STABLE_ID
    assert registry.resolve_asset_id("FB", "US", date(2020, 1, 15)) == "META_INC_STABLE_ID"

    # Date in 2023 should resolve META to the SAME economic asset ID!
    assert registry.resolve_asset_id("META", "US", date(2023, 1, 15)) == "META_INC_STABLE_ID"

    # Default fallback for unknown ticker
    assert registry.resolve_asset_id("AAPL", "US", date(2024, 1, 1)) == "AAPL:US"


def test_deterministic_event_id():
    id1 = create_deterministic_event_id("AAPL:US", CorporateActionType.STOCK_SPLIT, date(2020, 8, 31), "sec")
    id2 = create_deterministic_event_id("AAPL:US", CorporateActionType.STOCK_SPLIT, date(2020, 8, 31), "sec")
    assert id1 == id2
    assert id1.startswith("ca_")
