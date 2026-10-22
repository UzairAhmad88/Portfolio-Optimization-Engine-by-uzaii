"""
FastAPI route definitions for Stage 34 institutional reporting:
Strategy Fact Sheets, Institutional Tear Sheets, and Research Diagnostics Annexes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.reports.assembler import ReportAssemblerService
from app.reports.contracts import (
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
)
from app.research.overfitting_models import OverfittingDiagnosticsRequest

router = APIRouter(prefix="/reports", tags=["Institutional Reporting & Tear Sheets"])


@router.get(
    "/fact-sheet/{backtest_id}",
    response_model=StrategyFactSheetPayload,
    status_code=status.HTTP_200_OK,
    summary="Get Strategy Fact Sheet",
    description="Compiles an executive 1-page Strategy Fact Sheet payload from an authorized backtest simulation.",
)
async def get_strategy_fact_sheet(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID (e.g. 'SPY:US' or 'SPY') for active return comparison."),
    ] = None,
) -> StrategyFactSheetPayload:
    return await run_in_threadpool(
        ReportAssemblerService.assemble_fact_sheet,
        backtest_id=backtest_id,
        current_user=current_user,
        db=db,
        benchmark_asset=benchmark_asset,
    )


@router.get(
    "/tear-sheet/{backtest_id}",
    response_model=InstitutionalTearSheetPayload,
    status_code=status.HTTP_200_OK,
    summary="Get Institutional Tear Sheet",
    description="Compiles a comprehensive 2-page Institutional Tear Sheet payload with gross vs net returns, drawdown analysis, TCA, and monthly matrices.",
)
async def get_institutional_tear_sheet(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID for comparative analytics."),
    ] = None,
) -> InstitutionalTearSheetPayload:
    return await run_in_threadpool(
        ReportAssemblerService.assemble_tear_sheet,
        backtest_id=backtest_id,
        current_user=current_user,
        db=db,
        benchmark_asset=benchmark_asset,
    )


@router.post(
    "/research-annex/{experiment_id}",
    response_model=ResearchDiagnosticsAnnexPayload,
    status_code=status.HTTP_200_OK,
    summary="Get Research Diagnostics Annex",
    description="Compiles a 3rd-page research annex with Stage 33 multiple-testing corrections, PBO, DSR, and MinBTL.",
)
async def get_research_diagnostics_annex(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    req: Annotated[
        OverfittingDiagnosticsRequest | None,
        Body(description="Optional candidate run selection and partition settings for overfitting diagnostics."),
    ] = None,
) -> ResearchDiagnosticsAnnexPayload:
    return await run_in_threadpool(
        ReportAssemblerService.assemble_research_annex,
        experiment_id=experiment_id,
        current_user=current_user,
        db=db,
        req=req,
    )


@router.get(
    "/unified/{backtest_id}",
    response_model=InstitutionalReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Unified Institutional Report",
    description="Compiles Fact Sheet, Tear Sheet, and linked Research Annex in a single unified institutional payload.",
)
async def get_unified_institutional_report(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID."),
    ] = None,
    experiment_id: Annotated[
        str | None,
        Query(description="Optional experiment UUID if explicitly bundling research annex with this backtest."),
    ] = None,
) -> InstitutionalReportResponse:
    return await run_in_threadpool(
        ReportAssemblerService.assemble_unified_report,
        backtest_id=backtest_id,
        current_user=current_user,
        db=db,
        benchmark_asset=benchmark_asset,
        experiment_id=experiment_id,
    )
