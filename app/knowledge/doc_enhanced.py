"""
增强文档处理器 - 使用MinerU2.6（在线上传）和 Docling/LlamaIndex
"""

import io
import time
import zipfile
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import requests
from requests.exceptions import RequestException
# LlamaIndex
from llama_index.readers.file import PDFReader, DocxReader
from app.config.app_config import settings


from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MinerUEnvelope(BaseModel):
    model_config = ConfigDict(strict=True)
    code: int
    msg: str | None = None
    data: dict[str, Any] | None = None


class MinerUUploadSlot(BaseModel):
    model_config = ConfigDict(strict=True)
    batch_id: str = Field(min_length=1)
    file_urls: list[str] = Field(min_length=1)


class MinerUMarkdownContent(BaseModel):
    model_config = ConfigDict(strict=True)
    markdown: str | None = Field(default=None, validation_alias=AliasChoices("markdown", "md", "text", "raw_text"))


class MinerUExtractedFile(BaseModel):
    model_config = ConfigDict(strict=True)
    data_id: str
    state: str = Field(min_length=1, validation_alias=AliasChoices("state", "status"))
    err_msg: str | None = None
    markdown: str | None = Field(default=None, validation_alias=AliasChoices("markdown", "full_markdown", "md"))
    content: MinerUMarkdownContent | None = None
    full_zip_url: str | None = Field(default=None, validation_alias=AliasChoices("full_zip_url", "zip_url"))


class MinerUBatchFiles(BaseModel):
    model_config = ConfigDict(strict=True)
    extract_result: list[MinerUExtractedFile] = Field(validation_alias=AliasChoices("extract_result", "files"))


