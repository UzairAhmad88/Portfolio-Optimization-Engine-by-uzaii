"""
FastAPI router for portfolio performance attribution, benchmark analysis, and risk-adjusted metrics.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.db.models import BacktestRunModel, UserModel
from app.db.session import get_db
from app.market_data.service import DatasetNotFoundError
from app.performance.models import (
    PerformanceAnalysisRequest,
    PerformanceReportListItem,
    PerformanceResponse,
)
from app.performance.service import (
    delete_performance_report,
    execute_performance_analysis,
    get_performance_report,
    list_performance_reports,
)

router = APIRouter(prefix="/performance", tags=["Portfolio Performance Attribution & Benchmark Analysis"])


@router.post(
    "/analyze",
    response_model=PerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute portfolio performance analysis against benchmark",
)
async def analyze_performance_endpoint(
    request: PerformanceAnalysisRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PerformanceResponse:
    """
    Executes a comparative performance evaluation against a benchmark asset.
    Computes active returns, tracking error, Information Ratio, Beta, Jensen's Alpha,
    Capture Ratios, and multi-period asset-level return contributions.
    """
    try:
        return await run_in_threadpool(
            execute_performance_analysis,
            req=request,
            user=current_user,
            db=session,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"errors": [str(e)]})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": [str(e)]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": [f"Performance analysis failed: {str(e)}"]},
        )


@router.get(
    "/backtests/{backtest_id}",
    response_model=PerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate an owned saved backtest against a reference benchmark",
)
async def evaluate_backtest_performance_endpoint(
    backtest_id: str,
    benchmark_asset: Annotated[str, Query(description="Benchmark asset ticker or ID in dataset (e.g. SPY:US)")],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    risk_free_rate: float = Query(default=0.0, ge=-0.1, le=0.5),
    save_report: bool = Query(default=False),
) -> PerformanceResponse:
    """
    Directly evaluates a saved backtest against a benchmark from its source dataset.
    """
    backtest = (
        session.query(BacktestRunModel)
        .filter(BacktestRunModel.id == backtest_id)
        .first()
    )
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Backtest run '{backtest_id}' not found."]},
        )
    if backtest.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Backtest run '{backtest_id}' not found."]},
        )

    req = PerformanceAnalysisRequest(
        dataset_id=backtest.dataset_id,
        backtest_id=backtest.id,
        name=f"Performance: {backtest.name} vs {benchmark_asset}",
        benchmark_asset=benchmark_asset,
        risk_free_rate=risk_free_rate,
        save_report=save_report,
    )

    try:
        return await run_in_threadpool(
            execute_performance_analysis,
            req=req,
            user=current_user,
            db=session,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"errors": [str(e)]})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": [str(e)]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": [f"Backtest performance evaluation failed: {str(e)}"]},
        )


@router.get(
    "/reports",
    response_model=list[PerformanceReportListItem],
    status_code=status.HTTP_200_OK,
    summary="List saved performance reports for authenticated user",
)
async def list_reports_endpoint(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[PerformanceReportListItem]:
    """Retrieves all saved performance reports owned by the authenticated researcher."""
    return await run_in_threadpool(
        list_performance_reports,
        user=current_user,
        db=session,
    )


@router.get(
    "/reports/{report_id}",
    response_model=PerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an owned saved performance report by ID",
)
async def get_report_endpoint(
    report_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PerformanceResponse:
    """Retrieves detailed performance metrics and time series for an owned report."""
    return await run_in_threadpool(
        get_performance_report,
        report_id=report_id,
        user=current_user,
        db=session,
    )


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an owned performance report",
)
async def delete_report_endpoint(
    report_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Deletes a saved performance report owned by the authenticated researcher."""
    await run_in_threadpool(
        delete_performance_report,
        report_id=report_id,
        user=current_user,
        db=session,
    )
