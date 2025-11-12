"""JWT-based authentication utilities for API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_password_hash, verify_password


class APIUser(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: bool = False


class APIUserInDB(APIUser):
    hashed_password: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _seed_users() -> Dict[str, APIUserInDB]:
    username = settings.security.api_default_username
    password = settings.security.api_default_password
    return {
        username: APIUserInDB(
            username=username,
            full_name=settings.security.api_default_fullname,
            hashed_password=get_password_hash(password),
            disabled=False,
        )
    }


_users_db: Dict[str, APIUserInDB] = _seed_users()


def authenticate_user(username: str, password: str) -> Optional[APIUserInDB]:
    user = _users_db.get(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.security.jwt_access_token_exp_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.security.jwt_secret_key,
        algorithm=settings.security.jwt_algorithm,
    )


def _decode_token(token: str) -> APIUserInDB:
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
    except JWTError:
        raise credentials_exception
    user = _users_db.get(username)
    if user is None:
        raise credentials_exception
    return user


def get_current_user(token: str = Depends(oauth2_scheme)) -> APIUserInDB:
    return _decode_token(token)


def get_current_active_user(current_user: APIUserInDB = Depends(get_current_user)) -> APIUser:
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
    "get_current_active_user",
    "oauth2_scheme",
]
