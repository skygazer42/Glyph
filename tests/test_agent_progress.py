"""Offline execution progress, source identity and cancellation regressions."""

from __future__ import annotations

import ast
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
import importlib
from pathlib import Path
import re
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]


def progress_api():
    return importlib.import_module("app.agents.service.progress")


def test_progress_context_is_nested_and_restored_after_failure():
    progress = progress_api()
    outer, inner = [], []
    progress.emit_progress("step_started", name="unobserved", label="unused")
    with progress.capture_progress(outer.append):
        progress.emit_progress("step_started", name="outer", label="准备")
        with pytest.raises(RuntimeError), progress.capture_progress(inner.append):
            progress.emit_progress("step_started", name="inner", label="检索")
            raise RuntimeError("private backend failure")
        progress.emit_progress("step_finished", name="outer", label="准备")
    progress.emit_progress("step_started", name="unobserved", label="unused")
    assert [event["name"] for event in outer] == ["outer", "outer"]
    assert [event["name"] for event in inner] == ["inner"]


def test_concurrent_and_threaded_work_keeps_the_request_progress_sink():
    progress = progress_api()

    async def run():
        ready = asyncio.Event()
        entered = 0

        async def request(name):
            nonlocal entered
            events = []
            with progress.capture_progress(events.append):
                entered += 1
                if entered == 2:
                    ready.set()
                await ready.wait()
                await asyncio.to_thread(progress.emit_progress, "step_started", name=name, label="检索")
                await asyncio.sleep(0)
                progress.emit_progress("step_finished", name=name, label="检索")
            return events

        return await asyncio.gather(request("public"), request("staff"))

    results = asyncio.run(run())
    assert [[event["name"] for event in request] for request in results] == [["public", "public"], ["staff", "staff"]]


def test_progress_observer_cannot_break_business_execution():
    progress = progress_api()
    observer = Mock(side_effect=RuntimeError("closed response stream"))
    with progress.capture_progress(observer):
        with progress.progress_step("search", "查询政策"):
            result = 42
    assert result == 42
    assert observer.call_count == 2


def test_cancelled_stage_is_closed_without_reporting_a_success_or_exception_text():
    progress = progress_api()
    events = []

    async def run():
        with progress.capture_progress(events.append):
            with pytest.raises(asyncio.CancelledError), progress.progress_step("search", "查询政策"):
                raise asyncio.CancelledError("private request details")
        progress.emit_progress("step_started", name="after", label="unused")

    asyncio.run(run())
    assert events == [
        {"type": "step_started", "name": "search", "label": "查询政策"},
        {"type": "step_finished", "name": "search", "label": "查询政策", "status": "cancelled"},
    ]


def test_native_tool_events_suppress_only_the_duplicate_wrapper_events():
    progress = progress_api()
    events = []
    with progress.capture_progress(events.append):
        with progress.native_tool_progress():
            with progress.progress_tool("knowledge_tool", "查询政策"):
                progress.emit_progress("tool_started", tool_call_id="real-call", name="knowledge_tool")
                progress.emit_progress("tool_finished", tool_call_id="real-call", name="knowledge_tool")
        with progress.progress_tool("rule_tool", "核对测算规则"):
            pass
    tools = [event for event in events if event["type"].startswith("tool_")]
    assert [event["name"] for event in tools] == ["knowledge_tool", "knowledge_tool", "rule_tool", "rule_tool"]
    assert tools[0]["tool_call_id"] == tools[1]["tool_call_id"] == "real-call"
    assert tools[2]["tool_call_id"] == tools[3]["tool_call_id"]


def document(identity, chunk, *, source="https://example.gov.cn/policy.html"):
    return SimpleNamespace(
        id=identity, title=f"住房公积金管理条例（第{chunk}/6段）", source=source,
        content=f"第十八条 住房公积金缴存和提取规定。片段{chunk}",
        metadata={"path": "resources/data/process/policy.md", "source_url": source, "chunk_idx": chunk, "page": 4},
    )


def test_sources_preserve_numbering_identity_excerpt_and_real_navigation_fields():
    progress = progress_api()
    first, second = document("chunk-one", 1), document("chunk-six", 6)
    sources = progress.source_references([first, second])
    assert [item["id"] for item in sources] == ["chunk-one", "chunk-six"]
    assert [item["chunk_idx"] for item in sources] == [1, 6]
    assert sources[0]["document_id"] == sources[1]["document_id"]
    assert sources[0]["url"] == "https://example.gov.cn/policy.html"
    assert sources[0]["excerpt"] == first.content
    assert sources[0]["page"] == 4
    assert sources[0]["title"] == first.title
    assert sources[0]["document_title"] == "住房公积金管理条例"


