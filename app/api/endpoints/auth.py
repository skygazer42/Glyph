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
    """工作人员登录凭据请求；密码不出现在模型 repr 中。"""

    username: str = Field(max_length=160)
    password: str = Field(max_length=1024, repr=False)


class StaffUserResponse(BaseModel):
    """返回已认证工作人员的公开身份信息，不包含凭据。"""

    username: str
    full_name: str | None


class StaffSessionResponse(BaseModel):
    """向客户端返回当前工作人员身份、到期时间和 CSRF 令牌。"""

    user: StaffUserResponse
    expires_at: datetime
    csrf_token: str


class LogoutResponse(BaseModel):
    """表示服务端已生成清除登录 Cookie 的响应。"""

    success: bool


@router.post("/login", response_model=StaffSessionResponse)
def login(body: LoginRequest, response: Response) -> StaffSessionResponse:
    """验证工作人员凭据并设置登录 Cookie，返回身份、到期时间和 CSRF 令牌；凭据无效返回 401。"""
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
    """返回经依赖校验的当前工作人员会话信息，并禁止响应缓存。"""
    assert access.user is not None and access.expires_at is not None and access.csrf_token is not None
    response.headers["Cache-Control"] = "no-store"
    return StaffSessionResponse(
        user=StaffUserResponse(username=access.user.username, full_name=access.user.full_name),
        expires_at=access.expires_at,
        csrf_token=access.csrf_token,
    )


@router.post("/logout", response_model=LogoutResponse, dependencies=[Depends(require_staff)])
def logout(response: Response) -> LogoutResponse:
    """清除客户端登录 Cookie；不撤销此前已签发的令牌。"""
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path="/api",
        secure=settings.security.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return LogoutResponse(success=True)
