"""
知识库相关端点
包含文档上传、嵌入、搜索等功能
"""

import json
import time
import shutil
import logging
from pathlib import Path
from uuid import uuid4
from typing import Optional, Tuple
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.api.schemas import (
    EmbedRequest,
    EmbedResponse,
    ParseRequest,
    ParseResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    UploadResponse,
    ListDocumentsResponse,
    DocumentInfo,
    DeleteDocumentResponse,
    StatsResponse
)
from app.api.deps import (
    get_enhanced_doc_processor,
    get_knowledge_service,
)
from app.knowledge import EnhancedDocumentProcessor, KnowledgeService
from app.models.base import PolicyDocument, PolicyType

router = APIRouter()
logger = logging.getLogger(__name__)

# 上传目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
PARSED_DIR = UPLOAD_DIR / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR = UPLOAD_DIR / ".status"
STATUS_DIR.mkdir(parents=True, exist_ok=True)
PARSED_STATUS_DIR = STATUS_DIR / "parsed"
PARSED_STATUS_DIR.mkdir(parents=True, exist_ok=True)
EMBED_STATUS_DIR = STATUS_DIR / "embedded"
EMBED_STATUS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_doc_id(raw_id: str) -> str:
    """避免路径遍历，始终返回文件名部分。"""
    return Path(raw_id).name


def _write_status_marker(dir_path: Path, doc_id: str, payload: dict) -> Path:
    """将状态信息写入 marker 文件。"""
    doc_id = _safe_doc_id(doc_id)
    marker_path = dir_path / f"{doc_id}.json"
    dir_path.mkdir(parents=True, exist_ok=True)
    payload_with_meta = {
        "doc_id": doc_id,
        "updated_at": time.time(),
        **payload,
    }
    marker_path.write_text(json.dumps(payload_with_meta, ensure_ascii=False), encoding="utf-8")
    return marker_path


def _mark_parsed(doc_id: str, markdown_path: Path, content_length: int) -> None:
    """记录文档已解析的状态。"""
    doc_id = _safe_doc_id(doc_id)
    _write_status_marker(
        PARSED_STATUS_DIR,
        doc_id,
        {
            "markdown_path": str(markdown_path),
            "content_length": content_length,
        },
    )


def _mark_embedded(doc_id: str) -> None:
    """记录文档已嵌入的状态。"""
    doc_id = _safe_doc_id(doc_id)
    _write_status_marker(
        EMBED_STATUS_DIR,
        doc_id,
        {},
    )


def _remove_status_marker(dir_path: Path, doc_id: str) -> None:
    """删除对应的状态文件。"""
    doc_id = _safe_doc_id(doc_id)
    marker = dir_path / f"{doc_id}.json"
    if marker.exists():
        marker.unlink()


def _has_marker(dir_path: Path, doc_id: str) -> bool:
    """检查 doc_id 的状态文件是否存在。"""
    doc_id = _safe_doc_id(doc_id)
    return (dir_path / f"{doc_id}.json").exists()


async def _build_policy_document(
    file_path: Path,
    processor: EnhancedDocumentProcessor,
    *,
    doc_id: Optional[str] = None,
) -> Tuple[PolicyDocument, int]:
    """使用增强文档处理器提取文本并构建 PolicyDocument。"""
    metadata = await processor.extract_with_metadata(file_path)
    if not metadata.get("success"):
        raise HTTPException(
            status_code=400,
            detail=metadata.get("error", "无法提取文档内容"),
        )
    text = metadata.get("text") or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="上传文档未解析到有效文本")

    title = metadata.get("title") or metadata.get("file_name") or file_path.stem
    summary = text[:200].strip()
    policy_type = metadata.get("doc_type")
    try:
        doc_type = PolicyType(policy_type) if policy_type else PolicyType.GUIDELINE
    except ValueError:
        doc_type = PolicyType.GUIDELINE

    document = PolicyDocument(
        id=uuid4(),
        title=title,
        content=text,
        summary=summary,
        source=str(file_path),
        doc_type=doc_type,
        metadata={**metadata, "uploaded_doc_id": doc_id or file_path.name},
    )
    return document, len(text)


