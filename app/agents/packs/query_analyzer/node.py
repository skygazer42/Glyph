"""
查询理解Agent - 分析用户查询意图和提取关键信息
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
import re
from datetime import datetime
import jieba
from autogen_core import MessageContext
from autogen_agentchat.messages import TextMessage
from app.agents.framework.base.base_agent import PolicyAgentBase
from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    UserQuery,
    QueryAnalysis,
    QueryIntent,
    PolicyType,
    UUID
)


class QueryAnalyzerAgent(PolicyAgentBase):
    """查询理解Agent，负责分析用户查询意图"""

    def __init__(self, model_client=None, **kwargs):
        super().__init__(
            agent_type=AgentType.QUERY_ANALYZER,
            name="QueryAnalyzer",
            description="分析用户查询，识别意图和提取关键信息",
            **kwargs
        )
        self.model_client = model_client

        # 意图识别关键词映射
        self.intent_keywords = {
            QueryIntent.ELIGIBILITY_CHECK: [
                "资格", "条件", "符合", "申请资格", "谁能", "什么人",
                "要求", "标准", "门槛", "限制", "需要满足"
            ],
            QueryIntent.BENEFIT_CALCULATION: [
                "多少钱", "补贴", "补助", "金额", "标准", "怎么算",
                "最高", "最低", "比例", "金额", "费用", "优惠"
            ],
            QueryIntent.APPLICATION_PROCESS: [
                "怎么申请", "流程", "步骤", "如何", "办理", "程序",
                "手续", "途径", "方式", "方法", "过程"
            ],
            QueryIntent.DEADLINE_QUERY: [
                "截止", "时间", "什么时候", "日期", "到什么时候",
                "有效期", "期限", "时效", "过期", "年底", "月底"
            ],
            QueryIntent.POLICY_COMPARISON: [
                "比较", "区别", "差异", "不同", "对比", "哪个好",
                "选择", "优缺点", "优势", "更适合"
            ],
            QueryIntent.DOCUMENT_REQUIREMENT: [
                "材料", "证件", "文件", "需要什么", "准备什么",
                "资料", "证明", "表格", "清单", "文档"
            ],
            QueryIntent.CONTACT_INFO: [
                "电话", "地址", "联系", "咨询", "哪里", "部门",
                "机构", "窗口", "网址", "邮箱"
            ],
            QueryIntent.STATUS_INQUIRY: [
                "进度", "状态", "查询进度", "申请状态", "结果",
                "审核", "通过了吗", "怎么样了", "办理进度"
            ]
        }

        # 政策类型关键词
        self.policy_type_keywords = {
            PolicyType.SUBSIDY: ["补贴", "补助", "津贴", "资金"],
            PolicyType.VOUCHER: ["消费券", "代金券", "购物券"],
            PolicyType.REPLACEMENT: ["以旧换新", "换新", "更新"],
            PolicyType.DISCOUNT: ["折扣", "优惠", "减免", "打折"],
            PolicyType.ALLOWANCE: ["津贴", "补贴", "补助"],
            PolicyType.TAX_EXEMPTION: ["免税", "减税", "税收优惠"],
            PolicyType.REGULATION: ["规定", "条例", "法规", "办法"],
            PolicyType.GUIDELINE: ["指南", "指导意见", "方案"]
        }

        # 常见实体模式
        self.entity_patterns = {
            "department": r"(济南市|山东省|商务厅|财政局|发改委|工信局|人社局)",
            "location": r"(济南|青岛|烟台|潍坊|淄博|济宁|泰安|威海|日照|临沂|德州|聊城|滨州|菏泽|全省)",
            "money": r"(\d+(?:\.\d+)?[万千百]?元)",
            "date": r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}月\d{1,2}日)",
            "percentage": r"(\d+(?:\.\d+)?%)"
        }

    async def process_request(self, request: UserQuery, context: MessageContext) -> QueryAnalysis:
        """处理用户查询请求"""
        self.logger.info(f"Processing query: {request.text[:50]}...")

        start_time = asyncio.get_event_loop().time()

        try:
            # 1. 文本预处理
            cleaned_text = self._preprocess_text(request.text)

            # 2. 意图识别
            intent = self._identify_intent(cleaned_text)

            # 3. 实体提取
            entities = self._extract_entities(cleaned_text)

            # 4. 关键词提取
            keywords = self._extract_keywords(cleaned_text)

            # 5. 政策类型识别
            policy_types = self._identify_policy_types(cleaned_text)

            # 6. 约束提取
            time_constraints = self._extract_time_constraints(cleaned_text)
            location_constraints = self._extract_location_constraints(entities)
            target_groups = self._extract_target_groups(cleaned_text)

            # 7. 生成推理过程
            reasoning = self._generate_reasoning(
                intent, entities, keywords, policy_types
            )

            # 8. 计算置信度
            confidence = self._calculate_confidence(
                intent, entities, keywords, policy_types
            )

            # 创建分析结果
            analysis = QueryAnalysis(
                query_id=request.id,
                intent=intent,
                entities=entities,
                keywords=keywords,
                policy_types=policy_types,
                time_constraints=time_constraints,
                location_constraints=location_constraints,
                target_groups=target_groups,
                confidence=confidence,
                reasoning=reasoning
            )

            # 更新指标
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(processing_time)

            self.logger.info(f"Query analyzed in {processing_time:.3f}s, intent: {intent.value}")

            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing query: {e}", exc_info=True)
            self.metrics["errors"] += 1
            # 返回默认分析结果
            return QueryAnalysis(
                query_id=request.id,
                intent=QueryIntent.GENERAL_INQUIRY,
                entities=[],
                keywords=[],
                policy_types=[],
                confidence=0.5,
                reasoning=f"分析出错，使用默认意图: {str(e)}"
            )

    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 去除多余空格和特殊字符
        text = re.sub(r'\s+', ' ', text.strip())
        # 转换为小写（保留中文）
        return text

    def _identify_intent(self, text: str) -> QueryIntent:
        """识别查询意图"""
        intent_scores = {}

        # 计算每个意图的匹配分数
        for intent, keywords in self.intent_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 1
            intent_scores[intent] = score

        # 返回得分最高的意图
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            if intent_scores[best_intent] > 0:
                return best_intent

        # 如果没有匹配的意图，返回通用查询
        return QueryIntent.GENERAL_INQUIRY

    def _extract_entities(self, text: str) -> List[str]:
        """提取命名实体"""
        entities = []

        # 使用正则表达式提取预定义实体
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text)
            entities.extend(matches)

        # 使用 jieba 分词提取其他可能的实体
        if jieba:
            words = jieba.cut(text)
        else:
            self.logger.debug("jieba 未安装，使用空格分词退化处理")
            words = text.split()
        for word in words:
            # 过滤掉太短的词和常见停用词
            if len(word) > 1 and word not in ["的", "是", "在", "有", "和", "与", "或"]:
                entities.append(word)

        # 去重并返回
        return list(set(entities))

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 使用TF-IDF或TextRank等方法提取关键词
        # 这里简化处理，提取重要词汇
        keywords = []

        # 政策相关关键词
        policy_keywords = [
            "补贴", "申请", "条件", "流程", "材料", "时间", "电话",
            "地址", "部门", "标准", "金额", "资格", "要求"
        ]

        for keyword in policy_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords

    def _identify_policy_types(self, text: str) -> List[PolicyType]:
        """识别相关政策类型"""
        identified_types = []

        for policy_type, keywords in self.policy_type_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    identified_types.append(policy_type)
                    break

        return list(set(identified_types))

    def _extract_time_constraints(self, text: str) -> Optional[str]:
        """提取时间约束"""
        # 查找时间相关的表达
        time_patterns = [
            r"今年内", r"年底前", r"本月", r"下月", r"(\d{4})年",
            r"第(\d+)季度", r"上半年", r"下半年"
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def _extract_location_constraints(self, entities: List[str]) -> Optional[str]:
        """从实体中提取地点约束"""
        location_keywords = ["济南", "青岛", "烟台", "全省", "市", "区", "县"]

        for entity in entities:
            for keyword in location_keywords:
                if keyword in entity:
                    return entity

        return None

    def _extract_target_groups(self, text: str) -> List[str]:
        """提取目标群体"""
        target_groups = []

        group_patterns = [
            r"(企业|公司|商户|个体户)",
            r"(个人|居民|市民|农户)",
            r"(大学生|毕业生|退役军人|残疾人)",
            r"(小微企业|规模企业|国企|民企)"
        ]

        for pattern in group_patterns:
            matches = re.findall(pattern, text)
            target_groups.extend(matches)

        return list(set(target_groups))

    def _generate_reasoning(
        self,
        intent: QueryIntent,
        entities: List[str],
        keywords: List[str],
        policy_types: List[PolicyType]
    ) -> str:
        """生成推理过程说明"""
        reasoning_parts = []

        reasoning_parts.append(f"识别意图为: {intent.value}")

        if entities:
            reasoning_parts.append(f"提取实体: {', '.join(entities[:5])}")

        if policy_types:
            reasoning_parts.append(f"政策类型: {', '.join([p.value for p in policy_types])}")

        if keywords:
            reasoning_parts.append(f"关键词: {', '.join(keywords[:5])}")

        return "; ".join(reasoning_parts)

    def _calculate_confidence(
        self,
        intent: QueryIntent,
        entities: List[str],
        keywords: List[str],
        policy_types: List[PolicyType]
    ) -> float:
        """计算分析置信度"""
        confidence = 0.5  # 基础置信度

        # 意图明确度
        if intent != QueryIntent.GENERAL_INQUIRY:
            confidence += 0.2

        # 实体数量
        if len(entities) >= 3:
            confidence += 0.1
        elif len(entities) >= 5:
            confidence += 0.2

        # 关键词匹配
        if len(keywords) >= 2:
            confidence += 0.1
        elif len(keywords) >= 4:
            confidence += 0.2

        # 政策类型识别
        if len(policy_types) > 0:
            confidence += 0.1

        # 确保置信度在0-1之间
        return min(max(confidence, 0.0), 1.0)

    def get_metrics(self) -> Dict[str, Any]:
        """获取Agent指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "memory_size": len(self.memory.memory_contents) if self.memory else 0
        }
