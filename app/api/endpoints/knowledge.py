"""
知识库相关端点
包含文档上传、嵌入、搜索等功能
"""

import shutil
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.api.schemas import (
    EmbedRequest,
    EmbedResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    UploadResponse,
    ListDocumentsResponse,
    DocumentInfo,
    DeleteDocumentResponse,
    StatsResponse
)
from app.api.deps import get_milvus_store, get_document_parser
from app.knowledge.milvus import MilvusStore
from app.agents.dsl_generator.document_parser import DocumentParser
from app.agents.framework.base.types import PolicyDocument

router = APIRouter()
logger = logging.getLogger(__name__)

# 上传目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_parser: DocumentParser = Depends(get_document_parser)
):
    """
    上传文档

    Args:
        file: 上传的文件

    Returns:
        上传结果
    """
    try:
        # 保存文件
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 解析文档
        content = doc_parser.parse(str(file_path))

        logger.info(f"文档上传成功: {file.filename}")

        return UploadResponse(
            success=True,
            doc_id=file.filename,
            file_path=str(file_path),
            content_length=len(content)
        )

    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed", response_model=EmbedResponse)
async def embed_document(
    request: EmbedRequest,
    milvus_store: MilvusStore = Depends(get_milvus_store),
    doc_parser: DocumentParser = Depends(get_document_parser)
):
    """
    将文档嵌入到向量库

    Args:
        request: 包含文档 ID 的请求

    Returns:
        嵌入结果
    """
    try:
        # 检查文档是否存在
        file_path = UPLOAD_DIR / request.doc_id
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文档不存在")

        # 解析文档内容
        content = doc_parser.parse(str(file_path))

        # 创建文档对象
        doc = PolicyDocument(
            id=request.doc_id,
            title=request.doc_id,
            content=content,
            source=str(file_path),
            doc_type="policy"
        )

        # 添加到向量库
        milvus_store.add_documents([doc])

        logger.info(f"文档已嵌入向量库: {request.doc_id}")

        return EmbedResponse(
            success=True,
            doc_id=request.doc_id,
            message="文档已成功嵌入到向量库"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    milvus_store: MilvusStore = Depends(get_milvus_store)
):
    """
    搜索知识库

    Args:
        request: 搜索请求

    Returns:
        搜索结果
    """
    try:
        # 执行搜索
        documents, scores = milvus_store.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold
        )

        # 转换为响应格式
        results = []
        for doc, score in zip(documents, scores):
            results.append(
                SearchResult(
                    id=getattr(doc, 'id', ''),
                    title=getattr(doc, 'title', ''),
                    content=getattr(doc, 'content', '')[:500],  # 限制长度
                    source=getattr(doc, 'source', ''),
                    score=float(score)
                )
            )

        logger.info(f"搜索完成，返回 {len(results)} 条结果")

        return SearchResponse(
            success=True,
            results=results,
            total=len(results)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=ListDocumentsResponse)
async def list_documents():
    """
    获取已上传的文档列表

    Returns:
        文档列表
    """
    try:
        if not UPLOAD_DIR.exists():
            return ListDocumentsResponse(
                success=True,
                documents=[],
                total=0
            )

        documents = []
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                documents.append(
                    DocumentInfo(
                        id=file_path.name,
                        name=file_path.name,
                        size=file_path.stat().st_size,
                        modified=file_path.stat().st_mtime
                    )
                )

        logger.info(f"获取文档列表，共 {len(documents)} 个")

        return ListDocumentsResponse(
            success=True,
            documents=documents,
            total=len(documents)
        )

    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document(doc_id: str):
    """
    删除文档

    Args:
        doc_id: 文档 ID

    Returns:
        删除结果
    """
    try:
        file_path = UPLOAD_DIR / doc_id
        if file_path.exists():
            file_path.unlink()

        logger.info(f"文档已删除: {doc_id}")

        return DeleteDocumentResponse(
            success=True,
            message="文档已删除"
        )

    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    milvus_store: MilvusStore = Depends(get_milvus_store)
):
    """
    获取知识库统计信息

    Returns:
        统计信息
    """
    try:
        stats = milvus_store.get_stats()

        logger.info("获取知识库统计信息")

        return StatsResponse(
            success=True,
            stats=stats
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
