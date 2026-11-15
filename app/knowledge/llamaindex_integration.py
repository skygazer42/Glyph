"""
LlamaIndex 集成模块 - 将分级索引集成到现有系统
"""


import tempfile
from uuid import UUID, NAMESPACE_URL, uuid5
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import asyncio
import anyio

from app.knowledge.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)
from app.config.app_config import settings
from app.models.base import PolicyDocument, PolicyType


class LlamaIndexIntegration:
    """LlamaIndex 分级索引集成"""

    def __init__(self, storage_dir: Optional[str] = None):
        resolved_dir = settings.llamaindex.storage_dir if storage_dir is None else storage_dir
        self.storage_dir = Path(resolved_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已有索引
        self.has_index = self._check_existing_index()
        self.retriever: Optional[HierarchicalRetriever] = None

        if self.has_index:
            self._load_retriever()

    def _check_existing_index(self) -> bool:
        """检查是否存在索引"""
        indices = ['doc_index', 'section_index', 'chunk_index']
        return all((self.storage_dir / idx).exists() for idx in indices)

    def _load_retriever(self) -> None:
        self.retriever = HierarchicalRetriever(str(self.storage_dir))
        print(f"已加载 LlamaIndex 检索器: {self.storage_dir}")

    async def build_index_from_documents(
        self, documents: List["PolicyDocument"], chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> bool:
        return await anyio.to_thread.run_sync(
            self._build_index_sync, documents, chunk_size, chunk_overlap,
        )

    def _build_index_sync(self, documents, chunk_size: int, chunk_overlap: int) -> bool:
        with tempfile.TemporaryDirectory(prefix="index-md-", dir=self.storage_dir) as temp_dir:
            md_files = []
            document_ids = {}
            for index, doc in enumerate(documents):
                content = f"# {doc.title}\n\n"
                if doc.source:
                    content += f"**来源:** {doc.source}\n\n"
                if doc.doc_type:
                    content += f"**类型:** {doc.doc_type}\n\n"
                path = Path(temp_dir) / f"{index}.md"
                path.write_text(content + doc.content, encoding="utf-8")
                md_files.append(str(path))
                document_ids[str(path)] = str(doc.id)
            builder = HierarchicalIndexBuilder(str(self.storage_dir))
            builder.processor.config = ChunkConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            stats = builder.build_from_markdown_files(md_files, document_ids=document_ids)
            print(f"索引构建成功: {stats}")
        previous = self.retriever
        self._load_retriever()
        self.has_index = True
        if previous is not None:
            previous.close()
        return True

    async def search(
        self, query: str, top_k: int = 10, threshold: float = 0.7,
        retrieval_mode: str = "hybrid",
    ) -> Tuple[List["PolicyDocument"], List[float]]:
        if self.retriever is None:
            raise RuntimeError("Hierarchical retriever is not initialized")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        nodes = await asyncio.to_thread(
            self.retriever.retrieve, query, top_k=top_k,
            use_rerank=True, retrieval_mode=retrieval_mode,
        )
        documents = []
        scores = []
        for node in nodes:
            score = float(node.metadata["retrieval_score"])
            if score < threshold:
                continue
            external_id = str(node.metadata.get("doc_id", node.id_))
            try:
                document_id = UUID(external_id)
            except ValueError:
                document_id = uuid5(NAMESPACE_URL, external_id)
            documents.append(PolicyDocument(
                id=document_id, title=node.metadata.get("title", ""),
                content=node.get_content(), source=node.metadata.get("source", ""),
                doc_type=PolicyType.GUIDELINE,
                metadata={**node.metadata, "index_document_id": external_id},
            ))
            scores.append(score)
        return documents, scores

    async def close(self) -> None:
        retriever, self.retriever = self.retriever, None
        self.has_index = False
        if retriever is not None:
            with anyio.fail_after(5, shield=True):
                await anyio.to_thread.run_sync(retriever.close, abandon_on_cancel=True)

    async def get_summary(self, query: str) -> str:
        """获取查询的摘要回答"""

        if self.retriever is None:
            raise RuntimeError("Hierarchical retriever is not initialized")
        retriever = self.retriever

        def query_summary() -> str:
            engine = retriever.get_query_engine(
                retrieval_mode="hybrid", response_mode="tree_summarize",
            )
            return str(engine.query(query))

        return await asyncio.to_thread(query_summary)

    def get_stats(self) -> Dict:
        """获取索引统计信息"""

        stats = {
            "has_index": self.has_index,
            "storage_dir": str(self.storage_dir)
        }

        if self.has_index:
            # 统计各索引大小
            for index_name in ['doc_index', 'section_index', 'chunk_index', 'summary_index']:
                index_path = self.storage_dir / index_name
                if index_path.exists():
                    size = sum(f.stat().st_size for f in index_path.rglob('*') if f.is_file())
                    stats[f"{index_name}_size_mb"] = round(size / (1024 * 1024), 2)

        return stats


# 增强现有的 VectorRetrieverAgent
class EnhancedVectorRetrieverAgent:
    """增强的向量检索代理 - 集成 LlamaIndex"""

    def __init__(self,
                 use_llamaindex: bool = True,
                 llamaindex_storage: Optional[str] = None):

        self.use_llamaindex = use_llamaindex

        # 初始化 LlamaIndex
        if self.use_llamaindex:
            self.llamaindex: Optional[LlamaIndexIntegration] = LlamaIndexIntegration(llamaindex_storage)
        else:
            self.llamaindex = None


    async def search(self,
                    query: str,
                    top_k: int = 10,
                    threshold: float = 0.7) -> Tuple[List["PolicyDocument"], List[float]]:
        """使用 LlamaIndex 进行搜索"""

        if self.llamaindex is None or not self.llamaindex.has_index:
            return [], []
        return await self.llamaindex.search(
            query, top_k=top_k, threshold=threshold, retrieval_mode="hybrid",
        )

    async def add_documents(self, documents: List["PolicyDocument"]) -> bool:
        if self.llamaindex is None:
            return False
        return await self.llamaindex.build_index_from_documents(documents)

    async def close(self) -> None:
        if self.llamaindex is not None:
            await self.llamaindex.close()


# 使用示例
async def demo():
    """演示集成使用"""

    retriever = await anyio.to_thread.run_sync(EnhancedVectorRetrieverAgent)
    try:
        query = "家电以旧换新补贴标准"
        documents, scores = await retriever.search(query, top_k=5)
        print(f"查询: {query}")
        print(f"找到 {len(documents)} 个相关文档:")
        for i, doc in enumerate(documents, 1):
            print(f"  {i}. {doc.title} (分数: {scores[i - 1]:.2f})")
            print(f"     {doc.content[:100]}...")
    finally:
        await retriever.close()


if __name__ == "__main__":
    asyncio.run(demo())
