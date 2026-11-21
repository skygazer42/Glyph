# Round 4 Bandit 告警上下文复核

本次复核覆盖原始 `bandit.txt` 中除测试 B101 断言外的全部 **60 项告警：9 项内部断言 + 51 项非断言告警**，涉及 21 个文件。逐项读取告警所在函数及必要调用入口，并将全部 60 项 `code` 片段逐行与当前源码核对，位置和内容一致。没有修改 Python 源码，没有运行反序列化攻击载荷、外部服务、种子数据或部署操作。

最终扫描生成时间为 `2026-11-15T00:34:12Z`，扫描错误为 0；首次快照的生成时间为 `2026-11-15T00:31:50Z`。两次告警位置和上下文一致。扫描器原有告警等级保持不变；“上下文已复核、保留边界”不表示告警消失、安全风险已解决或完成部署安全验证。

## 实际计数

| 统计项 | 数量 |
| --- | ---: |
| 原始全部告警 | 603 |
| HIGH / MEDIUM / LOW | 3 / 6 / 594 |
| B101 总数 | 552 |
| `tests/` 下的 B101，未重复逐项复核 | 543 |
| 生产/脚本内部 B101，本次逐项复核 | 9 |
| 非 B101，本次逐项复核 | 51 |
| 本次复核总数 | 60 |

按路径统计，生产/脚本文件有 38 项，`tests/` 下有 565 项。路径分类不等于功能分类：`tests/data_import.py` 是会操作外部数据库的开发工具，不能因为目录名就视为无副作用的单元测试。

| 规则 | 原始等级 | 数量 | 上下文结论 |
| --- | --- | ---: | --- |
| B701 | HIGH | 3 | 输出 YAML/DSL，HTML 自动转义不适用；普通 Jinja 的本地模板信任边界仍存在。 |
| B301 | MEDIUM | 2 | 实际 `pickle.load`，仅限可信本地持久化文件；没有把反序列化风险判为已消除。 |
| B104 | MEDIUM | 2 | 入口实际监听所有网卡，网络及认证边界仍需部署方约束。 |
| B314 | MEDIUM | 1 | HTTP 入口使用固定本地 GraphML 路径，XML 文件可信及资源大小边界仍保留。 |
| B102 | MEDIUM | 1 | 离线测试助手执行固定项目文件抽取的 AST，不是生产 API 执行外部 Python。 |
| B403 | LOW | 2 | 与上述两处实际 pickle 读取一并复核，不是独立修复证明。 |
| B405 | LOW | 1 | 与 GraphML 的 ElementTree 解析一并复核。 |
| B311 | LOW | 17 | 问候语选择或演示数据随机化，不生成令牌、密码或其他安全材料。 |
| B105 / B106 | LOW | 10 / 10 | 19 项为离线测试假凭据，1 项为显式运行的本地样例数据库凭据。 |
| B404 | LOW | 2 | subprocess 导入用于开发导入工具或离线测试；导入本身不证明命令注入。 |
| B101，非测试 | LOW | 9 | 已成立的构造、分支或重试不变量，不承担用户输入或授权校验。 |

## HIGH / MEDIUM 的实际边界

