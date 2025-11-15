# 置信度 (Confidence) 详解

## 概述

在Glyph系统中，**置信度** (Confidence) 是一个 0-1 之间的浮点数，表示系统对答案质量和准确性的信心程度。置信度越高,表示系统越确信答案的正确性。

## 置信度的计算方式

置信度在系统的不同阶段由不同组件计算，最终合并为一个综合置信度。

### 1. 意图识别置信度 (IntentRouter)

**位置**: `app/agents/packs/intent_router/node.py`

```python
# LLM返回的意图分类置信度
intent_confidence = llm_output.get("confidence", 0.6)  # 默认60%
```

**影响因素**:
- LLM对意图分类的确定性
- 查询的明确程度
- 关键词匹配度

**示例**:
```
查询: "家电以旧换新补贴标准是多少？"
意图: policy_inquiry
置信度: 0.96 (96%) - 非常明确的政策查询
```

### 2. 查询分析置信度 (QueryAnalyzer)

**位置**: `app/agents/packs/query_analyzer/node.py:323-343`

```python
def _calculate_confidence(self, query, analysis):
    confidence = 0.5  # 基础置信度 50%

    # 包含明确实体名称 +20%
    if analysis.get("entities"):
        confidence += 0.2

    # 包含政策领域关键词 +10%
    if analysis.get("domain"):
        confidence += 0.1

    # 具有明确意图 +20%
    if analysis.get("intent_clarity") == "high":
        confidence += 0.2

    # 包含数字/金额 +10%
    if analysis.get("has_numbers"):
        confidence += 0.1

    # 查询完整度高 +20%
    if analysis.get("completeness") == "high":
        confidence += 0.2

    # 有时间/地点限定 +10%
    if analysis.get("has_constraints"):
        confidence += 0.1

    return min(1.0, confidence)
```

**示例**:
```
查询: "济南市2025年家电补贴能领多少钱？"

分析结果:
✅ 实体: 济南市、家电补贴 → +20%
✅ 领域: 家电政策 → +10%
✅ 意图: 明确(补贴金额查询) → +20%
✅ 数字: 2025 → +10%
✅ 完整度: 高 → +20%
✅ 约束: 地点(济南)、时间(2025) → +10%

最终置信度: 50% + 90% = 100% (cap at 100%)
```

### 3. 答案生成置信度 (AnswerGenerator)

**位置**: `app/agents/packs/answer_generator/node.py:500-526`

这是**最重要**的置信度计算，综合考虑多个维度:

```python
async def _calculate_answer_confidence(
    self,
    sources: List[Tuple[str, float]],
    info: Dict[str, Any]
) -> float:
    """
    计算答案的综合置信度

    Args:
        sources: [(文档内容, 相似度分数), ...]
        info: 提取的政策信息字典

    Returns:
        0.0-1.0 的置信度分数
    """
    if not sources:
        return 0.0

    # 1️⃣ 来源质量置信度 (权重60%)
    # 基于向量检索的相似度分数
    source_confidence = sum(score for _, score in sources) / len(sources)

    # 2️⃣ 信息完整性因子 (权重40%)
    completeness_factor = 0.0

    # 包含资格标准 +25%
    if info.get("eligibility_criteria"):
        completeness_factor += 0.25

    # 包含补贴金额 +25%
    if info.get("benefits"):
        completeness_factor += 0.25

    # 包含申请流程 +25%
    if info.get("application_steps"):
        completeness_factor += 0.25

    # 包含截止时间 +25%
    if info.get("deadlines"):
        completeness_factor += 0.25

    # 3️⃣ 冲突惩罚
    # 每个冲突项扣10%
    conflict_penalty = 0.1 * len(info.get("conflicts", []))

    # 4️⃣ 最终置信度计算
    final_confidence = (
        source_confidence * 0.6 +      # 来源质量 60%
        completeness_factor * 0.4 -    # 完整性 40%
        conflict_penalty               # 冲突惩罚
    )

    # 限制在 [0.0, 1.0] 范围内
    return max(0.0, min(1.0, final_confidence))
```

**实际案例分析**:

#### 案例1: 高置信度答案 (90%)

```
查询: "家电以旧换新补贴标准是多少？"

检索结果:
- 文档1: 《济南市家电补贴细则》 相似度: 0.92
- 文档2: 《山东省家电政策》   相似度: 0.88

来源置信度: (0.92 + 0.88) / 2 = 0.90

提取信息:
✅ eligibility_criteria: "个人消费者,2级以上能效" → +0.25
✅ benefits: "15%基础补贴,1级额外5%" → +0.25
✅ application_steps: "实名认证→领取资格→购买→核销" → +0.25
✅ deadlines: "2025-01-01至2025-12-31" → +0.25

完整性因子: 1.0

冲突: 无 → 0

最终置信度 = 0.90 × 0.6 + 1.0 × 0.4 - 0
            = 0.54 + 0.4
            = 0.94 (94%)
```

