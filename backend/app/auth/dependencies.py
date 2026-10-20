"""
FastAPI dependency injectors for user authentication, role-based authorization,
and dataset access control.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.auth.service import get_user_by_id
from app.db.models import DatasetModel, UserModel
from app.db.session import get_db
from app.market_data import repository

logger = logging.getLogger("app.auth.dependencies")

# System fallback user used only when AUTH_REQUIRED=false is explicitly configured for offline test suites
SYSTEM_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
SYSTEM_DEV_USER = UserModel(
    id=SYSTEM_DEV_USER_ID,
    email="system.researcher@quantengine.local",
    hashed_password="",
    full_name="System Default Researcher",
    role="researcher",
    is_active=True,
)


def is_auth_required() -> bool:
    """
    Checks if authentication enforcement is enabled (default: True).
    Can be set to false via AUTH_REQUIRED=false for unauthenticated legacy test suites.
    """
    return os.environ.get("AUTH_REQUIRED", "true").lower() in ("true", "1", "yes")


def extract_token(request: Request) -> str | None:
    """
    Extracts the authentication token from either:
    1. 'Authorization: Bearer <token>' header (explicit client header, takes precedence).
    2. HttpOnly 'access_token' cookie (ambient browser session).
    """
    # 1. Check Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. Check HttpOnly cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None


def get_current_user(
    request: Request,
    session: Session = Depends(get_db),
) -> UserModel:
    """
    Authenticates the incoming request by verifying JWT credentials.
    Returns the corresponding UserModel or raises HTTP 401 Unauthorized.
    """
    token = extract_token(request)

    if not token:
        if not is_auth_required():
            return SYSTEM_DEV_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid token presented: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    """
    Verifies that the authenticated user account is active.
    Raises HTTP 403 Forbidden if the account has been disabled.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled. Please contact the administrator.",
        )
    return current_user


def require_role(*allowed_roles: str) -> Callable[[UserModel], UserModel]:
    """
    Dependency factory that restricts endpoint access to specified roles.
    Admins are always authorized.
    """

    def role_checker(
        user: UserModel = Depends(get_current_active_user),
    ) -> UserModel:
        if user.role == "admin" or user.role in allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires one of the following roles: {', '.join(allowed_roles)}.",
        )

    return role_checker


def check_dataset_access(
    session: Session, dataset_id: str, user: UserModel
) -> DatasetModel:
    """
    Enforces dataset tenant isolation and ownership rules:
    - User owns the dataset: Granted.
    - Dataset is shared: Granted.
    - Dataset has no owner (system/legacy): Granted.
    - User is admin: Granted.
    - Otherwise: HTTP 403 Forbidden.
    """
    dataset = repository.get_dataset_by_id(session, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found in persistent storage or registry.",
        )

    if (
        dataset.user_id is None
        or dataset.is_shared
        or dataset.user_id == user.id
        or user.role == "admin"
    ):
        return dataset

    logger.warning(
        "Unauthorized access attempt to dataset %s by user %s (owner: %s)",
        dataset_id,
        user.id,
        dataset.user_id,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this private dataset.",
    )
