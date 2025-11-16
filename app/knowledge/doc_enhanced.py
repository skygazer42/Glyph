"""
增强文档处理器 - 使用MinerU2.5和Docling/LlamaIndex
"""

import os
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import tempfile
import subprocess
import sys
from datetime import datetime
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
            try:
                text = await self._extract_with_mineru(file_path)
                if text and len(text.strip()) > 100:  # 确保提取成功
                    self.logger.info(f"Successfully extracted with MinerU from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"MinerU extraction failed: {e}")



        # 使用LlamaIndex
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            try:
                text = await self._extract_with_llamaindex(file_path)
                if text and len(text.strip()) > 100:
                    self.logger.info(f"Successfully extracted with LlamaIndex from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"LlamaIndex extraction failed: {e}")
        return None

    async def _extract_with_mineru(self, file_path: Path) -> Optional[str]:
        """使用MinerU2.5 (vLLM接口) 提取PDF"""
        if not requests:
            raise ImportError("requests is required for MinerU integration")

        # 准备API请求
        api_url = f"{self.mineru_base_url}/extract"

        # 读取文件
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            headers = {"Authorization": f"Bearer {self.mineru_api_key}"}

            # 添加处理选项
            data = {
                "ocr_all_images": "true" if self.ocr_enabled else "false",
                "extract_tables": "true" if self.table_extraction else "false",
                "extract_images": "true" if self.image_extraction else "false",
                "output_format": "markdown",
                "include_raw_ocr": "true"
            }

            # 发送请求
            response = requests.post(api_url, files=files, headers=headers, data=data, timeout=60)
            response.raise_for_status()

            result = response.json()

            # 提取文本内容
            if result.get("success"):
                content = result.get("content", {})
                markdown_text = content.get("markdown", "")
                raw_text = content.get("raw_text", "")

                # 优先使用markdown格式
                if markdown_text:
                    return markdown_text
                elif raw_text:
                    return raw_text
                else:
                    return None
            else:
                raise Exception(f"MinerU API error: {result.get('error', 'Unknown error')}")


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
                return "MinerU2.5 (vLLM)"
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
