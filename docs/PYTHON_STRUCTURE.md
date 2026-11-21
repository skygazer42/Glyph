# Python 代码与目录约定

本次按 `python-coding-guidelines` 整理仓库内的定义、引用、脚本和文档，继续支持项目既有的 Python 3.10。2026-11-17 的改动按用户要求暂不执行测试、静态检查、编译、服务启动或数据库操作；以下描述的是源码组织，不表示已通过运行验收。

后续逐文件、逐类、逐函数审查覆盖及保留理由见 [完整审查记录](python-audit/README.md)，包含全部当前定义的索引和源文件指纹。

## 目录职责

```text
api_server.py                     前端使用的 /api/* 应用入口
app/
  main.py                         保留 /query、/load-docs、认证与限流的应用入口
  api/
    endpoints/                    HTTP、SSE、上传和会话路由
    schemas.py                    问答、DSL、附件和通用 HTTP 契约
    deps.py                       应用依赖创建与关闭
  config/
    app_config.py                 环境、存储、解析器和框架配置
    agent_config.py               AgentServiceConfig 与 CLI 的配置
  models/
    base.py                       SQLAlchemy DeclarativeBase
    policy.py                     政策、问题、答案及 Agent 消息契约
    database.py                   连接、表、列、关系、值映射的 ORM 模型
    chat_history.py               会话、消息和快照的 ORM 模型
  schemas/
    database.py                   连接和元数据的创建、更新契约
    knowledge.py                  文档、解析、切块和索引的共享契约
    chat_history.py               聊天持久化输入契约
    text2sql.py                    SQL 消息、SQLQueryResult 和可视化响应
  persistence/
    db/
      registry.py                 ORM 模型注册，保证关系两端均可解析
      session.py                  引擎、会话工厂与请求会话
      access.py                   SQL 执行及连接、游标生命周期
      schema_introspector.py      物理数据库元数据同步
      init_db.py                  建表和显式示例数据初始化
    crud/
      base.py                     共有持久化操作与提交、回滚
      db_connection.py            连接记录与关联数据删除
      schema_metadata.py          表、列、关系、值映射的查询和写入
      chat_history.py             聊天记录持久化
  knowledge/
    document_processor.py         MinerU / LlamaIndex 等文档解析处理
    document_workspace.py         文档预览、切块和索引工作区
                                  其余解析、索引和检索模块按现有职责保留
  agents/                         Agent、处理链、DSL 和运行框架
  core/                           认证、日志、模型客户端
  utils/lifecycle.py              有界异步资源清理
scripts/                          运维命令，使用 python -m scripts.<模块>
examples/                         可选演示
  r2r/                            外部 R2R 源码参考，独立于应用运行依赖
tests/                            自动化测试与测试数据
```

## 合并与保留

- 数据库的五个 ORM 小模块合并为 `models/database.py`；五个创建、更新模型模块合并为 `schemas/database.py`；四个元数据 CRUD 模块合并为 `persistence/crud/schema_metadata.py`。一次元数据维护可以在对应职责模块中直接阅读。
- `models/base.py` 只提供 ORM 基类，政策数据位于 `models/policy.py`，读取政策契约不应连带加载 SQLAlchemy。
- 知识库路由和文档服务共同依赖的模型位于 `schemas/knowledge.py`，服务层不再从 `api/schemas.py` 反向取得处理配置。
- 连接删除涉及关联数据顺序和可选 Neo4j 清理，聊天持久化涉及消息顺序和会话事务，分别保留独立模块。数据库客户端、文档解析器及检索器各有独立资源或可选依赖，继续独立维护。
- 删除没有实际调用方的 `agents/models` 兼容模型包、`schemas/query.py` 中未使用的重复请求模型及聊天 CRUD 中未使用的方法。SQL 服务结果并入 `schemas/text2sql.py`，命名为 `SQLQueryResult`；其字段和缺省语义保持原契约。
- `get_by_user_sessions` 改名为 `list_active`，准确表示现有过滤行为。本次不增加用户隔离，也不把旧方法名当作已有权限保证。
- CLI 直接使用 `AgentService`，初始化和有界关闭仍由命令入口负责，删除只做转发的 `AgentOrchestratorService`。

两套 Web 入口的路由、响应结构及认证能力不同，因此分别保留。`api_server.py` 是现有前端对应的入口；`app/main.py` 提供另一套已有协议。本次不将它们互相替换。

## 命名与导入

模块、函数、参数使用 `snake_case`，类使用 `PascalCase`，固定业务常量使用 `UPPER_SNAKE_CASE`。保留 `id`、`url`、`db` 等明确缩写以及框架回调名。SQL 表名、外键、索引、API 字段、环境变量和 YAML 规则函数名属于持久化或外部协议，不按 Python 内部改名处理。

