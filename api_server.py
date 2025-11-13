"""
FastAPI 后端服务
模块化架构，集成 DSL 生成、知识库和 Agent 问答功能
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入 endpoint 路由
from app.api.endpoints import agent, dsl, knowledge, uploads, knowledge_graph
from app.api.schemas import HealthResponse
from app.api.deps import get_session_manager


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 应用启动中...")

    # 启动会话管理器
    session_manager = get_session_manager()
    session_manager.start()
    logger.info("✅ 会话管理器已启动")

    yield

    # 关闭时执行
    logger.info("🔄 应用关闭中...")
    await session_manager.stop()
    logger.info("✅ 会话管理器已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="政策DSL生成和知识库管理系统",
    description="模块化架构，支持 SSE 流式响应和会话管理",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent.router, prefix="/api/agent", tags=["Agent 问答"])
app.include_router(dsl.router, prefix="/api/dsl", tags=["DSL 生成"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["附件上传"])
app.include_router(knowledge_graph.router, prefix="/api/knowledge-graph", tags=["知识图谱"])

# ==================== 健康检查 ====================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        service="政策DSL生成和知识库管理系统",
        version="2.0.0"
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("="*60)
    logger.info("🚀 启动 政策DSL生成和知识库管理系统 API服务器")
    logger.info("="*60)
    logger.info("📍 地址: http://0.0.0.0:8000")
    logger.info("📚 API文档: http://0.0.0.0:8000/docs")
    logger.info("="*60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
