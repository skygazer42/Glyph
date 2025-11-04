"""
AG State - Agent状态管理模块示例
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import logging

from ...models.base import AgentType, MessageType
from ..core.agent_base import AgentBase
from ..core.message_bus import Message

logger = logging.getLogger(__name__)


class AgentStateManager(AgentBase):
    """
    Agent状态管理器 - 管理所有Agent的状态和上下文
    """

    def __init__(self):
        super().__init__(
            agent_id="agent_state_manager",
            agent_type=AgentType.SPECIALIZED,
            name="Agent State Manager",
            description="管理和持久化Agent状态"
        )
        self.capabilities = [
            "get_state",
            "set_state",
            "update_state",
            "delete_state",
            "list_states",
            "backup_state",
            "restore_state",
            "clear_expired_states"
        ]
        self._states: Dict[str, Dict[str, Any]] = {}  # state_id -> state_data
        self._sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session_data
        self._state_persistence_path = Path(__file__).parent.parent.parent / "data" / "states"
        self._state_persistence_path.mkdir(parents=True, exist_ok=True)
        self._default_ttl = 3600  # 默认状态保存1小时

    async def process(self, message: Message) -> Optional[Message]:
        """处理状态管理请求"""
        try:
            action = message.content.get("action")
            state_id = message.content.get("state_id")
            session_id = message.content.get("session_id")
            content = message.content.get("content", {})

            logger.info(f"Processing state action: {action} for state: {state_id}")

            # 根据动作执行相应操作
            if action == "get":
                result = await self._get_state(state_id, session_id)
            elif action == "set":
                result = await self._set_state(state_id, content, session_id)
            elif action == "update":
                result = await self._update_state(state_id, content, session_id)
            elif action == "delete":
                result = await self._delete_state(state_id, session_id)
            elif action == "list":
                result = await self._list_states(session_id)
            elif action == "backup":
                result = await self._backup_state(state_id or session_id)
            elif action == "restore":
                result = await self._restore_state(content.get("backup_file"))
            elif action == "clear_expired":
                result = await self._clear_expired_states()
            else:
                result = {"error": f"Unknown action: {action}"}

            return message.create_reply(
                content={
                    "action": action,
                    "state_id": state_id,
                    "session_id": session_id,
                    "result": result,
                    "status": "success" if "error" not in result else "failed"
                },
                sender=self.agent_id
            )

        except Exception as e:
            logger.error(f"Error in state manager: {e}")
            return message.create_reply(
                content={"error": str(e)},
                sender=self.agent_id
            )

    async def _get_state(
        self,
        state_id: Optional[str],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """获取状态"""
        # 如果没有指定state_id，返回会话状态
        if not state_id and session_id:
            return self._sessions.get(session_id, {})

        # 获取特定状态
        if state_id in self._states:
            state = self._states[state_id].copy()

            # 检查是否过期
            if self._is_state_expired(state):
                await self._delete_state(state_id, None)
                return {"error": f"State {state_id} has expired"}

            # 移除内部字段
            state.pop("created_at", None)
            state.pop("updated_at", None)
            state.pop("expires_at", None)

            return state

        return {"error": f"State not found: {state_id}"}

    async def _set_state(
        self,
        state_id: str,
        content: Dict[str, Any],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """设置状态"""
        now = datetime.now()
        ttl = content.pop("ttl", self._default_ttl)

        self._states[state_id] = {
            "state_id": state_id,
            "session_id": session_id,
            "content": content,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(seconds=ttl)
        }

        # 如果是会话状态，同时更新会话
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "states": [],
                    "created_at": now
                }

            self._sessions[session_id]["states"].append(state_id)
            self._sessions[session_id]["updated_at"] = now

        # 持久化到文件
        await self._persist_state(state_id)

        return {
            "state_id": state_id,
            "message": "State set successfully"
        }

    async def _update_state(
        self,
        state_id: str,
        updates: Dict[str, Any],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """更新状态"""
        if state_id not in self._states:
            return {"error": f"State not found: {state_id}"}

        state = self._states[state_id]

        # 更新内容
        if "content" in updates:
            state["content"].update(updates["content"])

        # 更新其他属性
        if "ttl" in updates:
            state["expires_at"] = datetime.now() + timedelta(seconds=updates["ttl"])

        state["updated_at"] = datetime.now()

        # 持久化更新
        await self._persist_state(state_id)

        return {
            "state_id": state_id,
            "message": "State updated successfully"
        }

    async def _delete_state(
        self,
        state_id: Optional[str],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """删除状态"""
        if state_id:
            # 删除特定状态
            if state_id in self._states:
                del self._states[state_id]

                # 从会话中移除
                for session in self._sessions.values():
                    if state_id in session.get("states", []):
                        session["states"].remove(state_id)

                # 删除持久化文件
                await self._delete_persisted_state(state_id)

                return {
                    "state_id": state_id,
                    "message": "State deleted successfully"
                }
            else:
                return {"error": f"State not found: {state_id}"}

        elif session_id:
            # 删除会话的所有状态
            if session_id in self._sessions:
                session = self._sessions[session_id]
                for state_id in session.get("states", []):
                    if state_id in self._states:
                        del self._states[state_id]
                        await self._delete_persisted_state(state_id)

                del self._sessions[session_id]

                return {
                    "session_id": session_id,
                    "message": "Session and all its states deleted successfully"
                }
            else:
                return {"error": f"Session not found: {session_id}"}

        else:
            return {"error": "Either state_id or session_id must be provided"}

    async def _list_states(self, session_id: Optional[str]) -> Dict[str, Any]:
        """列出状态"""
        states = []

        if session_id:
            # 列出会话的所有状态
            session = self._sessions.get(session_id, {})
            for state_id in session.get("states", []):
                if state_id in self._states and not self._is_state_expired(self._states[state_id]):
                    state = self._states[state_id]
                    states.append({
                        "state_id": state_id,
                        "created_at": state["created_at"].isoformat(),
                        "updated_at": state["updated_at"].isoformat(),
                        "expires_at": state["expires_at"].isoformat()
                    })
        else:
            # 列出所有状态
            for state_id, state in self._states.items():
                if not self._is_state_expired(state):
                    states.append({
                        "state_id": state_id,
                        "session_id": state.get("session_id"),
                        "created_at": state["created_at"].isoformat(),
                        "updated_at": state["updated_at"].isoformat(),
                        "expires_at": state["expires_at"].isoformat()
                    })

        return {"states": states, "count": len(states)}

    async def _backup_state(self, identifier: str) -> Dict[str, Any]:
        """备份状态"""
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "states": {},
            "sessions": {}
        }

        if identifier in self._states:
            # 备份单个状态
            backup_data["states"][identifier] = self._states[identifier]
        elif identifier in self._sessions:
            # 备份整个会话
            session = self._sessions[identifier]
            backup_data["sessions"][identifier] = session

            # 备份会话的所有状态
            for state_id in session.get("states", []):
                if state_id in self._states:
                    backup_data["states"][state_id] = self._states[state_id]
        else:
            # 备份所有状态
            backup_data["states"] = self._states.copy()
            backup_data["sessions"] = self._sessions.copy()

        # 保存备份文件
        backup_file = self._state_persistence_path / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

        return {
            "backup_file": str(backup_file),
            "states_count": len(backup_data["states"]),
            "sessions_count": len(backup_data["sessions"]),
            "message": "Backup created successfully"
        }

    async def _restore_state(self, backup_file: str) -> Dict[str, Any]:
        """恢复状态"""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            # 恢复状态
            restored_states = 0
            for state_id, state in backup_data.get("states", {}).items():
                # 转换时间字符串为datetime对象
                for time_field in ["created_at", "updated_at", "expires_at"]:
                    if time_field in state and isinstance(state[time_field], str):
                        state[time_field] = datetime.fromisoformat(state[time_field])

                # 只恢复未过期的状态
                if not self._is_state_expired(state):
                    self._states[state_id] = state
                    restored_states += 1

            # 恢复会话
            restored_sessions = 0
            for session_id, session in backup_data.get("sessions", {}).items():
                for time_field in ["created_at", "updated_at"]:
                    if time_field in session and isinstance(session[time_field], str):
                        session[time_field] = datetime.fromisoformat(session[time_field])

                self._sessions[session_id] = session
                restored_sessions += 1

            return {
                "restored_states": restored_states,
                "restored_sessions": restored_sessions,
                "message": "State restored successfully"
            }

        except Exception as e:
            return {"error": f"Failed to restore backup: {e}"}

    async def _clear_expired_states(self) -> Dict[str, Any]:
        """清理过期状态"""
        expired_states = []
        now = datetime.now()

        # 找出所有过期状态
        for state_id, state in list(self._states.items()):
            if self._is_state_expired(state):
                expired_states.append(state_id)
                del self._states[state_id]
                await self._delete_persisted_state(state_id)

        # 清理空会话
        empty_sessions = []
        for session_id, session in list(self._sessions.items()):
            # 移除过期状态引用
            session["states"] = [
                state_id for state_id in session.get("states", [])
                if state_id not in expired_states
            ]

            # 删除没有状态的会话
            if not session["states"]:
                empty_sessions.append(session_id)
                del self._sessions[session_id]

        return {
            "cleared_states": len(expired_states),
            "cleared_sessions": len(empty_sessions),
            "message": "Expired states cleared successfully"
        }

    async def _persist_state(self, state_id: str) -> None:
        """持久化状态到文件"""
        if state_id not in self._states:
            return

        state_file = self._state_persistence_path / f"{state_id}.json"
        state_data = self._states[state_id].copy()

        # 转换datetime对象为字符串
        for key, value in state_data.items():
            if isinstance(value, datetime):
                state_data[key] = value.isoformat()

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

    async def _delete_persisted_state(self, state_id: str) -> None:
        """删除持久化状态文件"""
        state_file = self._state_persistence_path / f"{state_id}.json"
        if state_file.exists():
            state_file.unlink()

    def _is_state_expired(self, state: Dict[str, Any]) -> bool:
        """检查状态是否过期"""
        if "expires_at" not in state:
            return False
        return datetime.now() > state["expires_at"]

    async def create_session(
        self,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建新会话"""
        if session_id in self._sessions:
            return {"error": f"Session already exists: {session_id}"}

        self._sessions[session_id] = {
            "session_id": session_id,
            "states": [],
            "metadata": metadata or {},
            "created_at": datetime.now()
        }

        return {
            "session_id": session_id,
            "message": "Session created successfully"
        }

    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话的完整状态"""
        if session_id not in self._sessions:
            return None

        session = self._sessions[session_id].copy()
        session_states = {}

        # 收集会话的所有状态
        for state_id in session.get("states", []):
            if state_id in self._states and not self._is_state_expired(self._states[state_id]):
                state = self._states[state_id].copy()
                # 移除内部字段
                state.pop("created_at", None)
                state.pop("updated_at", None)
                state.pop("expires_at", None)
                session_states[state_id] = state

        session["states"] = session_states
        return session

    def get_stats(self) -> Dict[str, Any]:
        """获取状态管理器统计信息"""
        total_states = len(self._states)
        active_states = sum(
            1 for state in self._states.values()
            if not self._is_state_expired(state)
        )
        total_sessions = len(self._sessions)

        return {
            "total_states": total_states,
            "active_states": active_states,
            "expired_states": total_states - active_states,
            "total_sessions": total_sessions,
            "persistence_path": str(self._state_persistence_path)
        }