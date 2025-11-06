#!/usr/bin/env python3
"""
混合切块方案：滑动窗口 + 关键词感知切分

策略：
1. 第一阶段：使用滑动窗口进行初步切分
2. 第二阶段：检测chunk中的关键词，在关键词边界进行智能切分
   - 确保每个chunk包含完整的关键词上下文
   - 避免在关键词中间切分
"""

import os
import re
import sys
import textwrap
from typing import List, Callable, Set
from pydantic import Field

# UTF-8输出（Windows兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from llama_index.core import Settings, Document
from llama_index.core.node_parser import NodeParser, SentenceSplitter
from llama_index.core.utils import get_tokenizer

# LLM and Embedding imports - optional for this chunking test
try:
    from llama_index.llms.openai import OpenAI
    from llama_index.embeddings.dashscope import DashScopeEmbedding
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# --- 自定义关键词感知混合解析器类 ---
class KeywordAwareParser(NodeParser):
    """
    关键词感知的混合切块解析器

    工作流程：
    1. 使用滑动窗口进行初步切分
    2. 检测关键词，在关键词边界进行二次切分
    3. 确保每个chunk包含完整的关键词上下文
    """

    primary_parser: NodeParser  # 滑动窗口解析器
    keywords: Set[str] = Field(default_factory=set)  # 关键词集合
    min_chunk_size: int = 200  # 最小chunk大小
    max_chunk_size: int = 800  # 最大chunk大小
    keyword_context_window: int = 50  # 关键词前后保留的字符数
    tokenizer: Callable = Field(default_factory=get_tokenizer, exclude=True)

    def _find_keyword_positions(self, text: str) -> List[tuple]:
        """
        查找文本中所有关键词的位置

        返回: [(keyword, start_pos, end_pos), ...]
        """
        positions = []
        for keyword in self.keywords:
            # 使用正则查找所有匹配位置
            for match in re.finditer(re.escape(keyword), text):
                positions.append((keyword, match.start(), match.end()))

        # 按位置排序
        positions.sort(key=lambda x: x[1])
        return positions

    def _split_by_keywords(self, text: str) -> List[str]:
        """
        根据关键词边界切分文本

        策略：
        1. 找到所有关键词位置
        2. 在关键词之间寻找合适的切分点
        3. 保证每个chunk包含完整的关键词上下文
        """
        keyword_positions = self._find_keyword_positions(text)

        if not keyword_positions:
            # 没有关键词，返回整个文本
            return [text]

        print(f"      发现 {len(keyword_positions)} 个关键词:")
        for kw, start, end in keyword_positions[:5]:  # 只显示前5个
            print(f"        - '{kw}' at position {start}")
        if len(keyword_positions) > 5:
            print(f"        ... 还有 {len(keyword_positions) - 5} 个")

        chunks = []
        current_start = 0
        text_len = len(text)

        i = 0
        while i < len(keyword_positions):
            keyword, kw_start, kw_end = keyword_positions[i]

            # 计算包含当前关键词的chunk范围
            chunk_start = max(current_start, kw_start - self.keyword_context_window)

            # 尝试向前延伸到句子边界
            if chunk_start > current_start:
                # 寻找前面最近的句号、换行等
                for sep in ['。', '\n', '！', '？', '. ', '! ', '? ']:
                    sep_pos = text.rfind(sep, current_start, chunk_start)
                    if sep_pos != -1:
                        chunk_start = sep_pos + len(sep)
                        break

            # 尝试包含后续的关键词（如果它们很近）
            chunk_end = kw_end + self.keyword_context_window
            j = i + 1
            while j < len(keyword_positions):
                next_kw, next_start, next_end = keyword_positions[j]
                # 如果下一个关键词很近，尝试包含它
                if next_start - chunk_end < self.keyword_context_window:
                    chunk_end = next_end + self.keyword_context_window
                    j += 1
                else:
                    break

            # 确保chunk不会太大
            if chunk_end - chunk_start > self.max_chunk_size:
                chunk_end = chunk_start + self.max_chunk_size

            # 尝试在句子边界结束
            if chunk_end < text_len:
                for sep in ['。', '\n', '！', '？', '. ', '! ', '? ']:
                    sep_pos = text.find(sep, chunk_end, min(chunk_end + 50, text_len))
                    if sep_pos != -1:
                        chunk_end = sep_pos + len(sep)
                        break

            chunk_end = min(chunk_end, text_len)

            # 提取chunk
            chunk_text = text[chunk_start:chunk_end].strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(chunk_text)

            # 更新位置
            current_start = chunk_end
            i = j

        # 处理剩余文本
        if current_start < text_len:
            remaining = text[current_start:].strip()
            if len(remaining) >= self.min_chunk_size:
                chunks.append(remaining)
            elif chunks:
                # 如果剩余文本太短，合并到最后一个chunk
                chunks[-1] += " " + remaining

        return chunks

    def _parse_nodes(self, documents: List[Document], **kwargs) -> List[Document]:
        print("=" * 70)
        print("🔧 开始执行【滑动窗口 + 关键词感知切分】")
        print("=" * 70)

        # 第一阶段：滑动窗口初步切分
        print("\n📍 第一阶段：滑动窗口初步切分")
        print("-" * 70)
        primary_nodes = self.primary_parser.get_nodes_from_documents(documents)
        print(f"初步切分出 {len(primary_nodes)} 个chunk\n")

        for i, p_node in enumerate(primary_nodes, 1):
            token_count = len(self.tokenizer(p_node.get_content()))
            print(f"【初步Chunk {i}】(大小: {token_count} tokens)")
            print("  " + "-" * 60)
            preview = p_node.get_content().strip()[:100]
            print(f"  {preview}...")
            print("  " + "-" * 60)

        # 第二阶段：关键词感知的智能切分
        print("\n📍 第二阶段：关键词感知的智能切分")
        print("-" * 70)
        print(f"关键词列表: {', '.join(list(self.keywords)[:10])}")
        if len(self.keywords) > 10:
            print(f"           ... 还有 {len(self.keywords) - 10} 个关键词")
        print()

        final_nodes = []

        for i, node in enumerate(primary_nodes, 1):
            content = node.get_content()
            content_len = len(content)
            token_count = len(self.tokenizer(content))

            print(f"\n>>> 处理【初步Chunk {i}】(大小: {token_count} tokens, {content_len} 字符)")

            # 检查是否包含关键词
            has_keywords = any(kw in content for kw in self.keywords)

            if not has_keywords:
                print(f"  └─ 未发现关键词，直接保留原chunk")
                final_nodes.append(node)
                continue

            # 检查大小
            if token_count <= self.min_chunk_size:
                print(f"  └─ Chunk很小 ({token_count} tokens)，直接保留")
                final_nodes.append(node)
                continue

            if token_count <= self.max_chunk_size and has_keywords:
                print(f"  └─ 大小适中且包含关键词，直接保留")
                final_nodes.append(node)
                continue

            # 需要基于关键词进行二次切分
            print(f"  └─ Chunk较大 ({token_count} tokens) 且包含关键词，进行智能切分...")
            print(f"\n      【原始内容】")
            print("      " + "=" * 55)
            print(textwrap.indent(content.strip()[:200] + "...", '      | '))
            print("      " + "=" * 55)

            # 执行关键词感知切分
            sub_chunks = self._split_by_keywords(content)

            print(f"\n      【切分结果】: 被切成 {len(sub_chunks)} 个子chunk")

            for j, sub_chunk in enumerate(sub_chunks, 1):
                sub_token_count = len(self.tokenizer(sub_chunk))

                # 找出这个子chunk包含的关键词
                found_keywords = [kw for kw in self.keywords if kw in sub_chunk]

                print(f"\n        【子Chunk {i}.{j}】(大小: {sub_token_count} tokens)")
                print(f"        包含关键词: {', '.join(found_keywords[:5])}")
                if len(found_keywords) > 5:
                    print(f"                   ... 还有 {len(found_keywords) - 5} 个")
                print("        " + "-" * 45)
                preview = sub_chunk.strip()[:150]
                print(textwrap.indent(preview + "...", '        | '))
                print("        " + "-" * 45)

                # 创建新节点
                sub_node = Document(text=sub_chunk)
                sub_node.metadata = node.metadata.copy()
                sub_node.metadata['parent_chunk_id'] = i
                sub_node.metadata['sub_chunk_id'] = j
                sub_node.metadata['keywords'] = found_keywords[:10]  # 保存关键词

                final_nodes.append(sub_node)

        print("\n" + "=" * 70)
        print(f"✅ 【混合切分】完成！最终生成 {len(final_nodes)} 个chunk")
        print("=" * 70)

        return final_nodes

    @classmethod
    def from_defaults(cls, **kwargs):
        raise NotImplementedError("请直接实例化此类")


