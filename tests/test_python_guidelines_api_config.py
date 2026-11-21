"""Offline regression coverage for API boundaries and shared configuration."""

from __future__ import annotations

import asyncio
import importlib.util
import io
import logging
import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from jose import jwt


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_module(monkeypatch):
    """Load owned modules without starting the application's external clients."""
    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        monkeypatch.setitem(sys.modules, name, module)
        return module

    for name in ("app", "app.api", "app.api.endpoints", "app.core", "app.domains", "app.models"):
        stub(name)

    def load(path, *, name=None):
        module_name = name or "_api_audit_" + path.replace("/", "_").replace(".", "_")
        spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        return module

    load.stub = stub
    return load


def test_zero_token_lifetime_is_not_replaced_by_default(load_module):
    security = SimpleNamespace(
        jwt_secret_key="test-secret", jwt_algorithm="HS256", jwt_access_token_exp_minutes=60,
        api_default_username="test", api_default_password="password", api_default_fullname="Test",
    )
    load_module.stub("app.config.app_config", settings=SimpleNamespace(security=security))
    load_module("app/core/security.py", name="app.core.security")
    auth = load_module("app/core/auth.py")
    before = datetime.now(timezone.utc).timestamp()
    token = auth.create_access_token({"sub": "test"}, expires_delta=timedelta(0))
    claims = jwt.decode(token, "test-secret", algorithms=["HS256"], options={"verify_exp": False})
    assert before - 1 <= claims["exp"] <= before + 2


def test_graph_missing_file_keeps_404(load_module, monkeypatch, tmp_path):
    graph = load_module("app/api/endpoints/knowledge_graph.py")
    monkeypatch.chdir(tmp_path)
    application = FastAPI()
    application.include_router(graph.router)
    with TestClient(application) as client:
        response = client.get("/graph")
    assert response.status_code == 404
    assert response.json()["detail"] == "知识图谱文件不存在，请先导入数据"


def test_graph_preserves_zero_weight(load_module, tmp_path):
    graph = load_module("app/api/endpoints/knowledge_graph.py")
    graph_file = tmp_path / "graph.graphml"
    graph_file.write_text(
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="weight" attr.name="weight"/><graph edgedefault="directed">'
        '<node id="a"/><node id="b"/><edge source="a" target="b">'
        '<data key="weight">0</data></edge></graph></graphml>', encoding="utf-8",
    )
    nodes, links = graph.parse_graphml(graph_file)
    assert [node.id for node in nodes] == ["a", "b"]
    assert links[0].weight == 0


def test_graph_rejects_supplied_invalid_weight(load_module, tmp_path):
    graph = load_module("app/api/endpoints/knowledge_graph.py")
    graph_file = tmp_path / "invalid.graphml"
    graph_file.write_text(
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="weight" attr.name="weight"/><graph>'
        '<edge source="a" target="b"><data key="weight">invalid</data></edge>'
        '</graph></graphml>', encoding="utf-8",
    )
    with pytest.raises(ValueError):
        graph.parse_graphml(graph_file)


def test_logging_reconfiguration_closes_replaced_handlers(load_module, tmp_path):
    module = load_module("app/core/logging_manager.py")
    manager = module.LoggingManager("python-audit-api-config")
    manager.configure(log_dir=str(tmp_path), enable_console=False)
    previous = manager.logger.handlers[0]
    previous_stream = previous.stream
    try:
        manager.configure(enable_console=False)
        assert previous_stream.closed
        assert manager.logger.handlers == []
    finally:
        previous.close()


def test_logging_reconfiguration_keeps_borrowed_handler_open(load_module):
    module = load_module("app/core/logging_manager.py")
    manager = module.LoggingManager("python-audit-api-config-borrowed")
    handler = Mock(spec=logging.Handler)
    handler.level = logging.NOTSET
    manager.configure(handler=handler)
    manager.configure(enable_console=False)
    handler.close.assert_not_called()
    assert handler not in manager.logger.handlers


@pytest.mark.parametrize("event_kind", ["handler", "construction"])
def test_logging_error_events_preserve_traceback_outside_except(load_module, event_kind):
    module = load_module("app/core/logging_manager.py")
    manager = module.LoggingManager(f"python-audit-error-event-{event_kind}")

    def failed_operation():
        raise ValueError("audit failure")

    try:
        failed_operation()
    except ValueError as exc:
        failure = exc

    with io.StringIO() as output:
        handler = logging.StreamHandler(output)
        manager.configure(handler=handler)
        try:
            if event_kind == "handler":
                manager.log_handler_exception("payload", "agent", failure)
            else:
                manager.log_agent_construction_error("agent", failure)
            formatted = output.getvalue()
            assert "Traceback (most recent call last)" in formatted
            assert "failed_operation" in formatted
            assert "ValueError: audit failure" in formatted
        finally:
            manager.configure(enable_console=False)
            handler.close()


