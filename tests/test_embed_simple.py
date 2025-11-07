#!/usr/bin/env python3
"""简化的文档嵌入和检索测试"""

import sys
import os
from pathlib import Path

# 清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if key in os.environ:
        del os.environ[key]

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置UTF-8输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from config.settings import settings
from knowledge_base.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever
)

# 配置LlamaIndex使用DashScope embedding
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding

Settings.embed_model = OpenAIEmbedding(
    model=settings.embedding.dashscope_model,
    api_key=settings.embedding.dashscope_api_key,
    api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def main():
    print("="*60)
    print("文档嵌入和检索测试")
    print("="*60)

    # 数据目录
    data_dir = "F:/pythonproject/gov/data/process"
    storage_dir = "./storage/policy_index"

    print("\n[1] 查找Markdown文件...")
    data_path = Path(data_dir)
    md_files = list(data_path.rglob("*.md"))
    print(f"   找到 {len(md_files)} 个文件")
    for i, f in enumerate(md_files[:5], 1):
        print(f"   {i}. {f.name}")

    if not md_files:
        print("错误: 没有找到Markdown文件")
        return 1

    print("\n[2] 初始化索引构建器...")
    builder = HierarchicalIndexBuilder(
        storage_dir=storage_dir,
        embed_model_name=None
    )
    print("   完成")

    print("\n[3] 构建分级索引...")
    print("   注意: 这可能需要几分钟时间")
    stats = builder.build_from_markdown_files(
        [str(f) for f in md_files],
        use_llm=True,
        enable_images=True
    )

    print("\n[4] 索引统计:")
    print(f"   - 文档数: {stats['total_docs']}")
    print(f"   - 章节数: {stats['total_sections']}")
    print(f"   - 块数: {stats['total_chunks']}")
    print(f"   - 图片数: {stats['total_images']}")

    print("\n[5] 验证多级索引结构...")
    print("   加载检索器...")
    retriever = HierarchicalRetriever(
        storage_dir=storage_dir,
        use_rerank="dashscope",
        enable_images=True
    )
    print("   完成")

    print("\n[6] 测试检索...")
    test_queries = [
        "家电补贴申请条件",
        "手机以旧换新政策",
        "汽车消费券"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n   查询{i}: {query}")
        try:
            results = retriever.retrieve(
                query=query,
                top_k=3,
                use_rerank=True,
                retrieval_mode="hybrid"
            )

            print(f"   返回 {len(results)} 个结果")
            for j, node in enumerate(results, 1):
                node_type = node.metadata.get('type', 'unknown')
                title = node.metadata.get('title', '无标题')
                text_preview = node.text[:80].replace('\n', ' ')
                print(f"   [{j}] 类型={node_type}, 标题={title}")
                print(f"       内容预览: {text_preview}...")
                print(f"       节点ID: {node.id_}")
        except Exception as e:
            print(f"   错误: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
