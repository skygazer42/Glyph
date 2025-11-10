"""
简化的知识库测试脚本 - 直接测试,避免复杂导入
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time
from dataclasses import dataclass
from dotenv import load_dotenv
import numpy as np

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(str(Path(__file__).parent))


@dataclass
class SimpleDocument:
    """简单文档类"""
    id: str
    title: str
    content: str
    source: str
    doc_type: str


def load_markdown_files(data_dir: Path) -> List[SimpleDocument]:
    """加载所有 Markdown 文件"""
    documents = []
    md_files = list(data_dir.glob("**/*.md"))

    print(f"找到 {len(md_files)} 个文档文件\n")

    for md_file in md_files:
        try:
            # 读取文档内容
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 从文件路径提取文档信息
            relative_path = md_file.relative_to(data_dir)
            doc_id = str(relative_path).replace("\\", "/")
            title = md_file.stem

            doc = SimpleDocument(
                id=doc_id,
                title=title,
                content=content,
                source=str(md_file),
                doc_type="policy"
            )

            documents.append(doc)
            print(f"[OK] 加载: {title[:50]}... ({len(content)} 字符)")

        except Exception as e:
            print(f"[FAIL] 加载失败 {md_file.name}: {e}")

    return documents


def test_milvus_connection():
    """测试 Milvus 连接"""
    from pymilvus import connections, utility

    host = os.getenv("DATABASE__MILVUS_HOST", "localhost")
    port = int(os.getenv("DATABASE__MILVUS_PORT", "19530"))

    print(f"\n尝试连接 Milvus: {host}:{port}")

    try:
        connections.connect(
            alias="test",
            host=host,
            port=str(port)
        )
        print("[OK] Milvus 连接成功")

        # 列出所有集合
        collections = utility.list_collections(using="test")
        print(f"[OK] 现有集合: {collections}")

        connections.disconnect("test")
        return True

    except Exception as e:
        print(f"[FAIL] Milvus 连接失败: {e}")
        try:
            connections.disconnect("test")
        except:
            pass
        return False


def test_dashscope_embedding():
    """测试 DashScope Embedding API"""
    import requests

    api_key = os.getenv("EMBEDDING_DASHSCOPE_API_KEY")
    model = os.getenv("EMBEDDING_DASHSCOPE_MODEL", "text-embedding-v3")
    dimension = int(os.getenv("EMBEDDING_DASHSCOPE_DIMENSION", "1024"))

    print(f"\n测试 DashScope Embedding API")
    print(f"  Model: {model}")
    print(f"  Dimension: {dimension}")

    if not api_key:
        print("[FAIL] 未找到 EMBEDDING_DASHSCOPE_API_KEY")
        return False

    url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    test_text = "这是一个测试文本"
    data = {
        "model": model,
        "input": {"texts": [test_text]},
        "parameters": {"dimension": dimension}
    }

    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=30)
        elapsed = time.time() - start_time

        response.raise_for_status()
        result = response.json()

        if "output" in result and "embeddings" in result["output"]:
            embedding = result["output"]["embeddings"][0]["embedding"]
            print(f"[OK] Embedding 生成成功")
            print(f"  向量维度: {len(embedding)}")
            print(f"  耗时: {elapsed:.3f}s")
            print(f"  向量前5个值: {embedding[:5]}")
            return True
        else:
            print(f"[FAIL] 响应格式异常: {result}")
            return False

    except Exception as e:
        print(f"[FAIL] Embedding 生成失败: {e}")
        return False


def test_full_pipeline():
    """测试完整的知识库流程"""
    print("\n" + "="*60)
    print("完整流程测试")
    print("="*60)

    # 导入知识库模块
    try:
        from app.knowledge.milvus import MilvusStore
        print("[OK] 成功导入 MilvusStore")
    except Exception as e:
        print(f"[FAIL] 导入失败: {e}")
        return False

    # 创建 MilvusStore 实例
    try:
        print("\n连接到知识库...")
        store = MilvusStore()
        stats = store.get_stats()
        print(f"[OK] 知识库连接成功")
        print(f"  Collection: {stats['collection_name']}")
        print(f"  Backend: {stats['backend']}")
        print(f"  Model: {stats['model']}")
        print(f"  Dimension: {stats['dim']}")
        print(f"  Total Documents: {stats['total_documents']}")
    except Exception as e:
        print(f"[FAIL] 知识库连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 加载文档
    data_dir = Path("data/process")
    documents = load_markdown_files(data_dir)

    if not documents:
        print("[FAIL] 没有加载到文档")
        return False

    # 转换为 PolicyDocument
    try:
        from app.agents.base.types import PolicyDocument

        policy_docs = []
        for doc in documents:
            policy_doc = PolicyDocument(
                id=doc.id,
                title=doc.title,
                content=doc.content,
                source=doc.source,
                doc_type=doc.doc_type
            )
            policy_docs.append(policy_doc)

        print(f"\n准备嵌入 {len(policy_docs)} 个文档...")

    except ImportError as e:
        print(f"[FAIL] 无法导入 PolicyDocument: {e}")
        print("尝试使用简单字典...")

        # 使用字典作为替代
        policy_docs = []
        for doc in documents:
            policy_doc = type('PolicyDocument', (), {
                'id': doc.id,
                'title': doc.title,
                'content': doc.content,
                'source': doc.source,
                'doc_type': doc.doc_type
            })()
            policy_docs.append(policy_doc)

    # 嵌入文档
    try:
        print("开始嵌入文档...")
        start_time = time.time()
        store.add_documents(policy_docs)
        elapsed = time.time() - start_time

        print(f"[OK] 文档嵌入成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  平均: {elapsed/len(policy_docs):.2f}s/文档")

        # 更新统计
        stats = store.get_stats()
        print(f"  数据库总文档数: {stats['total_documents']}")

    except Exception as e:
        print(f"[FAIL] 文档嵌入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试搜索
    test_queries = [
        "济南市手机购新补贴的标准是什么?",
        "家电以旧换新需要哪些条件?",
        "山东省智能手表购新补贴政策",
        "平板电脑的补贴金额是多少?",
    ]

    print("\n" + "="*60)
    print("测试知识库召回")
    print("="*60)

    for i, query in enumerate(test_queries, 1):
        print(f"\n测试 {i}/{len(test_queries)}: {query}")
        print("-" * 60)

        try:
            start_time = time.time()
            results, scores = store.search(
                query=query,
                top_k=3,
                threshold=0.3
            )
            elapsed = time.time() - start_time

            print(f"[OK] 搜索完成 (耗时: {elapsed:.3f}s)")
            print(f"  找到 {len(results)} 个相关文档")

            for j, (doc, score) in enumerate(zip(results, scores), 1):
                print(f"\n  [{j}] 相似度: {score:.4f}")
                print(f"      标题: {doc.title[:60]}...")
                content_preview = doc.content[:100].replace('\n', ' ')
                print(f"      内容: {content_preview}...")

        except Exception as e:
            print(f"[FAIL] 搜索失败: {e}")
            import traceback
            traceback.print_exc()

    return True


def main():
    """主测试函数"""
    print("="*60)
    print("知识库功能测试")
    print("="*60)

    # 测试 1: Milvus 连接
    print("\n[测试 1] Milvus 连接测试")
    print("-" * 60)
    if not test_milvus_connection():
        print("\n[WARNING] Milvus 连接失败,请检查 Docker 服务是否运行")
        return

    # 测试 2: Embedding API
    print("\n[测试 2] Embedding API 测试")
    print("-" * 60)
    if not test_dashscope_embedding():
        print("\n[WARNING] Embedding API 测试失败,请检查 API Key")
        return

    # 测试 3: 完整流程
    print("\n[测试 3] 完整知识库流程测试")
    print("-" * 60)
    test_full_pipeline()

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