def test_retrieved_fragment_titles_restore_numbers_without_inventing_a_document_identity():
    progress = progress_api()
    doc = document("vector-chunk-id", 6)
    doc.metadata = {}
    reference = progress.source_references([doc])[0]
    assert reference["id"] == "vector-chunk-id"
    assert reference["document_id"] == doc.source
    assert reference["chunk_number"] == reference["chunk_total"] == 6
    assert reference["chunk_idx"] == 5
    doc.source = "unidentified local origin"
    reference = progress.source_references([doc])[0]
    assert not reference["document_id"] and not reference["url"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:password@example.gov.cn/", "https://example.gov.cn/\nprivate"])
def test_source_navigation_rejects_active_credentials_and_control_characters(url):
    progress = progress_api()
    sources = progress.source_references([document("one", 1, source=url)])
    assert not sources[0]["url"]


@pytest.fixture
def service_module(monkeypatch):
    """Load the actual service definitions without clients, SQL or parser imports."""
    progress = progress_api()
    source = ast.parse((ROOT / "app/agents/service/agent_service.py").read_text(encoding="utf-8-sig"))
    definitions = [node for node in source.body if isinstance(node, ast.ClassDef) and node.name in {"_RequestState", "_PerfTrace", "AgentService"}]
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *definitions], type_ignores=[])
    module = ModuleType("_progress_service_under_test")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    module.__dict__.update(
        asyncio=asyncio, ContextVar=ContextVar, dataclass=dataclass, field=field,
        time=time, re=re, uuid4=uuid4,
        emit_progress=progress.emit_progress, progress_step=progress.progress_step,
        progress_tool=progress.progress_tool, source_references=progress.source_references,
        logging_manager=Mock(), session_store=SimpleNamespace(add_answer=Mock()),
        autogen_memory_store=SimpleNamespace(add_assistant_message=AsyncMock()),
    )
    exec(compile(ast.fix_missing_locations(tree), str(ROOT / "app/agents/service/agent_service.py"), "exec"), module.__dict__)
    return module


def make_service(module):
    service = module.AgentService.__new__(module.AgentService)
    service._request_state = ContextVar("progress_request")
    service.config = SimpleNamespace(answer_plain_output=False)
    service._agentchat_enabled = service._agentchat_team_enabled = False
    service._log_timing_breakdown = False
    service._trace_latency, service._slow_log_ms = False, 1000
    return service


def test_final_source_payload_keeps_multiple_fragments_in_original_citation_order(service_module):
    module = service_module
    service = make_service(module)
    documents = [document("one", 1), document("six", 6)]
    final = SimpleNamespace(answer="依据资料1及资料2。", sources=documents, metadata={})
    events = []

    async def run():
        token = service._request_state.set(module._RequestState())
        try:
            with progress_api().capture_progress(events.append):
                return await service._finalize_answer(
                    final=final, route="knowledge", intent_result={"intent": "policy"},
                    rewritten_query="policy", session_id="one", user_id=None, connection_id=None,
                    conversation_context={}, domain_context=None, attachments=[],
                    trace=module._PerfTrace(False, 1000), start_time=time.perf_counter(),
                )
        finally:
            service._request_state.reset(token)

    result = asyncio.run(run())
    assert [item["id"] for item in result.metadata["sources"]] == ["one", "six"]
    assert next(event["sources"] for event in events if event["type"] == "sources") == result.metadata["sources"]
    assert [(event["type"], event["name"]) for event in events if event["type"].startswith("step_")] == [
        ("step_started", "answer_finalize"), ("step_finished", "answer_finalize")
    ]