- `app/agents/dsl_generator/dsl_generator.py:92`、`:99` 和 `app/agents/dsl_generator/dsl_generator_domain.py:55`：三处环境用于生成 YAML。前者仅编译源码内置的 `DSL_TEMPLATE` 或加载构造时指定目录的模板；生产依赖在 `app/api/deps.py:49` 固定为 `templates`。后者按源码中的领域配置获取本地模板路径，再将数据交给 `render`。没有发现把请求数据本身当作 Jinja 模板源码再次编译的路径，因此 B701 的 HTML 转义风险不直接对应此输出类型。**普通 Environment 仍不是不可信模板沙箱**；若模板目录或当前工作目录可被攻击者写入，存在执行恶意模板的风险。普通变量值不会因此自动变成安全 YAML 序列化；本次没有把 HTML 转义设置当作 YAML 注入防护证明。
- `app/agents/framework/common/embedding_manager.py:51`、`app/agents/packs/vector_retriever/node.py:95`：实际使用 `pickle.load`，读取同一对象持久化的本地索引元数据，路径也可由 Python 构造参数指定。代码没有验证文件签名、真实性或写入者身份。**攻击者能够替换元数据文件时，pickle 可以执行任意代码**；“文件位于本地”不能单独消除该风险。没有确认请求可直接指定这两个读取路径或写入原始 pickle 字节，但也没有验证部署文件权限、挂载目录或制品供应链。需要保持可信本地文件前提；把这些记录统称为误报或已解决不准确。
- `api_server.py:113`、`app/main.py:220`：两入口的 `0.0.0.0` 是真实监听配置，不是未运行示例字符串。前者的 FastAPI/路由装配没有全局认证依赖，GraphML 路由也没有声明认证依赖；CORS 的 localhost 来源限制不等于客户端认证。后者包含具体认证依赖，但本次没有验证其实际配置或部署入口。网络可达性、反向代理、访问控制和防火墙均未实测，故 B104 应保留网络暴露风险，不能写成安全消除。此复核没有扩展为新增认证或部署功能。
- `app/api/endpoints/knowledge_graph.py:94`：两个 HTTP 处理函数将固定路径 `resources/data/lightrag/graph_chunk_entity_relation.graphml` 交给 `ET.parse`，请求没有接收任意文件路径或原始 XML。此函数读取完整 XML，未设置文件大小或应用级解析资源上限。固定路径不保证内容可信；被篡改或异常庞大的本地文件仍可能导致解析错误或资源耗尽。没有确认远程 XML 注入路径，也没有将标准库解析器判为可安全接受任意不可信 XML。
- `tests/test_python_guidelines_tooling.py:72`：助手从项目根目录下的源码解析 AST，抽取测试指定定义和 Pydantic/typing 导入，再执行编译结果。调用者为离线测试，已读调用处使用固定项目文件；不是生产服务接收用户提供的代码。可信仓库源码仍会执行其装饰器、默认值和所选定义，不能把这个测试助手解释成 Python 沙箱。

## 其余 51 项非断言告警的逐组定位

HIGH/MEDIUM 共 9 项已在上节逐项解释；以下列出其余 LOW 的实际位置，合计仍为 51 项非断言告警。

