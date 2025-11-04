"""
简化的Agent控制器 - 更清晰的架构设计
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging

from models.base import AgentType, MessageType

logger = logging.getLogger(__name__)


class SimpleAgent:
    """简化的Agent基类"""

    def __init__(self, name: str, agent_type: AgentType):
        self.name = name
        self.agent_type = agent_type
        self.is_active = True

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据的抽象方法，子类必须实现"""
        raise NotImplementedError

    async def start(self):
        """启动Agent"""
        self.is_active = True
        logger.info(f"Agent {self.name} started")

    async def stop(self):
        """停止Agent"""
        self.is_active = False
        logger.info(f"Agent {self.name} stopped")


class MessageQueue:
    """简单的消息队列"""

    def __init__(self):
        self._queue = asyncio.Queue()
        self._subscribers: Dict[str, List[Callable]] = {}

    async def publish(self, topic: str, data: Dict[str, Any]):
        """发布消息到主题"""
        message = {
            "topic": topic,
            "data": data,
            "timestamp": datetime.now()
        }
        await self._queue.put(message)

        # 通知订阅者
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")

    def subscribe(self, topic: str, callback: Callable):
        """订阅主题"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    async def get(self) -> Optional[Dict[str, Any]]:
        """获取消息"""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None


class AgentHub:
    """Agent中心 - 管理所有Agent"""

    def __init__(self):
        self.agents: Dict[str, SimpleAgent] = {}
        self.message_queue = MessageQueue()
        self.workflows: Dict[str, List[str]] = {}
        self.running = False

    def register(self, agent: SimpleAgent):
        """注册Agent"""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def create_workflow(self, name: str, agent_names: List[str]):
        """创建工作流"""
        # 验证所有Agent都存在
        for agent_name in agent_names:
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} not found")

        self.workflows[name] = agent_names
        logger.info(f"Created workflow: {name} -> {agent_names}")

    async def run_workflow(self, workflow_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行工作流"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow {workflow_name} not found")

        agent_names = self.workflows[workflow_name]
        current_data = input_data

        # 依次执行每个Agent
        for agent_name in agent_names:
            agent = self.agents[agent_name]
            if not agent.is_active:
                logger.warning(f"Agent {agent_name} is not active, skipping")
                continue

            logger.info(f"Running agent: {agent_name}")
            current_data = await agent.handle(current_data)

            # 如果Agent返回错误，停止工作流
            if current_data.get("error"):
                logger.error(f"Agent {agent_name} returned error: {current_data['error']}")
                break

        return current_data

    async def start(self):
        """启动所有Agent"""
        self.running = True
        for agent in self.agents.values():
            await agent.start()
        logger.info("AgentHub started")

    async def stop(self):
        """停止所有Agent"""
        self.running = False
        for agent in self.agents.values():
            await agent.stop()
        logger.info("AgentHub stopped")

    def get_agent(self, name: str) -> Optional[SimpleAgent]:
        """获取Agent实例"""
        return self.agents.get(name)


# 示例Agent实现
class QueryAnalyzer(SimpleAgent):
    """查询分析Agent"""

    def __init__(self):
        super().__init__("query_analyzer", AgentType.QUERY_ANALYZER)

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析用户查询"""
        query = data.get("query", "")

        # 简单的意图识别
        if "补贴" in query or "金额" in query:
            intent = "benefit_calculation"
        elif "资格" in query or "条件" in query:
            intent = "eligibility_check"
        elif "申请" in query or "流程" in query:
            intent = "application_process"
        else:
            intent = "general_inquiry"

        # 提取关键信息
        keywords = []
        if "企业" in query:
            keywords.append("企业")
        if "个人" in query:
            keywords.append("个人")
        if "小微企业" in query:
            keywords.append("小微企业")

        result = {
            "query": query,
            "intent": intent,
            "keywords": keywords,
            "confidence": 0.8
        }

        # 更新数据
        data.update(result)
        return data


class PolicyRetriever(SimpleAgent):
    """政策检索Agent"""

    def __init__(self):
        super().__init__("policy_retriever", AgentType.POLICY_RETRIEVER)
        # 模拟政策数据库
        self.policies = {
            "企业补贴": {
                "title": "小微企业创业补贴政策",
                "content": "符合条件的小微企业可申请最高10万元创业补贴",
                "conditions": ["注册时间满1年", "员工人数少于50人", "年营业额低于500万"]
            },
            "个人补贴": {
                "title": "个人技能提升补贴",
                "content": "个人参加职业技能培训可申请最高3000元补贴",
                "conditions": ["持有本地户口", "取得相关证书", "未享受过同类补贴"]
            }
        }

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """检索相关政策"""
        keywords = data.get("keywords", [])

        # 根据关键词检索政策
        retrieved_policies = []
        for keyword in keywords:
            if keyword in self.policies:
                retrieved_policies.append(self.policies[keyword])

        result = {
            "retrieved_policies": retrieved_policies,
            "count": len(retrieved_policies)
        }

        data.update(result)
        return data


class AnswerGenerator(SimpleAgent):
    """答案生成Agent"""

    def __init__(self):
        super().__init__("answer_generator", AgentType.ANSWER_GENERATOR)

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终答案"""
        query = data.get("query", "")
        intent = data.get("intent", "")
        policies = data.get("retrieved_policies", [])

        # 生成答案
        if policies:
            answer = f"根据您的问题：{query}\n\n"
            answer += "为您找到以下相关政策：\n\n"

            for i, policy in enumerate(policies, 1):
                answer += f"{i}. {policy['title']}\n"
                answer += f"   {policy['content']}\n"
                answer += f"   申请条件：{', '.join(policy['conditions'])}\n\n"

            answer += "如需了解更多详情或申请流程，请咨询相关部门。"
        else:
            answer = f"抱歉，暂未找到与您的问题相关的政策信息。\n"
            answer += "建议您：\n"
            answer += "1. 使用更具体的关键词\n"
            answer += "2. 咨询当地政策服务热线\n"
            answer += "3. 访问政府官方网站查询"

        result = {
            "answer": answer,
            "generated_at": datetime.now().isoformat()
        }

        data.update(result)
        return data


# 使用示例
async def main():
    """主函数 - 演示如何使用"""
    # 创建Agent中心
    hub = AgentHub()

    # 注册Agent
    hub.register(QueryAnalyzer())
    hub.register(PolicyRetriever())
    hub.register(AnswerGenerator())

    # 创建工作流
    hub.create_workflow("policy_qa", [
        "query_analyzer",
        "policy_retriever",
        "answer_generator"
    ])

    # 启动Agent中心
    await hub.start()

    # 测试查询
    test_queries = [
        {"query": "小微企业能申请多少补贴？"},
        {"query": "个人技能培训有什么补贴政策？"},
        {"query": "申请创业补贴需要什么条件？"}
    ]

    for query_data in test_queries:
        print(f"\n{'='*50}")
        print(f"用户查询：{query_data['query']}")
        print(f"{'='*50}")

        # 运行工作流
        result = await hub.run_workflow("policy_qa", query_data)

        # 输出答案
        print("\n回答：")
        print(result.get("answer", "抱歉，无法生成答案"))
        print(f"\n处理时间：{result.get('generated_at', 'N/A')}")

    # 停止Agent中心
    await hub.stop()


if __name__ == "__main__":
    asyncio.run(main())