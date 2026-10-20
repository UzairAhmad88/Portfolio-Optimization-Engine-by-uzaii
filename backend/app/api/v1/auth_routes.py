"""
API endpoints for authentication, user registration, session termination, and identity verification.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.auth.schemas import (
    AuthMessageResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.auth.security import create_access_token
from app.auth.service import (
    AccountDisabledError,
    AuthenticationError,
    RateLimitExceededError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)
from app.db.models import UserModel
from app.db.session import get_db

logger = logging.getLogger("app.api.v1.auth")
router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User Account",
    description="Registers a new named researcher or administrator account with a hashed password.",
    responses={
        409: {"description": "Email address already registered."},
        422: {"description": "Password or email validation failed."},
    },
)
def register_user_endpoint(
    request: UserRegisterRequest,
    session: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        user = register_user(session, request)
        return UserResponse.model_validate(user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User and Create Session",
    description="Validates user credentials, returns a JWT bearer token, and sets a secure HttpOnly session cookie.",
    responses={
        401: {"description": "Invalid email or password."},
        403: {"description": "Account is disabled."},
        429: {"description": "Too many failed attempts; account temporarily locked."},
    },
)
def login_endpoint(
    login_req: UserLoginRequest,
    raw_request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    try:
        user = authenticate_user(session, login_req, client_identifier=client_ip)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AccountDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    access_token = create_access_token(
        subject=user.id,
        claims={"email": user.email, "role": user.role},
    )

    # Configure HttpOnly cookie for web browser session security
    is_secure = os.environ.get("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=3600 * 24,  # 24 hours
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=AuthMessageResponse,
    summary="Log Out User",
    description="Invalidates client session by clearing the HttpOnly access token cookie.",
)
def logout_endpoint(response: Response) -> AuthMessageResponse:
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return AuthMessageResponse(detail="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="Returns the identity and role profile of the currently authenticated user.",
    responses={
        401: {"description": "Unauthenticated or invalid/expired session."},
        403: {"description": "User account is disabled."},
    },
)
def get_current_user_profile(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)