# --- 全局配置 ---
# LLM配置（可选，本测试不需要）
if DASHSCOPE_API_KEY and HAS_LLM:
    try:
        DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        Settings.llm = OpenAI(
            model="qwen-plus",
            api_base=DASHSCOPE_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            temperature=0.1
        )
        Settings.embed_model = DashScopeEmbedding(
            model_name="text-embedding-v2",
            api_key=DASHSCOPE_API_KEY,
            batch_size=10
        )
        print("✓ LLM和Embedding已配置")
    except Exception as e:
        print(f"⚠ LLM配置失败（不影响切块测试）: {e}")
else:
    print("ℹ 本测试只需要切块功能，不需要LLM配置")


# --- 准备测试文档（政策文档） ---
policy_document = Document(
    text="""
济南市2025年家电以旧换新补贴实施细则

第一章 总则

第一条 为贯彻落实国家和省关于促进消费的政策措施，鼓励居民更新家用电器，提升居民生活品质，根据《山东省家电以旧换新实施方案》，制定本细则。

第二条 补贴范围包括电视机、冰箱、洗衣机、空调、热水器等家用电器。本次活动补贴资金总额为5000万元，用完即止。

第二章 补贴标准

第三条 对个人消费者购买2级及以上能效或水效标准的补贴产品，按最终销售价格的15%给予补贴；对其中购买1级及以上能效或水效标准的产品，额外再给予产品最终销售价格5%的补贴。单件产品补贴金额最高不超过2000元。

第四条 补贴申请条件：
（一）申请人须为具有完全民事行为能力的自然人；
（二）申请人须提供济南市户籍证明或居住证；
（三）购买的产品须为补贴范围内的新产品；
（四）须在参与活动的销售企业购买，并取得正规发票；
（五）须完成旧家电的回收处理。

第三章 申请流程

第五条 补贴申请流程：
（一）个人消费者通过"泉城购"服务平台完成实名认证，领取补贴资格；
（二）领取补贴资格后，在参与活动的企业（门店）或电商平台购买补贴范围内的产品；
（三）核销补贴资格，享受支付立减，每个补贴资格仅限购买1件产品；
（四）销售企业需按要求完成产品配送、安装、旧家电回收及发票开具等流程。

第四章 监督管理

第六条 市商务局负责活动的总体组织协调，市场监管部门负责产品质量监督，财政部门负责补贴资金管理。

第七条 参与活动的销售企业应建立完善的销售记录，确保补贴产品符合能效标准，不得虚报价格、骗取补贴。

第八条 发现违规行为的，将取消企业参与资格，追回违规补贴资金，并依法追究相关责任。

第五章 附则

第九条 本细则由市商务局负责解释。

第十条 本细则自发布之日起施行，有效期至2025年12月31日。

附件：
1. 补贴产品目录
2. 参与活动企业名单
3. 补贴申请表格式
"""
)


