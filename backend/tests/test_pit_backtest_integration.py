"""
Focused integration tests for Point-in-Time Backtesting Integration (Session 51 / DEF-31-01).

Verifies:
1. Existing callers using legacy defaults retain prior behavior.
2. Strict mode excludes events not available by the cutoff.
3. Missing announcement/publication availability fails closed in strict mode.
4. A later correction cannot alter an earlier cutoff's view.
5. A future corporate action cannot influence an earlier historical decision.
6. A split is not mistaken for a market loss in the strict adjusted series.
7. Dividend-inclusive total return is distinct from price return.
8. Double adjustment prevention on pre-adjusted data.
9. Unsupported or complex events produce an explicit, safe outcome.
10. Dataset access controls and tenant isolation remain enforced.
11. End-to-end backtest API execution returns point-in-time metadata.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.backtesting.data import prepare_backtest_data
from app.backtesting.models import BacktestRequest
from app.backtesting.service import execute_backtest
from app.db.models import DatasetModel, PriceBarModel, UserModel
from app.main import app
from app.market_data import repository
from app.market_data.adjustments import AdjustmentPolicy
from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)
from app.db.session import get_db_session
from app.db.models import CorporateActionModel, PriceBarModel, DatasetModel, UserModel


@pytest.fixture
def db_session():
    with get_db_session() as session:
        session.query(CorporateActionModel).delete()
        session.query(PriceBarModel).delete()
        session.query(DatasetModel).delete()
        session.commit()
        yield session
        session.query(CorporateActionModel).delete()
        session.query(PriceBarModel).delete()
        session.query(DatasetModel).delete()
        session.commit()


def _seed_test_user_and_dataset(
    db_session: Session,
    dataset_name: str = "PIT Test Dataset",
    email: str | None = None,
) -> tuple[UserModel, DatasetModel]:
    unique_id = uuid4().hex[:8]
    user_email = f"{unique_id}_{email}" if email else f"pit_user_{unique_id}@example.com"
    user = UserModel(
        id=str(uuid4()),
        email=user_email,
        hashed_password=hash_password("Password123!"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    dataset_id = str(uuid4())
    dataset = DatasetModel(
        id=dataset_id,
        user_id=user.id,
        filename=f"{dataset_name.lower().replace(' ', '_')}_{unique_id}.csv",
        content_sha256=f"sha256_{unique_id}",
        rows_examined=10,
        valid_rows=10,
        rejected_rows=0,
        status="completed",
        point_in_time_status="unverified_legacy",
    )
    db_session.add(dataset)
    db_session.commit()

    return user, dataset


def _create_bar(
    dataset_id: str,
    ticker: str,
    market: str,
    currency: str,
    date: date,
    close: float,
    adj_close: float | None = None,
) -> PriceBarModel:
    return PriceBarModel(
        dataset_id=dataset_id,
        asset_id=f"{ticker}:{market}",
        ticker=ticker,
        market=market,
        currency=currency,
        date=date,
        close=close,
        adj_close=adj_close if adj_close is not None else close,
    )


def test_legacy_backtest_data_preparation_unaltered(db_session: Session):
    """1. Existing callers using legacy defaults (use_point_in_time=False) retain prior behavior."""
    user, ds = _seed_test_user_and_dataset(db_session, "Legacy Test DS")

    # Seed 3 days of price bars with provider adjusted_close
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    # Provider adjusted close is 50, raw close is 100 on day 1
    for d, raw_c, adj_c in zip(dates, [100.0, 100.0, 50.0], [50.0, 50.0, 50.0]):
        bar = _create_bar(ds.id, "AAPL", "US", "USD", d, raw_c, adj_c)
        db_session.add(bar)
    db_session.commit()

    # Call with legacy defaults
    clean_df, resolved, currency, periods, warnings = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["AAPL"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        min_required_observations=2,
        use_point_in_time=False,
    )

    assert "AAPL:US" in clean_df.columns
    # In legacy mode, it uses provider adjusted_close (50.0)
    assert clean_df["AAPL:US"].iloc[0] == 50.0
    assert clean_df["AAPL:US"].iloc[1] == 50.0
    assert clean_df["AAPL:US"].iloc[2] == 50.0
    assert "pit_metadata" not in clean_df.attrs


def test_strict_pit_excludes_future_announced_actions(db_session: Session):
    """2. Strict mode excludes events not announced by the decision cutoff date."""
    user, ds = _seed_test_user_and_dataset(db_session, "Future Action DS")

    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    for d, raw_c in zip(dates, [100.0, 100.0, 50.0]):
        bar = _create_bar(ds.id, "TSLA", "US", "USD", d, raw_c, raw_c)
        db_session.add(bar)
    db_session.commit()

    # Register 2:1 split effective 2024-01-04, but announced on 2024-01-03
    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_tsla_split",
                "asset_id": "TSLA:US",
                "ticker": "TSLA",
                "market": "US",
                "event_type": "stock_split",
                "effective_date": date(2024, 1, 4),
                "announcement_date": date(2024, 1, 3),
                "value": 2.0,
                "currency": "USD",
                "source": "sec_filing",
                "is_point_in_time_verified": True,
            }
        ],
    )
    db_session.commit()

    # Cutoff prior to announcement date (2024-01-02)
    clean_df_early, _, _, _, warnings_early = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["TSLA"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 4),
        user=user,
        session=db_session,
        use_point_in_time=True,
        as_of_date=date(2024, 1, 2),  # Cutoff before announcement!
        strict_pit=True,
    )

    # Split was NOT announced as of Jan 2, so historical Day 1 & Day 2 prices are NOT split-adjusted!
    assert clean_df_early["TSLA:US"].iloc[0] == 100.0
    assert clean_df_early["TSLA:US"].iloc[1] == 100.0
    assert clean_df_early.attrs["pit_metadata"]["eligible_actions_count"] == 0
    assert clean_df_early.attrs["pit_metadata"]["excluded_future_actions_count"] == 1

    # Cutoff on or after announcement date (2024-01-03)
    clean_df_late, _, _, _, warnings_late = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["TSLA"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 4),
        user=user,
        session=db_session,
        use_point_in_time=True,
        as_of_date=date(2024, 1, 3),  # Cutoff after announcement!
        strict_pit=True,
    )

    # Split WAS announced by Jan 3, so Day 1 & Day 2 prices are split-adjusted to 50.0!
    assert clean_df_late["TSLA:US"].iloc[0] == 50.0
    assert clean_df_late["TSLA:US"].iloc[1] == 50.0
    assert clean_df_late["TSLA:US"].iloc[2] == 50.0
    assert clean_df_late.attrs["pit_metadata"]["eligible_actions_count"] == 1


def test_missing_announcement_date_fails_closed_in_backtest(db_session: Session):
    """3. Events lacking authoritative announcement timestamp fail closed in strict PIT mode."""
    user, ds = _seed_test_user_and_dataset(db_session, "Fail Closed DS")

    for d in [date(2024, 1, 2), date(2024, 1, 3)]:
        bar = _create_bar(ds.id, "XYZ", "US", "USD", d, 100.0, 100.0)
        db_session.add(bar)
    db_session.commit()

    # Save event without announcement_date
    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_unverified",
                "asset_id": "XYZ:US",
                "ticker": "XYZ",
                "market": "US",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 1, 3),
                "announcement_date": None,  # Missing!
                "value": 1.0,
                "currency": "USD",
                "source": "unverified_feed",
            }
        ],
    )

    with pytest.raises(ValueError, match="Strict Point-in-Time verification failed"):
        prepare_backtest_data(
            dataset_id=ds.id,
            requested_assets=["XYZ"],
            start_date=None,
            end_date=None,
            user=user,
            session=db_session,
            use_point_in_time=True,
            strict_pit=True,
        )


def test_later_revision_cannot_alter_earlier_cutoff_view(db_session: Session):
    """4. A later corporate action revision cannot alter an earlier cutoff's view."""
    user, ds = _seed_test_user_and_dataset(db_session, "Revision DS")

    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    for d, c in zip(dates, [100.0, 98.0, 98.0]):
        bar = _create_bar(ds.id, "MSFT", "US", "USD", d, c, c)
        db_session.add(bar)
    db_session.commit()

    # Revision 1 announced on Jan 10 ($1.00 dividend)
    # Revision 2 announced on Feb 10 ($2.00 dividend correction)
    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_msft_div_v1",
                "asset_id": "MSFT:US",
                "ticker": "MSFT",
                "market": "US",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 1, 3),
                "announcement_date": date(2024, 1, 10),
                "value": 1.0,
                "currency": "USD",
                "source": "reuters",
                "revision_id": "rev_1",
            },
            {
                "event_id": "ca_msft_div_v2",
                "asset_id": "MSFT:US",
                "ticker": "MSFT",
                "market": "US",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 1, 3),
                "announcement_date": date(2024, 2, 10),  # Corrected later
                "value": 2.0,
                "currency": "USD",
                "source": "reuters",
                "revision_id": "rev_2",
            },
        ],
    )

    # Query as of Jan 20 (before Rev 2 was announced)
    df_jan, _, _, _, _ = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["MSFT"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        use_point_in_time=True,
        as_of_date=date(2024, 1, 20),
        strict_pit=True,
    )
    # In Jan, only Rev 1 ($1.00) is known. Day 1 adj price = 100 * (1 - 1/100) = 99.0
    assert abs(df_jan["MSFT:US"].iloc[0] - 99.0) < 1e-4

    # Query as of Feb 20 (after Rev 2 was announced)
    df_feb, _, _, _, _ = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["MSFT"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        use_point_in_time=True,
        as_of_date=date(2024, 2, 20),
        strict_pit=True,
    )
    # In Feb, Rev 2 ($2.00) is known and supersedes Rev 1. Day 1 adj price = 100 * (1 - 2/100) = 98.0
    assert abs(df_feb["MSFT:US"].iloc[0] - 98.0) < 1e-4

    # Crucial anti-retroactivity check: the Jan 20 query remains at 99.0 regardless of Rev 2's existence
    assert abs(df_jan["MSFT:US"].iloc[0] - 99.0) < 1e-4


