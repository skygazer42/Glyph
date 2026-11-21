"""
Milvus vector store for document embeddings and similarity search.

Supports backends:
- openai (default): OpenAI Embeddings API
- dashscope: Alibaba Cloud text embeddings
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import requests
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

from app.config.app_config import settings
from app.models.policy import PolicyDocument, PolicyType


class DashScopeEmbedding(BaseModel):
    """One finite numeric vector returned for one input text."""

    model_config = ConfigDict(strict=True, extra="ignore", allow_inf_nan=False)

    embedding: list[float] = Field(min_length=1)


class DashScopeEmbeddingOutput(BaseModel):
    """Each HTTP request below submits exactly one input text."""

    model_config = ConfigDict(strict=True, extra="ignore")

    embeddings: list[DashScopeEmbedding] = Field(min_length=1, max_length=1)


class DashScopeEmbeddingResponse(BaseModel):
    """Dense embedding output; request IDs and usage remain SDK metadata."""

    model_config = ConfigDict(strict=True, extra="ignore")

    output: DashScopeEmbeddingOutput


class MilvusStore:
    """Milvus vector database for storing and retrieving policy documents."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        backend: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        db_name: Optional[str] = None
    ):
        """Initialize the Milvus store."""

        # Embedding config - 优先使用 settings.embedding
        self.backend = settings.embedding.backend if backend is None else backend
        self.model_name = self._get_model_name_from_backend(settings) if model_name is None else model_name
        if not self.model_name.strip():
            raise ValueError("Embedding model name must not be empty")
        self.embedding_dim = self._infer_dim()

        # Milvus config - 使用 settings.database.milvus_*
        self.host = settings.database.milvus_host if host is None else host
        self.port = settings.database.milvus_port if port is None else port
        self.user = settings.database.milvus_user if user is None else user
        self.password = settings.database.milvus_password if password is None else password
        self.db_name = settings.database.milvus_db_name if db_name is None else db_name
        self.collection_name = settings.database.milvus_collection_name if collection_name is None else collection_name

        # Connect and initialize
        self.collection: Optional[Collection] = None
        self._connection_alias = f"glyph-{uuid4().hex}"
        self._connected = False
        self._connect()

    def _connect(self):
        """Connect to Milvus and initialize collection."""
        try:
            connections.connect(
                alias=self._connection_alias,
                host=self.host,
                port=str(self.port),
                user=self.user,
                password=self.password,
                db_name=self.db_name
            )

            self._connected = True
            if utility.has_collection(self.collection_name, using=self._connection_alias):
                self.collection = Collection(self.collection_name, using=self._connection_alias)

                # 验证维度是否匹配
                existing_dim = None
                for field in self.collection.schema.fields:
                    if field.name == "embedding":
                        existing_dim = field.params.get("dim")
                        break

                if existing_dim != self.embedding_dim:
                    raise ValueError(
                        f"Collection '{self.collection_name}' already exists with dimension {existing_dim}, "
                        f"but current embedding model requires dimension {self.embedding_dim}. "
                        f"Please either:\n"
                        f"1. Drop the existing collection: utility.drop_collection('{self.collection_name}')\n"
                        f"2. Use a different collection name\n"
                        f"3. Switch to an embedding model with dimension {existing_dim}"
                    )

                self.collection.load()
            else:
                self._create_collection()

        except Exception as e:
            try:
                self.close()
            except Exception:
                logging.getLogger(__name__).exception("Failed to clean up Milvus initialization")
            raise ConnectionError(f"Failed to connect to Milvus: {e}") from e

    def _create_collection(self):
        """Create Milvus collection with schema."""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=128),
        ]

        schema = CollectionSchema(fields=fields, description="Policy documents")
        self.collection = Collection(name=self.collection_name, schema=schema, using=self._connection_alias)

        # Create index
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()

    def add_documents(self, documents: List["PolicyDocument"], *, upsert: bool = False, flush: bool = True):
        """Add documents, or replace stable primary keys when explicitly requested."""
        if not documents:
            return

        if self.collection is None:
            raise RuntimeError("Milvus collection is not initialized")
        # Prepare texts
        texts = [f"{doc.title} {doc.content}" for doc in documents]

        # Generate embeddings
        embeddings = self._embed_texts(texts)

        # Prepare entities
        entities = []
        for idx, doc in enumerate(documents):
            entities.append({
                "id": str(doc.id)[:512],  # 截断过长的ID
                "embedding": embeddings[idx].tolist(),
                "title": doc.title[:2048],  # 增加到2048
                "content": doc.content[:65535],
                "source": doc.source[:1024] if doc.source else "",  # 增加到1024
                "doc_type": doc.doc_type[:128] if doc.doc_type else "",
            })

        if upsert:
            self.collection.upsert(entities)
        else:
            self.collection.insert(entities)
        if flush:
            self.collection.flush()

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List["PolicyDocument"], List[float]]:
        """Search for similar documents."""
        if self.collection is None:
            raise RuntimeError("Milvus collection is not initialized")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        # Generate query embedding
        query_emb = self._embed_texts([query])[0]

        # Search params
        search_params: Dict[str, Any] = {"metric_type": "IP", "params": {}}
        for index in self.collection.indexes:
            nlist = index.params.get("params", {}).get("nlist")
            if nlist is not None:
                # A title filter can leave a single matching guide in any IVF
                # partition. Probe all partitions rather than silently omitting it.
                search_params["params"]["nprobe"] = int(nlist) if filters else min(int(nlist), 128)
                break

        # Build filter expression
        expr = self._build_filter(filters) if filters else None

        # Search
        results = self.collection.search(
            data=[query_emb.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["id", "title", "content", "source", "doc_type"]
        )

        documents = []
        scores = []
        for hits in results:
            for hit in hits:
                if hit.score >= threshold:
                    documents.append(PolicyDocument(
                        id=hit.id, title=hit.entity.get("title"),
                        content=hit.entity.get("content"), source=hit.entity.get("source"),
                        doc_type=PolicyType(hit.entity.get("doc_type")),
                    ))
                    scores.append(float(hit.score))
        return documents, scores

    @staticmethod
    def _build_filter(filters: Dict[str, Any]) -> Optional[str]:
        """Build Milvus filter expression."""
        expressions = []

        if "doc_type" in filters:
            expressions.append(f'doc_type == {json.dumps(str(filters["doc_type"]), ensure_ascii=False)}')

        if "source" in filters:
            expressions.append(f'source like {json.dumps("%" + str(filters["source"]) + "%", ensure_ascii=False)}')

        if "title" in filters:
            expressions.append(f'title like {json.dumps("%" + str(filters["title"]) + "%", ensure_ascii=False)}')

        if "coverage_year" in filters:
            expressions.append(f'content like {json.dumps("%保障年度：" + str(filters["coverage_year"]) + "%", ensure_ascii=False)}')

        if "content" in filters:
            expressions.append(f'content like {json.dumps("%" + str(filters["content"]) + "%", ensure_ascii=False)}')

        return " && ".join(expressions) if expressions else None

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        if self.backend == "openai":
            return self._embed_openai(texts)
        elif self.backend == "dashscope":
            return self._embed_dashscope(texts)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}. Supported: openai, dashscope")

    def _get_model_name_from_backend(self, settings) -> str:
        """根据后端获取模型名称"""
        if self.backend == "openai":
            return settings.embedding.openai_model
        elif self.backend == "dashscope":
            return settings.embedding.dashscope_model
        raise ValueError(f"Unsupported backend: {self.backend}. Supported: openai, dashscope")

    def _embed_openai(self, texts: List[str]) -> np.ndarray:
        """OpenAI embeddings."""

        # 使用 settings.embedding 配置
        api_key = settings.embedding.openai_api_key or os.getenv("LLM_API_KEY")
        base_url = settings.embedding.openai_base_url

        if not api_key:
            raise ValueError("Missing API key for OpenAI backend")

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        with client:
            res = client.embeddings.create(model=self.model_name, input=texts)
            vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        return self._normalize(vecs)

    def _embed_dashscope(self, texts: List[str]) -> np.ndarray:
        """DashScope embeddings."""

        api_key = settings.embedding.dashscope_api_key
        if not api_key:
            raise ValueError("Missing API key for DashScope backend")

        url = settings.embedding.dashscope_base_url
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        all_vecs = []
        for text in texts:
            data = {
                "model": self.model_name,
                "input": {"texts": [text]}
            }
            # 添加可选参数
            parameters: Dict[str, Any] = {}
            if settings.embedding.dashscope_dimension is not None:
                parameters["dimension"] = settings.embedding.dashscope_dimension
            if settings.embedding.dashscope_output_type:
                parameters["output_type"] = settings.embedding.dashscope_output_type
            if parameters:
                data["parameters"] = parameters

            with requests.post(url, headers=headers, json=data, timeout=settings.embedding.timeout) as response:
                response.raise_for_status()
                result = response.json()
            embedding_response = DashScopeEmbeddingResponse.model_validate(result)
            embedding = embedding_response.output.embeddings[0].embedding
            if len(embedding) != self.embedding_dim:
                raise ValueError(
                    f"DashScope embedding dimension {len(embedding)} does not match "
                    f"collection dimension {self.embedding_dim}"
                )
            all_vecs.append(embedding)

        vecs = np.array(all_vecs, dtype=np.float32)
        return self._normalize(vecs)

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        """L2 normalize vectors."""
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        return (vecs / norms).astype(np.float32)

    def _infer_dim(self) -> int:
        """Infer embedding dimension from backend and model.

        Known OpenAI models use their native dimension. Other OpenAI models use
        EMBEDDING_DIM. DashScope uses an explicit dimension, a supported generic
        dimension, or its provider default of 1024.
        """

        dimension: int
        if self.backend == "openai":
            # OpenAI embedding dimensions
            if "3-large" in self.model_name:
                return 3072
            if "3-small" in self.model_name or "ada-002" in self.model_name:
                return 1536
            dimension = settings.embedding.dimension

        elif self.backend == "dashscope":
            # DashScope text-embedding-v3 支持: 64, 128, 256, 512, 768, 1024
            # 优先使用明确配置的维度
            requested_dimension = settings.embedding.dashscope_dimension
            if requested_dimension is not None:
                dimension = requested_dimension
            else:
                dimension = settings.embedding.dimension
                if dimension > 0 and dimension not in (64, 128, 256, 512, 768, 1024):
                    dimension = 1024
        else:
            raise ValueError(f"Unsupported backend: {self.backend}. Supported: openai, dashscope")

        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive")
        return dimension

    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        if self.collection is None:
            raise RuntimeError("Milvus collection is closed")
        return {
            "total_documents": self.collection.num_entities,
            "collection_name": self.collection_name,
            "host": self.host,
            "port": self.port,
            "backend": self.backend,
            "model": self.model_name,
            "dim": self.embedding_dim
        }

    def close(self) -> None:
        """Disconnect this store's alias without unloading the shared server collection."""
        self.collection = None
        if self._connected:
            connections.disconnect(self._connection_alias)
            self._connected = False

    def __del__(self):
        # Explicit close reports errors. Destruction is best effort, including partial init.
        if getattr(self, "_connected", False):
            try:
                self.close()
            except Exception:
                logging.getLogger(__name__).debug("Milvus destructor cleanup failed", exc_info=True)
