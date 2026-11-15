"""Offline regression coverage for repository maintenance scripts and examples."""

import ast
import asyncio
import anyio
import json
import subprocess
import sys
import pytest
from types import ModuleType, SimpleNamespace
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_builder_requires_the_query_promised_by_its_workflow():
    from examples.ag_builder import QueryAnalyzer

    with pytest.raises(KeyError, match='query'):
        asyncio.run(QueryAnalyzer().handle({}))


def test_enterprise_roles_use_current_sdk_and_borrow_model_client():
    from autogen_core import CancellationToken
    from autogen_agentchat.messages import TextMessage
    from autogen_ext.models.replay import ReplayChatCompletionClient
    from examples.enterprise_agents import EnterpriseAutoGenConfig

    client = ReplayChatCompletionClient(['analysis'] * 6)
    config = EnterpriseAutoGenConfig(client)
    agents = config.create_enterprise_agents()
    assert set(agents) == {
        'enterprise_data_collector', 'enterprise_financial_analyst',
        'enterprise_risk_analyst', 'enterprise_quantitative_analyst',
        'enterprise_compliance_officer', 'enterprise_portfolio_manager',
    }
    prompts = config.get_agent_system_messages()
    assert all(len(prompts[name]) > 100 for name in agents)
    assert all(config.validate_agent_configuration().values())

    async def exchange():
        try:
            for agent in agents.values():
                response = await agent.on_messages([TextMessage(content='analyze', source='user')], CancellationToken())
                assert response.chat_message.to_text() == 'analysis'
        finally:
            await client.close()

    asyncio.run(exchange())


def load_definitions(path, names, **namespace):
    """Exercise standalone reference methods without optional R2R/LLM services."""
    namespace.setdefault("anyio", anyio)
    source = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    model_names = {
        node.name for node in source.body if isinstance(node, ast.ClassDef)
        and node.name not in namespace
        and any(isinstance(base, ast.Name) and base.id == "BaseModel"
                or isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name)
                and base.value.id == "RootModel" for base in node.bases)
    }
    imports = [node for node in source.body if isinstance(node, ast.ImportFrom)
               and node.module in {"pydantic", "typing"}]
    definitions = [node for node in source.body
                   if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name in set(names) | model_names]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                              *imports, *definitions], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), path, "exec"), namespace)
    for name in model_names:
        namespace[name].model_rebuild(_types_namespace=namespace)
    return namespace


def test_policy_seed_exports_all_categories_and_preserves_quotes(tmp_path):
    namespace = runpy.run_path(str(ROOT / "resources/database/seed_data/policy_qa_seed.py"))
    output = tmp_path / "seed.json"

    assert namespace["export_qa_to_json"](output) == output

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["metadata"]["total_qa_pairs"] == 21
    assert len(data["metadata"]["categories"]) == 5
    assert len(data["qa_pairs"]) == 21
    assert '"新能源"' in data["qa_pairs"][3]["answer"]
    assert '"泉城购"' in data["qa_pairs"][13]["question"]
    for pair in data["qa_pairs"]:
        assert pair["question"]
        assert pair["answer"]
        assert pair["difficulty_level"] in {1, 2, 3}
        assert pair["verified"] is True


def test_simple_seed_import_has_no_file_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    namespace = runpy.run_path(str(ROOT / "resources/database/seed_data/generate_qa_data.py"))

    assert len(namespace["qa_data"]["qa_pairs"]) == 10
    assert list(tmp_path.iterdir()) == []


def test_simple_seed_main_still_exports_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    runpy.run_path(str(ROOT / "resources/database/seed_data/generate_qa_data.py"), run_name="__main__")

    data = json.loads((tmp_path / "policy_qa_初始数据.json").read_text(encoding="utf-8"))
    assert len(data["qa_pairs"]) == 10