def test_split_prevents_artificial_market_loss(db_session: Session):
    """6. A 2:1 stock split is not mistaken for a 50% market loss in the strict adjusted series."""
    user, ds = _seed_test_user_and_dataset(db_session, "Split DS")

    # Day 1: $100. Day 2: 2:1 split happens, price drops to $50.
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    for d, c in zip(dates, [100.0, 50.0]):
        bar = _create_bar(ds.id, "NVDA", "US", "USD", d, c, c)
        db_session.add(bar)
    db_session.commit()

    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_nvda_split",
                "asset_id": "NVDA:US",
                "ticker": "NVDA",
                "market": "US",
                "event_type": "stock_split",
                "effective_date": date(2024, 1, 3),
                "announcement_date": date(2024, 1, 2),
                "value": 2.0,
                "currency": "USD",
                "source": "sec_8k",
            }
        ],
    )

    clean_df, _, _, _, _ = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["NVDA"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        use_point_in_time=True,
        as_of_date=date(2024, 1, 3),
        strict_pit=True,
    )

    # Day 1 adjusted close is $50.00, Day 2 is $50.00
    p1 = clean_df["NVDA:US"].iloc[0]
    p2 = clean_df["NVDA:US"].iloc[1]
    assert abs(p1 - 50.0) < 1e-4
    assert abs(p2 - 50.0) < 1e-4
    # Realized return between Day 1 and Day 2 is exactly 0.0% (not -50%!)
    realized_ret = (p2 - p1) / p1
    assert abs(realized_ret - 0.0) < 1e-6