#### 案例2: 中置信度答案 (70%)

```
查询: "消费券怎么用？"

检索结果:
- 文档1: 《泉城购消费券活动》 相似度: 0.75
- 文档2: 《家电补贴细则》    相似度: 0.65
- 文档3: 《汽车消费券》      相似度: 0.60

来源置信度: (0.75 + 0.65 + 0.60) / 3 = 0.67

提取信息:
✅ benefits: "满200减30" → +0.25
✅ application_steps: "领券→使用" → +0.25
❌ eligibility_criteria: 未提取 → 0
❌ deadlines: 未明确 → 0

完整性因子: 0.5

冲突: 1个(不同活动规则冲突) → -0.1

最终置信度 = 0.67 × 0.6 + 0.5 × 0.4 - 0.1
            = 0.40 + 0.20 - 0.1
            = 0.50 (50%)
```

#### 案例3: 低置信度答案 (20%)

```
查询: "列出近三个月发布的政策标题及来源"

检索结果:
- 知识库未找到匹配文档

来源置信度: 0.0

提取信息: 全部为空

完整性因子: 0.0

冲突: 0

最终置信度 = 0.0 × 0.6 + 0.0 × 0.4 - 0
            = 0.0

# 系统设置最低置信度为0.2
返回: 0.2 (20%)
```

### 4. 规则引擎置信度

**位置**: 规则引擎计算结果的置信度

```python
# 规则匹配成功时
if rule_matched:
    confidence = 0.95  # 确定性规则，高置信度95%
else:
    confidence = 0.45  # 规则不匹配，低置信度45%
```

**示例**:
```
问题16: "一笔300元的餐饮消费，是否可以与商家折扣叠加？"

系统错误地路由到规则引擎，匹配了冰箱补贴规则
虽然计算成功(¥320),但这不是正确答案
置信度: 45% (反映了路由错误)
```

## 置信度的应用场景

### 1. 早停机制

```python
EARLY_STOP_CONF = 0.80  # 配置在.env中

# 当置信度达到80%时，停止进一步检索
if current_confidence >= EARLY_STOP_CONF:
    return answer  # 提前返回，节省成本
```

### 2. 答案质量评估

```python
if confidence >= 0.8:
    quality = "高质量答案"
elif confidence >= 0.5:
    quality = "中等质量答案,可能需要人工确认"
else:
    quality = "低质量答案,建议人工处理"
```

### 3. 用户反馈

在Web界面显示置信度，帮助用户判断答案可信度:

```
🟢 置信度 90%+ : 高度可信
🟡 置信度 50-90%: 一般可信,建议核实
🔴 置信度 <50% : 低可信度,需人工确认
```

## 测试结果中的置信度统计

根据20题测试结果:

```
平均置信度: 69.11%
最高置信度: 90.00% (对话类问题)
最低置信度: 20.00% (未找到文档的查询)

置信度分布:
- ≥80% (高): 2 题 (10%)
- 50-80% (中): 16 题 (80%)
- <50% (低): 2 题 (10%)
```

### 低置信度问题分析

**Q16 (45%)**: "一笔300元的餐饮消费，是否可以与商家折扣叠加？"
- **原因**: 错误路由到规则引擎,匹配了不相关的家电补贴规则
- **改进**: 优化路由逻辑,餐饮消费应路由到知识库或对话

**Q18 (20%)**: "列出近三个月发布的政策标题及来源"
- **原因**: 知识库未找到匹配文档
- **改进**: 需要接入Text2SQL或文档列表API

## 最佳实践

### 对于开发者

1. **监控低置信度问题**
   ```python
   if confidence < 0.5:
       logger.warning(f"Low confidence answer: {confidence} for query: {query}")
   ```

2. **人工介入阈值**
   ```python
   if confidence < 0.3:
       return "抱歉，我对这个问题不太确定，建议联系人工客服。"
   ```

3. **A/B测试不同置信度策略**
   - 测试不同的早停阈值
   - 调整置信度权重(来源60% vs 完整性40%)

### 对于用户

1. **查看置信度判断答案质量**
   - 置信度≥80%: 可直接使用
   - 置信度50-80%: 建议交叉验证
   - 置信度<50%: 需人工确认

2. **提供反馈改进系统**
   - 对低置信度但正确的答案点赞
   - 对高置信度但错误的答案反馈

## 总结

置信度是Glyph系统质量控制的核心指标，它:

1. ✅ **反映答案质量** - 综合评估来源、完整性和冲突
2. ✅ **指导系统行为** - 早停机制节省成本
3. ✅ **辅助用户决策** - 透明展示系统确定性
4. ✅ **持续改进依据** - 低置信度问题指向优化方向

通过理解和监控置信度，您可以更好地评估和优化Glyph系统的表现。
