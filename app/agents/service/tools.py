"""Helper utilities used by AgentService and pipeline agents."""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

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
        self._client: OpenAIChatCompletionClient | None = None
        resolved_key = api_key or os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY")

        if enabled and resolved_key:
            client_args: Dict[str, Any] = {
                "model": model,
                "api_key": resolved_key,
                "model_info": {
                    "vision": True,
                    "function_calling": False,
                    "json_output": False,
                    "family": "unknown",
                },
            }
            if base_url:
                client_args["base_url"] = base_url
            try:
                self._client = OpenAIChatCompletionClient(**client_args)
                self._enabled = True
                logger.info("VisionTool initialized with model {}", model)
            except Exception as exc:  # pragma: no cover - init failure
                self._enabled = False
                logger.error("VisionTool 初始化失败: {}", exc)
        else:
            self._enabled = False
            if enabled:
                logger.warning("VisionTool 启用失败，缺少 API Key 或模型配置。")

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._client)

    async def describe(self, query: str, attachments: List[Attachment]) -> str:
        if not self.enabled or not attachments:
            return ""
        content = self._build_contents(query, attachments)
        if len(content) <= 1:
            return ""
        try:
            response = await self._client.create(  # type: ignore[union-attr]
                [UserMessage(content=content, source="user")]
            )
            return (response.content or "").strip()
        except Exception as exc:  # pragma: no cover - external failure
            logger.error("VisionTool 描述失败: {}", exc)
            return ""

    def _build_contents(self, query: str, attachments: List[Attachment]) -> List[Dict[str, Any]]:
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
        if not attachment.path:
            return None
        path = Path(attachment.path)
        if not path.exists():
            logger.warning("VisionTool 找不到图片路径：{}", attachment.path)
            return None
        mime = attachment.mime_type or mimetypes.guess_type(path.name)[0] or "image/png"
        try:
            data = path.read_bytes()
            encoded = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{encoded}"
        except Exception as exc:  # pragma: no cover - file read error
            logger.error("VisionTool 读取图片失败 {}: {}", path, exc)
            return None


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
