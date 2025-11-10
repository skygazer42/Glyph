#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker环境功能测试脚本
测试文本嵌入和问答召回功能
"""

import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# 首先设置环境变量（在导入其他模块之前）
os.environ["EMBEDDING_DIM"] = "1024"
os.environ["EMBEDDING_DASHSCOPE_DIMENSION"] = "1024"

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.knowledge.milvus import MilvusStore

# 加载环境变量
load_dotenv(override=True)

# 定义简化的文档类型（避免导入整个agents模块）
@dataclass
class SimpleDocument:
    """简化的文档类型用于测试"""
    id: str
    title: str
    content: str
    source: str = ""
    doc_type: str = ""
    keywords: List[str] = None
    regions: List[str] = None
    target_groups: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.regions is None:
            self.regions = []
        if self.target_groups is None:
            self.target_groups = []

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def test_milvus_connection():
    """测试 Milvus 连接"""
    print_section("1. 测试 Milvus 连接")

    try:
        client = MilvusStore(
            host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
            port=int(os.getenv("DATABASE__MILVUS_PORT", "19530")),
            collection_name="test_collection_docker",
            backend=os.getenv("EMBEDDING_BACKEND", "dashscope"),
        )

        print("✓ Milvus 连接成功")
        print(f"  - Host: {os.getenv('DATABASE__MILVUS_HOST', 'localhost')}")
        print(f"  - Port: {os.getenv('DATABASE__MILVUS_PORT', '19530')}")
        print(f"  - Collection: test_collection_docker")
        print(f"  - Backend: {client.backend}")
        print(f"  - Model: {client.model_name}")
        print(f"  - Embedding Dim: {client.embedding_dim}")

        return client

    except Exception as e:
        print(f"✗ Milvus 连接失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_text_embedding(client):
    """测试文本嵌入功能"""
    print_section("2. 测试文本嵌入到知识库")

    if not client:
        print("✗ 跳过测试（Milvus客户端未初始化）")
        return False

    try:
        # 创建测试文档
        test_docs = [
            SimpleDocument(
                id="test_doc_1",
                title="人工智能简介",
                content="人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。",
                source="test_source_1",
                doc_type="AI",
                keywords=["人工智能", "计算机科学"],
                regions=["全国"],
                target_groups=["研究人员"]
            ),
            SimpleDocument(
                id="test_doc_2",
                title="深度学习应用",
                content="深度学习是机器学习的一个子集，它使用多层神经网络来学习数据的表示。深度学习在图像识别、语音识别等领域取得了巨大成功。",
                source="test_source_2",
                doc_type="AI",
                keywords=["深度学习", "神经网络"],
                regions=["全国"],
                target_groups=["工程师"]
            ),
            SimpleDocument(
                id="test_doc_3",
                title="自然语言处理",
                content="自然语言处理（NLP）是人工智能的一个重要分支，旨在让计算机能够理解、解释和生成人类语言。",
                source="test_source_3",
                doc_type="NLP",
                keywords=["自然语言处理", "NLP"],
                regions=["全国"],
                target_groups=["研究人员"]
            ),
            SimpleDocument(
                id="test_doc_4",
                title="向量数据库技术",
                content="向量数据库是一种专门用于存储和检索高维向量的数据库系统，广泛应用于相似性搜索和推荐系统。",
                source="test_source_4",
                doc_type="Database",
                keywords=["向量数据库", "相似性搜索"],
                regions=["全国"],
                target_groups=["开发者"]
            )
        ]

        print(f"准备插入 {len(test_docs)} 条测试文档...")

        # 插入文档
        client.add_documents(test_docs)

        print(f"✓ 成功插入 {len(test_docs)} 条文档")

        # 等待索引完成
        time.sleep(3)

        # 验证插入
        stats = client.collection.num_entities
        print(f"  - 集合中总文档数: {stats}")

        return True

    except Exception as e:
        print(f"✗ 文本嵌入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_qa_retrieval(client):
    """测试问答召回功能"""
    print_section("3. 测试问答召回")

    if not client:
        print("✗ 跳过测试（Milvus客户端未初始化）")
        return False

    try:
        # 测试查询
        test_queries = [
            "什么是人工智能？",
            "深度学习有什么应用？",
            "向量数据库的用途是什么？"
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n查询 {i}: {query}")
            print("-" * 60)

            # 执行检索
            documents, scores = client.search(query, top_k=2, threshold=0.0)

            if documents:
                print(f"✓ 检索到 {len(documents)} 条结果:")
                for j, (doc, score) in enumerate(zip(documents, scores), 1):
                    print(f"\n  结果 {j}:")
                    print(f"    相似度分数: {score:.4f}")
                    print(f"    标题: {doc.title}")
                    print(f"    内容: {doc.content[:100]}...")
                    print(f"    类型: {doc.doc_type}")
            else:
                print("  ✗ 未检索到结果")

        print("\n✓ 问答召回测试完成")
        return True

    except Exception as e:
        print(f"✗ 问答召回失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_advanced_search(client):
    """测试高级搜索功能"""
    print_section("4. 测试高级搜索（带过滤）")

    if not client:
        print("✗ 跳过测试（Milvus客户端未初始化）")
        return False

    try:
        query = "人工智能技术"
        print(f"查询: {query}")
        print(f"过滤条件: doc_type == 'AI'")
        print("-" * 60)

        # 使用元数据过滤
        documents, scores = client.search(
            query,
            top_k=3,
            threshold=0.0,
            filters={"doc_type": "AI"}
        )

        if documents:
            print(f"✓ 检索到 {len(documents)} 条符合条件的结果:")
            for i, (doc, score) in enumerate(zip(documents, scores), 1):
                print(f"\n  结果 {i}:")
                print(f"    相似度分数: {score:.4f}")
                print(f"    标题: {doc.title}")
                print(f"    类型: {doc.doc_type}")
                print(f"    内容: {doc.content[:80]}...")
        else:
            print("  ✗ 未检索到结果")

        return True

    except Exception as e:
        print(f"✗ 高级搜索失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def cleanup(client):
    """清理测试数据"""
    print_section("5. 清理测试环境")

    if client:
        try:
            # 删除测试集合
            from pymilvus import utility, connections

            # 确保连接
            if not connections.has_connection("default"):
                connections.connect(
                    alias="default",
                    host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
                    port=os.getenv("DATABASE__MILVUS_PORT", "19530")
                )

            if utility.has_collection("test_collection_docker"):
                utility.drop_collection("test_collection_docker")
                print("✓ 已删除测试集合: test_collection_docker")

        except Exception as e:
            print(f"⚠ 清理警告: {str(e)}")

def main():
    """主测试流程"""
    print("\n" + "=" * 80)
    print("  Docker 环境功能测试")
    print("  测试时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)

    # 检查配置
    print("\n配置信息:")
    print(f"  - Embedding Backend: {os.getenv('EMBEDDING_BACKEND', 'N/A')}")
    print(f"  - Embedding Model: {os.getenv('EMBEDDING_DASHSCOPE_MODEL', 'N/A')}")
    print(f"  - Milvus Host: {os.getenv('DATABASE__MILVUS_HOST', 'localhost')}")
    print(f"  - Milvus Port: {os.getenv('DATABASE__MILVUS_PORT', '19530')}")

    client = None
    success_count = 0
    total_tests = 4

    try:
        # 测试1: Milvus连接
        client = test_milvus_connection()
        if client:
            success_count += 1

        # 测试2: 文本嵌入
        if test_text_embedding(client):
            success_count += 1

        # 测试3: 问答召回
        if test_qa_retrieval(client):
            success_count += 1

        # 测试4: 高级搜索
        if test_advanced_search(client):
            success_count += 1

    finally:
        # 清理
        cleanup(client)

    # 测试总结
    print_section("测试总结")
    print(f"总测试数: {total_tests}")
    print(f"成功: {success_count}")
    print(f"失败: {total_tests - success_count}")
    print(f"成功率: {success_count/total_tests*100:.1f}%")

    if success_count == total_tests:
        print("\n✓ 所有测试通过！Docker环境功能正常。")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查配置和服务状态。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
