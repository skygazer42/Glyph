"""
增强版意图路由Agent - 使用统一提示词管理系统
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from autogen_core import MessageContext
from autogen_agentchat.messages import TextMessage

from ..chatdb.base_agent import BaseAgent
from ...models.base import UserQuery, UUID
from ...prompts import get_prompt_manager


class IntentClassification:
    """意图分类结果"""
    def __init__(self, data: Dict[str, Any]):
        self.intent_type = data.get("intent_type", "policy_inquiry")
        self.confidence = data.get("confidence", 0.5)
        self.keywords = data.get("keywords", [])
        self.entities = data.get("entities", {})
        self.reasoning = data.get("reasoning", "")


class EnhancedIntentRouterAgent(BaseAgent):
    """增强版意图路由Agent - 使用提示词管理系统"""

    def __init__(self, model_client=None, **kwargs):
        super().__init__(
            agent_id="enhanced_intent_router",
            agent_name="EnhancedIntentRouter",
            description="智能识别用户意图并路由到相应的处理链",
            **kwargs
        )

        self.model_client = model_client
        self.prompt_manager = get_prompt_manager()

        # 预定义的意图到处理链映射
        self.intent_to_chain = {
            "greeting": "chat",
            "farewell": "chat",
            "casual_chat": "chat",
            "policy_inquiry": "simple_query",
            "eligibility_check": "simple_query",
            "benefit_calculation": "calculation",
            "application_process": "simple_query",
            "deadline_query": "simple_query",
            "policy_comparison": "comparison",
            "contact_info": "simple_query"
        }

    async def process_request(
        self,
        request: UserQuery,
        context: MessageContext
    ) -> IntentClassification:
        """处理用户查询，识别意图"""

        self.logger.info(f"Processing query: {request.text[:50]}...")

        try:
            # 步骤1：使用LLM进行意图分类
            intent_result = await self._classify_intent_with_llm(request.text)

            # 步骤2：提取实体
            entities = await self._extract_entities_with_llm(request.text)

            # 步骤3：选择处理链
            processing_chain = await self._select_processing_chain(
                intent_result,
                entities
            )

            # 步骤4：构建结果
            result = IntentClassification({
                "intent_type": intent_result.intent_type,
                "confidence": intent_result.confidence,
                "keywords": intent_result.keywords,
                "entities": entities,
                "reasoning": intent_result.reasoning
            })

            # 添加处理链信息
            result.processing_chain = processing_chain.get("agents", [])
            result.requires_parallel = processing_chain.get("parallel", False)

            self.logger.info(
                f"Intent classified: {result.intent_type} "
                f"(confidence: {result.confidence:.2f}) "
                f"→ chain: {result.processing_chain}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error in intent classification: {e}")
            # 返回默认分类
            return IntentClassification({
                "intent_type": "policy_inquiry",
                "confidence": 0.5,
                "keywords": [],
                "entities": {},
                "reasoning": "Classification failed, using default"
            })

    async def _classify_intent_with_llm(self, query: str) -> IntentClassification:
        """使用LLM进行意图分类"""

        # 获取意图分类提示词
        prompt = self.prompt_manager.get_prompt(
            "intent.classification",
            query=query
        )

        # 调用LLM
        response = await self._call_llm(prompt)

        try:
            # 解析JSON响应
            result_data = json.loads(response)
            return IntentClassification(result_data)
        except json.JSONDecodeError:
            # 如果解析失败，尝试提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                return IntentClassification(result_data)
            else:
                # 完全失败，返回默认
                self.logger.warning(f"Failed to parse intent classification: {response}")
                return IntentClassification({
                    "intent_type": "policy_inquiry",
                    "confidence": 0.3,
                    "keywords": [],
                    "entities": {},
                    "reasoning": "Parse error"
                })

    async def _extract_entities_with_llm(self, query: str) -> Dict[str, Any]:
        """使用LLM提取实体"""

        # 获取实体提取提示词
        prompt = self.prompt_manager.get_prompt(
            "intent.entity_extraction",
            query=query
        )

        # 调用LLM
        response = await self._call_llm(prompt)

        try:
            # 解析JSON响应
            result_data = json.loads(response)
            return result_data.get("entities", {})
        except:
            # 解析失败，返回空实体
            self.logger.warning(f"Failed to parse entities: {response}")
            return {}

    async def _select_processing_chain(
        self,
        intent: IntentClassification,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """选择处理链"""

        # 基本处理链映射
        base_chain = self.intent_to_chain.get(
            intent.intent_type,
            "simple_query"
        )

        # 计算复杂度
        entity_count = sum(len(v) for v in entities.values())
        complexity = "simple" if entity_count <= 3 else "complex"

        # 获取链选择提示词
        prompt = self.prompt_manager.get_prompt(
            "intent.chain_selection",
            intent_type=intent.intent_type,
            confidence=intent.confidence,
            entity_count=entity_count,
            complexity=complexity
        )

        # 调用LLM
        response = await self._call_llm(prompt)

        try:
            # 解析响应
            result_data = json.loads(response)
            return {
                "chain": result_data.get("selected_chain", base_chain),
                "agents": result_data.get("expected_agents", []),
                "parallel": result_data.get("parallel_processing", False),
                "reasoning": result_data.get("reasoning", "")
            }
        except:
            # 解析失败，使用默认
            default_agents = self._get_default_agents(base_chain)
            return {
                "chain": base_chain,
                "agents": default_agents,
                "parallel": False,
                "reasoning": "Using default chain"
            }

    def _get_default_agents(self, chain_name: str) -> List[str]:
        """获取默认的Agent列表"""
        agent_mapping = {
            "chat": ["chat_agent"],
            "simple_query": ["policy_retriever", "policy_analyzer", "answer_generator"],
            "calculation": ["policy_retriever", "policy_analyzer", "calculation_agent", "answer_generator"],
            "comparison": ["policy_retriever", "policy_comparator", "answer_generator"],
            "complex_query": ["policy_retriever", "policy_analyzer", "policy_comparator", "calculation_agent"]
        }
        return agent_mapping.get(chain_name, ["policy_retriever", "policy_analyzer"])

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM模型"""
        if self.model_client:
            # 使用配置的模型客户端
            response = await self.model_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            return response.content
        else:
            # 使用默认的generate_response方法
            response = await self.generate_response(prompt)
            return response

    def get_supported_intents(self) -> List[str]:
        """获取支持的意图列表"""
        return list(self.intent_to_chain.keys())

    def get_prompt_stats(self) -> Dict[str, Any]:
        """获取提示词统计信息"""
        return self.prompt_manager.get_stats()

    async def update_prompt(self, category: str, name: str, content: str) -> bool:
        """更新提示词"""
        prompt_name = f"{category}.{name}"
        return self.prompt_manager.update_prompt(prompt_name, content)