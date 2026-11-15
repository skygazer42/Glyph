"""Helper utilities used by AgentService and pipeline agents."""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
from copy import deepcopy
from contextvars import ContextVar
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anyio.to_thread import run_sync
from dashscope import MultiModalConversation
import requests
from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionContentPartParam
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from tavily import TavilyClient

from app.agents.packs.intent_router.utils import LLMIntentClassifier
from app.knowledge.service import KnowledgeService
from app.models.base import Attachment, PolicyDocument, PolicyType
from app.utils.lifecycle import close_with_timeout


class _WebSearchHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    content: str
    url: str
    score: float


class _WebSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: List[_WebSearchHit]


class _DifySearchHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(validation_alias=AliasChoices("content", "text"))
    score: float = Field(validation_alias=AliasChoices("score", "similarity"))
    title: str | None = None
    document_name: str | None = None
    metadata: Dict[str, Any] | None = None


class _DifySearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hits: List[_DifySearchHit] = Field(validation_alias=AliasChoices("data", "hits", "items"))


class IntentDetectionTool:
    """Lightweight wrapper around the intent router classifier."""

    def __init__(self, classifier: LLMIntentClassifier | None = None) -> None:
        self.classifier = LLMIntentClassifier() if classifier is None else classifier

    async def detect(self, query: str) -> Dict[str, Any]:
        prediction = await self.classifier.classify(query)
        return prediction.model_dump()


