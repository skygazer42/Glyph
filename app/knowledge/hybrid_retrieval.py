#!/usr/bin/env python3
"""
混合检索策略：文档级召回 + 块级检索
Two-Stage Retrieval: Document-level Recall + Chunk-level Retrieval
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import re


class HybridRetriever:
    """
    两阶段混合检索器

    阶段1: BM25文档级召回（粗召回）
    阶段2: 块级精确检索（细检索）
    """

    def __init__(self, documents: List[Dict[str, Any]], chunked_documents: Dict[str, List[Dict[str, Any]]]):
        """
        Args:
            documents: 完整文档列表
                [{'text': '...', 'title': '...', 'file': '...', 'doc_id': '...'}, ...]
            chunked_documents: 已切块的文档
                {
                    'doc_id_1': [
                        {'text': 'chunk1...', 'chunk_id': 0, 'section': '...'},
                        {'text': 'chunk2...', 'chunk_id': 1, 'section': '...'},
                    ],
                    'doc_id_2': [...]
                }
        """
        self.documents = documents
        self.chunked_documents = chunked_documents
        self._build_document_index()

    def _build_document_index(self):
        """构建文档索引（用于快速查找）"""
        self.doc_id_to_doc = {doc.get('doc_id', doc.get('file', i)): doc
                              for i, doc in enumerate(self.documents)}

    def retrieve(
        self,
        query: str,
        top_k_docs: int = 10,
        top_k_chunks: int = 20,
        chunk_strategy: str = 'bm25'
    ) -> List[Dict[str, Any]]:
        """
        两阶段检索

        Args:
            query: 查询文本
            top_k_docs: 文档级召回数量
            top_k_chunks: 块级检索数量
            chunk_strategy: 块级检索策略 ('bm25', 'vector', 'hybrid')

        Returns:
            List of chunks with metadata
        """
        print(f"\n[HybridRetriever] 开始两阶段检索")
        print(f"  查询: {query}")
        print(f"  文档召回: Top {top_k_docs}, 块检索: Top {top_k_chunks}")

        # ===== 阶段1: 文档级召回 =====
        print(f"\n  [阶段1] 文档级BM25召回...")
        recalled_docs = self._recall_documents_bm25(query, top_k=top_k_docs)

        if not recalled_docs:
            print(f"    ⚠ 未召回任何文档")
            return []

        print(f"    ✓ 召回 {len(recalled_docs)} 个文档:")
        for i, (doc_id, score) in enumerate(recalled_docs[:5], 1):
            doc = self.doc_id_to_doc.get(doc_id, {})
            print(f"      {i}. [{score:.2f}] {doc.get('title', doc_id)[:40]}")

        # ===== 阶段2: 块级检索 =====
        print(f"\n  [阶段2] 在召回文档内进行块级检索...")

        # 收集所有召回文档的chunks
        candidate_chunks = []
        for doc_id, doc_score in recalled_docs:
            chunks = self.chunked_documents.get(doc_id, [])
            for chunk in chunks:
                candidate_chunks.append({
                    **chunk,
                    'doc_id': doc_id,
                    'doc_score': doc_score,
                    'doc_title': self.doc_id_to_doc.get(doc_id, {}).get('title', doc_id)
                })

        print(f"    候选chunks总数: {len(candidate_chunks)}")

        # 在候选chunks中进行检索
        if chunk_strategy == 'bm25':
            final_chunks = self._retrieve_chunks_bm25(query, candidate_chunks, top_k=top_k_chunks)
        elif chunk_strategy == 'vector':
            # TODO: 实现向量检索
            print(f"    ⚠ 向量检索未实现，使用BM25")
            final_chunks = self._retrieve_chunks_bm25(query, candidate_chunks, top_k=top_k_chunks)
        else:
            # hybrid: 未来可以结合BM25和向量
            final_chunks = self._retrieve_chunks_bm25(query, candidate_chunks, top_k=top_k_chunks)

        print(f"    ✓ 最终返回 {len(final_chunks)} 个chunks")
        for i, chunk in enumerate(final_chunks[:5], 1):
            preview = chunk['text'][:60].replace('\n', ' ')
            print(f"      {i}. [{chunk.get('chunk_score', 0):.2f}] {chunk['doc_title'][:30]} - {preview}...")

        return final_chunks

    def _recall_documents_bm25(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        文档级BM25召回

        Returns:
            [(doc_id, score), ...]
        """
        # 提取查询关键词
        keywords = self._extract_keywords(query)

        # 计算每个文档的BM25分数
        doc_scores = []
        for doc in self.documents:
            doc_id = doc.get('doc_id', doc.get('file', ''))
            score = self._calculate_bm25_score(
                keywords,
                doc['text'],
                doc.get('title', '')
            )

            if score > 0:
                doc_scores.append((doc_id, score))

        # 按分数排序
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return doc_scores[:top_k]

    def _retrieve_chunks_bm25(
        self,
        query: str,
        candidate_chunks: List[Dict[str, Any]],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        在候选chunks中进行BM25检索

        Args:
            query: 查询文本
            candidate_chunks: 候选chunk列表
            top_k: 返回数量

        Returns:
            排序后的chunks
        """
        keywords = self._extract_keywords(query)

        # 计算每个chunk的分数
        scored_chunks = []
        for chunk in candidate_chunks:
            chunk_score = self._calculate_bm25_score(
                keywords,
                chunk['text'],
                chunk.get('section', '')
            )

            # 融合文档级分数（可选）
            # 给文档级分数一个权重，确保在高相关文档中的chunks优先
            doc_score = chunk.get('doc_score', 0)
            combined_score = chunk_score * 0.8 + doc_score * 0.2

            if combined_score > 0:
                chunk_copy = chunk.copy()
                chunk_copy['chunk_score'] = combined_score
                chunk_copy['bm25_score'] = chunk_score
                scored_chunks.append(chunk_copy)

        # 按分数排序
        scored_chunks.sort(key=lambda x: x['chunk_score'], reverse=True)

        return scored_chunks[:top_k]

    def _extract_keywords(self, query: str) -> List[str]:
        """
        从查询中提取关键词

        简单实现：提取2-4字的词组
        """
        keywords = []

        # 去除问号、句号等
        query = re.sub(r'[?。！？,，]', '', query)

        # 提取不同长度的词组
        for i in range(len(query)):
            for length in [4, 3, 2]:
                if i + length <= len(query):
                    word = query[i:i+length]
                    # 过滤停用词
                    if word not in ['如何', '什么', '哪些', '是否', '可以', '的是', '多少', '怎么', '怎样']:
                        keywords.append(word)

        # 去重
        keywords = list(set(keywords))

        return keywords

    def _calculate_bm25_score(
        self,
        keywords: List[str],
        text: str,
        title: str = '',
        k1: float = 1.5,
        b: float = 0.75
    ) -> float:
        """
        计算BM25分数（简化版）

        Args:
            keywords: 查询关键词列表
            text: 文档/chunk文本
            title: 标题（可选，会加权）
            k1: BM25参数
            b: BM25参数

        Returns:
            BM25分数
        """
        score = 0.0
        text_lower = text.lower()
        title_lower = title.lower()

        # 简化的BM25实现
        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 计算词频 (TF)
            tf = text_lower.count(keyword_lower)

            if tf > 0:
                # 简化的BM25公式（不考虑IDF和文档长度归一化）
                # 实际BM25需要预先计算IDF和平均文档长度
                keyword_score = (tf * (k1 + 1)) / (tf + k1)
                score += keyword_score * len(keyword)  # 长词权重更高

            # 标题匹配加分
            if keyword_lower in title_lower:
                score += 10.0 * len(keyword)

        return score


# ===== 使用示例 =====

def create_hybrid_retriever_from_files(
    data_dir: Path,
    chunking_strategy: str = 'sentence',
    chunk_size: int = 600,
    chunk_overlap: int = 80
) -> HybridRetriever:
    """
    从Markdown文件创建HybridRetriever

    Args:
        data_dir: 数据目录
        chunking_strategy: 切块策略 ('sentence', 'simple', 'keyword_aware')
        chunk_size: chunk大小
        chunk_overlap: chunk重叠

    Returns:
        HybridRetriever实例
    """
    from app.knowledge.hierarchical_index import (
        HierarchicalMarkdownProcessor,
        ChunkConfig
    )

    print(f"\n[创建HybridRetriever]")
    print(f"  数据目录: {data_dir}")
    print(f"  切块策略: {chunking_strategy} (size={chunk_size}, overlap={chunk_overlap})")

    # 1. 读取所有文档
    md_files = list(data_dir.rglob("*.md"))
    documents = []

    print(f"\n  读取文档: 找到 {len(md_files)} 个文件")

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    documents.append({
                        'text': content,
                        'title': md_file.stem,
                        'file': md_file.name,
                        'doc_id': md_file.stem,
                        'size': len(content)
                    })
        except Exception as e:
            print(f"    警告: 无法读取 {md_file.name}: {e}")

    print(f"  ✓ 成功读取 {len(documents)} 个文档")

    # 2. 切块
    print(f"\n  切块处理...")
    config = ChunkConfig(
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    processor = HierarchicalMarkdownProcessor(config=config)

    chunked_documents = {}
    total_chunks = 0

    for doc in documents:
        doc_id = doc['doc_id']

        # 提取层次结构
        hierarchy = processor.extract_hierarchy(doc['text'], doc_id=doc_id)

        # 提取所有chunks
        chunks = []
        chunk_id = 0

        for section in hierarchy.get('sections', []):
            section_title = section.get('title', '')
            section_content = section.get('content', '')

            # 对section内容进行切块
            if section_content.strip():
                section_path = section.get('path', section_title)
                section_chunks = processor._split_into_chunks(
                    section_content,
                    section_id=f"{doc_id}_section_{len(chunks)}",
                    path=section_path
                )

                for chunk_text in section_chunks:
                    chunks.append({
                        'text': chunk_text,
                        'chunk_id': chunk_id,
                        'section': section_title,
                        'level': section.get('level', 0)
                    })
                    chunk_id += 1

            # 处理subsections
            for subsection in section.get('subsections', []):
                subsection_title = subsection.get('title', '')
                subsection_content = subsection.get('content', '')

                if subsection_content.strip():
                    subsection_path = subsection.get('path', f"{section_title} > {subsection_title}")
                    subsection_chunks = processor._split_into_chunks(
                        subsection_content,
                        section_id=f"{doc_id}_subsection_{len(chunks)}",
                        path=subsection_path
                    )

                    for chunk_text in subsection_chunks:
                        chunks.append({
                            'text': chunk_text,
                            'chunk_id': chunk_id,
                            'section': f"{section_title} > {subsection_title}",
                            'level': subsection.get('level', 0)
                        })
                        chunk_id += 1

        chunked_documents[doc_id] = chunks
        total_chunks += len(chunks)

    print(f"  ✓ 切块完成: 总共 {total_chunks} 个chunks")
    print(f"    平均每文档: {total_chunks / len(documents):.1f} chunks")

    # 3. 创建Retriever
    retriever = HybridRetriever(documents, chunked_documents)

    print(f"\n✓ HybridRetriever创建完成")
    return retriever


if __name__ == "__main__":
    """测试两阶段检索"""

    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 创建检索器
    data_dir = Path("F:/pythonproject/gov/data/process")
    retriever = create_hybrid_retriever_from_files(
        data_dir,
        chunking_strategy='sentence',
        chunk_size=600,
        chunk_overlap=80
    )

    # 测试查询
    test_queries = [
        "家电以旧换新的补贴标准是多少？",
        "手机购新补贴如何申请？",
        "汽车消费券可以在哪些地方使用？"
    ]

    print("\n" + "="*70)
    print("测试两阶段检索")
    print("="*70)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"测试 {i}/{len(test_queries)}: {query}")
        print(f"{'='*70}")

        # 执行检索
        results = retriever.retrieve(
            query,
            top_k_docs=10,      # 文档级召回10个
            top_k_chunks=20,    # 块级检索返回20个
            chunk_strategy='bm25'
        )

        # 显示结果
        print(f"\n[最终结果] Top 5 chunks:")
        for j, chunk in enumerate(results[:5], 1):
            print(f"\n  [{j}] 文档: {chunk['doc_title']}")
            print(f"      Section: {chunk.get('section', 'N/A')}")
            print(f"      分数: BM25={chunk.get('bm25_score', 0):.2f}, 组合={chunk.get('chunk_score', 0):.2f}")
            print(f"      内容: {chunk['text'][:150].replace(chr(10), ' ')}...")

    print("\n" + "="*70)
    print("测试完成!")
    print("="*70)
