#!/usr/bin/env python3
"""
完整的文档切片策略演示和评测
包含：Token、Sentence、SentenceWindow、Semantic 四种策略
"""

import os
import sys

# UTF-8输出（Windows兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from llama_index.core import VectorStoreIndex, Settings, Document
from llama_index.core.node_parser import (
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
    TokenTextSplitter,
    SentenceSplitter
)
from llama_index.core.postprocessor import MetadataReplacementPostProcessor

# 导入 OpenAI LLM (用于 DashScope 兼容模式)
from llama_index.llms.openai import OpenAI
# 导入 DashScopeEmbedding
from llama_index.embeddings.dashscope import DashScopeEmbedding

# 获取 API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

print("="*70)
print("LlamaIndex 文档切片策略完整演示")
print("="*70)

# 初始化 LlamaIndex 全局设置
if DASHSCOPE_API_KEY:
    try:
        # 1. 配置 LLM (使用 DashScope 的 qwen-plus 模型)
        Settings.llm = OpenAI(
            model="qwen-plus",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=DASHSCOPE_API_KEY,
            temperature=0.1
        )

        # 2. 配置嵌入模型
        Settings.embed_model = DashScopeEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
        )

        print("✓ LLM和Embedding已配置")
        print(f"  LLM: qwen-plus")
        print(f"  Embedding: text-embedding-v2\n")
        llm_configured = True
    except Exception as e:
        print(f"⚠ 配置失败: {e}")
        print("  本演示将只显示切片效果，不执行查询\n")
        llm_configured = False
else:
    print("⚠ 未找到 DASHSCOPE_API_KEY")
    print("  本演示将只显示切片效果，不执行查询\n")
    llm_configured = False


def evaluate_splitter(splitter, documents, question, splitter_name,
                      enable_query=False):
    """
    评测不同文档切片方法的效果

    Args:
        splitter: 切片器实例
        documents: 文档列表
        question: 测试问题
        splitter_name: 切片器名称
        enable_query: 是否执行查询（需要配置LLM和Embedding）
    """
    print(f"\n{'='*70}")
    print(f"正在使用【{splitter_name}】方法进行测试")
    print(f"{'='*70}\n")

    # ===== 第一部分：显示切片效果 =====
    print(f"【{splitter_name}】生成的原始文档切片:")
    print("─"*70)

    raw_nodes = splitter.get_nodes_from_documents(documents)

    print(f"总共生成 {len(raw_nodes)} 个切片\n")

    for i, node in enumerate(raw_nodes, 1):
        content = node.get_content()
        content_len = len(content)

        # 计算token数
        from llama_index.core.utils import get_tokenizer
        tokenizer = get_tokenizer()
        token_count = len(tokenizer(content))

        print(f"【切片 {i}】({token_count} tokens, {content_len} 字符)")

        # 特殊处理 SentenceWindow
        if isinstance(splitter, SentenceWindowNodeParser):
            original_text = node.metadata.get("original_text", "N/A")
            window_context = node.metadata.get("window", "N/A")

            print(f"  核心句子: {original_text[:100]}...")
            if window_context != "N/A":
                print(f"  窗口上下文长度: {len(window_context)} 字符")
                print(f"  预览: {window_context[:150].replace(chr(10), ' ')}...")
        else:
            # 普通切片，显示内容预览
            preview = content[:150].replace('\n', ' ')
            print(f"  内容: {preview}...")

        print("  " + "─"*60)

    # ===== 第二部分：执行查询（可选）=====
    if enable_query and llm_configured:
        print(f"\n{'─'*70}")
        print("开始执行查询测试...")
        print(f"{'─'*70}\n")

        try:
            # 构建索引
            print("  正在构建向量索引...")
            nodes = splitter.get_nodes_from_documents(documents)
            index = VectorStoreIndex(nodes, embed_model=Settings.embed_model)

            # 创建查询引擎
            print("  正在创建查询引擎...")
            query_engine_params = {
                "similarity_top_k": 3,  # 返回前3个最相关的
            }

            # 如果是 Sentence Window 切片，添加后处理器
            if isinstance(splitter, SentenceWindowNodeParser):
                query_engine_params["node_postprocessors"] = [
                    MetadataReplacementPostProcessor(target_metadata_key="window")
                ]
                print("  💡 检测到 Sentence Window 切片，已添加后处理器")

            query_engine = index.as_query_engine(**query_engine_params)

            # 执行查询
            print(f"\n  测试问题: {question}")
            print("\n  【模型回答】")
            print("  " + "─"*60)

            response = query_engine.query(question)
            answer = str(response)

            # 打印答案（分段显示）
            for line in answer.split('\n'):
                print(f"  {line}")
            print("  " + "─"*60)

            # 输出召回的参考片段
            print(f"\n  【召回的参考片段】(Top 3):")
            if response.source_nodes:
                for i, node in enumerate(response.source_nodes, 1):
                    print(f"\n  --- 片段 {i} (相似度: {node.score:.4f}) ---")

                    # 优化后的打印逻辑
                    if isinstance(splitter, SentenceWindowNodeParser):
                        # Sentence Window: 打印窗口内容和核心句子
                        window_content = node.metadata.get("window", "N/A")
                        original_text = node.metadata.get("original_text", "N/A")

                        print(f"  核心句子: {original_text[:100]}...")
                        print(f"  窗口上下文: {window_content[:200].replace(chr(10), ' ')}...")
                    else:
                        # 其他切片器：直接打印内容
                        content = node.get_content()
                        print(f"  {content[:200].replace(chr(10), ' ')}...")

                    print("  " + "─"*60)
            else:
                print("  ⚠ 未召回任何文档片段")

        except Exception as e:
            print(f"  ✗ 查询失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{splitter_name} 测试完成")
    print(f"{'='*70}\n")


