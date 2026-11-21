"""
In-memory session store for multi-turn conversation (infrastructure, not an agent).

Keeps recent turns and provides lightweight conversation history.
Controlled via environment variables:
- CONVERSATION__MAX_TURNS (default 20)
- CONVERSATION__HISTORY_WINDOW (default 5)
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.policy import FinalAnswer, UserQuery


MAX_TURNS = int(os.getenv("CONVERSATION__MAX_TURNS", os.getenv("CONVERSATION_MAX_TURNS", "20")))
HISTORY_WINDOW = int(os.getenv("CONVERSATION__HISTORY_WINDOW", os.getenv("CONVERSATION_HISTORY_WINDOW", "5")))

if MAX_TURNS <= 0 or HISTORY_WINDOW < 0:
    raise ValueError("MAX_TURNS must be positive and HISTORY_WINDOW non-negative")

_SESSIONS: Dict[str, Dict[str, Any]] = {}


def create_or_update_session(session_id: Optional[str], user_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    """创建或刷新进程内会话，返回标识和共享记录；不提供持久化或副本隔离。"""
    session_id = session_id or f"session_{datetime.now().timestamp()}"
    session = _SESSIONS.get(session_id)
    if session is None:
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "queries": [],
            "answers": [],
            "query_count": 0,
            "context": {},
        }
        _SESSIONS[session_id] = session
    else:
        session["last_active"] = datetime.now().isoformat()
        if user_id and not session["user_id"]:
            session["user_id"] = user_id
    return session_id, session


def add_query(session_id: str, query: UserQuery) -> None:
    """给已存在会话追加问题并按 MAX_TURNS 截断，更新查询计数与活跃时间。"""
    session = _SESSIONS[session_id]
    record = {
        "timestamp": datetime.now().isoformat(),
        "text": query.text,
        "query_id": str(query.id),
    }
    session["queries"].append(record)
    session["queries"] = session["queries"][-MAX_TURNS:]
    session["query_count"] = min(session["query_count"] + 1, MAX_TURNS)
    session["last_active"] = datetime.now().isoformat()


def add_answer(session_id: str, answer: FinalAnswer) -> None:
    """给已存在会话追加回答摘要，只保留最近 MAX_TURNS 条回答。"""
    session = _SESSIONS[session_id]
    record = {
        "timestamp": datetime.now().isoformat(),
        "answer": answer.answer,
        "confidence": float(answer.confidence),
        "sources_count": len(answer.sources),
    }
    session["answers"].append(record)
    session["last_active"] = datetime.now().isoformat()
    if len(session["answers"]) > MAX_TURNS:
        session["answers"] = session["answers"][ -MAX_TURNS : ]


def get_context(session_id: Optional[str]) -> Dict[str, Any]:
    """按配置窗口交错组装最近问题和回答；缺失会话返回新会话标记及空历史。"""
    if not session_id or session_id not in _SESSIONS:
        return {"is_new_session": True, "history": []}
    session = _SESSIONS[session_id]
    history_limit = max(0, min(HISTORY_WINDOW, MAX_TURNS))
    recent_queries = session["queries"][-history_limit:] if history_limit else []
    recent_answers = session["answers"][-history_limit:] if history_limit else []

    history: List[Dict[str, Any]] = []
    for i in range(max(len(recent_queries), len(recent_answers))):
        if i < len(recent_queries):
            history.append({
                "type": "query",
                "text": recent_queries[i]["text"],
                "timestamp": recent_queries[i]["timestamp"],
            })
        if i < len(recent_answers):
            history.append({
                "type": "answer",
                "text": recent_answers[i]["answer"],
                "timestamp": recent_answers[i]["timestamp"],
            })

    return {
        "is_new_session": session["query_count"] == 0,
        "history": history,
        "last_active": session["last_active"],
    }

