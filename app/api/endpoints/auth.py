"""Cookie-based authentication for the staff workbench."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from jose import jwt
from pydantic import BaseModel, Field

from app.config.app_config import settings
from app.core.access import (
    AUTH_COOKIE_NAME,
    STAFF_AUDIENCE,
    STAFF_PURPOSE,
    ChatAccess,
    get_signing_key,
    require_staff,
    require_staff_configuration,
)
from app.core.auth import authenticate_user

router = APIRouter(prefix="/auth", tags=["员工认证"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=160)
    password: str = Field(max_length=1024, repr=False)


class StaffUserResponse(BaseModel):
    username: str
    full_name: str | None


class StaffSessionResponse(BaseModel):
    user: StaffUserResponse
    expires_at: datetime
    csrf_token: str


class LogoutResponse(BaseModel):
    success: bool


@router.post("/login", response_model=StaffSessionResponse)
def login(body: LoginRequest, response: Response) -> StaffSessionResponse:
    require_staff_configuration()
    user = authenticate_user(body.username, body.password)
    if user is None or user.disabled:
        raise HTTPException(status_code=401, detail="用户名或密码不正确。")
    expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
        minutes=settings.security.jwt_access_token_exp_minutes
    )
    csrf_token = secrets.token_urlsafe(32)
    token = jwt.encode(
        {
            "sub": user.username,
            "aud": STAFF_AUDIENCE,
            "purpose": STAFF_PURPOSE,
            "role": "staff",
            "csrf": csrf_token,
            "exp": expires_at,
        },
        get_signing_key(),
        algorithm=settings.security.jwt_algorithm,
    )
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.security.jwt_access_token_exp_minutes * 60,
        expires=expires_at,
        path="/api",
        secure=settings.security.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return StaffSessionResponse(
        user=StaffUserResponse(username=user.username, full_name=user.full_name),
        expires_at=expires_at,
        csrf_token=csrf_token,
    )


@router.get("/session", response_model=StaffSessionResponse)
def session(
    response: Response, access: Annotated[ChatAccess, Depends(require_staff)]
) -> StaffSessionResponse:
    assert access.user is not None and access.expires_at is not None and access.csrf_token is not None
    response.headers["Cache-Control"] = "no-store"
    return StaffSessionResponse(
        user=StaffUserResponse(username=access.user.username, full_name=access.user.full_name),
        expires_at=access.expires_at,
        csrf_token=access.csrf_token,
    )


@router.post("/logout", response_model=LogoutResponse, dependencies=[Depends(require_staff)])
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path="/api",
        secure=settings.security.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return LogoutResponse(success=True)
