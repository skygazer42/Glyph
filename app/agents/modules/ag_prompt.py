"""
AG Prompt - Agent提示词管理模块示例
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from ...models.base import AgentType, MessageType
from ..core.agent_base import AgentBase
from ..core.message_bus import Message

logger = logging.getLogger(__name__)


class AgentPromptManager(AgentBase):
    """
    Agent提示词管理器 - 管理所有Agent的提示词模板
    """

    def __init__(self):
        super().__init__(
            agent_id="agent_prompt_manager",
            agent_type=AgentType.SPECIALIZED,
            name="Agent Prompt Manager",
            description="管理和优化Agent提示词"
        )
        self.capabilities = [
            "get_prompt",
            "update_prompt",
            "create_prompt",
            "delete_prompt",
            "list_prompts",
            "optimize_prompt",
            "validate_prompt"
        ]
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self._prompt_templates_path = Path(__file__).parent.parent.parent / "prompts" / "templates"
        self._load_default_prompts()

    async def process(self, message: Message) -> Optional[Message]:
        """处理提示词管理请求"""
        try:
            action = message.content.get("action")
            prompt_id = message.content.get("prompt_id")
            agent_type = message.content.get("agent_type")
            content = message.content.get("content", {})

            logger.info(f"Processing prompt action: {action} for prompt: {prompt_id}")

            # 根据动作执行相应操作
            if action == "get":
                result = await self._get_prompt(prompt_id or agent_type)
            elif action == "update":
                result = await self._update_prompt(prompt_id, content)
            elif action == "create":
                result = await self._create_prompt(
                    prompt_id,
                    agent_type,
                    content.get("template"),
                    content.get("variables", []),
                    content.get("description", "")
                )
            elif action == "delete":
                result = await self._delete_prompt(prompt_id)
            elif action == "list":
                result = await self._list_prompts(agent_type)
            elif action == "optimize":
                result = await self._optimize_prompt(prompt_id, content.get("criteria", []))
            elif action == "validate":
                result = self._validate_prompt(content.get("template", ""))
            else:
                result = {"error": f"Unknown action: {action}"}

            return message.create_reply(
                content={
                    "action": action,
                    "prompt_id": prompt_id,
                    "result": result,
                    "status": "success" if "error" not in result else "failed"
                },
                sender=self.agent_id
            )

        except Exception as e:
            logger.error(f"Error in prompt manager: {e}")
            return message.create_reply(
                content={"error": str(e)},
                sender=self.agent_id
            )

    async def _get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """获取提示词"""
        if prompt_id not in self._prompts:
            return {"error": f"Prompt not found: {prompt_id}"}

        prompt = self._prompts[prompt_id]

        # 如果提示词有变量，返回格式化模板
        if prompt.get("variables"):
            return {
                "prompt_id": prompt_id,
                "template": prompt["template"],
                "variables": prompt["variables"],
                "description": prompt.get("description", ""),
                "is_template": True
            }
        else:
            return {
                "prompt_id": prompt_id,
                "content": prompt["template"],
                "description": prompt.get("description", ""),
                "is_template": False
            }

    async def _update_prompt(self, prompt_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """更新提示词"""
        if prompt_id not in self._prompts:
            return {"error": f"Prompt not found: {prompt_id}"}

        prompt = self._prompts[prompt_id]

        if "template" in content:
            prompt["template"] = content["template"]
        if "variables" in content:
            prompt["variables"] = content["variables"]
        if "description" in content:
            prompt["description"] = content["description"]

        prompt["updated_at"] = str(asyncio.get_event_loop().time())

        return {
            "prompt_id": prompt_id,
            "message": "Prompt updated successfully"
        }

    async def _create_prompt(
        self,
        prompt_id: str,
        agent_type: str,
        template: str,
        variables: List[str] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """创建新的提示词"""
        if prompt_id in self._prompts:
            return {"error": f"Prompt already exists: {prompt_id}"}

        # 验证模板
        validation_result = self._validate_prompt(template)
        if not validation_result["valid"]:
            return validation_result

        self._prompts[prompt_id] = {
            "id": prompt_id,
            "agent_type": agent_type,
            "template": template,
            "variables": variables or [],
            "description": description,
            "created_at": str(asyncio.get_event_loop().time()),
            "updated_at": str(asyncio.get_event_loop().time())
        }

        return {
            "prompt_id": prompt_id,
            "message": "Prompt created successfully"
        }

    async def _delete_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """删除提示词"""
        if prompt_id not in self._prompts:
            return {"error": f"Prompt not found: {prompt_id}"}

        del self._prompts[prompt_id]

        return {
            "prompt_id": prompt_id,
            "message": "Prompt deleted successfully"
        }

    async def _list_prompts(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """列出提示词"""
        prompts = []

        for prompt_id, prompt in self._prompts.items():
            if agent_type and prompt.get("agent_type") != agent_type:
                continue

            prompts.append({
                "id": prompt_id,
                "agent_type": prompt.get("agent_type"),
                "description": prompt.get("description", ""),
                "is_template": bool(prompt.get("variables")),
                "created_at": prompt.get("created_at"),
                "updated_at": prompt.get("updated_at")
            })

        return {"prompts": prompts}

    async def _optimize_prompt(self, prompt_id: str, criteria: List[str]) -> Dict[str, Any]:
        """优化提示词"""
        if prompt_id not in self._prompts:
            return {"error": f"Prompt not found: {prompt_id}"}

        prompt = self._prompts[prompt_id]
        template = prompt["template"]

        # 简单的优化规则
        optimized = template

        # 清理多余空格
        optimized = " ".join(optimized.split())

        # 确保有清晰的指令
        if "你" not in optimized and "请" not in optimized:
            optimized = "请" + optimized

        # 添加输出格式要求（如果没有）
        if "输出格式" not in optimized and "output format" not in optimized.lower():
            optimized += "\n\n请以清晰的格式输出结果。"

        # 更新提示词
        prompt["template"] = optimized
        prompt["optimized"] = True
        prompt["optimization_criteria"] = criteria
        prompt["updated_at"] = str(asyncio.get_event_loop().time())

        return {
            "prompt_id": prompt_id,
            "optimized_template": optimized,
            "optimizations_applied": ["清理空格", "添加清晰指令", "格式化要求"],
            "message": "Prompt optimized successfully"
        }

    def _validate_prompt(self, template: str) -> Dict[str, Any]:
        """验证提示词模板"""
        if not template or not template.strip():
            return {"valid": False, "error": "Template cannot be empty"}

        # 检查模板语法
        issues = []

        # 检查是否有未闭合的变量标记
        open_braces = template.count("{")
        close_braces = template.count("}")
        if open_braces != close_braces:
            issues.append("Unclosed variable braces")

        # 检查是否包含明确的任务指令
        if not any(word in template for word in ["请", "你", "任务", "目标", "要求"]):
            issues.append("Missing clear task instruction")

        # 检查长度
        if len(template) > 10000:
            issues.append("Template too long (>10000 characters)")
        elif len(template) < 10:
            issues.append("Template too short (<10 characters)")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "length": len(template),
            "word_count": len(template.split())
        }

    def _load_default_prompts(self) -> None:
        """加载默认提示词"""
        self._prompts = {
            "query_analyzer": {
                "id": "query_analyzer",
                "agent_type": "query_analyzer",
                "template": """你是一个政策查询分析专家。请分析用户的问题并提取以下信息：

