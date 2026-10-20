from __future__ import annotations

import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.v1.auth_routes import router as auth_router
from app.api.v1.backtesting_routes import router as backtesting_router
from app.api.v1.black_litterman_routes import router as black_litterman_router
from app.api.v1.factor_routes import router as factor_router
from app.api.v1.execution_routes import router as execution_router
from app.api.v1.regime_switching_routes import router as regime_switching_router
from app.api.v1.attribution_routes import router as attribution_router
from app.api.v1.copula_routes import router as copula_router
from app.api.v1.multi_asset_routes import router as multi_asset_router
from app.api.v1.performance_routes import router as performance_router
from app.api.v1.research_routes import router as research_router
from app.api.v1.risk_parity_routes import router as risk_parity_router
from app.api.v1.robust_routes import router as robust_router
from app.api.v1.risk_simulation_routes import router as risk_simulation_router
from app.api.v1.scenario_routes import router as scenario_router
from app.api.v1.schemas import (
    CorporateActionCreate,
    CorporateActionResponse,
    DatasetAssetsResponse,
    DatasetMetadataResponse,
    DatasetQuery,
    DatasetQueryResponse,
    ErrorResponse,
    ExchangeCalendarResponse,
    HealthResponse,
    QualityAuditResponse,
    ValidationReportResponse,
)
from app.auth.dependencies import check_dataset_access, get_current_active_user
from app.db.models import UserModel
from app.db.session import engine, get_db
from app.market_data.service import (
    DatasetNotFoundError,
    add_corporate_actions_service,
    audit_dataset_quality_service,
    get_calendar_sessions_service,
    get_dataset_metadata,
    list_all_datasets,
    query_corporate_actions_service,
    query_dataset,
    register_csv_dataset,
    validate_csv,
)
from app.portfolio.models import (
    EfficientFrontierRequest,
    EfficientFrontierResponse,
    OptimizationRequest,
    OptimizationResponse,
    PortfolioComparisonRequest,
    PortfolioComparisonResponse,
    PortfolioDefinition,
    PortfolioValidationReport,
)
from app.portfolio.optimization_service import (
    execute_efficient_frontier,
    execute_portfolio_comparison,
    execute_portfolio_optimization,
)
from app.portfolio.service import (
    get_dataset_assets,
    validate_portfolio_definition,
)

router = APIRouter()

# Mount authentication and identity management routes
router.include_router(auth_router)

# Mount backtesting and simulation routes
router.include_router(backtesting_router)

# Mount scenario analysis and stress testing routes
router.include_router(scenario_router)

# Mount risk simulation and Monte Carlo routes
router.include_router(risk_simulation_router)

# Mount performance attribution and benchmark analysis routes
router.include_router(performance_router)

# Mount portfolio research experiments and strategy comparison routes
router.include_router(research_router)

# Mount robust portfolio optimization and estimation uncertainty routes
router.include_router(robust_router)

# Mount Black-Litterman portfolio optimization and Bayesian view routes
router.include_router(black_litterman_router)

# Mount Risk Parity and Hierarchical Risk Parity routes
router.include_router(risk_parity_router)

# Mount Factor Investing and Systematic Risk Decomposition routes
router.include_router(factor_router)

# Mount Multi-Asset Class Allocation and FX Hedging routes
router.include_router(multi_asset_router)

# Mount Optimal Execution and Market Impact Modeling routes
router.include_router(execution_router)

# Mount Regime-Switching HMM and Volatility Targeting routes
router.include_router(regime_switching_router)

# Mount Multi-Asset Performance Attribution and Systematic Factor Risk Attribution routes
router.include_router(attribution_router)

# Mount Copula Tail Risk and Tail Risk Parity routes
router.include_router(copula_router)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns current operational status, database connectivity, and active development stage milestone.",
)
def health() -> dict:
    db_status = "connected"
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"
    return {"status": "ok", "stage": "copula_tail_risk", "database": db_status}


@router.get(
    "/market-data/datasets",
    response_model=list[DatasetMetadataResponse],
    summary="List Registered Datasets",
    description="Retrieves a list of persistent datasets accessible to the authenticated researcher, ordered by creation date descending.",
)
def list_datasets_route(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    limit: int = 100,
    offset: int = 0,
):
    return list_all_datasets(
        limit=limit,
        offset=offset,
        user_id=current_user.id,
        is_admin=(current_user.role == "admin"),
    )


async def _read_upload(file: UploadFile) -> bytes:
    # Application-level cap. Reverse proxy/server request limits are also required in deployment.
    max_bytes = 10 * 1024 * 1024
    try:
        data = await file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=413, detail="CSV exceeds the 10 MB upload limit."
            )
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=415, detail="Upload a .csv file.")
        return data
    finally:
        await file.close()


