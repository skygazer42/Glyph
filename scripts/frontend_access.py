"""Local staff login and file-backed graph/rule preview, without model/database startup.

Run on loopback with uvicorn scripts.frontend_access:app --host 127.0.0.1.
The complete application remains api_server:app.
"""

from fastapi import Depends, FastAPI, HTTPException

from app.api.endpoints.auth import router
from app.api.endpoints.knowledge_graph import router as graph_router
from app.api.endpoints.rule_preview import router as preview_router
from app.core.access import require_staff

app = FastAPI(title="政策知识服务平台 · 本地前端访问")
app.include_router(router, prefix="/api")
app.include_router(graph_router, prefix="/api/knowledge-graph", dependencies=[Depends(require_staff)])
app.include_router(preview_router, prefix="/api/dsl", dependencies=[Depends(require_staff)])


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def unavailable_backend(path: str) -> None:
    """Keep unavailable data and model operations visible as failures."""
    raise HTTPException(status_code=503, detail="当前仅启动本地登录、图谱读取与规则草稿试算，资料处理与咨询服务尚未启动。")
