"""
意图路由Agent - 智能路由控制器
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime

from autogen_core import MessageContext

from ..base.base_agent import PolicyAgentBase
from .prompt import intent_system_instruction, intent_user_prompt
from .llm_classifier import LLMIntentClassifier
from ...models.base import (
    AgentType,
    UUID,
    UserQuery,
    QueryAnalysis,
    QueryIntent,
    PolicyType,
    BaseModel,
    Field
)

# 尝试导入jieba
try:
    import jieba
except ImportError:
    jieba = None


class IntentClassification(BaseModel):
    """意图分类结果"""
    intent_type: str  # 主要意图类型
    sub_intent: Optional[str] = None  # 子意图
    confidence: float = Field(ge=0, le=1)  # 置信度
    entities: Dict[str, Any] = Field(default_factory=dict)  # 提取的实体
    processing_chain: List[str] = Field(default_factory=list)  # 建议的处理链
    requires_parallel: bool = False  # 是否需要并行处理
    fallback_intent: Optional[str] = None  # 备选意图


class IntentRouterAgent(PolicyAgentBase):
    """意图路由Agent - 作为系统的总控制器"""

    def __init__(self, model_client=None, **kwargs):
        super().__init__(
            agent_type=AgentType.QUERY_ANALYZER,
            name="IntentRouter",
            description="智能识别用户意图并路由到相应的处理链",
            **kwargs
        )
        self.model_client = model_client
        self._llm_classifier = LLMIntentClassifier()

        # 意图分类器
        self.intent_classifiers = {
            "greeting": {
                "keywords": ["你好", "hello", "hi", "您好", "在吗", "在不在"],
                "patterns": [r"^(你好|您好|hello|hi)[\s,.!?]*$", r"^(在吗|在不在)[\s,.!?]*$"],
                "agent": "chat_agent",
                "response_type": "casual"
            },
            "farewell": {
                "keywords": ["再见", "bye", "拜拜", "谢谢", "感谢"],
                "patterns": [r"^(再见|拜拜|谢谢|感谢|bye)[\s,.!?]*$"],
                "agent": "chat_agent",
                "response_type": "farewell"
            },
            "casual_chat": {
                "keywords": ["你是谁", "干嘛的", "帮助", "介绍一下"],
                "patterns": [r"你是谁|介绍一下|你能做什么"],
                "agent": "chat_agent",
                "response_type": "introduction"
            },
            "policy_inquiry": {
                "keywords": ["政策", "补贴", "申请", "条件", "流程"],
                "sub_intents": {
                    "eligibility": ["资格", "条件", "符合", "谁能", "什么人"],
                    "benefit": ["多少钱", "补贴", "补助", "金额", "标准"],
                    "process": ["怎么申请", "流程", "步骤", "如何", "办理"],
                    "deadline": ["截止", "时间", "什么时候", "日期", "期限"],
                    "documents": ["材料", "证件", "文件", "需要什么"],
                    "contact": ["电话", "地址", "联系", "咨询", "哪里"]
                },
                "processing_chains": {
                    "kb_chain": ["knowledge_retriever", "policy_analyzer", "answer_generator"],
                    "graph_chain": ["graph_retriever", "policy_analyzer", "answer_generator"],
                    "hybrid_chain": ["knowledge_retriever", "graph_retriever", "policy_analyzer", "answer_generator"]
                },
                "agent": "policy_agent",
                "response_type": "structured"
            },
            "calculation": {
                "keywords": ["计算", "算算", "多少钱", "补贴金额"],
                "patterns": [r"计算|算算|帮我算|多少钱"],
                "agent": "calculation_agent",
                "response_type": "numerical"
            },
            "comparison": {
                "keywords": ["比较", "区别", "差异", "不同", "对比"],
                "patterns": [r"比较|区别|差异|哪个好"],
                "agent": "comparison_agent",
                "response_type": "comparison"
            },
            "status_inquiry": {
                "keywords": ["进度", "状态", "查询进度", "审核"],
                "patterns": [r"进度|状态|查询.*状态|审核.*怎么样"],
                "agent": "status_agent",
                "response_type": "status"
            },
            "recommendation": {
                "keywords": ["推荐", "建议", "哪个好", "选择"],
                "patterns": [r"推荐|建议|.*哪个好|怎么选择"],
                "agent": "recommendation_agent",
                "response_type": "recommendation"
            }
        }

        # 处理链配置
        self.chain_configs = {
            "kb_chain": {
                "name": "知识库检索链",
                "agents": ["KnowledgeRetrieverAgent", "PolicyAnalyzerAgent", "AnswerGeneratorAgent"],
                "suitable_for": ["具体政策查询", "申请流程", "材料清单"],
                "priority": 1
            },
            "graph_chain": {
                "name": "图谱检索链",
                "agents": ["GraphRetrieverAgent", "PolicyAnalyzerAgent", "AnswerGeneratorAgent"],
                "suitable_for": ["政策关系", "部门职责", "影响范围"],
                "priority": 2
            },
            "hybrid_chain": {
                "name": "混合检索链",
                "agents": ["KnowledgeRetrieverAgent", "GraphRetrieverAgent", "PolicyAnalyzerAgent", "AnswerGeneratorAgent"],
                "suitable_for": ["复杂查询", "跨领域问题", "综合性咨询"],
                "priority": 3,
                "requires_parallel": True
            },
            "calculation_chain": {
                "name": "计算链",
                "agents": ["PolicyExtractorAgent", "CalculationEngine", "ResultFormatter"],
                "suitable_for": ["补贴计算", "金额估算"],
                "priority": 4
            },
            "comparison_chain": {
                "name": "比较链",
                "agents": ["MultiPolicyRetriever", "PolicyComparator", "ComparisonFormatter"],
                "suitable_for": ["政策比较", "方案选择"],
                "priority": 5
            }
        }

    async def process_request(self, request: UserQuery, context: MessageContext) -> IntentClassification:
        """处理请求并进行智能路由"""
        self.logger.info(f"Routing query: {request.text[:50]}...")

        start_time = asyncio.get_event_loop().time()

        try:
            # 1. 文本预处理
            cleaned_text = self._preprocess_text(request.text)

            # 2. 意图分类（优先 LLM，失败回退规则）
            classification = await self._classify_intent_llm_first(cleaned_text)

            # 3. 实体提取
            entities = await self._extract_entities(cleaned_text)

            # 4. 确定处理链
            processing_chain = await self._determine_processing_chain(classification, entities)

            # 5. 优化路由决策
            final_decision = await self._optimize_routing_decision(
                classification, entities, processing_chain
            )

            # 构建路由结果
            result = IntentClassification(
                intent_type=classification["intent_type"],
                sub_intent=classification.get("sub_intent"),
                confidence=classification["confidence"],
                entities=entities,
                processing_chain=processing_chain["chain"],
                requires_parallel=processing_chain.get("parallel", False),
                fallback_intent=classification.get("fallback")
            )

            # 更新指标
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(processing_time)

            self.logger.info(
                f"Routed to {result.intent_type} -> {result.processing_chain} "
                f"(confidence: {result.confidence:.2f})"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error routing query: {e}", exc_info=True)
            self.metrics["errors"] += 1

            # 返回默认路由
            return IntentClassification(
                intent_type="policy_inquiry",
                confidence=0.5,
                processing_chain=["kb_chain"],
                fallback_intent="default_handler"
            )

    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    async def _classify_intent_llm_first(self, text: str) -> Dict[str, Any]:
        """优先使用 LLM 进行意图分类，失败则回退规则。"""
        llm = await self._llm_classify(text)
        if llm:
            # 期望 llm = {intent, sub_intent, confidence, chains, requires_parallel}
            intent = llm.get("intent") or "policy_inquiry"
            sub_intent = llm.get("sub_intent") if llm.get("sub_intent") not in [None, "null", "None", ""] else None
            try:
                confidence = float(llm.get("confidence", 0.6))
            except Exception:
                confidence = 0.6
            # 记下 LLM 的建议链（用于优化决策）
            llm_chains = llm.get("chains") or []
            requires_parallel = bool(llm.get("requires_parallel", False))

            return {
                "intent_type": intent,
                "sub_intent": sub_intent,
                "confidence": confidence,
                "llm_chains": llm_chains,
                "llm_parallel": requires_parallel
            }

        # 回退：规则分类
        return await self._classify_intent(text)

    async def _llm_classify(self, text: str) -> Optional[Dict[str, Any]]:
        """调用 Autogen AgentChat 进行意图分类，严格 JSON 返回。失败返回 None。"""
        try:
            return await self._llm_classifier.classify(text)
        except Exception:
            return None

    async def _classify_intent(self, text: str) -> Dict[str, Any]:
        """分类意图"""
        best_match = {"intent_type": "policy_inquiry", "confidence": 0.0}

        # 遍历所有意图分类器
        for intent_type, config in self.intent_classifiers.items():
            confidence = 0.0

            # 关键词匹配
            keyword_matches = 0
            for keyword in config.get("keywords", []):
                if keyword in text.lower():
                    keyword_matches += 1
                    confidence += 0.2

            # 模式匹配
            pattern_matches = 0
            for pattern in config.get("patterns", []):
                if re.search(pattern, text, re.IGNORECASE):
                    pattern_matches += 1
                    confidence += 0.3

            # 调整置信度
            confidence = min(confidence, 1.0)

            # 更新最佳匹配
            if confidence > best_match["confidence"]:
                best_match = {
                    "intent_type": intent_type,
                    "confidence": confidence,
                    "keyword_matches": keyword_matches,
                    "pattern_matches": pattern_matches
                }

            # 检查子意图
            if "sub_intents" in config and intent_type == "policy_inquiry":
                sub_intent = self._classify_sub_intent(text, config["sub_intents"])
                if sub_intent:
                    best_match["sub_intent"] = sub_intent
                    best_match["confidence"] += 0.1

        return best_match

    def _classify_sub_intent(self, text: str, sub_intents: Dict[str, List[str]]) -> Optional[str]:
        """分类子意图"""
        for sub_intent, keywords in sub_intents.items():
            for keyword in keywords:
                if keyword in text:
                    return sub_intent
        return None

    async def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {}

        # 政策类型
        entities["policy_types"] = self._extract_policy_types(text)

        # 金额
        entities["amounts"] = self._extract_amounts(text)

        # 时间
        entities["dates"] = self._extract_dates(text)

        # 地点
        entities["locations"] = self._extract_locations(text)

        # 部门
        entities["departments"] = self._extract_departments(text)

        # 目标群体
        entities["target_groups"] = self._extract_target_groups(text)

        return entities

    def _extract_policy_types(self, text: str) -> List[str]:
        """提取政策类型"""
        types = []
        policy_keywords = {
            "补贴": ["补贴", "补助", "津贴"],
            "消费券": ["消费券", "代金券"],
            "以旧换新": ["以旧换新", "换新"],
            "税收优惠": ["税收", "免税", "减税"],
            "住房": ["住房", "租房", "购房"],
            "就业": ["就业", "创业", "失业"]
        }

        for policy_type, keywords in policy_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    types.append(policy_type)
                    break

        return list(set(types))

    def _extract_amounts(self, text: str) -> List[str]:
        """提取金额"""
        patterns = [
            r"(\d+(?:\.\d+)?[万千百]?元)",
            r"(\d+(?:\.\d+)?%)"
        ]
        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            amounts.extend(matches)
        return list(set(amounts))

    def _extract_dates(self, text: str) -> List[str]:
        """提取日期"""
        patterns = [
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(\d{4}-\d{1,2}-\d{1,2})",
            r"(今年|明年|去年|年底|月初|月底)"
        ]
        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        return list(set(dates))

    def _extract_locations(self, text: str) -> List[str]:
        """提取地点"""
        locations = []
        location_keywords = ["济南", "青岛", "烟台", "潍坊", "全省", "市", "区", "县"]
        for keyword in location_keywords:
            if keyword in text:
                locations.append(keyword)
        return list(set(locations))

    def _extract_departments(self, text: str) -> List[str]:
        """提取部门"""
        departments = []
        dept_keywords = [
            "商务厅", "财政局", "发改委", "工信局", "人社局",
            "税务局", "住建局", "教育局", "卫健委"
        ]
        for keyword in dept_keywords:
            if keyword in text:
                departments.append(keyword)
        return list(set(departments))

    def _extract_target_groups(self, text: str) -> List[str]:
        """提取目标群体"""
        groups = []
        group_keywords = [
            "企业", "个人", "大学生", "退役军人", "残疾人",
            "老年人", "低收入家庭", "小微企业"
        ]
        for keyword in group_keywords:
            if keyword in text:
                groups.append(keyword)
        return list(set(groups))

    async def _determine_processing_chain(
        self,
        classification: Dict[str, Any],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """确定处理链"""
        intent_type = classification["intent_type"]

        # 如果 LLM 有建议链，直接采用（必要时并行）
        llm_chains = classification.get("llm_chains") or []
        llm_parallel = bool(classification.get("llm_parallel", False))
        if llm_chains:
            return {"chain": llm_chains, "parallel": llm_parallel}

        # 闲聊类直接返回
        if intent_type in ["greeting", "farewell", "casual_chat", "chit_chat", "general_query"]:
            return {"chain": ["chat_agent"], "parallel": False}

        # 计算类使用计算链
        if intent_type == "calculation":
            return {"chain": ["calculation_chain"], "parallel": False}

        # 比较类使用比较链
        if intent_type == "comparison":
            return {"chain": ["comparison_chain"], "parallel": False}

        # 澄清类
        if intent_type == "clarification":
            return {"chain": ["clarification_chain"], "parallel": False}

        # 政策查询类需要智能选择
        if intent_type == "policy_inquiry":
            return await self._select_policy_chain(classification, entities)

        # 默认使用知识库链
        return {"chain": ["kb_chain"], "parallel": False}

    async def _select_policy_chain(
        self,
        classification: Dict[str, Any],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """智能选择政策查询处理链"""
        chain_scores = {}

        # 基于实体数量打分
        entity_count = sum(len(v) for v in entities.values())

        # 基于查询复杂度打分
        complexity_indicators = {
            "policy_types": len(entities.get("policy_types", [])),
            "departments": len(entities.get("departments", [])),
            "locations": len(entities.get("locations", []))
        }
        complexity_score = sum(complexity_indicators.values())

        # 评估每个链的适合度
        if complexity_score <= 2:
            # 简单查询，使用知识库链
            chain_scores["kb_chain"] = 0.9
            chain_scores["graph_chain"] = 0.3
        elif complexity_score <= 4:
            # 中等复杂度，使用图谱链或混合链
            chain_scores["kb_chain"] = 0.6
            chain_scores["graph_chain"] = 0.7
            chain_scores["hybrid_chain"] = 0.8
        else:
            # 复杂查询，使用混合链
            chain_scores["kb_chain"] = 0.4
            chain_scores["graph_chain"] = 0.6
            chain_scores["hybrid_chain"] = 0.9

        # 特殊情况处理
        sub_intent = classification.get("sub_intent")
        if sub_intent == "comparison":
            chain_scores["comparison_chain"] = 0.95
        elif sub_intent == "benefit":
            chain_scores["calculation_chain"] = 0.8

        # 选择得分最高的链
        best_chain = max(chain_scores, key=chain_scores.get)

        return {
            "chain": [best_chain],
            "parallel": self.chain_configs.get(best_chain, {}).get("requires_parallel", False),
            "scores": chain_scores
        }

    async def _optimize_routing_decision(
        self,
        classification: Dict[str, Any],
        entities: Dict[str, Any],
        processing_chain: Dict[str, Any]
    ) -> Dict[str, Any]:
        """优化路由决策"""
        # 如果置信度太低，考虑并行处理
        if classification["confidence"] < 0.7 and not processing_chain.get("parallel"):
            # 可以同时运行多个链
            alternative_chains = ["kb_chain", "graph_chain"]
            if processing_chain["chain"][0] not in alternative_chains:
                processing_chain["chain"] = alternative_chains
                processing_chain["parallel"] = True
                processing_chain["fallback_chain"] = processing_chain["chain"][0]

        return processing_chain

    def get_metrics(self) -> Dict[str, Any]:
        """获取路由指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "intent_types": len(self.intent_classifiers),
            "chain_configs": len(self.chain_configs),
            "memory_size": len(self.memory.memory_contents) if self.memory else 0
        }
