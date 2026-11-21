# 第四轮主代理逐文件核对

全文阅读后记录；行号以该记录阅读时版本为准，最终清单另保存当前源码哈希。规则级别按 Skill 原文。未涉及的 Web、数据库、HTTP 等章节按文件职责不适用，不把推荐项或参考项升级为强制要求。

| 文件 | 具体规则对照、位置与处理 |
| --- | --- |
| app/agents/__init__.py | NAM-003强制、DES-006推荐：1–5为真实framework/packs入口；无请求或资源处理，保留包边界。 |
| app/agents/domain/__init__.py | NAM-003强制、DES-006推荐：5–8显式公开PolicyDomainContext/Builder；不新增聚合层。 |
| app/agents/domain/policy_domain.py | CLS-005推荐、DAT-006强制：内部dataclass容器用factory；FUN-002推荐：build依次规范化/提取地区时间/生成变体；region/time未命中确可空，展示拼接空串有实际语义。 |
| app/agents/framework/__init__.py | DES-003推荐、DES-006推荐：1–12为不同生命周期/消息协议子包；不因短文件删除真实边界。 |
| app/agents/framework/base/__init__.py | NAM-003强制、DES-006推荐：5–15显式导出AutoGen基类及工厂；与core.AgentBase不同协议。 |
| app/agents/framework/base/base_agent.py | CLS-004推荐：RoutedAgent/ABC/装饰器为框架契约；DAT-002强制：动态_handle处理器来自真实子类能力；ERR-001强制：异常产生ERROR消息且留traceback；ASY-006/009强制：ProactiveAgent跟踪调度任务、观察异常、取消后限时等待并关闭未启动协程。 |
| app/agents/framework/base/factory.py | DAT-001强制：answer_generator必填Protocol；RES-001/ASY-009强制：factory拥有agents/vector_store，AsyncExitStack关闭，借用answer_generator不越权关闭；DES-001强制：未实现GroupChat明确报错，无假成功。 |
| app/agents/framework/base/types.py | DAT-006强制、CLS-005推荐：内部消息dataclass各自factory；NAM-003强制：PolicyDocument明确再导出；不混作外部API请求。 |
| app/agents/framework/common/__init__.py | NAM-003强制、DES-006推荐：1–7列出实际公开模块，模型客户端/会话/嵌入有不同资源职责。 |
| app/agents/framework/common/autogen_memory_store.py | NAM-003强制：redis直接导入；DAT-002强制：ListMemory不存在是懒建状态；RES-001强制：健康探测关闭Redis；FUN-002推荐：实际ListMemory非持久化Redis，不宣称持久化。 |
| app/agents/framework/common/embedding_manager.py | DAT-001强制：构造先校验backend/维度，add_documents检查输入长度；RES-001/ASY-001强制：OpenAI上下文关闭，Ollama同步入口禁止事件循环内asyncio.run；ERR-001强制：选择Ollama直接导入，缺依赖抛出；本地FAISS pickle为既有受信存储边界。 |
| app/agents/framework/common/model_client.py | DAT-002/003强制：None表示未覆盖，temperature/seed=0保留；DAT-001强制：配置列表边界校验后取首项；RES-001强制：新客户端由调用者持有；DeepSeek/Qwen的model_info是实际SDK适配。 |
| app/agents/framework/common/session_manager.py | DAT-001/006强制：DB固定字段直接读取，消息/context深拷贝；DB-002强制：未命中返回None；持久化先成功再发布内存；ASY-006/009强制：cleanup_task由start/stop拥有，线程执行同步DB清理；DAT-003强制：limit=0和timeout=0有明确分支。 |
| app/agents/framework/common/session_store.py | DAT-001/006强制：写入已有session直接索引，各会话独立容器；DAT-003强制：history=0不切[-0:]；FUN-001强制：get_context的current_query没有使用且无带参调用，移除无职责参数；NAM-001强制：sid/sess/recent改为会话及历史窗口的实际名字。 |
| app/agents/framework/coordination/__init__.py | DES-006推荐、NAM-003强制：5–9仅导出实际Coordinator，未虚称导出SessionManagerAgent。 |
| app/agents/framework/coordination/coordinator.py | FUN-002推荐：process_request依次分析/检索/答案/验证/组装；DAT-001强制：内部success/data直接读；ERR-001强制：失败标记success=False；DAT-002强制：verifier真实可选，缺失报告未验证。 |
| app/agents/framework/coordination/session_manager.py | DAT-001/ERR-001强制：本轮修正action、更新context及add_query/add_answer必需字段.get，缺字段直接失败，正常未知会话仍False；DAT-006强制：SessionContext工厂；CLS-004推荐：AutoGen方法保持async协议；ASY-006/009强制：定期任务拥有者停止等待；sources_count直接len已成立sources列表。 |
| app/agents/framework/core/agent_base.py | CLS-004推荐：ABC/process为真实子类协议；ERR-001强制：处理失败产生ERROR_MESSAGE；ASY-005强制：finally恢复状态，CancelledError传播；DAT-002强制：message_bus实际挂载前可无；_message_lock串行保护实例共享状态。 |
| app/agents/framework/core/agent_registry.py | DAT-002强制：未注册/禁用明确不创建；ASY-006/009强制：创建锁、未发布实例finally清理、注销任务由shutdown_all收集；ERR-001强制：初始化False是既有失败协议且依赖链校验，不返回成功实例；DES-002推荐：保留真实注册/索引/实例生命周期职责。 |
| app/utils/lifecycle.py | ASY-009强制：本轮补isfinite校验，拒绝inf/nan及非正值，必要清理才shield；多个真实调用者复用，无新包装层。5个边界回归先红后绿。 |
| app/agents/framework/core/__init__.py | NAM-003强制、DES-006推荐：5–18显式列出controller/base/registry/bus/orchestrator公开对象；各自有独立资源和调度职责，不按文件数盲合并。 |
| app/agents/framework/core/agent_master.py | FUN-002推荐：initialize有加载/总线/注册/实例步骤；ASY-006/009强制：stop收集创建任务并用ExitStack关闭注册中心和总线；DAT-001/ERR-001强制：本轮工作流agents/branches必填，未知type抛错，显式未知workflow不再偷偷执行默认流程；正常无结果的Optional协议保留。 |
| app/agents/framework/core/message_bus.py | ASY-003/006强制：worker由start/stop持有，gather收集handler失败/取消；RES-002强制：request的临时订阅finally撤销；DAT-002强制：recipient=None为广播、timeout正常无响应为None；同步handler必须短且非阻塞，现有注册者为async代理和即时response_handler。 |
| app/agents/framework/core/orchestrator.py | FUN-002推荐：按已选择策略调度，顺序/pipeline/conditional复用顺序实现；ASY-005/006/009强制：并行波次失败取消并等待兄弟任务，取消继续传播；ERR-001强制：必需步骤None/ERROR_MESSAGE判失败；DAT-005推荐：入口一次合并context；retry_count是明确步骤配置且默认0。 |
| app/agents/framework/models/__init__.py | DES-006推荐、NAM-003强制：5–23显式公开框架消息、任务和工作流模型；未引入新的兼容层。 |
| app/agents/framework/models/base.py | PYD-003强制、DAT-006强制：43–79已有BaseModel/Field及独立容器工厂；TaskResult.result/error代表未完成/失败，receiver实际可广播；框架内模型与HTTP响应不同契约，保持枚举和内部职责。 |
| app/agents/framework/monitoring/monitor.py | ASY-001强制：CPU采样及SMTP阻塞操作在线程；RES-001/007强制：SMTP上下文且有限timeout，LogAlertChannel只关自己handler；ASY-006/009强制：本轮stop用共享有界shield等待task，在已取消scope内也完成清理；ERR-004强制：多告警通道允许独立失败并记录traceback；无采样数据为空统计，非外部请求。 |
| app/agents/framework/security/gateway.py | FUN-002推荐：process_request顺序认证/限流/授权/验证/审计；ERR-003/LOG-004强制：转换SecurityError保留cause，审计不输出token片段；RES-001强制：AuditLogger只关闭拥有的handler；DAT-002强制：认证无效/过期None为真实协议，query缺失由InputValidator拒绝，unknown IP是日志字段缺省，不伪造授权身份；非FastAPI入口。 |
| app/agents/models/__init__.py | DES-006推荐、NAM-003强制：5–21现有包公开模型入口，当前包用户仍使用；不新增兼容别名或平行模型定义。 |
| app/agents/models/base.py | DES-008强制：13–18为现有公开模型入口，内部业务已经指向app.models.base；DAT-006/PYD-003强制：AgentResponse为独有响应结构，工厂创建metadata；无依赖失败降级。 |
| app/agents/service/__init__.py | DES-006推荐、NAM-003强制：3–5只导出真实AgentService；已删除未使用旧memory模块，无新增门面。 |
| app/agents/service/agent_service.py | CLS-003/LOG-002强制：请求状态用ContextVar，finally reset；FUN-002推荐：保持已有FAQ/路由/工具/答案组装步骤，未套新执行框架；ASY-001/008/009强制：批量加载在线程、持有内部流直到消费完并同task关闭；DAT-001/002强制：本轮修复finalize的可选agentchat_meta=None被当dict，直接使用trace及其成立字段；DES-001强制：删除必有tools_used之后的死分支；session_id在prepare后已成立，不额外构造默认身份。 |
| app/agents/service/agentchat_router.py | FUN-005强制：AssistantAgent/TaskResult/TextMessage遵守真实SDK协议；ASY-003/008/009强制：会话锁保护agent共享状态，内部stream finally关闭，取消传播；ERR-001强制：空回复/运行失败有error且低置信标记，非假成功；DAT-002强制：primary_tool可真实无调用，cache未建是懒建状态，非缺依赖。 |
| app/agents/service/agentchat_team.py | FUN-005强制：UserProxy和RoundRobinGroupChat是现有协作模式，input_func返回空文本明确禁止API等人工终端；ASY-003/008/009强制：每会话锁/缓存、流关闭；ERR-001强制：空回复失败有error；DES-003推荐：team与单Assistant生命周期不同，保留现有两个实现，不抽无收益模板。 |
| app/agents/service/chat_history_store.py | NAM-003强制/DES-006推荐：CRUD内部依赖直接指向定义模块；DB-001/002/003、ERR-003、RES-001强制：所有session作用域finally关闭，正常fetch未命中None；本轮record_message直接ORM在db.begin内插消息并更新activity，避免CRUD各自commit破坏原子性；失败由事务上下文rollback，SQLite注入UPDATE失败证实无残留消息；connection_id缺失/关联不存在可空来自实际nullable外键。 |
| app/agents/service/tools.py | PYD-001/002/003强制：本轮Dify/Tavily稳定响应同文件BaseModel及AliasChoices校验，metadata为真实动态扩展；DAT-001/003强制：必需title/content/url/score不造值，score=0保留；DAT-002强制：Dify.metadata=None在拥有边界处理一次；DES-001/004强制、CLS-007推荐：无产品引用的同步service懒加载property删除，保留有调用者的get_service；ASY-005/006/007/009强制：初始化任务被持有，取消等待不丢线程资源，owned/borrowed区别；RES-001/007强制：requests响应finally.close与连接/读取timeout；ERR-004强制：Dify传输故障明确本地回退，InvalidJSONError重抛。 |
| tests/test_python_guidelines_integration.py | TST-001强制、TST-002/003推荐：execute_builtin用实际DSLGenerator/PolicyEngine，断言资格、金额、解释trace、0与无匹配；tmp_path管理文件资源，不调用外部服务，不靠代码形状证明正确。 |
| tests/test_python_guidelines_runtime.py | TST-001/005强制：loader由monkeypatch恢复sys.modules，线程释放在finally，真实AutoGen runtime本轮补finally.close；ContextVar测试同任务reset；新增清理预算/缺字段/可选metadata/工作流回归，保留真实requests.Response坏JSON继承测试；删除只为无调用同步property而存的测试；外部依赖替换不宣称在线集成通过。 |
| tests/test_python_guidelines_runtime_monitoring.py | TST-001/005强制：SMTP/日志handler归属、失败cause、零窗口均为行为断言；本轮增已取消scope stop等待真实task清理；tmp_path和mock隔离日志/SMTP/psutil，不触达邮件与远端服务。 |

