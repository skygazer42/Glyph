"""Helper utilities used by AgentService and pipeline agents."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from openai import AsyncOpenAI

from app.agents.framework.base.types import PolicyDocument
from app.agents.packs.intent_router.utils import LLMIntentClassifier
from app.knowledge.service import KnowledgeService
from app.models.base import Attachment

try:
    from tavily import TavilyClient
except Exception:  # pragma: no cover - optional dependency
    TavilyClient = None

class IntentDetectionTool:
    """Lightweight wrapper around the intent router classifier."""

    def __init__(self, classifier: LLMIntentClassifier | None = None) -> None:
        self.classifier = classifier or LLMIntentClassifier()

    async def detect(self, query: str) -> Dict[str, Any]:
        result = await self.classifier.classify(query)
        if result:
            return result
        # 默认兜底意图
        return {
            "intent": "policy_inquiry",
            "confidence": 0.3,
            "processing_chain": [
                "knowledge_retriever",
                "policy_analyzer",
                "answer_generator",
            ],
            "chains": ["kb_chain"],
        }


class KnowledgeTool:
    """Async facade sitting on top of KnowledgeService."""

    def __init__(self, service: KnowledgeService | None = None) -> None:
        self._service = service

    @property
    def service(self) -> KnowledgeService:
        if self._service is None:
            self._service = KnowledgeService()
        return self._service

    async def ingest(self, documents: List[PolicyDocument]) -> int:
        return await self.service.index_documents(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return await self.service.search(
            query, top_k=top_k, threshold=threshold, filters=filters
        )


class WebSearchTool:
    """Simple Tavily-backed web search helper for fallback retrieval."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_results: int = 3,
        search_depth: str = "basic",
        enabled: bool | None = None,
        site_filter: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.max_results = max_results
        self.search_depth = search_depth
        self.site_filter = (site_filter or "").strip()
        self._client = None

        if enabled is False:
            self._enabled = False
            logger.debug("Web search fallback disabled via configuration.")
            return

        self._enabled = bool(self.api_key and TavilyClient is not None)

        if self._enabled:
            self._client = TavilyClient(api_key=self.api_key)
            logger.info("WebSearchTool initialized with Tavily client.")
        else:
            if self.api_key and TavilyClient is None:
                logger.warning(
                    "tavily-python is not installed; disabling web search fallback."
                )
            elif enabled:
                logger.warning(
                    "Web search explicitly enabled but TAVILY_API_KEY/tavily client unavailable."
                )
            else:
                logger.debug("TAVILY_API_KEY not provided; web search fallback disabled.")

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._client)

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        limit = max_results or self.max_results
        search_query = query
        if self.site_filter:
            suffix = self.site_filter
            if not suffix.lower().startswith("site:"):
                suffix = f"site:{suffix}"
            search_query = f"{query} {suffix}".strip()
        try:
            response = self._client.search(
                query=search_query,
                search_depth=self.search_depth,
                max_results=limit,
            )
            results = response.get("results", [])
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Web search failed: %s", exc)
            return []

        formatted = []
        for item in results[:limit]:
            formatted.append(
                {
                    "title": item.get("title", "").strip(),
                    "content": item.get("content", "").strip(),
                    "url": item.get("url", ""),
                    "score": item.get("score", 0.0),
                }
            )
        return formatted

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "暂无可用的网络检索结果。"
        lines = ["以下为网络检索的关键信息："]
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "未提供标题"
            content = item.get("content", "")
            lines.append(
                f"\n[{idx}] 标题：{title}\n"
                f"内容：{content[:400]}\n来源：{item.get('url', '')}\n"
            )
        return "\n".join(lines)


