"""
检索Agent模块 - 负责从知识库检索相关信息
"""

from typing import Dict, Any, List, Optional
import json
from .base_module import BaseAgentModule

class RetrievalAgent(BaseAgentModule):
    """检索Agent"""

    def __init__(self):
        super().__init__("retrieval_agent", "1.0.0")
        self.description = "从知识库检索相关政策信息"

        # 模拟政策知识库
        self.knowledge_base = {
            "创业补贴": {
                "title": "大学生创业补贴政策",
                "content": "毕业5年内的大学生在我市初次创办企业，可申请3-10万元创业补贴。",
                "conditions": [
                    "毕业5年内的全日制普通高校毕业生",
                    "在我市初次创办企业并担任法定代表人",
                    "企业正常经营6个月以上",
                    "缴纳社会保险3个月以上"
                ],
                "amount": "3-10万元",
                "department": "市人社局",
                "phone": "12333"
            },
            "科技补贴": {
                "title": "科技创新券政策",
                "content": "小微企业、创业团队购买科技服务可使用科技创新券，最高额度5万元。",
                "conditions": [
                    "在本市注册的小微企业",
                    "或未在本市注册的创业团队",
                    "具有健全的财务制度",
                    "无不良信用记录"
                ],
                "amount": "最高5万元",
                "department": "市科技局",
                "phone": "56789"
            },
            "房租补贴": {
                "title": "创业场地房租补贴",
                "content": "入驻政府认定的创业孵化基地，可享受3年内房租补贴。",
                "conditions": [
                    "初次创业的各类劳动者",
                    "入驻认定的创业孵化基地",
                    "签订1年以上租赁合同",
                    "正常经营3个月以上"
                ],
                "amount": "不超过实际房租的50%",
                "department": "市就业服务中心",
                "phone": "98765"
            },
            "培训补贴": {
                "title": "职业技能培训补贴",
                "content": "参加职业技能培训并取得证书，可申请培训补贴。",
                "conditions": [
                    "本市户籍人员",
                    "或在本市缴纳失业保险的非本市户籍人员",
                    "参加职业技能培训",
                    "取得职业资格证书"
                ],
                "amount": "300-3000元",
                "department": "市人社局",
                "phone": "12333"
            }
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """检索相关政策"""
        intent = data.get("intent", "")
        keywords = data.get("keywords", [])
        entities = data.get("entities", {})

        # 根据意图和关键词检索
        results = self._search_policies(intent, keywords, entities)

        # 对结果进行排序和过滤
        sorted_results = self._rank_results(results, keywords, entities)

        # 更新数据
        result = {
            "retrieval_results": sorted_results,
            "result_count": len(sorted_results),
            "search_strategy": self._get_search_strategy(intent, keywords)
        }

        data.update(result)
        return data

    def _search_policies(
        self,
        intent: str,
        keywords: List[str],
        entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """搜索相关政策"""
        results = []
        search_terms = keywords.copy()

        # 添加实体到搜索词
        for entity_list in entities.values():
            search_terms.extend(entity_list)

        # 根据意图确定搜索重点
        intent_map = {
            "补贴查询": ["补贴", "补助", "津贴"],
            "资格条件": ["条件", "资格", "要求"],
            "申请流程": ["申请", "流程", "步骤"],
            "材料准备": ["材料", "文件", "证件"],
            "截止时间": ["时间", "日期", "截止"]
        }

        if intent in intent_map:
            search_terms.extend(intent_map[intent])

        # 在知识库中搜索
        for policy_id, policy in self.knowledge_base.items():
            score = self._calculate_relevance_score(
                policy, search_terms, intent
            )
            if score > 0:
                result = policy.copy()
                result["id"] = policy_id
                result["relevance_score"] = score
                results.append(result)

        return results

    def _calculate_relevance_score(
        self,
        policy: Dict[str, Any],
        search_terms: List[str],
        intent: str
    ) -> float:
        """计算相关性得分"""
        score = 0.0
        text = f"{policy['title']} {policy['content']}".lower()

        # 关键词匹配
        for term in search_terms:
            if term.lower() in text:
                score += 1.0

        # 标题匹配加分
        for term in search_terms:
            if term.lower() in policy['title'].lower():
                score += 2.0

        # 意图相关加分
        if "补贴" in text and "补贴" in intent:
            score += 1.0
        if "申请" in text and "申请" in intent:
            score += 1.0

        return score

    def _rank_results(
        self,
        results: List[Dict[str, Any]],
        keywords: List[str],
        entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """对结果排序"""
        # 按相关性得分排序
        sorted_results = sorted(
            results,
            key=lambda x: x["relevance_score"],
            reverse=True
        )

        # 限制返回数量
        return sorted_results[:5]

    def _get_search_strategy(self, intent: str, keywords: List[str]) -> str:
        """获取搜索策略说明"""
        if keywords:
            return f"基于关键词'{', '.join(keywords[:3])}'和意图'{intent}'进行搜索"
        else:
            return f"基于意图'{intent}'进行搜索"

    def add_policy(self, policy_id: str, policy_data: Dict[str, Any]):
        """添加新政策到知识库"""
        self.knowledge_base[policy_id] = policy_data
        self.metrics["knowledge_size"] = len(self.knowledge_base)

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """获取特定政策"""
        return self.knowledge_base.get(policy_id)