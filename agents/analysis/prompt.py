"""
用于 LLM 的政策分析抽取提示（中文）。
"""

from typing import Dict


def nlp_extraction_system_prompt() -> str:
    return (
        "你是一个政策文本信息抽取助手。收到指令后，只能输出严格的 JSON，"
        "不要输出任何 JSON 之外的文字或解释。"
    )


def nlp_extraction_user_prompt(content: str, instruction: str) -> str:
    return (
        "请根据以下指令，从政策文本中抽取信息。\n\n"
        f"指令：{instruction}\n\n"
        f"政策文本：\n{content}\n\n"
        "输出 JSON 数组（例如：[\"项1\", \"项2\"]）。"
    )


def full_analysis_system_prompt() -> str:
    return (
        "你是政策分析助手。阅读政策文本，输出严格 JSON，包含以下键："
        "eligibility_criteria（字符串数组）、benefit_details（字符串或 null）、application_steps（数组）、"
        "required_documents（数组）、deadlines（数组）、contact_info（数组）、limitations（数组）、analysis_confidence（0~1 浮点数）。"
        "不要输出 JSON 之外的任何文字。"
    )


def full_analysis_user_prompt(content: str, query_hint: str = "") -> str:
    hint = f"用户问题：{query_hint}\n\n" if query_hint else ""
    return (
        f"{hint}请分析下列政策文本，并按要求以 JSON 形式输出各字段。\n\n"
        f"政策文本：\n{content}"
    )
