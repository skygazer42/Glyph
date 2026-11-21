"""The AgentChat model stream must distinguish tool decisions from answer text."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
)
from autogen_core import FunctionCall
from autogen_core.models import FunctionExecutionResult

from app.agents.service.progress import capture_progress


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["agentchat_router", "agentchat_team"])
def wrapper(monkeypatch, request):
    monkeypatch.setenv("AGENTCHAT_REFLECT", "true")
    monkeypatch.setenv("AGENTCHAT_MAX_TOOL_ITERATIONS", "1")
    memory = ModuleType("app.agents.framework.common.autogen_memory_store")
    monkeypatch.setitem(sys.modules, memory.__name__, memory)
    module_name = f"_answer_boundary_{request.param}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"app/agents/service/{request.param}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    cls = module.AgentChatRouter if request.param == "agentchat_router" else module.AgentChatTeam
    instance = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(), rule_tool=Mock(),
                   text2sql_tool=Mock(), workflow_tool=Mock())
    return instance, "_get_or_create_agent" if request.param == "agentchat_router" else "_get_or_create_team"


def attach_stream(wrapper, stream):
    instance, factory = wrapper
    backend = SimpleNamespace(run_stream=stream, run=Mock(side_effect=AssertionError("must not replay tools")))
    setattr(instance, factory, AsyncMock(return_value=backend))
    return instance


def chunk(content):
    return ModelClientStreamingChunkEvent(content=content, source="assistant")


def tool_request(call_id="one"):
    return ToolCallRequestEvent(content=[FunctionCall(id=call_id, name="knowledge_tool", arguments='{"query":"private"}')], source="assistant")


def tool_result(call_id="one", *, is_error=False):
    return ToolCallExecutionEvent(content=[FunctionExecutionResult(call_id=call_id, name="knowledge_tool", content="private raw result", is_error=is_error)], source="assistant")


def terminal(answer):
    return TaskResult(messages=[TextMessage(content=answer, source="assistant")], stop_reason="done")


def test_tool_decision_fragments_are_dropped_but_reflection_streams_immediately(wrapper):
    completed = False
    closed = []

    async def stream(**kwargs):
        nonlocal completed
        try:
            for text in ['{"query":', '"private"}', "\n</tool", "_call>"]:
                yield chunk(text)
            yield tool_request()
            yield tool_result()
            yield chunk("根据[资料1]，")
            yield chunk("第18条规定。")
            completed = True
            yield TextMessage(content="根据[资料1]，第18条规定。", source="assistant")
            yield terminal("根据[资料1]，第18条规定。")
        finally:
            closed.append(True)

    instance = attach_stream(wrapper, stream)

    async def run():
        result = instance.run_stream("one", "policy")
        first = await anext(result)
        assert first == {"type": "chunk", "content": "根据[资料1]，"}
        assert not completed
        return [first, *[event async for event in result]]

    events = asyncio.run(run())
    assert [event["content"] for event in events if event["type"] == "chunk"] == ["根据[资料1]，", "第18条规定。"]
    assert events[-1]["answer"].answer == "根据[资料1]，第18条规定。"
    assert "error" not in events[-1]["meta"]
    assert closed == [True]


def test_direct_answer_waits_for_text_confirmation_without_simulated_tokens(wrapper):
    confirmed = False

    async def stream(**kwargs):
        nonlocal confirmed
        yield chunk("uncertain preliminary text")
        yield chunk("}")
        confirmed = True
        yield TextMessage(content="已确认的直接答复。", source="assistant")
        yield terminal("已确认的直接答复。")

    instance = attach_stream(wrapper, stream)

    async def run():
        events = []
        async for event in instance.run_stream("one", "policy"):
            assert confirmed
            events.append(event)
        return events

    events = asyncio.run(run())
    assert [event["content"] for event in events if event["type"] == "chunk"] == ["已确认的直接答复。"]


def test_multiple_tool_rounds_keep_the_intermediate_decision_private(wrapper):
    instance, _ = wrapper
    instance._max_tool_iterations = 2

    async def stream(**kwargs):
        yield chunk("first private tool decision")
        yield tool_request("first")
        yield tool_result("first")
        yield chunk("}</tool")
        yield chunk("_call>")
        yield tool_request("second")
        yield tool_result("second")
        yield chunk("最终")
        yield chunk("答复")
        yield TextMessage(content="最终答复", source="assistant")
        yield terminal("最终答复")

    attach_stream(wrapper, stream)
    events = asyncio.run(collect(instance))
    assert [event["content"] for event in events if event["type"] == "chunk"] == ["最终", "答复"]


def test_reflection_waits_for_all_requested_tools_to_finish(wrapper):
    async def stream(**kwargs):
        request = tool_request("first")
        request.content.extend(tool_request("second").content)
        yield request
        yield tool_result("first")
        yield chunk("must stay private while another tool runs")
        yield tool_result("second", is_error=True)
        yield chunk("可说明部分检索失败的安全答复")
        yield terminal("可说明部分检索失败的安全答复")

    instance = attach_stream(wrapper, stream)
    events = asyncio.run(collect(instance))
    assert [event["content"] for event in events if event["type"] == "chunk"] == ["可说明部分检索失败的安全答复"]


def test_early_answer_before_tool_limit_waits_for_text_confirmation(wrapper):
    instance, _ = wrapper
    instance._max_tool_iterations = 3
    confirmed = False

    async def stream(**kwargs):
        nonlocal confirmed
        yield tool_request()
        yield tool_result()
        yield chunk("可信答复")
        confirmed = True
        yield TextMessage(content="可信答复", source="assistant")
        yield terminal("可信答复")

    attach_stream(wrapper, stream)

    async def run():
        events = []
        async for event in instance.run_stream("one", "policy"):
            assert confirmed
            events.append(event)
        return events

    events = asyncio.run(run())
    assert events[0] == {"type": "chunk", "content": "可信答复"}


@pytest.mark.parametrize("end", ["empty", "task_result", "error", "control_text"])
def test_unconfirmed_or_control_text_is_never_a_successful_answer(wrapper, end):
    async def stream(**kwargs):
        yield chunk("}")
        yield chunk("\n</tool")
        yield chunk("_call>")
        if end == "task_result":
            yield TaskResult(messages=[], stop_reason="done")
        elif end == "error":
            raise RuntimeError("provider private failure")
        elif end == "control_text":
            yield terminal("}\n</tool_call>")

    instance = attach_stream(wrapper, stream)
    events = asyncio.run(collect(instance))
    assert [event for event in events if event["type"] == "chunk"] == []
    assert "error" in events[-1]["meta"]
    assert "</tool_call>" not in events[-1]["answer"].answer


def test_exception_closes_pending_tool_as_error_without_replay(wrapper):
    closed, progress = [], []

    async def stream(**kwargs):
        try:
            yield chunk("private decision")
            yield tool_request()
            raise RuntimeError("provider private failure")
        finally:
            closed.append(True)

    instance = attach_stream(wrapper, stream)

    async def run():
        with capture_progress(progress.append):
            return await collect(instance)

    events = asyncio.run(run())
    assert closed == [True]
    assert [event["type"] for event in events] == ["final"]
    assert progress[-1] == {"type": "tool_finished", "tool_call_id": "one", "name": "knowledge_tool", "status": "error"}


def test_cancellation_discards_private_tokens_and_closes_pending_tool(wrapper):
    closed, progress = [], []

    async def run():
        waiting = asyncio.Event()

        async def stream(**kwargs):
            try:
                yield chunk("private decision")
                yield tool_request()
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.append(True)

        instance = attach_stream(wrapper, stream)
        with capture_progress(progress.append):
            task = asyncio.create_task(collect(instance))
            await asyncio.wait_for(waiting.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
    assert closed == [True]
    assert progress[-1] == {"type": "tool_finished", "tool_call_id": "one", "name": "knowledge_tool", "status": "cancelled"}


def test_final_result_can_supply_confirmed_text_without_replaying_tools(wrapper):
    async def stream(**kwargs):
        yield chunk("uncertain text")
        yield terminal("权威最终正文[资料2]，第18条。")

    instance = attach_stream(wrapper, stream)
    events = asyncio.run(collect(instance))
    assert events[-1]["answer"].answer == "权威最终正文[资料2]，第18条。"
    assert "error" not in events[-1]["meta"]
    assert "uncertain text" not in str(events)


async def collect(instance):
    return [event async for event in instance.run_stream("one", "policy")]


@pytest.mark.parametrize("stop_method", ["cancel", "close"])
def test_interrupted_session_rebuilds_its_cached_agent_without_replaying_tools(wrapper, monkeypatch, stop_method):
    instance, factory = wrapper
    module = sys.modules[type(instance).__module__]
    cache = instance._agents if factory == "_get_or_create_agent" else instance._teams
    executions, closed = [], []
    other = SimpleNamespace()
    cache["other"] = other
    module.autogen_memory_store.build_buffered_context = AsyncMock(return_value=SimpleNamespace())
    retained_memory = object()
    module.autogen_memory_store.retained_memory = retained_memory

    async def fresh_stream(**kwargs):
        yield terminal("重建后正常答复")

    fresh = SimpleNamespace(run_stream=fresh_stream)
    monkeypatch.setattr(module, "AssistantAgent", Mock(return_value=fresh))
    if factory == "_get_or_create_team":
        monkeypatch.setattr(module, "UserProxyAgent", Mock(return_value=SimpleNamespace()))
        monkeypatch.setattr(module, "RoundRobinGroupChat", Mock(return_value=fresh))

    async def run():
        waiting = asyncio.Event()

        async def interrupted_stream(**kwargs):
            try:
                yield tool_request()
                executions.append("original tool ran once")
                yield tool_result()
                yield chunk("已开始生成")
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.append(True)

        old = SimpleNamespace(run_stream=interrupted_stream)
        cache["one"] = old
        if stop_method == "cancel":
            task = asyncio.create_task(collect(instance))
            await asyncio.wait_for(waiting.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            stream = instance.run_stream("one", "policy")
            assert (await anext(stream))["content"] == "已开始生成"
            await stream.aclose()

        assert "one" not in cache
        assert cache["other"] is other
        events = await collect(instance)
        assert cache["one"] is fresh
        assert events[-1]["answer"].answer == "重建后正常答复"
        assert "error" not in events[-1]["meta"]

    asyncio.run(run())
    assert executions == ["original tool ran once"]
    assert closed == [True]
    assert module.autogen_memory_store.retained_memory is retained_memory
    module.autogen_memory_store.build_buffered_context.assert_awaited_once_with("one", buffer_size=10)


def test_cancelled_non_stream_call_discards_only_its_cached_agent(wrapper):
    instance, factory = wrapper
    cache = instance._agents if factory == "_get_or_create_agent" else instance._teams
    other = SimpleNamespace()
    cache["other"] = other

    async def run():
        started = asyncio.Event()

        async def backend_run(**kwargs):
            started.set()
            await asyncio.Event().wait()

        old = SimpleNamespace(run=AsyncMock(side_effect=backend_run))
        cache["one"] = old
        task = asyncio.create_task(instance.run("one", "policy"))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert "one" not in cache
        assert cache["other"] is other
        assert old.run.await_count == 1

    asyncio.run(run())