# --- 示例文档 ---
documents = [
    Document(
        text="""
        LlamaIndex 是一个用于构建 LLM 应用程序的数据框架。
        它提供了一套工具，可以帮助开发者将私有数据与大型语言模型（LLMs）连接起来，
        实现包括问答、检索增强生成（RAG）等功能。
        LlamaIndex 支持多种数据源，包括 PDF、数据库、API 等。
        其核心概念包括文档加载器、节点解析器、索引和查询引擎。

        文档加载器负责将各种格式和来源的数据摄取到 LlamaIndex 中。
        节点解析器随后将这些加载的文档分解成更小、更易于管理的单元，称为节点。
        这些节点通常是句子或段落，具体取决于解析策略。
        索引是构建在这些节点之上的数据结构，旨在实现高效存储和检索，
        通常涉及向量嵌入以进行语义搜索。
        最后，查询引擎促进了与索引数据的交互，允许用户提出问题
        并利用 LLM 和检索到的信息合成答案。

        --- 以下是与 LlamaIndex 主题不太直接相关的内容 ---

        此外，Python 作为一门通用编程语言，其简洁性和丰富的库生态使其在 AI 领域广受欢迎。
        例如，NumPy 和 Pandas 是数据处理的基础，它们提供了强大的工具用于数值操作和结构化数据。
        Scikit-learn 则提供了全面的机器学习算法套件，适用于分类、回归和聚类等任务。
        这些工具共同构成了数据科学家和 AI 从业者的强大工具箱，
        使他们能够高效地开发和部署复杂的 AI 模型。

        --- 以下是另一个相关但概念上独立的部分 ---

        句子窗口切片是一种高级的切片策略，它在每个切片中包含一个目标句子，
        并在其前后添加一定数量的"窗口"句子作为上下文。
        这种方法旨在检索时为 LLM 提供丰富的局部上下文，从而提高生成答案的连贯性。
        语义切片则尝试根据文本的语义内容来划分段落，
        而不是仅仅依靠固定的字符数或句子数量。
        它利用嵌入模型计算句子或短语之间的语义相似度，
        识别出主题或含义发生自然转变的断点。
        这两种高级方法都能有效提升 RAG 应用的召回和生成质量。
        选择正确的切片策略通常取决于数据的具体特征和预期的查询类型。
        """
    )
]

question = "LlamaIndex 的主要功能和核心概念是什么？以及两种高级切片策略的区别？"

print(f"\n📄 测试文档信息:")
print(f"  文档数量: {len(documents)}")
print(f"  文档长度: {len(documents[0].text)} 字符")
print(f"  测试问题: {question}\n")

