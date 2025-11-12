"""
Graph-based retrieval agent powered by LightRAG.

Uses LightRAG's native storages and query modes (naive/local/global/hybrid).
Environment is configured via .env; no extra state is persisted here beyond LightRAG working_dir.
"""

import asyncio
import os
import inspect
from typing import Any, Dict, List, Optional, Callable, Awaitable

from autogen_core import MessageContext

from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    RetrievalRequest,
    RetrievalResult,
    PolicyDocument,
    RetrievalMethod,
    PolicyType,
)
from app.agents.framework.base.base_agent import StatefulAgent
from app.config import settings


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
        )

        self.working_dir = working_dir or os.getenv("LIGHTRAG_WORKDIR", "resources/data/lightrag")
        self.default_mode = os.getenv("LIGHTRAG_QUERY_MODE", default_mode)
        self.embedding_backend = (settings.embedding.backend or "dashscope").lower()
        if self.embedding_backend not in {"dashscope", "openai"}:
            raise ValueError(
                "LightRAG 需使用 dashscope 或 openai 嵌入，请将 EMBEDDING_BACKEND 设置为这两者之一。"
            )
        self.embedding_model = self._resolve_embedding_model()
        self.embedding_dim = self._infer_embedding_dim()

        # Lazy init members
        self._rag = None
        self._initialized = False

    async def initialize(self):
        """Initialize LightRAG with env-configured model + embedding functions."""
        if self._initialized:
            return

        try:
            os.makedirs(self.working_dir, exist_ok=True)

            from dotenv import load_dotenv
            load_dotenv(dotenv_path=os.getenv("DOTENV_PATH", ".env"), override=False)

            # Build LLM + Embedding funcs
            async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs) -> str:
                history_messages = history_messages or []
                from lightrag.llm.openai import openai_complete_if_cache
                return await openai_complete_if_cache(
                    os.getenv("LLM_MODEL_NAME", os.getenv("LLM_MODEL", "deepseek-chat")),
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""),
                    base_url=(os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"),
                    **kwargs,
                )

            from lightrag.utils import EmbeddingFunc

            embedding_func = EmbeddingFunc(
                embedding_dim=self.embedding_dim,
                max_token_size=int(os.getenv("MAX_EMBED_TOKENS", "8192")),
                func=self._embedding_callable(),
            )

            from lightrag import LightRAG
            self._rag = LightRAG(
                working_dir=self.working_dir,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
            )

            await self._rag.initialize_storages()

            try:
                from lightrag.kg.shared_storage import initialize_pipeline_status
                await initialize_pipeline_status()
            except Exception:
                # optional; continue if unavailable
                pass

            self._initialized = True
            self.logger.info("LightRAG initialized for GraphRetriever")

        except Exception as e:
            self.logger.error(f"Failed to initialize LightRAG: {e}")
            raise

    def _resolve_embedding_model(self) -> str:
        if self.embedding_backend == "openai":
            return settings.embedding.openai_model
        return settings.embedding.dashscope_model

    def _infer_embedding_dim(self) -> int:
        if self.embedding_backend == "openai":
            model = self.embedding_model or ""
            if "3-large" in model:
                return 3072
            if "3-small" in model or "ada-002" in model:
                return 1536
            return settings.embedding.dimension or 1536
        # dashscope
        if settings.embedding.dashscope_dimension:
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
        from openai import OpenAI

        api_key = settings.embedding.openai_api_key or os.getenv("LLM_API_KEY")
        base_url = settings.embedding.openai_base_url or os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise ValueError("Missing API key for OpenAI embeddings (set EMBEDDING_OPENAI_API_KEY or LLM_API_KEY)")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        attempts = int(os.getenv("LIGHTRAG_EMBED_RETRY", "1"))
        last_error: Optional[BaseException] = None
        for _ in range(max(1, attempts)):
            try:
                response = client.embeddings.create(model=self.embedding_model, input=texts)
                return [item.embedding for item in response.data]
            except Exception as exc:  # pragma: no cover - network call
                last_error = exc
                self.logger.warning("OpenAI embedding 调用失败（重试中）: %s", exc)
        self.logger.error("OpenAI embedding 调用失败，已重试 %s 次", attempts)
        raise last_error  # type: ignore[misc]

    async def _embed_dashscope(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._embed_dashscope_sync, texts)

    def _embed_dashscope_sync(self, texts: List[str]) -> List[List[float]]:
        import requests

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
            if settings.embedding.dashscope_dimension:
                parameters["dimension"] = settings.embedding.dashscope_dimension
            if settings.embedding.dashscope_output_type:
                parameters["output_type"] = settings.embedding.dashscope_output_type
            if parameters:
                payload["parameters"] = parameters
            last_error: Optional[requests.RequestException] = None
            for _ in range(max(1, attempts)):
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=settings.embedding.timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    vectors.append(data["output"]["embeddings"][0]["embedding"])
                    break
                except requests.RequestException as exc:
                    last_error = exc
                    self.logger.warning("DashScope embedding 调用失败（重试中）: %s", exc)
            else:
                self.logger.error("DashScope embedding 调用失败，已重试 %s 次", attempts)
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
            try:
                text = f"{doc.title}\n{doc.content}"
                await self._rag.ainsert(text)
                indexed += 1
            except Exception as e:
                self.logger.warning(f"Failed to index document {doc.title}: {e}")
        return indexed

    async def process_request(self, request: Any, context: MessageContext) -> RetrievalResult:
        """Process retrieval using LightRAG and return documents as snippets.

        Accepts either:
        - dict with {"query_text": str, "mode": "naive|local|global|hybrid", "top_k": int}
        - RetrievalRequest + dict-like context containing query_text (fallback)
        """
        if not self._initialized:
            await self.initialize()

        query_text = None
        mode = self.default_mode
        top_k = 5

        if isinstance(request, dict):
            query_text = request.get("query_text") or request.get("text")
            mode = request.get("mode", mode)
            top_k = int(request.get("top_k", top_k))
        elif hasattr(request, "query_id"):
            # Fallback: try to read from context
            if hasattr(context, "__dict__"):
                query_text = getattr(context, "query_text", None)
        
        if not query_text:
            raise ValueError("GraphRetrieverAgent requires 'query_text' to perform retrieval")

        # Execute query on LightRAG
        from lightrag import QueryParam
        resp = await self._rag.aquery(
            query_text,
            param=QueryParam(mode=mode, stream=False),
        )

        # Stream or string handling
        if inspect.isasyncgen(resp):
            chunks = []
            async for chunk in resp:
                if chunk:
                    chunks.append(str(chunk))
            text = "".join(chunks)
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
            query_id=getattr(request, "query_id", doc.id),
            documents=[doc],
            scores=[1.0],
            method=RetrievalMethod.GRAPH_TRAVERSAL,
            total_searched=1,
            search_time=0.0,
        )

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages by delegating to process_request."""
        try:
            request = message.content
            result = await self.process_request(request, ctx)
            return AgentMessage(
                type=MessageType.RETRIEVAL_RESULT,
                sender=self.agent_type,
                content=result.model_dump() if hasattr(result, 'model_dump') else result,
                metadata={"query_id": str(getattr(request, "query_id", "unknown"))}
            )
        except Exception as e:
            self.logger.error(f"Error handling user query: {e}")
            return None

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