@router.post(
    "/market-data/preview",
    response_model=ValidationReportResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Malformed CSV or missing required columns.",
        },
        413: {"model": ErrorResponse, "description": "File size exceeds upload limit."},
        415: {
            "model": ErrorResponse,
            "description": "Unsupported media type; must be a .csv file.",
        },
    },
    summary="Preview and Validate CSV",
    description=(
        "Validates an uploaded historical market data CSV file and returns a detailed data-quality "
        "report with accepted rows, rejected rows, errors, and warnings without registering the dataset in memory."
    ),
)
async def preview_csv(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
):
    raw = await _read_upload(file)
    try:
        return await run_in_threadpool(validate_csv, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/market-data/uploads",
    response_model=DatasetMetadataResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Malformed CSV or missing required columns.",
        },
        413: {"model": ErrorResponse, "description": "File size exceeds upload limit."},
        415: {
            "model": ErrorResponse,
            "description": "Unsupported media type; must be a .csv file.",
        },
        422: {
            "model": ValidationReportResponse,
            "description": "Validation failed with zero accepted rows.",
        },
    },
    summary="Upload and Register CSV Dataset",
    description=(
        "Validates and registers accepted price bars in the persistent dataset repository. "
        "Associates the dataset with the authenticated researcher. Returns HTTP 422 if no valid rows remain."
    ),
)
async def upload_csv(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
):
    raw = await _read_upload(file)
    clean_filename = os.path.basename(file.filename or "upload.csv")
    try:
        result = await run_in_threadpool(
            register_csv_dataset,
            raw,
            filename=clean_filename,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result["valid_rows"] == 0:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post(
    "/market-data/datasets/query",
    response_model=DatasetQueryResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Dataset ID not found in registry.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Invalid query parameters (e.g. start_date > end_date).",
        },
    },
    summary="Query Registered Dataset",
    description="Filters an authorized registered dataset by inclusive date range, optional ticker list, and market identifier.",
)
def query_market_data(
    request: DatasetQuery,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=422, detail="start_date must be on or before end_date."
        )
    check_dataset_access(session, request.dataset_id, current_user)
    try:
        return query_dataset(
            dataset_id=request.dataset_id,
            start_date=request.start_date,
            end_date=request.end_date,
            tickers=request.tickers,
            market=request.market,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/market-data/datasets/{dataset_id}",
    response_model=DatasetMetadataResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Dataset ID not found in registry.",
        },
    },
    summary="Get Dataset Metadata",
    description="Retrieves registration metadata, row counts, and validation summary for an authorized stored dataset.",
)
def dataset_metadata(
    dataset_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, dataset_id, current_user)
    try:
        return get_dataset_metadata(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/market-data/datasets/{dataset_id}/assets",
    response_model=DatasetAssetsResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Dataset ID not found in registry.",
        },
    },
    summary="List Available Assets in Dataset",
    description="Extracts unique assets, markets, trading currencies, date ranges, and bar counts from an authorized registered dataset.",
)
def list_dataset_assets(
    dataset_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, dataset_id, current_user)
    try:
        assets = get_dataset_assets(dataset_id)
        return {
            "dataset_id": dataset_id,
            "asset_count": len(assets),
            "assets": [a.model_dump() for a in assets],
        }
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/market-data/corporate-actions",
    response_model=list[CorporateActionResponse],
    summary="Register Corporate Actions",
    description="Registers canonical corporate action events (splits, reverse splits, dividends) for an asset or dataset.",
)
def create_corporate_actions_route(
    actions: list[CorporateActionCreate],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    for a in actions:
        if a.dataset_id:
            check_dataset_access(session, a.dataset_id, current_user)
    action_dicts = [a.model_dump() for a in actions]
    return add_corporate_actions_service(action_dicts)


@router.get(
    "/market-data/corporate-actions",
    response_model=list[CorporateActionResponse],
    summary="Query Corporate Actions",
    description="Queries corporate actions with optional asset_id, dataset_id, and point-in-time cutoff.",
)
def query_corporate_actions_route(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    asset_id: str | None = None,
    dataset_id: str | None = None,
    as_of_date: date | None = None,
    strict_pit: bool = False,
):
    if dataset_id:
        check_dataset_access(session, dataset_id, current_user)
    return query_corporate_actions_service(
        asset_id=asset_id,
        dataset_id=dataset_id,
        as_of_date=as_of_date,
        strict_pit=strict_pit,
    )


@router.post(
    "/market-data/datasets/{dataset_id}/quality-audit",
    response_model=QualityAuditResponse,
    summary="Run Dataset Quality Audit",
    description="Executes deterministic quality audit inspecting OHLC inversions, non-positive prices, missing sessions, discontinuities, and stale prices.",
)
def audit_dataset_quality_route(
    dataset_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    discontinuity_threshold: float = 0.35,
    stale_limit_days: int = 10,
):
    check_dataset_access(session, dataset_id, current_user)
    try:
        return audit_dataset_quality_service(
            dataset_id=dataset_id,
            discontinuity_threshold=discontinuity_threshold,
            stale_limit_days=stale_limit_days,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/market-data/calendars/{market}/sessions",
    response_model=ExchangeCalendarResponse,
    summary="Query Exchange Calendar Sessions",
    description="Returns open trading sessions and documented holidays for US or PSX exchanges within a date range.",
)
def get_calendar_sessions_route(
    market: str,
    start_date: date,
    end_date: date,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
):
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    try:
        return get_calendar_sessions_service(
            market=market,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/portfolios/validate",
    response_model=PortfolioValidationReport,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access referenced dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Referenced dataset ID not found in registry.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Malformed portfolio definition payload.",
        },
    },
    summary="Validate Portfolio Definition and Constraints",
    description=(
        "Validates a portfolio configuration against an authorized registered dataset, verifying asset existence, "
        "historical date coverage, currency homogeneity, and mathematical constraint feasibility."
    ),
)
async def validate_portfolio(
    portfolio: PortfolioDefinition,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, portfolio.dataset_id, current_user)
    report = await run_in_threadpool(validate_portfolio_definition, portfolio)
    return report


