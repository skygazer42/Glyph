"""
Policy retrieval agent for finding relevant policy documents.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
import numpy as np
import os

from app.agents.framework.base.base_agent import BaseAgent
from app.agents.framework.base.types import (
    MessageTypes,
    PolicyDocument,
    QueryResult,
    RetrievalMethod
)


class PolicyRetriever(BaseAgent):
    """Agent responsible for retrieving relevant policy documents."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        vector_store: Optional[Any] = None,
        graph_db: Optional[Any] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ):
        """Initialize the policy retriever."""
        super().__init__(name, "policy_retriever", llm_config)
        self.vector_store = vector_store
        self.graph_db = graph_db
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        # Embedding backend config（默认 openai，避免强制安装 torch）
        self.embedding_backend = (os.getenv("EMBEDDING_BACKEND") or "openai").lower()
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    def _get_default_system_message(self) -> str:
        """Get the default system message."""
        return """您是政策检索专员，负责根据用户查询找到相关的政策文档。

您的任务：
1. 分析用户查询，理解他们需要的政策类型
2. 使用向量相似度搜索查找相关文档
3. 使用图遍历查找关联政策（如需要）
4. 根据相关性对结果进行排序和筛选
5. 返回最相关的前K个政策文档

您必须考虑：
- 政策类型（补贴、税收优惠、法规等）
- 时间限制（生效日期、截止日期）
- 地理限制（国家、省级、市级）
- 目标群体（个人、企业、特定行业）
- 政策关系（互补、冲突、层级）

始终为检索结果提供来源和置信度评分。"""

    async def process_message(
        self,
        message: str,
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process retrieval request."""
        try:
            # Parse the message
            data = json.loads(message) if isinstance(message, str) else message
            query = data.get("query", "")
            filters = data.get("filters", {})
            method = RetrievalMethod(data.get("method", "hybrid"))

            # Perform retrieval
            if method == RetrievalMethod.VECTOR_SEARCH:
                results = await self._vector_search(query, filters)
            elif method == RetrievalMethod.GRAPH_SEARCH:
                results = await self._graph_search(query, filters)
            else:  # HYBRID
                results = await self._hybrid_search(query, filters)

            return self.format_success_response(
                results,
                MessageTypes.RETRIEVAL_RESULT
            )

        except Exception as e:
            return self.format_error_response(str(e))

    async def _vector_search(
        self,
        query: str,
        filters: Dict[str, Any]
    ) -> QueryResult:
        """Perform vector similarity search."""
        # Encode the query（按后端选择嵌入方式）
        query_embedding = await self._embed_query(query)

        # Search in vector store
        if self.vector_store:
            docs, scores = await self.vector_store.search(
                query_embedding,
                top_k=self.top_k,
                filters=filters
            )
        else:
            # Fallback to mock search
            docs, scores = self._mock_vector_search(query)

        # Filter by similarity threshold
        filtered_docs = []
        filtered_scores = []
        for doc, score in zip(docs, scores):
            if score >= self.similarity_threshold:
                filtered_docs.append(doc)
                filtered_scores.append(score)

        return QueryResult(
            query=query,
            documents=filtered_docs,
            scores=filtered_scores,
            method=RetrievalMethod.VECTOR_SEARCH,
            metadata={"search_type": "vector", "threshold": self.similarity_threshold}
        )

    async def _graph_search(
        self,
        query: str,
        filters: Dict[str, Any]
    ) -> QueryResult:
        """Perform graph-based search."""
        if not self.graph_db:
            # Fallback to vector search
            return await self._vector_search(query, filters)

        # Extract entities from query
        entities = await self._extract_entities(query)

        # Search in graph database
        docs = []
        scores = []

        for entity in entities:
            related_docs = await self.graph_db.find_related_policies(
                entity,
                max_depth=2,
                filters=filters
            )
            docs.extend(related_docs)
            scores.extend([0.8] * len(related_docs))  # Default score for graph search

        # Remove duplicates and rank
        unique_docs = self._remove_duplicates(docs)
        final_scores = scores[:len(unique_docs)]

        return QueryResult(
            query=query,
            documents=unique_docs,
            scores=final_scores,
            method=RetrievalMethod.GRAPH_SEARCH,
            metadata={"search_type": "graph", "entities": entities}
        )

    async def _hybrid_search(
        self,
        query: str,
        filters: Dict[str, Any]
    ) -> QueryResult:
        """Perform hybrid search combining vector and graph methods."""
        # Get results from both methods
        vector_results = await self._vector_search(query, filters)
        graph_results = await self._graph_search(query, filters)

        # Combine and re-rank results
        all_docs = vector_results.documents + graph_results.documents
        all_scores = vector_results.scores + graph_results.scores

        # Re-rank based on combined scores
        ranked_docs = sorted(
            zip(all_docs, all_scores),
            key=lambda x: x[1],
            reverse=True
        )[:self.top_k]

        documents = [doc for doc, _ in ranked_docs]
        scores = [score for _, score in ranked_docs]

        return QueryResult(
            query=query,
            documents=documents,
            scores=scores,
            method=RetrievalMethod.HYBRID,
            metadata={
                "search_type": "hybrid",
                "vector_count": len(vector_results.documents),
                "graph_count": len(graph_results.documents)
            }
        )

    async def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query using LLM."""
        messages = [
            {
                "role": "system",
                "content": "Extract key policy-related entities from the query. Return as a JSON list of strings."
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nEntities:"
            }
        ]

        response = await self.a_create(messages)
        try:
            entities = json.loads(response.content)
            return entities if isinstance(entities, list) else []
        except:
            # Fallback: extract keywords
            return [word for word in query.split() if len(word) > 3]

    def _remove_duplicates(self, docs: List[PolicyDocument]) -> List[PolicyDocument]:
        """Remove duplicate documents."""
        seen_ids = set()
        unique_docs = []
        for doc in docs:
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                unique_docs.append(doc)
        return unique_docs

    def _mock_vector_search(self, query: str) -> tuple:
        """Mock vector search for testing."""
        # Create mock documents
        mock_docs = [
            PolicyDocument(
                id="doc1",
                title="2025年家电以旧换新政策",
                content="2025年家电以旧换新实施细则...",
                source="山东省商务厅",
                doc_type="policy"
            ),
            PolicyDocument(
                id="doc2",
                title="济南市消费券发放方案",
                content="济南市消费券发放活动方案...",
                source="济南市政府",
                doc_type="policy"
            )
        ]
        mock_scores = [0.85, 0.72]
        return mock_docs, mock_scores

    async def _embed_query(self, query: str) -> np.ndarray:
        backend = self.embedding_backend
        if backend == "openai":
            try:
                from openai import OpenAI
            except Exception as e:
                raise RuntimeError("openai 包未安装，无法使用 openai 嵌入后端") from e
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            model = self.embedding_model_name or "text-embedding-3-small"
            if not api_key:
                raise RuntimeError("未配置 LLM_API_KEY/OPENAI_API_KEY，无法使用 openai 嵌入后端")
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            res = client.embeddings.create(model=model, input=[query])
            vecs = np.array([res.data[0].embedding], dtype=np.float32)
            from faiss import normalize_L2
            normalize_L2(vecs)
            return vecs
        if backend == "ollama":
            try:
                from lightrag.llm.ollama import ollama_embed
            except Exception as e:
                raise RuntimeError("需要安装 lightrag 以使用 ollama 嵌入后端") from e
            host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")
            model = self.embedding_model_name or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
            vecs = ollama_embed([query], embed_model=model, host=host)
            vecs = np.array(vecs, dtype=np.float32)
            from faiss import normalize_L2
            normalize_L2(vecs)
            return vecs
        # fallback zeros
        return np.zeros((1, int(os.getenv("EMBEDDING_DIM", "768"))), dtype=np.float32)
