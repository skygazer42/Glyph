"""Offline behavior regressions for runtime lifecycle and model boundaries."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("-inf"), float("nan")])
def test_cleanup_requires_finite_positive_budget(load_module, timeout):
    import asyncio

    module = load_module("app/utils/lifecycle.py")
    close = Mock()

    async def run():
        with pytest.raises(ValueError):
            await module.close_with_timeout(close, cleanup_timeout=timeout)

    asyncio.run(run())
    close.assert_not_called()


@pytest.fixture
def load_module(monkeypatch):
    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        monkeypatch.setitem(sys.modules, name, module)
        return module

    for name in ("app", "app.core", "app.models", "app.agents", "app.agents.framework", "app.agents.framework.common"):
        stub(name)

    def load(path, *, name=None):
        module_name = name or "_runtime_audit_" + path.replace("/", "_").replace(".", "_")
        spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        return module

    load.stub = stub
    return load


def test_llm_config_maps_first_entry_and_preserves_zero(load_module, monkeypatch):
    module = load_module("app/agents/framework/common/model_client.py")
    construct = Mock()
    monkeypatch.setattr(module, "OpenAIChatCompletionClient", construct)
    config: dict[str, Any] = {
        "config_list": [{"model": "deepseek-chat", "api_key": "first", "base_url": "https://example.test"},
                        {"model": "gpt-4o", "api_key": "second"}],
        "temperature": 0, "timeout": 12, "seed": 0,
    }
    module.create_openai_client(llm_config=config)
    actual = construct.call_args.kwargs
    assert actual["model"] == "deepseek-chat"
    assert actual["api_key"] == "first"
    assert actual["temperature"] == actual["seed"] == 0
    assert actual["timeout"] == 12
    assert actual["model_info"]["family"] == "unknown"
    assert config["config_list"][0]["model"] == "deepseek-chat"


def test_llm_config_rejects_empty_config_list(load_module):
    module = load_module("app/agents/framework/common/model_client.py")
    with pytest.raises(ValueError, match="config_list"):
        module.create_openai_client(llm_config={"config_list": []})


def test_session_creation_is_atomic_and_failed_store_not_published(load_module):
    import concurrent.futures
    import time
    module = load_module("app/agents/framework/common/session_manager.py")
    store = Mock()
    def fetch(*args):
        time.sleep(0.01)
        return None
    store.fetch_session.side_effect = fetch
    store.ensure_session.side_effect = lambda *a, **kw: time.sleep(0.01)
    manager = module.SessionManager(history_store=store)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        sessions = list(pool.map(lambda _: manager.get_or_create_session("same"), range(8)))
    assert len({id(session) for session in sessions}) == 1
    assert store.ensure_session.call_count == 1
    store.ensure_session.side_effect = RuntimeError("offline store")
    with pytest.raises(RuntimeError, match="offline store"):
        manager.create_session("failed")
    assert "failed" not in manager.sessions


def test_session_zero_limit_and_context_snapshot(load_module):
    module = load_module("app/agents/framework/common/session_manager.py")
    manager = module.SessionManager()
    manager.create_session("one")
    manager.add_message("one", "user", "hello")
    assert manager.get_messages("one", limit=0) == []
    returned = manager.get_messages("one")
    returned[0]["content"] = "corruption"
    assert manager.get_messages("one")[0]["content"] == "hello"
    manager.update_context("one", {"nested": {"answer": 1}})
    manager.get_context("one")["nested"]["answer"] = 2
    assert manager.get_context("one")["nested"]["answer"] == 1


def test_session_expiry_preserves_persisted_history_until_explicit_delete(load_module):
    import asyncio

    module = load_module("app/agents/framework/common/session_manager.py")
    store = Mock()
    manager = module.SessionManager(timeout=1, history_store=store)
    session = manager.create_session("one")
    manager.create_message_queue("one")
    session.last_active = module.time.time() - 2

    asyncio.run(manager.cleanup_expired_sessions())

    assert "one" not in manager.sessions
    assert manager.get_message_queue("one") is None
    store.delete_session.assert_not_called()
    manager.delete_session("one")
    store.delete_session.assert_called_once_with("one")


def test_policy_agent_uses_actual_runtime_and_memory_contract(load_module):
    import asyncio
    from autogen_core import AgentId, AgentInstantiationContext, SingleThreadedAgentRuntime
    models = load_module("app/models/policy.py", name="app.models.policy")
    module = load_module("app/agents/framework/base/base_agent.py")
    policy_base: Any = module.PolicyAgentBase
    class Agent(policy_base):
        async def process_request(self, request, context):
            return request
        async def _handle_user_query(self, message, context):
            return await self.process_request(message.content, context)
    async def check():
        runtime = SingleThreadedAgentRuntime()
        try:
            with AgentInstantiationContext.populate_context((runtime, AgentId("test", "default"))):
                agent = Agent(models.AgentType.QUERY_ANALYZER, "agent", "test", memory_size=1)
            message = models.AgentMessage(type=models.MessageType.USER_QUERY,
                sender=models.AgentType.COORDINATOR, content={"query": "first"})
            await agent._store_in_memory(message)
            message.content = {"query": "second"}
            await agent._store_in_memory(message)
            assert agent.get_metrics()["memory_size"] == 1
            assert "second" in await agent.get_memory_context()
            assert await agent.get_memory_context(limit=0) == ""
            assert await agent._route_message(message, None) == {"query": "second"}
        finally:
            await runtime.close()
    asyncio.run(check())


def test_session_context_independent_mutable_defaults(load_module):
    load_module.stub("app.agents.framework.coordination")
    load_module.stub("app.agents.framework.base.base_agent", PolicyAgentBase=object)
    load_module("app/models/policy.py")
    module = load_module("app/agents/framework/coordination/session_manager.py", name="app.agents.framework.coordination.session_manager")
    first = module.SessionContext(session_id="first")
    second = module.SessionContext(session_id="second")
    first.queries.append({"text": "hello"})
    assert second.queries == []


@pytest.mark.parametrize("payload", [
    {},
    {"action": "update_context", "context": {}},
    {"action": "update_context", "session_id": "missing"},
    {"action": "add_query", "session_id": "missing"},
    {"action": "add_answer", "session_id": "missing"},
])
def test_session_action_missing_required_field_is_visible(load_module, payload):
    import asyncio

    load_module.stub("app.agents.framework.coordination")
    load_module.stub("app.agents.framework.base.base_agent", PolicyAgentBase=object)
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module("app/agents/framework/coordination/session_manager.py", name="app.agents.framework.coordination.session_manager")
    agent = module.SessionManagerAgent.__new__(module.SessionManagerAgent)
    agent.sessions = {}

    async def run():
        with pytest.raises(KeyError):
            await agent.process_request(payload, None)
        assert await agent.process_request({"action": "add_query", "session_id": "missing", "query": "hello"}, None) is False

    asyncio.run(run())


def test_session_store_one_turn_and_zero_history(load_module, monkeypatch):
    from types import SimpleNamespace
    load_module("app/models/policy.py")
    module = load_module("app/agents/framework/common/session_store.py", name="app.agents.framework.common.session_store")
    monkeypatch.setattr(module, "MAX_TURNS", 1)
    monkeypatch.setattr(module, "HISTORY_WINDOW", 0)
    module.create_or_update_session("one", None)
    module.add_query("one", SimpleNamespace(text="first", id="first"))
    module.add_query("one", SimpleNamespace(text="last", id="last"))
    assert [item["text"] for item in module._SESSIONS["one"]["queries"]] == ["last"]
    assert module.get_context("one")["history"] == []


@pytest.mark.parametrize("write_method", ["add_query", "add_answer"])
def test_session_write_requires_existing_session(load_module, write_method):
    load_module("app/models/policy.py", name="app.models.policy")
    store = load_module("app/agents/framework/common/session_store.py", name="app.agents.framework.common.session_store")
    with pytest.raises(KeyError, match="missing"):
        getattr(store, write_method)("missing", Mock())


def test_llm_setup_preserves_proxy_environment(load_module, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    load_module.stub("app.config.app_config", settings=SimpleNamespace(model=SimpleNamespace(
        llm_model_name="gpt-4o", llm_api_key="not-real", llm_temperature=0, llm_base_url=None,
        llm_max_tokens=None, llm_timeout=None)))
    module = load_module("app/core/llms.py")
    import os
    assert os.environ["HTTPS_PROXY"] == "http://proxy.invalid:8080"
    import asyncio
    asyncio.run(module.model_client.close())


def test_coordinator_request_state_isolated_and_serializes_models(load_module):
    import asyncio
    import json
    from datetime import datetime
    from types import SimpleNamespace
    models = load_module("app/models/policy.py", name="app.models.policy")
    types_module = load_module("app/agents/framework/base/types.py", name="app.agents.framework.base.types")
    # The coordinator is a business workflow; it must not require a Core runtime.
    load_module.stub("app.agents.framework.base.base_agent", BaseAgent=object)
    module = load_module("app/agents/framework/coordination/coordinator.py", name="app.agents.framework.coordination.coordinator")
    doc = models.PolicyDocument(title="policy", content="content", source="source",
        doc_type=models.PolicyType.GUIDELINE, publish_date=datetime(2024, 1, 1))
    async def question(query):
        await asyncio.sleep(0)
        return {"success": True, "data": types_module.AnalysisReport(query, "general", [], [], [])}
    async def retrieve(payload):
        query = json.loads(payload)["query"]
        return {"success": True, "data": types_module.QueryResult(query, [doc], [1.0], types_module.RetrievalMethod.HYBRID)}
    async def analyze(payload):
        data = json.loads(payload)
        assert isinstance(data["documents"][0]["id"], str)
        assert data["documents"][0]["publish_date"].startswith("2024-")
        return {"success": True, "data": {"document_analyses": []}}
    async def answer(payload):
        query = json.loads(payload)["query"]
        return {"success": True, "data": {"answer": query, "sources": [], "confidence": 1}}
    agents = {key.value: SimpleNamespace(process_message=fn) for key, fn in [
        (types_module.AgentTypes.QUESTION_UNDERSTANDER, question),
        (types_module.AgentTypes.POLICY_RETRIEVER, retrieve),
        (types_module.AgentTypes.POLICY_ANALYZER, analyze),
        (types_module.AgentTypes.ANSWER_GENERATOR, answer),
    ]}
    async def check():
        coordinator = module.Coordinator("coordinator", {}, agents)
        results = await asyncio.gather(coordinator.process_query("first"), coordinator.process_query("second"))
        assert all(item["success"] for item in results), results
        assert [item["answer"]["answer"] for item in results] == ["first", "second"]
        assert [item["workflow_state"]["query"] for item in results] == ["first", "second"]
        assert results[0]["answer"]["metadata"]["retrieved_documents"] == 1
        json.dumps(results)
    asyncio.run(check())


def _load_core_modules(load_module):
    load_module.stub("app.agents.framework.core")
    load_module.stub("app.agents.framework.models")
    models = load_module("app/agents/framework/models/base.py", name="app.agents.framework.models.base")
    bus = load_module("app/agents/framework/core/message_bus.py", name="app.agents.framework.core.message_bus")
    base = load_module("app/agents/framework/core/agent_base.py", name="app.agents.framework.core.agent_base")
    registry = load_module("app/agents/framework/core/agent_registry.py", name="app.agents.framework.core.agent_registry")
    return models, bus, base, registry


def test_registry_uses_ids_and_waits_for_dependency_creation(load_module):
    import asyncio
    models, _, base, module = _load_core_modules(load_module)
    agent_base: Any = base.AgentBase
    class Agent(agent_base):
        async def process(self, message):
            return message
    async def check():
        registry = module.AgentRegistry()
        registry.register("dep", Agent, models.AgentType.KNOWLEDGE, "Human name")
        registry.register("root", Agent, models.AgentType.KNOWLEDGE, "Another name", dependencies=["dep"])
        registry.disable_agent("dep")
        assert [item.name for item in registry.list_agents()] == ["Another name"]
        registry.enable_agent("dep")
        chain = await registry.create_dependency_chain("root")
        assert [item.agent_id for item in chain] == ["dep", "root"]
        registry.unregister("dep")
        assert registry._agents_by_type[models.AgentType.KNOWLEDGE] == [registry.get_agent_info("root")]
        await registry.shutdown_all()
    asyncio.run(check())


def test_bus_delivers_directed_messages_once_and_tracks_failure(load_module):
    import asyncio
    models, module, _, _ = _load_core_modules(load_module)
    async def check():
        bus = module.MessageBus()
        first, second = Mock(), Mock()
        bus.subscribe(models.MessageType.DATA, first, agent_id="first")
        bus.subscribe(models.MessageType.DATA, second, agent_id="second")
        await bus._dispatch_message(module.Message(models.MessageType.DATA, {}, "sender", recipient="first"))
        assert first.call_count == 1
        assert second.call_count == 0
        failing = Mock(side_effect=RuntimeError("handler failed"))
        bus = module.MessageBus()
        bus.subscribe(models.MessageType.DATA, failing)
        await bus._dispatch_message(module.Message(models.MessageType.DATA, {}, "sender"))
        assert bus.get_stats()["messages_delivered"] == 0
        assert bus.get_stats()["messages_failed"] == 1
    asyncio.run(check())


def test_embedding_index_paths_and_negative_faiss_matches(load_module, tmp_path, monkeypatch):
    import numpy as np
    module = load_module("app/agents/framework/common/embedding_manager.py")
    index = tmp_path / "index.bin"
    manager = module.EmbeddingManager(backend="openai", index_path=str(index), embedding_dim=2)
    assert manager.metadata_path != manager.index_path
    manager.documents_metadata = [{"title": "last"}]
    manager.index = Mock()
    manager.index.search.return_value = (np.array([[0.9]]), np.array([[-1]]))
    monkeypatch.setattr(manager, "encode_documents", lambda docs: np.array([[1.0, 0.0]], dtype=np.float32))
    assert manager.search("query", threshold=0.0) == ([], [])
    with pytest.raises(ValueError, match="metadata"):
        manager.add_documents(["one", "two"], [{"title": "one"}])


def test_factory_uses_json_config_and_requires_compatible_answer_agent(load_module, tmp_path):
    import asyncio
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/agents/framework/base/types.py", name="app.agents.framework.base.types")
    owned = []
    for name, class_name in [("policy_retriever", "PolicyRetriever"), ("question_builder", "QuestionUnderstander"), ("policy_review", "PolicyReviewAgent")]:
        agent = SimpleNamespace(close=AsyncMock())
        owned.append(agent)
        load_module.stub("app.agents.packs." + name + ".node", **{class_name: Mock(return_value=agent)})
    load_module.stub("app.agents.packs.answer_generator.node", AnswerGeneratorAgent=Mock())
    load_module.stub("app.agents.framework.coordination.coordinator", Coordinator=Mock())
    path = tmp_path / "models.json"
    path.write_text(json.dumps([{"model": "gpt-4o", "api_key": "not-real"}]))
    module = load_module("app/agents/framework/base/factory.py", name="app.agents.framework.base.factory")
    factory = module.AgentFactory(config_path=str(path))
    assert factory.llm_config["config_list"][0]["model"] == "gpt-4o"
    with pytest.raises(TypeError, match="answer_generator"):
        factory.create_all_agents()
    with pytest.raises(NotImplementedError, match="AgentChatTeam"):
        factory.create_agent_group()
    vector = SimpleNamespace(close=Mock())
    load_module.stub("app.knowledge.milvus", MilvusStore=Mock(return_value=vector))
    supplied = SimpleNamespace(process_message=Mock())
    factory.create_all_agents(answer_generator=supplied)
    assert factory.get_agent(module.AgentTypes.ANSWER_GENERATOR) is supplied
    async def close():
        await factory.aclose()
        await factory.aclose()
    asyncio.run(close())
    for resource in owned:
        resource.close.assert_awaited_once()
    vector.close.assert_called_once()


def test_memory_limit_zero_and_redis_health_closes_client(load_module, monkeypatch):
    import asyncio
    client = Mock()
    load_module.stub("redis", Redis=Mock(from_url=Mock(return_value=client)))
    module = load_module("app/agents/framework/common/autogen_memory_store.py")
    async def check():
        await module.add_user_message("one", "hello")
        assert module.get_recent_messages("one", limit=0) == []
    asyncio.run(check())
    monkeypatch.setattr(module, "_REDIS_CFG", {"redis_url": "redis://not-real"})
    health = module.redis_health()
    assert health["connectivity"] == "ok"
    assert health["backend"] == "local" and health["persistent"] is False
    client.close.assert_called_once()


def test_router_stream_uses_terminal_answer_without_replaying_tools(load_module):
    import asyncio
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage
    load_module.stub("app.agents.framework.common.autogen_memory_store")
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module("app/agents/service/agentchat_router.py")
    class Assistant:
        name = "router_one"
        def __init__(self):
            self.calls = 0
        async def run_stream(self, *, task):
            self.calls += 1
            yield TaskResult(messages=[TextMessage(content="only once", source=self.name)], stop_reason="done")
        async def run(self, *, task):
            self.calls += 1
            raise AssertionError("tool pipeline must not be replayed")
    async def check():
        router = module.AgentChatRouter(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(),
            rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
        assistant = Assistant()
        async def ensure(session_id):
            return assistant
        router._get_or_create_agent = ensure
        events = [event async for event in router.run_stream("one", "query")]
        assert assistant.calls == 1
        assert events[-1]["answer"].answer == "only once"
    asyncio.run(check())


def _load_service_module(load_module):
    import logging
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    models = load_module("app/models/policy.py", name="app.models.policy")
    load_module.stub("app.agents.framework.base.types", PolicyDocument=models.PolicyDocument)
    load_module.stub("app.agents.pipeline.dialog_agent", ask_for_clarification=Mock(), respond_to_dialogue=Mock())
    for module, name in (
        ("graph_agent", "GraphAgent"), ("knowledge_agent", "KnowledgeAgent"),
        ("rewrite_agent", "RewriteAgent"), ("rule_agent", "RuleEngineAgent"),
        ("workflow_agent", "WorkflowAgent"),
    ):
        load_module.stub(f"app.agents.pipeline.{module}", **{name: Mock()})
    load_module.stub("app.agents.pipeline.text2sql_agent", answer_text2sql_query=AsyncMock())
    load_module.stub("app.agents.framework.common.session_store", add_answer=Mock())
    load_module.stub("app.agents.framework.common.autogen_memory_store")
    load_module.stub("app.agents.service.agentchat_router", AgentChatRouter=Mock(), agentchat_enabled=lambda: False)
    load_module.stub("app.agents.service.agentchat_team", AgentChatTeam=Mock(), agentchat_team_enabled=lambda: False)
    load_module.stub("app.agents.service.tools", **{name: Mock() for name in ("IntentDetectionTool", "KnowledgeTool", "VisionTool", "WebSearchTool", "UserProfileTool")})
    load_module.stub("app.agents.domain.policy_domain", PolicyDomainContext=Mock(), PolicyDomainContextBuilder=Mock())
    load_module.stub("app.core.logging_manager", UTF8JsonFormatter=logging.Formatter, logging_manager=Mock())
    load_module.stub("app.config.app_config", settings=SimpleNamespace())
    load_module.stub("app.config.agent_config", AgentServiceConfig=Mock())
    load_module.stub("app.knowledge.document_loader", DocumentLoader=Mock())
    load_module.stub("app.knowledge.service", KnowledgeService=Mock())
    load_module.stub("app.knowledge.faq_responder", FAQResponder=Mock())
    load_module.stub("app.persistence.db.session", SessionLocal=Mock())
    load_module.stub("app.persistence.crud.db_connection", db_connection=Mock())
    load_module.stub("app.core.llms", model_client=Mock())
    return load_module("app/agents/service/agent_service.py", name="app.agents.service.agent_service"), models


@pytest.mark.parametrize("agentchat_meta", [None, {}, {"primary_tool": "knowledge_tool"}])
def test_answer_finalization_accepts_optional_agentchat_metadata(load_module, agentchat_meta):
    import asyncio
    import time
    from contextvars import ContextVar
    from unittest.mock import AsyncMock

    module, models = _load_service_module(load_module)
    service = module.AgentService.__new__(module.AgentService)
    service._request_state = ContextVar("finalization_state")
    service.config = types.SimpleNamespace(answer_plain_output=False)
    service._agentchat_enabled = service._agentchat_team_enabled = False
    service._log_timing_breakdown = False
    module.autogen_memory_store.add_assistant_message = AsyncMock()
    final = models.FinalAnswer(query_id="00000000-0000-0000-0000-000000000001", answer="hello", sources=[], confidence=1, metadata={})

    async def run():
        token = service._request_state.set(module._RequestState())
        try:
            result = await service._finalize_answer(
                final=final, route="dialogue", intent_result={"intent": "greeting"},
                rewritten_query="hello", session_id="one", user_id=None, connection_id=None,
                conversation_context={"history": []}, domain_context=None, attachments=[],
                trace=module._PerfTrace(False, 1000), start_time=time.perf_counter(),
                agentchat_meta=agentchat_meta,
            )
            assert result.answer == "hello"
            assert result.metadata["tools_used"] == (["知识库检索"] if agentchat_meta else ["对话生成"])
            module.session_store.add_answer.assert_called_once_with("one", final)
        finally:
            service._request_state.reset(token)

    asyncio.run(run())


def test_service_request_attachments_are_isolated(load_module, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    module, models = _load_service_module(load_module)
    monkeypatch.setattr(module, "_configure_logging_once", lambda: None)
    config = SimpleNamespace(web_search=SimpleNamespace(tavily_api_key=None, max_results=3, search_depth="basic", enabled=False, site_filter=""),
        vision=SimpleNamespace(enabled=False, model="gpt-4o", api_key=None, base_url=None, prompt_template="", max_images=1, max_output_tokens=20),
        user_profile_db_path="", performance=SimpleNamespace(batch_size=1, trace_latency=False, slow_threshold_ms=100, log_timing_breakdown=False))
    service = module.AgentService(config=config)
    service._agentchat_enabled = True
    service._agentchat_no_fallback = False
    service._looks_like_greeting = lambda query: False
    service._looks_like_multimodal_invoice_question = lambda **kwargs: False
    service.faq_responder.maybe_answer.return_value = None
    service._resolve_connection_id = lambda connection_id: connection_id
    async def initialize(): pass
    service.initialize = initialize
    async def prepare(session_id, user_id, query): return session_id, query, {"history": [], "is_new_session": True}, False
    service._prepare_conversation_context = prepare
    async def rewrite(query, *, context): return query
    service.rewrite_agent.rewrite = rewrite
    async def finalize(**kwargs): return kwargs["final"]
    service._finalize_answer = finalize
    async def workflow(query, *, attachments, intent, allow_user_profile=True):
        return SimpleNamespace(answer=attachments[0].path, sources=[])
    service.workflow_agent.answer = workflow
    entered = 0
    ready = asyncio.Event()
    async def route(session_id, query):
        nonlocal entered
        entered += 1
        if entered == 2:
            ready.set()
        await ready.wait()
        return SimpleNamespace(answer=await service._tool_agentchat_workflow(query)), {}
    service._agentchat_router = SimpleNamespace(run=route)
    async def check():
        results = await asyncio.gather(*(service.process_query(name, session_id=name,
            attachments=[models.Attachment(path=name)]) for name in ("first", "second")))
        assert [item.answer for item in results] == ["first", "second"]
    asyncio.run(check())


def _load_tools_module(load_module):
    models = load_module("app/models/policy.py", name="app.models.policy")
    load_module.stub("app.agents.framework.base.types", PolicyDocument=models.PolicyDocument)
    load_module.stub("app.agents.packs.intent_router.utils", LLMIntentClassifier=Mock())
    load_module.stub("app.knowledge.service", KnowledgeService=Mock())
    return load_module("app/agents/service/tools.py")


def test_dify_response_closes_and_preserves_zero_score(load_module, monkeypatch):
    import requests
    module = _load_tools_module(load_module)
    response = Mock()
    response.json.return_value = {"hits": [{"content": "answer", "score": 0, "similarity": 0.9}]}
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    proxy = module.DifyKnowledgeProxy()
    docs, scores = proxy._search_sync("query", 1)
    assert scores == [0.0]
    assert len(docs) == 1
    response.close.assert_called_once()


def test_preset_user_profile_does_not_load_disk_or_lose_empty_record(load_module, tmp_path):
    module = _load_tools_module(load_module)
    path = tmp_path / "profiles.json"
    path.write_text('{"disk": {"name": "unexpected"}}')
    tool = module.UserProfileTool(db_path=str(path), preset_db={"empty": {}})
    import asyncio
    result = asyncio.run(tool.fetch("empty"))
    assert result["found"] is True
    assert asyncio.run(tool.fetch("disk"))["found"] is False


def test_vision_owned_client_closes_once(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module = _load_tools_module(load_module)
    tool = module.VisionTool()
    client = AsyncMock()
    tool._client = client
    async def check():
        await tool.aclose()
        await tool.aclose()
    asyncio.run(check())
    client.close.assert_awaited_once()


def test_knowledge_ingest_appends_vectors_off_loop_without_rebuilding_snapshot(load_module, monkeypatch):
    import asyncio
    import threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    monkeypatch.setenv("DIFY_KB_ENABLED", "false")
    module = _load_tools_module(load_module)
    writes = []

    def add_documents(documents):
        writes.append((documents, threading.get_ident()))

    service = SimpleNamespace(vector_store=SimpleNamespace(add_documents=add_documents),
                              index_documents=AsyncMock(side_effect=AssertionError("must preserve full snapshot")))
    tool = module.KnowledgeTool(service=service)
    documents = [object(), object()]
    assert asyncio.run(tool.ingest(documents)) == 2
    assert writes[0][0] is documents and writes[0][1] != threading.get_ident()
    service.index_documents.assert_not_awaited()


@pytest.mark.parametrize("filters,threshold,uses_dify", [(None, 0.6, True), ({"source": "allowed"}, 0.6, False), (None, 1, False)])
def test_knowledge_search_respects_filters_and_dify_threshold(load_module, monkeypatch, filters, threshold, uses_dify):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    monkeypatch.setenv("DIFY_KB_ENABLED", "false")
    module = _load_tools_module(load_module)
    low, high, local = object(), object(), object()
    service = SimpleNamespace(search=AsyncMock(return_value=([local], [1])), last_timings={})
    tool = module.KnowledgeTool(service=service)
    tool._dify = SimpleNamespace(enabled=True, search=AsyncMock(return_value=([low, high], [0.2, 0.9])))
    result = asyncio.run(tool.search("policy", threshold=threshold, filters=filters))
    if uses_dify:
        assert result == ([high], [0.9])
        service.search.assert_not_awaited()
    else:
        assert result == ([local], [1])
        service.search.assert_awaited_once_with("policy", top_k=5, threshold=threshold, filters=filters)
    if filters:
        tool._dify.search.assert_not_awaited()
    else:
        tool._dify.search.assert_awaited_once_with("policy", top_k=5)


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf")])
def test_knowledge_search_rejects_invalid_threshold_before_storage(load_module, monkeypatch, threshold):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    monkeypatch.setenv("DIFY_KB_ENABLED", "false")
    module = _load_tools_module(load_module)
    service = SimpleNamespace(search=AsyncMock())
    tool = module.KnowledgeTool(service=service)
    with pytest.raises(ValueError, match="threshold"):
        asyncio.run(tool.search("policy", threshold=threshold))
    service.search.assert_not_awaited()


@pytest.mark.parametrize("model_name,payload", [
    ("_WebSearchHit", {"title": "Policy", "content": "Text", "url": "https://example.test"}),
    ("_DifySearchHit", {"content": "Text"}),
])
@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_external_search_scores_reject_nonfinite_values(load_module, model_name, payload, score):
    module = _load_tools_module(load_module)
    with pytest.raises(ValueError):
        getattr(module, model_name).model_validate({**payload, "score": score})


@pytest.mark.parametrize("url,has_path,expected", [
    ("https://example.test/image.png", False, "remote"),
    ("data:image/png;base64,cG5n", False, "remote"),
    ("/attachments/image.png", True, "local"),
    ("/attachments/image.png", False, "error"),
    ("file:///outside.png", False, "error"),
])
def test_openai_vision_uses_absolute_urls_or_local_uploaded_bytes(load_module, tmp_path, url, has_path, expected):
    module = _load_tools_module(load_module)
    path = tmp_path / "image.png"
    path.write_bytes(b"png")
    attachment = module.Attachment(url=url, path=str(path) if has_path else None, mime_type="image/png")
    tool = module.VisionTool()
    if expected == "error":
        with pytest.raises(ValueError, match="absolute"):
            tool._resolve_image_url(attachment)
    else:
        assert tool._resolve_image_url(attachment) == (url if expected == "remote" else "data:image/png;base64,cG5n")


@pytest.mark.parametrize("backend,expected_route", [("team", "agentchat_team_error"), ("router", "agentchat_router_error")])
def test_agentchat_without_fallback_keeps_structured_backend_error(load_module, backend, expected_route):
    import asyncio
    from contextvars import ContextVar
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    module, _ = _load_service_module(load_module)
    service = object.__new__(module.AgentService)
    service._request_state = ContextVar("backend_error")
    service._trace_latency, service._slow_log_ms = False, 100
    service.initialize = AsyncMock()
    service._resolve_connection_id = Mock(return_value=None)
    service._prepare_conversation_context = AsyncMock(return_value=(
        "session", "policy", {"history": [], "is_new_session": False}, False,
    ))
    service._resolve_session_attachments = Mock(return_value=[])
    service.faq_responder = SimpleNamespace(maybe_answer=Mock(return_value=None))
    service._agentchat_enabled, service._agentchat_team_enabled = backend == "router", backend == "team"
    service._agentchat_no_fallback = True
    runner = SimpleNamespace(run=AsyncMock(return_value=(None, {"error": "backend unavailable"})))
    service._agentchat_team = runner if backend == "team" else None
    service._agentchat_router = runner if backend == "router" else None
    service._finalize_answer = AsyncMock(side_effect=lambda **kwargs: kwargs["final"])

    answer = asyncio.run(service.process_query("政策补贴条件", session_id="session"))

    assert answer.verification_passed is False
    assert answer.metadata["route"] == expected_route
    assert answer.metadata["agentchat_meta"]["error"] == "backend unavailable"
    assert service._finalize_answer.call_args.kwargs["route"] == expected_route


def _load_orchestrator_module(load_module):
    models, bus, _, _ = _load_core_modules(load_module)
    module = load_module("app/agents/framework/core/orchestrator.py", name="app.agents.framework.core.orchestrator")
    return module, models, bus


def test_workflow_success_uses_seconds_and_default_branch(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module, models, bus = _load_orchestrator_module(load_module)
    calls = []
    async def handle(message):
        calls.append(message.content["number"])
        return bus.Message(models.MessageType.DATA, {"number": message.content["number"] + 1}, "agent")
    agent = types.SimpleNamespace(handle_message=handle)
    orchestrator = module.AgentOrchestrator(types.SimpleNamespace(get_instance=AsyncMock(return_value=agent)), None)
    orchestrator.create_conditional_workflow("branch", {"chosen": ["one", "two", "three"], "other": ["no"]}, default_branch="chosen")
    result = asyncio.run(orchestrator.execute_workflow("branch", bus.Message(models.MessageType.DATA, {"number": 0}, "user")))
    assert result.content == {"number": 3}
    assert calls == [0, 1, 2]
    assert isinstance(orchestrator.get_stats()["execution_stats"]["avg_execution_time"], float)


def test_parallel_workflow_executes_dependency_waves_and_rejects_cycles(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module, models, bus = _load_orchestrator_module(load_module)
    calls = []
    def agent(name):
        async def handle(message):
            calls.append(name)
            if name == "third":
                assert message.content["first"] == 1 and message.content["second"] == 1
            return bus.Message(models.MessageType.DATA, {name: 1}, name)
        return types.SimpleNamespace(handle_message=handle)
    agents = {name: agent(name) for name in ("first", "second", "third")}
    registry = types.SimpleNamespace(get_instance=AsyncMock(side_effect=lambda name: agents[name]))
    orchestrator = module.AgentOrchestrator(registry, None)
    workflow = module.Workflow("parallel").set_strategy(module.ExecutionStrategy.PARALLEL)
    for name in agents:
        workflow.add_step(module.WorkflowStep(name, name))
    workflow.add_dependency("third", "first").add_dependency("third", "second")
    orchestrator.register_workflow(workflow)
    result = asyncio.run(orchestrator.execute_workflow("parallel", bus.Message(models.MessageType.DATA, {}, "user")))
    assert result.content == {"first": 1, "second": 1, "third": 1}
    assert calls[-1] == "third"
    workflow.add_dependency("first", "third")
    with pytest.raises(ValueError, match="[Cc]ycle"):
        orchestrator._get_execution_order(workflow)


def test_missing_or_failed_required_workflow_step_is_failed(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module, models, bus = _load_orchestrator_module(load_module)
    registry = types.SimpleNamespace(get_instance=AsyncMock(return_value=None))
    orchestrator = module.AgentOrchestrator(registry, None)
    orchestrator.create_simple_workflow("missing", ["missing"])
    assert asyncio.run(orchestrator.execute_workflow("missing", bus.Message(models.MessageType.DATA, {}, "user"))) is None
    assert orchestrator.execution_stats["failed_executions"] == 1


def test_controller_uses_supported_intents_and_cleans_partial_start(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    _, models, _ = _load_orchestrator_module(load_module)
    module = load_module("app/agents/framework/core/agent_master.py", name="app.agents.framework.core.agent_master")
    controller = module.AgentMasterController()
    assert controller._route_to_agent(models.QueryIntent.BENEFIT_CALCULATION) == "calculation_agent"
    controller.message_bus = types.SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    async def fail():
        raise RuntimeError("registration failed")
    controller._auto_register_agents = fail
    assert asyncio.run(controller.initialize()) is False
    controller.message_bus.stop.assert_awaited_once()
    controller.registry.shutdown_all = AsyncMock(side_effect=RuntimeError("shutdown failed"))
    with pytest.raises(RuntimeError, match="shutdown failed"):
        asyncio.run(controller.stop())
    assert controller.message_bus.stop.await_count == 2


def test_controller_preserves_explicit_core_registration(load_module):
    import asyncio
    _, models, _ = _load_orchestrator_module(load_module)
    base = sys.modules["app.agents.framework.core.agent_base"]
    module = load_module("app/agents/framework/core/agent_master.py", name="app.agents.framework.core.agent_master")
    agent_base: Any = base.AgentBase
    class Agent(agent_base):
        async def process(self, message):
            return message
    async def check():
        controller = module.AgentMasterController()
        controller.register_agent_module("custom", Agent, models.AgentType.KNOWLEDGE, "Display name", auto_create=False)
        assert await controller.initialize() is True
        controller.orchestrator.create_simple_workflow("custom", ["custom"])
        assert await controller.process_request({"question": "offline"}, "custom") == {"question": "offline"}
        await controller.stop()
        assert not controller.running and not controller.registry._instances
    asyncio.run(check())


@pytest.mark.parametrize("config,error", [
    ({"type": "sequential"}, KeyError),
    ({"type": "conditional"}, KeyError),
    ({"type": "unsupported"}, ValueError),
])
def test_controller_rejects_incomplete_workflow_config(load_module, config, error):
    import asyncio

    _load_orchestrator_module(load_module)
    module = load_module("app/agents/framework/core/agent_master.py", name="app.agents.framework.core.agent_master")
    controller = module.AgentMasterController()
    with pytest.raises(error):
        asyncio.run(controller.create_workflow_from_config("invalid", config))
    assert "invalid" not in controller.orchestrator.workflows


def test_explicit_unknown_workflow_does_not_run_default(load_module):
    import asyncio
    from unittest.mock import AsyncMock

    _load_orchestrator_module(load_module)
    module = load_module("app/agents/framework/core/agent_master.py", name="app.agents.framework.core.agent_master")
    controller = module.AgentMasterController()
    controller._default_process = AsyncMock()
    assert asyncio.run(controller.process_request({"question": "policy"}, "missing")) is None
    controller._default_process.assert_not_awaited()


def test_parallel_failure_cancels_owned_sibling(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module, models, bus = _load_orchestrator_module(load_module)
    async def check():
        entered = asyncio.Event()
        closed = asyncio.Event()
        async def block(message):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()
        async def fail(message):
            await entered.wait()
            raise RuntimeError("failed")
        agents = {"block": types.SimpleNamespace(handle_message=block), "fail": types.SimpleNamespace(handle_message=fail)}
        orchestrator = module.AgentOrchestrator(types.SimpleNamespace(get_instance=AsyncMock(side_effect=lambda name: agents[name])), None)
        workflow = module.Workflow("failure").set_strategy(module.ExecutionStrategy.PARALLEL)
        for name in agents:
            workflow.add_step(module.WorkflowStep(name, name))
        orchestrator.register_workflow(workflow)
        assert await orchestrator.execute_workflow("failure", bus.Message(models.MessageType.DATA, {}, "user")) is None
        assert closed.is_set()
        assert orchestrator.execution_stats["failed_executions"] == 1
    asyncio.run(check())


def test_chat_history_zero_limit_and_delete_failure_closes_session(load_module):
    load_module.stub("app.persistence.db.session", SessionLocal=Mock())
    load_module.stub("app.models.chat_history", ChatMessage=Mock(), ChatSession=Mock())
    crud = load_module.stub("app.persistence.crud.chat_history", **{name: Mock() for name in ("chat_session", "chat_message", "chat_history_snapshot")})
    load_module.stub("app.persistence.crud.db_connection", db_connection=Mock())
    schemas = load_module("app/schemas/chat_history.py", name="app.schemas.chat_history")
    assert schemas.ChatSessionCreate
    module = load_module("app/agents/service/chat_history_store.py")
    db = Mock()
    messages = [types.SimpleNamespace(session_id="one", message_type="user_query", content=f"message-{index}",
                region=None, message_metadata={}, order_index=index, created_at=None) for index in range(105)]

    def get_messages(db, *, session_id, limit=100):
        return messages if limit is None else messages[:limit]

    crud.chat_message.get_by_session.side_effect = get_messages
    store = module.ChatHistoryStore(session_factory=lambda: db)
    assert store.list_messages("one", limit=0) == []
    db.close.assert_called_once()
    recent = store.list_messages("one", limit=2)
    assert [message["content"] for message in recent] == ["message-103", "message-104"]
    assert len(store.list_messages("one")) == 105
    db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        store.delete_session("one")
    db.rollback.assert_called_once()
    assert db.close.call_count == 4


def test_scheduled_coroutine_closes_when_cancelled_before_first_step(load_module):
    import asyncio
    import inspect
    from autogen_core import AgentId, AgentInstantiationContext, SingleThreadedAgentRuntime
    models = load_module("app/models/policy.py", name="app.models.policy")
    module = load_module("app/agents/framework/base/base_agent.py")
    proactive_base: Any = module.ProactiveAgent
    class Agent(proactive_base):
        async def process_request(self, request, context):
            return request
    async def check():
        runtime = SingleThreadedAgentRuntime()
        try:
            with AgentInstantiationContext.populate_context((runtime, AgentId("test", "default"))):
                agent = Agent(models.AgentType.QUERY_ANALYZER, "agent", description="test")
            async def work():
                raise AssertionError("cancelled work must not start")
            coroutine = work()
            await agent.schedule_task(coroutine, delay=10)
            await agent.stop()
            assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
            assert not agent._scheduled_tasks
        finally:
            await runtime.close()
    asyncio.run(check())


def test_service_loads_entire_document_batch_outside_event_loop(load_module, tmp_path):
    import asyncio
    import threading
    from unittest.mock import AsyncMock
    module, _ = _load_service_module(load_module)
    owner_thread = threading.get_ident()
    def documents(path):
        assert threading.get_ident() != owner_thread
        yield "first"
        yield "second"
    service = module.AgentService.__new__(module.AgentService)
    service._loader = types.SimpleNamespace(iter_documents_from_directory=documents)
    service._ingest_batch_size = 1
    service.knowledge_tool = types.SimpleNamespace(ingest=AsyncMock(return_value=1))
    service.graph_agent = types.SimpleNamespace(ingest=AsyncMock(return_value=1))
    assert asyncio.run(service.ingest_paths([str(tmp_path)])) == {"loaded_docs": 2, "kb_indexed": 2, "rag_indexed": 2}


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
def test_agentchat_memory_failure_is_visible(load_module, filename):
    import asyncio
    from unittest.mock import AsyncMock
    load_module.stub("app.agents.framework.common.autogen_memory_store",
                     build_buffered_context=AsyncMock(side_effect=RuntimeError("corrupt memory")))
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module(f"app/agents/service/{filename}.py")
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    router = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(),
                 rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
    with pytest.raises(RuntimeError, match="corrupt memory"):
        asyncio.run(router.run("session", "query"))


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
def test_agentchat_empty_reply_is_failure(load_module, filename):
    import asyncio
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage
    from unittest.mock import AsyncMock
    load_module.stub("app.agents.framework.common.autogen_memory_store")
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module(f"app/agents/service/{filename}.py")
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    router = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(),
                 rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())
    backend = types.SimpleNamespace(run=AsyncMock(return_value=TaskResult(
        messages=[TextMessage(content="question", source="user")], stop_reason="empty")))
    if filename == "agentchat_router":
        router._get_or_create_agent = AsyncMock(return_value=backend)
    else:
        router._get_or_create_team = AsyncMock(return_value=backend)
    final, debug = asyncio.run(router.run("session", "question"))
    assert final is None
    assert "answer" in debug["error"]


def test_conversation_history_excludes_current_query_and_counts_turns(load_module, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    module, _ = _load_service_module(load_module)
    store = load_module("app/agents/framework/common/session_store.py", name="app.agents.framework.common.session_store")
    memory = load_module("app/agents/framework/common/autogen_memory_store.py")
    monkeypatch.setattr(module, "session_store", store)
    monkeypatch.setattr(module, "autogen_memory_store", memory)
    monkeypatch.setattr(module, "settings", types.SimpleNamespace(system=types.SimpleNamespace(
        conversation_history_window=5)))
    service = module.AgentService.__new__(module.AgentService)
    async def check():
        sid, first, context, used = await service._prepare_conversation_context(None, None, "first")
        assert sid and first == "first" and used is False and context["is_new_session"] is True
        await memory.add_assistant_message(sid, "response")
        next_sid, query, context, used = await service._prepare_conversation_context(sid, None, "second")
        assert next_sid == sid and used is True and context["is_new_session"] is False
        assert query.count("second") == 1
        assert "first" in query and "response" in query
        assert store._SESSIONS[sid]["query_count"] == 2
        monkeypatch.setattr(memory, "add_user_message", AsyncMock(side_effect=RuntimeError("memory unavailable")))
        with pytest.raises(RuntimeError, match="memory unavailable"):
            await service._prepare_conversation_context(sid, None, "third")
    asyncio.run(check())


def test_service_stream_closes_in_same_request_context_and_records_final(load_module):
    import asyncio
    from contextvars import ContextVar
    from unittest.mock import AsyncMock
    module, models = _load_service_module(load_module)
    service = module.AgentService.__new__(module.AgentService)
    service._request_state = ContextVar("stream_state")
    service._session_attachments_store = {}
    service._agentchat_enabled = True
    service._agentchat_team_enabled = False
    service._trace_latency = False
    service._slow_log_ms = 1000
    service.initialize = AsyncMock()
    service._resolve_connection_id = lambda value: value
    service._prepare_conversation_context = AsyncMock(return_value=("unique", "context question", {"history": [], "is_new_session": True}, False))
    service._finalize_answer = AsyncMock(side_effect=lambda **kwargs: kwargs["final"])
    module.autogen_memory_store.add_user_message = AsyncMock()
    closed = []
    received = []
    async def stream(sid, query):
        received.append((sid, query))
        try:
            yield {"type": "chunk", "content": "token"}
            yield {"type": "final", "answer": models.FinalAnswer(
                query_id="00000000-0000-0000-0000-000000000001", answer="answer", sources=[],
                confidence=1, metadata={"route": "agentchat_stream"}), "meta": {"duration_ms": 10}}
        finally:
            closed.append(service._request)
    service._agentchat_router = types.SimpleNamespace(run_stream=stream)
    async def check():
        iterator = service.process_query_stream("question")
        assert (await anext(iterator))["content"] == "token"
        await iterator.aclose()
        assert len(closed) == 1
        with pytest.raises(LookupError):
            service._request_state.get()
        events = [event async for event in service.process_query_stream("question")]
        assert events[-1]["answer"].answer == "answer"
        service._finalize_answer.assert_awaited_once()
        assert received == [("unique", "context question"), ("unique", "context question")]
    asyncio.run(check())


def test_core_agent_serializes_shared_state_and_releases_on_cancel(load_module, monkeypatch):
    import asyncio
    models, bus, base, _ = _load_core_modules(load_module)
    agent_base: Any = base.AgentBase
    class Agent(agent_base):
        async def process(self, message):
            await asyncio.sleep(0)
            return message
    async def check():
        agent = Agent("one", models.AgentType.KNOWLEDGE, "One")
        entered = []
        release = asyncio.Event()
        async def process(message):
            entered.append(message.content["index"])
            if message.content["index"] == 1:
                await release.wait()
            return message
        monkeypatch.setattr(agent, "process", process)
        first = asyncio.create_task(agent.handle_message(bus.Message(models.MessageType.DATA, {"index": 1}, "user")))
        await asyncio.sleep(0)
        second = asyncio.create_task(agent.handle_message(bus.Message(models.MessageType.DATA, {"index": 2}, "user")))
        await asyncio.sleep(0)
        assert entered == [1]
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await second
        assert entered == [1, 2] and agent.status == base.AgentStatus.IDLE
        assert agent.get_status()["metrics"]["processed_count"] == 1
    asyncio.run(check())


def test_profile_corruption_is_visible_and_caller_metadata_is_owned(load_module, tmp_path):
    import asyncio
    module = _load_tools_module(load_module)
    path = tmp_path / "profiles.json"
    path.write_text('{"broken":', encoding="utf-8")
    with pytest.raises(ValueError):
        module.UserProfileTool(db_path=str(path))
    preset = {"user": {"name": "User", "history": ["one"], "found": False, "user_id": "spoof"}}
    tool = module.UserProfileTool(preset_db=preset)
    result = asyncio.run(tool.fetch("user"))
    assert result["found"] is True and result["user_id"] == "user"
    result["history"].append("bad")
    assert preset["user"]["history"] == ["one"]


def test_memory_negative_limit_rejected_even_without_session(load_module):
    module = load_module("app/agents/framework/common/autogen_memory_store.py")
    with pytest.raises(ValueError, match="limit"):
        module.get_recent_messages("missing", limit=-1)


def test_handler_cancellation_not_counted_as_delivery(load_module):
    import asyncio
    models, module, _, _ = _load_core_modules(load_module)
    async def cancelled(message):
        raise asyncio.CancelledError()
    async def check():
        bus = module.MessageBus()
        bus.subscribe(models.MessageType.DATA, cancelled)
        with pytest.raises(asyncio.CancelledError):
            await bus._dispatch_message(module.Message(models.MessageType.DATA, {}, "sender"))
        assert bus.get_stats()["messages_delivered"] == 0
    asyncio.run(check())


def test_knowledge_initialization_off_loop_and_shared_once(load_module, monkeypatch):
    import asyncio
    import threading
    module = _load_tools_module(load_module)
    owner_thread = threading.get_ident()
    service = Mock()
    def build():
        assert threading.get_ident() != owner_thread
        return service
    construct = Mock(side_effect=build)
    monkeypatch.setattr(module, "KnowledgeService", construct)
    tool = module.KnowledgeTool()
    async def check():
        first, second = await asyncio.gather(tool.get_service(), tool.get_service())
        assert first is second is service
        assert construct.call_count == 1
    asyncio.run(check())


def test_web_and_vision_failures_are_visible(load_module):
    import asyncio
    from unittest.mock import AsyncMock
    module = _load_tools_module(load_module)
    web = module.WebSearchTool(enabled=False)
    web._client = Mock(search=Mock(side_effect=RuntimeError("network unavailable")))
    with pytest.raises(RuntimeError, match="network unavailable"):
        web.search("query")
    vision = module.VisionTool()
    vision._client = Mock()
    vision._client.chat.completions.create = AsyncMock(side_effect=RuntimeError("vision unavailable"))
    vision._build_openai_contents = lambda *args: [{"type": "text", "text": "q"}, {"type": "image_url", "image_url": {"url": "https://example.test/image"}}]
    with pytest.raises(RuntimeError, match="vision unavailable"):
        asyncio.run(vision._describe_openai("q", []))


def test_missing_required_search_dependency_fails_at_import(load_module, monkeypatch):
    import builtins

    _load_tools_module(load_module)
    original_import = builtins.__import__

    def import_without_tavily(name, *args, **kwargs):
        if name == "tavily":
            raise ModuleNotFoundError("No module named 'tavily'", name="tavily")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_tavily)
    with pytest.raises(ModuleNotFoundError, match="tavily"):
        load_module("app/agents/service/tools.py")


def test_explicit_search_enable_requires_credentials(load_module, monkeypatch):
    module = _load_tools_module(load_module)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        module.WebSearchTool(enabled=True)
    assert not module.WebSearchTool(enabled=False).enabled
    assert not module.WebSearchTool().enabled


@pytest.mark.parametrize("missing_field", ["title", "score"])
def test_search_result_missing_required_field_is_not_fabricated(load_module, monkeypatch, missing_field):
    module = _load_tools_module(load_module)
    result = {"title": "Policy", "content": "Details", "url": "https://example.test", "score": 0}
    del result[missing_field]
    monkeypatch.setattr(module, "TavilyClient", Mock(return_value=Mock(search=Mock(return_value={"results": [result]}))))
    tool = module.WebSearchTool(api_key="test-key", enabled=True)
    with pytest.raises(ValueError, match=missing_field):
        tool.search("policy")


def test_dify_missing_score_is_not_zero_relevance(load_module, monkeypatch):
    import requests

    module = _load_tools_module(load_module)
    response = Mock()
    response.json.return_value = {"hits": [{"content": "answer"}]}
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    with pytest.raises(ValueError, match="score"):
        module.DifyKnowledgeProxy()._search_sync("query", 1)
    response.close.assert_called_once()


def test_dify_fallback_only_handles_transport_failure(load_module, monkeypatch):
    import asyncio

    import requests

    module = _load_tools_module(load_module)
    monkeypatch.setenv("DIFY_KB_ENABLED", "true")
    monkeypatch.setenv("DIFY_KB_BASE_URL", "https://dify.example.test")
    monkeypatch.setenv("DIFY_KB_API_KEY", "test-key")
    monkeypatch.setenv("DIFY_KB_ID", "dataset")
    proxy = module.DifyKnowledgeProxy()
    search = Mock(side_effect=ValueError("malformed response"))
    monkeypatch.setattr(proxy, "_search_sync", search)
    with pytest.raises(ValueError, match="malformed response"):
        asyncio.run(proxy.search("query"))

    search.side_effect = requests.ConnectionError("unavailable")
    assert asyncio.run(proxy.search("query")) == ([], [])


def test_dify_invalid_json_response_propagates(load_module, monkeypatch):
    import asyncio

    import requests

    module = _load_tools_module(load_module)
    monkeypatch.setenv("DIFY_KB_ENABLED", "true")
    monkeypatch.setenv("DIFY_KB_BASE_URL", "https://dify.example.test")
    monkeypatch.setenv("DIFY_KB_API_KEY", "test-key")
    monkeypatch.setenv("DIFY_KB_ID", "dataset")
    response = requests.Response()
    response.status_code = 200
    response._content = b"not valid JSON"
    response.close = Mock()
    monkeypatch.setattr(requests, "post", Mock(return_value=response))

    with pytest.raises(requests.exceptions.JSONDecodeError):
        asyncio.run(module.DifyKnowledgeProxy().search("query"))
    response.close.assert_called_once()


@pytest.mark.parametrize("tool_name,dependency_name", [
    ("knowledge", "knowledge_agent"), ("graph", "graph_agent"),
    ("text2sql", "answer_text2sql_query"), ("workflow", "workflow_agent"),
])
def test_agentchat_tool_failure_is_reported_as_error(load_module, monkeypatch, tool_name, dependency_name):
    import asyncio
    from contextvars import ContextVar
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    module, _ = _load_service_module(load_module)
    service = module.AgentService.__new__(module.AgentService)
    service._request_state = ContextVar("tool_error_state")
    service._resolve_connection_id = lambda connection_id: 1
    fail = AsyncMock(side_effect=RuntimeError("upstream failed"))
    if tool_name == "text2sql":
        monkeypatch.setattr(module, dependency_name, fail)
    else:
        setattr(service, dependency_name, SimpleNamespace(answer=fail))

    async def check():
        token = service._request_state.set(module._RequestState())
        try:
            with pytest.raises(RuntimeError, match="upstream failed"):
                await getattr(service, f"_tool_agentchat_{tool_name}")("query")
            assert service._request.tool_metrics[-1]["error"] == "upstream failed"
        finally:
            service._request_state.reset(token)

    asyncio.run(check())


@pytest.mark.parametrize("metadata", [None, {}])
def test_dify_optional_metadata_without_title(load_module, monkeypatch, metadata):
    module = _load_tools_module(load_module)
    response = Mock()
    response.json.return_value = {"data": [{"content": "policy", "score": 0, "metadata": metadata}]}
    monkeypatch.setattr(module.requests, "post", Mock(return_value=response))
    proxy = module.DifyKnowledgeProxy()
    documents, scores = proxy._search_sync("policy", 1)
    assert documents[0].title == "Dify 知识库条目"
    assert scores == [0]
    response.close.assert_called_once()


def test_explicit_vision_enable_requires_credentials(load_module, monkeypatch):
    module = _load_tools_module(load_module)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        module.VisionTool(enabled=True)


def test_explicit_dify_enable_requires_configuration(load_module, monkeypatch):
    module = _load_tools_module(load_module)
    monkeypatch.setenv("DIFY_KB_ENABLED", "true")
    monkeypatch.delenv("DIFY_KB_BASE_URL", raising=False)
    monkeypatch.delenv("DIFY_KB_API_KEY", raising=False)
    monkeypatch.delenv("DIFY_KB_ID", raising=False)
    monkeypatch.delenv("DIFY_DATASET_ID", raising=False)
    with pytest.raises(ValueError, match="Dify"):
        module.DifyKnowledgeProxy()


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
@pytest.mark.parametrize("invalid_iterations", ["", "0", "-1"])
def test_invalid_agentchat_tool_budget_is_not_replaced(load_module, monkeypatch, filename, invalid_iterations):
    load_module.stub("app.agents.framework.common.autogen_memory_store")
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module(f"app/agents/service/{filename}.py")
    agent_class = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    monkeypatch.setenv("AGENTCHAT_MAX_TOOL_ITERATIONS", invalid_iterations)
    with pytest.raises(ValueError):
        agent_class(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(),
                    rule_tool=Mock(), text2sql_tool=Mock(), workflow_tool=Mock())


def test_registry_unregister_without_loop_preserves_registration(load_module):
    import asyncio
    models, _, base, registry_module = _load_core_modules(load_module)
    agent_base: Any = base.AgentBase
    class Agent(agent_base):
        async def process(self, message):
            return message
    registry = registry_module.AgentRegistry()
    registry.register("one", Agent, models.AgentType.KNOWLEDGE, "One")
    instance = asyncio.run(registry.create_instance("one"))
    with pytest.raises(RuntimeError, match="running event loop"):
        registry.unregister("one")
    assert registry.get_stats()["agents_by_type"]["knowledge"] == 1
    assert asyncio.run(registry.get_instance("one")) is instance
    asyncio.run(registry.shutdown_all())


@pytest.mark.parametrize("filename", ["agentchat_router", "agentchat_team"])
def test_agentchat_stream_closes_under_parent_cancellation(load_module, filename):
    import asyncio
    import anyio
    from autogen_agentchat.messages import ModelClientStreamingChunkEvent, ToolCallRequestEvent, ToolCallExecutionEvent
    from autogen_core import FunctionCall
    from autogen_core.models import FunctionExecutionResult
    from unittest.mock import AsyncMock
    load_module.stub("app.agents.framework.common.autogen_memory_store")
    load_module("app/models/policy.py", name="app.models.policy")
    module = load_module(f"app/agents/service/{filename}.py")
    cls = module.AgentChatRouter if filename == "agentchat_router" else module.AgentChatTeam
    router = cls(model_client=None, knowledge_tool=Mock(), graph_tool=Mock(), rule_tool=Mock(),
                 text2sql_tool=Mock(), workflow_tool=Mock())
    router._reflect_on_tool_use = True
    router._max_tool_iterations = 1
    closed = []
    class Stream:
        def __init__(self):
            self.events = iter([
                ToolCallRequestEvent(content=[FunctionCall(id="one", name="knowledge_tool", arguments="{}")], source="assistant"),
                ToolCallExecutionEvent(content=[FunctionExecutionResult(call_id="one", name="knowledge_tool", content="policy", is_error=False)], source="assistant"),
                ModelClientStreamingChunkEvent(content="chunk", source="assistant"),
            ])
        def __aiter__(self):
            return self
        async def __anext__(self):
            return next(self.events)
        async def aclose(self):
            await anyio.lowlevel.checkpoint()
            closed.append(asyncio.current_task())
    backend = Mock(run_stream=Mock(return_value=Stream()))
    setattr(router, "_get_or_create_agent" if filename == "agentchat_router" else "_get_or_create_team", AsyncMock(return_value=backend))
    async def check():
        with anyio.CancelScope() as scope:
            stream = router.run_stream("one", "query")
            assert (await anext(stream))["content"] == "chunk"
            scope.cancel()
            await stream.aclose()
        assert closed == [asyncio.current_task()]
    asyncio.run(check())


def test_failed_document_read_is_not_successful_empty_ingest(load_module, tmp_path):
    import asyncio
    module, _ = _load_service_module(load_module)
    service = module.AgentService.__new__(module.AgentService)
    service._loader = Mock()
    service._loader.load_single_file.side_effect = OSError("unreadable document")
    service._ingest_batch_size = 1
    with pytest.raises(OSError, match="unreadable document"):
        asyncio.run(service.ingest_paths([str(tmp_path / "unreadable.pdf")]))


def test_failed_persistence_does_not_publish_memory_message(load_module):
    module = load_module("app/agents/framework/common/session_manager.py")
    store = Mock()
    store.record_message.side_effect = OSError("database unavailable")
    manager = module.SessionManager(history_store=store)
    manager.create_session("one", title="existing")
    with pytest.raises(OSError, match="database unavailable"):
        manager.add_message("one", "user", "question")
    assert manager.sessions["one"].messages == []
    assert manager.sessions["one"].message_count == 0


def test_cancelled_knowledge_initialization_remains_owned(load_module, monkeypatch):
    import asyncio
    import threading
    from unittest.mock import AsyncMock
    module = _load_tools_module(load_module)
    entered = threading.Event()
    release = threading.Event()
    built = threading.Event()
    service = Mock(close=AsyncMock())
    def build():
        entered.set()
        assert release.wait(2)
        built.set()
        return service
    monkeypatch.setattr(module, "KnowledgeService", build)
    tool = module.KnowledgeTool()
    async def check():
        task = asyncio.create_task(tool.get_service())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert await asyncio.to_thread(built.wait, 2)
        await tool.aclose()
        service.close.assert_awaited_once()
    asyncio.run(check())


def test_knowledge_shutdown_does_not_publish_closed_pending_service(load_module, monkeypatch):
    import asyncio
    import threading
    from unittest.mock import AsyncMock
    module = _load_tools_module(load_module)
    entered = threading.Event()
    release = threading.Event()
    service = Mock(close=AsyncMock())
    def build():
        entered.set()
        assert release.wait(2)
        return service
    monkeypatch.setattr(module, "KnowledgeService", build)
    tool = module.KnowledgeTool()
    async def check():
        request = asyncio.create_task(tool.get_service())
        closing = None
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            closing = asyncio.create_task(tool.aclose())
            await asyncio.sleep(0)
            assert tool._closed
        finally:
            release.set()
        try:
            with pytest.raises(RuntimeError, match="closed"):
                await request
        finally:
            if closing is not None:
                await closing
        service.close.assert_awaited_once()
    asyncio.run(check())


def test_registry_shutdown_cleans_instances_in_cancelled_parent_scope(load_module):
    import asyncio
    import anyio
    from unittest.mock import AsyncMock
    _, _, _, module = _load_core_modules(load_module)
    closed = []
    async def shutdown():
        await anyio.lowlevel.checkpoint()
        closed.append("closed")
    registry = module.AgentRegistry()
    registry._instances["one"] = Mock(shutdown=AsyncMock(side_effect=shutdown))
    async def check():
        with anyio.CancelScope() as scope:
            scope.cancel()
            await registry.shutdown_all()
        assert closed == ["closed"]
    asyncio.run(check())


@pytest.mark.parametrize("query,expected", [
    ("补贴", False), ("政策", False), ("汽车", False), ("你好", True), ("hi!", True),
])
def test_short_business_queries_are_not_misrouted_as_greetings(load_module, query, expected):
    module, _ = _load_service_module(load_module)
    service = object.__new__(module.AgentService)
    assert service._looks_like_greeting(query) is expected


@pytest.mark.parametrize("router,team,expected", [(True, False, True), (False, True, True), (False, False, False)])
def test_agentchat_streaming_capability_supports_each_backend(load_module, router, team, expected):
    module, _ = _load_service_module(load_module)
    service = object.__new__(module.AgentService)
    service._agentchat_enabled, service._agentchat_team_enabled = router, team
    assert service.agentchat_streaming_enabled is expected


def test_text2sql_tool_uses_the_connection_selected_by_its_request(load_module, monkeypatch):
    import asyncio
    from contextvars import ContextVar
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    module, _ = _load_service_module(load_module)
    service = object.__new__(module.AgentService)
    service._request_state = ContextVar("selected_connection")
    service._resolve_connection_id = Mock(side_effect=AssertionError("selected connection must stay on the request"))
    answer_query = AsyncMock(return_value=SimpleNamespace(answer="selected connection", sources=[]))
    monkeypatch.setattr(module, "answer_text2sql_query", answer_query)

    async def run():
        token = service._request_state.set(module._RequestState(connection_id=7))
        try:
            return await service._tool_agentchat_text2sql("policy count")
        finally:
            service._request_state.reset(token)

    assert asyncio.run(run()) == "selected connection"
    answer_query.assert_awaited_once_with("policy count", connection_id=7)
    service._resolve_connection_id.assert_not_called()


@pytest.mark.parametrize("cancel_caller", [False, True])
def test_session_stop_distinguishes_child_and_caller_cancellation(load_module, cancel_caller):
    import asyncio
    module = load_module("app/agents/framework/common/session_manager.py")
    manager = module.SessionManager()
    async def check():
        manager.start()
        await asyncio.sleep(0)
        stopping = asyncio.create_task(manager.stop())
        try:
            if cancel_caller:
                asyncio.get_running_loop().call_soon(stopping.cancel)
                with pytest.raises(asyncio.CancelledError):
                    await stopping
            else:
                await stopping
                assert manager._cleanup_task is None
        finally:
            await manager.stop()
    asyncio.run(check())