def test_importer_uses_explicit_root_and_propagates_process_failure(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(ROOT / "tests/data_import.py"))
    importer = namespace["DataImporter"](project_root=tmp_path)
    assert importer.data_dir == tmp_path / "resources/data"

    async def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="database unavailable")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    import pytest

    with pytest.raises(subprocess.CalledProcessError):
        asyncio.run(importer._run_command(["docker", "version"]))


def test_importer_removes_temporary_script_when_process_fails(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(ROOT / "tests/data_import.py"))
    importer = namespace["DataImporter"](project_root=tmp_path)
    observed = []

    async def fail(command, **kwargs):
        script = Path(command[-1])
        observed.append(script)
        assert await asyncio.to_thread(script.read_text, encoding="utf-8") == "print('中文')"
        raise RuntimeError("failed")

    monkeypatch.setattr(importer, "_run_command", fail)
    import pytest

    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(importer._run_python_script("print('中文')"))
    assert not observed[0].exists()


def test_importer_cancellation_reaps_process_before_removing_script(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__('tempfile'), 'tempdir', str(tmp_path))
    ns = runpy.run_path(str(ROOT / 'tests/data_import.py'))
    reaped = []

    async def check():
        with anyio.CancelScope() as scope:
            class Process:
                returncode = None

                def kill(self):
                    self.returncode = -9

                async def communicate(self, input=None):
                    if self.returncode is None:
                        scope.cancel()
                        await anyio.lowlevel.checkpoint()
                    await anyio.lowlevel.checkpoint()
                    reaped.append(True)
                    assert list(tmp_path.glob('glyph-import-*/import_data.py'))
                    return b'', b''

            async def create(*args, **kwargs):
                return Process()

            monkeypatch.setattr(asyncio, 'create_subprocess_exec', create)
            await ns['DataImporter'](tmp_path)._run_python_script('pass')
        assert scope.cancelled_caught
        assert reaped == [True] and list(tmp_path.iterdir()) == []

    anyio.run(check)


def test_mysql_failure_does_not_include_credentials_in_arguments_or_exception(tmp_path, monkeypatch):
    secret = "offline-test-secret"
    monkeypatch.setenv("MYSQL_ROOT_PASSWORD", secret)
    namespace = runpy.run_path(str(ROOT / "tests/data_import.py"))
    importer = namespace["DataImporter"](project_root=tmp_path)

    async def fail(*command, **kwargs):
        assert secret not in " ".join(command)
        assert kwargs["env"]["MYSQL_PWD"] == secret
        assert command[command.index("-e") + 1] == "MYSQL_PWD"
        raise subprocess.CalledProcessError(1, command, stderr="not available")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    with pytest.raises(subprocess.CalledProcessError) as failure:
        asyncio.run(importer.init_mysql())
    assert secret not in str(failure.value)


def test_empty_cli_batch_writes_empty_result_without_querying(tmp_path, capsys):
    namespace = load_definitions("scripts/unified_cli.py", {"batch_mode"}, asyncio=asyncio, Path=Path, json=json, logging=__import__("logging"))
    query_file = tmp_path / "queries.txt"
    query_file.write_text("\n  \n", encoding="utf-8")

    asyncio.run(namespace["batch_mode"](object(), str(query_file)))

    assert json.loads(query_file.with_suffix(".json").read_text(encoding="utf-8"))["results"] == []
    assert "平均置信度" not in capsys.readouterr().out


def test_cli_batch_failure_remains_visible(tmp_path):
    namespace = load_definitions("scripts/unified_cli.py", {"batch_mode"}, asyncio=asyncio, Path=Path, json=json, logging=__import__("logging"))
    import pytest

    with pytest.raises(FileNotFoundError):
        asyncio.run(namespace["batch_mode"](object(), str(tmp_path / "missing.txt")))