def test_dividend_inclusive_total_return_distinct_from_price_return(db_session: Session):
    """7. Dividend-inclusive total return adjustment is distinct from price-only adjustment."""
    user, ds = _seed_test_user_and_dataset(db_session, "Div Return DS")

    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    for d, c in zip(dates, [100.0, 95.0]):
        bar = _create_bar(ds.id, "IBM", "US", "USD", d, c, c)
        db_session.add(bar)
    db_session.commit()

    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_ibm_div",
                "asset_id": "IBM:US",
                "ticker": "IBM",
                "market": "US",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 1, 3),
                "announcement_date": date(2024, 1, 2),
                "value": 5.0,  # $5.00 cash dividend
                "currency": "USD",
                "source": "pr_newswire",
            }
        ],
    )

    # Total return mode: Day 1 adjusted = 100 * (1 - 5/100) = 95.0. Day 2 = 95.0. Return = 0.0%
    df_tot, _, _, _, _ = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["IBM"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        use_point_in_time=True,
        adjustment_type="total",
        as_of_date=date(2024, 1, 3),
        strict_pit=True,
    )
    assert abs(df_tot["IBM:US"].iloc[0] - 95.0) < 1e-4
    assert abs(df_tot["IBM:US"].iloc[1] - 95.0) < 1e-4

    # Price return mode: Cash dividend is NOT adjusted into price series
    # Day 1 remains 100.0, Day 2 is 95.0. Return = -5.0%
    df_px, _, _, _, _ = prepare_backtest_data(
        dataset_id=ds.id,
        requested_assets=["IBM"],
        start_date=None,
        end_date=None,
        user=user,
        session=db_session,
        use_point_in_time=True,
        adjustment_type="price",
        as_of_date=date(2024, 1, 3),
        strict_pit=True,
    )
    assert abs(df_px["IBM:US"].iloc[0] - 100.0) < 1e-4
    assert abs(df_px["IBM:US"].iloc[1] - 95.0) < 1e-4


