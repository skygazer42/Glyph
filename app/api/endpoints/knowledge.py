"""
知识库相关端点
包含文档上传、嵌入、搜索等功能
"""

import json
import os
import time
import shutil
import logging
from pathlib import Path
from threading import Lock
from uuid import NAMESPACE_URL, uuid4, uuid5
from typing import Annotated, BinaryIO, Optional, Tuple
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.schemas.knowledge import (
    EmbedRequest,
    EmbedResponse,
    ParseRequest,
    ParseResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    UploadResponse,
    ListDocumentsResponse,
    DocumentListQuery, DocumentSummary,
    DeleteDocumentResponse,
    StatsResponse,
    CapabilitiesResponse, ProcessingCapabilities, ParserCapability,
    ProcessingConfig, DocumentWorkspaceResponse, ChunkPreviewRequest,
    ChunkPreviewResponse, SaveProcessingConfigRequest, SaveProcessingConfigResponse,
)
from app.api.deps import (
    get_enhanced_doc_processor,
    get_knowledge_service,
)
from app.knowledge.document_processor import EnhancedDocumentProcessor
from app.knowledge.service import KnowledgeService
from app.knowledge.document_workspace import DocumentWorkspace, SUPPORTED_FORMATS, atomic_write, safe_document_id
from app.knowledge.document_catalog import DocumentCatalog
from app.models.policy import PolicyDocument, PolicyType

router = APIRouter()
logger = logging.getLogger(__name__)

# 上传目录
UPLOAD_DIR = Path("uploads")
PARSED_DIR = UPLOAD_DIR / "parsed"
STATUS_DIR = UPLOAD_DIR / ".status"
PARSED_STATUS_DIR = STATUS_DIR / "parsed"
EMBED_STATUS_DIR = STATUS_DIR / "embedded"
_catalogs: dict[tuple[Path, ...], DocumentCatalog] = {}
_catalog_lock = Lock()


def _workspace() -> DocumentWorkspace:
    return DocumentWorkspace(UPLOAD_DIR, PARSED_DIR, PARSED_STATUS_DIR, EMBED_STATUS_DIR)


def _catalog() -> DocumentCatalog:
    paths = tuple(path.absolute() for path in (UPLOAD_DIR, PARSED_DIR, PARSED_STATUS_DIR, EMBED_STATUS_DIR))
    with _catalog_lock:
        if paths not in _catalogs:
            _catalogs[paths] = DocumentCatalog(_workspace())
        return _catalogs[paths]


def warm_document_catalog() -> None:
    """Build/restore the listing snapshot before the server accepts requests."""
    _catalog().documents()


def _capabilities() -> ProcessingCapabilities:
    """根据配置返回解析器可选能力；可用标记不代表已探测外部服务连通性。"""
    from app.config.app_config import settings

    return ProcessingCapabilities(
        parsers=[
            ParserCapability(value="auto", label="自动选择", available=True),
            ParserCapability(value="mineru", label="MinerU", available=bool(settings.mineru.enabled and settings.mineru.api_key)),
            ParserCapability(value="llamaindex", label="LlamaIndex", available=True),
            ParserCapability(value="text", label="纯文本", available=True),
        ],
        ocr=False, hierarchical_index=False,
    )


def _selected_processor(config: ProcessingConfig, processor: EnhancedDocumentProcessor) -> EnhancedDocumentProcessor:
    """自动模式复用注入处理器；显式解析器配置创建对应处理器实例。"""
    if config.parser == "auto":
        return processor
    return EnhancedDocumentProcessor(config={
        "mineru_enabled": config.parser == "mineru",
        "llamaindex_enabled": config.parser == "llamaindex",
    })


def _save_upload(file_path: Path, source: BinaryIO) -> tuple[int, int]:
    """Keep file creation, copying and closing in the same worker thread."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    identity = None
    try:
        with open(file_path, "xb") as buffer:
            stat = os.fstat(buffer.fileno())
            identity = (stat.st_dev, stat.st_ino)
            shutil.copyfileobj(source, buffer)
    except BaseException as exc:
        if identity is None and isinstance(exc, FileExistsError):
            raise HTTPException(status_code=409, detail="同名文档已存在，请重命名后上传") from exc
        if identity is not None and file_path.exists():
            stat = file_path.stat()
            if (stat.st_dev, stat.st_ino) == identity:
                file_path.unlink()
        raise
    return identity


def _snapshot_parse_cache(workspace: DocumentWorkspace, doc_id: str) -> dict[Path, bytes | None]:
    """读取正文和解析标记的原始字节快照，缺失文件记为 None，供失败恢复使用。"""
    paths = (workspace.parsed_path(doc_id), workspace.marker_path(PARSED_STATUS_DIR, doc_id))
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _rollback_failed_upload(file_path: Path, identity: tuple[int, int], source_version: str | None,
                            parsed_text: str | None, previous_cache: dict[Path, bytes | None]) -> None:
    """Remove only this request's unchanged file and restore its own cache writes."""
    if not file_path.is_file() or file_path.is_symlink():
        return
    stat = file_path.stat()
    if (stat.st_dev, stat.st_ino) != identity:
        return
    workspace = _workspace()
    if source_version is not None and workspace.source_version(file_path.name) != source_version:
        return
    for path, previous in previous_cache.items():
        if not path.is_file():
            continue
        current = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            owned = current == parsed_text
        else:
            owned = json.loads(current).get("source_version") == source_version
        if not owned:
            continue
        if previous is None:
            path.unlink()
        else:
            atomic_write(path, previous.decode("utf-8"))
    file_path.unlink()