@router.post(
    "/portfolios/optimize",
    response_model=OptimizationResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access referenced dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Referenced dataset ID not found in registry.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Optimization failed due to infeasible constraints, non-positive excess returns, or solver failure.",
        },
    },
    summary="Optimize Portfolio Allocation",
    description=(
        "Solves a mathematical portfolio optimization problem (Minimum-Variance, Maximum-Sharpe, or Equal-Weight) "
        "using historical prices from an authorized dataset, synchronized returns, and verified investment constraints via SciPy SLSQP."
    ),
)
async def optimize_portfolio_route(
    request: OptimizationRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, request.portfolio.dataset_id, current_user)
    result = await run_in_threadpool(execute_portfolio_optimization, request)
    if not result.is_success:
        if any("not found" in err.lower() for err in result.errors):
            raise HTTPException(status_code=404, detail=result.errors[0])
        raise HTTPException(status_code=422, detail=result.model_dump())
    return result


@router.post(
    "/portfolios/efficient-frontier",
    response_model=EfficientFrontierResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access referenced dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Referenced dataset ID not found in registry.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Frontier computation failed due to infeasible constraints or solver failure.",
        },
    },
    summary="Generate Efficient Frontier",
    description=(
        "Computes the Markowitz efficient frontier curve for an authorized portfolio under user-configured investment constraints. "
        "Solves target-return quadratic optimization problems using SciPy SLSQP, classifying points into efficient, "
        "dominated, and infeasible targets."
    ),
)
async def efficient_frontier_route(
    request: EfficientFrontierRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, request.portfolio.dataset_id, current_user)
    result = await run_in_threadpool(execute_efficient_frontier, request)
    if not result.is_success:
        if any("not found" in err.lower() for err in result.errors):
            raise HTTPException(status_code=404, detail=result.errors[0])
        raise HTTPException(status_code=422, detail=result.model_dump())
    return result


@router.post(
    "/portfolios/compare",
    response_model=PortfolioComparisonResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: user does not own or have permission to access referenced dataset.",
        },
        404: {
            "model": ErrorResponse,
            "description": "Referenced dataset ID not found in registry.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Comparison failed due to missing portfolios or data invalidity.",
        },
    },
    summary="Compare Portfolio Allocations",
    description=(
        "Performs side-by-side performance and risk analytics comparison across Global Minimum-Variance, "
        "Maximum Sharpe Ratio, Equal-Weight, and custom user-specified portfolio allocations on an authorized dataset."
    ),
)
async def compare_portfolios_route(
    request: PortfolioComparisonRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
):
    check_dataset_access(session, request.portfolio.dataset_id, current_user)
    result = await run_in_threadpool(execute_portfolio_comparison, request)
    if not result.is_success:
        if any("not found" in err.lower() for err in result.errors):
            raise HTTPException(status_code=404, detail=result.errors[0])
        raise HTTPException(status_code=422, detail=result.model_dump())
    return result
