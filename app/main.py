#!/usr/bin/env python3
"""
轻量后端入口（FastAPI）：统一通过 AgentService 提供问答接口。

启动示例：
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

环境：参考 .env / README 中的 LLM_*、嵌入、Reranker 等配置。
"""

import logging
from typing import List, Optional, Any, Dict

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel, Field

from app.agents.service import AgentService
from app.core.auth import (
    APIUser,
    authenticate_user,
    create_access_token,
    get_current_user_or_dummy,
)
from app.core.config import settings


# ============================================
# 日志过滤器: 过滤 health check 请求日志
# ============================================
class HealthCheckFilter(logging.Filter):
    """过滤健康检查端点的访问日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        # 过滤包含 /health 或 /api/health 的日志
        message = record.getMessage()
        return not any(
            pattern in message
            for pattern in ["/health", "GET /api/health", "GET /health"]
        )


# 应用过滤器到 uvicorn 的 access logger
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


class QueryRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None)
    user_id: Optional[str] = Field(None)
    connection_id: Optional[int] = Field(
        None, description="Text2SQL 场景下使用的数据库连接ID"
    )


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    verification_passed: bool
    sources: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class LoadDocsRequest(BaseModel):
    paths: List[str] = Field(..., description="待加载的文件/目录列表")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_app() -> FastAPI:
    """Factory to build the FastAPI application."""
    application = FastAPI(title="Policy QA Backend", version="1.0.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    async def on_startup():
        agent_service = AgentService()
        await agent_service.initialize()
        application.state.agent_service = agent_service
        if not settings.security.rate_limit_disable:
            try:
                redis = await aioredis.from_url(
                    settings.security.rate_limit_redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await FastAPILimiter.init(redis)
                application.state.redis = redis
            except Exception as exc:
                application.state.redis = None
                application.logger.warning("Rate limiter init failed, continuing without limits: %s", exc)
        else:
            application.state.redis = None

    @application.on_event("shutdown")
    async def on_shutdown():
        # 当前 AgentService 无需特殊释放资源
        application.state.agent_service = None  # type: ignore[attr-defined]
        redis = getattr(application.state, "redis", None)
        if redis:
            await redis.close()
        try:
            await FastAPILimiter.close()
        except Exception:
            pass

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    query_rate_limiter = None
    docs_rate_limiter = None
    if not settings.security.rate_limit_disable:
        query_rate_limiter = RateLimiter(
            times=settings.security.rate_limit_query_times,
            seconds=settings.security.rate_limit_query_seconds,
        )
        docs_rate_limiter = RateLimiter(
            times=settings.security.rate_limit_docs_times,
            seconds=settings.security.rate_limit_docs_seconds,
        )

    @application.post("/auth/login", response_model=TokenResponse)
    async def login(form_data: OAuth2PasswordRequestForm = Depends()):
        user = authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token({"sub": user.username})
        return TokenResponse(access_token=token)

    query_dependencies = []
    if query_rate_limiter:
        query_dependencies.append(Depends(query_rate_limiter))
    @application.post(
        "/query",
        response_model=QueryResponse,
        dependencies=query_dependencies,
    )
    async def query(
        req: QueryRequest,
        current_user: APIUser = Depends(get_current_user_or_dummy),
    ):
        try:
            service: AgentService = application.state.agent_service
            final = await service.process_query(
                req.query,
                session_id=req.session_id,
                user_id=req.user_id,
                connection_id=req.connection_id,
            )
            sources = []
            for s in final.sources or []:
                try:
                    sources.append(s.dict())
                except Exception:
                    sources.append({"title": getattr(s, "title", ""), "source": getattr(s, "source", "")})
            return QueryResponse(
                answer=final.answer,
                confidence=final.confidence,
                verification_passed=final.verification_passed,
                sources=sources,
                metadata=final.metadata or {},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    docs_dependencies = []
    if docs_rate_limiter:
        docs_dependencies.append(Depends(docs_rate_limiter))
    @application.post(
        "/load-docs",
        dependencies=docs_dependencies,
    )
    async def load_docs(
        req: LoadDocsRequest,
        current_user: APIUser = Depends(get_current_user_or_dummy),
    ):
        try:
            service: AgentService = application.state.agent_service
            stats = await service.ingest_paths(req.paths)
            return stats
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
