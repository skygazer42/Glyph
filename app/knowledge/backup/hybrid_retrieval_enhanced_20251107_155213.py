#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的混合检索策略：文档级召回 + 块级检索
Enhanced Hybrid Retrieval with Query Enhancement and Document Type Boosting

核心改进：
1. 查询增强 (Query Enhancement) - 根据意图扩展查询关键词
2. 文档类型加权 (Document Type Boosting) - 根据查询意图提升对应文档类型权重
3. 更智能的BM25评分 - 结合关键词匹配和文档类型匹配
"""

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import re


class EnhancedHybridRetriever:
    """
    增强版两阶段混合检索器

    阶段1: 文档级召回（BM25 + 文档类型加权）
    阶段2: 块级精确检索（BM25 + 文档分数融合）
    """

    # 查询意图识别规则
    INTENT_RULES = {
        "家电以旧换新": {
            "keywords": ["家电", "以旧换新", "换新"],
            "doc_type": "家电数码政策",
            "boost_keywords": ["家电", "补贴", "以旧换新", "回收"],
            "boost_factor": 2.0
        },
        "手机购新": {
            "keywords": ["手机", "购新", "买新"],
            "doc_type": "家电数码政策",
            "boost_keywords": ["手机", "数码", "购新", "补贴", "智能"],
            "boost_factor": 2.5
        },
        "数码产品": {
            "keywords": ["智能手表", "手表", "数码", "电子产品"],
            "doc_type": "家电数码政策",
            "boost_keywords": ["智能", "数码", "购新", "补贴"],
            "boost_factor": 2.0
        },
        "汽车补贴": {
            "keywords": ["汽车", "新车", "购车"],
            "doc_type": "汽车消费政策",
            "boost_keywords": ["汽车", "新车", "补贴", "申请"],
            "boost_factor": 2.0
        },
        "消费活动": {
            "keywords": ["消费", "活动", "消费券", "泉城购"],
            "doc_type": "消费活动政策",
            "boost_keywords": ["消费", "活动", "济南", "泉城"],
            "boost_factor": 1.5
        }
    }

    def __init__(self, documents: List[Dict[str, Any]], chunked_documents: Dict[str, List[Dict[str, Any]]]):
        """
        Args:
            documents: 完整文档列表
            chunked_documents: 已切块的文档
        """
        self.documents = documents
        self.chunked_documents = chunked_documents
        self._build_document_index()

    def _build_document_index(self):
        """构建文档索引"""
        self.doc_id_to_doc = {doc.get('doc_id', doc.get('file', i)): doc
                              for i, doc in enumerate(self.documents)}

    def _detect_query_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """
        检测查询意图

        Returns:
            {"intent": "手机购新", "doc_type": "家电数码政策", "boost_keywords": [...]}
        """
        query_lower = query.lower()

        # 匹配意图规则
        for intent_name, rule in self.INTENT_RULES.items():
            # 检查是否匹配关键词
            matches = sum(1 for kw in rule["keywords"] if kw in query_lower)
            if matches > 0:
                return {
                    "intent": intent_name,
                    "doc_type": rule["doc_type"],
                    "boost_keywords": rule["boost_keywords"],
                    "boost_factor": rule["boost_factor"]
                }

        return None

    def _enhance_query(self, query: str, intent: Optional[Dict[str, Any]]) -> str:
        """
        查询增强：根据意图扩展查询关键词

        Example:
            query: "买新手机有什么优惠活动？"
            intent: "手机购新"
            enhanced: "买新手机有什么优惠活动？ 手机 数码 购新 补贴 智能"
        """
        if not intent:
            return query

        # 添加增强关键词
        boost_keywords = intent["boost_keywords"]
        enhanced_query = query + " " + " ".join(boost_keywords)

        return enhanced_query

    def retrieve(
        self,
        query: str,
        top_k_docs: int = 10,
        top_k_chunks: int = 20,
        chunk_strategy: str = 'bm25',
        enable_query_enhancement: bool = True,
        enable_doc_type_boost: bool = True
    ) -> List[Dict[str, Any]]:
        """
        两阶段增强检索

        Args:
            query: 查询文本
            top_k_docs: 文档级召回数量
            top_k_chunks: 块级检索数量
            chunk_strategy: 块级检索策略
            enable_query_enhancement: 是否启用查询增强
            enable_doc_type_boost: 是否启用文档类型加权

        Returns:
            List of chunks with metadata
        """
        print(f"\n[EnhancedHybridRetriever] 开始增强版两阶段检索")
        print(f"  查询: {query}")
        print(f"  查询增强: {'启用' if enable_query_enhancement else '禁用'}")
        print(f"  类型加权: {'启用' if enable_doc_type_boost else '禁用'}")

        # 检测查询意图
        intent = self._detect_query_intent(query)
        if intent:
            print(f"  意图识别: {intent['intent']} → 目标类型: {intent['doc_type']}")
        else:
            print(f"  意图识别: 无明确意图，使用通用检索")

        # 查询增强
        enhanced_query = query
        if enable_query_enhancement and intent:
            enhanced_query = self._enhance_query(query, intent)
            print(f"  增强查询: {enhanced_query[:80]}...")

        # ===== 阶段1: 文档级召回 =====
        print(f"\n  [阶段1] 文档级BM25召回 (带类型加权)...")
        recalled_docs = self._recall_documents_bm25(
            enhanced_query,
            top_k=top_k_docs,
            intent=intent if enable_doc_type_boost else None
        )

        if not recalled_docs:
            print(f"    ⚠ 未召回任何文档")
            return []

        print(f"    ✓ 召回 {len(recalled_docs)} 个文档:")
        for i, (doc_id, score, doc_type) in enumerate(recalled_docs[:5], 1):
            doc = self.doc_id_to_doc.get(doc_id, {})
            type_match = "✓" if intent and doc_type == intent['doc_type'] else " "
            print(f"      {i}. [{type_match}] [{score:.2f}] {doc.get('title', doc_id)[:35]} ({doc_type})")

        # ===== 阶段2: 块级检索 =====
        print(f"\n  [阶段2] 在召回文档内进行块级检索...")

        # 收集所有召回文档的chunks
        candidate_chunks = []
        for doc_id, doc_score, doc_type in recalled_docs:
            chunks = self.chunked_documents.get(doc_id, [])
            for chunk in chunks:
                candidate_chunks.append({
                    **chunk,
                    'doc_id': doc_id,
                    'doc_score': doc_score,
                    'doc_title': self.doc_id_to_doc.get(doc_id, {}).get('title', doc_id),
                    'doc_type': doc_type
                })

        print(f"    候选chunks总数: {len(candidate_chunks)}")

        # 在候选chunks中进行检索
        final_chunks = self._retrieve_chunks_bm25(
            enhanced_query,
            candidate_chunks,
            top_k=top_k_chunks,
            intent=intent if enable_doc_type_boost else None
        )

        print(f"    ✓ 最终返回 {len(final_chunks)} 个chunks")
        for i, chunk in enumerate(final_chunks[:5], 1):
            preview = chunk['text'][:50].replace('\n', ' ')
            type_match = "✓" if intent and chunk.get('doc_type') == intent['doc_type'] else " "
            print(f"      {i}. [{type_match}] [{chunk.get('chunk_score', 0):.2f}] {chunk.get('full_title', chunk['doc_title'])[:35]}")

        return final_chunks

    def _recall_documents_bm25(
        self,
        query: str,
        top_k: int = 10,
        intent: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float, str]]:
        """
        文档级BM25召回（带文档类型加权）

        Returns:
            [(doc_id, score, doc_type), ...]
        """
        keywords = self._extract_keywords(query)

        # 计算每个文档的BM25分数
        doc_scores = []
        for doc in self.documents:
            doc_id = doc.get('doc_id', doc.get('file', ''))
            doc_type = doc.get('doc_type', '消费活动政策')

            # 基础BM25分数
            base_score = self._calculate_bm25_score(
                keywords,
                doc['text'],
                doc.get('title', '')
            )

            # 文档类型加权
            final_score = base_score
            if intent and doc_type == intent['doc_type']:
                boost_factor = intent.get('boost_factor', 2.0)
                final_score = base_score * boost_factor
                # print(f"      文档类型匹配: {doc.get('title', '')[:30]} 加权 {boost_factor}x")

            if final_score > 0:
                doc_scores.append((doc_id, final_score, doc_type))

        # 按分数排序
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return doc_scores[:top_k]

    def _retrieve_chunks_bm25(
        self,
        query: str,
        candidate_chunks: List[Dict[str, Any]],
        top_k: int = 20,
        intent: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        在候选chunks中进行BM25检索（带类型加权）
        """
        keywords = self._extract_keywords(query)

        # 计算每个chunk的分数
        scored_chunks = []
        for chunk in candidate_chunks:
            # 基础BM25分数
            chunk_score = self._calculate_bm25_score(
                keywords,
                chunk['text'],
                chunk.get('section', '')
            )

            # 文档级分数融合
            doc_score = chunk.get('doc_score', 0)
            combined_score = chunk_score * 0.7 + doc_score * 0.3

            # 文档类型加权
            if intent:
                chunk_doc_type = chunk.get('doc_type', '')
                if chunk_doc_type == intent['doc_type']:
                    boost_factor = intent.get('boost_factor', 2.0)
                    combined_score = combined_score * boost_factor

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
        """
        keywords = []

        # 去除问号、句号等
        query = re.sub(r'[?。！？,，]', '', query)

        # 提取不同长度的词组
        for i in range(len(query)):
            for length in [4, 3, 2]:
                if i + length <= len(query):
                    keyword = query[i:i+length]
                    if keyword and keyword not in keywords:
                        keywords.append(keyword)

        return keywords

    def _calculate_bm25_score(
        self,
        keywords: List[str],
        text: str,
        title: str = "",
        k1: float = 1.5,
        b: float = 0.75
    ) -> float:
        """
        计算BM25分数（简化版）

        Args:
            keywords: 关键词列表
            text: 文档文本
            title: 文档标题（可选，给予更高权重）
            k1: BM25参数
            b: BM25参数
        """
        text_lower = text.lower()
        title_lower = title.lower() if title else ""

        score = 0.0

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 标题匹配（高权重）
            if title_lower and keyword_lower in title_lower:
                score += 10.0

            # 文本匹配
            count = text_lower.count(keyword_lower)
            if count > 0:
                # 简化的BM25公式
                tf = count / (count + k1)
                score += tf * len(keyword)

        return score


def create_enhanced_hybrid_retriever_from_files(
    data_dir: Path,
    chunking_strategy: str = 'sentence',
    chunk_size: int = 600,
    chunk_overlap: int = 80
):
    """
    从Markdown文件创建增强版HybridRetriever

    Args:
        data_dir: 数据目录
        chunking_strategy: 切块策略
        chunk_size: chunk大小
        chunk_overlap: chunk重叠

    Returns:
        EnhancedHybridRetriever实例
    """
    from app.knowledge.hierarchical_index import (
        HierarchicalMarkdownProcessor,
        ChunkConfig
    )

    print(f"\n[创建增强版HybridRetriever]")
    print(f"  数据目录: {data_dir}")
    print(f"  切块策略: {chunking_strategy} (size={chunk_size}, overlap={chunk_overlap})")

    # 1. 读取所有文档（带完整元数据）
    md_files = list(data_dir.rglob("*.md"))
    documents = []

    print(f"\n  读取文档: 找到 {len(md_files)} 个文件")

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                continue

            # 提取标题
            lines = content.split('\n')
            title = None
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break

            if not title:
                title = md_file.stem

            # 确定文档类型
            file_path_str = str(md_file)
            if "家电" in file_path_str or "数码" in file_path_str or "家电" in title:
                doc_type = "家电数码政策"
            elif "汽车" in file_path_str or "新车" in file_path_str or "汽车" in title:
                doc_type = "汽车消费政策"
            elif "消费券" in title or "泉城购" in title or "消费活动" in title:
                doc_type = "消费活动政策"
            else:
                doc_type = "消费活动政策"

            documents.append({
                'text': content,
                'title': title,
                'file': md_file.name,
                'doc_id': md_file.stem,
                'doc_type': doc_type,
                'source': str(md_file.relative_to(data_dir)),
                'size': len(content)
            })

        except Exception as e:
            print(f"    警告: 无法读取 {md_file.name}: {e}")

    print(f"  ✓ 成功读取 {len(documents)} 个文档")

    # 打印文档类型统计
    doc_types = {}
    for doc in documents:
        dt = doc['doc_type']
        doc_types[dt] = doc_types.get(dt, 0) + 1

    print(f"\n  文档类型统计:")
    for dt, count in doc_types.items():
        print(f"    - {dt}: {count}个")

    # 2. 切块（保留文档元数据）
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
        doc_type = doc['doc_type']
        doc_title = doc['title']

        # 提取层次结构
        hierarchy = processor.extract_hierarchy(doc['text'], doc_id=doc_id)

        # 提取所有chunks（保留文档元数据）
        chunks = []
        chunk_id = 0

        for section in hierarchy.get('sections', []):
            section_title = section.get('title', '')
            section_content = section.get('content', '')

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
                        'level': section.get('level', 0),
                        'doc_type': doc_type,
                        'doc_title': doc_title,
                        'full_title': f"{doc_title} - {section_title}" if section_title else doc_title
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
                            'level': subsection.get('level', 0),
                            'doc_type': doc_type,
                            'doc_title': doc_title,
                            'full_title': f"{doc_title} - {section_title} > {subsection_title}"
                        })
                        chunk_id += 1

        chunked_documents[doc_id] = chunks
        total_chunks += len(chunks)

    print(f"  ✓ 切块完成: 总共 {total_chunks} 个chunks")
    print(f"    平均每文档: {total_chunks / len(documents):.1f} chunks")

    # 3. 创建Retriever
    retriever = EnhancedHybridRetriever(documents, chunked_documents)

    print(f"\n✓ 增强版HybridRetriever创建完成")
    return retriever


if __name__ == "__main__":
    """测试增强版混合检索"""

    data_dir = Path("/data/temp33/gov/data/process")

    # 创建增强版检索器
    retriever = create_enhanced_hybrid_retriever_from_files(
        data_dir,
        chunking_strategy='sentence',
        chunk_size=600,
        chunk_overlap=80
    )

    # 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
    ]

    print("\n" + "=" * 70)
    print("测试增强版混合检索")
    print("=" * 70)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 70}")
        print(f"测试 {i}: {query}")
        print(f"{'=' * 70}")

        # 执行检索
        results = retriever.retrieve(
            query,
            top_k_docs=10,
            top_k_chunks=3,
            enable_query_enhancement=True,
            enable_doc_type_boost=True
        )

        # 显示结果
        print(f"\n[最终结果] Top 3 chunks:")
        for j, chunk in enumerate(results[:3], 1):
            print(f"\n  [{j}] 文档: {chunk.get('full_title', 'N/A')}")
            print(f"      类型: {chunk.get('doc_type', 'N/A')}")
            print(f"      分数: {chunk.get('chunk_score', 0):.2f}")
            print(f"      内容: {chunk['text'][:100].replace(chr(10), ' ')}...")

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
