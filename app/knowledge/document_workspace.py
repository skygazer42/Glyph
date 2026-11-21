"""Local document inspection, versioned parse cache and processing preferences.

This module never creates a vector store or invokes a document parser. Offsets
are Python Unicode character offsets into the exact returned text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

import fitz
from fastapi import HTTPException

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from app.schemas.knowledge import (
    ChunkingConfig,
    ChunkPreview,
    ChunkPreviewRequest,
    ChunkPreviewResponse,
    DocumentWorkspaceResponse,
    ParsedContent,
    ProcessingCapabilities,
    ProcessingConfig,
    SaveProcessingConfigRequest,
    SaveProcessingConfigResponse,
    WorkspacePage,
)

SUPPORTED_FORMATS = {".pdf", ".txt", ".md", ".doc", ".docx"}


def safe_document_id(raw_id: str) -> str:
    """Reject noncanonical identifiers instead of silently selecting a basename."""
    if (
        not raw_id
        or raw_id in {".", ".."}
        or raw_id != raw_id.strip()
        or raw_id.endswith(".")
        or re.search(r'[\\/:*?"<>|\x00-\x1f\x7f]', raw_id)
        or Path(raw_id).name != raw_id
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", raw_id)
    ):
        raise HTTPException(status_code=400, detail="无效的文档 ID")
    return raw_id


def atomic_write(path: Path, content: str) -> None:
    """在同目录写入临时文件、刷新并 fsync 后以 os.replace 替换目标；清理临时文件，不保证多文件事务或目录断电持久性。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False, suffix=".tmp"
        ) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                # Windows readers and antivirus can briefly deny replacement.
                # Genuine permission errors still propagate after bounded retry.
                if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 5:
                    raise
                sleep(0.025 * 2**attempt)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _canonical_path(path: Path) -> Path:
    """Compare equivalent Windows extended paths using one drive/UNC spelling."""
    resolved = path.resolve()
    if sys.platform != "win32":
        return resolved
    value = str(resolved)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    return Path(value.removeprefix("\\\\?\\"))


