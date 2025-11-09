#!/usr/bin/env python3
"""
测试分级索引系统（文档-章-块）
测试文档嵌入、分级检索和问答召回效果
"""

import sys
import os
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)
from config import settings

# 清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if key in os.environ:
        del os.environ[key]

def print_header(title: str, char: str = "="):
    """打印标题"""
    width = 80
    print()
    print(char * width)
    print(f" {title}")
    print(char * width)
    print()

def print_section(title: str):
    """打印章节标题"""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}\n")

def build_hierarchical_index(data_dir: str, storage_dir: str, use_llm: bool = False):
    """构建分级索引"""
    print_header("步骤 1: 构建分级索引（文档-章-块）")

    # 查找所有 Markdown 文件
    print("🔍 查找 Markdown 文件...")
    md_files = list(Path(data_dir).rglob("*.md"))

    if not md_files:
        print(f"❌ 未找到 Markdown 文件: {data_dir}")
        return None

    print(f"✓ 找到 {len(md_files)} 个 Markdown 文件:\n")
    for i, file in enumerate(md_files, 1):
        print(f"  {i}. {file.name} ({file.stat().st_size / 1024:.1f} KB)")

    print_section("开始构建索引")

    # 配置嵌入模型
    embed_model_name = None
    if settings.embedding.backend == "dashscope":
        print(f"📦 使用 DashScope Embedding: {settings.embedding.dashscope_model}")
    elif settings.embedding.backend == "openai":
        print(f"📦 使用 OpenAI Embedding: {settings.embedding.openai_model}")
        embed_model_name = settings.embedding.openai_model

    # 构建索引
    builder = HierarchicalIndexBuilder(
        storage_dir=storage_dir,
        embed_model_name=embed_model_name
    )

    print("\n🚀 开始处理...")
    print(f"   - 提取文档层级结构")
    print(f"   - 生成章节摘要 {'(使用 LLM)' if use_llm else '(截取文本)'}")
    print(f"   - 创建三级索引: 文档 -> 章节 -> 块")
    print(f"   - 构建向量索引")
    print()

    stats = builder.build_from_markdown_files(
        [str(f) for f in md_files],
        use_llm=use_llm,
        enable_images=True
    )

    print_section("索引构建完成")
    print("📊 统计信息:")
    print(f"   - 文档数量: {stats['total_docs']}")
    print(f"   - 章节数量: {stats['total_sections']}")
    print(f"   - 文本块数量: {stats['total_chunks']}")
    print(f"   - 图片数量: {stats['total_images']}")
    print(f"   - 存储位置: {stats['storage_dir']}")

    return stats

def test_hierarchical_retrieval(storage_dir: str):
    """测试分级检索"""
    print_header("步骤 2: 测试分级检索（文档-章-块）")

    # 初始化检索器
    print("🔧 初始化分级检索器...")
    retriever = HierarchicalRetriever(
        storage_dir=storage_dir,
        use_rerank="dashscope",  # 使用 DashScope 重排
        enable_images=True
    )
    print("✓ 检索器初始化成功\n")

    # 测试查询
    test_queries = [
        "家电以旧换新补贴标准是什么？",
        "手机购新补贴的申请条件和金额",
        "汽车消费券有哪些档位？",
        "数码产品的补贴政策"
    ]

    retrieval_modes = ["hybrid", "hierarchical", "direct"]

    for query in test_queries:
        print_section(f"查询: {query}")

        for mode in retrieval_modes:
            print(f"\n  【{mode.upper()} 检索模式】")

            try:
                nodes = retriever.retrieve(
                    query=query,
                    top_k=5,
                    use_rerank=True,
                    retrieval_mode=mode
                )

                print(f"  ✓ 检索到 {len(nodes)} 个结果\n")

                for i, node in enumerate(nodes, 1):
                    node_type = node.metadata.get('type', 'unknown')
                    level = node.metadata.get('level', 'N/A')
                    path = node.metadata.get('path', 'N/A')
                    title = node.metadata.get('title', 'N/A')

                    print(f"    [{i}] 类型: {node_type} (Level {level})")
                    print(f"        路径: {path}")
                    print(f"        标题: {title}")
                    print(f"        内容: {node.text[:120]}...")
                    print()

            except Exception as e:
                print(f"  ❌ 检索失败: {e}\n")

    return retriever

