# Python review round 3 — tooling / knowledge / packs / pipeline

**Final source frozen.** 原定88个Python文件均逐文件复核，相对round2有43个文件变化；未新增Python模块、依赖或部署操作，未修改其他代理所有权文件及round2历史证据。

本报告使用 `C:/Users/luke/.codex/skills/python-coding-guidelines/SKILL.md` 及NAM/FUN/DAT/ERR/DES章节。事先计划见 [tooling-plan.md](tooling-plan.md)，逐文件结论及冻结源码LF SHA256见 [tooling-files.json](tooling-files.json)，实际检查命令与输出见 [tooling-verification.json](tooling-verification.json)。清单包含88/88路径，没有用目录抽样代替逐文件审核。

本轮检查各文件导入、定义、主流程分支和返回契约；受影响函数及实际调用者重新阅读。必需输入直接使用，不把空默认改名为safe函数或三元表达式保留下来。

## 已修正的确认问题

| 规约/级别 | 当前位置 | 问题、影响与最小修正 |
| --- | --- | --- |
| NAM-003 / DAT-002 / DES-004（强制） | `app/knowledge/document_loader.py:14` | 声明的python-docx曾被try-import与Callable/None伪装成可选依赖；改为Document直接导入，删除探测。RapidOCR、PIL/pyzbar、LightRAG pipeline-status等必需依赖同样直接使用。 |
| FUN-003 / DAT-001 / DAT-004（强制） | `app/agents/packs/graph_retriever/node.py:240` | 图请求query_text按真实字典必填；答案生成要求query_context/sources/synthesis；聊天/澄清要求text/query。删除无使用者的对象/属性输入协议兼容和伪空字段。 |
| FUN-001 / DAT-002 / DAT-004（强制） | `app/agents/packs/intent_router/utils.py:39` | 分类器稳定返回字典；坏JSON/非对象/缺或空intent抛ValueError。LLM-first策略在边界直接选规则，删除异常→None的_llm_classify包装，不需上游编造默认意图。 |
| FUN-002（推荐） / DES-004（强制） | `app/knowledge/doc_enhanced.py:52` | 配置决定唯一PDF解析器；选定MinerU/LlamaIndex失败传播，去掉假Docling能力与短文丢弃。DSL选定解析器同样不暗换引擎。 |
| DAT-001 / DAT-004 / DES-004（强制） | `app/knowledge/hierarchical_index.py:892` | 使用实际检索分数，缺score失败，不按排名造分数。显式选定的reranker失败保持错误；显式启用hierarchical的服务失败保持可见。 |
| DES-001（强制） / NAM-001（强制） | `app/agents/dsl_generator/template_registry.py:35` | 删除未用_safe_float；3个实际profile的prepare均必需，直接调用。删FAQ无使用者max_candidates、CLI死指标、虚假协议探测及无作用query参数。 |
| NAM-001（强制） / NAM-004（推荐） | `app/knowledge/mineru_adapter.py:89` | 动作明确为_get_session、_get_assistant、_search_knowledge、_parse_execution_plan、_parse_optional_number、_request_completion、_rank_by_retrieval_score；无生命周期原因的重复局部导入集中。 |

## 保留可选语义的具体依据

- MinerU session、OCR模型、AssistantAgent、索引retriever、LightRAG/reranker在首次初始化前或关闭后真实不存在，`None`表示资源生命周期。Milvus析构的`getattr(_connected)`覆盖构造在字段赋值前失败的实际部分初始化。
- FAQ文件是可选数据源，FAQ未匹配、未知规则/模板属于查询无结果；坏JSON及缺必需字段仍失败。金融数值解析的`None`由所有者转明确`INVALID_INPUT`，不生成假金额/假资格。batch迭代终止哨兵表示iterator耗尽。
- 无答案模型时模板、图片/层级检索关闭后对应的路径，属于既有配置模式。LLM-first规则路由、问题分析规则策略、改写失败用原句，以及成功向量检索后可选重排失败保留原排序，均有明确策略及日志/行为覆盖；不与选定必需解析器/模型失败混同。
- rerank的native LlamaIndex插件及vector独立Ollama插件不是runtime必需包；只在显式选定的功能边界导入，缺包直接失败，没有`Callable | None`或导入异常哨兵。
- scripts的建表/schema同步先装配仓库路径；embed-documents先清代理环境再初始化配置/模型，故保留有实际顺序原因的局部导入。其他无生命周期理由的stdlib/项目重复导入已集中。
- R2R参考例的外部thinking/signature/序列化变化有真实供应商协议，保留其探测；没有以本仓不存在的统一协议替代。ag_workflow高级示例明示固定路径，不凭风格发明路由算法。