def test_autogen_examples_do_not_start_work_on_import(monkeypatch):
    fake_agent_module = ModuleType("autogen_agentchat.agents")
    fake_agent_module.__dict__["AssistantAgent"] = object
    fake_tools_module = ModuleType("autogen_agentchat.tools")
    fake_tools_module.__dict__["AgentTool"] = object
    fake_ui_module = ModuleType("autogen_agentchat.ui")
    fake_ui_module.__dict__["Console"] = object
    fake_client_module = ModuleType("autogen_ext.models.openai")
    fake_client_module.__dict__["OpenAIChatCompletionClient"] = object
    fake_llms = ModuleType("app.core.llms")
    fake_llms.__dict__["model_client"] = object()
    for module in [fake_agent_module, fake_tools_module, fake_ui_module, fake_client_module, fake_llms]:
        monkeypatch.setitem(sys.modules, module.__name__, module)

    calls = []

    def record_run(coroutine):
        calls.append(coroutine)
        coroutine.close()

    monkeypatch.setattr(asyncio, "run", record_run)
    for name in ("autogen_demo1.py", "autogen_demo2.py"):
        runpy.run_path(str(ROOT / "examples" / name))
    assert calls == []


def test_streaming_reference_uses_final_citations_on_iteration_limit():
    class Agent:
        pass

    class Conversation:
        async def add_message(self, message):
            pass

    class Formatter:
        @staticmethod
        async def yield_message_event(message):
            yield ("message", message)

        @staticmethod
        async def yield_final_answer_event(payload):
            yield ("final", payload)

        @staticmethod
        async def yield_error_event(error):
            yield ("error", error)

        @staticmethod
        def yield_done_event():
            return ("done", None)

    class Tracker:
        def get_all_spans(self):
            return {}

    namespace = load_definitions("examples/base.py", {"R2RStreamingAgent"}, R2RAgent=Agent, re=__import__("re"), CitationTracker=Tracker, Message=SimpleNamespace, SSEFormatter=Formatter, logger=__import__("logging").getLogger(__name__))
    instance = object.__new__(namespace["R2RStreamingAgent"])
    instance._reset = lambda: setattr(instance, "_completed", False)
    instance.config = SimpleNamespace(max_iterations=0)
    instance.conversation = Conversation()

    async def setup(instruction):
        pass

    async def summarize(iterations):
        return "limit reached"

    instance._setup = setup
    instance._generate_llm_summary = summarize

    async def collect():
        return [event async for event in instance.arun()]

    events = asyncio.run(collect())
    assert ("final", {"id": "msg_final", "object": "agent.final_answer", "generated_answer": "limit reached", "citations": []}) in events
    assert not any(event[0] == "error" for event in events)


def test_citation_reference_calls_model_serialization():
    namespace = load_definitions("examples/base.py", {"R2RStreamingAgent"}, R2RAgent=object, re=__import__("re"), dump_obj=lambda value: value)
    instance = object.__new__(namespace["R2RStreamingAgent"])

    class Model:
        def dict(self):
            return {"title": "policy"}

    assert instance._create_citation_payload("abc1234", Model())["payload"] == {"title": "policy"}


@pytest.mark.parametrize('class_name', ['R2RStreamingAgent', 'R2RXMLStreamingAgent'])
def test_reference_early_stream_exit_closes_provider_generator(class_name):
    closed = []

    class Conversation:
        async def get_messages(self):
            return [{}]

    class Formatter:
        @staticmethod
        async def yield_message_event(message):
            yield message

    async def provider_stream(*args):
        try:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='answer text', tool_calls=[]), finish_reason=None)])
            await asyncio.Future()
        finally:
            closed.append(True)

    ns = load_definitions('examples/base.py', {'R2RStreamingAgent', 'R2RXMLStreamingAgent'},
                          R2RAgent=object, re=__import__('re'), CitationTracker=object,
                          SSEFormatter=Formatter, logger=__import__('logging').getLogger(__name__),
                          find_new_citation_spans=lambda *args: {})
    agent = object.__new__(ns[class_name])
    agent._reset = lambda: setattr(agent, '_completed', False)
    agent.config = SimpleNamespace(max_iterations=1)
    agent.conversation = Conversation()
    agent.get_generation_config = lambda *args, **kwargs: None
    agent.llm_provider = SimpleNamespace(aget_completion_stream=provider_stream)

    async def setup(instruction):
        pass

    agent._setup = setup

    async def check():
        stream = agent.arun()
        assert await anext(stream) == 'answer text'
        await stream.aclose()
        assert closed == [True]

    asyncio.run(check())


