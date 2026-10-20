"""
Unit tests for Market Data Quality and Anomaly Controls (Workstream 31.4).
"""

from datetime import date
import pytest

from app.market_data.corporate_actions import CorporateActionEvent, CorporateActionType
from app.market_data.quality import AnomalySeverity, audit_market_data_quality


def test_valid_data_passes_quality_audit():
    bars = [
        {"date": "2024-01-02", "ticker": "AAPL", "market": "US", "currency": "USD", "open": 185.0, "high": 186.0, "low": 184.0, "close": 185.5},
        {"date": "2024-01-03", "ticker": "AAPL", "market": "US", "currency": "USD", "open": 185.5, "high": 187.0, "low": 185.0, "close": 186.2},
    ]
    report = audit_market_data_quality(bars)
    assert report.is_valid is True
    assert report.error_count == 0


def test_ohlc_inversions_flagged_as_errors():
    bars = [
        # High lower than Low
        {"date": "2024-01-02", "ticker": "TEST", "market": "US", "currency": "USD", "open": 100.0, "high": 90.0, "low": 95.0, "close": 98.0},
        # High lower than Close
        {"date": "2024-01-03", "ticker": "TEST", "market": "US", "currency": "USD", "open": 100.0, "high": 102.0, "low": 98.0, "close": 105.0},
        # Low higher than Close
        {"date": "2024-01-04", "ticker": "TEST", "market": "US", "currency": "USD", "open": 100.0, "high": 105.0, "low": 102.0, "close": 99.0},
    ]
    report = audit_market_data_quality(bars)
    assert report.is_valid is False
    assert report.error_count >= 3
    rule_ids = [f.rule_id for f in report.findings]
    assert "DQ_OHLC_INVERSION" in rule_ids


def test_non_positive_or_non_finite_prices():
    bars = [
        {"date": "2024-01-02", "ticker": "BAD", "market": "US", "currency": "USD", "close": 0.0},
        {"date": "2024-01-03", "ticker": "BAD", "market": "US", "currency": "USD", "close": -5.0},
        {"date": "2024-01-04", "ticker": "BAD", "market": "US", "currency": "USD", "close": float("inf")},
    ]
    report = audit_market_data_quality(bars)
    assert report.is_valid is False
    assert any(f.rule_id == "DQ_NON_POSITIVE_PRICE" for f in report.findings)


def test_currency_market_mismatch():
    bars = [
        # US equity with PKR currency
        {"date": "2024-01-02", "ticker": "AAPL", "market": "US", "currency": "PKR", "close": 185.0},
        # PSX equity with USD currency
        {"date": "2024-01-02", "ticker": "OGDC", "market": "PSX", "currency": "USD", "close": 120.0},
    ]
    report = audit_market_data_quality(bars)
    assert report.is_valid is False
    curr_errors = [f for f in report.findings if f.rule_id == "DQ_CURRENCY_MISMATCH"]
    assert len(curr_errors) == 2


def test_stale_series_generates_warning():
    # 12 identical closes
    bars = [
        {"date": f"2024-01-{i:02d}", "ticker": "FLAT", "market": "US", "currency": "USD", "close": 50.0}
        for i in range(2, 16)
    ]
    report = audit_market_data_quality(bars, stale_limit_days=5)
    # Stale series is a WARNING, not a hard invalidation error
    assert any(f.rule_id == "DQ_STALE_SERIES" for f in report.findings)
    assert any(f.severity == AnomalySeverity.WARNING for f in report.findings)


def test_price_jump_discontinuity_with_and_without_corporate_action():
    # Case 1: 50% price drop from 100 to 50 without corporate action
    bars_unexplained = [
        {"date": "2024-01-02", "ticker": "JUMP", "market": "US", "currency": "USD", "close": 100.0},
        {"date": "2024-01-03", "ticker": "JUMP", "market": "US", "currency": "USD", "close": 50.0},
    ]
    rep_unexplained = audit_market_data_quality(bars_unexplained, corporate_actions=None)
    assert any(f.rule_id == "DQ_PRICE_DISCONTINUITY" for f in rep_unexplained.findings)

    # Case 2: Same 50% drop, but with accompanying active 2:1 stock split record
    split_ev = CorporateActionEvent(
        event_id="ca_legit_split",
        asset_id="JUMP:US",
        ticker="JUMP",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 1, 3),
        value=2.0,
        currency="USD",
        source="test",
    )
    rep_explained = audit_market_data_quality(bars_unexplained, corporate_actions=[split_ev])
    # Because corporate action exists on 2024-01-03, NO unexplained discontinuity warning is triggered!
    assert not any(f.rule_id == "DQ_PRICE_DISCONTINUITY" for f in rep_explained.findings)
