"""
LlamaIndex 集成模块 - 将分级索引集成到现有系统
"""


import os
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from pathlib import Path
import asyncio

# 延迟导入，避免循环依赖
if TYPE_CHECKING:
    from app.agents.framework.base.types import PolicyDocument

from app.knowledge.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)
from app.config import settings


class LlamaIndexIntegration:
    """LlamaIndex 分级索引集成"""

    def __init__(self, storage_dir: Optional[str] = None):
        resolved_dir = storage_dir or settings.llamaindex.storage_dir
        self.storage_dir = Path(resolved_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已有索引
        self.has_index = self._check_existing_index()
        self.retriever = None

        if self.has_index:
            self._load_retriever()

    def _check_existing_index(self) -> bool:
        """检查是否存在索引"""
        indices = ['doc_index', 'section_index', 'chunk_index']
        return all((self.storage_dir / idx).exists() for idx in indices)

    def _load_retriever(self):
        """加载检索器"""
        try:
            self.retriever = HierarchicalRetriever(str(self.storage_dir))
            print(f"已加载 LlamaIndex 检索器: {self.storage_dir}")
        except Exception as e:
            print(f"加载检索器失败: {e}")
            self.retriever = None

    async def build_index_from_documents(self, documents: List["PolicyDocument"],
                                        chunk_size: int = 800,
                                        chunk_overlap: int = 100) -> bool:
        """从 PolicyDocument 构建索引"""

        # 将文档写入临时 Markdown 文件
        temp_dir = self.storage_dir / "temp_md"
        temp_dir.mkdir(exist_ok=True)

        md_files = []
        for doc in documents:
            # 生成 Markdown 内容
            md_content = f"# {doc.title}\n\n"
            if doc.source:
                md_content += f"**来源:** {doc.source}\n\n"
            if doc.doc_type:
                md_content += f"**类型:** {doc.doc_type}\n\n"
            md_content += doc.content

            # 写入文件
            file_path = temp_dir / f"{doc.id}.md"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            md_files.append(str(file_path))

        # 构建索引
        config = ChunkConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        builder = HierarchicalIndexBuilder(str(self.storage_dir))
        builder.processor.config = config

        try:
            stats = builder.build_from_markdown_files(md_files)
            print(f"索引构建成功: {stats}")

            # 清理临时文件
            for f in md_files:
                os.remove(f)
            temp_dir.rmdir()

            # 重新加载检索器
            self._load_retriever()
            self.has_index = True
            return True

        except Exception as e:
            print(f"索引构建失败: {e}")
            return False

    async def search(self,
                    query: str,
                    top_k: int = 10,
                    threshold: float = 0.7,
                    retrieval_mode: str = "hybrid") -> Tuple[List["PolicyDocument"], List[float]]:
        """搜索文档"""

        if not self.retriever:
            print("错误: 检索器未初始化")
            return [], []

        try:
            # 执行检索
            nodes = self.retriever.retrieve(
                query,
                top_k=top_k,
                use_rerank=True,
                retrieval_mode=retrieval_mode
            )

            # 转换为 PolicyDocument
            from app.agents.framework.base.types import PolicyDocument
            documents = []
            scores = []

            for idx, node in enumerate(nodes):
                # 从元数据重建 PolicyDocument
                doc = PolicyDocument(
                    id=node.metadata.get('doc_id', node.id_),
                    title=node.metadata.get('title', ''),
                    content=node.text,
                    source=node.metadata.get('source', ''),
                    doc_type=node.metadata.get('type', ''),
                    keywords=[],
                    regions=[],
                    target_groups=[],
                    metadata={
                        'path': node.metadata.get('path', ''),
                        'level': node.metadata.get('level', 0),
                        'chunk_idx': node.metadata.get('chunk_idx', 0)
                    }
                )
                documents.append(doc)

                score = getattr(node, "score", None)
                if score is None:
                    # Fallback：按照排名提供轻量分数，但避免超过1
                    score = max(0.0, 1.0 - 0.05 * idx)
                scores.append(float(score))

            return documents, scores

        except Exception as e:
            print(f"搜索失败: {e}")
            return [], []

    async def get_summary(self, query: str) -> str:
        """获取查询的摘要回答"""

        if not self.retriever:
            return "检索器未初始化"

        try:
            # 获取查询引擎
            engine = self.retriever.get_query_engine(
                retrieval_mode="hybrid",
                response_mode="tree_summarize"
            )

            # 执行查询
            response = engine.query(query)
            return str(response)

        except Exception as e:
            return f"查询失败: {e}"

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
            self.llamaindex = LlamaIndexIntegration(llamaindex_storage)
        else:
            self.llamaindex = None


    async def search(self,
                    query: str,
                    top_k: int = 10,
                    threshold: float = 0.7) -> Tuple[List["PolicyDocument"], List[float]]:
        """使用 LlamaIndex 进行搜索"""

        documents = []
        scores = []

        # 1. 使用 LlamaIndex
        if self.llamaindex and self.llamaindex.has_index:
            try:
                docs, scs = await self.llamaindex.search(
                    query,
                    top_k=top_k,
                    threshold=threshold,
                    retrieval_mode="hybrid"
                )
                if docs:
                    documents.extend(docs)
                    scores.extend(scs)
            except Exception as e:
                print(f"LlamaIndex 搜索失败: {e}")

        return documents, scores

    async def add_documents(self, documents: List["PolicyDocument"]) -> bool:
        """添加文档到索引"""

        success = True

        # 1. 添加到 LlamaIndex
        if self.llamaindex:
            try:
                await self.llamaindex.build_index_from_documents(documents)
            except Exception as e:
                print(f"LlamaIndex 添加文档失败: {e}")
                success = False

        # 2. 添加到 FAISS
        if self.faiss_store:
            try:
                self.faiss_store.add_documents(documents)
            except Exception as e:
                print(f"FAISS 添加文档失败: {e}")
                success = False

        return success


# 使用示例
async def demo():
    """演示集成使用"""

    # 创建增强检索器
    retriever = EnhancedVectorRetrieverAgent(
        use_llamaindex=True,
        fallback_to_faiss=True
    )

    # 测试查询
    query = "家电以旧换新补贴标准"
    documents, scores = await retriever.search(query, top_k=5)

    print(f"查询: {query}")
    print(f"找到 {len(documents)} 个相关文档:")
    for i, (doc, score) in enumerate(zip(documents, scores), 1):
        print(f"  {i}. {doc.title} (分数: {score:.2f})")
        print(f"     {doc.content[:100]}...")


if __name__ == "__main__":
    asyncio.run(demo())