def test_reference_never_forges_anthropic_thinking_signature():
    ns = load_definitions('examples/base.py', {'R2RStreamingAgent'}, R2RAgent=object,
                          re=__import__('re'), Message=SimpleNamespace)
    agent = object.__new__(ns['R2RStreamingAgent'])

    async def add_message(message):
        pass

    agent.conversation = SimpleNamespace(add_message=add_message)
    with pytest.raises(ValueError, match='signature'):
        asyncio.run(agent._handle_thinking({}, 'unsigned thinking'))


def test_truncation_reenables_foreign_keys_after_failure():
    namespace = runpy.run_path(str(ROOT / "scripts/2_seed_mysql_text2sql.py"))
    commands = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            commands.append(sql)
            if sql.startswith("TRUNCATE"):
                raise RuntimeError("table locked")

    connection = SimpleNamespace(cursor=Cursor)
    with pytest.raises(RuntimeError, match="table locked"):
        namespace["truncate_tables"](connection, ["policy_documents"])
    assert commands[-1] == "SET FOREIGN_KEY_CHECKS=1;"


def test_dry_run_does_not_construct_knowledge_service(tmp_path):
    class Loader:
        def iter_documents_from_directory(self, path, limit):
            return iter([{"text": "one"}, {"text": "two"}])

    def fail_service():
        raise AssertionError("dry run must not initialize a store")

    logger = SimpleNamespace(info=lambda *args: None, success=lambda *args: None)
    namespace = load_definitions("scripts/5_embed_process_documents.py", {"ingest_documents"}, asyncio=asyncio, Path=Path, DocumentLoader=Loader, KnowledgeService=fail_service, logger=logger)
    asyncio.run(namespace["ingest_documents"](str(tmp_path), 1, None, True))


def test_embed_script_closes_owned_service_after_failed_ingestion(tmp_path):
    closed = []

    class Loader:
        def iter_documents_from_directory(self, path, limit):
            yield object()

    class Service:
        async def index_documents(self, documents):
            raise OSError('index failed')

        async def close(self):
            closed.append(True)

    ns = load_definitions('scripts/5_embed_process_documents.py', {'ingest_documents'},
                          asyncio=asyncio, Path=Path, DocumentLoader=Loader,
                          KnowledgeService=Service, logger=SimpleNamespace(info=lambda *args: None))
    with pytest.raises(OSError, match='index failed'):
        asyncio.run(ns['ingest_documents'](str(tmp_path), 1, None, False))
    assert closed == [True]


def test_init_milvus_script_closes_store_when_stats_fail():
    closed = []

    class Store:
        collection_name = 'offline'

        def get_stats(self):
            raise OSError('stats failed')

        def close(self):
            closed.append(True)

    ns = load_definitions('scripts/3_init_milvus.py', {'init_milvus_collection'}, MilvusStore=Store)
    assert ns['init_milvus_collection']() is False
    assert closed == [True]


