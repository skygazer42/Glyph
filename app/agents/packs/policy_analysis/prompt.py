"""
用于 LLM 的政策分析抽取提示（中文）。
"""


NLP_EXTRACTION_SYSTEM_PROMPT = (
    "你是一个政策文本信息抽取助手。收到指令后，只能输出严格的 JSON，"
    "不要输出任何 JSON 之外的文字或解释。"
)


def build_nlp_extraction_user_prompt(content: str, instruction: str) -> str:
    return (
        "请根据以下指令，从政策文本中抽取信息。\n\n"
        f"指令：{instruction}\n\n"
        f"政策文本：\n{content}\n\n"
        "输出 JSON 数组（例如：[\"项1\", \"项2\"]）。"
    )