1. 查询意图：{intent_options}
2. 关键实体：政策类型、部门、时间、地点、金额等
3. 用户背景：企业类型、规模、行业等
4. 具体需求：想了解什么、想解决什么问题

用户问题：{query}

请以JSON格式输出分析结果。""",
                "variables": ["intent_options", "query"],
                "description": "查询分析提示词",
                "created_at": "2024-01-01T00:00:00Z"
            },
            "policy_analyzer": {
                "id": "policy_analyzer",
                "agent_type": "policy_analyzer",
                "template": """你是一个政策分析专家。基于以下政策文档和用户问题，请提供准确、详细的解答：

政策文档：
{policy_content}

用户问题：{query}

分析要求：
1. 直接回答用户问题
2. 引用相关政策条款
3. 说明适用条件
4. 提供申请步骤（如适用）
5. 注意事项和常见问题

请确保回答准确、易懂、实用。""",
                "variables": ["policy_content", "query"],
                "description": "政策分析提示词",
                "created_at": "2024-01-01T00:00:00Z"
            },
            "answer_generator": {
                "id": "answer_generator",
                "agent_type": "answer_generator",
                "template": """基于以下分析结果，生成最终的回答：

查询分析：{query_analysis}
政策分析：{policy_analysis}
检索结果：{retrieval_results}

请生成一个完整、准确、易读的最终答案，包括：
1. 直接回答
2. 政策依据
3. 操作指南
4. 注意事项
5. 后续建议""",
                "variables": ["query_analysis", "policy_analysis", "retrieval_results"],
                "description": "答案生成提示词",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }

    async def format_prompt(self, prompt_id: str, variables: Dict[str, Any]) -> Optional[str]:
        """格式化提示词模板"""
        if prompt_id not in self._prompts:
            return None

        prompt = self._prompts[prompt_id]
        template = prompt["template"]

        try:
            # 替换变量
            formatted = template.format(**variables)
            return formatted
        except KeyError as e:
            logger.error(f"Missing variable for prompt {prompt_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error formatting prompt {prompt_id}: {e}")
            return None

    def export_prompts(self, file_path: str) -> bool:
        """导出提示词到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export prompts: {e}")
            return False

    def import_prompts(self, file_path: str) -> bool:
        """从文件导入提示词"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported = json.load(f)

            # 合并导入的提示词
            for prompt_id, prompt in imported.items():
                self._prompts[prompt_id] = prompt

            return True
        except Exception as e:
            logger.error(f"Failed to import prompts: {e}")
            return False