内部代码从实际定义模块显式导入；包根不再聚合加载整个应用、所有 Agent 或知识库后端。例如：

```python
from app.config.agent_config import AgentServiceConfig
from app.models.policy import FinalAnswer, PolicyDocument
from app.models.database import DBConnection
from app.persistence.crud.db_connection import db_connection
from app.schemas.text2sql import SQLQueryResult
```

原 `app.utils.config.Config` 迁移为 `AgentServiceConfig`；环境变量、YAML 字段及默认值不变。直接构造替代无额外职责的 `from_env()`；文件配置继续使用 `from_file()`。未被业务使用的旧模型名属性不再保留。没有添加旧路径转发文件，仓库外的 Python 调用方需要迁移。

CLI 先读取有效配置，再把 `model` 的名称、密钥、地址、温度、token 上限和超时应用到模型设置，最后首次构造客户端。ASGI 入口继续使用环境配置；未配置 token 上限与超时时保留 SDK 默认值。字段支持依据 [AutoGen 配置定义](https://github.com/microsoft/autogen/blob/78ac9f8507d9f7c8e3d87b4db67b57e116ade1b7/python/packages/autogen-ext/src/autogen_ext/models/openai/config/__init__.py)。

对话、澄清和 SQL 展示采用无状态模块函数；持有模型、缓存、索引或流程资源的类继续保留。消费券 `CouponDiscountType` 表示执行器的 `AMOUNT`／`PERCENT`，商户场景由 `usage_limits` 表达；档位名称与可选封顶显式声明，避免校验后丢失。

依赖下限与已有代码用法对齐：查询参数模型要求 [FastAPI 0.115.0](https://fastapi.tiangolo.com/tutorial/query-param-models/)；现有 GraphFlow／DiGraphBuilder 在 [AutoGen 0.6.0 导出](https://github.com/microsoft/autogen/blob/python-v0.6.0/python/packages/autogen-agentchat/src/autogen_agentchat/teams/__init__.py)中可用，而原声明的 0.4.0 没有这些对象。本轮仅修正声明，没有安装或升级工作区依赖。

`password_encrypted` 是已有数据库字段名，当前实现仍沿用历史的明文凭据存储契约；本次没有引入密钥或执行数据迁移，不能将该字段名理解为已完成凭据加密。

## 脚本命令迁移

在仓库根目录执行。Shell、PowerShell、批处理、Docker 入口和相关说明均迁移到模块命令；步骤顺序继续由初始化脚本表达。

| 原文件名 | 当前命令 |
| --- | --- |
| `1_create_tables.py` | `python -m scripts.create_tables` |
| `2_seed_mysql_text2sql.py` | `python -m scripts.seed_mysql_text2sql` |
| `3_init_milvus.py` | `python -m scripts.init_milvus` |
| `4_embed_documents.py` | `python -m scripts.embed_documents` |
| `5_embed_process_documents.py` | `python -m scripts.embed_process_documents` |
| `6_seed_lightrag.py` | `python -m scripts.seed_lightrag` |
| `7_sync_text2sql_schema.py` | `python -m scripts.sync_text2sql_schema` |
| `tests/data_import.py` | `python -m scripts.import_data` |
| `tests/docker_rebuild_test.py` | `python -m scripts.render_docker_report`，仅渲染历史样例 |
| `scripts/unified_cli.py` | `python -m scripts.agent_cli` |

2026-11-21 进一步整理了处理器文件名、前端目录和开发 Compose 文件。当前全项目目录与迁移表见 [项目结构与命名](PROJECT_STRUCTURE.md)。历史审查报告保留当时的文件路径；本文此前的运行验收限制描述的是 2026-11-17 那一轮整理，不代表本次验证结果。

## 验证边界

已同步现有测试中的导入、替换模块和动态装载路径，保留 ORM 元数据基线与 API、事务、资源生命周期用例，并补充不安装运行依赖时的包发现用例；本轮均未执行。

后续需要在项目支持的 Python 环境补跑测试及静态检查，并检查 ORM 映射、Pydantic 运行时类型求值和 OpenAPI。当前工作区没有后端虚拟环境或实际 `.env`，本次没有安装依赖、生成凭据、启动服务或迁移数据。

外部 R2R 参考依赖本仓库未包含的 `core`、`shared` 及其版本协议；相关示例不构成应用运行依赖或已验证的独立命令。其外部序列化协议没有在缺少对应 SDK 源码的情况下机械改写。