| 规则与位置 | 具体判断 |
| --- | --- |
| B403：`app/agents/framework/common/embedding_manager.py:10`、`app/agents/packs/vector_retriever/node.py:10` | 两个 pickle 导入确有对应反序列化调用；与 B301 同一个可信文件边界，不能用“只是导入”掩盖调用风险。 |
| B405：`app/api/endpoints/knowledge_graph.py:7` | ElementTree 导入确有本地 GraphML 解析用途；风险见 B314。 |
| B311：`app/agents/packs/chat_agent/node.py:106`、`app/agents/pipeline/dialog_agent.py:32` | 从预置回复列表选择文字，无认证或授权职责。 |
| B311：`scripts/2_seed_mysql_text2sql.py:113`、`:114`、`:115`、`:133`、`:146`、`:164`、`:165`、`:168`、`:181`、`:198`、`:199`、`:207`、`:208`、`:221`、`:228` | 生成演示日期、分类、机构、金额、问题、难度、标签及权重；没有将这些随机值作为安全凭据。 |
| B106：`app/persistence/db/init_db.py:29` | `create_initial_data` 创建固定名称的本地样例连接，用户名为 root、密码为公开演示值。仓内只在 `__main__` 路径显式调用，导入模块不会执行这次数据写入。**它仍是弱样例凭据，显式运行会写入真实数据库，不能用于生产连接。** 本次未运行。 |
| B106：`tests/test_python_guidelines_api_config.py:59`、`tests/test_python_guidelines_knowledge_pipeline.py:979` | 分别为本地 JWT 行为回归及 Milvus 参数转发替身，值为测试构造的假凭据，无真实网络服务。 |
| B106：`tests/test_python_guidelines_persistence_chatdb.py:86`、`:109`、`:120`、`:248`、`:568`、`:576` | 驱动替身或 SQLite/连接参数快照，覆盖空密码、传参及线程所有权，不使用生产秘密。 |
| B106：`tests/test_python_guidelines_runtime_monitoring.py:19` | 注入测试共享密钥，运行于模块替身与临时目录。 |
| B105：`tests/test_python_guidelines_persistence_chatdb.py:262`、`:264`、`:265`、`:553`、`:610` | 空密码行为及断言；部分同一位置也触发 B101，告警数不等于独立缺陷数。 |
| B105：`tests/test_python_guidelines_runtime_monitoring.py:111`、`:178`、`:180`、`:204` | 假 SMTP 密码、密钥覆盖和 token 脱敏回归；SMTP 构造在相关测试中被替换，不发送真实邮件。 |
| B105：`tests/test_python_guidelines_tooling.py:183` | 假 MySQL 密码用于验证子进程参数和错误文本不泄露秘密，进程构造被测试替身截获。 |
| B404：`tests/data_import.py:8`、`tests/test_python_guidelines_tooling.py:7` | 前者使用 `asyncio.create_subprocess_exec` 的参数数组，不拼接 shell；超时、取消、退出码、子进程及临时目录清理已有离线回归。后者使用异常类型和测试替身。开发导入工具仍具有写入/重建外部数据的业务副作用，本次没有执行它。 |

## 9 项内部 assert 与分类理由校对

| 位置 | 已建立的不变量 |
| --- | --- |
| `app/agents/framework/core/agent_registry.py:128` | 有实例时先调用 `get_running_loop`，无有效循环会在修改索引前失败。后续断言只是类型收窄；不是用户输入检查。 |
| `app/agents/packs/graph_retriever/node.py:194`、`:236` | 两条重试路径都至少执行一次；成功会 return/break，走完失败路径时已经保存原异常。删除断言不会把失败转成成功。 |
| `app/agents/service/agent_service.py:565`、`:592`、`:728`、`:750`、`:1640` | 成功完成构造的实例在启用分支已装配对应 backend；构造失败不发布实例。stream 路径在两类 backend 均未启用时提前返回。断言不负责输入或授权校验。 |
| `scripts/5_embed_process_documents.py:83` | 非 dry-run 分支在进入批次处理前构造 KnowledgeService；dry-run 分支不会调用索引服务。 |

发现并已上报的理由修正：原 `static_review.py` 将 AgentService 写成“启用标志仅在实际 backend 构造成功后建立”。源码实际先设置启用标志，再在构造函数分支装配 backend；应以“成功完成构造的实例”描述其不变量。主代理已采纳、更新生成器并重新生成 `static-review.json`，本区核对五项理由均使用修正文案，60 项路径/行号/规则集合与原扫描一致。该措辞修正不代表发现新的运行错误。

## 结论与范围限制

除上述 AgentService 理由措辞外，分类理由与已读代码的用途、入口及边界一致。复核未确认普通请求能够直接控制 pickle 文件、Jinja 模板源码或 GraphML 原始 XML，也没有通过攻击测试或部署实测证明不存在这些路径。

仍未解决的实际风险包括：pickle 文件被替换后反序列化执行代码；不可信本地 Jinja 模板执行；本地 GraphML 篡改或超大文件的资源风险；全网卡监听及未验证的网络/认证边界；显式初始化后残留弱样例数据库凭据。它们是需要维持或另行收紧的边界，不能从本轮 Python 写法审核与上下文分类推导为安全已解决。本报告只增加独立复核说明，不修改源码、原始扫描输出或主代理的分类证据。