class DocumentWorkspace:
    """管理上传目录内的原文、版本化解析缓存和处理配置；不负责调用解析器或写入向量库。"""

    def __init__(self, upload_dir: Path, parsed_dir: Path, parsed_status_dir: Path, embedded_dir: Path):
        self.root = _canonical_path(upload_dir)
        self.parsed_dir = parsed_dir
        self.parsed_status_dir = parsed_status_dir
        self.embedded_dir = embedded_dir
        self.config_dir = upload_dir / ".status" / "processing"

    def contained_path(self, directory: Path, filename: str) -> Path:
        """解析并约束路径位于上传根目录内；符号链接或越界路径返回 400。"""
        candidate = directory / filename
        if candidate.is_symlink() or not _canonical_path(candidate).is_relative_to(self.root):
            raise HTTPException(status_code=400, detail="文档路径超出上传目录")
        return candidate

    def source_path(self, doc_id: str, *, must_exist: bool = True) -> Path:
        """返回规范文档 ID 对应的原文路径；要求存在时对缺失文件返回 404。"""
        path = self.contained_path(self.root, safe_document_id(doc_id))
        if must_exist and not path.is_file():
            raise HTTPException(status_code=404, detail="文档不存在")
        return path

    def source_version(self, doc_id: str) -> str:
        """读取原文字节并返回 SHA-256 版本；文件读取失败直接传播。"""
        return hashlib.sha256(self.source_path(doc_id).read_bytes()).hexdigest()

    def require_source_version(self, doc_id: str, expected: str | None) -> str:
        """返回当前原文版本；提供的预期版本不匹配时返回 409。"""
        current = self.source_version(doc_id)
        if expected is not None and current != expected:
            raise HTTPException(status_code=409, detail="原文已变更，请刷新工作区")
        return current

    def parsed_path(self, doc_id: str) -> Path:
        """返回受上传目录边界约束的 Markdown 缓存路径，不要求缓存已存在。"""
        safe_document_id(doc_id)
        return self.contained_path(self.parsed_dir, f"{doc_id}.md")

    def marker_path(self, directory: Path, doc_id: str) -> Path:
        """返回文档状态标记路径；先验证文档 ID 和目录边界。"""
        safe_document_id(doc_id)
        return self.contained_path(directory, f"{doc_id}.json")

    def parsed_content(self, doc_id: str, source_version: str) -> ParsedContent:
        """返回与原文版本匹配的非空解析正文；缺失或失效缓存标为不可用，旧缓存可首次绑定版本。"""
        path = self.parsed_path(doc_id)
        if not path.is_file():
            return ParsedContent(available=False)
        marker = self.marker_path(self.parsed_status_dir, doc_id)
        metadata = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
        if "source_version" not in metadata:
            # Existing Markdown caches predate source hashes. Bind a fresh legacy
            # cache once so later byte changes invalidate it, including same-mtime edits.
            if path.stat().st_mtime_ns < self.source_path(doc_id).stat().st_mtime_ns:
                return ParsedContent(available=False)
            metadata.update(source_version=source_version, parser="legacy")
            atomic_write(marker, json.dumps(metadata, ensure_ascii=False))
        if metadata["source_version"] != source_version:
            return ParsedContent(available=False)
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return ParsedContent(available=False)
        version = hashlib.sha256((source_version + "\0" + text).encode("utf-8")).hexdigest()
        return ParsedContent(
            available=True, text=text, version=version, source_version=source_version,
            parser=metadata["parser"], content_length=len(text),
        )

    def store_parsed(self, doc_id: str, text: str, source_version: str, parser: str) -> ParsedContent:
        """校验原文版本后分别原子替换正文和标记，再返回缓存；两个文件并非同一事务。"""
        self.require_source_version(doc_id, source_version)
        path = self.parsed_path(doc_id)
        marker = self.marker_path(self.parsed_status_dir, doc_id)
        atomic_write(path, text)
        atomic_write(marker, json.dumps({
            "doc_id": doc_id, "source_version": source_version, "parser": parser,
            "markdown_path": str(path), "content_length": len(text),
        }, ensure_ascii=False))
        return self.parsed_content(doc_id, source_version)

    def embedded(self, doc_id: str, source_version: str, *, parsed: ParsedContent | None = None) -> bool:
        """仅当嵌入标记同时匹配原文和解析正文版本时返回真；不检查向量库内容。"""
        marker = self.marker_path(self.embedded_dir, doc_id)
        if not marker.is_file():
            return False
        metadata = json.loads(marker.read_text(encoding="utf-8"))
        if parsed is None:
            parsed = self.parsed_content(doc_id, source_version)
        return bool(
            parsed.available
            and metadata.get("source_version") == source_version
            and metadata.get("parsed_version") == parsed.version
        )

    def require_parsed_version(self, doc_id: str, source_version: str,
                               expected: str | None) -> tuple[str, str]:
        """返回有效解析正文及其版本；无缓存或预期版本不匹配时返回 409。"""
        parsed = self.parsed_content(doc_id, source_version)
        if not parsed.available or parsed.text is None or parsed.version is None:
            raise HTTPException(status_code=409, detail="请先解析当前版本文档，再执行嵌入")
        if expected is not None and expected != parsed.version:
            raise HTTPException(status_code=409, detail="解析正文已变更，请刷新工作区")
        return parsed.text, parsed.version

    def config(self, doc_id: str) -> tuple[ProcessingConfig, str, str | None]:
        """返回配置、修订号和保存时间；未保存时返回默认配置、修订号 0 和 None。"""
        path = self.marker_path(self.config_dir, doc_id)
        if not path.is_file():
            return ProcessingConfig(), "0", None
        saved = json.loads(path.read_text(encoding="utf-8"))
        return ProcessingConfig.model_validate(saved["config"]), saved["revision"], saved["saved_at"]

    def validate_config(self, doc_id: str, config: ProcessingConfig, capabilities: ProcessingCapabilities) -> None:
        """按当前能力和源文件格式校验配置；不支持的选项返回 422，不启动处理。"""
        if config.index == "hierarchical":
            raise HTTPException(status_code=422, detail="当前文档工作区尚未启用分级索引")
        if config.ocr != "auto":
            raise HTTPException(status_code=422, detail="当前解析器不支持按文档覆盖 OCR 开关")
        available = {item.value for item in capabilities.parsers if item.available}
        if config.parser not in available:
            raise HTTPException(status_code=422, detail="所选解析器当前不可用")
        suffix = self.source_path(doc_id).suffix.lower()
        if config.parser == "text" and suffix not in {".txt", ".md"}:
            raise HTTPException(status_code=422, detail="纯文本解析器仅支持 TXT / Markdown")
        if config.parser == "mineru" and suffix != ".pdf":
            raise HTTPException(status_code=422, detail="MinerU 解析器仅支持 PDF")

    @contextmanager
    def document_lock(self, doc_id: str, operation: Literal["processing", "embedding", "upload"]):
        """按文档及操作类型获取跨进程非阻塞文件锁；竞争返回 409，正常或异常退出时释放锁。"""
        path = self.contained_path(self.config_dir, f"{safe_document_id(doc_id)}.{operation}.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as stream:
            try:
                if sys.platform == "win32":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise HTTPException(status_code=409, detail="文档正在处理，请稍后刷新重试") from exc
            try:
                yield
            finally:
                if sys.platform == "win32":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def save_config(self, doc_id: str, request: SaveProcessingConfigRequest,
                    capabilities: ProcessingCapabilities) -> SaveProcessingConfigResponse:
        """在文档处理锁内核对原文和配置修订后写入新修订；冲突返回 409，不触发解析或嵌入。"""
        config = ProcessingConfig.model_validate(request.model_dump(exclude={"source_version", "revision"}))
        self.validate_config(doc_id, config, capabilities)
        with self.document_lock(doc_id, "processing"):
            source_version = self.require_source_version(doc_id, request.source_version)
            _, revision, _ = self.config(doc_id)
            if request.revision != revision:
                raise HTTPException(status_code=409, detail="配置已由其他窗口修改，请刷新后重试")
            revision = uuid4().hex
            saved_at = datetime.now(timezone.utc).isoformat()
            atomic_write(self.marker_path(self.config_dir, doc_id), json.dumps({
                "config": config.model_dump(), "revision": revision,
                "saved_at": saved_at, "source_version": source_version,
            }, ensure_ascii=False))
        return SaveProcessingConfigResponse(success=True, config=config, revision=revision,
                                            saved_at=saved_at, source_version=source_version)

    def pages(self, doc_id: str, source_version: str) -> list[WorkspacePage]:
        """读取 PDF 或文本页及字符区间；PDF 资源在返回前关闭，不支持的格式返回空列表。"""
        path = self.source_path(doc_id)
        url = f"/api/knowledge/documents/{quote(doc_id, safe='')}/pages"
        if path.suffix.lower() == ".pdf":
            try:
                with fitz.open(path) as document:
                    pages = []
                    start = 0
                    for number, page in enumerate(document, start=1):
                        text = page.get_text()
                        pages.append(WorkspacePage(number=number, text=text, start=start,
                                                   end=start + len(text), has_text=bool(text.strip()),
                                                   image_url=f"{url}/{number}?source_version={source_version}"))
                        start += len(text)
                    return pages
            except (fitz.FileDataError, RuntimeError) as exc:
                raise HTTPException(status_code=422, detail="无法读取 PDF 原文") from exc
        if path.suffix.lower() in {".txt", ".md"}:
            for encoding in ("utf-8", "gbk", "gb2312", "big5"):
                try:
                    text = path.read_text(encoding=encoding)
                    return [WorkspacePage(number=1, text=text, start=0, end=len(text), has_text=bool(text.strip()))]
                except UnicodeDecodeError:
                    continue
            raise HTTPException(status_code=422, detail="无法解码原文")
        return []

    def workspace(self, doc_id: str, capabilities: ProcessingCapabilities) -> DocumentWorkspaceResponse:
        """汇总原文页面、有效缓存、配置及嵌入标记；返回前再次核对原文版本。"""
        path = self.source_path(doc_id)
        source_version = self.source_version(doc_id)
        pages = self.pages(doc_id, source_version)
        parsed = self.parsed_content(doc_id, source_version)
        if parsed.available and parsed.text == "".join(page.text for page in pages):
            parsed.page_mapping = "exact"
        config, revision, saved_at = self.config(doc_id)
        self.require_source_version(doc_id, source_version)
        stat = path.stat()
        return DocumentWorkspaceResponse(
            success=True, doc_id=doc_id, name=doc_id, format=path.suffix.lstrip(".").lower(),
            size=stat.st_size, modified=stat.st_mtime, source_version=source_version,
            source_url=f"/api/knowledge/documents/{quote(doc_id, safe='')}/source?source_version={source_version}",
            page_count=len(pages), pages=pages, parsed=parsed, config=config,
            config_revision=revision, saved_at=saved_at,
            embedded=self.embedded(doc_id, source_version), capabilities=capabilities,
        )

    def page_image(self, doc_id: str, number: int, expected_version: str | None) -> bytes:
        """渲染指定 PDF 页为 PNG 字节并前后核对版本；页号越界返回 404，非 PDF 返回 422。"""
        path = self.source_path(doc_id)
        source_version = self.require_source_version(doc_id, expected_version)
        if path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=422, detail="仅 PDF 提供页面图像")
        try:
            with fitz.open(path) as document:
                if number < 1 or number > len(document):
                    raise HTTPException(status_code=404, detail="页面不存在")
                image = document[number - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
        except (fitz.FileDataError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail="无法读取 PDF 页面") from exc
        self.require_source_version(doc_id, source_version)
        return image

    def preview(self, doc_id: str, request: ChunkPreviewRequest) -> ChunkPreviewResponse:
        """按解析正文的 Unicode 字符偏移预览分块，不写入索引；仅正文与原文完全一致时映射页号。"""
        source_version = self.require_source_version(doc_id, request.source_version)
        parsed = self.parsed_content(doc_id, source_version)
        if not parsed.available or parsed.text is None or parsed.version is None:
            raise HTTPException(status_code=409, detail="当前原文尚无有效解析正文，请先解析")
        if parsed.version != request.parsed_version:
            raise HTTPException(status_code=409, detail="解析正文已变更，请刷新工作区")
        # Pages are assigned only if the cached parser text exactly equals the
        # local source text; semantic resemblance cannot establish offsets.
        pages = self.pages(doc_id, source_version)
        mapped = parsed.text == "".join(page.text for page in pages)
        text = parsed.text
        chunks: list[ChunkPreview] = []
        start = 0
        previous_end = 0
        while start < len(text):
            end = min(start + request.size, len(text))
            if request.boundary == "sentence" and end < len(text):
                lower = max(start + request.overlap + 1, start + request.size // 2, previous_end + 1)
                boundaries = list(re.finditer(r"[。！？.!?；;\n]", text[lower:end]))
                if boundaries:
                    end = lower + boundaries[-1].end()
            chunks.append(ChunkPreview(
                id=f"{parsed.version}:{start}:{end}", number=len(chunks) + 1,
                text=text[start:end], start=start, end=end,
                pages=[page.number for page in pages if page.start < end and page.end > start] if mapped else [],
                overlap=max(0, previous_end - start),
            ))
            if end == len(text):
                break
            previous_end = end
            start = end - request.overlap
        self.require_source_version(doc_id, source_version)
        return ChunkPreviewResponse(
            success=True, source_version=source_version, parsed_version=parsed.version,
            config=ChunkingConfig(size=request.size, overlap=request.overlap, boundary=request.boundary),
            chunks=chunks, total=len(chunks),
        )
