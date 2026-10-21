"""
Service layer for portfolio backtesting: orchestrates data preparation,
simulation engine execution, PostgreSQL persistence, and access authorization.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.data import prepare_backtest_data
from app.backtesting.engine import run_portfolio_simulation
from app.backtesting.models import (
    BacktestListItem,
    BacktestRequest,
    BacktestResponse,
    BacktestSummaryMetrics,
    EquityPoint,
    RebalanceEvent,
)
from app.db.models import BacktestRunModel, UserModel


def execute_backtest(
    request: BacktestRequest,
    current_user: UserModel,
    session: Session,
) -> BacktestResponse:
    """
    Executes a historical backtest simulation and persists results in the database.
    """
    # 1. Prepare historical price panel and validate asset/dataset access
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=request.start_date,
        end_date=request.end_date,
        user=current_user,
        session=session,
        min_required_observations=request.training_window + 2
        if request.strategy_type == "walk_forward_optimization"
        else 2,
        use_point_in_time=request.use_point_in_time,
        as_of_date=request.as_of_date,
        strict_pit=request.strict_pit,
        adjustment_type=request.adjustment_type,
    )


    # Map weights to canonical resolved asset IDs
    canonical_weights: dict[str, float] | None = None
    if request.weights:
        canonical_weights = {}
        for aid in resolved_assets:
            ticker = aid.split(":")[0]
            if aid in request.weights:
                canonical_weights[aid] = float(request.weights[aid])
            elif ticker in request.weights:
                canonical_weights[aid] = float(request.weights[ticker])
            else:
                canonical_weights[aid] = 0.0

    # 2. Run simulation engine
    metrics, equity_curve, rebalance_events = run_portfolio_simulation(
        prices=clean_prices,
        strategy_type=request.strategy_type,
        target_weights=canonical_weights,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
        training_window=request.training_window,
        test_window=request.test_window,
        optimization_objective=request.optimization_objective,
        periods_per_year=periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    # 3. Persist run record
    backtest_id = str(uuid4())
    now_utc = datetime.now(timezone.utc)

    eff_start = date.fromisoformat(metrics.effective_start_date) if metrics.effective_start_date else None
    eff_end = date.fromisoformat(metrics.effective_end_date) if metrics.effective_end_date else None

    run_record = BacktestRunModel(
        id=backtest_id,
        user_id=current_user.id,
        dataset_id=request.dataset_id,
        name=request.name,
        strategy_type=request.strategy_type,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
        start_date=eff_start,
        end_date=eff_end,
        status="completed",
        strategy_config_json=json.dumps(request.model_dump(mode="json")),
        summary_metrics_json=json.dumps(metrics.model_dump(mode="json")),
        equity_curve_json=json.dumps([pt.model_dump(mode="json") for pt in equity_curve]),
        rebalance_events_json=json.dumps([ev.model_dump(mode="json") for ev in rebalance_events]),
        created_at=now_utc,
    )

    session.add(run_record)
    session.commit()
    session.refresh(run_record)

    return BacktestResponse(
        id=backtest_id,
        dataset_id=request.dataset_id,
        user_id=current_user.id,
        name=request.name,
        strategy_type=request.strategy_type,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
        status="completed",
        created_at=now_utc.isoformat(),
        metrics=metrics,
        equity_curve=equity_curve,
        rebalance_events=rebalance_events,
        warnings=warnings,
        point_in_time_metadata=getattr(clean_prices, "attrs", {}).get("pit_metadata"),
    )



def list_user_backtests(
    current_user: UserModel,
    session: Session,
    limit: int = 50,
    offset: int = 0,
) -> list[BacktestListItem]:
    """
    Lists backtests belonging to the current user, ordered by creation date descending.
    Admins can view all backtests.
    """
    stmt = select(BacktestRunModel)
    if current_user.role != "admin":
        stmt = stmt.where(BacktestRunModel.user_id == current_user.id)

    stmt = stmt.order_by(BacktestRunModel.created_at.desc()).limit(limit).offset(offset)
    records = session.scalars(stmt).all()

    items: list[BacktestListItem] = []
    for r in records:
        m = r.get_summary_metrics()
        items.append(
            BacktestListItem(
                id=r.id,
                dataset_id=r.dataset_id,
                user_id=r.user_id,
                name=r.name,
                strategy_type=r.strategy_type,
                rebalance_frequency=r.rebalance_frequency,
                initial_capital=float(r.initial_capital),
                final_value_net=float(m.get("final_value_net", r.initial_capital)),
                cumulative_return_net=float(m.get("cumulative_return_net", 0.0)),
                cagr_net=float(m.get("cagr_net", 0.0)),
                sharpe_ratio_net=m.get("sharpe_ratio_net"),
                max_drawdown_net=float(m.get("max_drawdown_net", 0.0)),
                status=r.status,
                created_at=r.created_at.isoformat(),
            )
        )
    return items


def get_backtest_by_id(
    backtest_id: str,
    current_user: UserModel,
    session: Session,
) -> BacktestResponse:
    """
    Retrieves full backtest run results by ID, enforcing user authorization.
    """
    record = session.get(BacktestRunModel, backtest_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run '{backtest_id}' not found.",
        )

    if record.user_id and record.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this backtest simulation.",
        )

    metrics_dict = record.get_summary_metrics()
    equity_curve_raw = record.get_equity_curve()
    rebalance_events_raw = record.get_rebalance_events()

    metrics = BacktestSummaryMetrics(**metrics_dict)
    equity_curve = [EquityPoint(**pt) for pt in equity_curve_raw]
    rebalance_events = [RebalanceEvent(**ev) for ev in rebalance_events_raw]

    return BacktestResponse(
        id=record.id,
        dataset_id=record.dataset_id,
        user_id=record.user_id,
        name=record.name,
        strategy_type=record.strategy_type,
        rebalance_frequency=record.rebalance_frequency,
        initial_capital=float(record.initial_capital),
        transaction_cost_bps=float(record.transaction_cost_bps),
        slippage_bps=float(record.slippage_bps),
        status=record.status,
        created_at=record.created_at.isoformat(),
        metrics=metrics,
        equity_curve=equity_curve,
        rebalance_events=rebalance_events,
        warnings=[],
    )


def delete_backtest_by_id(
    backtest_id: str,
    current_user: UserModel,
    session: Session,
) -> dict[str, str]:
    """
    Deletes a persistent backtest run by ID, enforcing user authorization.
    """
    record = session.get(BacktestRunModel, backtest_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run '{backtest_id}' not found.",
        )

    if record.user_id and record.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this backtest simulation.",
        )

    session.delete(record)
    session.commit()
    return {"status": "deleted", "id": backtest_id}