本轮最终交叉复核：AgentService 的pipeline代理、领域builder、日志对象、settings/Config及DocumentLoader均直接导入定义模块；monitor/gateway配置同样调整。公共包导出与实际子模块命名空间装配保留。两份运行时测试按真实依赖路径隔离，103项通过；逐文件清单已记录最后源码哈希及当前顶层定位。

packs契约连带交叉复核：IntentDetectionTool.detect在IntentPrediction模型转向既有AgentService字典契约的实际边界调用model_dump；Router继续读已验证的模型属性。两个真实消费者的回归确认0、False、null与空chains不被改成默认值，已重读该变更并刷新tools.py的哈希、行数和定位。

终审删除RewriteAgent的domain_hint闲置形参及缓存键第三项，AgentService唯一实际调用此前固定传None，已同步删除。该提示未参与改写结果，无其他产品调用或公开契约；保留query/context缓存区分和真实历史改写行为，已有5项改写回归通过，未增加代码形状测试。

统一202文件验证的532项回归通过，但Ruff发现监控取消回归的anyio.sleep(0)触发ASYNC115。仅改为anyio.lowlevel.checkpoint并重读清理task段，不新增代码形状测试；最终源码哈希已刷新。前次完整验证快照保存在first-verification；最终证据采用修正后重新运行结果。

最终统一验证：532 passed in11.62s；mypy202无错误、配置后Ruff0、202文件编译及3.10语法通过；真实入口导入/OpenAPI引用解析通过并禁止TCP，范围内diff通过。源码及配置验证前后哈希稳定，实际命令与限制见metadata.json和主报告。Bandit保留3高/6中/594低告警，另有独立上下文复核，不称安全清零。
