#!/usr/bin/env python3
"""
轻量后端入口（FastAPI）：统一通过 AgentService 提供问答接口。

启动示例：
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

环境：参考 .env / README 中的 LLM_*、嵌入、Reranker 等配置。
"""

from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.service import AgentService


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

    @application.on_event("shutdown")
    async def on_shutdown():
        # 当前 AgentService 无需特殊释放资源
        application.state.agent_service = None  # type: ignore[attr-defined]

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    @application.post("/query", response_model=QueryResponse)
    async def query(req: QueryRequest):
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

    @application.post("/load-docs")
    async def load_docs(req: LoadDocsRequest):
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