def _build_policy_document_from_cache(
    text: str,
    file_path: Path,
    *,
    doc_id: str,
    parsed_path: Path,
) -> Tuple[PolicyDocument, int]:
    """根据缓存的 Markdown 文本构建 PolicyDocument。"""
    title = doc_id or file_path.stem
    summary = text[:200].strip()
    metadata = {
        "uploaded_doc_id": doc_id,
        "text_length": len(text),
        "parsed_markdown_path": str(parsed_path),
        "extraction_method": "cached_markdown",
    }
    document = PolicyDocument(
        id=uuid4(),
        title=title,
        content=text,
        summary=summary or title,
        source=str(file_path),
        doc_type=PolicyType.GUIDELINE,
        metadata=metadata,
    )
    return document, len(text)


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_doc_processor)
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

        # 解析文档，确保可被知识库使用
        _, content_length = await _build_policy_document(file_path, processor, doc_id=file.filename)

        logger.info(f"文档上传成功: {file.filename}")

        return UploadResponse(
            success=True,
            doc_id=file.filename,
            file_path=str(file_path),
            content_length=content_length
        )

    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse", response_model=ParseResponse)
async def parse_document(
    request: ParseRequest,
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_doc_processor),
):
    """
    解析已上传的文档，生成 Markdown 缓存。
    """
    safe_doc_id = _safe_doc_id(request.doc_id)
    try:
        file_path = UPLOAD_DIR / safe_doc_id
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文档不存在")

        document, content_length = await _build_policy_document(file_path, processor, doc_id=safe_doc_id)

        parsed_path = PARSED_DIR / f"{safe_doc_id}.md"
        parsed_path.write_text(document.content or "", encoding="utf-8")

        _mark_parsed(safe_doc_id, parsed_path, content_length)

        logger.info(f"文档解析成功: {safe_doc_id} -> {parsed_path}")

        return ParseResponse(
            success=True,
            doc_id=safe_doc_id,
            markdown_path=str(parsed_path),
            content_length=content_length,
            message="文档已解析为 Markdown，可直接用于嵌入",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"文档解析失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/embed", response_model=EmbedResponse)
async def embed_document(
    request: EmbedRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_doc_processor),
):
    """
    将文档嵌入到向量库

    Args:
        request: 包含文档 ID 的请求

    Returns:
        嵌入结果
    """
    safe_doc_id = _safe_doc_id(request.doc_id)
    try:
        # 检查文档是否存在
        file_path = UPLOAD_DIR / safe_doc_id
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文档不存在")

        parsed_path = PARSED_DIR / f"{safe_doc_id}.md"
        if parsed_path.exists():
            text = parsed_path.read_text(encoding="utf-8")
            if not text.strip():
                raise HTTPException(status_code=400, detail="已解析的 Markdown 内容为空")
            document, _ = _build_policy_document_from_cache(
                text,
                file_path,
                doc_id=safe_doc_id,
                parsed_path=parsed_path,
            )
        else:
            # 解析文档并构建 PolicyDocument
            document, _ = await _build_policy_document(file_path, processor, doc_id=safe_doc_id)

        # 添加到知识库
        await knowledge_service.index_documents([document])

        _mark_embedded(safe_doc_id)

        logger.info(f"文档已嵌入知识库: {safe_doc_id}")

        return EmbedResponse(
            success=True,
            doc_id=safe_doc_id,
            message="文档已成功入库并可用于检索"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    搜索知识库

    Args:
        request: 搜索请求

    Returns:
        搜索结果
    """
    try:
        # 执行搜索（统一走 KnowledgeService，可联动 LlamaIndex/MinerU）
        documents, scores = await knowledge_service.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold,
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
                        modified=file_path.stat().st_mtime,
                        embedded=_has_marker(EMBED_STATUS_DIR, file_path.name)
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
        safe_doc_id = _safe_doc_id(doc_id)
        file_path = UPLOAD_DIR / safe_doc_id
        if file_path.exists():
            file_path.unlink()
        parsed_path = PARSED_DIR / f"{safe_doc_id}.md"
        if parsed_path.exists():
            parsed_path.unlink()
        _remove_status_marker(PARSED_STATUS_DIR, safe_doc_id)
        _remove_status_marker(EMBED_STATUS_DIR, safe_doc_id)

        logger.info(f"文档已删除: {safe_doc_id}")

        return DeleteDocumentResponse(
            success=True,
            message="文档已删除"
        )

    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    获取知识库统计信息

    Returns:
        统计信息
    """
    try:
        stats = knowledge_service.vector_store.get_stats()

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