def _write_status_marker(dir_path: Path, doc_id: str, payload: dict) -> Path:
    """将状态信息写入 marker 文件。"""
    doc_id = safe_document_id(doc_id)
    marker_path = _workspace().marker_path(dir_path, doc_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    payload_with_meta = {
        "doc_id": doc_id,
        "updated_at": time.time(),
        **payload,
    }
    atomic_write(marker_path, json.dumps(payload_with_meta, ensure_ascii=False))
    return marker_path


def _mark_embedded(doc_id: str, source_version: str, parsed_version: str, vector_id: str) -> None:
    """记录文档已嵌入的状态。"""
    doc_id = safe_document_id(doc_id)
    _write_status_marker(
        EMBED_STATUS_DIR,
        doc_id,
        {"source_version": source_version, "parsed_version": parsed_version, "vector_id": vector_id},
    )


def _remove_status_marker(dir_path: Path, doc_id: str) -> None:
    """删除对应的状态文件。"""
    doc_id = safe_document_id(doc_id)
    marker = _workspace().marker_path(dir_path, doc_id)
    if marker.exists():
        marker.unlink()


async def _build_policy_document(
    file_path: Path,
    processor: EnhancedDocumentProcessor,
    *,
    doc_id: Optional[str] = None,
) -> Tuple[PolicyDocument, int]:
    """使用增强文档处理器提取文本并构建 PolicyDocument。"""
    metadata = await processor.extract_with_metadata(file_path)
    if not metadata["success"]:
        raise HTTPException(
            status_code=400,
            detail=metadata["error"],
        )
    text = metadata["text"]
    if not text.strip():
        raise HTTPException(status_code=400, detail="上传文档未解析到有效文本")

    title = metadata.get("title") or metadata["file_name"]
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
        metadata={**metadata, "uploaded_doc_id": file_path.name if doc_id is None else doc_id},
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
    summary = text[:200].strip()
    metadata = {
        "uploaded_doc_id": doc_id,
        "text_length": len(text),
        "parsed_markdown_path": str(parsed_path),
        "extraction_method": "cached_markdown",
    }
    source_identity = file_path.resolve().as_uri()
    if file_path.drive:
        source_identity = source_identity.casefold()
    document = PolicyDocument(
        id=uuid5(NAMESPACE_URL, f"glyph:knowledge:{source_identity}"),
        title=doc_id,
        content=text,
        summary=summary,
        source=str(file_path),
        doc_type=PolicyType.GUIDELINE,
        metadata=metadata,
    )
    return document, len(text)


def _embed_document_once(request: EmbedRequest, knowledge_service: KnowledgeService) -> EmbedResponse:
    """在线程内持有嵌入锁，校验原文和解析版本后 upsert 向量并写标记；后续失败不回滚已写向量。"""
    doc_id = safe_document_id(request.doc_id)
    workspace = _workspace()
    with workspace.document_lock(doc_id, "embedding"):
        file_path = workspace.source_path(doc_id)
        source_version = workspace.require_source_version(doc_id, request.source_version)
        config, _, _ = workspace.config(doc_id)
        workspace.validate_config(doc_id, config, _capabilities())
        parsed_text, parsed_version = workspace.require_parsed_version(doc_id, source_version, request.parsed_version)
        if workspace.embedded(doc_id, source_version):
            return EmbedResponse(success=True, doc_id=doc_id, message="当前版本文档已入库")
        document, _ = _build_policy_document_from_cache(
            parsed_text, file_path, doc_id=doc_id, parsed_path=workspace.parsed_path(doc_id),
        )
        # Stable primary keys plus Milvus upsert keep retries safe after an
        # uncertain flush or local marker-write failure. Shared hierarchy stays intact.
        knowledge_service.vector_store.add_documents([document], upsert=True)
        workspace.require_source_version(doc_id, source_version)
        workspace.require_parsed_version(doc_id, source_version, parsed_version)
        _mark_embedded(doc_id, source_version, parsed_version, str(document.id))
    return EmbedResponse(success=True, doc_id=doc_id, message="文档已成功入库并可用于检索")


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_doc_processor)
):
    """保存上传原文并解析为版本化 Markdown 缓存，返回文档标识和原文版本；不执行向量嵌入，失败时仅尝试清理本请求拥有的文件及缓存。"""
    created_identity = None
    source_version = None
    parsed_text = None
    previous_cache: dict[Path, bytes | None] = {}
    try:
        # 保存文件
        if file.filename is None:
            raise HTTPException(status_code=400, detail="上传文件缺少文件名")
        doc_id = safe_document_id(Path(file.filename).name)
        if not doc_id:
            raise HTTPException(status_code=400, detail="上传文件缺少文件名")
        workspace = _workspace()
        file_path = workspace.source_path(doc_id, must_exist=False)
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise HTTPException(status_code=422, detail="不支持的文档格式")
        created_identity = await run_in_threadpool(_save_upload, file_path, file.file)

        # 解析文档，确保可被知识库使用
        source_version = await run_in_threadpool(workspace.source_version, doc_id)
        document, content_length = await _build_policy_document(file_path, processor, doc_id=doc_id)
        parsed_text = document.content
        previous_cache = await run_in_threadpool(_snapshot_parse_cache, workspace, doc_id)
        await run_in_threadpool(workspace.store_parsed, doc_id, document.content, source_version,
                                document.metadata.get("extraction_method", "auto"))

        logger.info(f"文档上传成功: {file.filename}")

        return UploadResponse(
            success=True,
            doc_id=doc_id,
            file_path=str(file_path),
            content_length=content_length,
            parsed=True,
            source_version=source_version,
        )

    except HTTPException:
        if created_identity is not None:
            await run_in_threadpool(_rollback_failed_upload, file_path, created_identity, source_version,
                                    parsed_text, previous_cache)
        raise
    except Exception as e:
        if created_identity is not None:
            await run_in_threadpool(_rollback_failed_upload, file_path, created_identity, source_version,
                                    parsed_text, previous_cache)
        logger.exception(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/parse", response_model=ParseResponse)
async def parse_document(
    request: ParseRequest,
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_doc_processor),
):
    """
    解析已上传的文档，生成 Markdown 缓存。
    """
    safe_doc_id = safe_document_id(request.doc_id)
    try:
        workspace = _workspace()
        file_path = await run_in_threadpool(workspace.source_path, safe_doc_id)
        source_version = await run_in_threadpool(workspace.require_source_version, safe_doc_id, request.source_version)
        saved_config, _, _ = await run_in_threadpool(workspace.config, safe_doc_id)
        config = saved_config if request.options is None else request.options
        overrides = request.model_dump(include={"parser", "ocr"}, exclude_none=True)
        config = ProcessingConfig.model_validate({**config.model_dump(), **overrides})
        await run_in_threadpool(workspace.validate_config, safe_doc_id, config, _capabilities())
        processor = await run_in_threadpool(_selected_processor, config, processor)
        document, content_length = await _build_policy_document(file_path, processor, doc_id=safe_doc_id)
        parsed = await run_in_threadpool(workspace.store_parsed, safe_doc_id, document.content, source_version,
                                         document.metadata.get("extraction_method", config.parser))
        parsed_path = workspace.parsed_path(safe_doc_id)

        logger.info(f"文档解析成功: {safe_doc_id} -> {parsed_path}")

        return ParseResponse(
            success=True,
            doc_id=safe_doc_id,
            markdown_path=str(parsed_path),
            content_length=content_length,
            message="文档已解析为 Markdown，可直接用于嵌入",
            source_version=source_version,
            parsed_version=parsed.version,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"文档解析失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/embed", response_model=EmbedResponse)