## 父代理限定复核的更正

此前冻结结论遗漏了必填字符串/维度的empty-or及真实历史协议。仅对父代理确认的位置继续修正，不据此重写全区：

- graph的backend/model均为配置必填str，直接使用；已知模型维度保持既有值，自定义OpenAI模型直接取必填dimension，0或负数在该Agent选择维度的边界抛ValueError，未跨所有权改配置模型。
- DocumentLoader直接提取keywords；_extract_content为str或raise，去掉不真实Optional；图片去重变量按URL对象命名。
- DialogueAgent的query直接strip；Markdown图片非可选分组直接给alt_text，保留合法空字符串本身。
- 复核真实调用链发现AgentService使用autogen_memory_store.get_recent_messages返回List[str]，不是SessionStore.get_context的字典项。RewriteAgent改为消费实际用户:/助手:前缀，不新增字典/字符串兼容。改源前真实ListMemory多轮测试复现AttributeError，修正后通过；无context、空context及空history正常语义保留。
- Vector rerank直接使用本模块已产生的documents/scores和PolicyDocument.content，空content不变成title；去掉缺失scores及列表长度不足时的假0分。只有rerank的top_n子集外项在既定融合公式中仍为0，属于实际算法；可选精化失败回原向量排序策略不变。
- graph LLM_API_KEY/OPENAI_API_KEY配置候选仍可缺失；template_registry可选平台、rule_agent可选规则元数据和R2R流式delta暂缺name/arguments有实际来源，未机械删除这些缺省。

改源前限定回归分别确认了3项失败（非正维度、空content被替换）和2项失败（真实字符串history）；最终所有测试及静态检查重新执行。清单已经刷新为这次冻结源码，旧中间快照不再代表最终结果。

## 验证及范围

编辑前140项回归通过；限定复核后最终 **165项通过**：tooling26、packs/DSL75、knowledge/pipeline64。覆盖坏意图、选定解析器/模型错误、图/层级搜索错误、真实分数和短文本保留；AST隔离测试显式注入移动后的依赖，生产代码不为测试制造兼容状态。

- Ruff `E4,E7,E9,F,B,ASYNC`通过。
- mypy88文件通过，实际使用`--ignore-missing-imports --follow-imports=silent --disable-error-code=import-untyped`；未声称第三方缺失stubs被全面检查。
- 全88文件Python3.10 AST及当前Python3.11编译通过；scoped `git diff --check`退出0，仅现有Windows换行转换提示。
- docx/PyPDF2/RapidOCR/PIL/pyzbar和LightRAG pipeline-status必需导入在当前安装环境验证，无安装动作。
- pytest成功退出0后，第三方`ascii_colors.ConsoleHandler.close()`在解释器关闭时输出`ValueError: I/O operation on closed file`。告警未被隐藏，未加入无关库monkeypatch。
- 未执行真实MySQL/Milvus/LightRAG/MinerU/LLM/OCR服务调用、数据库迁移/seed、Docker重建或部署。R2R的外部core/shared宿主不在本环境，未宣称参考例独立运行通过；历史Docker fixture仍为executed=False。
- 二进制.doc没有因风格审核新增解析器；现存docx解析器会拒绝不支持的文件。金融、排序、图像识别算法未凭风格猜改。

## 88文件阅读结论

下列每项对应JSON中的当前SHA256。changed表示相对round2快照变化。