def test_environment_aliases_honor_false_and_zero(load_module, monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "17")
    monkeypatch.setenv("AUTOGEN_ENABLED", "false")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    settings = load_module("app/config/app_config.py")
    assert settings.EmbeddingSettings(_env_file=None).dimension == 17
    assert settings.AutoGenSettings(_env_file=None).enabled is False
    assert settings.ModelSettings().llm_temperature == 0


def test_config_import_does_not_create_runtime_directories(load_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    create_directory = Mock(side_effect=AssertionError("configuration import must stay read only"))
    monkeypatch.setattr(Path, "mkdir", create_directory)
    module = load_module("app/config/app_config.py")
    assert isinstance(module.settings, module.Settings)
    create_directory.assert_not_called()


def test_agent_service_config_environment_and_serialization(load_module, monkeypatch):
    monkeypatch.setenv("LLM_MODEL_NAME", "offline-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    module = load_module("app/config/agent_config.py")
    config = module.AgentServiceConfig(_env_file=None)
    assert config.model.model_name == "offline-model"
    assert config.model.temperature == 0
    assert config.model_dump()["model"]["model_name"] == "offline-model"


def test_agent_config_accepts_disabled_conversation_history(load_module):
    module = load_module("app/config/agent_config.py")
    assert module.ConversationConfig(history_window=0).history_window == 0


@pytest.mark.parametrize("configured_value", ["", "configured-value"])
def test_optional_tool_configuration_has_explicit_unconfigured_values(
    load_module, monkeypatch, tmp_path, configured_value,
):
    for name in (
        "VISION__API_KEY", "VISION__BASE_URL", "WEB_SEARCH__TAVILY_API_KEY",
        "API_KEY", "BASE_URL", "TAVILY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    module = load_module("app/config/agent_config.py")
    assert module.VisionConfig().api_key is None
    assert module.VisionConfig().base_url is None
    assert module.WebSearchConfig().tavily_api_key is None
    environment_file = tmp_path / "tools.env"
    environment_file.write_text(
        f"VISION__API_KEY={configured_value}\n"
        f"VISION__BASE_URL={configured_value}\n"
        f"WEB_SEARCH__TAVILY_API_KEY={configured_value}\n",
        encoding="utf-8",
    )

    config = module.AgentServiceConfig(_env_file=environment_file)

    expected = None if configured_value == "" else configured_value
    assert config.vision.api_key == expected
    assert config.vision.base_url == expected
    assert config.web_search.tavily_api_key == expected


def _load_main(load_module):
    service = SimpleNamespace(initialize=AsyncMock(), aclose=AsyncMock())
    load_module.stub("app.agents.service.agent_service", AgentService=lambda: service)
    load_module.stub("app.core.llms", model_client=SimpleNamespace(close=AsyncMock()))
    from pydantic import BaseModel

    class APIUser(BaseModel):
        username: str

    load_module.stub("app.core.auth", APIUser=APIUser, authenticate_user=Mock(),
                     create_access_token=Mock(), get_current_user_or_dummy=lambda: APIUser(username="test"))
    security = SimpleNamespace(rate_limit_disable=True, rate_limit_redis_url="redis://offline",
                               rate_limit_query_times=1, rate_limit_query_seconds=1,
                               rate_limit_docs_times=1, rate_limit_docs_seconds=1)
    load_module.stub("app.config.app_config", settings=SimpleNamespace(security=security))
    return load_module("app/main.py"), service, security


def test_query_preserves_validated_source_fields(load_module):
    module, service, _ = _load_main(load_module)
    source = SimpleNamespace(model_dump=lambda: {"title": "Policy", "source": "offline", "content": "Full text"})
    service.process_query = AsyncMock(return_value=SimpleNamespace(
        answer="Answer", confidence=0.0, verification_passed=False,
        sources=[source], metadata={},
    ))
    with TestClient(module.create_app()) as client:
        response = client.post("/query", json={"query": "policy"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["content"] == "Full text"


def test_rate_limiter_failure_is_visible_and_closes_client(load_module, monkeypatch):
    module, service, security = _load_main(load_module)
    security.rate_limit_disable = False
    redis = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(module.aioredis, "from_url", AsyncMock(return_value=redis))
    monkeypatch.setattr(module.FastAPILimiter, "init", AsyncMock(side_effect=RuntimeError("Redis unavailable")))
    with pytest.raises(RuntimeError, match="Redis unavailable"):
        with TestClient(module.create_app()):
            pass
    redis.aclose.assert_awaited_once()
    service.aclose.assert_awaited_once()
    module.model_client.close.assert_awaited_once()


def test_domain_invalid_config_preserves_current_domains(load_module, tmp_path):
    load_module.stub("app.domains.prompt_catalog", get_domain_prompt=lambda name: None)
    module = load_module("app/domains/manager.py")
    config = module.DomainConfig()
    previous = config.domains
    file_path = tmp_path / "domains.yaml"
    file_path.write_text("- invalid-domain\n", encoding="utf-8")
    with pytest.raises(ValueError):
        config.load_config(str(file_path))
    assert config.domains is previous


@pytest.mark.parametrize("catalog", ["false", "[]", "domains: []"])
def test_prompt_catalog_rejects_non_mapping_configuration(load_module, monkeypatch, tmp_path, catalog):
    module = load_module("app/domains/prompt_catalog.py")
    path = tmp_path / "catalog.yaml"
    path.write_text(catalog, encoding="utf-8")
    monkeypatch.setattr(module, "CATALOG_PATH", path)

    with pytest.raises(ValueError, match="mapping"):
        module.list_domain_prompts()


def _stub_api_dependencies(load_module):
    class ChatAccess:
        is_staff = True
        namespace = "staff:offline-owner:"

    load_module.stub(
        "app.core.access", ChatAccess=ChatAccess, ChatSessionKey=SimpleNamespace,
        get_chat_access=ChatAccess, require_staff=ChatAccess,
        resolve_chat_session=lambda access, client_id, **kwargs: SimpleNamespace(
            storage_id="offline-session", client_id="offline-session"
        ),
    )
    names = {
        "app.agents.dsl_generator.dsl_extractor": "DSLExtractor",
        "app.agents.dsl_generator.dsl_generator": "DSLGenerator",
        "app.agents.dsl_generator.document_parser": "DocumentParser",
        "app.agents.dsl_generator.rule_engine": "PolicyEngine",
        "app.agents.service.agent_service": "AgentService",
        "app.agents.framework.common.session_manager": "SessionManager",
        "app.agents.service.chat_history_store": "ChatHistoryStore",
    }
    for module_name, class_name in names.items():
        load_module.stub(module_name, **{class_name: type(class_name, (), {})})
    load_module.stub("app.knowledge.service", KnowledgeService=type("KnowledgeService", (), {}))
    load_module.stub("app.knowledge.document_processor", EnhancedDocumentProcessor=type("EnhancedDocumentProcessor", (), {}))
    load_module.stub("app.core.llms", model_client=object())


def test_failed_service_initialization_is_not_cached(load_module, monkeypatch):
    _stub_api_dependencies(load_module)
    dependencies = load_module("app/api/deps.py")
    failed = SimpleNamespace(initialize=AsyncMock(side_effect=RuntimeError("offline failure")), aclose=AsyncMock())
    ready = SimpleNamespace(initialize=AsyncMock())
    constructor = Mock(side_effect=[failed, ready])
    monkeypatch.setattr(dependencies, "AgentService", constructor)

    async def check():
        with pytest.raises(RuntimeError, match="offline failure"):
            await dependencies.get_agent_service()
        assert await dependencies.get_agent_service() is ready
        assert await dependencies.get_agent_service() is ready

    asyncio.run(check())
    assert constructor.call_count == 2
    failed.aclose.assert_awaited_once()


def test_concurrent_service_initialization_is_shared(load_module, monkeypatch):
    _stub_api_dependencies(load_module)
    dependencies = load_module("app/api/deps.py")

    class Service:
        def __init__(self):
            self.ready = False

        async def initialize(self):
            await asyncio.sleep(0)
            self.ready = True

    constructor = Mock(side_effect=Service)
    monkeypatch.setattr(dependencies, "AgentService", constructor)

    async def check():
        async def get_ready_service():
            service = await dependencies.get_agent_service()
            assert service.ready
            return service

        results = await asyncio.gather(*(get_ready_service() for _ in range(3)))
        assert all(service is results[0] for service in results)

    asyncio.run(check())
    assert constructor.call_count == 1


@pytest.mark.parametrize("factory_name, constructor_name", [
    ("get_dsl_generator", "DSLGenerator"),
    ("get_dsl_extractor", "DSLExtractor"),
    ("get_document_parser", "DocumentParser"),
    ("get_policy_engine", "PolicyEngine"),
    ("get_knowledge_service", "KnowledgeService"),
    ("get_enhanced_doc_processor", "EnhancedDocumentProcessor"),
    ("get_session_manager", "SessionManager"),
])
def test_sync_dependencies_share_concurrent_first_construction(
    load_module, monkeypatch, factory_name, constructor_name,
):
    _stub_api_dependencies(load_module)
    dependencies = load_module("app/api/deps.py")
    constructing = threading.Event()
    duplicate = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    count_lock = threading.Lock()
    instances = []

    def construct(*args, **kwargs):
        instance = object()
        with count_lock:
            instances.append(instance)
            (constructing if len(instances) == 1 else duplicate).set()
        assert release.wait(3), "test did not release dependency construction"
        return instance

    monkeypatch.setattr(dependencies, constructor_name, construct)
    factory = getattr(dependencies, factory_name)

    def second_request():
        second_started.set()
        return factory()

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(factory)
        try:
            assert constructing.wait(2)
            second = workers.submit(second_request)
            assert second_started.wait(2)
            duplicate.wait(0.2)
        finally:
            release.set()
        first_result, second_result = first.result(), second.result()

    assert len(instances) == 1
    assert first_result is second_result


def test_lifespan_stops_session_manager_after_error(load_module):
    for name in ("agent", "dsl", "knowledge", "uploads", "knowledge_graph", "db_connections"):
        from fastapi import APIRouter
        load_module.stub("app.api.endpoints." + name, router=APIRouter())
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    manager = SimpleNamespace(start=Mock(), stop=AsyncMock())
    close_dependencies = AsyncMock()
    load_module.stub("app.api.deps", get_session_manager=lambda: manager,
                     close_dependencies=close_dependencies)
    module = load_module("api_server.py")

    async def check():
        with pytest.raises(RuntimeError, match="request failure"):
            async with module.lifespan(module.app):
                raise RuntimeError("request failure")

    asyncio.run(check())
    manager.stop.assert_awaited_once()
    close_dependencies.assert_awaited_once()


def _load_knowledge_api(load_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_enhanced_doc_processor=lambda: None,
                     get_knowledge_service=lambda: None)
    return load_module("app/api/endpoints/knowledge.py")


def test_upload_preserves_document_validation_error(load_module, monkeypatch, tmp_path):
    module = _load_knowledge_api(load_module, monkeypatch, tmp_path)
    processor = SimpleNamespace(extract_with_metadata=AsyncMock(return_value={
        "success": False, "error": "unsupported document",
    }))
    file = UploadFile(file=io.BytesIO(b"invalid"), filename="policy.pdf")

    async def check():
        with pytest.raises(HTTPException) as error:
            await module.upload_document(file=file, processor=processor)
        assert error.value.status_code == 400
        assert error.value.detail == "unsupported document"

    asyncio.run(check())


def test_upload_uses_contained_filename(load_module, monkeypatch, tmp_path):
    module = _load_knowledge_api(load_module, monkeypatch, tmp_path)
    processor = SimpleNamespace(extract_with_metadata=AsyncMock(return_value={
        "success": True, "text": "policy text", "file_name": "policy.txt",
    }))
    file = UploadFile(file=io.BytesIO(b"policy"), filename="../outside.txt")
    result = asyncio.run(module.upload_document(file=file, processor=processor))
    assert result.doc_id == "outside.txt"
    assert (tmp_path / "uploads/outside.txt").read_bytes() == b"policy"
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize("fail", [False, True])
def test_upload_file_lifecycle_runs_off_loop(load_module, monkeypatch, tmp_path, fail):
    module = _load_knowledge_api(load_module, monkeypatch, tmp_path)
    processor = SimpleNamespace(extract_with_metadata=AsyncMock(return_value={
        "success": True, "text": "policy text", "file_name": "policy.txt",
    }))
    loop_thread = threading.get_ident()
    opened = []
    real_open = open

    def record_open(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        opened.append((threading.get_ident(), handle))
        return handle

    class UploadSource(io.BytesIO):
        def read(self, *args):
            if fail:
                raise OSError("upload read failed")
            return super().read(*args)

    monkeypatch.setattr(module, "open", record_open, raising=False)
    with UploadSource(b"policy") as source:
        file = UploadFile(file=source, filename="policy.txt")
        if fail:
            with pytest.raises(HTTPException) as error:
                asyncio.run(module.upload_document(file=file, processor=processor))
            assert error.value.status_code == 500
            assert isinstance(error.value.__cause__, OSError)
        else:
            asyncio.run(module.upload_document(file=file, processor=processor))
    assert len(opened) == 1
    worker_thread, handle = opened[0]
    assert worker_thread != loop_thread
    assert handle.closed


def test_search_does_not_hide_broken_document_contract(load_module, monkeypatch, tmp_path, caplog):
    module = _load_knowledge_api(load_module, monkeypatch, tmp_path)
    service = SimpleNamespace(search=AsyncMock(return_value=([SimpleNamespace(id="1")], [0.0])))
    request = module.SearchRequest(query="policy")

    async def check():
        with pytest.raises(HTTPException) as error:
            await module.search_knowledge(request=request, knowledge_service=service)
        assert error.value.status_code == 500
        assert isinstance(error.value.__cause__, AttributeError)

    asyncio.run(check())
    record = next(record for record in caplog.records if record.exc_info is not None)
    assert record.exc_info[0] is AttributeError


def test_search_rejects_misaligned_documents_and_scores(load_module, monkeypatch, tmp_path):
    module = _load_knowledge_api(load_module, monkeypatch, tmp_path)
    document = SimpleNamespace(id="1", title="Policy", content="Text", source="offline")
    service = SimpleNamespace(search=AsyncMock(return_value=([document], [])))

    async def check():
        with pytest.raises(HTTPException) as error:
            await module.search_knowledge(request=module.SearchRequest(query="policy"), knowledge_service=service)
        assert error.value.status_code == 500
        assert isinstance(error.value.__cause__, ValueError)

    asyncio.run(check())


@pytest.mark.parametrize("route", ["chat", "stream"])
@pytest.mark.parametrize("location", ["outside", "missing"])
def test_chat_rejects_unowned_attachment_paths_before_session_or_stream(load_module, monkeypatch, tmp_path, route, location):
    monkeypatch.chdir(tmp_path)
    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_session_manager=lambda: None, get_agent_service=lambda: None)
    uploads = load_module("app/api/endpoints/uploads.py", name="app.api.endpoints.uploads")
    uploads.ATTACHMENT_DIR.mkdir(parents=True)
    outside = tmp_path / "private.png"
    outside.write_bytes(b"private")
    path = outside if location == "outside" else uploads.ATTACHMENT_DIR / "missing.png"
    module = load_module("app/api/endpoints/agent.py")
    threads = []
    original_validate = module._validate_uploaded_attachment_paths

    def validate(attachments, access):
        threads.append(threading.get_ident())
        return original_validate(attachments, access)

    monkeypatch.setattr(module, "_validate_uploaded_attachment_paths", validate)
    manager = SimpleNamespace(get_or_create_session=Mock(), add_message=Mock())
    service = SimpleNamespace(process_query=AsyncMock(), process_query_stream=Mock())
    request_type = module.ChatRequest if route == "chat" else module.ChatStreamRequest
    request = request_type(message="policy", attachments=[module.Attachment(path=str(path))])
    handler = module.agent_chat if route == "chat" else module.agent_chat_stream

    async def invoke():
        access = module.ChatAccess()
        prepare = module._prepare_chat_request if route == "chat" else module._prepare_stream_request
        key = await prepare(request, access)
        return await handler(request, access, key, manager, service)

    with pytest.raises(HTTPException) as error:
        asyncio.run(invoke())

    assert error.value.status_code == 400
    assert threads and threads[0] != threading.get_ident()
    manager.get_or_create_session.assert_not_called()
    manager.add_message.assert_not_called()
    service.process_query.assert_not_awaited()
    service.process_query_stream.assert_not_called()


def test_attachment_validation_accepts_real_uploads_and_remote_urls(load_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_session_manager=lambda: None, get_agent_service=lambda: None)
    uploads = load_module("app/api/endpoints/uploads.py", name="app.api.endpoints.uploads")
    directory = uploads.attachment_directory(uploads.ChatAccess())
    directory.mkdir(parents=True)
    path = directory / "uploaded.png"
    path.write_bytes(b"image")
    module = load_module("app/api/endpoints/agent.py")
    assert module._validate_uploaded_attachment_paths([
        module.Attachment(path=str(path)), module.Attachment(url="https://example.test/image.png"),
    ], module.ChatAccess()) is None


def test_attachment_download_rejects_parent_paths(load_module, monkeypatch, tmp_path):
    _load_knowledge_api(load_module, monkeypatch, tmp_path)
    _stub_api_dependencies(load_module)
    module = load_module("app/api/endpoints/uploads.py")
    (tmp_path / "outside.txt").write_text("private", encoding="utf-8")
    application = FastAPI()
    application.include_router(module.router, prefix="/attachments")
    with TestClient(application) as client:
        response = client.get("/attachments/%2e%2e%5c%2e%2e%5coutside.txt")
    assert response.status_code == 404


@pytest.mark.parametrize("route", ["chat", "stream", "agentchat_stream"])
def test_chat_history_operations_run_off_event_loop(load_module, monkeypatch, route):
    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_session_manager=lambda: None, get_agent_service=lambda: None)
    module = load_module("app/api/endpoints/agent.py")
    loop_thread = threading.get_ident()
    threads = []
    session = SimpleNamespace(session_id="offline-session", message_count=0)

    def get_session(*args, **kwargs):
        threads.append(threading.get_ident())
        return session

    def add_message(*args, **kwargs):
        threads.append(threading.get_ident())
        session.message_count += 1

    manager = SimpleNamespace(get_or_create_session=get_session, add_message=add_message)
    answer = SimpleNamespace(answer="Answer", confidence=0.0,
                             metadata={"session_id": "offline-session", "route": "offline"})

    async def stream(*args, **kwargs):
        yield {"type": "final", "answer": answer}

    service = SimpleNamespace(process_query=AsyncMock(return_value=answer),
                              process_query_stream=stream, agentchat_streaming_enabled=True)
    monkeypatch.setenv("AGENTCHAT_STREAM_ENABLED", "true" if route == "agentchat_stream" else "false")

    async def check():
        key = module.ChatSessionKey(storage_id="offline-session", client_id="offline-session")
        if route == "chat":
            response = await module.agent_chat(module.ChatRequest(message="Policy?"), module.ChatAccess(), key, manager, service)
            assert response.message == "Answer"
        else:
            response = await module.agent_chat_stream(module.ChatStreamRequest(message="Policy?"), module.ChatAccess(), key, manager, service)
            events = [event async for event in response.body_iterator]
            assert events[-1]["event"] == "done"

    asyncio.run(check())
    assert session.message_count == 2
    assert len(threads) == 3
    assert all(thread != loop_thread for thread in threads)


@pytest.mark.parametrize("cancelled", [False, True])
def test_sse_early_close_finishes_owned_stream_in_consumer_context(
    load_module, monkeypatch, cancelled,
):
    import anyio

    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_session_manager=lambda: None, get_agent_service=lambda: None)
    module = load_module("app/api/endpoints/agent.py")
    monkeypatch.setenv("AGENTCHAT_STREAM_ENABLED", "true")
    context = ContextVar("sse_audit_context", default="outside")
    cleanup_tasks = []
    manager = SimpleNamespace(
        get_or_create_session=Mock(return_value=SimpleNamespace(session_id="offline", message_count=0)),
        add_message=Mock(),
    )

    async def stream():
        token = context.set("inside")
        try:
            yield {"type": "chunk", "content": "partial answer"}
        finally:
            await anyio.lowlevel.checkpoint()
            context.reset(token)
            cleanup_tasks.append(asyncio.current_task())

    async def check():
        inner = stream()
        service = SimpleNamespace(agentchat_streaming_enabled=True, process_query_stream=lambda *a, **kw: inner)
        key = module.ChatSessionKey(storage_id="offline-session", client_id="offline-session")
        response = await module.agent_chat_stream(module.ChatStreamRequest(message="Policy?"), module.ChatAccess(), key, manager, service)
        try:
            assert (await anext(response.body_iterator))["event"] == "session"
            assert (await anext(response.body_iterator))["event"] == "message"
            assert context.get() == "inside"
            with anyio.CancelScope() as scope:
                if cancelled:
                    scope.cancel()
                await response.body_iterator.aclose()
            assert cleanup_tasks == [asyncio.current_task()]
            assert context.get() == "outside"
            assert manager.add_message.call_count == 1
        finally:
            await inner.aclose()

    anyio.run(check)


@pytest.mark.parametrize("close_failure", [False, True])
def test_dependency_shutdown_closes_all_owned_resources(load_module, close_failure):
    _stub_api_dependencies(load_module)
    dependencies = load_module("app/api/deps.py")
    service = SimpleNamespace(aclose=AsyncMock(side_effect=RuntimeError("service close failed") if close_failure else None))
    knowledge = SimpleNamespace(close=AsyncMock())
    model = SimpleNamespace(close=AsyncMock())
    dependencies._agent_service = service
    dependencies._knowledge_service = knowledge
    dependencies.model_client = model

    async def check():
        if close_failure:
            with pytest.raises(RuntimeError, match="service close failed"):
                await dependencies.close_dependencies()
        else:
            await dependencies.close_dependencies()

    asyncio.run(check())
    service.aclose.assert_awaited_once()
    knowledge.close.assert_awaited_once()
    model.close.assert_awaited_once()
    assert dependencies._agent_service is None
    assert dependencies._knowledge_service is None


def test_lightweight_app_closes_service_and_model_on_shutdown(load_module):
    module, service, _ = _load_main(load_module)
    with TestClient(module.create_app()):
        pass
    service.aclose.assert_awaited_once()
    module.model_client.close.assert_awaited_once()


def test_owned_resource_close_survives_parent_cancellation_and_has_budget(load_module):
    import anyio
    lifecycle = load_module("app/utils/lifecycle.py")
    closed = []
    async def close():
        await anyio.lowlevel.checkpoint()
        closed.append(True)
        return "closed"
    async def hanging_close():
        await anyio.sleep_forever()
    async def check():
        with anyio.CancelScope() as scope:
            scope.cancel()
            assert await lifecycle.close_with_timeout(close) == "closed"
        assert closed == [True]
        with pytest.raises(TimeoutError):
            await lifecycle.close_with_timeout(hanging_close, cleanup_timeout=0.01)
    anyio.run(check)


@pytest.mark.parametrize("max_tokens,timeout", [(None, None), (123, 3.5)])
def test_shared_client_forwards_only_configured_optional_model_limits(load_module, max_tokens, timeout):
    transport = Mock(return_value=object())
    constructor = Mock(return_value=object())
    load_module.stub("httpx", AsyncClient=transport)
    load_module.stub("autogen_ext.models.openai", OpenAIChatCompletionClient=constructor)
    load_module.stub("app.config.app_config", settings=SimpleNamespace(model=SimpleNamespace(
        llm_model_name="offline-model", llm_api_key="offline-key", llm_temperature=0,
        llm_base_url="https://model.invalid/v1", llm_max_tokens=max_tokens, llm_timeout=timeout,
    )))
    module = load_module("app/core/llms.py")
    assert module.model_client is constructor.return_value
    actual = constructor.call_args.kwargs
    for name, value in (("max_tokens", max_tokens), ("timeout", timeout)):
        if value is None:
            assert name not in actual
        else:
            assert actual[name] == value
    assert actual["temperature"] == 0
    transport.assert_called_once_with(trust_env=False)


@pytest.mark.parametrize("api_key", [None, ""])
def test_shared_client_rejects_missing_credentials_before_opening_transport(load_module, api_key):
    transport = Mock(side_effect=AssertionError("missing credentials must not open a transport"))
    constructor = Mock()
    load_module.stub("httpx", AsyncClient=transport)
    load_module.stub("autogen_ext.models.openai", OpenAIChatCompletionClient=constructor)
    load_module.stub("app.config.app_config", settings=SimpleNamespace(model=SimpleNamespace(llm_api_key=api_key)))
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        load_module("app/core/llms.py")
    transport.assert_not_called()
    constructor.assert_not_called()


@pytest.mark.parametrize("service_import_fails", [False, True])
def test_cli_applies_yaml_model_options_before_client_import_and_registers_cleanup(load_module, monkeypatch, tmp_path, service_import_fails):
    import argparse
    import builtins
    from contextlib import AsyncExitStack
    from test_python_guidelines_tooling import load_definitions

    monkeypatch.chdir(tmp_path)
    for name in ("LLM_MODEL_NAME", "LLM_API_KEY", "LLM_BASE_URL", "LLM_TEMPERATURE", "LLM_MAX_TOKENS", "LLM_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    config_file = tmp_path / "model.yaml"
    config_file.write_text(
        "model:\n  model_name: yaml-model\n  api_key: yaml-key\n  base_url: https://yaml.invalid/v1\n"
        "  temperature: 0\n  max_tokens: 123\n  timeout: 3\n", encoding="utf-8",
    )
    load_module("app/config/agent_config.py", name="app.config.agent_config")
    expected = {"llm_model_name": "yaml-model", "llm_api_key": "yaml-key", "llm_base_url": "https://yaml.invalid/v1",
                "llm_temperature": 0, "llm_max_tokens": 123, "llm_timeout": 3}
    copied_model = SimpleNamespace(**expected)
    copy_model = Mock(return_value=copied_model)
    settings = SimpleNamespace(model=SimpleNamespace(model_copy=copy_model))
    load_module.stub("app.config.app_config", settings=settings)
    events = []
    client = SimpleNamespace(close=AsyncMock(side_effect=lambda: events.append("client-close")))
    service = SimpleNamespace(aclose=AsyncMock(side_effect=lambda: events.append("service-close")), initialize=AsyncMock())
    construct_client, construct_service = Mock(return_value=client), Mock(return_value=service)
    load_module.stub("httpx", AsyncClient=Mock(return_value=object()))
    load_module.stub("autogen_ext.models.openai", OpenAIChatCompletionClient=construct_client)
    load_module.stub("app.agents.service.agent_service", AgentService=construct_service)
    load_module("app/utils/lifecycle.py", name="app.utils.lifecycle")
    metrics = Mock()
    namespace = load_definitions(
        "scripts/agent_cli.py", {"main"}, argparse=argparse, asyncio=asyncio, Path=Path, sys=sys,
        AsyncExitStack=AsyncExitStack, metrics_mode=metrics,
        logging=SimpleNamespace(DEBUG=10, INFO=20, basicConfig=Mock(), getLogger=Mock(return_value=Mock())),
    )
    original_import = builtins.__import__

    def configured_import(name, *args, **kwargs):
        if name == "app.core.llms":
            events.append("client-import")
            assert settings.model is copied_model
            copy_model.assert_called_once_with(update=expected)
            return load_module("app/core/llms.py", name="app.core.llms")
        if name == "app.agents.service.agent_service":
            events.append("service-import")
            if service_import_fails:
                raise RuntimeError("service import failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", configured_import)
    monkeypatch.setattr(sys, "argv", ["agent_cli", "--config", str(config_file), "--metrics"])
    if service_import_fails:
        with pytest.raises(SystemExit) as error:
            asyncio.run(namespace["main"]())
        assert error.value.code == 1
        construct_service.assert_not_called()
        assert events == ["client-import", "service-import", "client-close"]
    else:
        asyncio.run(namespace["main"]())
        metrics.assert_called_once_with(service)
        service.initialize.assert_not_awaited()
        assert events == ["client-import", "service-import", "service-close", "client-close"]
    actual = construct_client.call_args.kwargs
    assert {key: actual[key] for key in ("model", "api_key", "base_url", "temperature", "max_tokens", "timeout")} == {
        "model": "yaml-model", "api_key": "yaml-key", "base_url": "https://yaml.invalid/v1",
        "temperature": 0, "max_tokens": 123, "timeout": 3,
    }


def test_real_autogen_transport_is_owned_without_mutating_proxy_environment(load_module, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    load_module.stub("app.config.app_config", settings=SimpleNamespace(model=SimpleNamespace(
        llm_model_name="offline-model", llm_api_key="offline-key", llm_temperature=0,
        llm_base_url="http://model.invalid/v1",
        llm_max_tokens=None, llm_timeout=None,
    )))
    module = load_module("app/core/llms.py")
    http = module.model_client._client._client
    assert http.trust_env is False and not http.is_closed
    assert module.model_client._client.base_url.host == "model.invalid"
    import os
    assert os.environ["HTTP_PROXY"] == "http://proxy.invalid:8080"
    asyncio.run(module.model_client.close())
    assert http.is_closed


def test_lightweight_health_and_load_docs_have_response_contracts(load_module):
    module, service, _ = _load_main(load_module)
    service.ingest_paths = AsyncMock(return_value={"loaded_docs": 0, "kb_indexed": 0, "rag_indexed": 0, "internal": "secret"})
    with TestClient(module.create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post("/load-docs", json={"paths": []})
        schema = client.get("/openapi.json").json()
    assert response.json() == {"loaded_docs": 0, "kb_indexed": 0, "rag_indexed": 0}
    assert schema["paths"]["/load-docs"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("LoadDocsResponse")


@pytest.mark.parametrize("endpoint, operation, payload", [
    ("/query", "process_query", {"query": "policy"}),
    ("/load-docs", "ingest_paths", {"paths": []}),
])
def test_lightweight_error_boundary_logs_original_traceback(
    load_module, caplog, endpoint, operation, payload,
):
    module, service, _ = _load_main(load_module)
    setattr(service, operation, AsyncMock(side_effect=RuntimeError("offline operation failed")))
    with TestClient(module.create_app()) as client:
        response = client.post(endpoint, json=payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "offline operation failed"
    records = [record for record in caplog.records if record.name == module.__name__]
    assert len(records) == 1
    assert records[0].exc_info[0] is RuntimeError
    assert records[0].exc_info[2] is not None


@pytest.mark.parametrize("route", ["chat", "stream"])
def test_chat_required_service_fields_are_not_silently_replaced(load_module, monkeypatch, caplog, route):
    _stub_api_dependencies(load_module)
    load_module("app/models/policy.py", name="app.models.policy")
    load_module("app/api/schemas.py", name="app.api.schemas")
    load_module.stub("app.api.deps", get_session_manager=lambda: None, get_agent_service=lambda: None)
    module = load_module("app/api/endpoints/agent.py")
    manager = SimpleNamespace(
        get_or_create_session=Mock(return_value=SimpleNamespace(session_id="offline", message_count=0)),
        add_message=Mock(),
    )

    async def invalid_stream(*args, **kwargs):
        yield {"content": "missing required event type"}

    service = SimpleNamespace(
        process_query=AsyncMock(return_value=SimpleNamespace(answer="Answer", metadata={})),
        process_query_stream=invalid_stream, agentchat_streaming_enabled=True,
    )
    monkeypatch.setenv("AGENTCHAT_STREAM_ENABLED", "true")

    async def check():
        key = module.ChatSessionKey(storage_id="offline-session", client_id="offline-session")
        if route == "chat":
            with pytest.raises(HTTPException) as error:
                await module.agent_chat(module.ChatRequest(message="Policy?"), module.ChatAccess(), key, manager, service)
            assert isinstance(error.value.__cause__, AttributeError)
        else:
            response = await module.agent_chat_stream(module.ChatStreamRequest(message="Policy?"), module.ChatAccess(), key, manager, service)
            events = [event async for event in response.body_iterator]
            assert events[-1]["event"] == "error"
            assert "咨询服务暂时不可用" in events[-1]["data"]
            assert "type" not in events[-1]["data"]
            assert any(record.exc_info and record.exc_info[0] is KeyError for record in caplog.records)

    asyncio.run(check())
