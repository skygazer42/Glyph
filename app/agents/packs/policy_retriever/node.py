"""
Policy retrieval agent for finding relevant policy documents.
"""

import asyncio
import logging
import anyio

from typing import Dict, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, field_validator

from app.agents.framework.common.model_client import create_openai_client
from autogen_core.models import SystemMessage, UserMessage
from app.agents.framework.base.types import (
    MessageTypes,
    QueryResult,
    RetrievalMethod
)
from app.models.base import PolicyDocument


class RetrievalRequest(BaseModel):
    """Policy-search input shared by JSON messages and direct mapping callers."""

    model_config = ConfigDict(strict=True, extra="ignore")

    query: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    method: RetrievalMethod = Field(default=RetrievalMethod.HYBRID, strict=False)

    @field_validator("query")
    @classmethod
    def require_nonempty_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Policy retrieval requires a nonempty query")
        return value


class PolicyEntities(RootModel[list[str]]):
    """Text entities accepted by the graph-search boundary."""

    model_config = ConfigDict(strict=True)


class PolicyRetriever:
    """Agent responsible for retrieving relevant policy documents."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        vector_store: Optional[Any] = None,
        graph_db: Optional[Any] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        *, model_client=None,
    ):
        """Initialize the policy retriever."""
        self.name = name
        self.llm_config = llm_config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.system_message = self._get_default_system_message()
        self._owns_model_client = model_client is None
        self.model_client = create_openai_client(llm_config=llm_config) if model_client is None else model_client
        self.vector_store = vector_store
        self.graph_db = graph_db
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
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
        message: str | Dict[str, Any],
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process retrieval request."""
        try:
            # Parse the message
            if isinstance(message, str):
                request = RetrievalRequest.model_validate_json(message)
            else:
                request = RetrievalRequest.model_validate(message)

            # Perform retrieval
            if request.method == RetrievalMethod.VECTOR_SEARCH:
                results = await self._vector_search(request.query, request.filters)
            elif request.method == RetrievalMethod.GRAPH_SEARCH:
                results = await self._graph_search(request.query, request.filters)
            else:  # HYBRID
                results = await self._hybrid_search(request.query, request.filters)

            return {"success": True, "data": results, "type": MessageTypes.RETRIEVAL_RESULT.value}

        except Exception as e:
            self.logger.exception("Policy request failed")
            return {"success": False, "error": str(e)}

    async def _vector_search(
        self,
        query: str,
        filters: Dict[str, Any]
    ) -> QueryResult:
        """Perform vector similarity search."""
        if self.vector_store is None:
            raise ValueError("PolicyRetriever requires a configured vector_store")
        # MilvusStore.search owns embedding and exposes a synchronous text API.
        docs, scores = await asyncio.to_thread(
            self.vector_store.search, query, top_k=self.top_k,
            threshold=self.similarity_threshold, filters=filters,
        )
        if len(docs) != len(scores):
            raise ValueError("Vector store returned mismatched documents and scores")

        # Filter by similarity threshold
        filtered_docs = []
        filtered_scores = []
        for index, doc in enumerate(docs):
            score = scores[index]
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
        if self.graph_db is None:
            raise RuntimeError("PolicyRetriever requires a configured graph_db for graph search")

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
        if self.graph_db is None:
            return vector_results
        graph_results = await self._graph_search(query, filters)

        # Combine and re-rank results
        all_docs = vector_results.documents + graph_results.documents
        all_scores = vector_results.scores + graph_results.scores

        # Re-rank based on combined scores
        if len(all_docs) != len(all_scores):
            raise ValueError("Retrieval results have mismatched documents and scores")
        ranked_docs = sorted(
            [(doc, all_scores[index]) for index, doc in enumerate(all_docs)],
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

        response = await self._request_completion(messages)
        try:
            return PolicyEntities.model_validate_json(response).root
        except ValidationError:
            self.logger.warning("Invalid policy entities; using query keywords", exc_info=True)
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

    async def _request_completion(self, messages: List[Dict[str, str]]) -> str:
        """Send complete role-tagged messages through the current async SDK."""
        sdk_messages = [SystemMessage(content=message["content"])
                        if message["role"] == "system"
                        else UserMessage(content=message["content"], source="user")
                        for message in messages]
        response = await self.model_client.create(sdk_messages)
        if not isinstance(response.content, str):
            raise ValueError("Policy model must return text")
        return response.content

    async def close(self):
        """Release only the model client created by this business object."""
        if self._owns_model_client:
            self._owns_model_client = False
            with anyio.fail_after(5, shield=True):
                await self.model_client.close()
