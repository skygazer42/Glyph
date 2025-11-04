"""
Graph-based retrieval agent powered by LightRAG.

Uses LightRAG's native storages and query modes (naive/local/global/hybrid).
Environment is configured via .env; no extra state is persisted here beyond LightRAG working_dir.
"""

import os
import inspect
from typing import Any, Dict, List, Optional

from autogen_core import MessageContext

from ...models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    RetrievalRequest,
    RetrievalResult,
    PolicyDocument,
    RetrievalMethod,
    PolicyType,
)
from ..base.base_agent import StatefulAgent


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

        self.working_dir = working_dir or os.getenv("LIGHTRAG_WORKDIR", "data/lightrag")
        self.default_mode = os.getenv("LIGHTRAG_QUERY_MODE", default_mode)

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
            from lightrag.llm.ollama import ollama_embed

            embedding_func = EmbeddingFunc(
                embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
                max_token_size=int(os.getenv("MAX_EMBED_TOKENS", "8192")),
                func=lambda texts: ollama_embed(
                    texts,
                    embed_model=os.getenv("EMBEDDING_MODEL", "bge-m3:latest"),
                    host=os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434"),
                ),
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

    async def add_texts(self, texts: List[str]):
        """Insert raw texts into LightRAG store."""
        if not self._initialized:
            await self.initialize()
        for t in texts:
            await self._rag.ainsert(t)

    async def add_documents(self, documents: List[PolicyDocument]):
        """Insert PolicyDocuments into LightRAG store."""
        if not self._initialized:
            await self.initialize()
        for doc in documents:
            text = f"{doc.title}\n{doc.content}"
            await self._rag.ainsert(text)

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
