#!/usr/bin/env python3
"""
测试集成到 hierarchical_index.py 的三种切块策略
"""

import os
import sys

# UTF-8输出（Windows兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from knowledge_base.hierarchical_index import (
    HierarchicalMarkdownProcessor,
    ChunkConfig
)

print("="*70)
print("测试 hierarchical_index.py 中集成的切块策略")
print("="*70)

# 准备测试文本
test_text = """
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
"""

print(f"\n📄 测试文档长度: {len(test_text)} 字符\n")

# 定义政策关键词
policy_keywords = {
    "补贴", "补贴标准", "补贴资金", "补贴申请", "补贴范围",
    "家电", "以旧换新", "电视机", "冰箱", "洗衣机", "空调", "热水器",
    "能效标准", "水效标准", "申请条件", "申请流程",
    "实名认证", "补贴资格", "发票", "商务局", "市场监管"
}

# ===========================================
# 测试 1: Simple 策略（字符级）
# ===========================================
print("\n" + "🔹"*35)
print("测试 1: Simple 策略（字符级滑动窗口）")
print("🔹"*35)

config_simple = ChunkConfig(
    chunking_strategy='simple',
    chunk_size=400,      # 字符
    chunk_overlap=50
)

processor_simple = HierarchicalMarkdownProcessor(config=config_simple)
chunks_simple = processor_simple._split_simple(test_text)

print(f"\n✓ 生成 {len(chunks_simple)} 个切块\n")
for i, chunk in enumerate(chunks_simple[:3], 1):  # 只显示前3个
    print(f"【切块 {i}】(长度: {len(chunk)} 字符)")
    print("─" * 70)
    preview = chunk[:150].replace('\n', ' ')
    print(f"{preview}...")
    print("─" * 70)
    print()

if len(chunks_simple) > 3:
    print(f"... 还有 {len(chunks_simple) - 3} 个切块\n")

# ===========================================
# 测试 2: Sentence 策略（推荐）
# ===========================================
print("\n" + "🔹"*35)
print("测试 2: Sentence 策略（句子级滑动窗口）⭐ 推荐")
print("🔹"*35)

config_sentence = ChunkConfig(
    chunking_strategy='sentence',
    chunk_size=300,      # tokens
    chunk_overlap=50
)

processor_sentence = HierarchicalMarkdownProcessor(config=config_sentence)
chunks_sentence = processor_sentence._split_sentence(test_text)

print(f"\n✓ 生成 {len(chunks_sentence)} 个切块\n")
for i, chunk in enumerate(chunks_sentence[:3], 1):
    from llama_index.core.utils import get_tokenizer
    tokenizer = get_tokenizer()
    token_count = len(tokenizer(chunk))

    print(f"【切块 {i}】({token_count} tokens, {len(chunk)} 字符)")
    print("─" * 70)
    preview = chunk[:150].replace('\n', ' ')
    print(f"{preview}...")
    print("─" * 70)
    print()

if len(chunks_sentence) > 3:
    print(f"... 还有 {len(chunks_sentence) - 3} 个切块\n")

# ===========================================
# 测试 3: Keyword Aware 策略
# ===========================================
print("\n" + "🔹"*35)
print("测试 3: Keyword Aware 策略（关键词感知）")
print("🔹"*35)

config_keyword = ChunkConfig(
    chunking_strategy='keyword_aware',
    chunk_size=500,          # tokens（初步切分）
    chunk_overlap=80,
    keywords=policy_keywords,
    min_chunk_size=150,
    max_chunk_size=600,      # 字符（二次切分阈值）
    keyword_context_window=80
)

processor_keyword = HierarchicalMarkdownProcessor(config=config_keyword)
chunks_keyword = processor_keyword._split_keyword_aware(test_text)

print(f"\n✓ 生成 {len(chunks_keyword)} 个切块")
print(f"✓ 使用 {len(policy_keywords)} 个关键词\n")

for i, chunk in enumerate(chunks_keyword[:3], 1):
    from llama_index.core.utils import get_tokenizer
    tokenizer = get_tokenizer()
    token_count = len(tokenizer(chunk))

    # 统计包含的关键词
    found_keywords = [kw for kw in policy_keywords if kw in chunk]

    print(f"【切块 {i}】({token_count} tokens, {len(chunk)} 字符)")
    print(f"包含关键词: {', '.join(found_keywords[:5])}")
    if len(found_keywords) > 5:
        print(f"           ... 还有 {len(found_keywords) - 5} 个")
    print("─" * 70)
    preview = chunk[:150].replace('\n', ' ')
    print(f"{preview}...")
    print("─" * 70)
    print()

if len(chunks_keyword) > 3:
    print(f"... 还有 {len(chunks_keyword) - 3} 个切块\n")

# ===========================================
# 对比总结
# ===========================================
print("\n" + "="*70)
print("📊 切块策略对比总结")
print("="*70)

print(f"""
| 策略 | 切块数 | 平均大小 | 说明 |
|------|--------|---------|------|
| Simple | {len(chunks_simple)} | {sum(len(c) for c in chunks_simple) // len(chunks_simple)} 字符 | 字符级，可能切断句子 |
| Sentence | {len(chunks_sentence)} | {sum(len(c) for c in chunks_sentence) // len(chunks_sentence)} 字符 | 句子级，语义完整 ⭐ |
| KeywordAware | {len(chunks_keyword)} | {sum(len(c) for c in chunks_keyword) // len(chunks_keyword)} 字符 | 保留关键词上下文 |
""")

print("\n💡 推荐配置:\n")
print("  【通用文档】")
print("    chunking_strategy='sentence'")
print("    chunk_size=600")
print("    chunk_overlap=80")
print()
print("  【政策文档】（需要保留关键词）")
print("    chunking_strategy='keyword_aware'")
print("    chunk_size=500")
print("    chunk_overlap=80")
print("    keywords=<政策关键词集合>")
print("    max_chunk_size=600")
print()

print("="*70)
print("✅ 测试完成！")
print("="*70)
print("\n📝 使用方法:\n")
print("```python")
print("from knowledge_base.hierarchical_index import ChunkConfig, HierarchicalMarkdownProcessor")
print()
print("# 方式1: 使用句子切分（推荐）")
print("config = ChunkConfig(")
print("    chunking_strategy='sentence',")
print("    chunk_size=600,")
print("    chunk_overlap=80")
print(")")
print()
print("# 方式2: 使用关键词感知切分")
print("config = ChunkConfig(")
print("    chunking_strategy='keyword_aware',")
print("    chunk_size=500,")
print("    keywords={'补贴', '家电', '申请流程', ...},")
print("    max_chunk_size=600")
print(")")
print()
print("processor = HierarchicalMarkdownProcessor(config=config)")
print("```")
