"""Centralized logging helpers for agent/runtime events."""

from __future__ import annotations

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


class LoggingManager:
    """Wraps ``autogen_core`` logging events with a simple management API."""

    def __init__(self, name: str = EVENT_LOGGER_NAME) -> None:
        self._logger = logging.getLogger(name)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

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
        formatter = formatter or logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

        if handler is not None:
            handler.setFormatter(formatter)
            self._add_handler(handler)
        elif enable_console:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self._add_handler(stream_handler)

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
            self._add_handler(file_handler)

    # ---- LLM events -----------------------------------------------------

    def log_llm_stream_start(
        self,
        messages: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        self._logger.info(LLMStreamStartEvent(messages=messages, **kwargs))

    def log_llm_stream_end(
        self,
        response: Dict[str, Any],
        *,
        prompt_tokens: int,
        completion_tokens: int,
        **kwargs: Any,
    ) -> None:
        self._logger.info(
            LLMStreamEndEvent(
                response=response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                **kwargs,
            )
        )

    def log_llm_call(
        self,
        messages: List[Dict[str, Any]],
        response: Dict[str, Any],
        *,
        prompt_tokens: int,
        completion_tokens: int,
        **kwargs: Any,
    ) -> None:
        self._logger.info(
            LLMCallEvent(
                messages=messages,
                response=response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                **kwargs,
            )
        )

    # ---- Tool events ----------------------------------------------------

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str,
    ) -> None:
        self._logger.info(
            ToolCallEvent(tool_name=tool_name, arguments=arguments, result=result)
        )

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
        self._logger.info(
            MessageEvent(
                payload=payload,
                sender=sender,
                receiver=receiver,
                kind=kind,
                delivery_stage=delivery_stage,
                **kwargs,
            )
        )

    def log_message_dropped(
        self,
        payload: str,
        *,
        sender: Any = None,
        receiver: Any = None,
        kind: MessageKind = MessageKind.DIRECT,
        **kwargs: Any,
    ) -> None:
        self._logger.warning(
            MessageDroppedEvent(
                payload=payload,
                sender=sender,
                receiver=receiver,
                kind=kind,
                **kwargs,
            )
        )

    def log_handler_exception(
        self,
        payload: str,
        handling_agent: Any,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        self._logger.error(
            MessageHandlerExceptionEvent(
                payload=payload,
                handling_agent=handling_agent,
                exception=exception,
                **kwargs,
            )
        )

    def log_agent_construction_error(
        self,
        agent_id: Any,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        self._logger.error(
            AgentConstructionExceptionEvent(
                agent_id=agent_id, exception=exception, **kwargs
            )
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