class KnowledgeTool:
    """Async facade sitting on top of KnowledgeService."""

    def __init__(self, service: KnowledgeService | None = None) -> None:
        self._service = service
        self._owns_service = service is None
        self._service_task: asyncio.Task[KnowledgeService] | None = None
        self._closed = False
        self._dify = DifyKnowledgeProxy()
        self._last_timings: ContextVar[dict[str, float]] = ContextVar("knowledge_tool_timings")

    async def aclose(self) -> None:
        self._closed = True
        if self._service_task is not None:
            await close_with_timeout(partial(asyncio.shield, self._service_task))
        if self._owns_service and self._service is not None:
            service, self._service = self._service, None
            await close_with_timeout(service.close)

    @property
    def last_timings(self) -> dict[str, float]:
        return self._last_timings.get({}).copy()

    async def _initialize_service(self) -> KnowledgeService:
        service = await run_sync(KnowledgeService)
        if self._closed:
            await close_with_timeout(service.close)
        else:
            self._service = service
        return service

    async def get_service(self) -> KnowledgeService:
        if self._closed:
            raise RuntimeError("Knowledge tool is closed")
        if self._service is not None:
            return self._service
        if self._service_task is None:
            self._service_task = asyncio.create_task(self._initialize_service())
            # The facade retains the task even if its requesting caller cancels.
            self._service_task.add_done_callback(
                lambda task: None if task.cancelled() else task.exception()
            )
        service = await asyncio.shield(self._service_task)
        if self._closed:
            raise RuntimeError("Knowledge tool is closed")
        return service

    async def ingest(self, documents: List[PolicyDocument]) -> int:
        service = await self.get_service()
        return await service.index_documents(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        self._last_timings.set({})
        if top_k < 0:
            raise ValueError("top_k must not be negative")
        if top_k == 0:
            return [], []
        # 优先使用 Dify 知识库（若启用）
        if self._dify.enabled:
            docs, scores = await self._dify.search(query, top_k=top_k)
            if docs:
                return docs, scores
        service = await self.get_service()
        result = await service.search(
            query, top_k=top_k, threshold=threshold, filters=filters
        )
        self._last_timings.set(service.last_timings.copy())
        return result


class WebSearchTool:
    """Simple Tavily-backed web search helper for fallback retrieval."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_results: int = 3,
        search_depth: str = "basic",
        enabled: bool | None = None,
        site_filter: str = "",
    ) -> None:
        self.api_key = os.getenv("TAVILY_API_KEY") if api_key is None else api_key
        self.max_results = max_results
        self.search_depth = search_depth
        self.site_filter = site_filter.strip()
        self._client: TavilyClient | None = None

        if enabled is False:
            logger.debug("Web search fallback disabled via configuration.")
            return
        if not self.api_key:
            if enabled:
                raise ValueError("TAVILY_API_KEY is required when web search is enabled")
            logger.debug("TAVILY_API_KEY not provided; web search fallback disabled.")
            return
        self._client = TavilyClient(api_key=self.api_key)
        logger.info("WebSearchTool initialized with Tavily client.")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        client = self._client
        if client is None:
            return []
        limit = self.max_results if max_results is None else max_results
        if limit < 0:
            raise ValueError("max_results must not be negative")
        if limit == 0:
            return []
        search_query = query
        if self.site_filter:
            suffix = self.site_filter
            if not suffix.lower().startswith("site:"):
                suffix = f"site:{suffix}"
            search_query = f"{query} {suffix}".strip()
        response = client.search(
            query=search_query,
            search_depth=self.search_depth,
            max_results=limit,
        )
        results = _WebSearchResponse.model_validate(response).results

        formatted = []
        for item in results[:limit]:
            formatted.append(
                {
                    "title": item.title.strip(),
                    "content": item.content.strip(),
                    "url": item.url,
                    "score": item.score,
                }
            )
        return formatted

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "暂无可用的网络检索结果。"
        lines = ["以下为网络检索的关键信息："]
        for idx, item in enumerate(results, 1):
            title = item["title"] or "未提供标题"
            content = item["content"]
            lines.append(
                f"\n[{idx}] 标题：{title}\n"
                f"内容：{content[:400]}\n来源：{item['url']}\n"
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
        prompt_template: str = "请描述图片中的关键信息。",
        max_images: int = 2,
        max_output_tokens: int = 800,
    ) -> None:
        self.prompt_template = prompt_template
        if max_images < 1:
            raise ValueError("max_images must be positive")
        self.max_images = max_images
        self.max_output_tokens = max_output_tokens
        self._client: AsyncOpenAI | None = None
        self._dashscope_api_key: Optional[str] = None
        self._mode: str = "disabled"
        self._model_name = model
        if not enabled:
            return
        resolved_key = api_key
        if resolved_key is None:
            resolved_key = os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError("An API key is required when vision is enabled")
        if base_url and "dashscope.aliyuncs.com" in base_url.lower():
            self._initialize_dashscope(resolved_key)
        else:
            self._initialize_openai(resolved_key, base_url)

    @property
    def enabled(self) -> bool:
        return self._mode != "disabled"

    async def describe(self, query: str, attachments: List[Attachment]) -> str:
        if not self.enabled or not attachments:
            return ""
        if self._mode == "dashscope":
            return await self._describe_dashscope(query, attachments)
        return await self._describe_openai(query, attachments)

    async def aclose(self) -> None:
        client, self._client = self._client, None
        self._mode = "disabled"
        self._dashscope_api_key = None
        if client is not None:
            await client.close()


    def _build_openai_contents(self, query: str, attachments: List[Attachment]) -> List[ChatCompletionContentPartParam]:
        prompt = self.prompt_template.format(query=query)
        payload: List[ChatCompletionContentPartParam] = [{"type": "text", "text": prompt}]
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
        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    def _resolve_dashscope_image_ref(self, attachment: Attachment) -> Optional[str]:
        if attachment.url and attachment.url.startswith(("http://", "https://", "oss://")):
            return attachment.url
        path = self._resolve_local_image_path(attachment)
        if not path:
            return None
        resolved = path.resolve()
        return str(resolved)

    def _resolve_local_image_path(self, attachment: Attachment) -> Optional[Path]:
        if not attachment.path:
            return None
        path = Path(attachment.path)
        if not path.is_file():
            raise FileNotFoundError(f"Vision image does not exist: {path}")
        return path

    def _initialize_openai(self, api_key: str, base_url: Optional[str]) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._mode = "openai"
        logger.info("VisionTool initialized with model {}", self._model_name)

    def _initialize_dashscope(self, api_key: str) -> None:
        self._dashscope_api_key = api_key
        self._mode = "dashscope"
        logger.info("VisionTool initialized with DashScope model {}", self._model_name)

    async def _describe_openai(self, query: str, attachments: List[Attachment]) -> str:
        client = self._client
        if client is None:
            raise RuntimeError("OpenAI vision client is not initialized")
        content = await asyncio.to_thread(self._build_openai_contents, query, attachments)
        if len(content) <= 1:
            return ""
        response = await client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": content}],
            max_tokens=self.max_output_tokens,
        )
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Vision provider returned no answer")
        return response.choices[0].message.content.strip()

    async def _describe_dashscope(self, query: str, attachments: List[Attachment]) -> str:
        if self._dashscope_api_key is None:
            raise RuntimeError("DashScope vision client is not initialized")
        messages = await asyncio.to_thread(self._build_dashscope_messages, query, attachments)
        if not messages:
            return ""
        response = await asyncio.to_thread(
            MultiModalConversation.call,
            model=self._model_name,
            messages=messages,
            api_key=self._dashscope_api_key,
            max_tokens=self.max_output_tokens,
        )
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(f"DashScope vision failed ({response.code}): {response.message}")
        text = self._extract_dashscope_text(response).strip()
        if not text:
            raise ValueError("DashScope vision provider returned no answer")
        return text

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
        # MultiModalConversationOutput exposes choices, with multimodal content
        # represented as a sequence of {"text": ...}/{"image": ...} parts.
        for choice in response.output.choices:
            texts = [part["text"] for part in choice["message"]["content"] if "text" in part]
            if texts:
                return "\n".join(texts)
        return ""


class DifyKnowledgeProxy:
    """Lightweight Dify KB retriever (dataset retrieve API)."""

    def __init__(self) -> None:
        self.enabled = os.getenv("DIFY_KB_ENABLED", "").lower() in {"1", "true", "yes", "on"}
        self.base_url = os.getenv("DIFY_KB_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("DIFY_KB_API_KEY")
        self.dataset_id = os.getenv("DIFY_KB_ID") or os.getenv("DIFY_DATASET_ID")
        self.top_k = int(os.getenv("DIFY_KB_TOP_K", "5"))
        if self.enabled and (not self.base_url or not self.api_key or not self.dataset_id):
            raise ValueError("Dify KB requires base_url, api_key and dataset_id when enabled")

    async def search(self, query: str, top_k: Optional[int] = None) -> Tuple[List[PolicyDocument], List[float]]:
        if not self.enabled:
            return [], []
        limit = self.top_k if top_k is None else top_k
        if limit < 0:
            raise ValueError("top_k must not be negative")
        if limit == 0:
            return [], []
        try:
            return await asyncio.to_thread(self._search_sync, query, limit)
        except requests.RequestException as exc:
            # Requests' JSON errors also inherit RequestException; malformed
            # responses must remain visible instead of triggering fallback.
            if isinstance(exc, requests.exceptions.InvalidJSONError):
                raise
            logger.opt(exception=True).warning("Dify KB 搜索失败，回退本地知识库：{}", exc)
            return [], []

    def _search_sync(self, query: str, top_k: int) -> Tuple[List[PolicyDocument], List[float]]:
        url = f"{self.base_url}/v1/datasets/{self.dataset_id}/retrieve"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "top_k": top_k}
        resp = requests.post(url, headers=headers, json=payload, timeout=(5, 15))
        try:
            resp.raise_for_status()
            data = resp.json()
        finally:
            resp.close()
        hits = _DifySearchResponse.model_validate(data).hits

        docs: List[PolicyDocument] = []
        scores: List[float] = []
        for item in hits:
            text = item.content
            if not text:
                continue
            meta = item.metadata
            if meta is None:
                meta = {}
            title = (
                item.title
                or item.document_name
                or meta.get("title")
                or "Dify 知识库条目"
            )
            regions = []
            if "region" in meta:
                regions = [meta["region"]] if isinstance(meta["region"], str) else list(meta["region"])
            doc = PolicyDocument(
                title=title,
                content=text,
                summary=None,
                source=meta.get("source") or "Dify",
                doc_type=PolicyType.GUIDELINE,
                publish_date=None,
                effective_date=None,
                expiry_date=None,
                relevant_departments=[],
                target_groups=[],
                regions=regions,
                keywords=meta.get("keywords") or [],
                embedding=None,
                metadata={"origin": "dify", **meta},
                retrieval_origin="dify",
            )
            docs.append(doc)
            scores.append(item.score)
        return docs, scores


class UserProfileTool:
    """Simple helper for querying user profile/history records."""

    def __init__(self, db_path: str = "resources/data/user_profiles.json", preset_db: Optional[Dict[str, Any]] = None) -> None:
        self.db_path = db_path
        self._db = deepcopy(preset_db) if preset_db is not None else {}
        if preset_db is None:
            self._load_from_file()

    def _load_from_file(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            logger.warning("UserProfileTool 未找到数据库文件：{}", path)
            return
        with path.open("r", encoding="utf-8") as profile_file:
            records = json.load(profile_file)
        if not isinstance(records, dict) or not all(isinstance(profile, dict) for profile in records.values()):
            raise ValueError("User profile data must map user identifiers to profile objects")
        self._db = records
        logger.info("UserProfileTool 已加载 {} 条用户历史记录", len(self._db))

    async def fetch(self, user_id: str) -> Dict[str, Any]:
        profile = self._db.get(user_id)
        if profile is not None:
            return {**deepcopy(profile), "user_id": user_id, "found": True}
        return {
            "user_id": user_id,
            "found": False,
            "message": "系统中未找到该用户的历史记录。",
        }

    def format_profile(self, profile: Dict[str, Any]) -> str:
        if not profile["found"]:
            return profile["message"]
        history = profile.get("history") or []
        history_text = "\n  - ".join(history) if history else "无历史记录"
        return (
            f"用户：{profile.get('name','未知')}（ID: {profile['user_id']}）\n"
            f"所属地区：{profile.get('region','未知')}  等级：{profile.get('level','未知')}\n"
            f"最近登录：{profile.get('last_login','未知')}\n"
            f"历史事件：\n  - {history_text}"
        )


__all__ = ["IntentDetectionTool", "KnowledgeTool", "WebSearchTool", "VisionTool", "UserProfileTool"]
