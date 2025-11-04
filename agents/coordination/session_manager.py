"""
会话管理Agent - 管理用户会话和上下文
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from collections import deque

import os
from autogen_core import MessageContext
from autogen_agentchat.messages import TextMessage

from ..base.base_agent import PolicyAgentBase
from ...models.base import (
    AgentType,
    UUID,
    UserQuery,
    FinalAnswer,
    BaseModel,
    Field
)


class SessionContext(BaseModel):
    """会话上下文"""
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    query_count: int = 0
    queries: List[Dict[str, Any]] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None


class SessionManagerAgent(PolicyAgentBase):
    """会话管理Agent，负责管理用户会话状态和上下文"""

    def __init__(self, session_timeout: int = 3600, max_history: int = 50, max_turns: Optional[int] = None, history_window: Optional[int] = None, **kwargs):
        super().__init__(
            agent_type=AgentType.COORDINATOR,
            name="SessionManager",
            description="管理用户会话和对话上下文",
            **kwargs
        )

        self.session_timeout = session_timeout  # 会话超时时间（秒）
        self.max_history = max_history  # 最大历史记录数（条目）
        # 多轮对话参数（支持.env 配置）
        self.max_turns = max_turns if max_turns is not None else int(os.getenv("CONVERSATION__MAX_TURNS", os.getenv("CONVERSATION_MAX_TURNS", "20")))
        self.history_window = history_window if history_window is not None else int(os.getenv("CONVERSATION__HISTORY_WINDOW", os.getenv("CONVERSATION_HISTORY_WINDOW", "5")))

        # 会话存储
        self.sessions: Dict[str, SessionContext] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # 用户ID到会话ID的映射

        # 定期清理过期会话
        asyncio.create_task(self._cleanup_expired_sessions())

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> Dict[str, Any]:
        """处理会话管理请求"""
        action = request.get("action")

        if action == "create_or_update":
            return await self._create_or_update_session(request)
        elif action == "get":
            return await self._get_session(request.get("session_id"))
        elif action == "list":
            return await self._list_user_sessions(request.get("user_id"))
        elif action == "delete":
            return await self._delete_session(request.get("session_id"))
        elif action == "update_context":
            return await self._update_session_context(request)
        elif action == "add_query":
            return await self._add_query_to_session(request)
        elif action == "add_answer":
            return await self._add_answer_to_session(request)
        elif action == "get_context":
            return await self._get_context_for_query(request)
        elif action == "summarize":
            return await self._summarize_session(request.get("session_id"))
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _create_or_update_session(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """创建或更新会话"""
        session_id = request.get("session_id")
        user_id = request.get("user_id")

        if session_id is None:
            # 创建新会话
            session_id = f"session_{datetime.now().timestamp()}_{UUID()}"

        # 获取或创建会话
        if session_id not in self.sessions:
            session = SessionContext(
                session_id=session_id,
                user_id=user_id
            )
            self.sessions[session_id] = session

            # 关联到用户
            if user_id:
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = []
                if session_id not in self.user_sessions[user_id]:
                    self.user_sessions[user_id].append(session_id)

            self.logger.info(f"Created new session: {session_id} for user: {user_id}")
        else:
            # 更新现有会话
            session = self.sessions[session_id]
            session.last_active = datetime.now()

            # 更新用户ID（如果之前没有）
            if user_id and not session.user_id:
                session.user_id = user_id
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = []
                self.user_sessions[user_id].append(session_id)

        return {
            "session_id": session_id,
            "created": session_id not in self.sessions or session.query_count == 0,
            "context": session.dict()
        }

    async def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_active = datetime.now()
            return session.dict()
        return None

    async def _list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用户的所有会话"""
        if user_id not in self.user_sessions:
            return []

        sessions = []
        for session_id in self.user_sessions[user_id]:
            if session_id in self.sessions:
                sessions.append(self.sessions[session_id].dict())

        return sorted(sessions, key=lambda x: x["last_active"], reverse=True)

    async def _delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        # 从用户会话列表中移除
        if session.user_id and session.user_id in self.user_sessions:
            if session_id in self.user_sessions[session.user_id]:
                self.user_sessions[session.user_id].remove(session_id)

        # 删除会话
        del self.sessions[session_id]

        self.logger.info(f"Deleted session: {session_id}")
        return True

    async def _update_session_context(self, request: Dict[str, Any]) -> bool:
        """更新会话上下文"""
        session_id = request.get("session_id")
        context_updates = request.get("context", {})

        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        session.context.update(context_updates)
        session.last_active = datetime.now()

        return True

    async def _add_query_to_session(self, request: Dict[str, Any]) -> bool:
        """向会话添加查询"""
        session_id = request.get("session_id")
        query = request.get("query")

        if not session_id or not query:
            return False

        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        # 创建查询记录
        query_record = {
            "timestamp": datetime.now().isoformat(),
            "text": query.text if isinstance(query, UserQuery) else query,
            "query_id": str(query.id) if isinstance(query, UserQuery) else None
        }

        # 如超过最大轮数，丢弃最早的记录（保持最近 max_turns 轮）
        if session.query_count >= self.max_turns:
            # 移除最早一条查询和对应的最早一条答案（如果有）
            if session.queries:
                session.queries = session.queries[-(self.max_turns - 1):]
            if session.answers and len(session.answers) > (self.max_turns - 1):
                session.answers = session.answers[-(self.max_turns - 1):]

        # 添加到查询历史
        session.queries.append(query_record)
        session.query_count = min(session.query_count + 1, self.max_turns)
        session.last_active = datetime.now()

        # 限制历史记录数量
        if len(session.queries) > self.max_history:
            session.queries = session.queries[-self.max_history:]

        # 更新上下文中的最近查询
        session.context["last_query"] = query_record
        session.context["recent_queries"] = session.queries[-5:]  # 最近5条查询

        return True

    async def _add_answer_to_session(self, request: Dict[str, Any]) -> bool:
        """向会话添加答案"""
        session_id = request.get("session_id")
        answer = request.get("answer")

        if not session_id or not answer:
            return False

        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        # 创建答案记录
        answer_record = {
            "timestamp": datetime.now().isoformat(),
            "answer": answer.answer if isinstance(answer, FinalAnswer) else answer,
            "confidence": answer.confidence if isinstance(answer, FinalAnswer) else None,
            "sources_count": len(answer.sources) if isinstance(answer, FinalAnswer) and answer.sources else 0
        }

        # 添加到答案历史
        session.answers.append(answer_record)
        session.last_active = datetime.now()

        # 限制历史记录数量
        if len(session.answers) > self.max_history:
            session.answers = session.answers[-self.max_history:]

        # 同步轮数限制（保持最近 max_turns 条答案）
        if len(session.answers) > self.max_turns:
            session.answers = session.answers[-self.max_turns:]

        # 更新上下文
        session.context["last_answer"] = answer_record
        session.context["recent_answers"] = session.answers[-5:]  # 最近5条答案

        return True

    async def _get_context_for_query(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """获取查询所需的上下文"""
        session_id = request.get("session_id")
        current_query = request.get("query", "")

        context = {
            "session_id": session_id,
            "is_new_session": True,
            "history": [],
            "related_entities": set(),
            "previous_intents": [],
            "topic_continuity": False
        }

        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            context["is_new_session"] = session.query_count == 0

            # 获取最近的对话历史
            recent_limit = max(1, min(self.history_window, self.max_turns))
            recent_queries = session.queries[-recent_limit:] if session.queries else []
            recent_answers = session.answers[-recent_limit:] if session.answers else []

            # 构建对话历史
            history = []
            for i in range(max(len(recent_queries), len(recent_answers))):
                if i < len(recent_queries):
                    history.append({
                        "type": "query",
                        "text": recent_queries[i]["text"],
                        "timestamp": recent_queries[i]["timestamp"]
                    })
                if i < len(recent_answers):
                    history.append({
                        "type": "answer",
                        "text": recent_answers[i]["answer"],
                        "timestamp": recent_answers[i]["timestamp"]
                    })

            context["history"] = history

            # 提取相关实体
            for query in recent_queries:
                # 简单的实体提取（实际应该使用NLP）
                entities = self._extract_simple_entities(query["text"])
                context["related_entities"].update(entities)

            # 检查话题连续性
            if session.queries:
                last_query = session.queries[-1]["text"]
                similarity = self._calculate_query_similarity(last_query, current_query)
                context["topic_continuity"] = similarity > 0.6

            # 获取之前的意图
            if "intents" in session.context:
                context["previous_intents"] = session.context["intents"][-3:]

        context["related_entities"] = list(context["related_entities"])

        return context

    def _extract_simple_entities(self, text: str) -> List[str]:
        """简单的实体提取"""
        entities = []

        # 政策相关关键词
        policy_keywords = [
            "补贴", "申请", "条件", "流程", "材料", "时间", "电话",
            "地址", "部门", "标准", "金额", "资格", "要求",
            "家电", "汽车", "消费券", "以旧换新"
        ]

        for keyword in policy_keywords:
            if keyword in text:
                entities.append(keyword)

        return entities

    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """计算查询相似度"""
        # 简单的基于关键词重叠的相似度计算
        words1 = set(query1.lower().split())
        words2 = set(query2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    async def _summarize_session(self, session_id: str) -> Optional[str]:
        """生成会话摘要"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # 如果已经有摘要，返回它
        if session.summary:
            return session.summary

        # 生成新的摘要
        if session.queries:
            # 提取主要话题
            topics = []
            for query in session.queries[-5:]:  # 最近5个查询
                entities = self._extract_simple_entities(query["text"])
                topics.extend(entities)

            # 统计最常见的话题
            topic_counts = {}
            for topic in topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

            # 生成摘要
            top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:3]

            summary_parts = [
                f"会话包含{session.query_count}个查询",
                f"主要话题：{', '.join([topic for topic, _ in top_topics])}"
            ]

            session.summary = "；".join(summary_parts)

        return session.summary

    async def _cleanup_expired_sessions(self):
        """定期清理过期会话"""
        while True:
            try:
                current_time = datetime.now()
                expired_sessions = []

                for session_id, session in self.sessions.items():
                    if (current_time - session.last_active).seconds > self.session_timeout:
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    await self._delete_session(session_id)
                    self.logger.info(f"Cleaned up expired session: {session_id}")

                # 每10分钟清理一次
                await asyncio.sleep(600)

            except Exception as e:
                self.logger.error(f"Error cleaning up sessions: {e}")
                await asyncio.sleep(60)

    def get_metrics(self) -> Dict[str, Any]:
        """获取Agent指标"""
        total_sessions = len(self.sessions)
        active_sessions = sum(
            1 for s in self.sessions.values()
            if (datetime.now() - s.last_active).seconds < 300  # 5分钟内活跃
        )

        return {
            **self.metrics,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_users": len(self.user_sessions),
            "session_timeout": self.session_timeout,
            "max_turns": self.max_turns,
            "history_window": self.history_window
        }
