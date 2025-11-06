"""
Milvus vector store for document embeddings and similarity search.

Supports backends:
- openai (default): OpenAI Embeddings API
- ollama: local embedding via lightrag.ollama
"""

import os
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

from ..agents.base.types import PolicyDocument


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
        from config.settings import settings

        # Embedding config - 优先使用 settings.embedding
        self.backend = backend or settings.embedding.backend
        self.model_name = model_name or self._get_model_name_from_backend(settings)
        self.embedding_dim = self._infer_dim()

        # Milvus config - 使用 settings.database.milvus_*
        self.host = host or settings.database.milvus_host
        self.port = port or settings.database.milvus_port
        self.user = user or settings.database.milvus_user
        self.password = password or settings.database.milvus_password
        self.db_name = db_name or settings.database.milvus_db_name
        self.collection_name = collection_name or settings.database.milvus_collection_name

        # Connect and initialize
        self.collection: Optional[Collection] = None
        self._connect()

    def _connect(self):
        """Connect to Milvus and initialize collection."""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=str(self.port),
                user=self.user,
                password=self.password,
                db_name=self.db_name
            )

            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.collection.load()
            else:
                self._create_collection()

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Milvus: {e}")

    def _create_collection(self):
        """Create Milvus collection with schema."""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=128),
        ]

        schema = CollectionSchema(fields=fields, description="Policy documents")
        self.collection = Collection(name=self.collection_name, schema=schema)

        # Create index
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()

    def add_documents(self, documents: List[PolicyDocument]):
        """Add documents to the store."""
        if not documents:
            return

        # Prepare texts
        texts = [f"{doc.title} {doc.content}" for doc in documents]

        # Generate embeddings
        embeddings = self._embed_texts(texts)

        # Prepare entities
        entities = []
        for idx, doc in enumerate(documents):
            entities.append({
                "id": str(doc.id),
                "embedding": embeddings[idx].tolist(),
                "title": doc.title[:1024],
                "content": doc.content[:65535],
                "source": doc.source[:512] if doc.source else "",
                "doc_type": doc.doc_type[:128] if doc.doc_type else "",
            })

        # Insert
        self.collection.insert(entities)
        self.collection.flush()

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """Search for similar documents."""
        # Generate query embedding
        query_emb = self._embed_texts([query])[0]

        # Search params
        search_params = {"metric_type": "IP", "params": {"nprobe": 10}}

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

        # Process results
        documents = []
        scores = []

        for hits in results:
            for hit in hits:
                if hit.score >= threshold:
                    doc = PolicyDocument(
                        id=hit.entity.get("id"),
                        title=hit.entity.get("title", ""),
                        content=hit.entity.get("content", ""),
                        source=hit.entity.get("source", ""),
                        doc_type=hit.entity.get("doc_type", ""),
                        keywords=[],
                        regions=[],
                        target_groups=[]
                    )
                    documents.append(doc)
                    scores.append(float(hit.score))

        return documents, scores

    def _build_filter(self, filters: Dict[str, Any]) -> Optional[str]:
        """Build Milvus filter expression."""
        expressions = []

        if "doc_type" in filters:
            expressions.append(f'doc_type == "{filters["doc_type"]}"')

        if "source" in filters:
            expressions.append(f'source like "%{filters["source"]}%"')

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
        return "text-embedding-3-small"

    def _embed_openai(self, texts: List[str]) -> np.ndarray:
        """OpenAI embeddings."""
        from openai import OpenAI
        from config.settings import settings

        # 使用 settings.embedding 配置
        api_key = settings.embedding.openai_api_key or os.getenv("LLM_API_KEY")
        base_url = settings.embedding.openai_base_url

        if not api_key:
            raise ValueError("Missing API key for OpenAI backend")

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        res = client.embeddings.create(model=self.model_name, input=texts)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        return self._normalize(vecs)

    def _embed_dashscope(self, texts: List[str]) -> np.ndarray:
        """DashScope embeddings."""
        import requests
        from config.settings import settings

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
            parameters = {}
            if settings.embedding.dashscope_dimension:
                parameters["dimension"] = settings.embedding.dashscope_dimension
            if settings.embedding.dashscope_output_type:
                parameters["output_type"] = settings.embedding.dashscope_output_type
            if parameters:
                data["parameters"] = parameters

            response = requests.post(url, headers=headers, json=data, timeout=settings.embedding.timeout)
            response.raise_for_status()
            result = response.json()
            embedding = result["output"]["embeddings"][0]["embedding"]
            all_vecs.append(embedding)

        vecs = np.array(all_vecs, dtype=np.float32)
        return self._normalize(vecs)

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        """L2 normalize vectors."""
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        return (vecs / norms).astype(np.float32)

    def _infer_dim(self) -> int:
        """Infer embedding dimension from backend and model."""
        from config.settings import settings

        if self.backend == "openai":
            if self.model_name and "3-large" in self.model_name:
                return 3072
            return 1536
        elif self.backend == "dashscope":
            return settings.embedding.dimension
        return settings.embedding.dimension

    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        return {
            "total_documents": self.collection.num_entities if self.collection else 0,
            "collection_name": self.collection_name,
            "host": self.host,
            "port": self.port,
            "backend": self.backend,
            "model": self.model_name,
            "dim": self.embedding_dim
        }

    def __del__(self):
        """Cleanup."""
        try:
            if self.collection:
                self.collection.release()
            connections.disconnect("default")
        except:
            pass