def test_pipeline_reports_only_real_stages_and_tool_failure_is_closed(service_module):
    module = service_module
    service = make_service(module)
    service.initialize = AsyncMock()
    service._prepare_conversation_context = AsyncMock(return_value=("one", "policy", {"history": [], "is_new_session": False}, False))
    service._resolve_session_attachments = Mock(return_value=[])
    service._looks_like_greeting = Mock(return_value=False)
    service.faq_responder = SimpleNamespace(maybe_answer=Mock(return_value=None))
    service.rewrite_agent = SimpleNamespace(rewrite=AsyncMock(return_value="policy"))
    service._domain_context_builder = SimpleNamespace(build=Mock(return_value=SimpleNamespace(to_metadata=lambda: {})))
    service._fast_route = Mock(return_value="knowledge")
    service.knowledge_agent = SimpleNamespace(answer=AsyncMock(side_effect=RuntimeError("private error details")))
    events = []

    async def run():
        with progress_api().capture_progress(events.append):
            with pytest.raises(RuntimeError, match="private error details"):
                await service.process_query("policy", allow_private_tools=False)
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())
    stages = {event["name"] for event in events if event["type"] == "step_started"}
    assert {"context", "faq", "rewrite", "knowledge"} <= stages
    assert "rule" not in stages and "graph" not in stages
    assert events[-1]["type"] == "step_finished" and events[-1]["status"] == "error"
    assert "private error details" not in str(events)


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
def test_autogen_stream_reports_actual_tool_call_ids_without_replay_or_payload_leaks(monkeypatch, filename):
    import importlib.util
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage, ToolCallExecutionEvent, ToolCallRequestEvent
    from autogen_core import FunctionCall
    from autogen_core.models import FunctionExecutionResult

    memory = ModuleType("app.agents.framework.common.autogen_memory_store")
    monkeypatch.setitem(sys.modules, memory.__name__, memory)
    module_name = f"_progress_{filename}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"app/agents/service/{filename}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    wrapper = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(), rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
    calls, observations, closed = [], [], []

    async def stream(**kwargs):
        calls.append(kwargs)
        try:
            yield ToolCallRequestEvent(content=[FunctionCall(id="real-id", name="knowledge_tool", arguments='{"query":"private input"}')], source="assistant")
            yield ToolCallExecutionEvent(content=[FunctionExecutionResult(call_id="real-id", name="knowledge_tool", content="private raw result", is_error=False)], source="assistant")
            yield TaskResult(messages=[TextMessage(content="final answer", source="assistant")], stop_reason="done")
        finally:
            closed.append(True)

    backend = SimpleNamespace(run_stream=stream, run=Mock(side_effect=AssertionError("no replay")))
    setattr(wrapper, "_get_or_create_agent" if filename == "agentchat_router" else "_get_or_create_team", AsyncMock(return_value=backend))

    async def run():
        with progress_api().capture_progress(observations.append):
            return [item async for item in wrapper.run_stream("session", "question")]

    events = asyncio.run(run())
    assert events[-1]["answer"].answer == "final answer"
    assert len(calls) == len(closed) == 1
    assert [item["type"] for item in observations] == ["tool_started", "tool_finished"]
    assert all(item["tool_call_id"] == "real-id" for item in observations)
    assert "private input" not in str(observations) and "private raw result" not in str(observations)


