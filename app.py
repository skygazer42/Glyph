#!/usr/bin/env python3
"""
轻量后端入口（FastAPI）：统一通过 SmartOrchestrator 提供问答接口。

启动示例：
  uvicorn app:app --host 0.0.0.0 --port 8000 --reload

环境：参考 .env / README 中的 LLM_*、嵌入、Reranker 等配置。
"""

import asyncio
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.orchestrators.smart import SmartOrchestrator
from utils.config import Config
from utils.document_loader import DocumentLoader


class QueryRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None)
    user_id: Optional[str] = Field(None)


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    verification_passed: bool
    sources: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class LoadDocsRequest(BaseModel):
    paths: List[str] = Field(..., description="待加载的文件/目录列表")


app = FastAPI(title="Policy QA Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # 初始化编排器
    cfg = Config.from_env()
    orch = SmartOrchestrator(
        model_config=cfg.model,
        vector_store_config=cfg.vector_store,
        logging_config=cfg.logging,
    )
    await orch.initialize()
    app.state.orchestrator = orch


@app.on_event("shutdown")
async def on_shutdown():
    orch: SmartOrchestrator = getattr(app.state, "orchestrator", None)
    if orch:
        # 当前实现未暴露关闭方法；如后续需要可补充
        pass


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    try:
        orch: SmartOrchestrator = app.state.orchestrator
        final = await orch.process_query(req.query, session_id=req.session_id, user_id=req.user_id)
        # FinalAnswer 为 Pydantic BaseModel，可直接 dict()
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


@app.post("/load-docs")
async def load_docs(req: LoadDocsRequest):
    try:
        loader = DocumentLoader()
        all_docs = []
        for p in req.paths:
            docs = []
            try:
                docs = loader.load_from_directory(p)
            except Exception:
                # 不是目录则尝试单文件
                doc = loader.load_single_file(p)
                if doc:
                    docs = [doc]
            all_docs.extend(docs)

        orch: SmartOrchestrator = app.state.orchestrator
        loaded_kb = 0
        loaded_rag = 0
        if all_docs:
            try:
                await orch.kb_agents["knowledge_retriever"].add_documents(all_docs)
                loaded_kb = len(all_docs)
            except Exception:
                pass
            try:
                if orch.graph_agents.get("graph_retriever"):
                    await orch.graph_agents["graph_retriever"].add_documents(all_docs)
                    loaded_rag = len(all_docs)
            except Exception:
                pass
        return {"loaded_docs": len(all_docs), "kb_indexed": loaded_kb, "rag_indexed": loaded_rag}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
