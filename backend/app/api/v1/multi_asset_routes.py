"""
API Routes for Multi-Asset Class Allocation, Cash Drag & Multi-Currency FX Hedging.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.multi_asset.models import (
    MultiAssetBacktestRequest,
    MultiAssetBacktestResponse,
    MultiAssetOptimizeRequest,
    MultiAssetOptimizeResponse,
)
from app.multi_asset.service import (
    execute_multi_asset_backtest,
    execute_multi_asset_optimization,
)

router = APIRouter(prefix="/multi-asset", tags=["Multi-Asset Allocation & FX Hedging"])


@router.post(
    "/optimize",
    response_model=MultiAssetOptimizeResponse,
    summary="Optimize multi-asset allocation under class limits and cash buffers",
    description="Solves hierarchical asset-class allocations, cash drag requirements, and FX risk decomposition.",
)
def optimize_multi_asset(
    request: MultiAssetOptimizeRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MultiAssetOptimizeResponse:
    return execute_multi_asset_optimization(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/backtest",
    response_model=MultiAssetBacktestResponse,
    summary="Walk-forward backtest for multi-asset class portfolio",
    description="Simulates chronological walk-forward rebalancing with currency conversions, cash yield accrual, and weight drift.",
)
def backtest_multi_asset(
    request: MultiAssetBacktestRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MultiAssetBacktestResponse:
    return execute_multi_asset_backtest(
        request=request,
        current_user=current_user,
        db=db,
    )
