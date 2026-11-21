# Python 全文件审核报告

> 当前状态：第三轮纠偏进行中。用户指出必需依赖被伪装为可选等实际漏项，因此撤回下文第二轮“适用强制项已清零”的当前合规结论。以下统计与验证仅证明第二轮对应源码快照；第三轮修正及证据见 [整改计划](round3/plan.md)。

审核日期：2026-11-15。依据：`python-coding-guidelines` 的 87 条规则；代码基线：`034a6614d16070c5a875d162b876c60f83bfa2c8`。本报告以第二轮当前源码及验证为准。

按最终要求使用 **2 个子智能体**，主代理承担运行时、跨分区复核和统一验证。**208/208 个 Python 文件已完成全文二审，适用的强制项未解决数为 0**：199 个原文件中修正 133 个、审核保留 66 个；新增 8 个回归测试文件和 1 个共用生命周期工具。逐文件审核记录、当前源码和最终验证输入的哈希完全匹配，无遗漏、重复或额外记录。

此结论包含按实际框架协议保留并说明的写法，不代表所有推荐项都必须采用同一种实现，也不代表真实外部服务已完成集成验证。

## 范围与逐文件证据

范围包含项目入口、包导出、业务模块、脚本、示例、种子脚本和测试。排除第三方依赖、虚拟环境、缓存与 `temp/` 内的运行副本，完整排除项见清单。

- [第二轮整改计划](compliance-plan.md)：先建立行为保护，再修正与复核；[首轮计划](plan.md) 保留历史。
- [原始 199 文件清单](inventory.json)：原文件归属、基线与排除项。
- [最终 208 文件覆盖记录](coverage.json)：每个文件的全文范围、当前 SHA256、二轮结论、所属报告；同时绑定七份报告的原始字节 SHA256。
- [修改及新增的 Python 文件清单](changed-files.txt)：133 个原文件与 9 个新文件。
- [当前验证元数据](round2/metadata.json)：真实命令、退出码、耗时、输入与检查后源码哈希、配置哈希和依赖声明补验。
- [覆盖核对](round2/coverage-check.txt)、[交付一致性检查](round2/handoff-check.json)：覆盖数量、源码、报告和配置之间的一致性。
- [根分区独立交叉复核](round2/root-cross-review.md)：取消、初始化竞态、日志堆栈等问题的独立复现及修正证据。

逐文件报告记录适用规则、问题位置、影响、最小改法、职责与合并判断、验证和保留原因。未修改的文件同样有全文记录，二轮结论绑定当前文件哈希。

| 分区 | 原文件 | 新文件 | 全文记录 |
| --- | ---: | ---: | --- |
| API、配置、核心工具、领域与入口 | 29 | 2 | [31 条](reviews/api_config.json) |
| ORM、schema、持久化与 ChatDB | 49 | 1 | [50 条](reviews/persistence_chatdb.json) |
| Agent framework、service、domain 与 models | 36 | 1 | [37 条](reviews/runtime.json) |
| 脚本、示例、种子脚本与原有测试 | 24 | 1 | [25 条](reviews/tooling.json) |
| Agent packs 与 DSL | 39 | 1 | [40 条](reviews/packs_dsl.json) |
| 知识模块与 Agent pipeline | 22 | 1 | [23 条](reviews/knowledge_pipeline.json) |
| 集成与监控回归测试 | 0 | 2 | [2 条](reviews/integration.json) |
| 合计 | 199 | 9 | 208 |

## 主要修正与简化

- 明确 Pydantic v2、查询结果、模型事件与工具数据契约；区分 `None`、`0`、`False` 和合法空集合，移除掩盖必需字段缺失、虚构评分或金融参数的兜底。显式业务模板预设继续保留。
- 使用 SQLAlchemy 2 的原生 `Mapped` 描述 ORM，解决首轮 69 项类型诊断。八张表的元数据及 SQLite/MySQL/PostgreSQL DDL 契约保持一致，没有执行迁移。
- 将 DBAccess 从 738 行简化到 271 行，保留八种方言与公开入口；删除盲目 SQL 重放，明确事务、连接、游标及失败边界。数据库 Session 的创建、使用和关闭归属同一工作线程，DuckDB 保留原连接的临时表及初始化状态。
- 简化重复的流式处理和最终保存路径，保留真实查询计数；历史消息先于当前问题，工具只执行一次，附件、引用、指标和上下文按请求/任务隔离。
- 修复共享 Agent 状态并发、会话保存原子性、后台任务异常和取消统计；日志保留实际 traceback，失败不再被包装成正常空结果。
- 补齐客户端、上传、文件、子进程与索引资源所有权；阻塞工作移出事件循环。共用 `close_with_timeout` 在原任务内执行有界协作式清理，覆盖流上下文、已取消调用方及注册中心启动清理前的取消窗口。
- 修复知识服务并发初始化、调用方取消后的资源收回、关闭期间禁止发布已关闭服务等竞态。API 生命周期用 AsyncExitStack 释放已获取资源。
- 将不受限 eval 改为有限 AST；规则执行使用沙箱与 StrictUndefined。普通 Jinja 的 YAML/DSL 生成器继续使用可信本地模板，不能将其误称为沙箱。
- 对齐真实 AutoGen、检索、reranker、MinerU multipart/预签名上传等协议；修复 ZIP 路径穿越、HTTP/文件/进程关闭及认证会话隔离。企业示例采用当前 AgentChat 角色；外部 R2R 契约不以假模块代替。
- 保留有真实职责的包导出、模块和框架方法，没有为减少文件数删除业务职责或新增兼容框架。

