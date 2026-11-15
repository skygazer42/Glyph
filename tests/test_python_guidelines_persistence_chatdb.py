"""Offline regression coverage for persistence ownership and ChatDB messages."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex, CreateTable


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_module(monkeypatch):
    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        monkeypatch.setitem(sys.modules, name, module)
        return module

    for name in (
        "app", "app.core", "app.models", "app.schemas", "app.persistence",
        "app.persistence.db", "app.persistence.crud", "app.agents", "app.agents.chatdb",
    ):
        stub(name)
    stub("app.core.llms", model_client=Mock())

    class ModuleLoader:
        def __call__(self, path, *, name=None):
            module_name = name or "_persistence_audit_" + path.replace("/", "_").replace(".", "_")
            spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            monkeypatch.setitem(sys.modules, module_name, module)
            spec.loader.exec_module(module)
            return module

        def stub(self, name, **attributes):
            return stub(name, **attributes)

    return ModuleLoader()


@pytest.fixture
def dbaccess(load_module):
    return load_module("app/persistence/db/dbaccess.py")


def connection_double():
    cursor = Mock()
    cursor.description = [("value",)]
    cursor.fetchall.return_value = [(0,)]
    connection = Mock()
    connection.cursor.return_value = cursor
    return connection, cursor


def test_unconnected_database_has_explicit_error(dbaccess):
    with pytest.raises(Exception, match="connect|连接"):
        dbaccess.DBAccess().run_sql("SELECT 1")


@pytest.mark.parametrize("fail", [False, True])
def test_mysql_cursor_and_owned_connection_close(dbaccess, monkeypatch, fail):
    import pymysql

    connection, cursor = connection_double()
    monkeypatch.setattr(pymysql, "connect", Mock(return_value=connection))
    if fail:
        cursor.execute.side_effect = ValueError("query failed")
    access = dbaccess.DBAccess()
    access.connect_to_mysql(host="host", dbname="db", user="user", password="secret", port=3306)
    try:
        if fail:
            with pytest.raises(ValueError, match="query failed"):
                access.run_sql("SELECT 0")
            connection.rollback.assert_called_once()
        else:
            assert access.run_sql("SELECT 0").to_dict("records") == [{"value": 0}]
        cursor.close.assert_called_once()
    finally:
        access.close()
        access.close()
    connection.close.assert_called_once()


def test_mysql_empty_password_is_not_replaced_by_environment(dbaccess, monkeypatch):
    import pymysql

    connection, _ = connection_double()
    connect = Mock(return_value=connection)
    monkeypatch.setattr(pymysql, "connect", connect)
    monkeypatch.setenv("PASSWORD", "wrong-secret")
    access = dbaccess.DBAccess()
    access.connect_to_mysql(host="host", dbname="db", user="user", password="", port=3306)
    assert connect.call_args.kwargs["password"] == ""
    access.close()


def test_postgres_reuses_owned_connection_and_closes_each_cursor(dbaccess, load_module):
    connection, cursor = connection_double()
    connect = Mock(return_value=connection)
    load_module.stub("psycopg2", connect=connect, Error=RuntimeError, InterfaceError=ConnectionError)
    load_module.stub("psycopg2.extras")
    access = dbaccess.DBAccess()
    access.connect_to_postgres(host="host", dbname="db", user="user", password="secret", port=5432)
    try:
        assert access.run_sql("SELECT 0").to_dict("records") == [{"value": 0}]
        assert access.run_sql("SELECT 0").to_dict("records") == [{"value": 0}]
    finally:
        access.close()
    assert connect.call_count == 1
    assert cursor.close.call_count == 2
    connection.close.assert_called_once()


def test_bigquery_implicit_credentials_error_is_preserved(dbaccess, load_module):
    error = RuntimeError("missing application credentials")
    load_module.stub("google.api_core.exceptions", GoogleAPIError=RuntimeError)
    load_module.stub("google.cloud", bigquery=SimpleNamespace(Client=Mock(side_effect=error)))
    load_module.stub("google.oauth2", service_account=Mock())
    with pytest.raises(RuntimeError, match="missing application credentials"):
        dbaccess.DBAccess().connect_to_bigquery(project_id="project")


def test_duckdb_init_failure_closes_connection(dbaccess, load_module):
    connection = Mock()
    connection.query.side_effect = ValueError("bad init")
    load_module.stub("duckdb", connect=Mock(return_value=connection))
    with pytest.raises(ValueError, match="bad init"):
        dbaccess.DBAccess().connect_to_duckdb(":memory:", init_sql="bad")
    connection.close.assert_called_once()


def test_duckdb_download_has_timeout_and_closes_response(dbaccess, load_module, monkeypatch, tmp_path):
    response = Mock(content=b"database")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr(dbaccess.requests, "get", get)
    monkeypatch.chdir(tmp_path)
    connection = Mock()
    load_module.stub("duckdb", connect=Mock(return_value=connection))
    access = dbaccess.DBAccess()
    access.connect_to_duckdb("https://example.test/db.duckdb")
    assert get.call_args.kwargs["timeout"]
    response.__exit__.assert_called_once()
    assert (tmp_path / "db.duckdb").read_bytes() == b"database"
    access.close()


@pytest.fixture
def orm(load_module):
    base = load_module("app/models/base.py", name="app.models.base")
    modules = {}
    for entity in ("db_connection", "schema_table", "schema_column", "schema_relationship", "value_mapping", "chat_history"):
        modules[entity] = load_module(f"app/models/{entity}.py", name=f"app.models.{entity}")
    engine = create_engine("sqlite://")
    try:
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
        base.Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield SimpleNamespace(base=base, session=session, **modules)
    finally:
        engine.dispose()


def orm_contract(base):
    """Record database semantics independently of Python mapping annotations."""
    tables = {}
    for table in base.Base.metadata.sorted_tables:
        tables[table.name] = {
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "unique": column.unique,
                    "index": column.index,
                    "default": str(column.default.arg) if column.default is not None else None,
                    "server_default": str(column.server_default.arg) if column.server_default is not None else None,
                    "onupdate": str(column.onupdate.arg) if column.onupdate is not None else None,
                    "foreign_keys": sorted((key.target_fullname, key.ondelete, key.onupdate) for key in column.foreign_keys),
                }
                for column in table.columns
            ],
            "indexes": sorted((index.name, index.unique, [column.name for column in index.columns]) for index in table.indexes),
        }
    ddl = {}
    for name, dialect in (("sqlite", sqlite.dialect()), ("mysql", mysql.dialect()), ("postgresql", postgresql.dialect())):
        statements = []
        for table in base.Base.metadata.sorted_tables:
            statements.append(str(CreateTable(table).compile(dialect=dialect)))
            for index in sorted(table.indexes, key=lambda index: index.name):
                statements.append(str(CreateIndex(index).compile(dialect=dialect)))
        ddl[name] = statements
    return {"metadata": tables, "ddl": ddl}


def test_native_orm_mapping_preserves_existing_metadata_and_dialects(orm):
    baseline = json.loads((ROOT / "docs/python-audit/round2/api/orm-contract-before.json").read_text(encoding="utf-8"))
    # JSON normalizes tuples in the metadata into arrays.
    assert json.loads(json.dumps(orm_contract(orm.base))) == baseline


def test_native_orm_relationships_preserve_orphan_cascades_and_primary_keys(orm, load_module):
    crud = load_module("app/persistence/crud/base.py", name="app.persistence.crud.base")
    connection = add_connection(orm)
    table = orm.schema_table.SchemaTable(connection_id=connection.id, table_name="items")
    column = orm.schema_column.SchemaColumn(column_name="value", data_type="integer")
    mapping = orm.value_mapping.ValueMapping(nl_term="zero", db_value="0")
    column.value_mappings.append(mapping)
    table.columns.append(column)
    session = orm.chat_history.ChatSession(id="session", title="Offline")
    message = orm.chat_history.ChatMessage(message_type="user_query", content="q", order_index=0)
    session.messages.append(message)
    orm.session.add_all([table, session])
    orm.session.commit()
    assert column.table is table and mapping.column is column and message.session is session
    assert crud.CRUDBase(orm.chat_history.ChatSession).get(orm.session, "session") is session
    assert crud.CRUDBase(orm.db_connection.DBConnection).get(orm.session, connection.id) is connection
    orm.session.delete(table)
    orm.session.delete(session)
    orm.session.commit()
    assert orm.session.query(orm.schema_column.SchemaColumn).count() == 0
    assert orm.session.query(orm.value_mapping.ValueMapping).count() == 0
    assert orm.session.query(orm.chat_history.ChatMessage).count() == 0


def add_connection(orm):
    connection = orm.db_connection.DBConnection(
        name="test", db_type="mysql", host="host", port=3306,
        username="user", password_encrypted="old", database_name="db",
    )
    orm.session.add(connection)
    orm.session.commit()
    return connection


def test_connection_update_preserves_empty_password_and_input(orm, load_module):
    load_module.stub("app.config.app_config", settings=SimpleNamespace(database=SimpleNamespace(use_neo4j=False)))
    load_module.stub("app.core.security", get_password_hash=Mock(), verify_password=Mock())
    load_module("app/schemas/db_connection.py", name="app.schemas.db_connection")
    load_module("app/persistence/crud/base.py", name="app.persistence.crud.base")
    module = load_module("app/persistence/crud/crud_db_connection.py")
    connection = add_connection(orm)
    update = {"password": "", "name": "updated"}
    module.db_connection.update(orm.session, db_obj=connection, obj_in=update)
    assert connection.password_encrypted == ""
    assert update == {"password": "", "name": "updated"}


def test_schema_refresh_removes_value_mappings_before_columns(orm, load_module, monkeypatch):
    module = load_module("app/persistence/db/schema_introspector.py")
    connection = add_connection(orm)
    table = orm.schema_table.SchemaTable(connection_id=connection.id, table_name="old")
    orm.session.add(table)
    orm.session.flush()
    column = orm.schema_column.SchemaColumn(table_id=table.id, column_name="id", data_type="int")
    orm.session.add(column)
    orm.session.flush()
    orm.session.add(orm.value_mapping.ValueMapping(column_id=column.id, nl_term="zero", db_value="0"))
    orm.session.commit()
    raw_connection = Mock()
    monkeypatch.setattr(module, "_open_mysql_connection", Mock(return_value=raw_connection))
    monkeypatch.setattr(module, "_load_mysql_tables", Mock(return_value=[]))
    monkeypatch.setattr(module, "_load_mysql_columns", Mock(return_value={}))
    monkeypatch.setattr(module, "_load_mysql_relationships", Mock(return_value=[]))
    module.refresh_mysql_schema_metadata(orm.session, connection)
    assert orm.session.query(orm.value_mapping.ValueMapping).count() == 0
    assert orm.session.query(orm.schema_table.SchemaTable).count() == 0
    raw_connection.close.assert_called_once()


def test_schema_refresh_failure_rolls_back_prior_metadata(orm, load_module, monkeypatch):
    module = load_module("app/persistence/db/schema_introspector.py")
    connection = add_connection(orm)
    table = orm.schema_table.SchemaTable(connection_id=connection.id, table_name="old")
    orm.session.add(table)
    orm.session.commit()
    monkeypatch.setattr(module, "_open_mysql_connection", Mock(return_value=Mock()))
    monkeypatch.setattr(module, "_load_mysql_tables", Mock(return_value=[{}]))
    monkeypatch.setattr(module, "_load_mysql_columns", Mock(return_value={}))
    monkeypatch.setattr(module, "_load_mysql_relationships", Mock(return_value=[]))
    with pytest.raises(KeyError):
        module.refresh_mysql_schema_metadata(orm.session, connection)
    assert orm.session.query(orm.schema_table.SchemaTable).one().table_name == "old"


def test_collector_flushes_explicit_empty_result(load_module):
    load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/base.py", name="app.agents.chatdb.base")
    collector = module.StreamResponseCollector()
    callback = AsyncMock()
    collector.set_callback(callback)
    asyncio.run(collector.buffer_message(None, "source", "done", result={}))
    assert callback.await_count == 1
    assert callback.call_args.args[1].result == {}


def test_collector_keeps_messages_arriving_during_flush(load_module):
    load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/base.py", name="app.agents.chatdb.base")
    collector = module.StreamResponseCollector()
    collector.message_buffers["first"] = "before"
    delivered = []

    async def receive(ctx, message, message_context):
        delivered.append(message.content)
        if message.content == "before":
            await collector.buffer_message(None, "first", "after")
            await collector.buffer_message(None, "second", "new source")

    collector.set_callback(receive)
    asyncio.run(collector.flush_all_buffers())
    assert delivered == ["before"]
    assert collector.message_buffers == {"first": "after", "second": "new source"}


class FakeAgent:
    internal_unbound_subscriptions_list: list[object] = []

    def __init__(self, **kwargs):
        self.id = SimpleNamespace(key="test")
        self.send_response = AsyncMock()
        self.send_error = AsyncMock()
        self.publish_message = AsyncMock()
        self.handle_exception = AsyncMock()


def test_unconfigured_hybrid_agent_generates_sql_without_claiming_retrieval(load_module, monkeypatch):
    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    load_module.stub("app.config.app_config", settings=SimpleNamespace(system=SimpleNamespace(
        hybrid_retrieval_enabled=True, auto_learning_enabled=True,
    )))
    schemas = load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module(
        "app/agents/chatdb/hybrid_sql_generator.py", name="app.agents.chatdb.hybrid_sql_generator",
    )
    model_agent = SimpleNamespace(run=AsyncMock(return_value=object()))
    constructor = Mock(return_value=model_agent)
    monkeypatch.setattr(module, "AssistantAgent", constructor)
    agent = module.HybridSqlGeneratorAgent()
    agent.db_type = "MySQL"
    agent.model_client = Mock()
    agent.rebuild_memory_from_content = Mock(return_value=object())
    agent.final_text = Mock(return_value="SELECT 0")
    message = schemas.AnalysisMessage(query="q", analysis="a", memory_content=[], connection_id=0)

    asyncio.run(agent.handle_analysis_message(message, None))

    agent.handle_exception.assert_not_awaited()
    published = agent.publish_message.call_args.args[0]
    assert published.sql == "SELECT 0"
    assert published.connection_id == 0
    assert "MySQL" in constructor.call_args.kwargs["system_message"]
    final_event = next(call for call in agent.send_response.call_args_list if call.kwargs.get("is_final"))
    assert final_event.kwargs["result"] == {"sql": "SELECT 0", "examples_used": 0}
    progress = [call.args[0] for call in agent.send_response.call_args_list]
    assert any("尚未配置" in text for text in progress)
    assert not any("正在使用混合检索引擎查找" in text for text in progress)


def test_sql_error_is_propagated_to_visualization_and_run_off_loop(load_module):
    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    load_module("app/persistence/db/dbaccess.py", name="app.persistence.db.dbaccess")
    schemas = load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/sql_executor.py", name="app.agents.chatdb.sql_executor")
    event_loop_thread = threading.get_ident()
    called_threads = []

    def run_sql(sql):
        called_threads.append(threading.get_ident())
        raise ValueError("database unavailable")

    agent = module.SqlExecutorAgent(db_access=SimpleNamespace(run_sql=run_sql))
    message = schemas.SqlExplanationMessage(query="q", sql="SELECT 1", explanation="e", connection_id=0)
    asyncio.run(agent.handle_message(message, None))
    result = agent.publish_message.call_args.args[0]
    assert result.error == "SQL执行错误: database unavailable"
    assert result.connection_id == 0
    assert called_threads and called_threads[0] != event_loop_thread


@pytest.mark.parametrize("fail", [False, True])
def test_execute_query_closes_owned_access(load_module, monkeypatch, fail):
    load_module.stub("app.models.db_connection", DBConnection=object)
    load_module("app/persistence/db/dbaccess.py", name="app.persistence.db.dbaccess")
    module = load_module("app/agents/chatdb/db_service.py")
    access = Mock()
    access.run_sql.return_value = pd.DataFrame([{"value": 0}])
    if fail:
        access.run_sql.side_effect = ValueError("failed")
    monkeypatch.setattr(module, "_build_db_access", Mock(return_value=access))
    if fail:
        with pytest.raises(ValueError, match="failed"):
            module.execute_query(object(), "SELECT 0")
    else:
        assert module.execute_query(object(), "SELECT 0") == [{"value": 0}]
    access.close.assert_called_once()


def test_sql_value_mapping_uses_literal_terms_and_values(load_module):
    load_module.stub("app.config.app_config", settings=SimpleNamespace(performance=SimpleNamespace(cache_ttl=256)))
    load_module("app/agents/chatdb/domain_zh_gov.py", name="app.agents.chatdb.domain_zh_gov")
    module = load_module("app/agents/chatdb/text2sql_utils.py", name="app.agents.chatdb.text2sql_utils")
    assert module.process_sql_with_value_mappings(
        "SELECT * FROM t WHERE t.city = 'A+B'", {"t.city": {"A+B": "0"}},
    ) == "SELECT * FROM t WHERE t.city = '0'"
    assert module.process_sql_with_value_mappings(
        "SELECT * FROM t WHERE city = 'capital'", {"t.city": {"capital": "O'Brien"}},
    ) == "SELECT * FROM t WHERE city = 'O''Brien'"


def test_domain_month_window_includes_last_day_and_keeps_zero(load_module):
    from datetime import date

    module = load_module("app/agents/chatdb/domain_zh_gov.py", name="app.agents.chatdb.domain_zh_gov")
    previous = module.parse_time_window("上个月", today=date(2024, 4, 30))
    assert previous.end == date(2024, 3, 31)
    zero = module.parse_time_window("近0月", today=date(2024, 3, 31))
    assert zero.start == zero.end == date(2024, 3, 31)


def test_schema_retrieval_failure_is_visible(load_module):
    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    load_module.stub("app.agents.chatdb.text2sql_service", retrieve_schema_for_connection=AsyncMock(side_effect=ValueError("metadata unavailable")))
    load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/schema_retriever.py", name="app.agents.chatdb.schema_retriever")
    agent = module.SchemaRetrieverAgent()
    with pytest.raises(ValueError, match="metadata unavailable"):
        asyncio.run(agent.retrieve_schema(0, "q"))


def test_visualization_rejects_non_object_json_with_safe_empty_row_fallback(load_module):
    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/visualization_recommender.py", name="app.agents.chatdb.visualization_recommender")
    agent = module.VisualizationRecommenderAgent()
    assert agent._parse_visualization_config("[]", [{}])["type"] == "table"
    assert agent._parse_visualization_config("invalid", [{}])["config"]["columns"] == []
    assert agent._parse_visualization_config("{}", [{"value": 0}])["config"]["columns"] == ["value"]


def test_crud_commit_failure_leaves_session_usable(orm, load_module):
    from sqlalchemy.exc import IntegrityError
    from pydantic import BaseModel

    module = load_module("app/persistence/crud/base.py", name="app.persistence.crud.base")
    add_connection(orm)

    class ConnectionCreate(BaseModel):
        name: str = "test"
        db_type: str = "mysql"
        host: str = "host"
        port: int = 3306
        username: str = "user"
        password_encrypted: str = ""
        database_name: str = "db"

    repository = module.CRUDBase(orm.db_connection.DBConnection)
    with pytest.raises(IntegrityError):
        repository.create(orm.session, obj_in=ConnectionCreate())
    assert repository.create(orm.session, obj_in=ConnectionCreate(name="next")).name == "next"


@pytest.mark.parametrize("activity_failure", [False, True])
def test_chat_message_and_session_activity_commit_atomically(orm, load_module, activity_failure):
    from datetime import datetime

    load_module("app/schemas/chat_history.py", name="app.schemas.chat_history")
    load_module("app/persistence/crud/base.py", name="app.persistence.crud.base")
    load_module("app/persistence/crud/crud_chat_history.py", name="app.persistence.crud.crud_chat_history")
    engine = orm.session.get_bind()
    load_module.stub("app.persistence.db.session", SessionLocal=lambda: Session(engine))
    load_module.stub("app.persistence.crud.crud_db_connection", db_connection=Mock())
    store_module = load_module("app/agents/service/chat_history_store.py")
    previous_activity = datetime(2020, 1, 1)
    orm.session.add(orm.chat_history.ChatSession(id="atomic-session", title="Offline", updated_at=previous_activity))
    orm.session.commit()

    def fail_activity_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith(f"UPDATE {orm.chat_history.ChatSession.__tablename__} "):
            raise RuntimeError("session activity update failed")

    if activity_failure:
        event.listen(engine, "before_cursor_execute", fail_activity_update)
    try:
        store = store_module.ChatHistoryStore()
        if activity_failure:
            with pytest.raises(RuntimeError, match="session activity update failed"):
                store.record_message("atomic-session", role="user", content="Policy?", order_index=0)
        else:
            store.record_message("atomic-session", role="user", content="Policy?", order_index=0)
    finally:
        if activity_failure:
            event.remove(engine, "before_cursor_execute", fail_activity_update)

    orm.session.expire_all()
    messages = orm.session.query(orm.chat_history.ChatMessage).all()
    session = orm.session.get(orm.chat_history.ChatSession, "atomic-session")
    if activity_failure:
        assert messages == []
        assert session.updated_at == previous_activity
    else:
        assert len(messages) == 1
        assert messages[0].content == "Policy?" and messages[0].order_index == 0
        assert session.updated_at > previous_activity


def test_text_model_result_rejects_tool_events(load_module):
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage, ToolCallExecutionEvent

    load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/base.py", name="app.agents.chatdb.base")
    assert module.BaseAgent.final_text(TaskResult(messages=[TextMessage(content="SELECT 0", source="model")])) == "SELECT 0"
    with pytest.raises(TypeError, match="text|Text"):
        module.BaseAgent.final_text(TaskResult(messages=[ToolCallExecutionEvent(content=[], source="model")]))
    with pytest.raises(ValueError, match="empty"):
        module.BaseAgent.final_text(TaskResult(messages=[TextMessage(content="  ", source="model")]))


def test_connection_settings_snapshot_does_not_read_orm_in_worker(load_module):
    owner_thread = threading.get_ident()
    class Connection:
        db_type = "mysql"
        host = "host"
        database_name = "db"
        username = "user"
        password_encrypted = ""
        port = 3306
        def __getattribute__(self, name):
            if threading.get_ident() != owner_thread:
                raise RuntimeError("ORM values must be read on their owning thread")
            return super().__getattribute__(name)
    load_module.stub("app.models.db_connection", DBConnection=Connection)
    access = Mock()
    access.run_sql.return_value = pd.DataFrame([{"value": 0}])
    load_module.stub("app.persistence.db.dbaccess", DBAccess=Mock(return_value=access))
    module = load_module("app/agents/chatdb/db_service.py")
    settings = module.ConnectionSettings.from_connection(Connection())
    async def query():
        return await asyncio.to_thread(module.execute_query, settings, "SELECT 0")
    assert asyncio.run(query()) == [{"value": 0}]
    access.connect_to_mysql.assert_called_once_with(host="host", dbname="db", user="user", password="", port=3306)
    access.close.assert_called_once()


@pytest.mark.parametrize("fail", [False, True])
def test_text2sql_owned_session_closes_before_llm_and_keeps_io_off_loop(load_module, fail):
    owner = threading.get_ident()
    events = []
    connection = SimpleNamespace(id=0, db_type="mysql", host="host", database_name="db", username="user", password_encrypted="", port=3306)
    class OwnedSession:
        def __enter__(self):
            assert threading.get_ident() != owner
            events.append("open")
            return self
        def __exit__(self, *args):
            assert threading.get_ident() != owner
            events.append("close")
    load_module.stub("app.models.db_connection", DBConnection=SimpleNamespace)
    load_module.stub("app.persistence.db.dbaccess", DBAccess=Mock())
    load_module("app/agents/chatdb/db_service.py", name="app.agents.chatdb.db_service")
    load_module.stub("app.persistence.db.session", SessionLocal=OwnedSession)
    load_module.stub("app.persistence.crud", db_connection=SimpleNamespace(get=Mock(return_value=connection)))
    schema = {"tables": [{"id": 1, "name": "t", "description": None}], "columns": [], "relationships": []}
    async def select(snapshot, query):
        assert threading.get_ident() == owner
        assert events == ["open", "close"]
        return snapshot
    load_module.stub("app.agents.chatdb.text2sql_utils", snapshot_schema=Mock(return_value=schema), select_relevant_schema=select,
                     retrieve_relevant_schema=AsyncMock(), get_value_mappings=Mock(return_value={}), format_schema_for_prompt=Mock(return_value="t"),
                     process_sql_with_value_mappings=lambda sql, mappings: sql, validate_sql=lambda sql: True,
                     extract_sql_from_llm_response=lambda response: response)
    if fail:
        sys.modules["app.agents.chatdb.text2sql_utils"].snapshot_schema.side_effect = ValueError("metadata unavailable")
    load_module("app/schemas/query.py", name="app.schemas.query")
    load_module("app/agents/chatdb/domain_zh_gov.py", name="app.agents.chatdb.domain_zh_gov")
    module = load_module("app/agents/chatdb/text2sql_service.py", name="app.agents.chatdb.text2sql_service")
    async def llm(prompt):
        assert threading.get_ident() == owner
        assert events == ["open", "close"]
        return "SELECT 0"
    def execute(settings, sql):
        assert threading.get_ident() != owner
        assert settings.port == 3306 and settings.password_encrypted == ""
        return [{"value": 0}]
    module.generate_sql_with_model = llm
    module.execute_query = execute
    result = asyncio.run(module.process_text2sql_query_for_connection_async(0, "q"))
    if fail:
        assert "metadata unavailable" in result.error and result.results is None
    else:
        assert result.error is None and result.results == [{"value": 0}]
    assert events == ["open", "close"]


@pytest.mark.parametrize("missing_final", [False, True])
def test_query_analyzer_emits_actual_analysis_and_closes_stream(load_module, monkeypatch, missing_final):
    from autogen_agentchat.messages import TextMessage
    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    schemas = load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/query_analyzer.py", name="app.agents.chatdb.query_analyzer")
    closed = []
    async def stream(**kwargs):
        try:
            if not missing_final:
                yield TextMessage(content="Actual SQL analysis", source="query_analyzer")
        finally:
            closed.append(True)
    monkeypatch.setattr(module, "AssistantAgent", lambda **kwargs: SimpleNamespace(run_stream=stream))
    agent = module.QueryAnalyzerAgent()
    agent.model_client = object()
    agent._prepare_task = lambda *args: "task"
    agent.serialize_memory_content = lambda memory: []
    asyncio.run(agent.handle_message(schemas.SchemaContextMessage(query="q"), None))
    assert closed == [True]
    if missing_final:
        agent.handle_exception.assert_awaited_once()
        agent.publish_message.assert_not_awaited()
    else:
        assert agent.publish_message.call_args.args[0].analysis == "Actual SQL analysis"


def test_borrowed_database_serializes_queries_and_close(dbaccess):
    from concurrent.futures import ThreadPoolExecutor
    import time
    access = dbaccess.DBAccess()
    events = []
    entered = threading.Event()
    release = threading.Event()
    def query(sql):
        events.append(sql)
        entered.set()
        assert release.wait(2)
        events.append("done")
        return pd.DataFrame()
    access._run_sql = query
    access._close_connection = lambda: events.append("closed")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(access.run_sql, "SELECT 1")
        assert entered.wait(2)
        close = pool.submit(access.close)
        time.sleep(0.01)
        assert events == ["SELECT 1"]
        release.set()
        first.result(timeout=2)
        close.result(timeout=2)
    assert events == ["SELECT 1", "done", "closed"]


@pytest.mark.parametrize("missing_final", [False, True])
def test_sql_explainer_requires_final_result_and_closes_stream(load_module, monkeypatch, missing_final):
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage

    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    schemas = load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module = load_module("app/agents/chatdb/sql_explainer.py", name="app.agents.chatdb.sql_explainer")
    closed = []
    async def stream(**kwargs):
        try:
            if not missing_final:
                yield TaskResult(messages=[TextMessage(content="Returns the value zero", source="sql_explainer")])
        finally:
            closed.append(True)
    monkeypatch.setattr(module, "AssistantAgent", lambda **kwargs: SimpleNamespace(run_stream=stream))
    agent = module.SqlExplainerAgent()
    agent.model_client = object()
    agent._prepare_prompt = lambda *args: "prompt"
    agent.final_text = lambda result: result.messages[-1].content
    asyncio.run(agent.handle_message(schemas.SqlMessage(query="q", sql="SELECT 0"), None))
    assert closed == [True]
    if missing_final:
        agent.handle_exception.assert_awaited_once()
        agent.publish_message.assert_not_awaited()
    else:
        assert agent.publish_message.call_args.args[0].explanation == "Returns the value zero"


def test_duckdb_borrowed_query_preserves_initialized_session(dbaccess, load_module):
    connection = Mock()
    state = []
    def query(sql):
        if sql == "CREATE TEMP TABLE answer AS SELECT 0 value":
            state.append("answer")
        else:
            assert state == ["answer"]
        return SimpleNamespace(to_df=lambda: pd.DataFrame([{"value": 0}]))
    connection.query.side_effect = query
    load_module.stub("duckdb", connect=Mock(return_value=connection))
    access = dbaccess.DBAccess()
    access.connect_to_duckdb(":memory:", init_sql="CREATE TEMP TABLE answer AS SELECT 0 value")
    try:
        assert asyncio.run(asyncio.to_thread(access.run_sql, "SELECT * FROM answer")).to_dict("records") == [{"value": 0}]
        connection.cursor.assert_not_called()
    finally:
        access.close()
    connection.close.assert_called_once()


def test_zero_query_cache_capacity_disables_storage_and_negative_is_invalid(load_module):
    load_module.stub("app.config.app_config", settings=SimpleNamespace(performance=SimpleNamespace(cache_ttl=0)))
    module = load_module("app/agents/chatdb/text2sql_utils.py", name="app.agents.chatdb.text2sql_utils")
    cache = module._LRUCache(0)
    cache.put("q", {"entities": []})
    assert cache.get("q") is None and len(cache) == 0
    with pytest.raises(ValueError, match="nonnegative"):
        module._LRUCache(-1)


def test_sql_validation_distinguishes_bad_queries_from_parser_failures(load_module, monkeypatch):
    from sqlparse.exceptions import SQLParseError

    load_module.stub("app.config.app_config", settings=SimpleNamespace(performance=SimpleNamespace(cache_ttl=0)))
    module = load_module("app/agents/chatdb/text2sql_utils.py", name="app.agents.chatdb.text2sql_utils")
    monkeypatch.setattr(module.sqlparse, "parse", Mock(side_effect=SQLParseError("invalid SQL")))
    assert module.validate_sql("SELECT (") is False
    monkeypatch.setattr(module.sqlparse, "parse", Mock(side_effect=RuntimeError("parser failed")))
    with pytest.raises(RuntimeError, match="parser failed"):
        module.validate_sql("SELECT 1")


@pytest.mark.parametrize("kind", ["analyzer", "explainer"])
def test_chatdb_send_failure_closes_model_stream_before_handler_returns(load_module, monkeypatch, kind):
    from autogen_agentchat.messages import ModelClientStreamingChunkEvent

    load_module.stub("app.agents.chatdb.base", BaseAgent=FakeAgent)
    schemas = load_module("app/schemas/text2sql.py", name="app.schemas.text2sql")
    load_module("app/agents/chatdb/types.py", name="app.agents.chatdb.types")
    module_path = "query_analyzer" if kind == "analyzer" else "sql_explainer"
    module = load_module(f"app/agents/chatdb/{module_path}.py", name=f"app.agents.chatdb.{module_path}")
    closed = []
    async def stream(**kwargs):
        try:
            yield ModelClientStreamingChunkEvent(content="chunk", source=module_path)
            pytest.fail("stream must stop after sending fails")
        finally:
            closed.append(True)
    monkeypatch.setattr(module, "AssistantAgent", lambda **kwargs: SimpleNamespace(run_stream=stream))
    if kind == "analyzer":
        agent = module.QueryAnalyzerAgent()
        agent._prepare_task = lambda *args: "task"
        message = schemas.SchemaContextMessage(query="q")
    else:
        agent = module.SqlExplainerAgent()
        agent._prepare_prompt = lambda *args: "prompt"
        message = schemas.SqlMessage(query="q", sql="SELECT 0")
    agent.model_client = object()
    agent.send_response.side_effect = OSError("client disconnected")
    async def check():
        await agent.handle_message(message, None)
        assert closed == [True]
    asyncio.run(check())
    agent.handle_exception.assert_awaited_once()
    agent.publish_message.assert_not_awaited()


@pytest.fixture
def round4_text2sql(load_module):
    load_module.stub("app.config.app_config", settings=SimpleNamespace(performance=SimpleNamespace(cache_ttl=0)))
    load_module("app/agents/chatdb/domain_zh_gov.py", name="app.agents.chatdb.domain_zh_gov")
    return load_module("app/agents/chatdb/text2sql_utils.py", name="app.agents.chatdb.text2sql_utils")


@pytest.mark.parametrize("change", [
    {"entities": "policy"}, {"relationships": [1]}, {"query_intent": {}},
    {"likely_aggregations": "count"}, {"time_related": "false"},
    {"comparison_related": None},
])
def test_round4_text2sql_invalid_analysis_uses_visible_keyword_strategy(
    round4_text2sql, monkeypatch, caplog, change
):
    module = round4_text2sql
    payload = {"entities": [], "relationships": [], "query_intent": "find policy",
               "likely_aggregations": [], "time_related": False, "comparison_related": False}
    payload.update(change)
    monkeypatch.setattr(module, "model_client", SimpleNamespace(create=AsyncMock(
        return_value=SimpleNamespace(content=json.dumps(payload)))))
    result = asyncio.run(module.analyze_query_with_llm("policy details"))
    assert result == module._create_fallback_analysis("policy details")
    assert any(record.exc_info and "using keyword analysis" in record.message for record in caplog.records)


def test_round4_text2sql_valid_analysis_preserves_empty_lists_false_and_cache(round4_text2sql, monkeypatch):
    module = round4_text2sql
    payload = {"entities": [], "relationships": [], "query_intent": "find policy",
               "likely_aggregations": [], "time_related": False, "comparison_related": False}
    create = AsyncMock(return_value=SimpleNamespace(content=json.dumps(payload)))
    monkeypatch.setattr(module, "model_client", SimpleNamespace(create=create))
    assert asyncio.run(module.analyze_query_with_llm("policy")) == payload
    assert asyncio.run(module.analyze_query_with_llm("policy")) == payload
    create.assert_awaited_once()


@pytest.mark.parametrize("row", [
    {"table_id": "7", "relevance_score": 8, "reasoning": "relevant"},
    {"table_id": True, "relevance_score": 8, "reasoning": "relevant"},
    {"table_id": 7, "relevance_score": 11, "reasoning": "relevant"},
    {"table_id": 7, "relevance_score": float("nan"), "reasoning": "relevant"},
    {"table_id": 7, "reasoning": "relevant"},
    {"table_id": 7, "relevance_score": 8, "reasoning": {}},
    {"table_id": 999, "relevance_score": 8, "reasoning": "not an available table"},
])
def test_round4_text2sql_invalid_ranking_uses_visible_keyword_strategy(
    round4_text2sql, monkeypatch, caplog, row
):
    module = round4_text2sql
    monkeypatch.setattr(module, "model_client", SimpleNamespace(create=AsyncMock(
        return_value=SimpleNamespace(content=json.dumps([row])))))
    fallback = Mock(return_value=[(7, 4.0)])
    monkeypatch.setattr(module, "basic_table_matching", fallback)
    tables = [{"id": 7, "name": "documents", "description": "policy"}]
    result = asyncio.run(module.find_relevant_tables_semantic("details", {}, tables))
    assert result == [(7, 4.0)]
    fallback.assert_called_once_with("details", tables)
    assert any(record.exc_info and "using keyword matching" in record.message for record in caplog.records)


@pytest.mark.parametrize("ranking, expected", [
    ([], []),
    ([{"table_id": 0, "relevance_score": 0, "reasoning": "unrelated"}], []),
    ([{"table_id": 0, "relevance_score": 8, "reasoning": "relevant"}], [(0, 8)]),
])
def test_round4_text2sql_valid_ranking_keeps_empty_zero_and_integer_ids(
    round4_text2sql, monkeypatch, ranking, expected
):
    module = round4_text2sql
    monkeypatch.setattr(module, "model_client", SimpleNamespace(create=AsyncMock(
        return_value=SimpleNamespace(content=json.dumps(ranking)))))
    fallback = Mock(side_effect=AssertionError("valid ranking must not enter fallback"))
    monkeypatch.setattr(module, "basic_table_matching", fallback)
    assert asyncio.run(module.find_relevant_tables_semantic(
        "details", {}, [{"id": 0, "name": "documents", "description": "policy"}])) == expected
    fallback.assert_not_called()