def test_workflow_stream_skips_final_task_result_and_stops_runtime():
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage

    class Runtime:
        def start(self):
            self.started = True

        async def stop(self):
            self.started = False

    class Team:
        async def run_stream(self, task):
            message = TextMessage(content="answer", source="assistant")
            yield message
            yield TaskResult(messages=[message])

    logger = SimpleNamespace(info=lambda *args: None)
    events = SimpleNamespace(log_message_event=lambda **kwargs: None, log_handler_exception=lambda **kwargs: None)
    namespace = load_definitions("examples/ag_workflow.py", {"AGWorkflow"}, SingleThreadedAgentRuntime=Runtime, TextMessage=TextMessage, TaskResult=TaskResult, logging_manager=events, logger=logger)
    workflow = namespace["AGWorkflow"](object())
    workflow.teams["demo"] = Team()

    async def run():
        await workflow.initialize()
        try:
            return await workflow.run_team("demo", "question")
        finally:
            await workflow.shutdown()

    messages = asyncio.run(run())
    assert [message.content for message in messages] == ["answer"]
    assert workflow.runtime.started is False


def test_research_executor_allows_loop_progress_and_reports_timeout():
    namespace = load_definitions("examples/research.py", {"ResearchAgentMixin"}, RAGAgentMixin=object, asyncio=asyncio, tempfile=__import__("tempfile"), os=__import__("os"), subprocess=subprocess, sys=sys)
    instance = object.__new__(namespace["ResearchAgentMixin"])

    async def run():
        execution = asyncio.create_task(instance._execute_python_with_process_timeout("import time; time.sleep(0.2); print('中文')"))
        await asyncio.sleep(0.03)
        assert not execution.done()
        result = await execution
        assert result["success"] is True
        assert result["stdout"].strip() == "中文"
        assert "中文" in instance._format_python_results(result)
        timeout = await instance._execute_python_with_process_timeout("import time; time.sleep(10)", timeout=0.05)
        assert timeout["timed_out"] is True
        assert timeout["success"] is False
        assert isinstance(timeout["stdout"], str)
        assert "Execution Timeout" in instance._format_python_results(timeout)
        assert "## Error:" in instance._format_python_results(timeout)

    asyncio.run(run())


def test_research_formatter_requires_explicit_execution_status():
    namespace = load_definitions("examples/research.py", {"ResearchAgentMixin"}, RAGAgentMixin=object)
    instance = object.__new__(namespace["ResearchAgentMixin"])
    result = {"result": None, "stdout": "", "stderr": "", "error": None, "timed_out": False, "timeout": 10}

    with pytest.raises(KeyError, match="success"):
        instance._format_python_results(result)


def test_research_cancelled_process_is_reaped_and_temporary_file_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__('tempfile'), 'tempdir', str(tmp_path))
    reaped = []

    async def check():
        with anyio.CancelScope() as scope:
            class Process:
                returncode = None

                def kill(self):
                    self.returncode = -9

                async def communicate(self):
                    if self.returncode is None:
                        scope.cancel()
                        await anyio.lowlevel.checkpoint()
                    await anyio.lowlevel.checkpoint()
                    reaped.append(True)
                    return b'', b''

            async def create_process(*args, **kwargs):
                return Process()

            monkeypatch.setattr(asyncio, 'create_subprocess_exec', create_process)
            ns = load_definitions('examples/research.py', {'ResearchAgentMixin'},
                                  RAGAgentMixin=object, asyncio=asyncio, sys=sys,
                                  tempfile=__import__('tempfile'), os=__import__('os'))
            agent = object.__new__(ns['ResearchAgentMixin'])
            await agent._execute_python_with_process_timeout('pass')
        assert scope.cancelled_caught
        assert reaped == [True]
        assert list(tmp_path.iterdir()) == []

    anyio.run(check)


