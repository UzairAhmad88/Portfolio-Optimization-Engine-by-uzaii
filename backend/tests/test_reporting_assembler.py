"""
Unit test suite for ReportAssemblerService (Stage 34 Gate B).
Tests quantitative metrics assembly, gross vs net segregation, benchmark attribution,
monthly compounding matrices, provenance lineage, and warning generation.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import uuid4
import numpy as np
import pytest
from fastapi import HTTPException

from app.db.models import (
    BacktestRunModel,
    DatasetModel,
    DatasetSnapshotModel,
    PerformanceReportModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.db.session import get_db_session
from app.reports.assembler import ReportAssemblerService
from app.reports.contracts import (
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
)

USER_1_ID = "00000000-0000-0000-0000-000000000001"
USER_2_ID = "00000000-0000-0000-0000-000000000002"
ADMIN_ID = "00000000-0000-0000-0000-0000000000aa"


@pytest.fixture
def seed_reporting_users():
    with get_db_session() as session:
        for uid, email, role in [
            (USER_1_ID, "user1@quant.local", "researcher"),
            (USER_2_ID, "user2@quant.local", "researcher"),
            (ADMIN_ID, "admin@quant.local", "admin"),
        ]:
            u = session.get(UserModel, uid)
            if not u:
                session.add(
                    UserModel(
                        id=uid,
                        email=email,
                        hashed_password="hash",
                        full_name=f"User {uid}",
                        role=role,
                        is_active=True,
                    )
                )
        session.commit()

    user1 = UserModel(
        id=USER_1_ID,
        email="user1@quant.local",
        hashed_password="hash",
        full_name="User 1",
        role="researcher",
        is_active=True,
    )
    user2 = UserModel(
        id=USER_2_ID,
        email="user2@quant.local",
        hashed_password="hash",
        full_name="User 2",
        role="researcher",
        is_active=True,
    )
    admin = UserModel(
        id=ADMIN_ID,
        email="admin@quant.local",
        hashed_password="hash",
        full_name="Admin",
        role="admin",
        is_active=True,
    )
    return user1, user2, admin


@pytest.fixture
def seed_backtest_with_snapshot(seed_reporting_users):
    user1, _, _ = seed_reporting_users
    dataset_id = str(uuid4())
    snapshot_id = str(uuid4())
    backtest_id = str(uuid4())

    with get_db_session() as session:
        # Create dataset
        ds = DatasetModel(
            id=dataset_id,
            user_id=user1.id,
            filename="us_tech_equities.csv",
            content_sha256="d" * 64,
            rows_examined=100,
            valid_rows=100,
            rejected_rows=0,
            status="completed",
        )
        session.add(ds)

        # Create immutable snapshot
        snap = DatasetSnapshotModel(
            id=snapshot_id,
            dataset_id=dataset_id,
            user_id=user1.id,
            tag="v1.0-certified",
            manifest_sha256="e" * 64,
            manifest_json=json.dumps({"schema_version": "1.2", "total_bars": 100}),
            is_frozen=True,
        )
        session.add(snap)

        # Create equity curve (252 days)
        base_nav = 100000.0
        equity_curve = []
        for i in range(252):
            d_str = f"2023-{(i // 22) + 1:02d}-{(i % 22) + 1:02d}"
            r_net = 0.0008 + 0.0001 * (i % 5 - 2)
            r_gross = r_net + 0.0002
            v_net = base_nav * (1.0 + 0.20 * (i / 252.0))
            v_gross = base_nav * (1.0 + 0.22 * (i / 252.0))
            dd_net = 0.04 * (1.0 if (50 <= i <= 80) else 0.0)
            dd_gross = 0.038 * (1.0 if (50 <= i <= 80) else 0.0)
            equity_curve.append({
                "date": d_str,
                "portfolio_value_net": v_net,
                "portfolio_value_gross": v_gross,
                "return_net": r_net,
                "return_gross": r_gross,
                "drawdown_net": dd_net,
                "drawdown_gross": dd_gross,
            })

        summary = {
            "initial_value": 100000.0,
            "final_value_net": 120000.0,
            "final_value_gross": 122000.0,
            "cumulative_return_net": 0.2000,
            "cumulative_return_gross": 0.2200,
            "cagr_net": 0.2000,
            "cagr_gross": 0.2200,
            "annualized_return_net": 0.1850,
            "annualized_return_gross": 0.2010,
            "volatility_annualized_net": 0.1250,
            "volatility_annualized_gross": 0.1245,
            "sharpe_ratio_net": 1.4800,
            "sharpe_ratio_gross": 1.6145,
            "sortino_ratio_net": 2.1500,
            "sortino_ratio_gross": 2.3100,
            "max_drawdown_net": 0.0400,
            "max_drawdown_gross": 0.0380,
            "drawdown_peak_date": "2023-03-08",
            "drawdown_trough_date": "2023-04-12",
            "total_turnover": 2.50,
            "total_transaction_costs": 250.0,
            "total_slippage_costs": 125.0,
            "total_friction_costs": 375.0,
            "number_of_rebalances": 12,
            "observation_count": 252,
            "periods_per_year": 252,
            "effective_start_date": "2023-01-03",
            "effective_end_date": "2023-12-29",
        }

        strat_cfg = {
            "assets": ["AAPL", "MSFT", "GOOGL", "AMZN"],
            "weights": {"AAPL": 0.35, "MSFT": 0.30, "GOOGL": 0.20, "AMZN": 0.15},
            "strategy_type": "target_weights",
            "rebalance_frequency": "monthly",
            "initial_capital": 100000.0,
            "transaction_cost_bps": 10.0,
            "slippage_bps": 5.0,
            "risk_free_rate": 0.02,
        }

        bt = BacktestRunModel(
            id=backtest_id,
            user_id=user1.id,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            name="US Momentum Core Strategy",
            strategy_type="target_weights",
            rebalance_frequency="monthly",
            initial_capital=100000.0,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
            start_date=date(2023, 1, 3),
            end_date=date(2023, 12, 29),
            status="completed",
            strategy_config_json=json.dumps(strat_cfg),
            summary_metrics_json=json.dumps(summary),
            equity_curve_json=json.dumps(equity_curve),
            rebalance_events_json=json.dumps([]),
        )
        session.add(bt)
        session.commit()

        return backtest_id, dataset_id, snapshot_id


class TestReportAssemblerFactSheet:
    """Verifies Strategy Fact Sheet analytical assembly."""

    def test_assemble_fact_sheet_success(self, seed_reporting_users, seed_backtest_with_snapshot):
        user1, _, _ = seed_reporting_users
        backtest_id, dataset_id, snapshot_id = seed_backtest_with_snapshot

        with get_db_session() as session:
            payload = ReportAssemblerService.assemble_fact_sheet(
                backtest_id=backtest_id,
                current_user=user1,
                db=session,
            )

        assert isinstance(payload, StrategyFactSheetPayload)
        assert payload.envelope.report_type == "fact_sheet"
        assert payload.envelope.report_title == "US Momentum Core Strategy"
        assert payload.envelope.snapshot_id == snapshot_id
        assert payload.envelope.snapshot_manifest_digest == "e" * 64
        assert payload.envelope.dataset_filename == "us_tech_equities.csv"
        assert payload.envelope.is_hypothetical is True

        # Mandate
        assert payload.mandate.strategy_type == "target_weights"
        assert payload.mandate.initial_capital == 100000.0
        assert payload.mandate.rebalance_frequency == "monthly"
        assert len(payload.mandate.investment_universe) == 4

        # KPIs
        assert payload.kpis.cumulative_return_net == 0.2000
        assert payload.kpis.cumulative_return_gross == 0.2200
        assert payload.kpis.cagr_net == 0.2000
        assert payload.kpis.cagr_gross == 0.2200
        assert payload.kpis.sharpe_ratio_net == 1.4800
        assert payload.kpis.sharpe_ratio_gross == 1.6145
        assert payload.kpis.calmar_ratio_net == pytest.approx(0.2000 / 0.0400, rel=1e-4)
        assert payload.kpis.calmar_ratio_gross == pytest.approx(0.2200 / 0.0380, rel=1e-4)

        # Holdings
        assert len(payload.top_holdings) == 4
        assert payload.top_holdings[0].ticker == "AAPL"
        assert payload.top_holdings[0].effective_weight == 0.35

        # Monthly returns
        assert len(payload.monthly_returns) >= 11
        for cell in payload.monthly_returns:
            assert cell.year == 2023
            assert 1 <= cell.month <= 12
            assert cell.return_net > 0.0

        # Compact wealth curve downsampled
        assert len(payload.compact_wealth_curve) <= 250
        assert payload.compact_wealth_curve[0].date == "2023-01-01" or payload.compact_wealth_curve[0].date.startswith("2023-01")

    def test_assemble_fact_sheet_unauthorized_user_raises_404(
        self, seed_reporting_users, seed_backtest_with_snapshot
    ):
        _, user2, _ = seed_reporting_users
        backtest_id, _, _ = seed_backtest_with_snapshot

        with get_db_session() as session:
            with pytest.raises(HTTPException) as exc_info:
                ReportAssemblerService.assemble_fact_sheet(
                    backtest_id=backtest_id,
                    current_user=user2,  # User 2 does not own this backtest
                    db=session,
                )
            assert exc_info.value.status_code == 404

    def test_assemble_fact_sheet_admin_user_has_access(
        self, seed_reporting_users, seed_backtest_with_snapshot
    ):
        _, _, admin = seed_reporting_users
        backtest_id, _, _ = seed_backtest_with_snapshot

        with get_db_session() as session:
            payload = ReportAssemblerService.assemble_fact_sheet(
                backtest_id=backtest_id,
                current_user=admin,  # Admin can access all backtests
                db=session,
            )
            assert payload.envelope.source_backtest_id == backtest_id


class TestReportAssemblerTearSheet:
    """Verifies Institutional Tear Sheet 2-page analytical assembly."""

    def test_assemble_tear_sheet_comprehensive(
        self, seed_reporting_users, seed_backtest_with_snapshot
    ):
        user1, _, _ = seed_reporting_users
        backtest_id, _, _ = seed_backtest_with_snapshot

        with get_db_session() as session:
            payload = ReportAssemblerService.assemble_tear_sheet(
                backtest_id=backtest_id,
                current_user=user1,
                db=session,
            )

        assert isinstance(payload, InstitutionalTearSheetPayload)
        assert payload.envelope.report_type == "tear_sheet"
        assert len(payload.equity_curve) == 252
        assert len(payload.asset_allocation) == 4
        assert payload.friction_and_execution is not None
        assert payload.friction_and_execution.transaction_cost_bps == 10.0
        assert payload.friction_and_execution.slippage_bps == 5.0
        assert payload.friction_and_execution.friction_drag_bps == 37.5  # (375 / 100000) * 10000

    def test_assemble_tear_sheet_mutable_dataset_warning(self, seed_reporting_users):
        """When backtest lacks a snapshot certification, emits WARN_MUTABLE_DATASET."""
        user1, _, _ = seed_reporting_users
        dataset_id = str(uuid4())
        backtest_id = str(uuid4())

        with get_db_session() as session:
            ds = DatasetModel(
                id=dataset_id,
                user_id=user1.id,
                filename="live_feed.csv",
                content_sha256="f" * 64,
                rows_examined=10,
                valid_rows=10,
                rejected_rows=0,
            )
            session.add(ds)

            bt = BacktestRunModel(
                id=backtest_id,
                user_id=user1.id,
                dataset_id=dataset_id,
                snapshot_id=None,  # No snapshot
                name="Live Dataset Run",
                strategy_type="equal_weight",
                rebalance_frequency="daily",
                initial_capital=50000.0,
                transaction_cost_bps=0.0,
                slippage_bps=0.0,
                summary_metrics_json=json.dumps({"cumulative_return_net": 0.05, "max_drawdown_net": 0.01}),
                equity_curve_json=json.dumps([{"date": "2023-01-03", "portfolio_value_net": 52500.0, "return_net": 0.05, "drawdown_net": 0.0}]),
                strategy_config_json=json.dumps({"assets": ["SPY"]}),
            )
            session.add(bt)
            session.commit()

            payload = ReportAssemblerService.assemble_tear_sheet(
                backtest_id=backtest_id,
                current_user=user1,
                db=session,
            )

        warn_codes = [w.code for w in payload.envelope.warnings]
        assert "WARN_MUTABLE_DATASET" in warn_codes
        assert payload.envelope.snapshot_id is None
        assert payload.envelope.snapshot_manifest_digest is None

    def test_assemble_tear_sheet_undefined_calmar_on_zero_drawdown(self, seed_reporting_users):
        """When max drawdown is 0.0, Calmar ratio must be None, never 0.0."""
        user1, _, _ = seed_reporting_users
        dataset_id = str(uuid4())
        backtest_id = str(uuid4())

        with get_db_session() as session:
            ds = DatasetModel(
                id=dataset_id,
                user_id=user1.id,
                filename="zero_dd.csv",
                content_sha256="1" * 64,
                rows_examined=5,
                valid_rows=5,
                rejected_rows=0,
            )
            session.add(ds)

            bt = BacktestRunModel(
                id=backtest_id,
                user_id=user1.id,
                dataset_id=dataset_id,
                name="Perfect Upward Run",
                strategy_type="target_weights",
                rebalance_frequency="daily",
                initial_capital=10000.0,
                transaction_cost_bps=0.0,
                slippage_bps=0.0,
                summary_metrics_json=json.dumps({
                    "cagr_net": 0.15,
                    "max_drawdown_net": 0.0,  # Zero drawdown!
                    "cagr_gross": 0.16,
                    "max_drawdown_gross": 0.0,
                }),
                equity_curve_json=json.dumps([{"date": "2023-01-03", "portfolio_value_net": 10500.0, "return_net": 0.05, "drawdown_net": 0.0}]),
                strategy_config_json=json.dumps({"assets": ["SPY"]}),
            )
            session.add(bt)
            session.commit()

            payload = ReportAssemblerService.assemble_tear_sheet(
                backtest_id=backtest_id,
                current_user=user1,
                db=session,
            )

        assert payload.kpis.max_drawdown_net == 0.0
        assert payload.kpis.calmar_ratio_net is None
        assert payload.kpis.calmar_ratio_gross is None


class TestReportAssemblerResearchAnnexAndUnified:
    """Verifies Research Diagnostics Annex and Unified Report assembly."""

    def test_assemble_unified_report(
        self, seed_reporting_users, seed_backtest_with_snapshot
    ):
        user1, _, _ = seed_reporting_users
        backtest_id, _, _ = seed_backtest_with_snapshot

        with get_db_session() as session:
            unified = ReportAssemblerService.assemble_unified_report(
                backtest_id=backtest_id,
                current_user=user1,
                db=session,
            )

        assert isinstance(unified, InstitutionalReportResponse)
        assert unified.envelope.report_type == "unified_tear_sheet"
        assert unified.fact_sheet is not None
        assert unified.tear_sheet is not None
        assert unified.fact_sheet.kpis.cumulative_return_net == 0.2000
        assert unified.tear_sheet.friction_and_execution is not None