def test_qa_recall(storage_dir: str):
    """测试问答召回效果"""
    print_header("步骤 3: 测试问答召回效果")

    # 初始化检索器和 LLM
    print("🔧 初始化检索器和 LLM...")
    retriever = HierarchicalRetriever(
        storage_dir=storage_dir,
        use_rerank="dashscope",
        enable_images=True
    )

    from openai import OpenAI
    llm_client = OpenAI(
        api_key=settings.model.llm_api_key,
        base_url=settings.model.llm_base_url
    )

    print(f"✓ LLM: {settings.model.llm_model_name}\n")

    # 测试问题
    test_questions = [
        {
            "question": "济南市家电以旧换新的补贴标准是多少？",
            "expected_keywords": ["补贴", "家电", "以旧换新", "标准"]
        },
        {
            "question": "购买手机可以享受多少补贴？需要什么条件？",
            "expected_keywords": ["手机", "补贴", "条件", "购新"]
        },
        {
            "question": "汽车消费券有哪些档位？每个档位能领多少钱？",
            "expected_keywords": ["汽车", "消费券", "档位"]
        }
    ]

    for i, item in enumerate(test_questions, 1):
        question = item["question"]
        expected_keywords = item["expected_keywords"]

        print_section(f"问题 {i}: {question}")

        # Step 1: 分级检索
        print("🔍 执行分级检索...")

        nodes = retriever.retrieve(
            query=question,
            top_k=5,
            use_rerank=True,
            retrieval_mode="hybrid"
        )

        print(f"✓ 检索到 {len(nodes)} 个相关节点\n")

        # 分析召回结果
        print("📊 召回分析:")
        node_types = {}
        for node in nodes:
            node_type = node.metadata.get('type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1

        for node_type, count in node_types.items():
            print(f"   - {node_type}: {count} 个")

        print("\n📄 检索结果详情:")
        contexts = []
        for j, node in enumerate(nodes, 1):
            node_type = node.metadata.get('type', 'unknown')
            path = node.metadata.get('path', 'N/A')

            contexts.append(node.text)

            print(f"\n   [{j}] 类型: {node_type}")
            print(f"       路径: {path}")
            print(f"       内容: {node.text[:150]}...")

            # 检查是否包含预期关键词
            matched_keywords = [kw for kw in expected_keywords if kw in node.text]
            if matched_keywords:
                print(f"       ✓ 匹配关键词: {', '.join(matched_keywords)}")

        # Step 2: LLM 生成回答
        print("\n\n💭 生成回答...")

        context_text = "\n\n---\n\n".join(contexts)

        prompt = f"""你是一个政策咨询助手，专门解答济南市的消费补贴政策问题。

请根据以下政策文档内容回答用户的问题。要求：
1. 回答要准确、具体，直接引用政策原文的数字和条件
2. 如果有多个档位或标准，请分条列出
3. 如果文档中没有相关信息，请明确说明
4. 保持简洁专业的语气

政策文档内容：
{context_text}

用户问题：{question}

回答："""

        try:
            response = llm_client.chat.completions.create(
                model=settings.model.llm_model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的政策咨询助手，擅长解答消费补贴政策问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )

            answer = response.choices[0].message.content

            print("=" * 80)
            print(" 📝 LLM 回答")
            print("=" * 80)
            print()
            print(answer)
            print()

            # 评估回答质量
            print("📈 回答评估:")
            matched_in_answer = [kw for kw in expected_keywords if kw in answer]
            print(f"   - 包含预期关键词: {len(matched_in_answer)}/{len(expected_keywords)}")
            print(f"   - 关键词: {', '.join(matched_in_answer) if matched_in_answer else '无'}")
            print(f"   - 回答长度: {len(answer)} 字符")

        except Exception as e:
            print(f"❌ LLM 回答失败: {e}")

        print()

def main():
    """主函数"""
    print_header("分级索引系统测试", "=")

    print("📋 配置信息:")
    print(f"   - 数据目录: /data/temp33/gov/data/process")
    print(f"   - 存储目录: /data/temp33/gov/storage/hierarchical")
    print(f"   - Embedding: {settings.embedding.backend}")
    print(f"   - LLM: {settings.model.llm_model_name}")
    print(f"   - Reranker: DashScope")

    data_dir = "/data/temp33/gov/data/process"
    storage_dir = "/data/temp33/gov/storage/hierarchical"

    # 检查数据目录
    if not Path(data_dir).exists():
        print(f"\n❌ 数据目录不存在: {data_dir}")
        return

    # 询问是否重新构建索引
    print("\n" + "=" * 80)
    rebuild = input("是否重新构建索引？[y/N]: ").strip().lower()

    if rebuild == 'y':
        # 步骤 1: 构建索引
        stats = build_hierarchical_index(
            data_dir=data_dir,
            storage_dir=storage_dir,
            use_llm=False  # 不使用 LLM 生成摘要（更快）
        )

        if stats is None:
            print("\n❌ 索引构建失败")
            return
    else:
        print("\n✓ 使用现有索引")

    # 步骤 2: 测试分级检索
    retriever = test_hierarchical_retrieval(storage_dir)

    # 步骤 3: 测试问答召回
    test_qa_recall(storage_dir)

    print_header("测试完成", "=")
    print("✓ 所有测试完成！")
    print("\n📝 总结:")
    print("   1. 分级索引（文档-章-块）已构建")
    print("   2. 三种检索模式测试完成: hybrid, hierarchical, direct")
    print("   3. 问答召回效果已验证")
    print()

if __name__ == "__main__":
    main()
