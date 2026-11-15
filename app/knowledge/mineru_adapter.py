"""
MinerU 文档解析适配器

支持两种模式：
1. 官方云服务 API (https://mineru.net)
2. 本地服务 API (http://localhost:30001)
"""

import os
import logging
import json
import asyncio
import anyio
import io
import zipfile
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal
import aiohttp
import aiofiles

from app.config.app_config import settings


from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MinerUApiResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    code: int
    msg: str | None = None
    data: dict[str, Any] | None = None


class MinerUUploadData(BaseModel):
    model_config = ConfigDict(strict=True)
    batch_id: str = Field(min_length=1)
    file_urls: list[str] = Field(min_length=1)


class MinerUTaskFile(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    state: str = Field(min_length=1)
    full_zip_url: str | None = None
    err_msg: str | None = None


class MinerUTaskData(BaseModel):
    model_config = ConfigDict(strict=True)
    # An empty list while the service schedules a task is a real pending state.
    extract_result: list[MinerUTaskFile] = Field(default_factory=list)


class MinerULocalFile(BaseModel):
    model_config = ConfigDict(strict=True)
    markdown: str = Field(min_length=1, validation_alias=AliasChoices("md", "markdown", "md_content"))


class MinerULocalResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    results: dict[str, MinerULocalFile] = Field(min_length=1)


class MinerUArchiveContent(BaseModel):
    model_config = ConfigDict(strict=True)
    content: str


class MinerUAdapter:
    """MinerU 文档解析适配器 - 支持官方 API 和本地服务"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        mode: Literal["official", "local", "auto"] = "auto"
    ):
        """
        初始化 MinerU 适配器

        Args:
            config: 配置字典（可选）
            mode: 运行模式
                - "official": 使用官方云服务 API
                - "local": 使用本地服务 API
                - "auto": 自动检测（默认）
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # API配置 - 使用 settings.mineru
        self.enabled = self.config.get("enabled", settings.mineru.enabled)
        self.api_key = self.config.get("api_key", settings.mineru.api_key)
        self.timeout = self.config.get("timeout", settings.mineru.timeout)

        # 自动检测模式
        if mode == "auto":
            # 如果有 API key，优先使用官方 API
            if self.api_key:
                self.mode = "official"
                self.base_url = "https://mineru.net/api/v4"
            else:
                self.mode = "local"
                self.base_url = self.config.get("base_url", settings.mineru.api_base_url)
        else:
            self.mode = mode
            if mode == "official":
                self.base_url = "https://mineru.net/api/v4"
            else:
                self.base_url = self.config.get("base_url", settings.mineru.api_base_url)

        # 处理选项
        self.ocr_enabled = self.config.get("ocr_all_images", settings.mineru.ocr_all_images)
        self.extract_images = self.config.get("extract_images", settings.mineru.extract_images)
        self.extract_tables = self.config.get("extract_tables", settings.mineru.extract_tables)
        self.extract_formulas = self.config.get("extract_formulas", settings.mineru.extract_formulas)
        self.language = self.config.get("language", "ch")  # 默认中文
        self.backend = self.config.get("backend", "vlm-http-client")  # 本地服务后端

        # 会话管理
        self.session: Optional[aiohttp.ClientSession] = None

        self.logger.info(f"MinerU 适配器初始化: mode={self.mode}, url={self.base_url}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取可用的 HTTP 会话，首次调用时创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers: Dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
        return self.session

    async def close(self):
        """关闭会话"""
        session, self.session = self.session, None
        if session is not None and not session.closed:
            with anyio.fail_after(5, shield=True):
                await session.close()

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康状态信息
                - status: "healthy" | "unhealthy" | "unavailable" | "error"
                - message: 状态描述
                - details: 详细信息
        """
        try:
            await self._get_session()

            if self.mode == "official":
                # 官方 API: 测试创建任务
                return await self._health_check_official()
            else:
                # 本地服务: 检查 OpenAPI 端点
                return await self._health_check_local()

        except Exception as e:
            self.logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"健康检查失败: {str(e)}",
                "details": {"mode": self.mode, "error": str(e)}
            }

    async def _health_check_official(self) -> Dict[str, Any]:
        """官方 API 健康检查"""
        session = await self._get_session()
        try:
            # 测试 API key 有效性
            test_data = {
                "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
                "is_ocr": True
            }

            async with session.post(
                f"{self.base_url}/extract/task",
                json=test_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 401:
                    return {
                        "status": "unhealthy",
                        "message": "API 密钥无效或已过期",
                        "details": {"error_code": "A0202"}
                    }
                elif response.status == 403:
                    return {
                        "status": "unhealthy",
                        "message": "API 密钥权限不足",
                        "details": {"error_code": "A0211"}
                    }
                elif response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        return {
                            "status": "healthy",
                            "message": "MinerU 官方 API 服务可用",
                            "details": {"api_base": self.base_url}
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "message": f"API 返回错误: {result.get('msg', '未知错误')}",
                            "details": {"error_code": result.get("code")}
                        }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"API 服务异常: HTTP {response.status}",
                        "details": {"status_code": response.status}
                    }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "message": "API 请求超时",
                "details": {"timeout": "10s"}
            }
        except aiohttp.ClientError:
            return {
                "status": "unavailable",
                "message": "无法连接到 MinerU 官方 API 服务",
                "details": {"api_base": self.base_url}
            }

    async def _health_check_local(self) -> Dict[str, Any]:
        """本地服务健康检查"""
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.base_url}/openapi.json",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    openapi_data = await response.json()
                    has_file_parse = "/file_parse" in openapi_data.get("paths", {})

                    if has_file_parse:
                        return {
                            "status": "healthy",
                            "message": "MinerU 本地服务运行正常",
                            "details": {
                                "server_url": self.base_url,
                                "api_version": openapi_data.get("info", {}).get("version", "unknown")
                            }
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "message": "MinerU 服务缺少必要的端点",
                            "details": {"server_url": self.base_url}
                        }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"MinerU 服务响应异常: {response.status}",
                        "details": {"server_url": self.base_url}
                    }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "message": "MinerU 服务连接超时",
                "details": {"server_url": self.base_url}
            }
        except aiohttp.ClientError:
            return {
                "status": "unavailable",
                "message": "MinerU 服务无法连接,请检查服务是否启动",
                "details": {"server_url": self.base_url}
            }

    async def extract_document(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        提取文档内容

        Args:
            file_path: 文件路径
            options: 处理参数
                官方 API:
                    - is_ocr: 是否启用 OCR (默认: True)
                    - enable_formula: 是否启用公式识别 (默认: True)
                    - enable_table: 是否启用表格识别 (默认: True)
                    - language: 文档语言 (默认: "ch")
                    - page_ranges: 页码范围 (默认: None)
                本地服务:
                    - lang_list: 语言列表 (默认: ["ch"])
                    - backend: 后端类型 (默认: "vlm-http-client")
                    - parse_method: 解析方法 (默认: "auto")
                    - server_url: VLM 服务器地址 (vlm-http-client 时需要)

        Returns:
            Dict: 提取结果
                - success: bool
                - content: 提取的内容（markdown 格式）
                - metadata: 元数据
                - processing_time: 处理时间
        """
        if not await asyncio.to_thread(os.path.exists, file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检查服务健康状态
        health = await self.health_check()
        if health["status"] != "healthy":
            raise RuntimeError(f"MinerU 服务不可用: {health['message']}")

        start_time = time.time()
        options = options or {}

        try:
            self.logger.info(f"MinerU 开始处理: {os.path.basename(file_path)} (mode={self.mode})")

            if self.mode == "official":
                result = await self._extract_official(file_path, options)
            else:
                result = await self._extract_local(file_path, options)

            processing_time = time.time() - start_time
            result["processing_time"] = processing_time

            self.logger.info(
                f"MinerU 处理成功: {os.path.basename(file_path)} - "
                f"{len(result['content'])} 字符 ({processing_time:.2f}s)"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"MinerU 处理失败: {str(e)} ({processing_time:.2f}s)"
            self.logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
                "processing_time": processing_time
            }

    async def _extract_official(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用官方 API 提取文档"""
        # 步骤 1: 上传文件
        batch_id = await self._upload_file_official(file_path, options)
        self.logger.info(f"文件上传成功，batch_id: {batch_id}")

        # 步骤 2: 轮询任务结果
        result = await self._poll_batch_result(batch_id)
        self.logger.info(f"任务完成，状态: {result['state']}")

        # 步骤 3: 下载并解压结果
        content = await self._download_and_extract(result["full_zip_url"])

        return {
            "success": True,
            "content": content,
            "metadata": {
                "batch_id": batch_id,
                "state": result["state"],
                "file_name": os.path.basename(file_path)
            }
        }

    async def _upload_file_official(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> str:
        """上传文件到官方 API 并返回 batch_id"""
        filename = os.path.basename(file_path)

        upload_data = {
            "enable_formula": options.get("enable_formula", self.extract_formulas),
            "enable_table": options.get("enable_table", self.extract_tables),
            "language": options.get("language", self.language),
            "files": [{
                "name": filename,
                "is_ocr": options.get("is_ocr", self.ocr_enabled),
                "data_id": filename[:30],
                "page_ranges": options.get("page_ranges"),
            }]
        }

        session = await self._get_session()
        # 申请上传链接
        async with session.post(
            f"{self.base_url}/file-urls/batch",
            json=upload_data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"申请上传链接失败: HTTP {response.status}")

            result = MinerUApiResponse.model_validate(await response.json())
            if result.code != 0:
                raise RuntimeError(f"申请上传链接失败: {result.msg}")
            upload = MinerUUploadData.model_validate(result.data)
            batch_id, upload_urls = upload.batch_id, upload.file_urls

        # 上传文件
        upload_url = upload_urls[0]
        async with aiofiles.open(file_path, "rb") as f:
            file_data = await f.read()

        # The pre-signed object-storage URL must not receive our MinerU bearer token.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as upload_session:
            async with upload_session.put(upload_url, data=file_data) as response:
                response.raise_for_status()

        return batch_id

    async def _poll_batch_result(
        self,
        batch_id: str,
        max_wait_time: int = 600
    ) -> Dict[str, Any]:
        """轮询批量任务结果"""
        session = await self._get_session()
        start_time = time.monotonic()

        while time.monotonic() - start_time < max_wait_time:
            async with session.get(
                f"{self.base_url}/extract-results/batch/{batch_id}",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"查询任务状态失败: HTTP {response.status}")

                result = MinerUApiResponse.model_validate(await response.json())
                if result.code != 0:
                    raise RuntimeError(f"查询任务状态失败: {result.msg}")
                task = MinerUTaskData.model_validate(result.data)
                if not task.extract_result:
                    await asyncio.sleep(5)
                    continue
                file_result = task.extract_result[0]
                if file_result.state == "done":
                    if not file_result.full_zip_url:
                        raise ValueError("Completed MinerU task requires full_zip_url")
                    return file_result.model_dump(exclude_none=True)
                if file_result.state == "failed":
                    raise RuntimeError(f"文档解析失败: {file_result.err_msg}")

                # 继续等待
                await asyncio.sleep(5)

        raise TimeoutError("任务处理超时")

    async def _download_and_extract(self, zip_url: str) -> str:
        """下载并解压结果文件"""
        if not zip_url:
            raise RuntimeError("未获取到结果下载链接")

        # Signed object-storage URLs must not receive the API bearer token.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(zip_url) as response:
                response.raise_for_status()
                zip_content = await response.read()

        return await asyncio.to_thread(self._read_result_archive, zip_content)

    @staticmethod
    def _read_result_archive(zip_content: bytes) -> str:
        """Read result members without extracting paths or creating temporary files."""
        with zipfile.ZipFile(io.BytesIO(zip_content)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            markdown = next((name for name in names if Path(name).name == "full.md"), None)
            if markdown is None:
                markdown = next((name for name in names if name.lower().endswith(".md")), None)
            if markdown is not None:
                return archive.read(markdown).decode("utf-8")
            result_json = next((name for name in names if name.lower().endswith(".json")), None)
            if result_json is not None:
                return MinerUArchiveContent.model_validate_json(archive.read(result_json)).content
        raise RuntimeError("无法从结果中提取文本内容")

    async def _extract_local(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用本地服务提取文档"""
        # 构建请求数据
        data = aiohttp.FormData()

        # 添加文件
        async with aiofiles.open(file_path, "rb") as f:
            file_content = await f.read()

        data.add_field(
            "files",
            file_content,
            filename=os.path.basename(file_path),
            content_type="application/octet-stream"
        )

        # 添加参数
        data.add_field("lang_list", json.dumps(options.get("lang_list", [self.language])))
        data.add_field("backend", options.get("backend", self.backend))
        data.add_field("parse_method", options.get("parse_method", "auto"))
        data.add_field("return_md", "true")

        # vlm-http-client 需要 server_url
        if options.get("backend") == "vlm-http-client" and options.get("server_url"):
            data.add_field("server_url", options["server_url"])

        session = await self._get_session()
        # 发送请求
        async with session.post(
            f"{self.base_url}/file_parse",
            data=data,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as response:
            if response.status != 200:
                error_detail = "未知错误"
                try:
                    error_data = await response.json()
                    error_detail = error_data.get("detail", str(error_data))
                except (ValueError, aiohttp.ContentTypeError):
                    error_detail = await response.text() or f"HTTP {response.status}"

                raise RuntimeError(f"MinerU 处理失败: {error_detail}")

            # 解析响应
            result = MinerULocalResponse.model_validate(await response.json())
            file_result = next(iter(result.results.values()))
            content = file_result.markdown
            if not content.strip():
                raise RuntimeError("MinerU 未返回任何文本内容")

            return {
                "success": True,
                "content": content,
                "metadata": {
                    "backend": options.get("backend", self.backend),
                    "file_name": os.path.basename(file_path)
                }
            }

    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        if self.mode == "official":
            return [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"]
        else:
            return [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]

    def supports_file_type(self, file_ext: str) -> bool:
        """检查是否支持该文件类型"""
        return file_ext.lower() in self.get_supported_extensions()

    async def batch_extract(
        self,
        file_paths: List[str],
        options: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        批量提取文档

        Args:
            file_paths: 文件路径列表
            options: 处理参数
            max_concurrent: 最大并发数

        Returns:
            List[Dict]: 提取结果列表
        """
        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_single(file_path: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.extract_document(file_path, options)
                except Exception as e:
                    self.logger.error(f"Failed to extract {file_path}: {e}", exc_info=True)
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
        """
        获取提取统计信息

        Args:
            result: extract_document 返回的结果

        Returns:
            Dict: 统计信息
        """
        if not result["success"]:
            return {
                "success": False,
                "error": result["error"]
            }

        content = result["content"]
        metadata = result["metadata"]

        stats = {
            "success": True,
            "text_length": len(content),
            "processing_time": result["processing_time"],
            "file_name": metadata["file_name"],
            "mode": self.mode
        }

        # 添加模式相关的统计
        if self.mode == "official":
            stats["batch_id"] = metadata["batch_id"]
            stats["state"] = metadata["state"]
        else:
            stats["backend"] = metadata["backend"]

        return stats

    def get_info(self) -> Dict[str, Any]:
        """获取适配器信息"""
        return {
            "mode": self.mode,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
            "timeout": self.timeout,
            "supported_extensions": self.get_supported_extensions(),
            "options": {
                "ocr_enabled": self.ocr_enabled,
                "extract_images": self.extract_images,
                "extract_tables": self.extract_tables,
                "extract_formulas": self.extract_formulas,
                "language": self.language,
                "backend": self.backend if self.mode == "local" else None
            }
        }