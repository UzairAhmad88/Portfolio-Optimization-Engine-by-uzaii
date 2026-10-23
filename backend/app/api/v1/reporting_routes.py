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


# =========================================================================
# STAGE 34 GATE D: SECURE SERVER-SIDE PDF EXPORT DISPATCHERS
# =========================================================================

import re
from fastapi import Response
from app.reports.renderer import render_html_to_pdf
from app.reports.pdf_templates import (
    render_fact_sheet_html,
    render_research_annex_html,
    render_tear_sheet_html,
    render_unified_report_html,
)


def _sanitize_filename(prefix: str, name: str | None, resource_id: str) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name or "mandate").strip("_")
    short_id = str(resource_id)[:8]
    return f"{prefix}_{clean_name}_{short_id}.pdf"


def _build_pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
            "Content-Length": str(len(pdf_bytes)),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/fact-sheet/{backtest_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export Strategy Fact Sheet PDF",
    description="Assembles and renders an executive 1-page Strategy Fact Sheet PDF artifact using headless Chromium.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
@router.get(
    "/export/fact-sheet/{backtest_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def export_strategy_fact_sheet_pdf(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID."),
    ] = None,
) -> Response:
    def _generate() -> bytes:
        payload = ReportAssemblerService.assemble_fact_sheet(
            backtest_id=backtest_id,
            current_user=current_user,
            db=db,
            benchmark_asset=benchmark_asset,
        )
        html_doc = render_fact_sheet_html(payload)
        return render_html_to_pdf(html_doc)

    pdf_bytes = await run_in_threadpool(_generate)
    filename = _sanitize_filename("fact_sheet", "strategy", backtest_id)
    return _build_pdf_response(pdf_bytes, filename)


@router.get(
    "/tear-sheet/{backtest_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export Institutional Tear Sheet PDF",
    description="Assembles and renders a comprehensive 2-page Institutional Tear Sheet PDF artifact using headless Chromium.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
@router.get(
    "/export/tear-sheet/{backtest_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def export_institutional_tear_sheet_pdf(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID."),
    ] = None,
) -> Response:
    def _generate() -> bytes:
        payload = ReportAssemblerService.assemble_tear_sheet(
            backtest_id=backtest_id,
            current_user=current_user,
            db=db,
            benchmark_asset=benchmark_asset,
        )
        html_doc = render_tear_sheet_html(payload)
        return render_html_to_pdf(html_doc)

    pdf_bytes = await run_in_threadpool(_generate)
    filename = _sanitize_filename("tear_sheet", "institutional", backtest_id)
    return _build_pdf_response(pdf_bytes, filename)


@router.post(
    "/research-annex/{experiment_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export Research Diagnostics Annex PDF",
    description="Assembles and renders an institutional 1-page Research Diagnostics Annex PDF artifact using headless Chromium.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
@router.post(
    "/export/research-annex/{experiment_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def export_research_diagnostics_annex_pdf(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    req: Annotated[
        OverfittingDiagnosticsRequest | None,
        Body(description="Optional candidate run selection and partition settings."),
    ] = None,
) -> Response:
    def _generate() -> bytes:
        payload = ReportAssemblerService.assemble_research_annex(
            experiment_id=experiment_id,
            current_user=current_user,
            db=db,
            req=req,
        )
        html_doc = render_research_annex_html(payload)
        return render_html_to_pdf(html_doc)

    pdf_bytes = await run_in_threadpool(_generate)
    filename = _sanitize_filename("research_annex", "cscv_diagnostics", experiment_id)
    return _build_pdf_response(pdf_bytes, filename)


@router.get(
    "/unified/{backtest_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export Unified Institutional Dossier PDF",
    description="Assembles and renders a multi-page Unified Institutional Report Dossier (up to 3 pages) using headless Chromium.",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
@router.get(
    "/export/unified/{backtest_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def export_unified_institutional_report_pdf(
    backtest_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    benchmark_asset: Annotated[
        str | None,
        Query(description="Optional benchmark ticker or asset ID."),
    ] = None,
    experiment_id: Annotated[
        str | None,
        Query(description="Optional experiment UUID if explicitly bundling research annex."),
    ] = None,
) -> Response:
    def _generate() -> bytes:
        payload = ReportAssemblerService.assemble_unified_report(
            backtest_id=backtest_id,
            current_user=current_user,
            db=db,
            benchmark_asset=benchmark_asset,
            experiment_id=experiment_id,
        )
        html_doc = render_unified_report_html(payload)
        return render_html_to_pdf(html_doc)

    pdf_bytes = await run_in_threadpool(_generate)
    filename = _sanitize_filename("institutional_dossier", "complete", backtest_id)
    return _build_pdf_response(pdf_bytes, filename)