def test_rag_reference_initializes_each_agent_once_and_keeps_registry():
    class Agent:
        def __init__(self, **kwargs):
            self.init_count = getattr(self, "init_count", 0) + 1
            self.init_arguments = kwargs
            self.config = kwargs["config"]
            self._tools = []

    class Registry:
        def __bool__(self):
            return False

    names = {"RAGAgentMixin", "R2RRAGAgent", "R2RXMLToolsRAGAgent", "R2RStreamingRAGAgent", "R2RXMLToolsStreamingRAGAgent"}
    namespace = load_definitions("examples/rag.py", names, R2RAgent=Agent, R2RXMLToolsAgent=Agent, R2RStreamingAgent=Agent, R2RXMLStreamingAgent=Agent, ToolRegistry=Registry, SearchResultsCollector=object, logger=__import__("logging").getLogger(__name__))
    for name in names - {"RAGAgentMixin"}:
        registry = Registry()
        instance = namespace[name](database_provider=object(), llm_provider=object(), config=SimpleNamespace(rag_tools=[], stream=False), search_settings=object(), rag_generation_config=object(), knowledge_search_method=object(), content_method=object(), file_search_method=object(), tool_registry=registry)
        assert instance.init_count == 1
        assert instance.tool_registry is registry

    research_names = {"ResearchAgentMixin", "R2RResearchAgent", "R2RStreamingResearchAgent", "R2RXMLToolsResearchAgent", "R2RXMLToolsStreamingResearchAgent"}
    research = load_definitions("examples/research.py", research_names, **namespace)
    for name in research_names - {"ResearchAgentMixin"}:
        for maximum, expected in ((0, 0), (None, 15), (7, 7)):
            config = SimpleNamespace(rag_tools=[], research_tools=[], stream=False, max_iterations=maximum)
            database, llm, generation, search = object(), object(), object(), object()
            instance = research[name](app_config=object(), database_provider=database, llm_provider=llm, config=config, search_settings=search, rag_generation_config=generation, knowledge_search_method=object(), content_method=object(), file_search_method=object())
            assert instance.init_count == 1
            assert instance.config.max_iterations == expected
            assert instance.init_arguments["database_provider"] is database
            assert instance.init_arguments["llm_provider"] is llm
            assert instance.init_arguments["rag_generation_config"] is generation
            assert instance.search_settings is search


