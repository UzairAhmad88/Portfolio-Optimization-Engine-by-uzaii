"""
Pydantic schemas for authentication requests, user registrations, and identity responses.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserRegisterRequest(BaseModel):
    """
    Payload for creating a new named researcher or admin account.
    """

    email: str = Field(..., description="User email address (case-insensitive).")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must contain at least 8 characters, including upper, lower, and digit.",
    )
    full_name: str | None = Field(
        None, max_length=150, description="Optional full name or display name."
    )
    role: Literal["researcher", "admin"] = Field(
        default="researcher", description="Assigned role: researcher or admin."
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned or not EMAIL_REGEX.match(cleaned):
            raise ValueError("A valid email address is required.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one numeric digit.")
        return v


class UserLoginRequest(BaseModel):
    """
    Payload for authenticating with email and password.
    """

    email: str = Field(..., description="User email address.")
    password: str = Field(..., description="Plaintext password.")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    """
    Safe public user identity representation. Never discloses password hashes or secret salt.
    """

    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """
    Authentication response returning the access token and user identity.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthMessageResponse(BaseModel):
    """
    Generic message response for authentication status (e.g. logout confirmation).
    """

    detail: str
