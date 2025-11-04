"""
In-memory session store for multi-turn conversation (infrastructure, not an agent).

Keeps recent turns and provides lightweight context like recent history.
Controlled via environment variables:
- CONVERSATION__MAX_TURNS (default 20)
- CONVERSATION__HISTORY_WINDOW (default 5)
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ...models.base import UserQuery, FinalAnswer


MAX_TURNS = int(os.getenv("CONVERSATION__MAX_TURNS", os.getenv("CONVERSATION_MAX_TURNS", "20")))
HISTORY_WINDOW = int(os.getenv("CONVERSATION__HISTORY_WINDOW", os.getenv("CONVERSATION_HISTORY_WINDOW", "5")))

_SESSIONS: Dict[str, Dict[str, Any]] = {}


def create_or_update_session(session_id: Optional[str], user_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    sid = session_id or f"session_{datetime.now().timestamp()}"
    sess = _SESSIONS.get(sid)
    if not sess:
        sess = {
            "session_id": sid,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "queries": [],
            "answers": [],
            "query_count": 0,
            "context": {},
        }
        _SESSIONS[sid] = sess
    else:
        sess["last_active"] = datetime.now().isoformat()
        if user_id and not sess.get("user_id"):
            sess["user_id"] = user_id
    return sid, sess


def add_query(session_id: str, query: UserQuery) -> None:
    sess = _SESSIONS.get(session_id)
    if not sess:
        return
    record = {
        "timestamp": datetime.now().isoformat(),
        "text": query.text,
        "query_id": str(query.id),
    }
    # enforce max turns
    if sess["query_count"] >= MAX_TURNS:
        if sess["queries"]:
            sess["queries"] = sess["queries"][-(MAX_TURNS - 1) :]
        if sess["answers"] and len(sess["answers"]) > (MAX_TURNS - 1):
            sess["answers"] = sess["answers"][-(MAX_TURNS - 1) :]

    sess["queries"].append(record)
    sess["query_count"] = min(sess["query_count"] + 1, MAX_TURNS)
    sess["last_active"] = datetime.now().isoformat()


def add_answer(session_id: str, answer: FinalAnswer) -> None:
    sess = _SESSIONS.get(session_id)
    if not sess:
        return
    record = {
        "timestamp": datetime.now().isoformat(),
        "answer": answer.answer,
        "confidence": float(answer.confidence),
        "sources_count": len(answer.sources) if answer.sources else 0,
    }
    sess["answers"].append(record)
    sess["last_active"] = datetime.now().isoformat()
    if len(sess["answers"]) > MAX_TURNS:
        sess["answers"] = sess["answers"][ -MAX_TURNS : ]


def get_context(session_id: Optional[str], current_query: str = "") -> Dict[str, Any]:
    if not session_id or session_id not in _SESSIONS:
        return {"is_new_session": True, "history": []}
    sess = _SESSIONS[session_id]
    recent = max(1, min(HISTORY_WINDOW, MAX_TURNS))
    recent_queries = sess["queries"][ -recent : ]
    recent_answers = sess["answers"][ -recent : ]

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
        "is_new_session": sess["query_count"] == 0,
        "history": history,
        "last_active": sess["last_active"],
    }

