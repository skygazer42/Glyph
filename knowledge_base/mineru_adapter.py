"""
MinerU vLLM接口适配器
"""

import os
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
import aiohttp
import aiofiles

from ..config.settings import settings


class MinerUAdapter:
    """MinerU vLLM接口适配器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化MinerU适配器"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # API配置
        self.base_url = self.config.get("base_url", settings.model.mineru_base_url)
        self.api_key = self.config.get("api_key", settings.model.mineru_api_key)
        self.model = self.config.get("model", settings.model.mineru_model)
        self.temperature = self.config.get("temperature", settings.model.mineru_temperature)
        self.max_tokens = self.config.get("max_tokens", settings.model.mineru_max_tokens)

        # 处理选项
        self.ocr_all_images = self.config.get("ocr_all_images", settings.mineru.ocr_all_images)
        self.ocr_dpi = self.config.get("ocr_dpi", settings.mineru.ocr_dpi)
        self.extract_images = self.config.get("extract_images", settings.mineru.extract_images)
        self.extract_tables = self.config.get("extract_tables", settings.mineru.extract_tables)
        self.extract_lists = self.config.get("extract_lists", settings.mineru.extract_lists)
        self.extract_formulas = self.config.get("extract_formulas", settings.mineru.extract_formulas)
        self.preserve_layout = self.config.get("preserve_layout", settings.mineru.preserve_layout)
        self.output_format = self.config.get("output_format", settings.mineru.output_format)
        self.include_raw_ocr = self.config.get("include_raw_ocr", settings.mineru.include_raw_ocr)

        # 会话管理
        self.session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def _ensure_session(self):
        """确保会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )

    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self._ensure_session()
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    async def extract_document(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """提取文档内容"""
        await self._ensure_session()

        # 合并选项
        extract_options = {
            "ocr_all_images": options.get("ocr_all_images", self.ocr_all_images),
            "ocr_dpi": options.get("ocr_dpi", self.ocr_dpi),
            "extract_images": options.get("extract_images", self.extract_images),
            "extract_tables": options.get("extract_tables", self.extract_tables),
            "extract_lists": options.get("extract_lists", self.extract_lists),
            "extract_formulas": options.get("extract_formulas", self.extract_formulas),
            "preserve_layout": options.get("preserve_layout", self.preserve_layout),
            "output_format": options.get("output_format", self.output_format),
            "include_raw_ocr": options.get("include_raw_ocr", self.include_raw_ocr)
        }

        # 准备文件上传
        data = aiohttp.FormData()
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="application/pdf"
        )

        # 添加选项
        for key, value in extract_options.items():
            data.add_field(key, str(value).lower())

        try:
            # 发送请求
            async with self.session.post(f"{self.base_url}/extract", data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Extraction failed: {response.status} - {error_text}")

                result = await response.json()

                if result.get("success"):
                    return result
                else:
                    raise Exception(f"API error: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Document extraction failed: {e}")
            raise

    async def extract_document_stream(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式提取文档内容"""
        await self._ensure_session()

        # 合并选项（同上）
        extract_options = {
            "ocr_all_images": options.get("ocr_all_images", self.ocr_all_images),
            "ocr_dpi": options.get("ocr_dpi", self.ocr_dpi),
            "extract_images": options.get("extract_images", self.extract_images),
            "extract_tables": options.get("extract_tables", self.extract_tables),
            "extract_lists": options.get("extract_lists", self.extract_lists),
            "extract_formulas": options.get("extract_formulas", self.extract_formulas),
            "preserve_layout": options.get("preserve_layout", self.preserve_layout),
            "output_format": options.get("output_format", self.output_format),
            "include_raw_ocr": options.get("include_raw_ocr", self.include_raw_ocr)
        }

        # 准备文件上传
        data = aiohttp.FormData()
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="application/pdf"
        )

        # 添加选项
        for key, value in extract_options.items():
            data.add_field(key, str(value).lower())
        data.add_field("stream", "true")

        try:
            # 发送流式请求
            async with self.session.post(f"{self.base_url}/extract", data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Stream extraction failed: {response.status} - {error_text}")

                # 处理流式响应
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.logger.error(f"Stream document extraction failed: {e}")
            raise

    async def get_document_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文档元数据"""
        await self._ensure_session()

        # 准备文件上传
        data = aiohttp.FormData()
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="application/pdf"
        )

        try:
            async with self.session.post(f"{self.base_url}/metadata", data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Metadata extraction failed: {response.status} - {error_text}")

                result = await response.json()
                return result

        except Exception as e:
            self.logger.error(f"Document metadata extraction failed: {e}")
            raise

    async def extract_pages(
        self,
        file_path: str,
        pages: List[int],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """提取指定页面"""
        await self._ensure_session()

        # 合并选项
        extract_options = {
            "ocr_all_images": options.get("ocr_all_images", self.ocr_all_images),
            "ocr_dpi": options.get("ocr_dpi", self.ocr_dpi),
            "extract_images": options.get("extract_images", self.extract_images),
            "extract_tables": options.get("extract_tables", self.extract_tables),
            "extract_lists": options.get("extract_lists", self.extract_lists),
            "extract_formulas": options.get("extract_formulas", self.extract_formulas),
            "preserve_layout": options.get("preserve_layout", self.preserve_layout),
            "output_format": options.get("output_format", self.output_format),
            "include_raw_ocr": options.get("include_raw_ocr", self.include_raw_ocr)
        }

        # 添加页面范围
        extract_options["pages"] = ",".join(map(str, pages))

        # 准备文件上传
        data = aiohttp.FormData()
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="application/pdf"
        )

        # 添加选项
        for key, value in extract_options.items():
            data.add_field(key, str(value))

        try:
            async with self.session.post(f"{self.base_url}/extract", data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Page extraction failed: {response.status} - {error_text}")

                result = await response.json()
                return result

        except Exception as e:
            self.logger.error(f"Page extraction failed: {e}")
            raise

    async def batch_extract(
        self,
        file_paths: List[str],
        options: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """批量提取文档"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_single(file_path: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.extract_document(file_path, options)
                except Exception as e:
                    self.logger.error(f"Failed to extract {file_path}: {e}")
                    return {
                        "success": False,
                        "file_path": file_path,
                        "error": str(e)
                    }

        # 并发处理
        tasks = [extract_single(path) for path in file_paths]
        results = await asyncio.gather(*tasks)
        return results

    def get_extraction_stats(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """获取提取统计信息"""
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }

        content = result.get("content", {})
        stats = {
            "success": True,
            "text_length": len(content.get("markdown", "")) or len(content.get("raw_text", "")),
            "has_tables": content.get("has_tables", False),
            "has_images": content.get("has_images", False),
            "has_formulas": content.get("has_formulas", False),
            "pages_processed": content.get("pages_processed", 0),
            "ocr_performed": content.get("ocr_performed", False),
            "extraction_time": result.get("extraction_time", 0),
            "file_size": result.get("file_size", 0)
        }

        # 添加详细信息
        if "images" in content:
            stats["image_count"] = len(content["images"])
        if "tables" in content:
            stats["table_count"] = len(content["tables"])
        if "formulas" in content:
            stats["formula_count"] = len(content["formulas"])

        return stats