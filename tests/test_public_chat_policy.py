"""Offline regressions for trusted public/staff tool permissions."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


class GraphBuilder:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)

    def add_edge(self, source, target):
        pass

    def build(self):
        return self.nodes


class Message(SimpleNamespace):
    pass


@pytest.fixture
def policy_modules(monkeypatch):
    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    async def close_callback(callback):
        await callback()

    modules = {
        "app.agents.domain.policy_domain": {"PolicyDomainContext": Mock(), "PolicyDomainContextBuilder": Mock()},
        "app.agents.framework.common": {"autogen_memory_store": Mock(), "session_store": Mock()},
        "app.agents.pipeline.dialog_agent": {"ask_for_clarification": Mock(), "respond_to_dialogue": Mock()},
        "app.agents.pipeline.graph_agent": {"GraphAgent": Mock()},
        "app.agents.pipeline.knowledge_agent": {"KnowledgeAgent": Mock()},
        "app.agents.pipeline.rewrite_agent": {"RewriteAgent": Mock()},
        "app.agents.pipeline.rule_agent": {"RuleEngineAgent": Mock()},
        "app.agents.pipeline.text2sql_agent": {"answer_text2sql_query": AsyncMock()},
        "app.agents.service.agentchat_router": {"AgentChatRouter": Mock(), "agentchat_enabled": Mock()},
        "app.agents.service.agentchat_team": {"AgentChatTeam": Mock(), "agentchat_team_enabled": Mock()},
        "app.agents.service.tools": {name: Mock() for name in (
            "IntentDetectionTool", "KnowledgeTool", "VisionTool", "WebSearchTool", "UserProfileTool"
        )},
        "app.config.agent_config": {"AgentServiceConfig": Mock()},
        "app.config.app_config": {"settings": SimpleNamespace()},
        "app.core.llms": {"model_client": Mock()},
        "app.core.logging_manager": {"logging_manager": Mock()},
        "app.knowledge.document_loader": {"DocumentLoader": Mock()},
        "app.knowledge.faq_responder": {"FAQResponder": Mock()},
        "app.knowledge.service": {"KnowledgeService": Mock()},
        "app.models.policy": {name: SimpleNamespace for name in (
            "Attachment", "FinalAnswer", "PolicyDocument", "UserQuery"
        )},
        "app.persistence.crud.db_connection": {"db_connection": Mock()},
        "app.persistence.db.session": {"SessionLocal": Mock()},
        "app.utils.lifecycle": {"close_with_timeout": close_callback},
        "autogen_agentchat.agents": {"AssistantAgent": lambda name, **kwargs: SimpleNamespace(name=name, **kwargs)},
        "autogen_agentchat.base": {"ChatAgent": SimpleNamespace},
        "autogen_agentchat.conditions": {"SourceMatchTermination": Mock()},
        "autogen_agentchat.messages": {"BaseChatMessage": Message, "TextMessage": Message},
        "autogen_agentchat.teams": {"DiGraphBuilder": GraphBuilder, "GraphFlow": lambda **kwargs: SimpleNamespace(**kwargs)},
        "autogen_core.tools": {
            "BaseTool": Mock(),
            "FunctionTool": lambda function, **kwargs: SimpleNamespace(name=function.__name__, function=function, **kwargs),
        },
    }
    packages = set()
    for name in (*modules, "app.agents.pipeline.workflow_agent", "app.agents.service.agent_service"):
        parts = name.split(".")
        packages.update(".".join(parts[:index]) for index in range(1, len(parts)))
    for package in sorted(packages):
        stub(package)
    for name, attributes in modules.items():
        stub(name, **attributes)

    def load(name):
        spec = importlib.util.spec_from_file_location(name, ROOT.joinpath(*name.split(".")).with_suffix(".py"))
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    workflow = load("app.agents.pipeline.workflow_agent")
    service = load("app.agents.service.agent_service")
    return SimpleNamespace(workflow=workflow, service=service)


@pytest.fixture
def service(policy_modules):
    module = policy_modules.service
    instance = module.AgentService.__new__(module.AgentService)
    instance._request_state = ContextVar("public_policy_request")
    instance._trace_latency = False
    instance._slow_log_ms = 1000
    instance._agentchat_enabled = False
    instance._agentchat_team_enabled = False
    instance.initialize = AsyncMock()
    instance._resolve_connection_id = Mock(return_value=23)
    instance._resolve_session_attachments = Mock(return_value=[])
    instance._prepare_conversation_context = AsyncMock(return_value=(
        "owned-session", "effective question", {"history": [], "is_new_session": True}, False
    ))
    instance._looks_like_greeting = Mock(return_value=True)
    instance._finalize_answer = AsyncMock(side_effect=lambda **kwargs: kwargs["final"])
    final = SimpleNamespace(answer="政策答复", sources=[], metadata={})
    module.respond_to_dialogue.return_value = final
    instance.faq_responder = SimpleNamespace(maybe_answer=Mock(return_value=None))
    instance.rewrite_agent = SimpleNamespace(rewrite=AsyncMock(return_value="政策问题"))
    instance._domain_context_builder = SimpleNamespace(build=Mock(return_value=SimpleNamespace(to_metadata=lambda: {})))
    instance._fast_route = Mock(return_value="workflow")
    instance.workflow_agent = SimpleNamespace(answer=AsyncMock(return_value=final))
    return instance


def test_public_query_never_resolves_default_database_and_resets_context(service):
    observed_permissions = []

    def finish(**kwargs):
        observed_permissions.append(service._request.allow_private_tools)
        return kwargs["final"]

    service._finalize_answer.side_effect = finish

    async def run():
        result = await service.process_query("你好", allow_private_tools=False)
        assert result.answer == "政策答复"
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())
    assert observed_permissions == [False]
    service._resolve_connection_id.assert_not_called()
    assert service._finalize_answer.await_args.kwargs["connection_id"] is None


def test_existing_staff_caller_keeps_default_database_resolution(service):
    asyncio.run(service.process_query("你好"))
    service._resolve_connection_id.assert_called_once_with(None)
    assert service._finalize_answer.await_args.kwargs["connection_id"] == 23


def test_concurrent_public_and_staff_requests_keep_separate_permissions(service):
    async def run():
        entered = 0
        ready = asyncio.Event()

        async def finish(**kwargs):
            nonlocal entered
            permission = service._request.allow_private_tools
            entered += 1
            if entered == 2:
                ready.set()
            await ready.wait()
            assert service._request.allow_private_tools is permission
            return SimpleNamespace(permission=permission)

        service._finalize_answer.side_effect = finish
        results = await asyncio.gather(
            service.process_query("public", allow_private_tools=False),
            service.process_query("staff", allow_private_tools=True),
        )
        assert [result.permission for result in results] == [False, True]
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())


@pytest.mark.parametrize("streamed", [False, True])
@pytest.mark.parametrize("private_args", [
    {"force_text2sql": True}, {"connection_id": 1}, {"connection_id": 0},
    {"user_id": "someone"}, {"user_id": ""},
])
def test_public_private_arguments_fail_before_any_request_work(service, streamed, private_args):
    async def run():
        with pytest.raises(PermissionError):
            if streamed:
                await anext(service.process_query_stream("question", allow_private_tools=False, **private_args))
            else:
                await service.process_query("question", allow_private_tools=False, **private_args)
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())
    service.initialize.assert_not_awaited()
    service._resolve_connection_id.assert_not_called()
    service._prepare_conversation_context.assert_not_awaited()


def test_model_selected_sql_tool_cannot_access_database(service, policy_modules):
    async def run():
        token = service._request_state.set(policy_modules.service._RequestState(allow_private_tools=False))
        try:
            with pytest.raises(PermissionError):
                await service._tool_agentchat_text2sql("SELECT private_data")
        finally:
            service._request_state.reset(token)

    asyncio.run(run())
    service._resolve_connection_id.assert_not_called()
    policy_modules.service.answer_text2sql_query.assert_not_awaited()


def test_direct_sql_route_cannot_bypass_public_permission(service, policy_modules):
    service._looks_like_greeting.return_value = False
    service._fast_route.return_value = "text2sql"
    with pytest.raises(PermissionError):
        asyncio.run(service.process_query("private SQL", allow_private_tools=False))
    service._resolve_connection_id.assert_not_called()
    policy_modules.service.answer_text2sql_query.assert_not_awaited()


@pytest.mark.parametrize("allowed", [False, True])
def test_pipeline_and_agentchat_workflow_receive_request_permission(service, policy_modules, allowed):
    service._looks_like_greeting.return_value = False
    asyncio.run(service.process_query("政策问题", allow_private_tools=allowed))
    assert service.workflow_agent.answer.await_args.kwargs["allow_user_profile"] is allowed
    service.workflow_agent.answer.reset_mock()

    async def run_tool():
        token = service._request_state.set(policy_modules.service._RequestState(allow_private_tools=allowed))
        try:
            assert await service._tool_agentchat_workflow("政策问题") == "政策答复"
        finally:
            service._request_state.reset(token)

    asyncio.run(run_tool())
    assert service.workflow_agent.answer.await_args.kwargs["allow_user_profile"] is allowed


@pytest.mark.parametrize("allowed", [False, True])
def test_stream_fallback_keeps_permission_argument_and_outer_context(service, allowed):
    observed_permissions = []

    async def answer(*args, **kwargs):
        observed_permissions.append(service._request.allow_private_tools)
        return SimpleNamespace(answer="policy", metadata={})

    service.process_query = AsyncMock(side_effect=answer)

    async def run():
        events = [event async for event in service.process_query_stream("question", allow_private_tools=allowed)]
        assert events[0]["type"] == "final"
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())
    assert observed_permissions == [allowed]
    assert service.process_query.await_args.kwargs["allow_private_tools"] is allowed


def test_public_live_stream_skips_database_and_cleans_up_in_its_request_context(service):
    service._agentchat_enabled = True
    closed_permissions = []

    async def backend_stream(session_id, query):
        try:
            assert service._request.allow_private_tools is False
            yield {"type": "chunk", "content": "政策"}
        finally:
            closed_permissions.append(service._request.allow_private_tools)

    service._agentchat_router = SimpleNamespace(run_stream=backend_stream)

    async def run():
        stream = service.process_query_stream("question", allow_private_tools=False)
        assert (await anext(stream))["content"] == "政策"
        await stream.aclose()
        with pytest.raises(LookupError):
            service._request_state.get()

    asyncio.run(run())
    service._resolve_connection_id.assert_not_called()
    assert closed_permissions == [False]


def make_workflow(module):
    return module.WorkflowAgent(
        vision_tool=SimpleNamespace(enabled=True, describe=AsyncMock(return_value="图片内容")),
        knowledge_agent=SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(answer="政策内容"))),
        rule_agent=SimpleNamespace(compute=AsyncMock(return_value=SimpleNamespace(answer="补贴计算"))),
        user_profile_tool=SimpleNamespace(fetch=AsyncMock(return_value={"found": True}), format_profile=Mock(return_value="私人档案")),
    )


def test_public_workflow_keeps_vision_knowledge_rules_and_omits_profiles(policy_modules):
    workflow = make_workflow(policy_modules.workflow)
    context = {}
    attachment = SimpleNamespace(path="public-attachment")
    flow = workflow._build_flow(context, [attachment], None, allow_user_profile=False)
    agents = {agent.name: agent for agent in flow.participants}
    tools = {tool.name: tool for tool in agents["task_router"].tools}
    assert set(tools) == {"query_policy_knowledge", "execute_rule_engine"}

    async def run():
        assert await agents["vision_analyzer"].tools[0].function("read") == "图片内容"
        assert await tools["query_policy_knowledge"].function("question") == "政策内容"
        assert await tools["execute_rule_engine"].function("calculate") == "补贴计算"

    asyncio.run(run())
    workflow.user_profile_tool.fetch.assert_not_awaited()


def test_staff_workflow_can_still_read_user_profile(policy_modules):
    workflow = make_workflow(policy_modules.workflow)
    flow = workflow._build_flow({}, [], None)
    router = next(agent for agent in flow.participants if agent.name == "task_router")
    profile_tool = next(tool for tool in router.tools if tool.name == "fetch_user_profile")
    assert asyncio.run(profile_tool.function(" employee-id ")) == "私人档案"
    workflow.user_profile_tool.fetch.assert_awaited_once_with("employee-id")


@pytest.mark.parametrize("allowed", [False, True])
def test_workflow_answer_passes_permission_into_flow(policy_modules, allowed):
    workflow = make_workflow(policy_modules.workflow)

    async def empty_stream(**kwargs):
        for event in ():
            yield event

    workflow._build_flow = Mock(return_value=SimpleNamespace(run_stream=empty_stream))
    workflow._select_final_answer = Mock(return_value=SimpleNamespace(metadata={}))
    asyncio.run(workflow.answer("政策问题", allow_user_profile=allowed))
    assert workflow._build_flow.call_args.kwargs["allow_user_profile"] is allowed
