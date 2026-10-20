"""
User account lifecycle, password verification, and authentication services.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas import UserLoginRequest, UserRegisterRequest
from app.auth.security import hash_password, rate_limiter, verify_password
from app.db.models import UserModel

logger = logging.getLogger("app.auth.service")


class UserAlreadyExistsError(ValueError):
    """Raised when registering an email address that is already registered."""


class AuthenticationError(ValueError):
    """Raised when authentication credentials (email/password) are invalid."""


class AccountDisabledError(ValueError):
    """Raised when attempting to authenticate an inactive or disabled account."""


class RateLimitExceededError(ValueError):
    """Raised when too many failed authentication attempts trigger a temporary lockout."""


def register_user(session: Session, req: UserRegisterRequest) -> UserModel:
    """
    Creates a new user record with a cryptographic bcrypt password hash.
    Ensures email uniqueness and safe transaction commitment.
    """
    norm_email = req.email.strip().lower()

    # Check for existing user by normalized email
    stmt = select(UserModel).where(UserModel.email == norm_email)
    existing = session.scalars(stmt).first()
    if existing is not None:
        raise UserAlreadyExistsError(f"An account with email '{norm_email}' is already registered.")

    hashed_pw = hash_password(req.password)
    user = UserModel(
        id=str(uuid4()),
        email=norm_email,
        hashed_password=hashed_pw,
        full_name=req.full_name.strip() if req.full_name else None,
        role=req.role,
        is_active=True,
    )

    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info("Successfully registered user id=%s email=%s role=%s", user.id, user.email, user.role)
    return user


def authenticate_user(
    session: Session, req: UserLoginRequest, client_identifier: str = ""
) -> UserModel:
    """
    Authenticates a user by email and password with brute-force rate-limiting.
    Returns the authenticated UserModel or raises an exception.
    """
    rate_key = f"{client_identifier}:{req.email}" if client_identifier else req.email

    if rate_limiter.is_locked_out(rate_key):
        logger.warning("Authentication blocked by rate limit for identifier: %s", rate_key)
        raise RateLimitExceededError(
            "Too many failed login attempts. Account access is temporarily locked. "
            "Please wait 5 minutes before trying again."
        )

    norm_email = req.email.strip().lower()
    stmt = select(UserModel).where(UserModel.email == norm_email)
    user = session.scalars(stmt).first()

    if user is None or not verify_password(req.password, user.hashed_password):
        failures = rate_limiter.record_failure(rate_key)
        logger.warning(
            "Failed login attempt for email: %s (failure count: %d)", norm_email, failures
        )
        raise AuthenticationError("Invalid email or password.")

    if not user.is_active:
        logger.warning("Login attempt for inactive user id=%s email=%s", user.id, user.email)
        raise AccountDisabledError("User account is disabled. Please contact the administrator.")

    # Successful authentication resets failed attempts
    rate_limiter.reset(rate_key)
    user.last_login_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)
    logger.info("User authenticated successfully id=%s email=%s", user.id, user.email)
    return user


def get_user_by_id(session: Session, user_id: str) -> UserModel | None:
    """
    Retrieves a user by stable UUID primary key.
    """
    return session.get(UserModel, user_id)


def get_user_by_email(session: Session, email: str) -> UserModel | None:
    """
    Retrieves a user by normalized unique email.
    """
    norm_email = email.strip().lower()
    stmt = select(UserModel).where(UserModel.email == norm_email)
    return session.scalars(stmt).first()
