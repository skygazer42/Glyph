# 第三轮 API 分区逐文件复核

80 个原有所有权文件逐一复核；78 个现存文件、2 个确认无消费者后删除的文件。共享 app/utils/lifecycle.py 归主代理审核，不计入本表。

| 文件 | 结果 | 具体结论 |
| --- | --- | --- |
| `api_server.py` | 复核保留 | 保留 FastAPI lifespan 顺序、AsyncExitStack 清理边界和 logging.Filter 协议；延后导入有环境/日志初始化顺序依据。 |
| `app/__init__.py` | 复核保留 | 应用工厂/实例的实际公共导出，直接显式导入；不额外包装。 |
| `app/agents/chatdb/__init__.py` | 复核保留 | 现有 agent/factory/constants 公共导出；HybridSqlGeneratorAgent 仍被配置装配引用，保留名称。 |
| `app/agents/chatdb/base.py` | 已改正 | schema 快照必需键直接读取；纯 schema/memory 转换改 staticmethod；保留默认模型/数据库、空 schema 哨兵、可选 callback 和实际缓冲状态。 |
| `app/agents/chatdb/db_service.py` | 复核保留 | ConnectionSettings 是跨线程值快照；查询拥有 DBAccess 并 finally 关闭；明确支持/不支持数据库分支，未探测对象形态。 |
| `app/agents/chatdb/domain_zh_gov.py` | 已改正 | 移除未用时间单位表；展开年/月/日、正则匹配、区域别名/标准值命名；TimeWindow 的实际 start/end 明确必需；保留未识别时间 None 和可选覆盖文件。 |
| `app/agents/chatdb/factory.py` | 已改正 | DBAccess 改必需注入；每种 agent 的注册/选型与 closure 订阅有实际框架职责，保留工厂、延迟 Hybrid 导入和 callback 初始化检查。 |
| `app/agents/chatdb/hybrid_sql_generator.py` | 已改正 | 确认无引擎装配者，移除永远 None/False 的伪生命周期及不可达示例/学习/分类方法；保留配置入口、标准生成与 examples_used=0；改正虚假检索进度提示。 |
| `app/agents/chatdb/query_analyzer.py` | 已改正 | 静态提示构造不再接收 self；保留真实交互 input_func 分支、流式最终结果校验与有界关闭；主流程按构造→消费→发布顺序可读。 |
| `app/agents/chatdb/schema_retriever.py` | 已改正 | 检索成功直接访问 tables；保留未提供 connection_id 时空 schema 的消息契约及无表提示，异常传播不伪造成功。 |
| `app/agents/chatdb/sql_executor.py` | 已改正 | 必需 DBAccess 由调用方借入；去掉未用 connection_id/清理SQL单次转发；成功/失败合流构造 SqlResultMessage；保留错误字段并记录 traceback。 |
| `app/agents/chatdb/sql_explainer.py` | 已改正 | 静态提示构造职责明确；TaskResult 最终文本与流关闭保留；解释缺失是实际失败，未以空文本继续。 |
| `app/agents/chatdb/sql_generator.py` | 已改正 | 删除无调用 _prepare_prompt 及注释掉的备用流程；静态模板方法不接收 self；保留 memory→模型→最终文本→发布的真实生成流程。 |
| `app/agents/chatdb/text2sql_service.py` | 已改正 | 删除无调用 standalone Session 兼容包装；模型生成命名明确且不重复包异常；按工作线程Session快照→模型→校验→执行编排，实际 QueryResponse 错误边界记录 traceback；文档引用的类适配保留。 |
| `app/agents/chatdb/text2sql_utils.py` | 已改正 | 删除无调用扩展表过滤/Session桥接函数；列/表/映射/SQL语句命名明确；必需 schema 字段直读；仅 SQLParseError 转校验失败，意外解析器错误继续传播；显式关键词降级有既有业务契约和日志。 |
| `app/agents/chatdb/types.py` | 复核保留 | 枚举/主题/数据库常量表达实际协议值，保留既有公共映射和默认 MySQL 语义，不合并不同协议类型。 |
| `app/agents/chatdb/visualization_recommender.py` | 已改正 | 无状态提示/任务/解析用 staticmethod；保留实际 SQL 错误、正常空结果、有效图表三分支；非法模型 JSON 明确日志后显示原始列，未编造图表轴。 |
| `app/api/__init__.py` | 复核保留 | 包标记和避免循环导入的说明，无多余转发/导出。 |
| `app/api/deps.py` | 复核保留 | 直接导入必需组件；None 表示单例未初始化/已关闭，保留锁内二次检查与关闭失败可见性；依赖函数是 FastAPI 框架入口。 |
| `app/api/endpoints/__init__.py` | 复核保留 | 路由包标记；由 api_server 显式装配，不反向导出业务组件。 |
| `app/api/endpoints/agent.py` | 已改正 | 确定 AgentService 属性直接读取；去掉两处手工 traceback 重复格式化；event/attachment/session 命名明确；会话未命中使用 is None；保留真实可选附件/用户ID/SSE分支。 |
| `app/api/endpoints/db_connections.py` | 已改正 | connections/connection 替代缩写；ORM 未命中显式 None；Session 始终关闭，响应字段直接使用已查询对象。 |
| `app/api/endpoints/dsl.py` | 已改正 | DocumentParser 保证 metadata 键，改直接访问；去掉重复 traceback；保留真实自选文件名与规则未命中/HTTP错误边界。 |
| `app/api/endpoints/knowledge.py` | 复核保留 | 复核上传/缓存/嵌入/搜索/统计各入口与 producer 契约；metadata 的 title/doc_type 真实可选，文件名和内容必需；保留同线程文件生命周期、strict zip 和现有 marker 职责。 |
| `app/api/endpoints/knowledge_graph.py` | 复核保留 | XML 节点id/边端点必需，属性/文本是真正可选字段；默认权重仅在属性缺失时用，0保留、无效值报错；文件缺失404保持。 |
| `app/api/endpoints/uploads.py` | 已改正 | 去掉 filename 重复 None/falsey 判断与 exists+is_file 重复探测；保留上传边界合法文件名、下载路径约束与可选MIME默认。 |
| `app/api/schemas.py` | 复核保留 | Pydantic 请求/响应与Query模型明确外部契约；可选请求字段和可变默认 factory 有实际用途，无内部形态探测。 |
| `app/config/__init__.py` | 复核保留 | 显式导出两组实际配置 API；不合并具有不同现有消费者的 Settings/Config。 |
| `app/config/app_config.py` | 复核保留 | 逐类复核环境别名、默认和有意义的可选服务密钥；0/False不被 or 兜底覆盖；MinerU 模式选择与 AutoGen环境属性有实际职责，保持业务配置不扩大改动。 |
| `app/config/autogen.py` | 审核后删除 | 全仓调用/导入/文档核实无消费者的旧 AutoGenConfig 常量脚手架，已删除；实际配置由 app_config.AutoGenSettings 提供。 |
| `app/core/__init__.py` | 已改正 | 删去无消费者模型注册表导出；保留实际 settings/model_client/security/logging 公共API。 |
| `app/core/auth.py` | 已改正 | 用户查询未命中显式 None；保留JWT外部边界 sub 缺失/令牌失败、实际禁用认证分支，以及expires_delta=0语义。 |
| `app/core/config.py` | 复核保留 | 共享 settings 的实际兼容导出，消费者明确，无新逻辑层。 |
| `app/core/llms.py` | 已改正 | model_settings 命名明确；必需依赖直接导入；使用配置规定的 llm_base_url，移除空URL悄悄切换服务商兜底；api_key未配置检查真实，HTTP transport所有权保留。 |
| `app/core/logging_manager.py` | 已改正 | 事件按 AutoGen kwargs 既有协议直接序列化；Formatter只捕获实际JSON解析失败；默认formatter只处理None；保留借入handler与自建handler的不同关闭责任。 |
| `app/core/model_clients.py` | 审核后删除 | 全仓核实只有包自导出的无消费者 registry/get/register/get_default，已删除；共享模型实际创建位于core.llms。 |
| `app/core/security.py` | 复核保留 | 密码哈希/核对职责及盐缺省边界明确；保留 hash 结构校验与恒定时间比较，不改认证算法。 |
| `app/domains/__init__.py` | 复核保留 | 现有领域配置/模型注册公共API使用显式导出，未引入泛化注册器。 |
| `app/domains/manager.py` | 已改正 | 真实域未命中使用None；可选prompt文件路径只读取一次，config_file命名明确；动态目录支持可选normalization/prompt来源，加载非法顶层保留原配置。 |
| `app/domains/prompt_catalog.py` | 已改正 | YAML在加载边界区分真正空文档与错误false/list；验证根和domains映射，防止伪装无提示；保留缺文件/缺domains的既有可选目录语义。 |
| `app/domains/schemas.py` | 复核保留 | 领域数据使用Pydantic，未设上限等None有明确业务说明；枚举和registry按实际领域类别公开，未自行删除业务模型。 |
| `app/main.py` | 已改正 | request替代req，用户未命中显式None；应用创建/限流开关/资源关闭按真实生命周期顺序；框架依赖和请求响应模型保留。 |
| `app/models/__init__.py` | 复核保留 | 显式导出实际共享消息/领域模型；无额外适配层。 |
| `app/models/base.py` | 已改正 | Attachment直接检查可选mime_type，无or空串中间值；字符串后缀用endswith tuple；日期校验区分None；保留消息必填字段与SQLAlchemy声明基类协议。 |
| `app/models/chat_history.py` | 复核保留 | 复核Mapped字段与真实nullable DDL、会话/消息关系和复合索引；不为类型整齐改变数据库约束。 |
| `app/models/db_connection.py` | 复核保留 | 连接字段必需、时间字段nullable与DDL一致；TYPE_CHECKING仅为关系类型循环，非运行依赖兜底。 |
| `app/models/llms.py` | 复核保留 | 实际examples和API deps仍消费的兼容导出，保留并指向唯一core.llms客户端。 |
| `app/models/schema_column.py` | 复核保留 | 列字段/主外键布尔与数据库nullable契约一致；关系命名明确，保留SQLAlchemy框架声明。 |
| `app/models/schema_relationship.py` | 复核保留 | 关系端点必需，描述/类型真实可空；显式外键关系消除源/目标歧义，未改变范围。 |
| `app/models/schema_table.py` | 复核保留 | 表与连接关系必需，描述/ui metadata真实可空；级联删除和关系保留。 |
| `app/models/value_mapping.py` | 复核保留 | 列id/自然语言值/数据库值必需；可空时间与现有DDL一致，0值/空字符串未被默认覆盖。 |
| `app/persistence/__init__.py` | 复核保留 | 持久层包导出真实db/crud模块，无通用代理。 |
| `app/persistence/crud/__init__.py` | 复核保留 | 显式仓库实例导出，与实际消费者一致。 |
| `app/persistence/crud/base.py` | 复核保留 | CRUDBase承担真实重复事务/模型映射职责；已知mapper列直接更新，保留BaseModel或字典更新的实际接口、未提供与显式None区别、提交失败回滚。 |
| `app/persistence/crud/crud_chat_history.py` | 已改正 | 会话存在分支明确is not None；其余查询/批量写入和Session事务一致，真实未命中保留Optional。 |
| `app/persistence/crud/crud_db_connection.py` | 复核保留 | 复核密码更新重命名、关联删除范围及回滚；Neo4j关闭后失败日志并继续MySQL删除是明确现有部分成功策略，非必需依赖的伪可选导入。 |
| `app/persistence/crud/crud_schema_column.py` | 复核保留 | 按table/table_ids查询责任明确；空table_ids返回空列表代表无查询范围，不放大到所有表；first真实未命中Optional。 |
| `app/persistence/crud/crud_schema_relationship.py` | 复核保留 | 按connection/source/target/columns范围查询明确；双端or_为SQL逻辑；空table_ids不越界。 |
| `app/persistence/crud/crud_schema_table.py` | 复核保留 | 按连接及表名查询，继承CRUD承担实际公共事务；ORM未命中Optional合理。 |
| `app/persistence/crud/crud_value_mapping.py` | 复核保留 | 列与术语联合过滤明确；分页/first契约稳定，不添加数据缺失兜底。 |
| `app/persistence/db/__init__.py` | 复核保留 | 空包标记，无可删业务或额外初始化。 |
| `app/persistence/db/base.py` | 复核保留 | 显式导入模型是SQLAlchemy metadata注册真实需求，保留导入副作用说明。 |
| `app/persistence/db/base_class.py` | 复核保留 | 重新导出唯一声明Base，避免双metadata的兼容边界，实际消费者明确。 |
| `app/persistence/db/dbaccess.py` | 已改正 | 已声明必需PyMySQL/SQLAlchemy导入上移；去run_sql无用kwargs；保留可选数据库驱动按选型局部直接导入、连接callback None生命周期和RLock串行资源边界。 |
| `app/persistence/db/init_db.py` | 已改正 | 删除init_db不使用的Session参数并同步唯一调用；连接未命中显式None；只审核脚本而未执行建表/种子数据。 |
| `app/persistence/db/schema_introspector.py` | 已改正 | mysql_connection/schema_table/column_info/source/target全称区分不同业务对象，去掉已是bool的重复转换；保留信息schema读取、映射先删与完整事务回滚。 |
| `app/persistence/db/session.py` | 已改正 | database_settings替代db_cfg；URL.create处理凭据编码，生成器在finally关闭Session；不提前执行连接。 |
| `app/schemas/__init__.py` | 复核保留 | 显式导出外部契约，避免星号导入和不必要动态加载。 |
| `app/schemas/chat_history.py` | 复核保留 | 创建字段必需，更新字段None配合exclude_unset表达部分更新；可变metadata未共享。 |
| `app/schemas/db_connection.py` | 复核保留 | 创建密码必需，更新密码可选且保留空密码；没有把None/空密码合并。 |
| `app/schemas/query.py` | 复核保留 | SQL/结果/错误上下文保持已有响应协议；错误None与正常空结果可区分。 |
| `app/schemas/schema_column.py` | 复核保留 | 创建与更新模型职责各异；布尔False有效，更新None不替代False；空Create子类标明真实外部契约。 |
| `app/schemas/schema_relationship.py` | 复核保留 | 关系创建端点必需，更新端点可选；不合并不同请求协议。 |
| `app/schemas/schema_table.py` | 复核保留 | 表创建/更新约束清晰；描述与UI元数据实际可选。 |
| `app/schemas/text2sql.py` | 复核保留 | Pydantic消息继承表达查询→分析→SQL→结果协议；schema空哨兵、error可选和列表factory均有实际消费者。 |
| `app/schemas/value_mapping.py` | 复核保留 | 映射创建/部分更新模型明确；nl_term/db_value字符串直接保留，不填造默认值。 |
| `app/utils/__init__.py` | 复核保留 | 实际配置公开导出，保留兼容导入路径。 |
| `app/utils/config.py` | 已改正 | Vision api_key/base_url、Tavily key改真正可选并定向在.env边界归一化空项；PyYAML直接顶层导入；保留其余业务配置、class factory以及环境属性接口。 |
| `tests/test_python_guidelines_api_config.py` | 已改正 | 在原回归上新增配置空项/真值和非法提示目录边界测试；覆盖HTTP、资源清理、线程和响应契约，不以源码字符串断言代替行为。 |
| `tests/test_python_guidelines_persistence_chatdb.py` | 已改正 | 新增解析格式错误与意外故障区别、Hybrid未装配时准确进度与SQL发布回归；原SQL安全、Session/驱动关闭、ORM/DDL及流结果用例保留。 |
