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

# 导入基础库
try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    requests = None
    RequestException = None

# 导入Docling (优先使用)
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

# 导入LlamaIndex (备选)
try:
    from llama_index.core import SimpleDirectoryReader
    from llama_index.core.readers import PDFReader
    from llama_index.readers.file import DocxReader, TextReader
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False

# 导入原有的处理库作为后备
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import docx
except ImportError:
    docx = None

from ..config.settings import settings


class EnhancedDocumentProcessor:
    """增强文档处理器 - 支持多种文档解析引擎"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化MinerU客户端
        self.mineru_enabled = self.config.get("mineru_enabled", True)
        self.mineru_base_url = self.config.get("mineru_base_url", settings.model.mineru_base_url)
        self.mineru_api_key = self.config.get("mineru_api_key", settings.model.mineru_api_key)

        # 初始化Docling转换器
        self.docling_enabled = self.config.get("docling_enabled", DOCLING_AVAILABLE)
        if self.docling_enabled and DOCLING_AVAILABLE:
            self.docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfPipelineOptions(
                        generate_table_images=True,
                        generate_picture_images=True,
                        do_ocr=True,
                        ocr_options={"lang": ["zh", "en"]}
                    )
                }
            )
            self.logger.info("Docling converter initialized")

        # 初始化LlamaIndex读取器
        self.llamaindex_enabled = self.config.get("llamaindex_enabled", LLAMAINDEX_AVAILABLE)
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            self.llamaindex_readers = {
                ".pdf": PDFReader(),
                ".docx": DocxReader(),
                ".doc": DocxReader(),
                ".txt": TextReader(),
                ".md": TextReader()
            }
            self.logger.info("LlamaIndex readers initialized")

        # 处理选项
        self.ocr_enabled = self.config.get("ocr_enabled", settings.document.enable_ocr)
        self.table_extraction = self.config.get("table_extraction", settings.document.enable_table_extraction)
        self.image_extraction = self.config.get("image_extraction", settings.document.enable_image_extraction)

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

        # 备选：使用Docling
        if self.docling_enabled and DOCLING_AVAILABLE:
            try:
                text = await self._extract_with_docling(file_path)
                if text and len(text.strip()) > 100:
                    self.logger.info(f"Successfully extracted with Docling from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"Docling extraction failed: {e}")

        # 备选：使用LlamaIndex
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            try:
                text = await self._extract_with_llamaindex(file_path)
                if text and len(text.strip()) > 100:
                    self.logger.info(f"Successfully extracted with LlamaIndex from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"LlamaIndex extraction failed: {e}")

        # 最后使用PyPDF2作为后备
        if PyPDF2 is not None:
            try:
                text = await self._extract_with_pypdf2(file_path)
                if text and len(text.strip()) > 0:
                    self.logger.info(f"Successfully extracted with PyPDF2 from {file_path.name}")
                    return text
            except Exception as e:
                self.logger.warning(f"PyPDF2 extraction failed: {e}")

        self.logger.error(f"All PDF extraction methods failed for {file_path.name}")
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

    async def _extract_with_docling(self, file_path: Path) -> Optional[str]:
        """使用Docling提取文档"""
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling is not installed")

        # Docling是同步的，使用线程池执行
        loop = asyncio.get_event_loop()

        def _process_with_docling():
            result = self.docling_converter.convert(str(file_path))
            if result.document:
                # 导出为markdown
                return result.document.export_to_markdown()
            return None

        return await loop.run_in_executor(None, _process_with_docling)

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

    async def _extract_with_pypdf2(self, file_path: Path) -> Optional[str]:
        """使用PyPDF2提取PDF（后备方案）"""
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is not installed")

        loop = asyncio.get_event_loop()

        def _process_with_pypdf2():
            text = []
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text.append(page.extract_text())
            return "\n".join(text)

        return await loop.run_in_executor(None, _process_with_pypdf2)

    async def _extract_from_docx(self, file_path: Path) -> Optional[str]:
        """从DOCX提取文本"""

        # 优先使用Docling
        if self.docling_enabled and DOCLING_AVAILABLE:
            try:
                text = await self._extract_with_docling(file_path)
                if text:
                    return text
            except Exception as e:
                self.logger.warning(f"Docling DOCX extraction failed: {e}")

        # 备选：使用LlamaIndex
        if self.llamaindex_enabled and LLAMAINDEX_AVAILABLE:
            try:
                text = await self._extract_with_llamaindex(file_path)
                if text:
                    return text
            except Exception as e:
                self.logger.warning(f"LlamaIndex DOCX extraction failed: {e}")

        # 最后使用python-docx
        if docx is not None:
            loop = asyncio.get_event_loop()

            def _process_with_docx():
                doc = docx.Document(file_path)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return "\n".join(text)

            return await loop.run_in_executor(None, _process_with_docx)

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

        if self.mineru_enabled or self.docling_enabled or self.llamaindex_enabled or PyPDF2:
            formats.append(".pdf")

        if self.docling_enabled or self.llamaindex_enabled or docx:
            formats.extend([".docx", ".doc"])

        return formats

    def test_engines(self) -> Dict[str, bool]:
        """测试各个引擎是否可用"""
        results = {
            "mineru": self._test_mineru(),
            "docling": DOCLING_AVAILABLE and self.docling_enabled,
            "llamaindex": LLAMAINDEX_AVAILABLE and self.llamaindex_enabled,
            "pypdf2": PyPDF2 is not None,
            "docx": docx is not None
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