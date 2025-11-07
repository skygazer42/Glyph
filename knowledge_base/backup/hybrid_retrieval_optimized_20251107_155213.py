#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的混合检索策略：文档级召回 + 块级检索
改进版：增强元数据保留和评估逻辑
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import re


def create_optimized_hybrid_retriever_from_files(
    data_dir: Path,
    chunking_strategy: str = 'sentence',
    chunk_size: int = 600,
    chunk_overlap: int = 80
):
    """
    从Markdown文件创建优化的HybridRetriever（带完整元数据）

    Args:
        data_dir: 数据目录
        chunking_strategy: 切块策略
        chunk_size: chunk大小
        chunk_overlap: chunk重叠

    Returns:
        HybridRetriever实例
    """
    from knowledge_base.hierarchical_index import (
        HierarchicalMarkdownProcessor,
        ChunkConfig
    )
    from knowledge_base.hybrid_retrieval import HybridRetriever

    print(f"\n[创建优化版HybridRetriever]")
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

            # 确定文档类型（关键改进！）
            file_path_str = str(md_file)
            if "家电" in file_path_str or "数码" in file_path_str or "家电" in title:
                doc_type = "家电数码政策"
            elif "汽车" in file_path_str or "新车" in file_path_str or "汽车" in title:
                doc_type = "汽车消费政策"
            elif "消费券" in title or "泉城购" in title or "消费活动" in title:
                doc_type = "消费活动政策"
            else:
                doc_type = "消费活动政策"  # 默认类型

            documents.append({
                'text': content,
                'title': title,
                'file': md_file.name,
                'doc_id': md_file.stem,
                'doc_type': doc_type,  # 保留文档类型！
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

        # 提取所有chunks（保留文档元数据！）
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
                        # 关键改进：添加文档级元数据到每个chunk
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
                            # 关键改进：添加文档级元数据到每个chunk
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
    retriever = HybridRetriever(documents, chunked_documents)

    print(f"\n✓ 优化版HybridRetriever创建完成")
    return retriever


if __name__ == "__main__":
    """测试优化版混合检索"""

    data_dir = Path("/data/temp33/gov/data/process")

    # 创建优化版检索器
    retriever = create_optimized_hybrid_retriever_from_files(
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
    print("测试优化版混合检索")
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
            chunk_strategy='bm25'
        )

        # 显示结果元数据
        print(f"\n[结果详情] Top 3 chunks:")
        for j, chunk in enumerate(results[:3], 1):
            print(f"\n  [{j}] 文档: {chunk.get('doc_title', 'N/A')}")
            print(f"      类型: {chunk.get('doc_type', 'N/A')}")
            print(f"      Section: {chunk.get('section', 'N/A')}")
            print(f"      分数: {chunk.get('chunk_score', 0):.2f}")
            print(f"      内容: {chunk['text'][:100].replace(chr(10), ' ')}...")

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
