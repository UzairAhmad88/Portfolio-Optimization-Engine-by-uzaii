"""
FastAPI router for portfolio research experiments, reproducible run execution,
and multi-strategy comparison.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.research.models import (
    ComparisonRequest,
    ComparisonResponse,
    ExperimentCreateRequest,
    ExperimentListItem,
    ExperimentResponse,
    ExperimentRunListItem,
    ExperimentRunResponse,
    ExperimentUpdateRequest,
)
from app.research.overfitting_models import (
    OverfittingDiagnosticsRequest,
    OverfittingDiagnosticsResponse,
)
from app.research.service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["Portfolio Research Experiments"])


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new research experiment definition",
)
async def create_experiment_endpoint(
    request: ExperimentCreateRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExperimentResponse:
    try:
        return await run_in_threadpool(
            ResearchService.create_experiment,
            req=request,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in create_experiment: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error creating research experiment.",
        )


@router.get(
    "/experiments",
    response_model=list[ExperimentListItem],
    status_code=status.HTTP_200_OK,
    summary="List all research experiments for authenticated user",
)
async def list_experiments_endpoint(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ExperimentListItem]:
    try:
        return await run_in_threadpool(
            ResearchService.list_experiments,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in list_experiments: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error listing research experiments.",
        )


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an owned research experiment by ID",
)
async def get_experiment_endpoint(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExperimentResponse:
    try:
        return await run_in_threadpool(
            ResearchService.get_experiment,
            experiment_id=experiment_id,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in get_experiment: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving research experiment.",
        )


@router.patch(
    "/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update research experiment metadata or configuration",
)
async def update_experiment_endpoint(
    experiment_id: str,
    request: ExperimentUpdateRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExperimentResponse:
    try:
        return await run_in_threadpool(
            ResearchService.update_experiment,
            experiment_id=experiment_id,
            req=request,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in update_experiment: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error updating research experiment.",
        )


@router.delete(
    "/experiments/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an owned research experiment and its runs",
)
async def delete_experiment_endpoint(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        await run_in_threadpool(
            ResearchService.delete_experiment,
            experiment_id=experiment_id,
            user=current_user,
            db=session,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in delete_experiment: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error deleting research experiment.",
        )


@router.post(
    "/experiments/{experiment_id}/runs",
    response_model=ExperimentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a research experiment run (non-destructive rerun)",
)
async def execute_run_endpoint(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExperimentRunResponse:
    try:
        return await run_in_threadpool(
            ResearchService.execute_experiment_run,
            experiment_id=experiment_id,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in execute_run: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error executing research run.",
        )


@router.get(
    "/experiments/{experiment_id}/runs",
    response_model=list[ExperimentRunListItem],
    status_code=status.HTTP_200_OK,
    summary="List all executions for an owned research experiment",
)
async def list_runs_endpoint(
    experiment_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ExperimentRunListItem]:
    try:
        return await run_in_threadpool(
            ResearchService.list_experiment_runs,
            experiment_id=experiment_id,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in list_runs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error listing research runs.",
        )


@router.get(
    "/runs/{run_id}",
    response_model=ExperimentRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an individual research run by ID",
)
async def get_run_endpoint(
    run_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExperimentRunResponse:
    try:
        return await run_in_threadpool(
            ResearchService.get_experiment_run,
            run_id=run_id,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in get_run: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving research run.",
        )


@router.post(
    "/comparisons",
    response_model=ComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare compatible completed research experiment runs",
)
async def compare_runs_endpoint(
    request: ComparisonRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ComparisonResponse:
    try:
        return await run_in_threadpool(
            ResearchService.compare_experiment_runs,
            req=request,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in compare_runs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error comparing research runs.",
        )


@router.post(
    "/experiments/{experiment_id}/overfitting-diagnostics",
    response_model=OverfittingDiagnosticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute backtest overfitting diagnostics (CSCV, PBO, DSR, MinBTL) across experiment runs",
)
async def compute_overfitting_diagnostics_endpoint(
    experiment_id: str,
    request: OverfittingDiagnosticsRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> OverfittingDiagnosticsResponse:
    try:
        return await run_in_threadpool(
            ResearchService.compute_experiment_overfitting,
            experiment_id=experiment_id,
            req=request,
            user=current_user,
            db=session,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected error in compute_overfitting_diagnostics: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error computing overfitting diagnostics.",
        )

