"""JWT-based authentication utilities for API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config.app_config import settings
from app.core.security import get_password_hash, verify_password


class APIUser(BaseModel):
    """API 使用的账号身份，不包含密码散列。"""

    username: str
    full_name: Optional[str] = None
    disabled: bool = False


class APIUserInDB(APIUser):
    """认证时使用的内部账号记录，包含可验证的密码散列。"""

    hashed_password: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _seed_users() -> Dict[str, APIUserInDB]:
    """从当前配置构造默认账号快照；账号或密码缺失时返回空映射。"""
    username = settings.security.api_default_username
    password = settings.security.api_default_password
    if not username or not password:
        return {}
    return {
        username: APIUserInDB(
            username=username,
            full_name=settings.security.api_default_fullname,
            hashed_password=get_password_hash(password),
            disabled=False,
        )
    }


_users_db: Dict[str, APIUserInDB] = _seed_users()


def get_api_user(username: str) -> Optional[APIUserInDB]:
    """读取启动时构造的内存账号记录；未找到时返回 None。"""
    return _users_db.get(username)


def authenticate_user(username: str, password: str) -> Optional[APIUserInDB]:
    """验证用户名和密码，失败返回 None；是否禁用由后续访问依赖检查。"""
    user = get_api_user(username)
    if user is None:
        # Keep unknown usernames on the same password-derivation path.
        get_password_hash(password, salt="missing-api-user")
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """复制声明并写入 UTC 到期时间后签名；未指定有效期时采用配置值。"""
    if not settings.security.jwt_secret_key:
        raise HTTPException(status_code=503, detail="认证签名密钥未配置，请设置 SECURITY__JWT_SECRET_KEY。")
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.security.jwt_access_token_exp_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.security.jwt_secret_key,
        algorithm=settings.security.jwt_algorithm,
    )


def _decode_token(token: str) -> APIUserInDB:
    """验证 Bearer JWT 并查找内存账号；令牌或账号无效时抛出 HTTP 401。"""
    if not settings.security.jwt_secret_key:
        raise HTTPException(status_code=503, detail="认证签名密钥未配置，请设置 SECURITY__JWT_SECRET_KEY。")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.security.jwt_secret_key,
            algorithms=[settings.security.jwt_algorithm],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    user = _users_db.get(username)
    if user is None:
        raise credentials_exception
    return user


def get_current_user(token: str = Depends(oauth2_scheme)) -> APIUserInDB:
    """OAuth2 依赖入口，解析 Bearer 令牌并返回内部账号记录。"""
    return _decode_token(token)


def get_current_active_user(current_user: APIUserInDB = Depends(get_current_user)) -> APIUser:
    """拒绝已禁用账号，向依赖方提供当前可用的 API 身份。"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def _optional_oauth_token(request: Request) -> Optional[str]:
    """Return Bearer token if present; allow missing token when auth is disabled."""
    if settings.security.disable_auth:
        return None
    return await oauth2_scheme(request)


async def get_current_user_or_dummy(
    token: Optional[str] = Depends(_optional_oauth_token),
) -> APIUser:
    """
    Dependency used by API endpoints.

    When SECURITY__DISABLE_AUTH=true, bypass JWT validation and return a dummy user.
    Otherwise, enforce JWT auth via the regular flow.
    """
    if settings.security.disable_auth:
        return APIUser(username="auth-disabled", full_name="Auth Disabled", disabled=False)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _decode_token(token)
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


__all__ = [
    "APIUser",
    "APIUserInDB",
    "authenticate_user",
    "create_access_token",
    "get_api_user",
    "get_current_active_user",
    "oauth2_scheme",
]