依赖声明也已整理：删除标准库 asyncio，去重 FastAPI/Pydantic/Uvicorn，补齐源码已经使用的直接依赖，将 pytest 等检查工具分组到 [requirements-dev.txt](../../requirements-dev.txt)。[requirements.txt](../../requirements.txt) 中 AnyIO 下限为 4.1，以匹配 `abandon_on_cancel` 参数；当前安装版本 4.11 未改变。本次没有安装包或引入新的功能依赖。

## 当前验证

环境：Windows、Anaconda Python 3.11.7，启用 `python -X utf8`。所有验证期间 Python 源码保持不变，之后交付核对再次比较哈希。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| pytest 离线回归 | **279 项通过**，测试输出 8.34 秒 | [pytest.txt](round2/pytest.txt) |
| mypy，含未注解函数体 | **208 个文件，0 错误** | [mypy.txt](round2/mypy.txt) |
| Ruff E4/E7/E9/F/B/ASYNC | FastAPI 声明配置后 **0 项**；原始结果 28 项 B008 | [配置结果](round2/ruff-fastapi.json)、[原始结果](round2/ruff-raw.json) |
| 编译及 Python 3.10 语法 | **208 个文件全部通过** | [compile.txt](round2/compile.txt) |
| 真实导入与 OpenAPI | api_server：24 路径/40 schema；app.main：4 路径/9 schema；引用全部可解析 | [imports.txt](round2/imports.txt) |
| Bandit | **HIGH 3、MEDIUM 6、LOW 466**，退出码 1；475 条均已逐条复核 | [原始输出](round2/bandit.txt)、[解析 JSON](round2/bandit.json)、[逐条复核](round2/static-review.json) |
| 范围内 git diff --check | 通过 | [diff-check.txt](round2/diff-check.txt) |
| AnyIO 版本声明补验 | 源码未变；语法、编译和 requirements 解析再次通过 | [补验结果](round2/requirements-followup.txt)、[版本依据](round2/anyio-version-contract.txt) |

pytest 实际命令：`python -X utf8 -m pytest -m "not slow and not requires_network" --maxfail=1 -q`。八个回归文件覆盖 API/配置 32、持久化/ChatDB 36、知识/pipeline 56、packs/DSL 58、runtime 51、监控 12、tooling 26、集成 8 项。部分回归隔离外部依赖或抽取固定项目 AST，真实导入另行验证，并禁止 TCP 连接及关闭共享模型客户端。

mypy 实际参数包含 `--explicit-package-bases --follow-imports=silent --ignore-missing-imports --disable-error-code import-untyped --check-untyped-defs`。第三方缺失 stub/未注解导入属于已声明边界，没有用整文件忽略或 cast 隐藏业务函数体错误。

Ruff 的 28 项原始 B008 均是 FastAPI Depends/File 声明；只对这两个具体声明函数配置 `extend-immutable-calls`。`examples/research.py` 为保留外部公开工具的 timeout 参数，在声明处精确说明 ASYNC109 例外，实际子进程等待有 asyncio.wait_for 预算，没有整类屏蔽。

Bandit 的三项 HIGH 来自可信本地 YAML/DSL 生成器关闭 HTML 转义；六项 MEDIUM 为两处本地 FAISS pickle、固定本地 GraphML 解析、两处显式全接口监听和一项执行固定项目 AST 的测试。LOW 中 423 项为 pytest assert，其他包括示例随机数、测试凭据、导入及可选日志美化分支。扫描没有内部错误，但扫描退出码仍为 1，不能将上下文复核表述为安全扫描零告警。

首轮 [final/](final/) 是历史证据，包含 207 文件、182 测试及当时未解决的 69 项 mypy 诊断，不代表当前结论。第二轮首次统一验证的失败原文保留在 [round2/attempt1/](round2/attempt1/)；修正后才产生本轮通过结果。最初基线保留在 [baseline/](baseline/)。

## 保留边界与风险

- 未调用真实 DB、Milvus、Neo4j、Redis、LLM、MinerU、OCR、SMTP 等业务服务；离线通过不能证明生产配置、权限与端到端集成可用。
- Python 3.10 只做语法兼容检查；行为测试实际运行于 Python 3.11.7。
- 内存桥接当前为本地、非持久化模式；Redis ping 仅是连通性检查。旧 Core/GroupChat 路径需显式注册或注入受支持实现，当前主路径为现代 AgentChatTeam。既有缓存容量/TTL 产品策略没有扩展。
- 可选自动 LightRAG 种子导入、主答案保存后的辅助 memory 写入及 Dify 显式本地检索回退保留既有契约，失败日志保留堆栈；主保存及显式知识导入失败仍向调用方传播。
- YAML/DSL 生成模板及本地 FAISS pickle 必须可信；固定 GraphML 若改为接收外部 XML，需要重新验证输入边界。有界清理依赖协作式取消，不能强制中止阻塞线程或不遵守取消协议的第三方资源。
- 可选 LlamaIndex Milvus 插件与外部 R2R core/shared 环境未做真实集成；AST 隔离回归不构成其可用性证明。
- 仓库不存在 `scripts/check_config.py` 和 `scripts/check_mineru_config.py`，未声称执行这两项约定检查。

本次变更尚未提交、推送、部署或执行数据库迁移；现有服务仍运行先前副本。工作区前端改动不属于本次审核范围。
