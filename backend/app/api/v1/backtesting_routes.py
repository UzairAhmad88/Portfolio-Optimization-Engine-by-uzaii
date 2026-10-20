"""
FastAPI route definitions for portfolio strategy backtesting and simulation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.backtesting.models import (
    BacktestListItem,
    BacktestRequest,
    BacktestResponse,
)
from app.backtesting.service import (
    delete_backtest_by_id,
    execute_backtest,
    get_backtest_by_id,
    list_user_backtests,
)
from app.db.models import UserModel
from app.db.session import get_db

router = APIRouter(prefix="/backtests", tags=["Backtesting & Simulation"])


@router.post(
    "",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Portfolio Backtest",
    description="Simulates historical strategy performance with realistic transaction costs, slippage, and rebalancing schedules.",
)
async def create_backtest(
    request: BacktestRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> BacktestResponse:
    try:
        return await run_in_threadpool(
            execute_backtest,
            request=request,
            current_user=current_user,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=list[BacktestListItem],
    summary="List User Backtests",
    description="Retrieves a list of backtest runs executed by the authenticated user, ordered by creation date descending.",
)
def list_backtests(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[BacktestListItem]:
    return list_user_backtests(
        current_user=current_user,
        session=session,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{backtest_id}",
    response_model=BacktestResponse,
    summary="Get Backtest Run Details",
    description="Retrieves the complete result, summary metrics, equity curves, and rebalance logs for an authorized backtest run.",
)
def get_backtest(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> BacktestResponse:
    return get_backtest_by_id(
        backtest_id=backtest_id,
        current_user=current_user,
        session=session,
    )


@router.delete(
    "/{backtest_id}",
    summary="Delete Backtest Run",
    description="Deletes a persistent backtest run belonging to the authenticated user.",
)
def delete_backtest(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    return delete_backtest_by_id(
        backtest_id=backtest_id,
        current_user=current_user,
        session=session,
    )
