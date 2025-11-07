"""
FastAPI 后端服务
集成 DSL 生成和知识库功能
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yaml
import shutil
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from agents.dsl_generator.dsl_extractor import DSLExtractor
from agents.dsl_generator.dsl_generator import DSLGenerator
from agents.dsl_generator.document_parser import DocumentParser
from agents.dsl_generator.rule_engine import PolicyEngine
from knowledge_base.milvus import MilvusStore

app = FastAPI(title="政策DSL生成和知识库管理系统")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化模块（确保使用正确的环境变量）
dsl_generator = DSLGenerator(output_dir="rules")
# 传递 API 密钥和基础 URL 给 DSLExtractor
dsl_extractor = DSLExtractor(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_BASE_URL")
)
doc_parser = DocumentParser()
policy_engine = PolicyEngine(rule_dir="rules")

# 知识库存储（延迟初始化）
milvus_store = None

# ==================== Pydantic 模型 ====================

class GenerateDSLRequest(BaseModel):
    text: str

class SaveDSLRequest(BaseModel):
    rule_id: str
    yaml_content: str
    filename: Optional[str] = None

class TestDSLRequest(BaseModel):
    rule_id: str
    inputs: Dict[str, Any]

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    threshold: float = 0.7

class EmbedRequest(BaseModel):
    doc_id: str

# ==================== DSL 相关接口 ====================

@app.post("/api/dsl/generate")
async def generate_dsl(request: GenerateDSLRequest):
    """从文本生成DSL"""
    try:
        # 预处理文本
        processed = doc_parser.preprocess_text(request.text)

        # 提取结构化数据
        dsl_data = dsl_extractor.extract(request.text, processed.get('metadata', {}))

        # 添加调试日志
        print(f"DEBUG: DSL Data from extractor: {dsl_data}")

        # 生成YAML
        yaml_content = dsl_generator.generate(dsl_data)

        return {
            "success": True,
            "dsl_data": dsl_data,
            "yaml_content": yaml_content
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"ERROR: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dsl/save")
async def save_dsl(request: SaveDSLRequest):
    """保存DSL到文件"""
    try:
        filename = request.filename or f"{request.rule_id}.yaml"
        file_path = dsl_generator.save(request.yaml_content, filename)

        # 重新加载规则引擎
        policy_engine.reload_rules()

        return {
            "success": True,
            "file_path": str(file_path),
            "rule_id": request.rule_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dsl/list")
async def list_dsl():
    """获取所有DSL规则列表"""
    try:
        policy_engine.reload_rules()
        rules = policy_engine.list_rules()
        return {
            "success": True,
            "rules": rules,
            "total": len(rules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dsl/{rule_id}")
async def get_dsl(rule_id: str):
    """获取DSL规则详情"""
    try:
        rule = policy_engine.get_rule_info(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")

        return {
            "success": True,
            "rule": rule
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dsl/test")
async def test_dsl(request: TestDSLRequest):
    """测试DSL规则"""
    try:
        result = policy_engine.execute(request.rule_id, request.inputs)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 知识库相关接口 ====================

def get_milvus_store():
    """获取或初始化 Milvus 存储"""
    global milvus_store
    if milvus_store is None:
        try:
            milvus_store = MilvusStore()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到Milvus: {str(e)}"
            )
    return milvus_store

@app.post("/api/knowledge/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档"""
    try:
        # 保存文件
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 解析文档
        content = doc_parser.parse(str(file_path))

        return {
            "success": True,
            "doc_id": file.filename,
            "file_path": str(file_path),
            "content_length": len(content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge/embed")
async def embed_document(request: EmbedRequest):
    """将文档嵌入到向量库"""
    try:
        store = get_milvus_store()

        # 读取文档内容
        file_path = Path("uploads") / request.doc_id
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文档不存在")

        content = doc_parser.parse(str(file_path))

        # 创建文档对象（使用简单字典代替PolicyDocument）
        from agents.base.types import PolicyDocument

        doc = PolicyDocument(
            id=request.doc_id,
            title=request.doc_id,
            content=content,
            source=str(file_path),
            doc_type="policy"
        )

        # 添加到向量库
        store.add_documents([doc])

        return {
            "success": True,
            "doc_id": request.doc_id,
            "message": "文档已成功嵌入到向量库"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge/search")
async def search_knowledge(request: SearchRequest):
    """搜索知识库"""
    try:
        store = get_milvus_store()

        documents, scores = store.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold
        )

        # 转换为可序列化的格式
        results = []
        for doc, score in zip(documents, scores):
            results.append({
                "id": getattr(doc, 'id', ''),
                "title": getattr(doc, 'title', ''),
                "content": getattr(doc, 'content', '')[:500],  # 限制内容长度
                "source": getattr(doc, 'source', ''),
                "score": float(score)
            })

        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/knowledge/documents")
async def list_documents():
    """获取已上传的文档列表"""
    try:
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return {"success": True, "documents": [], "total": 0}

        documents = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                documents.append({
                    "id": file_path.name,
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime
                })

        return {
            "success": True,
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/knowledge/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档"""
    try:
        file_path = Path("uploads") / doc_id
        if file_path.exists():
            file_path.unlink()

        return {
            "success": True,
            "message": "文档已删除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/knowledge/stats")
async def get_stats():
    """获取知识库统计信息"""
    try:
        store = get_milvus_store()
        stats = store.get_stats()

        return {
            "success": True,
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 健康检查 ====================

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "政策DSL生成和知识库管理系统"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