class VisionTool:
    """Vision-capable helper that routes images to a multimodal model."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        prompt_template: str = "",
        max_images: int = 2,
        max_output_tokens: int = 800,
    ) -> None:
        self.prompt_template = prompt_template or "请描述图片中的关键信息。"
        self.max_images = max(1, max_images)
        self.max_output_tokens = max_output_tokens
        self._client: AsyncOpenAI | None = None
        self._dashscope_client = None
        self._dashscope_api_key: Optional[str] = None
        self._mode: str = "disabled"
        self._model_name = model
        resolved_key = api_key or os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY")

        if enabled and resolved_key:
            dashscope_mode = bool(base_url and "dashscope.aliyuncs.com" in base_url.lower())
            if dashscope_mode:
                self._initialize_dashscope(resolved_key)
            else:
                self._initialize_openai(resolved_key, base_url)
        else:
            self._enabled = False
            if enabled:
                logger.warning("VisionTool 启用失败，缺少 API Key 或模型配置。")

    @property
    def enabled(self) -> bool:
        if not self._enabled:
            return False
        if self._mode == "dashscope":
            return bool(self._dashscope_client and self._dashscope_api_key)
        return bool(self._client)

    async def describe(self, query: str, attachments: List[Attachment]) -> str:
        if not self.enabled or not attachments:
            return ""
        if self._mode == "dashscope":
            return await self._describe_dashscope(query, attachments)
        return await self._describe_openai(query, attachments)

    def _build_openai_contents(self, query: str, attachments: List[Attachment]) -> List[Dict[str, Any]]:
        prompt = self.prompt_template.format(query=query)
        payload: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        added = 0
        for attachment in attachments:
            if added >= self.max_images:
                break
            image_url = self._resolve_image_url(attachment)
            if not image_url:
                continue
            payload.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                }
            )
            added += 1
        if added == 0:
            logger.debug("VisionTool 未找到可用图片，跳过多模态调用。")
        return payload

    def _resolve_image_url(self, attachment: Attachment) -> Optional[str]:
        if attachment.url:
            return attachment.url
        path = self._resolve_local_image_path(attachment)
        if not path:
            return None
        mime = attachment.mime_type or mimetypes.guess_type(path.name)[0] or "image/png"
        try:
            data = path.read_bytes()
            encoded = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{encoded}"
        except Exception as exc:  # pragma: no cover - file read error
            logger.error("VisionTool 读取图片失败 {}: {}", path, exc)
            return None

    def _resolve_dashscope_image_ref(self, attachment: Attachment) -> Optional[str]:
        if attachment.url and attachment.url.startswith(("http://", "https://", "oss://")):
            return attachment.url
        path = self._resolve_local_image_path(attachment)
        if not path:
            return None
        try:
            return path.resolve().as_uri()
        except ValueError:
            resolved = path.resolve()
            return f"file://{resolved}"

    def _resolve_local_image_path(self, attachment: Attachment) -> Optional[Path]:
        if not attachment.path:
            return None
        path = Path(attachment.path)
        if not path.exists():
            logger.warning("VisionTool 找不到图片路径：{}", attachment.path)
            return None
        return path

    def _initialize_openai(self, api_key: str, base_url: Optional[str]) -> None:
        try:
            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self._client = AsyncOpenAI(**client_kwargs)
            self._enabled = True
            self._mode = "openai"
            logger.info("VisionTool initialized with model {}", self._model_name)
        except Exception as exc:  # pragma: no cover - init failure
            self._enabled = False
            logger.error("VisionTool 初始化失败: {}", exc)

    def _initialize_dashscope(self, api_key: str) -> None:
        try:
            from dashscope import MultiModalConversation  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency failure
            self._enabled = False
            logger.error("VisionTool 初始化 DashScope SDK 失败: {}", exc)
            return
        self._dashscope_client = MultiModalConversation
        self._dashscope_api_key = api_key
        self._mode = "dashscope"
        self._enabled = True
        logger.info("VisionTool initialized with DashScope model {}", self._model_name)

    async def _describe_openai(self, query: str, attachments: List[Attachment]) -> str:
        if not self._client:
            return ""
        content = self._build_openai_contents(query, attachments)
        if not content or len(content) <= 1:
            return ""
        try:
            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=self.max_output_tokens,
            )
        except Exception as exc:  # pragma: no cover - external failure
            logger.error("VisionTool 描述失败: {}", exc)
            return ""
        choice = (response.choices or [None])[0]
        if choice and choice.message and choice.message.content:
            return choice.message.content.strip()
        return ""

    async def _describe_dashscope(self, query: str, attachments: List[Attachment]) -> str:
        if not self._dashscope_client or not self._dashscope_api_key:
            return ""
        messages = self._build_dashscope_messages(query, attachments)
        if not messages:
            return ""
        try:
            response = await asyncio.to_thread(
                self._dashscope_client.call,
                model=self._model_name,
                messages=messages,
                api_key=self._dashscope_api_key,
                max_tokens=self.max_output_tokens,
            )
        except Exception as exc:  # pragma: no cover - external failure
            logger.error("VisionTool DashScope 描述失败: {}", exc)
            return ""
        if not response or response.status_code != HTTPStatus.OK:
            code = getattr(response, "code", "unknown")
            message = getattr(response, "message", "unknown error")
            logger.error(
                "VisionTool DashScope 返回异常 code=%s message=%s",
                code,
                message,
            )
            return ""
        text = self._extract_dashscope_text(response)
        return text.strip() if text else ""

    def _build_dashscope_messages(
        self, query: str, attachments: List[Attachment]
    ) -> List[Dict[str, Any]]:
        prompt = self.prompt_template.format(query=query)
        contents: List[Dict[str, Any]] = []
        added = 0
        for attachment in attachments:
            if added >= self.max_images:
                break
            image_ref = self._resolve_dashscope_image_ref(attachment)
            if not image_ref:
                continue
            contents.append({"image": image_ref})
            added += 1
        if added == 0:
            logger.debug("VisionTool 未找到可用于 DashScope 的图片，跳过多模态调用。")
            return []
        contents.append({"text": prompt})
        return [{"role": "user", "content": contents}]

    def _extract_dashscope_text(self, response: Any) -> str:
        output = getattr(response, "output", None)
        if not output:
            return ""
        if isinstance(output, dict):
            text = output.get("text")
            choices = output.get("choices")
        else:
            text = getattr(output, "text", None)
            choices = getattr(output, "choices", None)
        if text:
            return str(text)
        if not choices:
            return ""
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
            if not message:
                continue
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", None)
            )
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        value = item.get("text")
                        if value:
                            texts.append(value)
                    elif isinstance(item, str):
                        texts.append(item)
                if texts:
                    return "\n".join(texts)
        return ""


class UserProfileTool:
    """Simple helper for querying user profile/history records."""

    def __init__(self, db_path: Optional[str] = None, preset_db: Optional[Dict[str, Any]] = None) -> None:
        self.db_path = db_path or "resources/data/user_profiles.json"
        self._db = preset_db or {}
        self._load_from_file()

    def _load_from_file(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            logger.warning("UserProfileTool 未找到数据库文件：%s", path)
            return
        try:
            import json

            with path.open("r", encoding="utf-8") as f:
                self._db = json.load(f) or {}
            logger.info("UserProfileTool 已加载 %s 条用户历史记录", len(self._db))
        except Exception as exc:
            logger.error("UserProfileTool 载入失败 %s: %s", path, exc)

    async def fetch(self, user_id: str) -> Dict[str, Any]:
        profile = self._db.get(user_id)
        if profile:
            return {"user_id": user_id, "found": True, **profile}
        return {
            "user_id": user_id,
            "found": False,
            "message": "系统中未找到该用户的历史记录。",
        }

    def format_profile(self, profile: Dict[str, Any]) -> str:
        if not profile.get("found"):
            return profile.get("message", "暂无记录")
        history = profile.get("history") or []
        history_text = "\n  - ".join(history) if history else "无历史记录"
        return (
            f"用户：{profile.get('name','未知')}（ID: {profile['user_id']}）\n"
            f"所属地区：{profile.get('region','未知')}  等级：{profile.get('level','未知')}\n"
            f"最近登录：{profile.get('last_login','未知')}\n"
            f"历史事件：\n  - {history_text}"
        )


__all__ = ["IntentDetectionTool", "KnowledgeTool", "WebSearchTool", "VisionTool", "UserProfileTool"]