async def embed_document(
    request: EmbedRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    将文档嵌入到向量库

    Args:
        request: 包含文档 ID 的请求

    Returns:
        嵌入结果
    """
    try:
        return await run_in_threadpool(_embed_document_once, request, knowledge_service)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"文档嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        for doc, score in zip(documents, scores, strict=True):
            results.append(
                SearchResult(
                    id=str(doc.id),
                    title=doc.title,
                    content=doc.content[:500],  # 限制长度
                    source=doc.source,
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
        logger.exception(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/documents", response_model=ListDocumentsResponse)
def list_documents(query: Annotated[DocumentListQuery, Query()]):
    """
    获取已上传的文档列表

    Returns:
        文档列表
    """
    try:
        documents = _catalog().documents()
        summary = DocumentSummary(total=len(documents), parsed=sum(doc.parsed for doc in documents),
                                  embedded=sum(doc.embedded for doc in documents))
        keyword = query.query.strip().casefold()
        matching = [doc for doc in documents if (not keyword or keyword in doc.name.casefold())
                    and (query.parsed == "all" or doc.parsed == (query.parsed == "parsed"))
                    and (query.indexed == "all" or doc.embedded == (query.indexed == "indexed"))]
        matching.sort(key=lambda doc: (doc.modified, doc.name), reverse=query.sort == "newest")
        total = len(matching)
        if query.page is not None:
            start = (query.page - 1) * query.page_size
            matching = matching[start:start + query.page_size]
        return ListDocumentsResponse(
            success=True, documents=matching, total=total, summary=summary,
            page=query.page, page_size=query.page_size if query.page is not None else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities():
    """返回当前配置声明的处理能力，不触发解析器探测或文档处理。"""
    return CapabilitiesResponse(success=True, capabilities=_capabilities())


@router.get("/documents/{doc_id}/workspace", response_model=DocumentWorkspaceResponse)
def get_document_workspace(doc_id: str, response: Response):
    """返回原文、页面、解析缓存和处理配置的版本化工作区，并禁止缓存。"""
    response.headers["Cache-Control"] = "no-store"
    result = _workspace().workspace(doc_id, _capabilities())
    _catalog().invalidate(doc_id)
    return result


@router.get("/documents/{doc_id}/source")
def get_document_source(doc_id: str, source_version: str | None = None):
    """校验可选原文版本后以内联文件响应返回原文；版本冲突返回 409。"""
    workspace = _workspace()
    workspace.require_source_version(doc_id, source_version)
    path = workspace.source_path(doc_id)
    media_type = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}.get(
        path.suffix.lower(), "application/octet-stream"
    )
    return FileResponse(path, media_type=media_type, filename=doc_id, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/documents/{doc_id}/pages/{page}")
def get_document_page(doc_id: str, page: int, source_version: str | None = None):
    """返回指定 PDF 页的 PNG 图像；版本冲突、格式或页号错误由工作区报告。"""
    image = _workspace().page_image(doc_id, page, source_version)
    return Response(image, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/documents/{doc_id}/chunks/preview", response_model=ChunkPreviewResponse)
def preview_document_chunks(doc_id: str, request: ChunkPreviewRequest):
    """根据指定原文和解析版本生成分块预览，不执行向量嵌入或保存分块。"""
    return _workspace().preview(doc_id, request)


@router.put("/documents/{doc_id}/processing-config", response_model=SaveProcessingConfigResponse)
def save_processing_config(doc_id: str, request: SaveProcessingConfigRequest):
    """核对文档版本及配置修订后保存处理偏好；不自动解析或重新嵌入文档。"""
    return _workspace().save_config(doc_id, request, _capabilities())


@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
def delete_document(doc_id: str):
    """
    删除文档

    Args:
        doc_id: 文档 ID

    Returns:
        删除结果
    """
    try:
        safe_doc_id = safe_document_id(doc_id)
        workspace = _workspace()
        file_path = workspace.source_path(safe_doc_id, must_exist=False)
        if file_path.exists():
            file_path.unlink()
        parsed_path = workspace.parsed_path(safe_doc_id)
        if parsed_path.exists():
            parsed_path.unlink()
        _remove_status_marker(PARSED_STATUS_DIR, safe_doc_id)
        _remove_status_marker(EMBED_STATUS_DIR, safe_doc_id)
        workspace.marker_path(workspace.config_dir, safe_doc_id).unlink(missing_ok=True)

        logger.info(f"文档已删除: {safe_doc_id}")

        return DeleteDocumentResponse(
            success=True,
            message="文档已删除"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    """
    获取知识库统计信息

    Returns:
        统计信息
    """
    try:
        vector_stats = knowledge_service.vector_store.get_stats()

        document_files = [
            path for path in UPLOAD_DIR.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in SUPPORTED_FORMATS
        ] if UPLOAD_DIR.exists() else []

        total_size = sum(path.stat().st_size for path in document_files)
        workspace = _workspace()
        embedded_count = sum(
            1 for path in document_files
            if workspace.embedded(path.name, workspace.source_version(path.name))
        )

        stats_payload = {
            "total_documents": len(document_files),
            "total_chunks": vector_stats["total_documents"],
            "embedding_count": embedded_count,
            "total_size": total_size,
            "vector_details": vector_stats,
        }

        logger.info("获取知识库统计信息")

        return StatsResponse(
            success=True,
            stats=stats_payload,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
