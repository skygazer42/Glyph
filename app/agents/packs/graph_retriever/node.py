"""
Graph-based retrieval agent powered by LightRAG.

Uses LightRAG's native storages and query modes (naive/local/global/hybrid).
Environment is configured via .env; no extra state is persisted here beyond LightRAG working_dir.
"""

import asyncio
import os
import inspect
import anyio
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc
from openai import OpenAI
import requests

from autogen_core import MessageContext

from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    RetrievalResult,
    PolicyDocument,
    RetrievalMethod,
    PolicyType,
)
from app.agents.framework.base.base_agent import StatefulAgent
from app.config.app_config import settings
from app.knowledge.rerank import Reranker


from pydantic import BaseModel, ConfigDict, Field


class DashscopeEmbedding(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    embedding: list[float] = Field(min_length=1)


class DashscopeEmbeddingOutput(BaseModel):
    embeddings: list[DashscopeEmbedding] = Field(min_length=1)


class DashscopeEmbeddingResponse(BaseModel):
    output: DashscopeEmbeddingOutput


class GraphRetrieverAgent(StatefulAgent):
    """LightRAG-backed graph retriever agent."""

    def __init__(
        self,
        working_dir: Optional[str] = None,
        default_mode: str = "hybrid",
        **kwargs,
    ):
        super().__init__(
            agent_type=AgentType.POLICY_RETRIEVER,
            name="GraphRetriever",
            description="基于LightRAG的图检索Agent",
            **kwargs,
        )

        self.working_dir = os.getenv("LIGHTRAG_WORKDIR", "resources/data/lightrag") if working_dir is None else working_dir
        self.default_mode = os.getenv("LIGHTRAG_QUERY_MODE", default_mode)
        self.embedding_backend = settings.embedding.backend.lower()
        if self.embedding_backend not in {"dashscope", "openai"}:
            raise ValueError(
                "LightRAG 需使用 dashscope 或 openai 嵌入，请将 EMBEDDING_BACKEND 设置为这两者之一。"
            )
        self.embedding_model = self._resolve_embedding_model()
        self.embedding_dim = self._infer_embedding_dim()
        self._reranker: Optional[Reranker] = None

        # Lazy init members
        self._rag: Any = None
        self._initialized = False

    async def initialize(self):
        """Initialize LightRAG with env-configured model + embedding functions."""
        if self._initialized:
            return

        try:
            await asyncio.to_thread(os.makedirs, self.working_dir, exist_ok=True)

            await asyncio.to_thread(load_dotenv, dotenv_path=os.getenv("DOTENV_PATH", ".env"), override=False)

            # Build LLM + Embedding funcs
            async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs) -> str:
                history_messages = history_messages or []
                return await openai_complete_if_cache(
                    os.getenv("LLM_MODEL_NAME", os.getenv("LLM_MODEL", "deepseek-chat")),
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""),
                    base_url=(os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"),
                    **kwargs,
                )

            embedding_func = EmbeddingFunc(
                embedding_dim=self.embedding_dim,
                max_token_size=int(os.getenv("MAX_EMBED_TOKENS", "8192")),
                func=self._embedding_callable(),
            )

            self._rag = LightRAG(
                working_dir=self.working_dir,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                rerank_model_func=self._create_rerank_callback(),
            )

            await self._rag.initialize_storages()

            await initialize_pipeline_status()

            self._initialized = True
            self.logger.info("LightRAG initialized for GraphRetriever")

        except BaseException:
            try:
                await self.close()
            except Exception:
                self.logger.error("Failed to release partially initialized LightRAG", exc_info=True)
            raise

    async def close(self):
        """Release storages initialized by this retriever."""
        rag, self._rag = self._rag, None
        try:
            if rag is not None:
                with anyio.fail_after(5, shield=True):
                    await rag.finalize_storages()
        finally:
            self._initialized = False
            if self._reranker is not None:
                reranker, self._reranker = self._reranker, None
                with anyio.fail_after(5, shield=True):
                    await anyio.to_thread.run_sync(reranker.close, abandon_on_cancel=True)

    def _resolve_embedding_model(self) -> str:
        if self.embedding_backend == "openai":
            return settings.embedding.openai_model
        return settings.embedding.dashscope_model

    def _infer_embedding_dim(self) -> int:
        if self.embedding_backend == "openai":
            if "3-large" in self.embedding_model:
                return 3072
            if "3-small" in self.embedding_model or "ada-002" in self.embedding_model:
                return 1536
            dimension = settings.embedding.dimension
            if dimension <= 0:
                raise ValueError("OpenAI embedding dimension must be positive")
            return dimension
        # dashscope
        if settings.embedding.dashscope_dimension is not None:
            return settings.embedding.dashscope_dimension
        if settings.embedding.dimension in [64, 128, 256, 512, 768, 1024]:
            return settings.embedding.dimension
        return 1024

    def _embedding_callable(self) -> Callable[[List[str]], Awaitable[List[List[float]]]]:
        if self.embedding_backend == "openai":
            return self._embed_openai
        return self._embed_dashscope

    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._embed_openai_sync, texts)

    def _embed_openai_sync(self, texts: List[str]) -> List[List[float]]:
        api_key = settings.embedding.openai_api_key or os.getenv("LLM_API_KEY")
        base_url = settings.embedding.openai_base_url or os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise ValueError("Missing API key for OpenAI embeddings (set EMBEDDING_OPENAI_API_KEY or LLM_API_KEY)")
        with OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key) as client:
            attempts = int(os.getenv("LIGHTRAG_EMBED_RETRY", "1"))
            last_error: Optional[BaseException] = None
            for _ in range(max(1, attempts)):
                try:
                    response = client.embeddings.create(model=self.embedding_model, input=texts)
                    return [item.embedding for item in response.data]
                except Exception as exc:  # pragma: no cover - network call
                    last_error = exc
                    self.logger.warning("OpenAI embedding 调用失败（重试中）: %s", exc, exc_info=True)
            self.logger.error("OpenAI embedding 调用失败，已重试 %s 次", attempts)
            assert last_error is not None
            raise last_error

    async def _embed_dashscope(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._embed_dashscope_sync, texts)

    def _embed_dashscope_sync(self, texts: List[str]) -> List[List[float]]:
        api_key = settings.embedding.dashscope_api_key
        if not api_key:
            raise ValueError("Missing DashScope API key (set EMBEDDING_DASHSCOPE_API_KEY)")
        url = settings.embedding.dashscope_base_url
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        vectors: List[List[float]] = []
        attempts = int(os.getenv("LIGHTRAG_EMBED_RETRY", "1"))
        for text in texts:
            payload: Dict[str, Any] = {
                "model": self.embedding_model,
                "input": {"texts": [text]},
            }
            parameters: Dict[str, Any] = {}
            if settings.embedding.dashscope_dimension is not None:
                parameters["dimension"] = settings.embedding.dashscope_dimension
            if settings.embedding.dashscope_output_type:
                parameters["output_type"] = settings.embedding.dashscope_output_type
            if parameters:
                payload["parameters"] = parameters
            last_error: Optional[requests.RequestException] = None
            for _ in range(max(1, attempts)):
                try:
                    with requests.post(url, headers=headers, json=payload, timeout=settings.embedding.timeout) as resp:
                        resp.raise_for_status()
                        data = DashscopeEmbeddingResponse.model_validate(resp.json())
                    vectors.append(data.output.embeddings[0].embedding)
                    break
                except requests.RequestException as exc:
                    last_error = exc
                    self.logger.warning("DashScope embedding 调用失败（重试中）: %s", exc, exc_info=True)
            else:
                self.logger.error("DashScope embedding 调用失败，已重试 %s 次", attempts)
                assert last_error is not None
                raise last_error
        return vectors

    async def add_texts(self, texts: List[str]):
        """Insert raw texts into LightRAG store."""
        if not self._initialized:
            await self.initialize()
        for t in texts:
            await self._rag.ainsert(t)

    async def add_documents(self, documents: List[PolicyDocument]) -> int:
        """Insert PolicyDocuments into LightRAG store. Returns count of indexed documents."""
        if not self._initialized:
            await self.initialize()
        indexed = 0
        for doc in documents:
            text = f"{doc.title}\n{doc.content}"
            await self._rag.ainsert(text)
            indexed += 1
        return indexed

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> RetrievalResult:
        """Process retrieval using LightRAG and return documents as snippets.

        Requires a query_text; mode and top_k use this retriever's configured defaults.
        """
        if not self._initialized:
            await self.initialize()

        query_text = request["query_text"]
        mode = request.get("mode", self.default_mode)
        top_k = int(request.get("top_k", 5))
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("GraphRetrieverAgent requires 'query_text' to perform retrieval")

        # Execute query on LightRAG
        resp = await self._rag.aquery(
            query_text,
            param=QueryParam(mode=mode, stream=False, top_k=top_k),
        )

        # Stream or string handling
        if inspect.isasyncgen(resp):
            chunks = []
            try:
                async for chunk in resp:
                    if chunk:
                        chunks.append(str(chunk))
            finally:
                with anyio.fail_after(5, shield=True):
                    await resp.aclose()
            text = "".join(chunks)
        elif resp is None:
            text = ""
        else:
            text = str(resp)

        # Convert to single PolicyDocument snippet
        doc = PolicyDocument(
            title=f"LightRAG-{mode} 结果",
            content=text,
            source="LightRAG",
            doc_type=PolicyType.GUIDELINE,
        )

        return RetrievalResult(
            query_id=request.get("query_id", doc.id),
            documents=[doc] if text.strip() else [],
            scores=[1.0] if text.strip() else [],
            method=RetrievalMethod.GRAPH_TRAVERSAL,
            total_searched=1,
            search_time=0.0,
        )

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages by delegating to process_request."""
        result = await self.process_request(message.content, ctx)
        return AgentMessage(
            type=MessageType.RETRIEVAL_RESULT,
            sender=self.agent_type,
            recipient=message.sender,
            content=result.model_dump(),
            correlation_id=message.correlation_id,
        )

    async def _handle_query_analysis(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle query analysis messages - not used by GraphRetriever."""
        # GraphRetriever doesn't need query analysis, just pass through
        return None

    async def on_message_impl(self, message: Any, ctx: MessageContext) -> Any:
        """
        Main message handler required by autogen_core BaseAgent.
        Delegates to process_request for actual retrieval.
        """
        return await self.process_request(message, ctx)

    def _create_rerank_callback(self) -> Callable[..., Awaitable[List[Dict[str, Any]]]]:
        reranker = Reranker()
        self._reranker = reranker

        async def _async_rerank(
            query: str,
            documents: List[str],
            top_n: Optional[int] = None,
        ) -> List[Dict[str, Any]]:
            if not documents:
                return []
            loop = asyncio.get_running_loop()

            def _run():
                return reranker.rerank(query, documents, top_n)

            ranked = await loop.run_in_executor(None, _run)

            payload: List[Dict[str, Any]] = []
            for idx, score, _ in ranked:
                payload.append({"index": idx, "relevance_score": float(score)})
            return payload

        return _async_rerank