def test_docker_report_identifies_fixture_and_accepts_output_path(tmp_path):
    namespace = runpy.run_path(str(ROOT / "tests/docker_rebuild_test.py"))
    output = tmp_path / "report.json"
    namespace["main"](output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["executed"] is False
    assert data["report_kind"] == "historical_fixture"


@pytest.mark.parametrize("field", ["level_1_bonus", "no_label_rate"])
def test_round4_appliance_requires_rate_for_selected_energy_level(field):
    from app.agents.dsl_generator.dsl_runtime_helpers import DSLRuntimeHelpers
    with pytest.raises((KeyError, ValueError)):
        DSLRuntimeHelpers.appliance_subsidy(
            {"price": 100, "energy_level": 1 if field == "level_1_bonus" else None},
            {"base_rate": .1}, 0,
        )


def test_round4_coupon_does_not_invent_expiry():
    from app.agents.dsl_generator.dsl_runtime_helpers import DSLRuntimeHelpers
    result = DSLRuntimeHelpers.consumer_coupon(
        {"consumption_amount": 100, "coupon_type": "AMOUNT", "claim_time": "2025-01-01"},
        tiers=[{"type": "AMOUNT", "threshold": 0, "discount": 10}],
        coupon_types=["AMOUNT"],
    )
    assert result["status"] == "QUALIFIED" and result["expire_at"] is None


@pytest.mark.parametrize("value", ["invalid", float("nan"), float("inf")])
def test_round4_runtime_rejects_provided_invalid_number(value):
    from app.agents.dsl_generator.dsl_runtime_helpers import DSLRuntimeHelpers
    with pytest.raises((ValueError, TypeError)):
        DSLRuntimeHelpers._parse_optional_number(value)


def test_round4_runtime_rejects_invalid_policy_window():
    from app.agents.dsl_generator.dsl_runtime_helpers import DSLRuntimeHelpers
    with pytest.raises(ValueError):
        DSLRuntimeHelpers.auto_subsidy(
            {"invoice_no_tax": 100, "vehicle_type": "NEV", "purchase_time": "2025-01-01", "claim_time": "2025-01-02"},
            windows={"purchase_window": {"start": "broken"}},
        )


@pytest.mark.parametrize("output", [None, {}, {"status": "QUALIFIED"}])
def test_round4_policy_engine_requires_explicit_output(output, tmp_path):
    from app.agents.dsl_generator.rule_engine import PolicyEngine
    engine = PolicyEngine(str(tmp_path))
    rule = {"rule_id": "r", "inputs": []}
    if output is not None:
        rule["output"] = output
    engine.rules["r"] = rule
    assert engine.execute("r", {})["status"] == "ERROR"


def test_round4_policy_engine_rejects_invalid_reference_date(tmp_path):
    from app.agents.dsl_generator.rule_engine import PolicyEngine
    engine = PolicyEngine(str(tmp_path))
    engine.rules["r"] = {"rule_id": "r", "valid_period": {"start": "2020-01-01"}, "output": {"status": "QUALIFIED", "final_result": "0"}}
    assert engine.execute("r", {"claim_time": "broken"})["status"] == "ERROR"


def test_round4_generator_rejects_selected_missing_template(tmp_path):
    from app.agents.dsl_generator.dsl_generator import DSLGenerator
    import jinja2
    generator = DSLGenerator(str(tmp_path), str(tmp_path))
    with pytest.raises(jinja2.TemplateNotFound):
        generator.generate({"rule_id": "r", "inputs": [], "output": {"status": "QUALIFIED", "final_result": "0"}}, template_name="missing.yaml.j2")


@pytest.mark.parametrize("profile,data,forbidden", [
    ("appliance", {"efficiency_rates": {"base_rate": .1}, "per_item_cap": 0}, "level_1_bonus"),
    ("auto", {"tiers": [{"powertrain": "NEV", "range": [0, None], "subsidy": 0}]}, "per_person_max_cars"),
    ("consumer_coupon", {"coupon_types": ["AMOUNT"], "tiers": [{"type": "AMOUNT", "threshold": 0, "discount": 0}]}, "valid_days"),
    ("consumer_coupon", {"coupon_types": ["AMOUNT"], "tiers": [{"type": "AMOUNT", "threshold": 0, "discount": 10}]}, "valid_days"),
])
def test_round4_templates_preserve_unknown_policy_terms(profile, data, forbidden, tmp_path):
    from app.agents.dsl_generator.dsl_generator import DSLGenerator
    from app.agents.dsl_generator.rule_engine import PolicyEngine
    import yaml
    generator = DSLGenerator(str(tmp_path), str(ROOT / "templates"))
    names = {"appliance": "appliance_subsidy.yaml.j2", "auto": "auto_subsidy.yaml.j2", "consumer_coupon": "consumer_coupon.yaml.j2"}
    content = generator.generate({"rule_id": "r", **data}, template_name=names[profile])
    rule = yaml.safe_load(content)
    section = {"appliance": "efficiency_rates", "auto": "limits", "consumer_coupon": "usage_limits"}[profile]
    assert rule[section].get(forbidden) is None
    assert rule.get("valid_period", {}).get("start") is None
    engine = PolicyEngine(str(tmp_path))
    engine.rules["r"] = rule
    inputs = {"appliance": {"price": 100, "energy_level": 2, "category": "冰箱"}, "auto": {"invoice_no_tax": 100, "vehicle_type": "NEV", "purchase_time": "2025-01-01", "claim_time": "2025-01-02", "buyer_id": "u"}, "consumer_coupon": {"consumption_amount": 100, "coupon_type": "AMOUNT", "claim_time": "2025-01-01", "user_id": "u"}}[profile]
    result = engine.execute("r", inputs)
    expected = "NOT_QUALIFIED" if profile == "consumer_coupon" and data["tiers"][0]["discount"] == 0 else "QUALIFIED"
    assert result["status"] == expected


@pytest.mark.parametrize("prepare,data", [
    ("_prepare_auto_payload", {"tiers": [{"range": [0, None], "subsidy": 0}]}),
    ("_prepare_coupon_payload", {"tiers": [{"type": "AMOUNT", "discount": 0}]}),
])
def test_round4_template_normalization_rejects_missing_financial_terms(prepare, data):
    from app.agents.dsl_generator.template_registry import TemplateRegistry
    with pytest.raises((ValueError, KeyError)):
        getattr(TemplateRegistry, prepare)(data)


@pytest.mark.parametrize("payload", [{"inputs": [{"name": "x"}]}, {"inputs": [{"name": "x", "type": 1}]}, {"valid_period": {"start": "2025-02-30"}}, {"valid_period": {"start": "2026-01-01", "end": "2025-01-01"}}])
def test_round4_extractor_rejects_malformed_contract(payload):
    from app.agents.dsl_generator.dsl_extractor import DSLExtractor
    with pytest.raises(ValueError):
        DSLExtractor(use_project_config=False)._parse_response(json.dumps(payload), "普通政策")


def test_round4_domain_requires_registered_schema():
    from app.agents.dsl_generator.dsl_generator_domain import DomainDrivenDSLGenerator
    with pytest.raises(ValueError):
        object.__new__(DomainDrivenDSLGenerator).validate_with_schema({}, "unknown")


@pytest.mark.parametrize("present", ["index", "metadata"])
def test_round4_vector_refuses_incomplete_persisted_pair(tmp_path, present):
    ns = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object, Path=Path, os=__import__("os"), faiss=SimpleNamespace(IndexFlatIP=lambda dim: object()))
    agent = object.__new__(ns["VectorRetrieverAgent"])
    agent.embedding_dim, agent.logger = 2, __import__("logging").getLogger(__name__)
    agent.index_path, agent.metadata_path = str(tmp_path / "index"), str(tmp_path / "metadata")
    Path(agent.index_path if present == "index" else agent.metadata_path).write_bytes(b"incomplete")
    with pytest.raises(ValueError, match="pair|together|incomplete"):
        agent._load_or_create_index()