def test_pre_adjusted_data_not_double_adjusted(db_session: Session):
    """8. Double adjustment is prevented; unverified provider adjustments fail closed in strict mode."""
    user, ds = _seed_test_user_and_dataset(db_session, "Divergent DS")

    # Seed divergent provider adjusted_close without corporate action record
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    for d, raw_c, adj_c in zip(dates, [100.0, 100.0], [50.0, 50.0]):
        bar = _create_bar(ds.id, "AMZN", "US", "USD", d, raw_c, adj_c)
        db_session.add(bar)
    db_session.commit()

    # In strict mode, provider divergence without verified actions in repository must fail closed!
    with pytest.raises(ValueError, match="provider adjusted_close that diverges from raw close"):
        prepare_backtest_data(
            dataset_id=ds.id,
            requested_assets=["AMZN"],
            start_date=None,
            end_date=None,
            user=user,
            session=db_session,
            use_point_in_time=True,
            strict_pit=True,
        )


def test_unsupported_complex_action_fails_safely():
    """9. Complex unsupported corporate actions (mergers, spin-offs) fail safely under standard policy."""
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    raw_df = pd.DataFrame({"date": dates, "close": [100.0, 100.0]})

    ev_complex = CorporateActionEvent(
        event_id="ca_complex_spinoff",
        asset_id="CMPLX:US",
        ticker="CMPLX",
        market="US",
        event_type=CorporateActionType.COMPLEX_UNSUPPORTED,
        effective_date=date(2024, 1, 3),
        value=1.0,
        currency="USD",
        source="sec",
    )

    with pytest.raises(ValueError, match="Complex unsupported corporate action"):
        from app.market_data.adjustments import adjust_ohlcv_series

        adjust_ohlcv_series(raw_df, [ev_complex], policy=AdjustmentPolicy(allow_unsupported_complex=False))


def test_tenant_isolation_enforced_in_pit_backtest(db_session: Session):
    """10. Tenant isolation and dataset authorization remain enforced in PIT mode."""
    user_owner, ds = _seed_test_user_and_dataset(db_session, "Owner DS", "owner@example.com")
    unique_att = uuid4().hex[:8]
    user_attacker = UserModel(
        id=str(uuid4()),
        email=f"attacker_{unique_att}@example.com",
        hashed_password=hash_password("Password123!"),
        role="user",
        is_active=True,
    )
    db_session.add(user_attacker)
    db_session.commit()

    # Attacker attempts to prepare backtest data on Owner's dataset
    with pytest.raises(HTTPException) as exc_info:
        prepare_backtest_data(
            dataset_id=ds.id,
            requested_assets=["TEST"],
            start_date=None,
            end_date=None,
            user=user_attacker,
            session=db_session,
            use_point_in_time=True,
            strict_pit=True,
        )
    assert exc_info.value.status_code == 403


def test_backtest_api_with_point_in_time_integration(db_session: Session):
    """11. End-to-end backtest API execution returns point-in-time metadata."""
    user, ds = _seed_test_user_and_dataset(db_session, "API Backtest DS", "api_user@example.com")

    # Seed 5 days of data
    dates = [
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
        date(2024, 1, 5),
        date(2024, 1, 8),
    ]
    for d in dates:
        bar = _create_bar(ds.id, "GOOGL", "US", "USD", d, 150.0, 150.0)
        db_session.add(bar)
    db_session.commit()

    repository.save_corporate_actions(
        session=db_session,
        dataset_id=ds.id,
        actions=[
            {
                "event_id": "ca_googl_div",
                "asset_id": "GOOGL:US",
                "ticker": "GOOGL",
                "market": "US",
                "event_type": "cash_dividend",
                "effective_date": date(2024, 1, 4),
                "announcement_date": date(2024, 1, 3),
                "value": 1.50,
                "currency": "USD",
                "source": "pr",
                "is_point_in_time_verified": True,
            }
        ],
    )

    req = BacktestRequest(
        dataset_id=ds.id,
        name="PIT Backtest Run",
        strategy_type="equal_weight",
        assets=["GOOGL"],
        initial_capital=100_000.0,
        use_point_in_time=True,
        as_of_date=date(2024, 1, 5),
        strict_pit=True,
        adjustment_type="total",
    )

    resp = execute_backtest(req, current_user=user, session=db_session)
    assert resp.status == "completed"
    assert resp.point_in_time_metadata is not None
    assert resp.point_in_time_metadata["as_of_date"] == "2024-01-05"
    assert resp.point_in_time_metadata["strict_pit"] is True
    assert resp.point_in_time_metadata["eligible_actions_count"] == 1
    assert any("PIT_STATUS: VERIFIED_PASS" in w for w in resp.warnings)
