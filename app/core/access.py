"""Staff cookie authentication and access to individual consultation sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from app.config.app_config import settings
from app.core.auth import APIUser, get_api_user

AUTH_COOKIE_NAME = "glyph_staff_session"
STAFF_AUDIENCE = "staff"
STAFF_PURPOSE = "staff_session"
PUBLIC_AUDIENCE = "consultation"
_PLACEHOLDER_PATTERN = re.compile(r"session_[A-Za-z0-9_-]+")
_PUBLIC_SESSION_PATTERN = re.compile(
    r"public:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_CSRF_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}")


@dataclass(frozen=True)
class ChatAccess:
    user: APIUser | None = None
    expires_at: datetime | None = None
    csrf_token: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.user is not None

    @property
    def namespace(self) -> str:
        if self.user is None:
            return "public:"
        owner = hashlib.sha256(self.user.username.encode("utf-8")).hexdigest()[:24]
        return f"staff:{owner}:"


@dataclass(frozen=True)
class ChatSessionKey:
    storage_id: str
    client_id: str


def get_signing_key() -> str:
    secret = settings.security.jwt_secret_key
    if not secret or len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="认证尚未配置：请设置至少 32 字节的 SECURITY__JWT_SECRET_KEY。",
        )
    if settings.security.jwt_algorithm not in {"HS256", "HS384", "HS512"}:
        raise HTTPException(
            status_code=503,
            detail="SECURITY__JWT_ALGORITHM 必须为 HS256、HS384 或 HS512。",
        )
    return secret


def require_staff_configuration() -> None:
    get_signing_key()
    if not settings.security.api_default_username or not settings.security.api_default_password:
        raise HTTPException(
            status_code=503,
            detail="员工账号尚未配置：请设置 SECURITY__API_DEFAULT_USERNAME 和 SECURITY__API_DEFAULT_PASSWORD。",
        )


def _decode_session_token(token: str, *, audience: str, purpose: str) -> tuple[dict, datetime]:
    secret = get_signing_key()
    if not token or len(token) > 2048:
        raise HTTPException(status_code=401, detail="会话凭证无效或已过期。")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[settings.security.jwt_algorithm],
            audience=audience,
            options={"require_exp": True, "require_sub": True, "require_aud": True},
        )
        if claims.get("aud") != audience or claims.get("purpose") != purpose:
            raise JWTError("Invalid token purpose")
        if type(claims["exp"]) is not int:
            raise JWTError("Invalid expiration")
        expires_at = datetime.fromtimestamp(claims["exp"], timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise JWTError("Expired token")
    except (JWTError, ValueError, TypeError, OverflowError, OSError) as exc:
        raise HTTPException(status_code=401, detail="会话凭证无效或已过期。") from exc
    return claims, expires_at


def require_staff(request: Request) -> ChatAccess:
    """Authenticate staff regardless of the legacy DISABLE_AUTH setting."""
    require_staff_configuration()
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=401, detail="请先登录员工工作台。")
    claims, expires_at = _decode_session_token(
        token, audience=STAFF_AUDIENCE, purpose=STAFF_PURPOSE
    )
    username = claims["sub"]
    csrf_token = claims.get("csrf")
    if (
        claims.get("role") != "staff"
        or username != settings.security.api_default_username
        or not isinstance(csrf_token, str)
        or _CSRF_PATTERN.fullmatch(csrf_token) is None
    ):
        raise HTTPException(status_code=401, detail="员工会话无效，请重新登录。")
    user = get_api_user(username)
    if user is None or user.disabled:
        raise HTTPException(status_code=401, detail="员工会话无效，请重新登录。")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied_csrf = request.headers.get("X-CSRF-Token")
        if (
            supplied_csrf is None
            or len(supplied_csrf) > 128
            or not hmac.compare_digest(supplied_csrf.encode("utf-8"), csrf_token.encode("utf-8"))
        ):
            raise HTTPException(status_code=403, detail="请求校验失败，请刷新页面后重试。")
    return ChatAccess(user=user, expires_at=expires_at, csrf_token=csrf_token)


def get_chat_access(request: Request) -> ChatAccess:
    audience = request.headers.get("X-Client-Audience", "public")
    if audience == "staff":
        return require_staff(request)
    if audience == "public":
        return ChatAccess()
    raise HTTPException(status_code=400, detail="不支持的访问入口。")


def resolve_chat_session(
    access: ChatAccess, client_id: str | None, *, create: bool = True
) -> ChatSessionKey:
    """Resolve only owned staff IDs or signed public capabilities to storage IDs."""
    if client_id is not None and (not client_id or len(client_id) > 2048):
        raise HTTPException(status_code=400, detail="会话标识格式不正确。")
    is_placeholder = (
        client_id is not None
        and len(client_id) <= 160
        and _PLACEHOLDER_PATTERN.fullmatch(client_id) is not None
    )
    if access.is_staff:
        if client_id is None:
            if not create:
                raise HTTPException(status_code=400, detail="请提供会话标识。")
            client_id = f"session_{uuid4().hex}"
            is_placeholder = True
        if is_placeholder:
            storage_id = access.namespace + client_id
        elif client_id.startswith(access.namespace):
            suffix = client_id[len(access.namespace):]
            if len(suffix) > 160 or _PLACEHOLDER_PATTERN.fullmatch(suffix) is None:
                raise HTTPException(status_code=400, detail="会话标识格式不正确。")
            storage_id = client_id
        else:
            raise HTTPException(status_code=403, detail="无权访问此会话。")
        return ChatSessionKey(storage_id=storage_id, client_id=storage_id)

    if client_id is None or is_placeholder:
        if not create:
            raise HTTPException(status_code=401, detail="请提供有效的公众会话凭证。")
        storage_id = f"public:{uuid4()}"
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.security.public_session_exp_hours
        )
        token = jwt.encode(
            {"sub": storage_id, "aud": PUBLIC_AUDIENCE, "purpose": PUBLIC_AUDIENCE, "exp": expires_at},
            get_signing_key(),
            algorithm=settings.security.jwt_algorithm,
        )
        return ChatSessionKey(storage_id=storage_id, client_id=token)
    claims, _ = _decode_session_token(
        client_id, audience=PUBLIC_AUDIENCE, purpose=PUBLIC_AUDIENCE
    )
    storage_id = claims["sub"]
    if _PUBLIC_SESSION_PATTERN.fullmatch(storage_id) is None:
        raise HTTPException(status_code=403, detail="无权访问此会话。")
    return ChatSessionKey(storage_id=storage_id, client_id=client_id)


__all__ = ["ChatAccess", "ChatSessionKey", "get_chat_access", "require_staff", "resolve_chat_session"]
