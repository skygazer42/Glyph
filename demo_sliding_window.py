#!/usr/bin/env python3
"""
演示句子级别的滑动窗口切片（Sentence Sliding Window）
展示 chunk_size 和 chunk_overlap 的工作原理
"""

import os
import sys

# UTF-8输出（Windows兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from llama_index.core import Settings, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.dashscope import DashScopeEmbedding

# --- 配置阿里云 DashScope API Key ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# DashScope 的 OpenAI 兼容模式的 base_url
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# --- 初始化 LlamaIndex 全局设置 (可选) ---
if DASHSCOPE_API_KEY:
    try:
        Settings.llm = OpenAI(
            model="qwen-plus",
            api_base=DASHSCOPE_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            temperature=0.1
        )

        Settings.embed_model = DashScopeEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
        )
        print("✓ LLM和Embedding已配置\n")
    except Exception as e:
        print(f"⚠ 配置失败（不影响切片演示）: {e}\n")
else:
    print("ℹ 本演示只需要切片功能，不需要LLM配置\n")


def demonstrate_sliding_window_splitter(documents, chunk_size, chunk_overlap):
    """
    演示 LlamaIndex 中保持句子完整性的滑动窗口切片。

    Args:
        documents (list[Document]): 待切分的文档列表。
        chunk_size (int): 每个切块的目标 Token 数量。
        chunk_overlap (int): 相邻切块之间重叠的 Token 数量。
    """
    print(f"{'='*70}")
    print(f"正在演示【句子滑动窗口切片】")
    print(f"{'='*70}")
    print(f"  切块大小 (chunk_size):    {chunk_size} tokens")
    print(f"  重叠大小 (chunk_overlap): {chunk_overlap} tokens")
    print(f"  重叠比例:                 {chunk_overlap/chunk_size*100:.1f}%")
    print(f"{'='*70}\n")

    # --- 第一步：创建切分器 ---
    # SentenceSplitter 优先保持句子完整性，再考虑大小
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    # --- 第二步：执行切分 ---
    # 获取切分后的节点（切块）
    nodes = splitter.get_nodes_from_documents(documents)

    # --- 第三步：打印切分结果，展示重叠效果 ---
    print("【切分结果】")
    print(f"文档被切分为 {len(nodes)} 个切块\n")
    print("─" * 70)

    for i, node in enumerate(nodes, 1):
        content = node.get_content().strip()
        # 计算实际token数（近似）
        from llama_index.core.utils import get_tokenizer
        tokenizer = get_tokenizer()
        token_count = len(tokenizer(content))

        print(f"\n【切块 {i}】 (实际: {token_count} tokens, {len(content)} 字符)")
        print("─" * 70)
        # 显示前150字符
        preview = content[:150] + "..." if len(content) > 150 else content
        print(f"{preview}")
        print("─" * 70)

    # --- 第四步：重点展示重叠部分 ---
    print("\n" + "="*70)
    print("【重叠分析】观察相邻切块的重叠部分")
    print("="*70)

    if len(nodes) > 1:
        for i in range(len(nodes) - 1):
            chunk1_content = nodes[i].get_content()
            chunk2_content = nodes[i + 1].get_content()

            # 查找实际的重叠文本
            # 从chunk1的末尾和chunk2的开头查找公共部分
            overlap_text = find_overlap(chunk1_content, chunk2_content)

            print(f"\n>>> 切块 {i+1} 与 切块 {i+2} 的重叠:")
            print("─" * 70)

            if overlap_text:
                overlap_length = len(overlap_text)
                from llama_index.core.utils import get_tokenizer
                tokenizer = get_tokenizer()
                overlap_tokens = len(tokenizer(overlap_text))

                print(f"重叠长度: {overlap_tokens} tokens ({overlap_length} 字符)")
                print(f"\n重叠内容:")
                print(f'"{overlap_text[:200]}{"..." if len(overlap_text) > 200 else ""}"')

                # 显示在两个chunk中的位置
                pos_in_chunk1 = chunk1_content.find(overlap_text)
                pos_in_chunk2 = chunk2_content.find(overlap_text)
                print(f"\n在切块{i+1}中: 位置 {pos_in_chunk1} (末尾部分)")
                print(f"在切块{i+2}中: 位置 {pos_in_chunk2} (开头部分)")
            else:
                print("⚠ 未检测到明显重叠（可能是句子边界对齐）")

            print("─" * 70)
    else:
        print("文档太短，未能生成多个切块。请使用更长的文档以观察效果。")

    # --- 第五步：可视化展示 ---
    print("\n" + "="*70)
    print("【滑动窗口可视化】")
    print("="*70)
    visualize_sliding_window(nodes, chunk_size, chunk_overlap)

    print(f"\n{'='*70}")
    print("滑动窗口切片演示完成")
    print(f"{'='*70}\n")