# --- 定义政策文档相关的关键词 ---
policy_keywords = {
    # 补贴相关
    "补贴", "补贴标准", "补贴资金", "补贴申请", "补贴范围", "补贴产品", "补贴金额",

    # 产品相关
    "家电", "以旧换新", "电视机", "冰箱", "洗衣机", "空调", "热水器",
    "能效标准", "水效标准", "能效", "水效",

    # 申请条件
    "申请条件", "申请流程", "实名认证", "补贴资格", "发票",

    # 部门相关
    "商务局", "市场监管", "财政部门",

    # 章节标题
    "第一章", "第二章", "第三章", "第四章", "第五章",
    "总则", "监督管理", "附则",

    # 数字金额
    "5000万元", "2000元", "15%", "5%", "2级", "1级"
}


def main():
    print("\n" + "🎯" * 35)
    print("  滑动窗口 + 关键词感知切分 - 测试程序")
    print("🎯" * 35 + "\n")

    # 实例化滑动窗口解析器（用于初步切分）- 使用更大的chunk_size
    window_parser = SentenceSplitter(
        chunk_size=1000,  # 更大的初步切分，会触发二次切分
        chunk_overlap=100
    )

    # 实例化关键词感知解析器
    keyword_parser = KeywordAwareParser(
        primary_parser=window_parser,
        keywords=policy_keywords,
        min_chunk_size=150,  # 降低最小值
        max_chunk_size=500,  # 降低最大值，会强制切分
        keyword_context_window=80,  # 关键词前后保留80个字符
        tokenizer=get_tokenizer()
    )

    # 执行切分
    final_nodes = keyword_parser.get_nodes_from_documents([policy_document])

    # --- 打印最终结果 ---
    print("\n\n" + "=" * 70)
    print("📊 最终切块结果汇总")
    print("=" * 70)
    print(f"\n切块总数: {len(final_nodes)}\n")

    for i, node in enumerate(final_nodes, 1):
        content = node.get_content().strip()
        token_count = len(get_tokenizer()(content))

        # 提取关键词
        found_keywords = node.metadata.get('keywords', [])
        if not found_keywords:
            found_keywords = [kw for kw in policy_keywords if kw in content]

        print(f"\n【最终Chunk {i}】")
        print(f"大小: {token_count} tokens ({len(content)} 字符)")
        print(f"关键词: {', '.join(found_keywords[:5])}")
        if len(found_keywords) > 5:
            print(f"       ... 还有 {len(found_keywords) - 5} 个")
        print("-" * 70)
        print(textwrap.indent(content[:300] + "..." if len(content) > 300 else content, '  '))
        print("-" * 70)

    # 统计信息
    print("\n\n" + "=" * 70)
    print("📈 统计信息")
    print("=" * 70)

    sizes = [len(get_tokenizer()(node.get_content())) for node in final_nodes]
    print(f"\nToken数统计:")
    print(f"  - 最小: {min(sizes)} tokens")
    print(f"  - 最大: {max(sizes)} tokens")
    print(f"  - 平均: {sum(sizes) / len(sizes):.1f} tokens")
    print(f"  - 总计: {sum(sizes)} tokens")

    # 关键词覆盖统计
    all_keywords_found = set()
    for node in final_nodes:
        content = node.get_content()
        for kw in policy_keywords:
            if kw in content:
                all_keywords_found.add(kw)

    print(f"\n关键词覆盖:")
    print(f"  - 总关键词数: {len(policy_keywords)}")
    print(f"  - 已覆盖: {len(all_keywords_found)}")
    print(f"  - 覆盖率: {len(all_keywords_found) / len(policy_keywords) * 100:.1f}%")

    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
