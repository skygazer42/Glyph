"""Centralized logging helpers for agent/runtime events."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from autogen_core import EVENT_LOGGER_NAME
from autogen_core.logging import (
    AgentConstructionExceptionEvent,
    DeliveryStage,
    LLMCallEvent,
    LLMStreamEndEvent,
    LLMStreamStartEvent,
    MessageDroppedEvent,
    MessageEvent,
    MessageHandlerExceptionEvent,
    MessageKind,
    ToolCallEvent,
)


class UTF8JsonFormatter(logging.Formatter):
    """自定义格式化器:将日志消息中的JSON转换为UTF-8可读格式"""
    def format(self, record):
        # 先应用标准格式
        formatted = super().format(record)
        # 尝试解析并重新序列化为UTF-8
        try:
            # 查找JSON部分(通常在最后一个" - "之后)
            if " - " in formatted:
                parts = formatted.split(" - ", 3)
                if len(parts) >= 4:
                    json_part = parts[3]
                    try:
                        # 解析JSON并用ensure_ascii=False重新序列化
                        data = json.loads(json_part)
                        readable_json = json.dumps(data, ensure_ascii=False, indent=None)
                        parts[3] = readable_json
                        formatted = " - ".join(parts)
                    except (json.JSONDecodeError, ValueError):
                        pass
        except Exception:
            pass
        return formatted


class LoggingManager:
    """Wraps ``autogen_core`` logging events with a simple management API."""

    def __init__(self, name: str = EVENT_LOGGER_NAME) -> None:
        self._logger = logging.getLogger(name)
        # 防止日志传播到root logger,避免重复输出
        self._logger.propagate = False

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @staticmethod
    def _serialize_event(event: Any) -> str:
        """Convert AutoGen logging events to UTF-8 JSON for readable console输出."""
        payload = getattr(event, "kwargs", None)
        if payload is None:
            return str(event)
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(event)

    def _add_handler(self, handler: logging.Handler) -> None:
        """Attach handler if a similar one doesn't already exist."""
        for existing in self._logger.handlers:
            if type(existing) is type(handler):
                if getattr(existing, "baseFilename", None) == getattr(handler, "baseFilename", None):
                    return
                if not getattr(existing, "baseFilename", None):
                    return
        self._logger.addHandler(handler)

    def configure(
        self,
        *,
        level: int = logging.INFO,
        formatter: Optional[logging.Formatter] = None,
        handler: Optional[logging.Handler] = None,
        log_dir: Optional[str] = None,
        filename: str = "app.log",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        enable_console: bool = True,
    ) -> None:
        """Configure logger handlers and optional rotating file output."""
        self._logger.setLevel(level)

        # 清除所有现有handlers,避免重复
        self._logger.handlers.clear()

        # 使用UTF-8JsonFormatter来正确显示中文
        formatter = formatter or UTF8JsonFormatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

        if handler is not None:
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        elif enable_console:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self._logger.addHandler(stream_handler)

        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            file_path = Path(log_dir) / filename
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    # ---- LLM events -----------------------------------------------------

    def log_llm_stream_start(
        self,
        messages: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        event = LLMStreamStartEvent(messages=messages, **kwargs)
        self._logger.info(self._serialize_event(event))

    def log_llm_stream_end(
        self,
        response: Dict[str, Any],
        *,
        prompt_tokens: int,
        completion_tokens: int,
        **kwargs: Any,
    ) -> None:
        event = LLMStreamEndEvent(
            response=response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            **kwargs,
        )
        self._logger.info(self._serialize_event(event))

    def log_llm_call(
        self,
        messages: List[Dict[str, Any]],
        response: Dict[str, Any],
        *,
        prompt_tokens: int,
        completion_tokens: int,
        **kwargs: Any,
    ) -> None:
        event = LLMCallEvent(
            messages=messages,
            response=response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            **kwargs,
        )
        self._logger.info(self._serialize_event(event))

    # ---- Tool events ----------------------------------------------------

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str,
    ) -> None:
        event = ToolCallEvent(tool_name=tool_name, arguments=arguments, result=result)
        self._logger.info(self._serialize_event(event))

    # ---- Message bus events --------------------------------------------

    def log_message_event(
        self,
        payload: str,
        *,
        sender: Any = None,
        receiver: Any = None,
        kind: MessageKind = MessageKind.DIRECT,
        delivery_stage: DeliveryStage = DeliveryStage.SEND,
        **kwargs: Any,
    ) -> None:
        event = MessageEvent(
            payload=payload,
            sender=sender,
            receiver=receiver,
            kind=kind,
            delivery_stage=delivery_stage,
            **kwargs,
        )
        self._logger.info(self._serialize_event(event))

    def log_message_dropped(
        self,
        payload: str,
        *,
        sender: Any = None,
        receiver: Any = None,
        kind: MessageKind = MessageKind.DIRECT,
        **kwargs: Any,
    ) -> None:
        event = MessageDroppedEvent(
            payload=payload,
            sender=sender,
            receiver=receiver,
            kind=kind,
            **kwargs,
        )
        self._logger.warning(self._serialize_event(event))

    def log_handler_exception(
        self,
        payload: str,
        handling_agent: Any,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        event = MessageHandlerExceptionEvent(
            payload=payload,
            handling_agent=handling_agent,
            exception=exception,
            **kwargs,
        )
        self._logger.error(self._serialize_event(event))

    def log_agent_construction_error(
        self,
        agent_id: Any,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        event = AgentConstructionExceptionEvent(
            agent_id=agent_id, exception=exception, **kwargs
        )
        self._logger.error(self._serialize_event(event))

    # ---- Generic logging ------------------------------------------------

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, **kwargs)


logging_manager = LoggingManager()

__all__ = ["LoggingManager", "logging_manager"]