def find_overlap(text1, text2, min_overlap=10):
    """
    查找两个文本之间的重叠部分
    从text1的末尾和text2的开头查找最长公共子串
    """
    # 从最长可能的重叠开始尝试
    max_possible = min(len(text1), len(text2))

    for length in range(max_possible, min_overlap, -1):
        # 取text1的后length个字符
        end_of_text1 = text1[-length:]
        # 取text2的前length个字符
        start_of_text2 = text2[:length]

        if end_of_text1 == start_of_text2:
            return end_of_text1

    return None


def visualize_sliding_window(nodes, chunk_size, chunk_overlap):
    """
    可视化展示滑动窗口的移动过程
    """
    print("\n滑动窗口示意图:\n")

    if len(nodes) == 0:
        print("无切块")
        return

    # 使用块来表示每个chunk
    total_display_width = 60
    chunk_char = "█"
    overlap_char = "▓"
    empty_char = "░"

    for i, node in enumerate(nodes, 1):
        content = node.get_content()
        from llama_index.core.utils import get_tokenizer
        tokenizer = get_tokenizer()
        actual_tokens = len(tokenizer(content))

        # 计算显示宽度（按比例）
        display_width = min(int(actual_tokens / chunk_size * 40), total_display_width)
        overlap_width = int(chunk_overlap / chunk_size * 40) if chunk_overlap > 0 else 0

        # 绘制切块
        chunk_viz = chunk_char * display_width
        print(f"Chunk {i}: {chunk_viz}  ({actual_tokens} tokens)")

        # 如果有下一个切块，显示重叠部分
        if i < len(nodes):
            overlap_viz = " " * (display_width - overlap_width) + overlap_char * overlap_width
            print(f"         {overlap_viz}  (重叠约 {chunk_overlap} tokens)")

    print("\n说明:")
    print(f"  {chunk_char} = 切块内容")
    print(f"  {overlap_char} = 重叠部分")


# --- 示例文档（包含多个句子）---
documents = [
    Document(
        text="""
        LlamaIndex 是一个用于构建 LLM 应用程序的数据框架。它提供了一套工具，帮助开发者将私有数据与大型语言模型（LLMs）连接起来，实现包括问答、检索增强生成（RAG）等功能。LlamaIndex 支持多种数据源，包括 PDF、数据库、API 等。

        其核心概念包括文档加载器、节点解析器、索引和查询引擎。文档加载器负责将各种格式和来源的数据摄取到 LlamaIndex 中。节点解析器随后将这些加载的文档分解成更小、更易于管理的单元，称为节点。这些节点通常是句子或段落，具体取决于解析策略。索引是构建在这些节点之上的数据结构，旨在实现高效存储和检索，通常涉及向量嵌入以进行语义搜索。

        查询引擎促进了与索引数据的交互，允许用户提出问题并利用 LLM 和检索到的信息合成答案。为了优化检索质量，LlamaIndex 提供了多种节点解析策略，包括固定大小切分、句子切分、段落切分等。选择合适的切分策略对于构建高质量的 RAG 应用至关重要。

        此外，LlamaIndex 还支持多种高级功能，如元数据过滤、混合检索、查询转换等。这些功能使得开发者能够构建更加智能和灵活的 LLM 应用程序。通过合理配置和使用这些工具，可以显著提升应用的性能和用户体验。
        """
    )
]

print("="*70)
print("句子滑动窗口切片演示程序")
print("="*70)
print("\n本演示将展示不同配置下的切分效果\n")

# --- 测试不同的配置 ---

print("\n" + "🔹"*35)
print("测试 1: 中等切块 + 小重叠")
print("🔹"*35)
demonstrate_sliding_window_splitter(documents, chunk_size=150, chunk_overlap=30)

print("\n" + "🔹"*35)
print("测试 2: 中等切块 + 大重叠")
print("🔹"*35)
demonstrate_sliding_window_splitter(documents, chunk_size=150, chunk_overlap=50)

print("\n" + "🔹"*35)
print("测试 3: 大切块 + 中等重叠")
print("🔹"*35)
demonstrate_sliding_window_splitter(documents, chunk_size=300, chunk_overlap=60)

print("\n" + "="*70)
print("💡 总结")
print("="*70)
print("""
【滑动窗口切片原理】:
1. 按照 chunk_size 切分文本
2. 保持句子完整性（不会在句子中间切断）
3. 相邻切块之间有 chunk_overlap 大小的重叠

【重叠的作用】:
✓ 保留上下文连贯性
✓ 避免重要信息被切断在边界处
✓ 提高检索的召回率

【推荐配置】:
- chunk_size: 500-800 tokens (适合大多数场景)
- chunk_overlap: chunk_size的10-20% (例如: 50-150 tokens)
- 重叠比例: 不要超过30%（避免冗余过多）
""")
