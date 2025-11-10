"""
测试知识库召回功能

测试流程:
1. 连接 Milvus 数据库
2. 加载 data/process 目录下的文档
3. 将文档嵌入到向量库
4. 执行多个测试查询
5. 评估召回质量
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import json
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.knowledge.milvus import MilvusStore
from app.agents.base.types import PolicyDocument
from app.agents.dsl_generator.document_parser import DocumentParser


class KnowledgeBaseTest:
    """知识库测试类"""

    def __init__(self):
        """初始化测试"""
        self.store = None
        self.parser = DocumentParser()
        self.data_dir = Path("data/process")
        self.test_queries = [
            "济南市手机购新补贴的标准是什么?",
            "家电以旧换新需要哪些条件?",
            "山东省智能手表购新补贴政策",
            "汽车消费补贴活动的时间和地点",
            "平板电脑的补贴金额是多少?",
            "以旧换新的申请流程",
            "哪些家电可以参加以旧换新?",
            "购新补贴的发放方式",
        ]

    def connect_to_milvus(self):
        """连接到 Milvus"""
        print("\n" + "="*60)
        print("步骤 1: 连接到 Milvus 数据库")
        print("="*60)

        try:
            self.store = MilvusStore()
            stats = self.store.get_stats()
            print(f"✓ 成功连接到 Milvus")
            print(f"  - Host: {stats['host']}:{stats['port']}")
            print(f"  - Collection: {stats['collection_name']}")
            print(f"  - Backend: {stats['backend']}")
            print(f"  - Model: {stats['model']}")
            print(f"  - Dimension: {stats['dim']}")
            print(f"  - Total Documents: {stats['total_documents']}")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False

    def load_documents(self) -> List[PolicyDocument]:
        """加载所有文档"""
        print("\n" + "="*60)
        print("步骤 2: 加载文档")
        print("="*60)

        documents = []
        md_files = list(self.data_dir.glob("**/*.md"))

        print(f"找到 {len(md_files)} 个文档文件\n")

        for md_file in md_files:
            try:
                # 读取文档内容
                content = self.parser.parse(str(md_file))

                # 从文件路径提取文档信息
                relative_path = md_file.relative_to(self.data_dir)
                doc_id = str(relative_path).replace("\\", "/")
                title = md_file.stem

                # 创建 PolicyDocument
                doc = PolicyDocument(
                    id=doc_id,
                    title=title,
                    content=content,
                    source=str(md_file),
                    doc_type="policy"
                )

                documents.append(doc)
                print(f"✓ 加载: {title[:50]}... ({len(content)} 字符)")

            except Exception as e:
                print(f"✗ 加载失败 {md_file.name}: {e}")

        print(f"\n总共成功加载 {len(documents)} 个文档")
        return documents

    def embed_documents(self, documents: List[PolicyDocument]):
        """将文档嵌入到向量库"""
        print("\n" + "="*60)
        print("步骤 3: 嵌入文档到向量库")
        print("="*60)

        if not documents:
            print("没有文档需要嵌入")
            return

        try:
            print(f"开始嵌入 {len(documents)} 个文档...")
            start_time = time.time()

            self.store.add_documents(documents)

            elapsed = time.time() - start_time
            print(f"✓ 成功嵌入所有文档")
            print(f"  - 耗时: {elapsed:.2f} 秒")
            print(f"  - 平均: {elapsed/len(documents):.2f} 秒/文档")

            # 获取更新后的统计信息
            stats = self.store.get_stats()
            print(f"  - 数据库总文档数: {stats['total_documents']}")

        except Exception as e:
            print(f"✗ 嵌入失败: {e}")
            raise

    def test_search(self):
        """测试搜索功能"""
        print("\n" + "="*60)
        print("步骤 4: 测试知识库召回")
        print("="*60)

        results_summary = []

        for i, query in enumerate(self.test_queries, 1):
            print(f"\n测试 {i}/{len(self.test_queries)}: {query}")
            print("-" * 60)

            try:
                start_time = time.time()
                documents, scores = self.store.search(
                    query=query,
                    top_k=5,
                    threshold=0.3  # 降低阈值以便看到更多结果
                )
                elapsed = time.time() - start_time

                print(f"✓ 搜索完成 (耗时: {elapsed:.3f}s)")
                print(f"  找到 {len(documents)} 个相关文档:")

                if not documents:
                    print("  ⚠ 没有找到相关文档")
                    results_summary.append({
                        "query": query,
                        "num_results": 0,
                        "top_score": 0.0,
                        "elapsed": elapsed
                    })
                    continue

                for j, (doc, score) in enumerate(zip(documents, scores), 1):
                    print(f"\n  [{j}] 相似度: {score:.4f}")
                    print(f"      标题: {doc.title[:60]}...")
                    print(f"      来源: {Path(doc.source).name}")
                    print(f"      内容预览: {doc.content[:100]}...")

                results_summary.append({
                    "query": query,
                    "num_results": len(documents),
                    "top_score": float(scores[0]) if scores else 0.0,
                    "avg_score": float(sum(scores) / len(scores)) if scores else 0.0,
                    "elapsed": elapsed
                })

            except Exception as e:
                print(f"✗ 搜索失败: {e}")
                results_summary.append({
                    "query": query,
                    "error": str(e),
                    "num_results": 0
                })

        return results_summary

    def print_summary(self, results: List[Dict[str, Any]]):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)

        successful_queries = [r for r in results if "error" not in r]
        failed_queries = [r for r in results if "error" in r]
        queries_with_results = [r for r in successful_queries if r["num_results"] > 0]

        print(f"\n总查询数: {len(results)}")
        print(f"成功查询: {len(successful_queries)}")
        print(f"失败查询: {len(failed_queries)}")
        print(f"有结果查询: {len(queries_with_results)}")
        print(f"召回率: {len(queries_with_results)/len(results)*100:.1f}%")

        if queries_with_results:
            avg_results = sum(r["num_results"] for r in queries_with_results) / len(queries_with_results)
            avg_score = sum(r["top_score"] for r in queries_with_results) / len(queries_with_results)
            avg_elapsed = sum(r["elapsed"] for r in successful_queries) / len(successful_queries)

            print(f"\n性能指标:")
            print(f"  - 平均结果数: {avg_results:.1f}")
            print(f"  - 平均最高分: {avg_score:.4f}")
            print(f"  - 平均查询时间: {avg_elapsed:.3f}s")

        if failed_queries:
            print(f"\n失败的查询:")
            for r in failed_queries:
                print(f"  - {r['query']}: {r['error']}")

        # 按相似度排序展示最佳匹配
        if queries_with_results:
            print(f"\n最佳匹配 (Top 3):")
            sorted_results = sorted(queries_with_results, key=lambda x: x["top_score"], reverse=True)[:3]
            for i, r in enumerate(sorted_results, 1):
                print(f"  {i}. {r['query']}")
                print(f"     相似度: {r['top_score']:.4f}, 结果数: {r['num_results']}")

    def run(self, skip_embedding: bool = False):
        """运行完整测试"""
        print("\n" + "="*60)
        print("知识库召回测试")
        print("="*60)

        # 连接数据库
        if not self.connect_to_milvus():
            return

        # 如果数据库为空或不跳过嵌入,则加载并嵌入文档
        stats = self.store.get_stats()
        if not skip_embedding or stats['total_documents'] == 0:
            documents = self.load_documents()
            if documents:
                self.embed_documents(documents)
        else:
            print(f"\n跳过文档嵌入,使用现有的 {stats['total_documents']} 个文档")

        # 测试搜索
        results = self.test_search()

        # 打印总结
        self.print_summary(results)

        print("\n" + "="*60)
        print("测试完成!")
        print("="*60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试知识库召回功能")
    parser.add_argument("--skip-embedding", action="store_true",
                        help="跳过文档嵌入步骤,使用现有数据")

    args = parser.parse_args()

    test = KnowledgeBaseTest()
    test.run(skip_embedding=args.skip_embedding)
