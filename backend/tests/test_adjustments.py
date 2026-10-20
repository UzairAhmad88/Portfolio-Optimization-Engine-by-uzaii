"""
Numerical test fixtures and deterministic validation for Workstream 31.3 (Adjustments & Returns).
All fixtures feature independently hand-calculated expected values.
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from app.db.session import get_db_session
from app.market_data import repository
from app.market_data.adjustments import (
    ADJUSTMENT_POLICY_VERSION,
    AdjustmentPolicy,
    adjust_ohlcv_series,
    calculate_discrete_returns,
    calculate_split_and_dividend_factors,
)
from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)


def test_forward_split_2_for_1_fixture():
    """
    Fixture 1: 2-for-1 Forward Split (k = 2.0)
    Day 1 (2024-01-02): Close = $100.00, Volume = 1,000,000
    Day 2 (2024-01-03): Ex-date for 2:1 split, Close = $50.00, Volume = 2,100,000

    Hand calculation:
    - Split multiplier for Day 1: 1 / 2.0 = 0.50
    - Day 1 adjusted close: 100.00 * 0.50 = $50.00
    - Day 2 adjusted close: 50.00 * 1.00 = $50.00
    - Day 1 adjusted volume: 1,000,000 / 0.50 = 2,000,000 shares
    - Price return on Day 2: (50.00 - 100.00/2.0) / (100.00/2.0) = 0.00%
    """
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    raw_df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 50.0],
        "open": [99.0, 50.5],
        "volume": [1_000_000.0, 2_100_000.0],
    })
    split_event = CorporateActionEvent(
        event_id="ca_split_2_1",
        asset_id="TEST:US",
        ticker="TEST",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 1, 3),
        value=2.0,
        currency="USD",
        source="test_fixture",
    )

    adj_df, factors_df = adjust_ohlcv_series(raw_df, [split_event])

    # Check factors
    assert pytest.approx(factors_df.loc[date(2024, 1, 2), "split_factor"], 1e-6) == 0.50
    assert pytest.approx(factors_df.loc[date(2024, 1, 3), "split_factor"], 1e-6) == 1.00

    # Check adjusted close
    assert pytest.approx(adj_df.loc[0, "adj_close"], 1e-6) == 50.00
    assert pytest.approx(adj_df.loc[1, "adj_close"], 1e-6) == 50.00

    # Check adjusted volume
    assert pytest.approx(adj_df.loc[0, "adj_volume"], 1e-6) == 2_000_000.0

    # Check discrete returns
    ret_price = calculate_discrete_returns(raw_df, [split_event], return_type="price")
    assert np.isnan(ret_price.iloc[0])
    assert pytest.approx(ret_price.iloc[1], 1e-6) == 0.00  # Exactly 0.00% economic return


def test_reverse_split_1_for_5_fixture():
    """
    Fixture 2: 1-for-5 Reverse Split (k = 0.2)
    Day 1 (2024-02-01): Close = $10.00
    Day 2 (2024-02-02): Ex-date for 1:5 reverse split, Close = $50.00

    Hand calculation:
    - Split multiplier for Day 1: 1 / 0.2 = 5.0
    - Day 1 adjusted close: 10.00 * 5.0 = $50.00
    - Day 2 adjusted close: 50.00 * 1.0 = $50.00
    - Price return on Day 2: (50.00 - 10.00/0.2) / (10.00/0.2) = 0.00%
    """
    dates = [date(2024, 2, 1), date(2024, 2, 2)]
    raw_df = pd.DataFrame({
        "date": dates,
        "close": [10.0, 50.0],
    })
    rev_event = CorporateActionEvent(
        event_id="ca_rev_1_5",
        asset_id="REV:US",
        ticker="REV",
        market="US",
        event_type=CorporateActionType.REVERSE_SPLIT,
        effective_date=date(2024, 2, 2),
        value=0.2,
        currency="USD",
        source="test_fixture",
    )

    adj_df, factors_df = adjust_ohlcv_series(raw_df, [rev_event])
    assert pytest.approx(factors_df.loc[date(2024, 2, 1), "split_factor"], 1e-6) == 5.0
    assert pytest.approx(adj_df.loc[0, "adj_close"], 1e-6) == 50.00
    assert pytest.approx(adj_df.loc[1, "adj_close"], 1e-6) == 50.00

    ret_price = calculate_discrete_returns(raw_df, [rev_event], return_type="price")
    assert pytest.approx(ret_price.iloc[1], 1e-6) == 0.00


def test_cash_dividend_price_vs_total_return_fixture():
    """
    Fixture 3: Cash Dividend ($2.00)
    Day 1 (2024-03-01): Close = $100.00
    Day 2 (2024-03-04): Ex-dividend date, Close = $98.00, Div = $2.00

    Hand calculation:
    - Prior close = $100.00
    - CRSP dividend factor for Day 1: 1 - (2.00 / 100.00) = 0.98
    - Day 1 adjusted close: 100.00 * 0.98 = $98.00
    - Price return on Day 2: (98.00 - 100.00) / 100.00 = -2.00%
    - Total return on Day 2: (98.00 + 2.00 - 100.00) / 100.00 = 0.00%
    """
    dates = [date(2024, 3, 1), date(2024, 3, 4)]
    raw_df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 98.0],
    })
    div_event = CorporateActionEvent(
        event_id="ca_div_2",
        asset_id="DIV:US",
        ticker="DIV",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 3, 4),
        value=2.00,
        currency="USD",
        source="test_fixture",
    )

    adj_df, factors_df = adjust_ohlcv_series(raw_df, [div_event])
    assert pytest.approx(factors_df.loc[date(2024, 3, 1), "dividend_factor"], 1e-6) == 0.98
    assert pytest.approx(adj_df.loc[0, "adj_close"], 1e-6) == 98.00
    assert pytest.approx(adj_df.loc[1, "adj_close"], 1e-6) == 98.00

    ret_price = calculate_discrete_returns(raw_df, [div_event], return_type="price")
    ret_total = calculate_discrete_returns(raw_df, [div_event], return_type="total")

    assert pytest.approx(ret_price.iloc[1], 1e-6) == -0.02  # -2.00% price return
    assert pytest.approx(ret_total.iloc[1], 1e-6) == 0.00   # 0.00% total return (dividend reinvested)


def test_combined_dividend_and_split_fixture():
    """
    Fixture 4: Dividend then Forward Split
    Day 1 (2024-04-01): Close = $100.00
    Day 2 (2024-04-02): Ex-dividend $2.00, Close = $98.00
    Day 3 (2024-04-03): Ex-split 2:1, Close = $49.00

    Hand calculation:
    - Day 2 dividend: factor = 1 - 2/100 = 0.98 applied to Day 1
    - Day 3 split (2:1): split factor 0.50 applied to Day 1 and Day 2
    - Combined factors:
      * Day 1 total factor = 0.98 * 0.50 = 0.49 -> Adj close = 100 * 0.49 = $49.00
      * Day 2 total factor = 1.00 * 0.50 = 0.50 -> Adj close = 98 * 0.50 = $49.00
      * Day 3 total factor = 1.00 * 1.00 = 1.00 -> Adj close = 49 * 1.00 = $49.00
    - Total returns: Day 2 = 0.00%, Day 3 = 0.00%.
    """
    dates = [date(2024, 4, 1), date(2024, 4, 2), date(2024, 4, 3)]
    raw_df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 98.0, 49.0],
    })
    div_ev = CorporateActionEvent(
        event_id="ca_comb_div",
        asset_id="COMB:US",
        ticker="COMB",
        market="US",
        event_type=CorporateActionType.CASH_DIVIDEND,
        effective_date=date(2024, 4, 2),
        value=2.00,
        currency="USD",
        source="test_fixture",
    )
    split_ev = CorporateActionEvent(
        event_id="ca_comb_split",
        asset_id="COMB:US",
        ticker="COMB",
        market="US",
        event_type=CorporateActionType.STOCK_SPLIT,
        effective_date=date(2024, 4, 3),
        value=2.00,
        currency="USD",
        source="test_fixture",
    )

    adj_df, factors_df = adjust_ohlcv_series(raw_df, [div_ev, split_ev])
    assert pytest.approx(adj_df.loc[0, "adj_close"], 1e-6) == 49.00
    assert pytest.approx(adj_df.loc[1, "adj_close"], 1e-6) == 49.00
    assert pytest.approx(adj_df.loc[2, "adj_close"], 1e-6) == 49.00

    ret_total = calculate_discrete_returns(raw_df, [div_ev, split_ev], return_type="total")
    assert pytest.approx(ret_total.iloc[1], 1e-6) == 0.00
    assert pytest.approx(ret_total.iloc[2], 1e-6) == 0.00


def test_repository_save_and_query_corporate_actions():
    """Verifies relational database persistence and query with PIT cutoff."""
    with get_db_session() as session:
        # Clear existing
        repository.clear_all_datasets(session)

        actions = [
            {
                "event_id": "ca_repo_1",
                "asset_id": "OGDC:PSX",
                "ticker": "OGDC",
                "market": "PSX",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 3, 15),
                "announcement_date": date(2024, 2, 20),
                "value": 3.0,
                "currency": "PKR",
                "source": "psx_official",
                "is_point_in_time_verified": True,
            },
            {
                "event_id": "ca_repo_2",
                "asset_id": "OGDC:PSX",
                "ticker": "OGDC",
                "market": "PSX",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 6, 20),
                "announcement_date": date(2024, 5, 25),
                "value": 2.5,
                "currency": "PKR",
                "source": "psx_official",
                "is_point_in_time_verified": True,
            },
        ]

        saved = repository.save_corporate_actions(session, actions)
        assert len(saved) == 2

        # Query all
        all_res = repository.query_corporate_actions(session, asset_id="OGDC:PSX")
        assert len(all_res) == 2

        # Query with strict PIT as of 2024-03-01: should only return the first event!
        pit_res = repository.query_corporate_actions(
            session,
            asset_id="OGDC:PSX",
            as_of_date=date(2024, 3, 1),
            strict_pit=True,
        )
        assert len(pit_res) == 1
        assert pit_res[0].id == "ca_repo_1"
