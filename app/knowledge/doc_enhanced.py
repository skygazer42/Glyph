"""
增强文档处理器 - 使用MinerU2.6（在线上传）和 Docling/LlamaIndex
"""

import io
import os
import time
import zipfile
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import tempfile
import subprocess
import sys
from datetime import datetime
from uuid import uuid4
import requests
from requests.exceptions import RequestException
# LlamaIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, DocxReader
LLAMAINDEX_AVAILABLE = True

# 原有处理库
import PyPDF2
from app.config import settings

class EnhancedDocumentProcessor:
    """增强文档处理器 - 支持多种文档解析引擎"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.docling_enabled = False  # Docling support (TODO: implement)

        # 初始化MinerU客户端
        self.mineru_enabled = self.config.get("mineru_enabled", settings.mineru.enabled)
        self.mineru_base_url = self.config.get("mineru_base_url", settings.mineru.get_effective_base_url())
        self.mineru_api_key = self.config.get("mineru_api_key", settings.mineru.api_key)
        self.mineru_timeout = int(self.config.get("mineru_timeout", settings.mineru.timeout))
        self.mineru_model_version = self.config.get("mineru_model_version", settings.mineru.model_version)
        self.mineru_poll_interval = float(self.config.get("mineru_poll_interval", settings.mineru.poll_interval))
        self.mineru_poll_timeout = int(self.config.get("mineru_poll_timeout", settings.mineru.poll_timeout))

        # 初始化LlamaIndex读取器
        self.llamaindex_enabled = self.config.get("llamaindex_enabled", LLAMAINDEX_AVAILABLE)
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            self.llamaindex_readers = {
                ".pdf": PDFReader(),
                ".docx": DocxReader(),
                ".doc": DocxReader(),
                # .txt 和 .md 使用原生 Python 读取
            }
            self.logger.info("LlamaIndex readers initialized")

        # 处理选项
        self.ocr_enabled = self.config.get("ocr_enabled", getattr(settings.document, "enable_ocr", True))
        self.table_extraction = self.config.get("table_extraction", getattr(settings.document, "enable_table_extraction", True))
        self.image_extraction = self.config.get("image_extraction", getattr(settings.document, "enable_image_extraction", True))

        self.logger.info(f"Enhanced Document Processor initialized:")
        self.logger.info(f"  - MinerU: {'enabled' if self.mineru_enabled else 'disabled'}")
        self.logger.info(f"  - Docling: {'enabled' if self.docling_enabled else 'disabled'}")
        self.logger.info(f"  - LlamaIndex: {'enabled' if self.llamaindex_enabled else 'disabled'}")

    async def extract_text(self, file_path: Union[str, Path]) -> Optional[str]:
        """提取文本的统一接口"""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                return await self._extract_from_pdf(file_path)
            elif suffix in [".docx", ".doc"]:
                return await self._extract_from_docx(file_path)
            elif suffix in [".txt", ".md"]:
                return await self._extract_from_text(file_path)
            else:
                self.logger.warning(f"Unsupported file format: {suffix}")
                return None
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {e}")
            return None

    async def _extract_from_pdf(self, file_path: Path) -> Optional[str]:
        """从PDF提取文本 - 多引擎支持"""

        # 优先使用MinerU2.5
        if self.mineru_enabled:
            self.logger.info("MinerU extraction attempt for %s", file_path.name)
            try:
                text = await self._extract_with_mineru(file_path)
                if text and len(text.strip()) > 100:  # 确保提取成功
                    self.logger.info(f"Successfully extracted with MinerU from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"MinerU extraction failed: {e}")
        else:
            self.logger.debug(
                "MinerU disabled, skip remote extraction for %s", file_path.name
            )

        # 使用LlamaIndex
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            self.logger.info("Fallback to LlamaIndex extraction for %s", file_path.name)
            try:
                text = await self._extract_with_llamaindex(file_path)
                if text and len(text.strip()) > 100:
                    self.logger.info(f"Successfully extracted with LlamaIndex from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"LlamaIndex extraction failed: {e}")
        return None

    async def _extract_with_mineru(self, file_path: Path) -> Optional[str]:
        """使用 MinerU 在线接口：申请上传 → PUT 文件 → 提交解析 → 拉取结果"""
        if not requests:
            raise ImportError("requests is required for MinerU integration")
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
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError("LlamaIndex is not installed")

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
        response = requests.post(
            f"{self.mineru_base_url}/file-urls/batch",
            headers=self._mineru_headers(),
            json=payload,
            timeout=self.mineru_timeout,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(f"MinerU upload slot failed: {body.get('msg')}")
        upload_urls = body.get("data", {}).get("file_urls") or []
        if not upload_urls:
            raise RuntimeError("MinerU upload slot response missing file_urls")
        batch_id = body.get("data", {}).get("batch_id", "")
        return upload_urls[0], batch_id, data_id

    def _mineru_upload_file(self, upload_url: str, file_path: Path) -> None:
        """上传文件到 MinerU 提供的 OSS 预签名地址。"""
        # 不能自定义 Content-Type，预签名链接已经包含所需签名；多余头会导致 403
        with open(file_path, "rb") as fp:
            response = requests.put(upload_url, data=fp, timeout=self.mineru_timeout)
        response.raise_for_status()

    def _mineru_poll_batch_result(self, batch_id: str, data_id: str) -> Dict[str, Any]:
        """轮询 MinerU 批量任务结果，直到找到对应 data_id。"""
        deadline = time.time() + self.mineru_poll_timeout
        while time.time() < deadline:
            response = requests.get(
                f"{self.mineru_base_url}/extract-results/batch/{batch_id}",
                headers={"Authorization": f"Bearer {self.mineru_api_key}"},
                timeout=self.mineru_timeout,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") != 0:
                raise RuntimeError(f"MinerU poll failed: {body.get('msg')}")
            entries = (
                body.get("data", {}).get("extract_result")
                or body.get("data", {}).get("files")
                or []
            )
            for entry in entries:
                if entry.get("data_id") == data_id:
                    state = entry.get("state") or entry.get("status")
                    if state in {"done", "success"}:
                        return entry
                    if state in {"failed", "error"}:
                        raise RuntimeError(
                            f"MinerU task failed: {entry.get('err_msg') or 'unknown error'}"
                        )
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
        response = requests.get(zip_url, timeout=self.mineru_timeout)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
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

        # 使用LlamaIndex
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            try:
                text = await self._extract_with_llamaindex(file_path)
                if text:
                    return text
            except Exception as e:
                self.logger.warning(f"LlamaIndex DOCX extraction failed: {e}")

        return None

    async def _extract_from_text(self, file_path: Path) -> Optional[str]:
        """从TXT/MD提取文本"""
        try:
            # 直接读取文本文件
            return await asyncio.get_event_loop().run_in_executor(
                None, file_path.read_text, "utf-8"
            )
        except UnicodeDecodeError:
            # 尝试其他编码
            for encoding in ["gbk", "gb2312", "big5"]:
                try:
                    return await asyncio.get_event_loop().run_in_executor(
                        None, file_path.read_text, encoding
                    )
                except:
                    continue
            return None

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
            "file_size": file_path.stat().st_size,
            "file_type": file_path.suffix.lower(),
            "text_length": len(text),
            "extracted_at": datetime.now().isoformat(),
            "extraction_method": self._get_extraction_method(file_path.suffix.lower())
        }

        # 如果使用了MinerU，添加额外的元数据
        if file_path.suffix.lower() == ".pdf" and self.mineru_enabled:
            try:
                # 尝试获取更详细的元数据
                api_url = f"{self.mineru_base_url}/metadata"
                with open(file_path, "rb") as f:
                    files = {"file": (file_path.name, f, "application/pdf")}
                    headers = {"Authorization": f"Bearer {self.mineru_api_key}"}

                    response = requests.post(api_url, files=files, headers=headers, timeout=30)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            metadata.update(result.get("metadata", {}))
            except Exception as e:
                self.logger.debug(f"Failed to get enhanced metadata: {e}")

        metadata["text"] = text
        return metadata

    def _get_extraction_method(self, file_type: str) -> str:
        """获取使用的提取方法"""
        if file_type == ".pdf":
            if self.mineru_enabled:
                return "MinerU2.6 (api)"
            elif self.docling_enabled:
                return "Docling"
            elif self.llamaindex_enabled:
                return "LlamaIndex"
            else:
                return "PyPDF2"
        elif file_type in [".docx", ".doc"]:
            if self.docling_enabled:
                return "Docling"
            elif self.llamaindex_enabled:
                return "LlamaIndex"
            else:
                return "python-docx"
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
            "llamaindex": LLAMAINDEX_AVAILABLE and self.llamaindex_enabled,
        }

        self.logger.info(f"Engine test results: {results}")
        return results

    def _test_mineru(self) -> bool:
        """测试MinerU连接"""
        if not self.mineru_enabled or not requests:
            return False

        try:
            response = requests.get(
                f"{self.mineru_base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
