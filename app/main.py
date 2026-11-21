#!/usr/bin/env python3
"""
轻量后端入口（FastAPI）：统一通过 AgentService 提供问答接口。

启动示例：
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

环境：参考 .env / README 中的 LLM_*、嵌入、Reranker 等配置。
"""

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import List, Optional, Any, Dict

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents.service.agent_service import AgentService
from app.core.auth import (
    APIUser,
    authenticate_user,
    create_access_token,
    get_current_user_or_dummy,
)
from app.config.app_config import settings
from app.core.llms import model_client
from app.utils.lifecycle import close_with_timeout

logger = logging.getLogger(__name__)

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
    """轻量问答入口的输入，可携带会话、用户和 Text2SQL 连接标识。"""

    query: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    connection_id: Optional[int] = Field(
        default=None, description="Text2SQL 场景下使用的数据库连接ID"
    )


class QueryResponse(BaseModel):
    """问答结果及检索来源；verification_passed 表示服务返回的核验状态。"""

    answer: str
    confidence: float
    verification_passed: bool
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LoadDocsRequest(BaseModel):
    """待导入知识库的本地文件或目录路径列表。"""

    paths: List[str] = Field(..., description="待加载的文件/目录列表")


class HealthResponse(BaseModel):
    """轻量进程健康端点的状态响应。"""

    status: str


class LoadDocsResponse(BaseModel):
    """文档导入返回的加载数量及知识库、图谱索引数量。"""

    loaded_docs: int
    kb_indexed: int
    rag_indexed: int


class TokenResponse(BaseModel):
    """登录成功返回的 Bearer 访问令牌。"""

    access_token: str
    token_type: str = "bearer"


def create_app() -> FastAPI:
    """Factory to build the FastAPI application."""
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """为本应用装配问答服务和可选限流连接，退出时执行已登记的有界清理。"""
        application.state.agent_service = None
        application.state.redis = None
        try:
            async with AsyncExitStack() as stack:
                stack.push_async_callback(close_with_timeout, model_client.close)
                service = AgentService()
                stack.push_async_callback(close_with_timeout, service.aclose)
                await service.initialize()
                application.state.agent_service = service
                if not settings.security.rate_limit_disable:
                    redis = await aioredis.from_url(
                        settings.security.rate_limit_redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    stack.push_async_callback(close_with_timeout, redis.aclose)
                    await FastAPILimiter.init(redis)
                    application.state.redis = redis
                yield
        finally:
            application.state.agent_service = None
            application.state.redis = None

    application = FastAPI(title="Policy QA Backend", version="1.0.0", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 静态资源：暴露 resources 目录用于图片等引用
    application.mount("/resources", StaticFiles(directory="resources"), name="resources")

    @application.get("/health", response_model=HealthResponse)
    async def health():
        """报告 HTTP 服务可响应，不探测模型、数据库或 Redis 的连通性。"""
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
        """验证账号密码并签发 Bearer 令牌；凭据不匹配时返回 HTTP 401。"""
        user = authenticate_user(form_data.username, form_data.password)
        if user is None:
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
        request: QueryRequest,
        current_user: APIUser = Depends(get_current_user_or_dummy),
    ):
        """执行一次问答并返回答案、来源和核验信息；执行异常转换为 HTTP 500。"""
        try:
            service: AgentService = application.state.agent_service
            final = await service.process_query(
                request.query,
                session_id=request.session_id,
                user_id=request.user_id,
                connection_id=request.connection_id,
            )
            sources = [source.model_dump() for source in final.sources]
            return QueryResponse(
                answer=final.answer,
                confidence=final.confidence,
                verification_passed=final.verification_passed,
                sources=sources,
                metadata=final.metadata,
            )
        except Exception as e:
            logger.exception("Query request failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    docs_dependencies = []
    if docs_rate_limiter:
        docs_dependencies.append(Depends(docs_rate_limiter))
    @application.post(
        "/load-docs",
        response_model=LoadDocsResponse,
        dependencies=docs_dependencies,
    )
    async def load_docs(
        request: LoadDocsRequest,
        current_user: APIUser = Depends(get_current_user_or_dummy),
    ):
        """将本地路径交给问答服务导入并返回计数；执行异常转换为 HTTP 500。"""
        try:
            service: AgentService = application.state.agent_service
            stats = await service.ingest_paths(request.paths)
            return stats
        except Exception as e:
            logger.exception("Document ingestion request failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