| 文件 | 变化 | 结论 |
| --- | --- | --- |
| `examples/ag_builder.py` | unchanged | NAM/FUN/DAT：消息广播、节点顺序和必填query/keywords契约清晰；get超时的None是队列无消息，逐订阅者best-effort有日志，未增加空业务默认。 |
| `examples/ag_prompt.py` | unchanged | NAM/FUN/DAT：系统提示常量及显式导出逐项核对；无运行态资源与伪可空值，connection_id约束保持原提示语义。 |
| `examples/ag_workflow.py` | changed | NAM/FUN/DAT：os及模型客户端导入集中；团队必须包含已注册的全部agent，不静默过滤；stream由创建者关闭。AdvancedOrchestrator固定eligibility_path是演示边界，未凭风格编造自动路由。 |
| `examples/autogen_demo1.py` | unchanged | NAM/FUN/DAT：已安装split Autogen SDK参数和main入口清晰；借用全局client不越权关闭，未配置web工具明确失败。 |
| `examples/autogen_demo2.py` | unchanged | NAM/FUN/DAT：AgentTool/Console实际框架协议保留；创建模型后的finally覆盖错误与取消，无伪造模型或结果。 |
| `examples/autogen_demo3.py` | changed | NAM/FUN/DAT：asyncio移至模块导入；TeamTool与两个真实owned模型依次有界关闭，禁用并行工具调用属于实际SDK约束。 |
| `examples/base.py` | unchanged | NAM/FUN/DAT：R2R参考宿主、供应商thinking/signature与序列化差异逐支核对；保留外部SDK协议探测及流终止None，不替换为本仓假协议。外部core/shared未安装，未宣称独立可运行。 |
| `examples/enterprise_agents.py` | unchanged | NAM/FUN/DAT：金融角色、split SDK类型和borrowed模型契约明确；真实角色提示/工具定义保留，没有无用途的客户端配置包装。 |
| `examples/image_search_demo.py` | changed | NAM/FUN/DAT：traceback集中导入；索引不存在及无命中为显式CLI分支，retriever初始化前None用于finally识别创建成功，最终owner关闭。 |
| `examples/mineru_test.py` | unchanged | NAM/FUN/DAT：官方/本地及batch示例沿用success/content/metadata；adapter由async-with拥有，文件不足明确跳过，不伪称实际远程测试完成。 |
| `examples/rag.py` | unchanged | NAM/FUN/DAT：工具注册与四个R2R宿主组合职责真实；config/_tools为宿主契约，不造空宿主后备；缺失外部core依赖的参考边界保留。 |
| `examples/research.py` | unchanged | NAM/FUN/DAT：研究工具的provider/conversation/get_generation_config由R2R宿主提供；timeout取消后先kill/reap再删临时文件，专项协议不凭风格重写。 |
| `resources/database/seed_data/generate_qa_data.py` | unchanged | NAM/FUN/DAT：逐项检查静态QA字段及main导出；import无写文件副作用，with拥有输出资源，政策数据不作风格性更改。 |
| `resources/database/seed_data/policy_qa_seed.py` | unchanged | NAM/FUN/DAT：分类seed合并、JSON输出及统计按业务顺序；必填字面量完整，无伪空填充或模块导入写盘。 |
| `scripts/1_create_tables.py` | unchanged | NAM/FUN/DAT：main先装配仓库sys.path再导入ORM是实际脚本生命周期；create_all错误传播，本次未执行建表。 |
| `scripts/2_seed_mysql_text2sql.py` | changed | NAM/FUN/DAT：声明依赖dotenv直接导入并调用，不用Callable/None探测；真实空密码、参数化值及FK恢复finally保留。 |
| `scripts/3_init_milvus.py` | unchanged | NAM/FUN/DAT：CLI构造、统计、关闭顺序明确；初始化失败exit1，owned MilvusStore在finally关闭，未运行数据库操作。 |
| `scripts/4_embed_documents.py` | changed | NAM/FUN/DAT：stdlib traceback集中导入，main内一次导入两层级类型；代理环境必须先清理后初始化配置/模型，故该实际局部导入保留。统计与查询失败退出码真实，retriever最终关闭。 |
| `scripts/5_embed_process_documents.py` | unchanged | NAM/FUN/DAT：dry-run仅扫描不创建store；正常路径构造/导入/统计按顺序，异步线程边界和owned service有界关闭保留。 |
| `scripts/6_seed_lightrag.py` | changed | NAM/FUN/DAT：清单读取、批量入库、成功后写manifest职责直接；GraphRetriever为必需类，构造在线程，owned资源最终关闭，不执行真实入库。 |
| `scripts/7_sync_text2sql_schema.py` | unchanged | NAM/FUN/DAT：仓库路径装配先于project imports有实际原因；数据库未命中才创建连接记录，owned Session finally关闭，无伪造schema成功。 |
| `scripts/unified_cli.py` | changed | NAM/FUN/DAT：删除无用agent_metrics和无使用者的object/dict指标探测；保留真实异步initialize生命周期及logging枚举选择。固定5条processing_chains仅为配置概览，未冒称性能测量。 |
| `tests/data_import.py` | unchanged | NAM/FUN/DAT：导入/测试工具及内嵌脚本文本均复核；显式子进程timeout/非零失败，取消kill/reap先于临时目录回收；本轮未运行Docker或真实数据库。 |
| `tests/docker_rebuild_test.py` | unchanged | NAM/FUN/DAT：历史报告fixture的executed=False契约清楚；main仅按请求生成历史说明，不把静态历史结果当本轮检查。 |
| `tests/test_python_guidelines_tooling.py` | unchanged | NAM/FUN/DAT：26项离线行为回归继续覆盖脚本、资源关闭与真实字段；AST加载器只保留指定定义，是明确测试隔离协议，不是生产兼容抽象。 |
| `app/agents/dsl_generator/__init__.py` | unchanged | NAM/FUN/DAT：DocumentParser/DSLExtractor/PolicyEngine/DSLGenerator/DSLPipeline五个真实公开导出逐项核对，包门面保留。 |
| `app/agents/dsl_generator/document_parser.py` | changed | NAM/FUN/DAT：Document/PdfReader/SimpleDirectoryReader必需对象直接导入；use_llama_index明确选择唯一解析路径，选定解析器失败传播，不以None或换引擎伪成功。 |
| `app/agents/dsl_generator/dsl_extractor.py` | changed | NAM/FUN/DAT：settings/OpenAI直接导入，删sys.path及导入失败默认；use_project_config选择真实模型或离线规则路径，_call_llm只负责模型请求；缺必需金融参数不补造业务值。 |
| `app/agents/dsl_generator/dsl_generator.py` | unchanged | NAM/FUN/DAT：加载/标准化/生成/存储职责清晰；rule_id和YAML错误保持可见，文件名限制为单段，明确preset模板与缺数据分开。 |
| `app/agents/dsl_generator/dsl_generator_domain.py` | changed | NAM/FUN/DAT：OpenAI、datetime/timedelta和sys集中模块导入；领域schema及必需rule_id直接读取，递归规范化与save沿用真实领域契约。 |
| `app/agents/dsl_generator/dsl_runtime_helpers.py` | changed | NAM/FUN/DAT：_safe_float改名_parse_optional_number表达实际解析；无效数字的None由金融helper转明确INVALID_INPUT，0与未配置限制区分。 |
| `app/agents/dsl_generator/main.py` | unchanged | NAM/FUN/DAT：Typer回调和Option/Argument遵守实际框架协议；JSON边界要求对象，命令主流程直接，不构造通用兼容层。 |
| `app/agents/dsl_generator/pipeline.py` | changed | NAM/FUN/DAT：settings必需直接导入，不再吞导入失败；解析→抽取→校验→生成→保存直接，validation错误阻止保存，batch逐项状态明确。 |
| `app/agents/dsl_generator/rule_engine.py` | changed | NAM/FUN/DAT：AST调用按允许函数名/helper/mapping.get直接分支，不建Optional Callable临时值；未知调用立即失败。规则未命中是实际查询None，非法输入/执行错误有独立状态。 |
| `app/agents/dsl_generator/template_registry.py` | changed | NAM/FUN/DAT：删除无人使用_safe_float；三个profile全部提供prepare，因此prepare为必需Callable并直接调用。领域默认只保留已有业务用途，缺政策金额失败。 |
| `app/agents/packs/__init__.py` | unchanged | NAM/FUN/DAT：12个真实包导出逐项核对；PolicyReviewAgent别名用于区分公开角色，不作为缺依赖或输入兼容探测。 |
| `app/agents/packs/answer_generator/__init__.py` | unchanged | NAM/FUN/DAT：AnswerGeneratorAgent为真实包导出，__all__一致，包门面无业务默认。 |
| `app/agents/packs/answer_generator/node.py` | changed | NAM/FUN/DAT：re集中导入；process_request明确字典契约，query_context/sources/synthesis必填，不探测不存在的请求对象类型。显式模型失败传播；无模型时模板是明确配置模式，assistant为真实懒状态。 |
| `app/agents/packs/answer_generator/prompt.py` | unchanged | NAM/FUN/DAT：生成提示函数参数与要求的JSON字段对齐；专属领域提示职责清楚，无运行态None或资源。 |
| `app/agents/packs/chat_agent/__init__.py` | unchanged | NAM/FUN/DAT：ChatAgent为真实包导出，__all__与导入对应，未增抽象。 |
| `app/agents/packs/chat_agent/node.py` | changed | NAM/FUN/DAT：request[text]是必需输入直接读取；可选response_type/intent仍为真实提示，聊天模板与响应错误协议清楚。 |
| `app/agents/packs/clarifier/__init__.py` | unchanged | NAM/FUN/DAT：ClarifierAgent真实公开导出，保持现有调用路径。 |
| `app/agents/packs/clarifier/node.py` | changed | NAM/FUN/DAT：query必需直接读取；删不被使用的alternatives集合，直接返回实际单个澄清问题，未预建多候选框架。 |
| `app/agents/packs/graph_retriever/__init__.py` | unchanged | NAM/FUN/DAT：GraphRetrieverAgent真实公开导出，无可选依赖探测或伪空对象。 |
| `app/agents/packs/graph_retriever/node.py` | changed | NAM/FUN/DAT：必需LightRAG及pipeline-status直接导入，query_text按真实字典必填；embedding backend/model为必填字符串直接使用，自定义OpenAI模型取配置维度且非正值明确拒绝，不再or1536。callback必需返回Callable，资源None只表生命周期。 |
| `app/agents/packs/intent_router/__init__.py` | unchanged | NAM/FUN/DAT：IntentRouterAgent与LLMIntentClassifier两个真实出口，未借重导出访问内部模型定义。 |
| `app/agents/packs/intent_router/node.py` | changed | NAM/FUN/DAT：LLM-first策略在自身边界直接调用分类器并选择规则，删除异常→None包装_llm_classify；坏confidence明确回规则而不捏造数值，规则后备是已命名业务策略。 |
| `app/agents/packs/intent_router/prompt.py` | unchanged | NAM/FUN/DAT：意图提示函数与intent/sub_intent/confidence/chains契约对应，无隐式运行态默认。 |
| `app/agents/packs/intent_router/utils.py` | changed | NAM/FUN/DAT：_ensure更名_get_assistant；classify稳定返回Dict，坏JSON/非对象/缺失或空intent直接ValueError。assistant/client None来自实际懒初始化，不把必需依赖声明成可空Callable。 |
| `app/agents/packs/policy_analysis/__init__.py` | unchanged | NAM/FUN/DAT：PolicyAnalyzerAgent单一实际公开出口，职责保留。 |
| `app/agents/packs/policy_analysis/node.py` | unchanged | NAM/FUN/DAT：条件/收益/流程/日期/联系人提取及综合评分逐分支核对；内部模型必需字段直接读，NLP共享Assistant有锁，专项权重不凭风格变更。 |
| `app/agents/packs/policy_analysis/prompt.py` | unchanged | NAM/FUN/DAT：专属分析提示函数与实际提取字段对齐，领域提示常量保留，无伪依赖/结果。 |
| `app/agents/packs/policy_comparator/__init__.py` | unchanged | NAM/FUN/DAT：PolicyComparatorAgent真实包门面，显式导出一致。 |
| `app/agents/packs/policy_comparator/node.py` | unchanged | NAM/FUN/DAT：Pydantic从定义包显式导入，比较维度、异构配置、表格和confidence按真实模型核对；必需comparison_type存在，不虚构比较结果。 |
| `app/agents/packs/policy_retriever/__init__.py` | unchanged | NAM/FUN/DAT：PolicyRetriever为实际公开类型，__all__保持真实调用。 |
| `app/agents/packs/policy_retriever/node.py` | changed | NAM/FUN/DAT：模型请求包装a_create更名_request_completion；PolicyDocument/分数配对契约直接，同步搜索在线程，仅关闭自己创建的模型，检索失败可见。 |
| `app/agents/packs/policy_review/__init__.py` | unchanged | NAM/FUN/DAT：PolicyReviewAgent与现存PolicyAnalyzer兼容公开名字有当前导出调用依据，不因推荐风格删框架入口。 |
| `app/agents/packs/policy_review/node.py` | changed | NAM/FUN/DAT：a_create改名_request_completion；PolicyDocument由app.models.base定义模块导入。LLM JSON必需分析字段在边界验证，simple_analysis是明确分析策略，owned模型关闭。 |
| `app/agents/packs/query_analyzer/__init__.py` | unchanged | NAM/FUN/DAT：QueryAnalyzerAgent真实包导出，不含运行分支或伪None。 |
| `app/agents/packs/query_analyzer/node.py` | unchanged | NAM/FUN/DAT：必需jieba直接导入；实体/关键词/时间/地区和QueryIntent映射为已有领域算法，按实际对象流转，未增加安装探测或空格替代分词。 |
| `app/agents/packs/question_builder/__init__.py` | unchanged | NAM/FUN/DAT：QuestionUnderstander/QuestionGenerator为两个真实公开角色，显式导出一致。 |
| `app/agents/packs/question_builder/node.py` | changed | NAM/FUN/DAT：a_create更名_request_completion；外部JSON由入口验证intent/实体/置信度，内部AnalysisReport字段直接用；规则后备有日志，owned模型幂等关闭。 |
| `app/agents/packs/vector_retriever/__init__.py` | unchanged | NAM/FUN/DAT：VectorRetrieverAgent为真实公开出口，未预建额外实现抽象。 |
| `app/agents/packs/vector_retriever/node.py` | changed | NAM/FUN/DAT：必需依赖集中导入，仅独立Ollama插件局部导入；_maybe_rerank直接读取本模块_search_similar的documents/scores及PolicyDocument.model_dump的content，不补造标题/零向量分数。rerank仅给top_n项，融合时未重排项0权重有真实算法语义；失败保留原排序。 |
| `tests/test_python_guidelines_packs_dsl.py` | changed | NAM/FUN/DAT：75项离线回归覆盖必需字段/选定模型失败、坏意图、选定解析器、真实维度、空content保留、真实零向量分数融合及optional-rerank失败。维度0/-1与空content回归均在改源前证实失败；AST依赖显式注入。 |
| `app/agents/pipeline/__init__.py` | unchanged | NAM/FUN/DAT：八个实际pipeline角色显式公开导出，包门面属于真实装配职责。 |
| `app/agents/pipeline/dialog_agent.py` | changed | NAM/FUN/DAT：query: str是必需调用契约，领域/缺槽检测直接query.strip，不把None伪装成空问题；可选domain_meta的业务信息缺省保留。 |
| `app/agents/pipeline/graph_agent.py` | changed | NAM/FUN/DAT：_graph_agent构造后必需，删构造失败→None和查询失败换知识路由；只有真实无图文档才使用已有知识后备，ingest/close直接调用实际拥有对象。 |
| `app/agents/pipeline/knowledge_agent.py` | changed | NAM/FUN/DAT：_safe_search更名_search_knowledge、re集中导入；KnowledgeTool上下文timings和PolicyDocument字段直接读取，domain_context/web_tool可选来自实际功能配置。 |
| `app/agents/pipeline/rewrite_agent.py` | changed | NAM/FUN/DAT：实际AgentService从AutoGen ListMemory提供List[str]，直接按用户:/助手:前缀读取，不再虚构item.get(type/text)字典协议或添加dict/str双兼容；多轮真实生产者回归已验证。无context/无history保持正常，cache仍含上下文。 |
| `app/agents/pipeline/rule_agent.py` | changed | NAM/FUN/DAT：_safe_parse_json更名_parse_execution_plan；坏JSON/缺rule_id/inputs失败并保留cause，必需status直接用，未知布尔输入留给INVALID_INPUT校验。 |
| `app/agents/pipeline/text2sql_agent.py` | unchanged | NAM/FUN/DAT：正connection_id入口验证；Session属于chatdb异步入口且不跨模型await；错误FinalAnswer有route/error状态，无结果与错误不混同。 |
| `app/agents/pipeline/workflow_agent.py` | unchanged | NAM/FUN/DAT：GraphFlow实际SDK流协议保留，run_stream由本函数finally有界关闭；borrowed模型不关闭，既有workflow后备附失败reason。 |
| `app/knowledge/__init__.py` | unchanged | NAM/FUN/DAT：存储/解析/OCR/索引/重排真实公开对象与__all__逐一核对；重导出是包协议，不替代内部定义模块依赖。 |
| `app/knowledge/doc_enhanced.py` | changed | NAM/FUN/DAT：删除常真LlamaIndex能力探测和未实现Docling状态；PDF按配置唯一选择MinerU或LlamaIndex，选定引擎失败传播，短真实文本不丢弃；抽取方法元数据反映实际引擎。 |
| `app/knowledge/document_loader.py` | changed | NAM/FUN/DAT：Document必需直接导入；_extract_content所有分支为str或raise，标注据实收紧；keywords由本loader直接提取，不探测从未写入的metadata键。图片去重变量为seen_image_urls/unique_image_urls/image_url；真实无文本仍无文档。 |
| `app/knowledge/faq_responder.py` | changed | NAM/FUN/DAT：os集中导入，删除无使用者max_candidates参数/状态；缺可选FAQ文件与真实未匹配返回None，损坏数据仍明确失败。 |
| `app/knowledge/hierarchical_index.py` | changed | NAM/FUN/DAT：删除常真LlamaIndex/图片能力门控，必需模型/分数类型直接导入；_rank_by_retrieval_score准确命名并删未用query；选定reranker失败传播，无score明确失败，不伪造排名分数。 |
| `app/knowledge/hybrid_retrieval.py` | changed | NAM/FUN/DAT：层级processor与stdlib依赖集中导入；doc_id/title为必需真实字段，0限额返回空列表，负限额/未知策略失败；专项BM25/RRF公式保留。 |
| `app/knowledge/image_retrieval.py` | changed | NAM/FUN/DAT：PIL/pyzbar/TextNode直接导入，get_images_for_nodes使用真实TextNode.metadata；Markdown group1非可选且返回str，直接使用alt_text，空alt保留为空，不增加empty-or。 |
| `app/knowledge/llamaindex_hybrid_retrieval.py` | changed | NAM/FUN/DAT：DashScope/OpenAI/SimpleDirectoryReader依赖直接模块导入；只None取配置默认，alpha=0保留；query_engine None是未建索引，实际client owner幂等关闭。 |
| `app/knowledge/llamaindex_integration.py` | changed | NAM/FUN/DAT：PolicyDocument/PolicyType由定义模块直接导入，删重复TYPE_CHECKING；使用真实retrieval_score，不按序号伪造分数；retriever None明确无索引/关闭，重建后换资源关闭旧owner。 |
| `app/knowledge/milvus.py` | changed | NAM/FUN/DAT：settings/HTTP/OpenAI及PolicyDocument/PolicyType集中直接导入，删重复局部/TYPE_CHECKING；collection None是初始化前/关闭状态，析构getattr(_connected)覆盖构造早期失败的真实部分初始化。 |
| `app/knowledge/mineru_adapter.py` | changed | NAM/FUN/DAT：_ensure_session更名_get_session表达取得/创建真实session；None仅是未创建/已关闭资源；success/content/metadata协议明确，官方签名请求用独立无认证session。 |
| `app/knowledge/rapid_ocr_processor.py` | changed | NAM/FUN/DAT：RapidOCR必需直接导入，删可用性flag/导入失败哨兵；self.ocr None属于真实模型懒加载，文件/PDF资源关闭和OCRException cause保留。 |
| `app/knowledge/rerank.py` | unchanged | NAM/FUN/DAT：settings与HTTP结果契约直接；明确选择的native LlamaIndex插件非runtime声明依赖，保持功能边界局部导入并让缺依赖失败，不用None隐藏。score=0有效，HTTP owner关闭。 |
| `app/knowledge/service.py` | changed | NAM/FUN/DAT：显式启用hierarchical时搜索错误传播，不伪成功切向量；真正禁用hierarchical配置才走向量路径。task-local timings与borrowed文档契约保持，owned store逐个有界关闭。 |
| `tests/test_python_guidelines_knowledge_pipeline.py` | changed | NAM/FUN/DAT：64项离线回归覆盖检索/解析失败、真实score、资源与短文本，并由真实AutoGen ListMemory生成List[str]验证多轮改写，改源前复现AttributeError；无history的None/{}/[]三例保留。 |

**本次限定修正后的源文件最终冻结通知：88个所有权文件不再编辑。** 当前哈希对应165项回归与本轮静态检查使用的源码；报告如实记录验证边界，不以检查通过宣称不存在其他遗漏。
