# Tooling round 4 review

本组已完成 88 个 Python 文件的逐文件审核，合计 23,976 行。完整清单、初读范围与哈希、最终源码哈希、规则编号/级别/实际位置、修正及保留理由见 [tooling-files.json](tooling-files.json)。88 条路径与 round3 分工完全一致，55 个文件记录了 104 项已处理规则问题，其余文件也均有具体审核观察。最终源码已经停止写入，`source_frozen=true`；最终 202 文件的统一验证由 root 执行。

本组只处理分工内 Python 与获明确授权的 3 个 Jinja 模板；没有安装依赖、新建 Python 模块、提交、部署、迁移或执行业务数据库操作。先完成全文初读，332 项基线通过后才修改 Python；影响行为的修正先以真实方法/模型回归验证旧错误，而非断言源码写法。最后新增的 LlamaIndex 源码及知识测试模块又完整复读，Milvus 最终交接源码及追加回归也已复核。所有最终哈希重新计算，规则级别与 Skill 原文核对一致，规则位置没有越界。

## 关键改正

- **DAT-001/004、PYD-001（强制）**：DSL 的 `dsl_extractor.py`、`dsl_runtime_helpers.py`、`template_registry.py`、`rule_engine.py` 及 3 个模板只消费实际政策事实，去掉虚构费率、金额、起止日、30 天期限、预算和限额；未声明限额明确为不受限。实际零值、空集合与 `None` 分开处理，坏日期/非有限金额保持失败可见。模板选择保持调用局部，缺模板或输出表达式错误不再被修补为成功。
- **PYD-001、ERR-001（强制）**：FAQ、MinerU、rerank、planner、实体数组、意图/问题/政策审查响应使用实际 Pydantic 边界；坏类型、非有限分数、缺必填字段不再转成空字符串、零置信度或普通成功。回答/图摘要为空、所选模型调用失败及解码穷尽均按真实失败处理。
- **DAT-003/009、RES-001（强制）**：Milvus 的关闭状态与假值 SDK 对象分开处理，连接只释放自有 alias；DashScope 响应要求非空有限数字、单文本恰好一向量且维数匹配。显式空账号/口令不被配置覆盖，非法非正维度明确报错；已知 OpenAI 原生维数、DashScope 有依据的正维数/1024 默认保留。FAISS 的索引和元数据必须成对存在；OCR 自建 PIL/PDF 图片释放。
- **DAT-004（强制）**：`llamaindex_hybrid_retrieval.py:174`、`:194` 两个后端在配置 LLM key 时拒绝空白模型名，删除 `qwen-turbo`/`gpt-4` 的虚构备用模型；真实自定义模型原样传 SDK。未配置 key 时仍保留 LLM 可选行为，key/base URL 查找规则保持实际契约。
- **DES-001（强制）及真实包入口规则**：核对调用后移除无效果的引用包装及 5 个调用、未用地区推断、重复图片提取器、未消费参数/状态/事件、不可达分支及没有迁移调用者的旧类别名；最终删除 `policy_analysis/prompt.py` 两个无消费者的 full-analysis 提示。配置、模型、领域和日志内部依赖指向定义模块。`workflow_agent.py` 在负责错误转换的边界保留 traceback。

## 保留理由

Jinja 注册/渲染、抽取、运行时和规则执行仍分别承担不同契约；知识检索器、文档解析、OCR、Milvus 与可选宿主有各自资源/SDK边界，没有仅为减少文件数合并。真实框架回调及公共入口保持实际协议。重写的 best-effort、明确的规则后备、可选 NLP/元数据/图片尺寸/二维码增强按文件中的具体边界保留，增强失败留 traceback；不会将选定的必需能力失败伪装为成功。演示/CLI 的简短 f-string 日志属于 LOG-003 推荐项，实际没有昂贵表达式或敏感配置，不作纯格式的大范围改写。

## 已执行证据

| 阶段 | 实际结果 | 证据 |
| --- | --- | --- |
| 组内稳定检查点 | 3 模块 275 passed；Ruff 通过；mypy 88 文件通过；Python 3.10 AST、当前编译及 scoped diff 通过 | [pytest](tooling-pytest-final.txt)、[Ruff](tooling-ruff-final.txt)、[mypy](tooling-mypy-final.txt)、[编译/diff](tooling-compile-diff-final.txt) |
| Milvus 响应契约 | 首批 NaN/字符串/空向量 3 项旧实现均失败；追加契约红测与绿测已留存 | [首批红](tooling-milvus-red.txt)、[追加红](milvus-extra-red.txt)、[绿](milvus-green.txt) |
| Milvus 最终配置交接 | 追加 17 项旧实现 9 failed/8 passed，修后 Milvus 子集 34 passed/77 deselected；API 交接两文件静态检查通过 | [红](glyph-round4-milvus-config-red.txt)、[绿](glyph-round4-milvus-config-green.txt) |
| LlamaIndex 最终修正 | 8 项旧实现 4 failed/4 passed；修后 8 项及真实 markdown 路径回归共 9 passed/110 deselected | [红](tooling-llama-config-red.txt)、[绿](tooling-llama-config-green.txt) |
| 最终触及文件静态检查 | LlamaIndex/知识测试 Ruff 和 mypy 2 文件通过；另含提示文件的 3 文件 Python 3.10 AST/编译/diff 通过 | [Ruff/mypy](tooling-llama-config-static.txt)、[语法/diff](tooling-llama-config-syntax.txt) |

275 项是最后 Milvus 追加和 LlamaIndex/无用提示清理前的组内检查点，不冒充最终全仓结果。依 root 要求不重复整组测试，最终统一检查以 root 的证据为准。

## 限制与兼容影响

离线 AST 定义隔离运行了真实方法及模型，不能证明所有应用导入和 SDK 集成；R2R 示例所依赖的外部 `core/shared` 宿主不在本仓库。未调用 live LLM、MinerU、Milvus、OCR 或 MySQL 业务集成。更严格的边界会拒绝过去被默认值掩盖的畸形 JSON/政策数据及空模型配置；无迁移消费者的旧别名和无用参数已删除。历史 275 绿测退出码为 0，但第三方 `ascii_colors.ConsoleHandler` 在解释器退出时报告 closed-stream flush `ValueError`，原始 stderr 已保留；未用无关 monkeypatch 隐藏。最近 9 项定向绿测 stderr 为空。
