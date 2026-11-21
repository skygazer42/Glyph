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
    def format(self, record: logging.LogRecord) -> str:
        """仅将既有日志格式中可解析的 JSON 消息转为中文可读文本，其余原样返回。"""
        formatted = super().format(record)
        parts = formatted.split(" - ", 3)
        if len(parts) != 4:
            return formatted
        try:
            payload = json.loads(parts[3])
        except json.JSONDecodeError:
            return formatted
        parts[3] = json.dumps(payload, ensure_ascii=False)
        return " - ".join(parts)


class LoggingManager:
    """Wraps ``autogen_core`` logging events with a simple management API."""

    def __init__(self, name: str = EVENT_LOGGER_NAME) -> None:
        self._logger = logging.getLogger(name)
        self._owned_handlers: set[logging.Handler] = set()
        # 防止日志传播到root logger,避免重复输出
        self._logger.propagate = False

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @staticmethod
    def _serialize_event(event: Any) -> str:
        """Convert AutoGen logging events to UTF-8 JSON for readable console输出."""
        return json.dumps(event.kwargs, ensure_ascii=False)

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
        """替换日志处理器，并按需配置控制台及滚动文件输出。

        只关闭本管理器创建且不再复用的处理器；外部传入的 handler 由调用方管理。
        """
        self._logger.setLevel(level)

        # Detach replaced handlers and release owned file streams.
        for previous in self._logger.handlers[:]:
            self._logger.removeHandler(previous)
            if previous is not handler and previous in self._owned_handlers:
                previous.close()
                self._owned_handlers.remove(previous)

        # 使用UTF-8JsonFormatter来正确显示中文
        if formatter is None:
            formatter = UTF8JsonFormatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

        if handler is not None:
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        elif enable_console:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self._logger.addHandler(stream_handler)
            self._owned_handlers.add(stream_handler)

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
            self._owned_handlers.add(file_handler)

    # ---- LLM events -----------------------------------------------------

    def log_llm_stream_start(
        self,
        messages: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        """将模型流式请求的输入消息封装为 AutoGen 开始事件并以 INFO 记录。"""
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
        """记录流式模型响应及调用方提供的输入、输出 token 数。"""
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
        """记录完整模型调用的消息、响应和 token 用量。"""
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
        """记录已完成工具调用的名称、参数和文本结果。"""
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
        """记录消息在发送或投递阶段的参与方、消息类型和载荷。"""
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
        """以 WARNING 记录未投递消息的载荷和参与方。"""
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
        """记录消息处理失败事件，并附上所传异常的原始回溯。"""
        event = MessageHandlerExceptionEvent(
            payload=payload,
            handling_agent=handling_agent,
            exception=exception,
            **kwargs,
        )
        self._logger.error(
            self._serialize_event(event),
            exc_info=(type(exception), exception, exception.__traceback__),
        )

    def log_agent_construction_error(
        self,
        agent_id: Any,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        """记录智能体构造失败事件，并附上所传异常的原始回溯。"""
        event = AgentConstructionExceptionEvent(
            agent_id=agent_id, exception=exception, **kwargs
        )
        self._logger.error(
            self._serialize_event(event),
            exc_info=(type(exception), exception, exception.__traceback__),
        )

    # ---- Generic logging ------------------------------------------------

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, **kwargs)


logging_manager = LoggingManager()

__all__ = ["LoggingManager", "logging_manager"]