def test_knowledge_sources_arrive_after_retrieval_and_before_model_generation(monkeypatch):
    import logging

    progress = progress_api()
    source = ast.parse((ROOT / "app/agents/pipeline/knowledge_agent.py").read_text(encoding="utf-8-sig"))
    definition = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "KnowledgeAgent")
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), definition], type_ignores=[])
    namespace = {
        "asyncio": asyncio, "time": time, "re": re, "uuid4": uuid4,
        "progress_step": progress.progress_step, "emit_progress": progress.emit_progress,
        "source_references": progress.source_references, "FinalAnswer": SimpleNamespace,
        "settings": SimpleNamespace(system=SimpleNamespace(early_stop_conf=0.8)),
        "UserMessage": lambda **kwargs: SimpleNamespace(**kwargs),
    }
    exec(compile(ast.fix_missing_locations(tree), "knowledge_agent.py", "exec"), namespace)
    agent = namespace["KnowledgeAgent"].__new__(namespace["KnowledgeAgent"])
    doc = document("retrieved-one", 1)
    doc.retrieval_origin = "knowledge_base"
    events = []

    async def search(*args):
        assert events[-1] == {"type": "step_started", "name": "retrieval", "label": "正在检索相关政策"}
        return [doc], [0.4], "policy"

    async def create(messages):
        assert [event["type"] for event in events] == ["step_started", "step_finished", "sources", "step_started"]
        assert events[-2]["sources"][0]["excerpt"] == doc.content
        assert events[-1]["name"] == "answer_generation"
        return SimpleNamespace(content="基于资料1的答复")

    namespace["model_client"] = SimpleNamespace(create=create)
    agent._domain_aware_search = search
    agent.tool = SimpleNamespace(last_timings={})
    agent._insurance_source_matches = Mock(return_value=True)
    agent._requested_period = Mock(return_value=None)
    agent._should_direct_return_dify = Mock(return_value=False)
    agent._estimate_confidence = Mock(return_value=0.4)
    agent._extract_preexisting_contract_answer = Mock(return_value=None)
    agent._format_documents = Mock(return_value="资料1原文")
    agent._build_summary_prompt = Mock(return_value="prompt")
    agent._remove_unsupported_applicability_labels = lambda answer, docs: answer
    agent._collect_images = Mock(return_value=[])
    agent.logger = logging.getLogger(__name__)

    async def run():
        with progress.capture_progress(events.append):
            return await agent.answer("办理材料有哪些")

    final = asyncio.run(run())
    assert final.answer == "基于资料1的答复"
    assert events[-1] == {"type": "step_finished", "name": "answer_generation", "label": "正在根据政策依据生成答复", "status": "completed"}


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
@pytest.mark.parametrize("session_id", [
    "staff:8c6976e5b5410415bde908bd:session_9d95de84421747909c2d2f7895b0ef82",
    "public:" + "long-signed-session-part_" * 12,
    "工作人员:咨询会话/公积金",
    "",
])
def test_agent_names_fit_the_actual_openai_sdk_contract(monkeypatch, filename, session_id):
    import importlib.util
    from autogen_ext.models.openai._utils import assert_valid_name

    memory = ModuleType("app.agents.framework.common.autogen_memory_store")
    memory.build_buffered_context = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setitem(sys.modules, memory.__name__, memory)
    common = importlib.import_module("app.agents.framework.common")
    monkeypatch.setattr(common, "autogen_memory_store", memory, raising=False)
    module_name = f"_name_contract_{filename}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"app/agents/service/{filename}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    created_names = []

    def create_agent(name, **kwargs):
        # This is the same validation used while constructing OpenAI messages,
        # without issuing a model request or needing a configured API key.
        assert_valid_name(name)
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        assert len(name) < 64
        created_names.append(name)
        return SimpleNamespace(name=name)

    monkeypatch.setattr(module, "AssistantAgent", create_agent)
    if filename == "agentchat_team":
        monkeypatch.setattr(module, "UserProxyAgent", create_agent)
        monkeypatch.setattr(module, "RoundRobinGroupChat", lambda participants, **kwargs: SimpleNamespace(participants=participants))
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    wrapper = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(), rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
    get_agent = wrapper._get_or_create_agent if filename == "agentchat_router" else wrapper._get_or_create_team

    async def run():
        first = await get_agent(session_id)
        assert await get_agent(session_id) is first
        other = await get_agent(session_id + ":other")
        assert other is not first

    asyncio.run(run())
    assert len(set(created_names)) == len(created_names)
    assert [call.args[0] for call in memory.build_buffered_context.await_args_list] == [session_id, session_id + ":other"]


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
def test_distinct_punctuation_sessions_do_not_share_agent_names(monkeypatch, filename):
    import importlib.util

    memory = ModuleType("app.agents.framework.common.autogen_memory_store")
    memory.build_buffered_context = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setitem(sys.modules, memory.__name__, memory)
    monkeypatch.setattr(importlib.import_module("app.agents.framework.common"), "autogen_memory_store", memory, raising=False)
    module_name = f"_name_identity_{filename}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"app/agents/service/{filename}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    def create(name, **kwargs):
        return SimpleNamespace(name=name)
    monkeypatch.setattr(module, "AssistantAgent", create)
    if filename == "agentchat_team":
        monkeypatch.setattr(module, "UserProxyAgent", create)
        monkeypatch.setattr(module, "RoundRobinGroupChat", lambda participants, **kwargs: SimpleNamespace(participants=participants))
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    wrapper = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(), rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
    get_agent = wrapper._get_or_create_agent if filename == "agentchat_router" else wrapper._get_or_create_team

    async def run():
        first, second = await get_agent("session-a"), await get_agent("session:a")
        if filename == "agentchat_router":
            assert first.name != second.name
        else:
            assert {agent.name for agent in first.participants}.isdisjoint(agent.name for agent in second.participants)

    asyncio.run(run())