def test_round4_vector_stats_reads_falsey_live_index():
    ns = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object)
    class Index:
        ntotal = 3
        def __bool__(self):
            return False
    agent = object.__new__(ns["VectorRetrieverAgent"])
    agent.vector_index, agent.document_metadata, agent.embedding_cache = Index(), [], {}
    agent.model_name, agent.embedding_dim, agent.embedding_backend = "model", 2, "openai"
    assert agent.get_stats()["index_size"] == 3


def test_round4_absent_policy_limit_is_unbounded(tmp_path):
    from app.agents.dsl_generator.rule_engine import PolicyEngine
    engine = PolicyEngine(str(tmp_path))
    engine.rules["r"] = {"rule_id": "r"}
    result = engine.check_limits("r", "u", "冰箱", {"冰箱_count": 10})
    assert result["allowed"] is True and result.get("limit") is None


@pytest.mark.parametrize("embedding", ["not-vector", [float("nan")]])
def test_round4_graph_embedding_rejects_invalid_response(embedding):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def json(self):
            return {"output": {"embeddings": [{"embedding": embedding}]}}
    class RequestError(Exception):
        pass
    cfg = SimpleNamespace(dashscope_api_key="token", dashscope_base_url="offline", dashscope_dimension=None, dashscope_output_type=None, timeout=1)
    ns = load_definitions("app/agents/packs/graph_retriever/node.py", {"GraphRetrieverAgent"}, StatefulAgent=object, settings=SimpleNamespace(embedding=cfg), os=__import__("os"), requests=SimpleNamespace(post=lambda *a, **kw: Response(), RequestException=RequestError))
    agent = object.__new__(ns["GraphRetrieverAgent"])
    agent.embedding_model = "model"
    with pytest.raises(ValueError):
        agent._embed_dashscope_sync(["query"])
