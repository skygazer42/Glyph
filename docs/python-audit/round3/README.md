# Python 全文件审核与修正

当前结果对应第三轮最终源码。此前“适用强制项全部清零”的笼统结论已撤回：用户指出的必需依赖伪可选等漏项确实存在。本轮继续修正具体问题，逐文件记录与验证共同作为证据，不以工具通过替代函数职责、命名或判空语义判断。

按要求使用 **2 个子智能体**，主代理负责运行时、跨模块复核及统一验证。当前范围 **205 个 Python 文件**（196 个原文件、9 个此前新增文件），另删除 3 个确认无消费者的旧模块。API/配置/持久化分区 78 个、脚本/解析/知识分区 88 个、主代理运行时分区 39 个；清单无遗漏或重复，审核哈希与最终验证输入、输出及当前源码一致。

## 实际改正

- 必需依赖直接导入，包括两处 `from docx import Document`，不再把 ImportError 转成 Optional Callable/None 或安装标志。显式选择的独立插件在使用边界直接导入，缺失直接失败；未新增功能依赖或安装包。
- 必填意图、模型事件、schema、文档和检索评分直接读取；删除伪标题、零分、空对象以及已确定模型名/维数的重复兜底。配置无效时明确失败，合法 0/False/空集合与未提供值分别处理。
- 依实际生产者修正多轮改写历史契约：AutoGen memory 提供带用户/助手前缀的字符串列表，改写器不再错误地按字典读取。回归使用真实记忆写入后的历史。
- 改正表达不清的计时、解析、检索和懒建函数名称；删除无职责转发、闲置参数、恒空状态及未装配 Hybrid 引擎的不可达脚手架。保留实际公开接口与标准 SQL 生成，未编造混合检索能力。
- 工具错误记录指标后重新抛出；显式启用但缺配置立即失败。Dify 只对真实请求异常采用已有本地检索回退，坏响应与字段错误保持可见。选定解析器、图组件或层级索引失败不再静默换后端。
- 删除无消费者的 `app/config/autogen.py`、`app/core/model_clients.py`、`app/agents/service/memory.py`。真实模型配置、共享模型客户端和主路径 AutoGen memory 保留。

真实可选配置、查询未命中、解析无文本、未匹配 FAQ、未创建/已关闭资源、流式工具字段尚未到达等仍有必要判空；具体保留原因写在分区记录中，没有把所有 None 或 `.get` 机械替换。

## 当前证据

| 范围 | 逐文件结论与当前源码哈希 |
| --- | --- |
| API / 配置 / 核心 / 领域 / ORM / 持久化 / ChatDB | [说明](round3/api-review.md)、[逐文件结论](round3/api/file-review.md)、[清单](round3/api/source-manifest.json) |
| 脚本 / 示例 / packs / DSL / 知识 / pipeline | [说明和逐文件结论](round3/tooling-review.md)、[清单](round3/tooling-files.json)、[分区验证](round3/tooling-verification.json) |
| framework / service / runtime / 集成与监控测试 | [说明](round3/root-review.md)、[清单](round3/root-files.json)、[最终只读交叉复核](round3/root-final-cross-review.md) |
| 全部文件 | [205 文件覆盖表](coverage.json)、[覆盖核对](round3/coverage-check.json)、[相对基线变更](changed-files.txt)、[本轮变更](round3/changed-since-round2.txt) |

执行依据为 [python-coding-guidelines](C:/Users/luke/.codex/skills/python-coding-guidelines/SKILL.md)，清理前写 [本轮计划](round3/plan.md)，先运行既有回归，再为真实行为变化补充覆盖。全部范围包含入口、业务、包导出、脚本、示例、种子和测试；排除第三方依赖、环境、缓存和 `temp/` 运行副本，精确排除项见覆盖表。

## 统一验证

Windows、Python 3.11.7，源码与配置在检查前后保持不变。真实命令、退出码、耗时及哈希见 [metadata.json](round3/metadata.json)。

| 检查 | 实际结果 |
| --- | --- |
| pytest 离线回归 | **332 passed in 8.32s**，见 [pytest.txt](round3/pytest.txt) |
| mypy（含未注解函数体） | **205 文件无错误**，见 [mypy.txt](round3/mypy.txt) |
| Ruff E4/E7/E9/F/B/ASYNC | 配置 FastAPI Depends/File 声明后 **0 项**；原始 28 项均为 B008，见 [配置结果](round3/ruff-fastapi.json)、[原始结果](round3/ruff-raw.json) |
| compile 与 Python 3.10 语法 | **205 文件通过**，见 [compile.txt](round3/compile.txt) |
| 真实入口导入 / OpenAPI | api_server 24 路径/40 schema，app.main 4 路径/9 schema，引用均可解析；禁止 TCP 连接且关闭共享模型客户端，见 [imports.txt](round3/imports.txt) |
| Bandit | **HIGH 3 / MEDIUM 6 / LOW 490**，退出码仍为 1；见 [原始输出](round3/bandit.txt)、[逐条上下文复核](round3/static-review.json) |
| 范围内 git diff --check | 通过，见 [diff-check.txt](round3/diff-check.txt) |

pytest 命令：`python -X utf8 -m pytest -m "not slow and not requires_network" --maxfail=1 -q`。mypy 使用 `--explicit-package-bases --follow-imports=silent --ignore-missing-imports --disable-error-code import-untyped --check-untyped-defs`，第三方缺失 stub 属于明确边界，没有把业务函数体整文件忽略。Ruff 仅配置两种真实 FastAPI 声明；research 示例保留已发布 timeout 参数的精确 ASYNC109 说明及真实等待预算。

Bandit 结果有 440 条测试 assert、9 条内部已建立状态的 assert，不能混称全为测试断言。HIGH 来自可信本地 YAML/DSL 模板关闭 HTML 转义；MEDIUM 包括本地 FAISS pickle、固定 GraphML、服务监听和测试 AST。保留这些边界不代表零安全告警或验证了生产网络配置。pytest 断言通过且退出 0，第三方 ascii_colors 在进程结束时仍输出关闭日志流告警，原文见 [stderr](round3/pytest.stderr.txt)。

## 保留限制

- 未调用真实 DB、Milvus、Neo4j、Redis、LLM、MinerU、OCR、SMTP 等业务服务；离线测试和导入检查不证明真实端到端集成可用。
- Python 3.10 仅检查语法，行为运行于 Python 3.11.7。部分外部插件/示例使用隔离 AST 回归，不能据此声称外部环境可运行。
- 本地 memory bridge 非持久化；Redis ping 仅连通性。旧 Core/GroupChat 需显式注入受支持 agent；主路径使用现代 AgentChat。既有业务后备和辅助写入策略保留并记录错误。
- 本地模板、pickle、GraphML 的信任来源必须保持；协作式有界清理不能强制中止不响应取消的线程或第三方资源。
- 仓库不存在约定的 `scripts/check_config.py` 和 `scripts/check_mineru_config.py`，没有声称执行。未提交、推送、部署、迁移或重启现有服务，前端既有改动不属于本次操作。

原始 [inventory.json](inventory.json)、[reviews/](reviews/)、[baseline/](baseline/)、[final/](final/) 与 [round2/](round2/) 保留为历史证据。第二轮覆盖表、变更清单及撤回前报告已保存在该历史目录，不能用于代表当前源码或继续引用其“全部清零”结论。
