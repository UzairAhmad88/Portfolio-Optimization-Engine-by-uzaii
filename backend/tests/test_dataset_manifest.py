"""
Unit tests for Stage 32 Canonical Observation Manifest Engine.

Workstream 32.1 & 32.3:
- Verifies deterministic Merkle composite hashing.
- Verifies permutation invariance: row-order shuffling produces identical digests.
- Verifies mutation sensitivity: any price bar or corporate action alteration changes digest.
- Verifies policy version sealing.
"""

from datetime import date
import random

from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)
from app.market_data.manifest import (
    build_dataset_manifest,
    compute_corporate_actions_digest,
    compute_price_bars_digest,
)


def _sample_records():
    return [
        {
            "ticker": "AAPL",
            "market": "US",
            "date": "2024-01-02",
            "open": 187.15,
            "high": 188.44,
            "low": 183.89,
            "close": 185.64,
            "adjusted_close": 185.64,
            "volume": 82488700,
            "currency": "USD",
        },
        {
            "ticker": "AAPL",
            "market": "US",
            "date": "2024-01-03",
            "open": 184.22,
            "high": 185.88,
            "low": 183.43,
            "close": 184.25,
            "adjusted_close": 184.25,
            "volume": 58414500,
            "currency": "USD",
        },
        {
            "ticker": "MSFT",
            "market": "US",
            "date": "2024-01-02",
            "open": 373.86,
            "high": 375.90,
            "low": 369.84,
            "close": 370.87,
            "adjusted_close": 370.87,
            "volume": 25258600,
            "currency": "USD",
        },
        {
            "ticker": "MSFT",
            "market": "US",
            "date": "2024-01-03",
            "open": 369.01,
            "high": 373.26,
            "low": 368.51,
            "close": 370.60,
            "adjusted_close": 370.60,
            "volume": 23083500,
            "currency": "USD",
        },
    ]


def _sample_actions():
    return [
        CorporateActionEvent(
            event_id="ca_aapl_split_2024",
            asset_id="AAPL:US",
            ticker="AAPL",
            market="US",
            event_type=CorporateActionType.STOCK_SPLIT,
            effective_date=date(2024, 6, 10),
            announcement_date=date(2024, 5, 2),
            value=2.0,
            currency="USD",
            source="SEC_8K",
            status=CorporateActionStatus.ACTIVE,
        ),
        CorporateActionEvent(
            event_id="ca_msft_div_2024",
            asset_id="MSFT:US",
            ticker="MSFT",
            market="US",
            event_type=CorporateActionType.CASH_DIVIDEND,
            effective_date=date(2024, 5, 15),
            announcement_date=date(2024, 4, 25),
            value=0.75,
            currency="USD",
            source="PR_NEWSWIRE",
            status=CorporateActionStatus.ACTIVE,
        ),
    ]


def test_manifest_determinism():
    records = _sample_records()
    actions = _sample_actions()

    m1 = build_dataset_manifest("ds_test_1", records, actions, as_of_date=date(2024, 6, 1))
    m2 = build_dataset_manifest("ds_test_1", records, actions, as_of_date=date(2024, 6, 1))

    assert m1.manifest_sha256 == m2.manifest_sha256
    assert m1.bars_digest == m2.bars_digest
    assert m1.actions_digest == m2.actions_digest
    assert m1.total_bars == 4
    assert m1.total_actions == 2


def test_manifest_permutation_invariance():
    """
    Shuffling the input row order must produce an IDENTICAL bars_digest and manifest_sha256.
    """
    records1 = _sample_records()
    records2 = list(records1)
    random.seed(42)
    random.shuffle(records2)

    # Ensure records2 is actually in a different order
    assert records1 != records2

    m1 = build_dataset_manifest("ds_test_1", records1, _sample_actions())
    m2 = build_dataset_manifest("ds_test_1", records2, _sample_actions())

    assert m1.bars_digest == m2.bars_digest
    assert m1.manifest_sha256 == m2.manifest_sha256


def test_manifest_price_mutation_sensitivity():
    """
    Any alteration to a single price bar must alter bars_digest and manifest_sha256.
    """
    records1 = _sample_records()
    records2 = [dict(r) for r in records1]
    # Mutate 1 close price by 1 cent
    records2[0]["close"] = 185.65

    m1 = build_dataset_manifest("ds_test_1", records1)
    m2 = build_dataset_manifest("ds_test_1", records2)

    assert m1.bars_digest != m2.bars_digest
    assert m1.manifest_sha256 != m2.manifest_sha256


def test_manifest_corporate_action_mutation_sensitivity():
    """
    Any alteration to a corporate action must alter actions_digest and manifest_sha256.
    """
    records = _sample_records()
    actions1 = _sample_actions()
    actions2 = [
        CorporateActionEvent(
            event_id=actions1[0].event_id,
            asset_id=actions1[0].asset_id,
            ticker=actions1[0].ticker,
            market=actions1[0].market,
            event_type=actions1[0].event_type,
            effective_date=actions1[0].effective_date,
            announcement_date=actions1[0].announcement_date,
            value=3.0,  # 3:1 split instead of 2:1
            currency=actions1[0].currency,
            source=actions1[0].source,
            status=actions1[0].status,
        ),
        actions1[1],
    ]

    m1 = build_dataset_manifest("ds_test_1", records, actions1)
    m2 = build_dataset_manifest("ds_test_1", records, actions2)

    assert m1.bars_digest == m2.bars_digest  # Price bars unchanged
    assert m1.actions_digest != m2.actions_digest
    assert m1.manifest_sha256 != m2.manifest_sha256


def test_manifest_policy_and_cutoff_sealing():
    """
    Altering calendar version, adjustment policy, or cutoff date must update manifest_sha256.
    """
    records = _sample_records()

    m_base = build_dataset_manifest("ds_test_1", records, calendar_version="US-NYSE-2026.1")
    m_cal_change = build_dataset_manifest("ds_test_1", records, calendar_version="US-NYSE-2026.2")
    m_policy_change = build_dataset_manifest("ds_test_1", records, adjustment_policy_version="2026.2")
    m_cutoff_change = build_dataset_manifest("ds_test_1", records, as_of_date=date(2024, 5, 1))

    assert m_base.manifest_sha256 != m_cal_change.manifest_sha256
    assert m_base.manifest_sha256 != m_policy_change.manifest_sha256
    assert m_base.manifest_sha256 != m_cutoff_change.manifest_sha256


def test_manifest_serialization():
    m = build_dataset_manifest("ds_test_1", _sample_records(), _sample_actions())
    json_str = m.to_json()
    assert "DATASET_MANIFEST" not in json_str  # Internal payload not exposed raw
    assert m.manifest_sha256 in json_str
    assert "AAPL:US" in json_str
    assert m.total_bars == 4
    assert m.total_actions == 2
