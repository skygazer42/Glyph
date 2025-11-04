"""
用于 LLM 的答案生成提示（中文）。
"""

from typing import Dict, List, Tuple


def generation_system_prompt() -> str:
    return (
        "你是政策问答的答案生成器。根据查询上下文与结构化信息，生成有用、准确的回答。"
        "回答正文使用 Markdown 文本输出，语言清晰、条理分明，包含关键条件/金额/步骤，避免臆测。"
    )


def generation_user_prompt(query_context: Dict, info: Dict, synthesis: Dict) -> str:
    return (
        "请基于以下信息生成对用户政策问题的回答。\n\n"
        f"查询上下文：{query_context}\n\n"
        f"结构化抽取结果：{info}\n\n"
        f"综合信息：{synthesis}\n\n"
        "回答要求：简洁、可执行，包含关键条件/金额/步骤，如有不确定请明确说明，不要编造。"
    )