class MinerUMetadata(BaseModel):
    model_config = ConfigDict(strict=True)
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnhancedDocumentProcessor:
    """增强文档处理器 - 支持多种文档解析引擎"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化MinerU客户端
        self.mineru_enabled = self.config.get("mineru_enabled", settings.mineru.enabled)
        self.mineru_base_url = self.config.get("mineru_base_url", settings.mineru.get_effective_base_url())
        self.mineru_api_key = self.config.get("mineru_api_key", settings.mineru.api_key)
        self.mineru_timeout = int(self.config.get("mineru_timeout", settings.mineru.timeout))
        self.mineru_model_version = self.config.get("mineru_model_version", settings.mineru.model_version)
        self.mineru_poll_interval = float(self.config.get("mineru_poll_interval", settings.mineru.poll_interval))
        self.mineru_poll_timeout = int(self.config.get("mineru_poll_timeout", settings.mineru.poll_timeout))

        # 初始化LlamaIndex读取器
        self.llamaindex_enabled = self.config.get("llamaindex_enabled", True)
        if self.llamaindex_enabled:
            self.llamaindex_readers = {
                ".pdf": PDFReader(),
                ".docx": DocxReader(),
                ".doc": DocxReader(),
                # .txt 和 .md 使用原生 Python 读取
            }
            self.logger.info("LlamaIndex readers initialized")

        self.logger.info("Enhanced Document Processor initialized:")
        self.logger.info(f"  - MinerU: {'enabled' if self.mineru_enabled else 'disabled'}")
        self.logger.info(f"  - LlamaIndex: {'enabled' if self.llamaindex_enabled else 'disabled'}")

    async def extract_text(self, file_path: Union[str, Path]) -> Optional[str]:
        """提取文本的统一接口"""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return await self._extract_from_pdf(file_path)
        if suffix in [".docx", ".doc"]:
            return await self._extract_from_docx(file_path)
        if suffix in [".txt", ".md"]:
            return await self._extract_from_text(file_path)
        raise ValueError(f"Unsupported file format: {suffix}")

    async def _extract_from_pdf(self, file_path: Path) -> Optional[str]:
        """从PDF提取文本 - 多引擎支持"""

        if not self.mineru_enabled and not self.llamaindex_enabled:
            raise RuntimeError("PDF extraction requires an enabled document parser")
        if self.mineru_enabled:
            self.logger.info("MinerU extraction attempt for %s", file_path.name)
            return await self._extract_with_mineru(file_path)
        return await self._extract_with_llamaindex(file_path)

    async def _extract_with_mineru(self, file_path: Path) -> Optional[str]:
        return await asyncio.to_thread(self._extract_with_mineru_sync, file_path)

    def _extract_with_mineru_sync(self, file_path: Path) -> Optional[str]:
        """使用 MinerU 在线接口：申请上传 → PUT 文件 → 提交解析 → 拉取结果"""
        if not self.mineru_api_key:
            raise ValueError("MinerU API key is not configured")

        upload_url, batch_id, data_id = self._mineru_request_upload_link(file_path.name)
        self.logger.debug("MinerU upload slot ready: batch=%s data=%s", batch_id, data_id)
        self._mineru_upload_file(upload_url, file_path)
        result_payload = self._mineru_poll_batch_result(batch_id, data_id)
        markdown_text = self._mineru_extract_markdown(result_payload)
        if markdown_text:
            return markdown_text
        raise RuntimeError("MinerU result did not contain markdown content")


    async def _extract_with_llamaindex(self, file_path: Path) -> Optional[str]:
        """使用LlamaIndex提取文档"""
        # LlamaIndex是同步的，使用线程池执行
        loop = asyncio.get_event_loop()

        def _process_with_llamaindex():
            reader = self.llamaindex_readers.get(file_path.suffix.lower())
            if reader:
                documents = reader.load_data(str(file_path))
                if documents:
                    # 合并所有文档的文本
                    return "\n\n".join(doc.text for doc in documents)
            return None

        return await loop.run_in_executor(None, _process_with_llamaindex)

    def _mineru_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.mineru_api_key}",
            "Content-Type": "application/json",
        }

    def _mineru_request_upload_link(self, file_name: str) -> tuple[str, str, str]:
        """申请 MinerU 上传地址，返回 (upload_url, batch_id, data_id)。"""
        data_id = str(uuid4())
        payload = {
            "files": [
                {"name": file_name, "data_id": data_id}
            ],
            "model_version": self.mineru_model_version,
        }
        with requests.post(
            f"{self.mineru_base_url}/file-urls/batch",
            headers=self._mineru_headers(),
            json=payload,
            timeout=self.mineru_timeout,
        ) as response:
            response.raise_for_status()
            body = MinerUEnvelope.model_validate(response.json())
        if body.code != 0:
            raise RuntimeError(f"MinerU upload slot failed: {body.msg}")
        slot = MinerUUploadSlot.model_validate(body.data)
        return slot.file_urls[0], slot.batch_id, data_id

    def _mineru_upload_file(self, upload_url: str, file_path: Path) -> None:
        """上传文件到 MinerU 提供的 OSS 预签名地址。"""
        # 不能自定义 Content-Type，预签名链接已经包含所需签名；多余头会导致 403
        with open(file_path, "rb") as fp:
            with requests.put(upload_url, data=fp, timeout=self.mineru_timeout) as response:
                response.raise_for_status()

    def _mineru_poll_batch_result(self, batch_id: str, data_id: str) -> Dict[str, Any]:
        """轮询 MinerU 批量任务结果，直到找到对应 data_id。"""
        deadline = time.monotonic() + self.mineru_poll_timeout
        while time.monotonic() < deadline:
            with requests.get(
                f"{self.mineru_base_url}/extract-results/batch/{batch_id}",
                headers={"Authorization": f"Bearer {self.mineru_api_key}"},
                timeout=self.mineru_timeout,
            ) as response:
                response.raise_for_status()
                body = MinerUEnvelope.model_validate(response.json())
            if body.code != 0:
                raise RuntimeError(f"MinerU poll failed: {body.msg}")
            batch = MinerUBatchFiles.model_validate(body.data)
            for entry in batch.extract_result:
                if entry.data_id == data_id:
                    if entry.state in {"done", "success"}:
                        return entry.model_dump(exclude_none=True)
                    if entry.state in {"failed", "error"}:
                        raise RuntimeError(f"MinerU task failed: {entry.err_msg}")
            time.sleep(self.mineru_poll_interval)
        raise TimeoutError(f"MinerU batch {batch_id} timeout for data_id={data_id}")

    def _mineru_extract_markdown(self, payload: Dict[str, Any]) -> Optional[str]:
        """从 MinerU extract_result 项或直接 payload 中提取 Markdown。"""
        if not payload:
            return None

        # 优先检查直接返回的 markdown 字段
        for key in ("markdown", "full_markdown", "md"):
            text = payload.get(key)
            if text:
                return text

        content = payload.get("content")
        if isinstance(content, dict):
            for key in ("markdown", "md", "text", "raw_text"):
                text = content.get(key)
                if text:
                    return text

        zip_url = payload.get("full_zip_url") or payload.get("zip_url")
        if zip_url:
            return self._mineru_download_md_from_zip(zip_url)
        return None

    def _mineru_download_md_from_zip(self, zip_url: str) -> Optional[str]:
        """下载 MinerU 提供的 zip，并提取 full.md / 任意 .md。"""
        with requests.get(zip_url, timeout=self.mineru_timeout) as response:
            response.raise_for_status()
            zip_content = response.content
        with zipfile.ZipFile(io.BytesIO(zip_content)) as archive:
            names = archive.namelist()
            target = "full.md" if "full.md" in names else None
            if not target:
                for candidate in names:
                    if candidate.lower().endswith(".md"):
                        target = candidate
                        break
            if not target:
                return None
            data = archive.read(target)
            return data.decode("utf-8", errors="ignore")

    async def _extract_from_docx(self, file_path: Path) -> Optional[str]:
        """从DOCX提取文本"""

        if not self.llamaindex_enabled:
            raise RuntimeError("DOCX extraction requires the LlamaIndex parser")
        return await self._extract_with_llamaindex(file_path)

    async def _extract_from_text(self, file_path: Path) -> str:
        """从TXT/MD提取文本"""
        for encoding in ("utf-8", "gbk", "gb2312"):
            try:
                return await asyncio.to_thread(file_path.read_text, encoding)
            except UnicodeDecodeError:
                continue
        return await asyncio.to_thread(file_path.read_text, "big5")

    async def extract_with_metadata(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """提取文本和元数据"""
        file_path = Path(file_path)

        # 提取文本
        text = await self.extract_text(file_path)

        if not text:
            return {
                "success": False,
                "error": "Failed to extract text",
                "file_path": str(file_path)
            }

        # 收集元数据
        metadata = {
            "success": True,
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_size": (await asyncio.to_thread(file_path.stat)).st_size,
            "file_type": file_path.suffix.lower(),
            "text_length": len(text),
            "extracted_at": datetime.now().isoformat(),
            "extraction_method": self._get_extraction_method(file_path.suffix.lower())
        }

        if file_path.suffix.lower() == ".pdf" and self.mineru_enabled:
            try:
                metadata.update(await asyncio.to_thread(self._fetch_mineru_metadata, file_path))
            except RequestException as exc:
                self.logger.debug("Failed to get enhanced metadata: %s", exc, exc_info=True)

        metadata["text"] = text
        return metadata

    def _fetch_mineru_metadata(self, file_path: Path) -> Dict[str, Any]:
        with file_path.open("rb") as stream:
            with requests.post(
                f"{self.mineru_base_url}/metadata",
                files={"file": (file_path.name, stream, "application/pdf")},
                headers={"Authorization": f"Bearer {self.mineru_api_key}"},
                timeout=self.mineru_timeout,
            ) as response:
                response.raise_for_status()
                result = MinerUMetadata.model_validate(response.json())
                return result.metadata if result.success else {}

    def _get_extraction_method(self, file_type: str) -> str:
        """获取使用的提取方法"""
        if file_type == ".pdf":
            if self.mineru_enabled:
                return "MinerU2.6 (api)"
            return "LlamaIndex"
        elif file_type in [".docx", ".doc"]:
            return "LlamaIndex"
        else:
            return "direct"

    def get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        formats = [".txt", ".md"]

        if self.mineru_enabled or self.llamaindex_enabled :
            formats.append(".pdf")

        if self.llamaindex_enabled:
            formats.extend([".docx", ".doc"])

        return formats

    def test_engines(self) -> Dict[str, bool]:
        """测试各个引擎是否可用"""
        results = {
            "mineru": self._test_mineru(),
            "llamaindex": self.llamaindex_enabled,
        }

        self.logger.info(f"Engine test results: {results}")
        return results

    def _test_mineru(self) -> bool:
        """测试MinerU连接"""
        if not self.mineru_enabled:
            return False

        try:
            with requests.get(
                f"{self.mineru_base_url}/health",
                timeout=5
            ) as response:
                return response.status_code == 200
        except RequestException:
            return False
