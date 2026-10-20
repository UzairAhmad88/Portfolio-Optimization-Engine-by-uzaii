"""
FastAPI REST routes for Multi-Asset Performance Attribution,
Brinson-Fachler Decomposition & Systematic Factor Risk Attribution.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.performance_attribution.models import (
    BrinsonAttributionRequest,
    BrinsonAttributionResponse,
    FactorAttributionRequest,
    FactorAttributionResponse,
)
from app.performance_attribution.service import (
    execute_brinson_attribution,
    execute_factor_attribution,
)

router = APIRouter(prefix="/attribution", tags=["Performance Attribution"])


@router.post(
    "/brinson",
    response_model=BrinsonAttributionResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute multi-period Brinson-Fachler active return attribution",
)
def compute_brinson_attribution(
    request: BrinsonAttributionRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> BrinsonAttributionResponse:
    """
    Decomposes active portfolio excess return into Allocation Effect,
    Selection Effect, and Interaction Effect with Cariño multi-period linking.
    """
    return execute_brinson_attribution(request, current_user, db)


@router.post(
    "/factor",
    response_model=FactorAttributionResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute systematic Barra factor active risk and return attribution",
)
def compute_systematic_factor_attribution(
    request: FactorAttributionRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FactorAttributionResponse:
    """
    Decomposes active portfolio return and active tracking variance into
    systematic factor risk contributions and idiosyncratic selection alpha.
    """
    return execute_factor_attribution(request, current_user, db)