# --- 开始测试不同的切片策略 ---

# ===========================================
# 1. Token 切片 - 小块无重叠
# ===========================================
print("\n" + "🔹"*35)
print("测试 1: Token 切片（小块，无重叠）")
print("🔹"*35)

token_splitter_small = TokenTextSplitter(
    chunk_size=30,
    chunk_overlap=0
)
evaluate_splitter(
    token_splitter_small,
    documents,
    question,
    "Token切片 (size=30, overlap=0)",
    enable_query=False  # Token切片效果差，不执行查询
)

# ===========================================
# 2. Token 切片 - 小块有重叠
# ===========================================
print("\n" + "🔹"*35)
print("测试 2: Token 切片（小块，有重叠）")
print("🔹"*35)

token_splitter_overlap = TokenTextSplitter(
    chunk_size=30,
    chunk_overlap=10
)
evaluate_splitter(
    token_splitter_overlap,
    documents,
    question,
    "Token切片 (size=30, overlap=10)",
    enable_query=False
)

# ===========================================
# 3. Sentence 切片 ⭐ 推荐
# ===========================================
print("\n" + "🔹"*35)
print("测试 3: Sentence 切片（句子边界）⭐ 推荐")
print("🔹"*35)

sentence_splitter = SentenceSplitter(
    chunk_size=200,      # tokens
    chunk_overlap=20
)
evaluate_splitter(
    sentence_splitter,
    documents,
    question,
    "Sentence切片 (size=200, overlap=20)",
    enable_query=llm_configured  # 如果配置了LLM，执行查询
)

# ===========================================
# 4. Sentence Window 切片
# ===========================================
print("\n" + "🔹"*35)
print("测试 4: Sentence Window 切片（带上下文窗口）")
print("🔹"*35)

sentence_window_splitter = SentenceWindowNodeParser(
    window_size=3,                      # 前后各3个句子
    window_metadata_key="window",
    original_text_metadata_key="original_text"
)
evaluate_splitter(
    sentence_window_splitter,
    documents,
    question,
    "SentenceWindow切片 (window=3)",
    enable_query=llm_configured
)

# ===========================================
# 5. Semantic 切片（需要embedding）
# ===========================================
if llm_configured:
    print("\n" + "🔹"*35)
    print("测试 5: Semantic 切片（语义边界）")
    print("🔹"*35)

    try:
        semantic_splitter = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=Settings.embed_model
        )
        evaluate_splitter(
            semantic_splitter,
            documents,
            question,
            "Semantic切片 (语义驱动)",
            enable_query=True
        )
    except Exception as e:
        print(f"⚠ Semantic切片测试失败: {e}\n")
else:
    print("\n⚠ 跳过 Semantic 切片测试（需要 DASHSCOPE_API_KEY）")

# ===========================================
# 总结
# ===========================================
print("\n" + "="*70)
print("📊 测试总结")
print("="*70)

print("""
【切片策略对比】

1. Token切片
   - 固定token数量切分
   - ❌ 会切断句子和单词
   - ❌ 不推荐用于中文文档
   - 适用: 代码文件（chunk_size较大时）

2. Sentence切片 ⭐ 推荐
   - 尊重句子边界
   - ✅ 语义完整性好
   - ✅ 基于token数量，更准确
   - 适用: 90%的文档场景

3. SentenceWindow切片
   - 保留上下文窗口
   - ✅ 检索时提供丰富上下文
   - ✅ 适合需要前后文的场景
   - 适用: 问答系统、长文档

4. Semantic切片
   - 根据语义相似度切分
   - ✅ 智能识别主题转换
   - ❌ 需要调用embedding API
   - 适用: 主题多样的文档

【推荐配置】

通用文档:
  SentenceSplitter(chunk_size=600, chunk_overlap=80)

问答系统:
  SentenceWindowNodeParser(window_size=3)

多主题文档:
  SemanticSplitterNodeParser(buffer_size=1)
""")

print("="*70)
print("✅ 所有测试完成！")
print("="*70)

if not llm_configured:
    print("\n💡 提示:")
    print("  设置 DASHSCOPE_API_KEY 环境变量可以启用查询测试")
    print("  export DASHSCOPE_API_KEY='your-api-key'")
