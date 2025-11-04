"""
查询分析Agent模块 - 负责分析用户查询意图
"""

from typing import Dict, Any, List
import re
from .base_module import BaseAgentModule

class QueryAgent(BaseAgentModule):
    """查询分析Agent"""

    def __init__(self):
        super().__init__("query_analyzer", "1.0.0")
        self.description = "分析用户查询，识别意图和提取关键信息"

        # 意图关键词映射
        self.intent_keywords = {
            "补贴查询": ["补贴", "补助", "津贴", "金额", "多少钱", "多少"],
            "资格条件": ["资格", "条件", "要求", "符合", "能否", "可以"],
            "申请流程": ["申请", "流程", "步骤", "怎么申请", "如何申请"],
            "材料准备": ["材料", "文件", "证件", "需要什么", "准备"],
            "截止时间": ["截止", "时间", "日期", "什么时候", "截止日"],
            "政策咨询": ["政策", "规定", "法规", "办法", "通知"]
        }

        # 实体提取模式
        self.entity_patterns = {
            "金额": r"(\d+元|\d+万|\d+千)",
            "企业类型": r"(小微企业|大型企业|中小企业|个体户|个人)",
            "地区": r"(上海|北京|广州|深圳|全国|全省|全市)",
            "时间": r"(\d{4}年|\d{1,2}月|\d{1,2}日)"
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析查询内容"""
        query = data.get("query", "")
        if not query:
            return {"error": "Query is empty"}

        # 清理查询文本
        query = query.strip()

        # 识别意图
        intent = self._identify_intent(query)

        # 提取实体
        entities = self._extract_entities(query)

        # 提取关键词
        keywords = self._extract_keywords(query)

        # 计算置信度
        confidence = self._calculate_confidence(intent, entities, keywords)

        # 更新数据
        result = {
            "original_query": query,
            "intent": intent,
            "entities": entities,
            "keywords": keywords,
            "confidence": confidence,
            "analysis_time": self.metrics["processed_count"]
        }

        data.update(result)
        return data

    def _identify_intent(self, query: str) -> str:
        """识别查询意图"""
        intent_scores = {}

        for intent, keywords in self.intent_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in query:
                    score += 1
            intent_scores[intent] = score

        # 返回得分最高的意图
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            if intent_scores[best_intent] > 0:
                return best_intent

        return "一般咨询"

    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """提取实体信息"""
        entities = {}

        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, query)
            if matches:
                entities[entity_type] = matches

        return entities

    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        keywords = []

        # 去除标点符号
        cleaned = re.sub(r"[，。！？、]", " ", query)

        # 分词（简单实现）
        words = cleaned.split()

        # 过滤停用词和保留重要词汇
        stop_words = {"的", "了", "是", "在", "我", "想", "知道", "请问", "一下"}
        important_words = {"补贴", "申请", "政策", "条件", "资格", "材料", "流程"}

        for word in words:
            if word not in stop_words and len(word) > 1:
                keywords.append(word)

        # 确保包含重要词汇
        for word in important_words:
            if word in query and word not in keywords:
                keywords.append(word)

        return keywords[:10]  # 限制关键词数量

    def _calculate_confidence(
        self,
        intent: str,
        entities: Dict[str, List[str]],
        keywords: List[str]
    ) -> float:
        """计算分析置信度"""
        confidence = 0.5  # 基础分数

        # 意图明确加分
        if intent != "一般咨询":
            confidence += 0.2

        # 实体数量加分
        entity_count = sum(len(v) for v in entities.values())
        confidence += min(entity_count * 0.1, 0.2)

        # 关键词数量加分
        confidence += min(len(keywords) * 0.02, 0.1)

        return min(confidence, 1.0)