"""
意图路由提示（中文优先）。

要求大模型阅读用户问题，仅输出一个严格的 JSON 对象，不允许有任何多余文字。
必须包含以下字段（键名为英文固定写法）：
{
  "intent": "greeting|farewell|chit_chat|calculation|comparison|summary|policy_inquiry|clarification",
  "sub_intent": "eligibility|process|deadline|documents|contact|null",
  "confidence": 0.0-1.0,
  "chains": ["chat_chain"|"calculation_chain"|"comparison_chain"|"kb_chain"|"graph_chain"|"hybrid_chain"],
  "requires_parallel": true|false
}

说明：
- greeting/farewell/chit_chat：走 chat_chain
- calculation（金额/比例/标准）：走 calculation_chain（必要时可补知识库）
- comparison（比较/哪个好/差异）：走 comparison_chain
- summary（概括/主题/关系/图谱）：走 graph_chain（LightRAG）
- policy_inquiry：当 sub_intent 为 eligibility/process/deadline/documents/contact 时走 kb_chain
- 若置信度低或问题含糊，请在 chains 中同时包含 kb_chain 与 graph_chain，并将 requires_parallel 设为 true；
  否则仅返回单一最佳链，requires_parallel 设为 false。
键名与取值请严格使用上述英文枚举，不要输出中文键名。
"""

from typing import List


def intent_system_instruction() -> str:
    return (
        "你是一个政策问答系统的意图路由器。阅读用户问题，仅输出严格的 JSON 对象，"
        "键名必须是 intent, sub_intent, confidence, chains, requires_parallel。"
        "intent 必须从：greeting, farewell, chit_chat, calculation, comparison, summary, policy_inquiry, clarification 中选择其一。"
        "若 intent 为 policy_inquiry，sub_intent 必须从：eligibility, process, deadline, documents, contact 中选择；否则为 null。"
        "confidence 为 0~1 的浮点数。chains 为数组，成员只能是：chat_chain, calculation_chain, comparison_chain, kb_chain, graph_chain, hybrid_chain。"
        "requires_parallel 仅在置信度较低或需要同时使用 KB 与 Graph 时为 true；否则为 false。"
        "请严格输出 JSON，不要输出任何 JSON 之外的文字。"
    )


def intent_user_prompt(query: str) -> str:
    examples: List[str] = [
        # chit_chat
        "\n示例：你好，在吗？\n",
        # calculation
        "\n示例：家电以旧换新最多能补多少钱？\n",
        # comparison
        "\n示例：济南和青岛的创业补贴政策有什么区别？\n",
        # summary
        "\n示例：请概括新能源汽车补贴政策的主要主题和相关部门关系。\n",
        # policy_inquiry
        "\n示例：申请新能源汽车补贴的条件和流程是什么？\n",
    ]
    return (
        "请对下列用户问题进行意图分类，并给出处理链（chains）。\n"
        "仅返回严格 JSON（不得含有多余文字）。\n\n"
        f"用户问题：{query}\n"
        + "\n".join(examples)
    )
