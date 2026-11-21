# 根分区最终只读交叉检查

范围：`app/agents/service/tools.py` 与 `app/agents/service/agent_service.py` 本轮依赖导入、意图检测返回、WebSearch/Vision 配置、Dify 异常边界和五条 AgentChat 工具路径。依照 python-coding-guidelines 的 NAM-003、DAT-001–005、ERR-001/002/004，沿真实生产者、调用方及安装的 AutoGen/Requests 实现核对。审核者未修改源码、测试或已冻结的 API 分区清单，未启动服务、访问网络或调用真实模型/数据库。

## 已发现并交主代理修复的问题

**[P2] ERR-001/ERR-002 强制：Dify 的请求异常回退最初也捕获了真实 JSON 解析错误。**

- 初始位置：`tools.py:414` 的 `except requests.RequestException`；下游 `resp.json()` 原在 428 行。
- 调用链：`KnowledgeTool.search` → `DifyKnowledgeProxy.search` → `asyncio.to_thread(_search_sync)` → `requests.Response.json()`。
- 实际影响：供应商返回 HTTP 200、正文 `not-json` 时，响应解析故障变成 `([], [])`；`KnowledgeTool` 继续查询本地知识库。此行为超出了本轮明确保留的请求故障回退语义。已有测试使用普通 `ValueError` 模拟坏响应，因此没有覆盖 Requests 的真实异常继承。
- 本机实际 MRO：`requests.exceptions.JSONDecodeError` → `requests.exceptions.InvalidJSONError` → `requests.exceptions.RequestException` → `OSError` → `json.decoder.JSONDecodeError` → `ValueError`。所以只验证普通 `ValueError` 会传播，不能证明真实 `Response.json()` 会传播。
- 只读复现：从当前源文件 AST 提取原样 `DifyKnowledgeProxy` 类，替换 `requests.post` 为本地真实 `requests.Response`；HTTP 状态设为 200，`_content=b'not-json'`，`_content_consumed=True`，`encoding='utf-8'`。初始输出为 `_search_sync: JSONDecodeError`、异步 `search: ([], [])`，同时记录本地回退警告。
- 已交主代理修复：主代理新增真实 Response 离线回归，确认红后，在请求异常边界将 `requests.exceptions.InvalidJSONError` 明确重新抛出；其余请求故障保留既有回退。前后证据见 [root-dify-json-before.txt](root-dify-json-before.txt) 与 [root-dify-json-after.txt](root-dify-json-after.txt)。

**修复后独立复核通过。** 审核者再次提取最新源文件中的同一类、使用相同真实 Response 复现，实际 `requests.exceptions.JSONDecodeError` 已向上传播，且没有记录回退警告；另将 `requests.post` 设为抛出 `requests.ConnectionError`，仍得到 `([], [])` 并记录一次警告。未发生真实网络请求。主代理该组 5 项 Dify 回归通过。最终源码/测试哈希由主代理在统一冻结后核验。

## 其余范围的检查与结论

| 检查位置 | 实际契约与结论 |
| --- | --- |
| `tools.py:17–28`，`requirements.txt:7/50/54/60` | requests、TavilyClient、MultiModalConversation、AsyncOpenAI 均为已声明依赖，采用直接导入；没有把缺必需依赖降为 None 的分支。KnowledgeService 来自实际所有者，没有通过装配层反向获取业务实现。 |
| `tools.py:31–38`，`intent_router/utils.py:39–76`，`agent_service.py:712–722/866–867` | IntentDetectionTool 原样 await 并返回分类器字典，不额外包装或虚构 intent。分类器解析 JSON、要求对象和非空字符串 intent；实际主流程补齐 raw_query/domain_context 后进入路由。格式/模型错误向上传播。 |
| `agent_service.py:881–961` | 必需 intent/raw_query/domain_context 直接读取。sub_intent 是提示协议允许的 null；chains 是真实分支提示，可在分类器只保证 intent 的契约下缺省。dialogue 分支原先残留的 `.get('intent', 'chit_chat')` 因上游已校验而不是新增运行故障，但仍是冗余的必填字段默认；主代理在报告集成时已按 DAT-001 改为直接读取 `intent_result['intent']`，最终统一验证覆盖该修正。 |
| `utils/config.py:61–101/145–162`，`config/__init__.py`，`agent_service.py:176–196` | AgentService 使用真实 Config 的 web_search/vision 子模型，将各项字段直接传入对应工具。可选凭据与 base_url 在配置边界只把精确空串规范化为 None；启用开关和值的传递一致。 |
| `tools.py:132–210`，`pipeline/knowledge_agent.py:271–275` | 显式禁用不建客户端；显式启用缺凭据报错；独立调用时 enabled=None 表示按真实环境凭据自动配置。Tavily 的 results/title/content/url/score 直接读取，0 分与显式 max_results=0 保留。KnowledgeAgent 在线程执行同步检索，实际禁用才返回空结果，供应商错误不在工具中伪装无结果。展示层空标题使用默认文案有明确用途。 |
| `tools.py:213–389`，`pipeline/workflow_agent.py:112–143` | Vision 显式启用但无真实凭据报错；None 凭据可按已存在的 VISION_API_KEY/OPENAI_API_KEY 配置路径解析。仅已配置 DashScope 地址选择 DashScope，否则使用 AsyncOpenAI 的真实默认/配置地址。关闭状态、未附图、附件缺本地路径、可选 MIME、内容部件只有 image 没有 text 均有实际来源。外部调用、坏状态和缺答案错误保持可见。 |
| `agent_service.py:1346–1430`，Router/Team 的构造位置 | 五条知识、图谱、规则、SQL、workflow 工具方法均 await 实际业务方法、直接读取 FinalAnswer.answer/sources；捕获异常只补错误指标/traceback 后裸 raise。规则路径缺计算信息转知识库是已有业务路由，知识库后备自身失败同样传播。SQL 的真实无可用 connection_id、workflow 的当前请求附件来自既有上下文。 |
| 安装的 `AssistantAgent._execute_tool_call`、`StaticStreamWorkbench.call_tool_stream` | AssistantAgent 从 workbench 的 ToolResult 读取 is_error；workbench 捕获工具异常并构造 is_error=True 的 ToolResult。五条路径重新抛出与真实 SDK 协议一致，错误文本不再作为工具成功返回。 |
| `agent_service.py:466–475/1626–1671`，`_request` | 普通与流式入口创建、重置 ContextVar 请求状态，工具闭包的来源、附件和指标均使用该状态；并发请求隔离协议保留。 |
| `tools.py` 的 Dify/UserProfile 元数据与 `agent_service.py` 的引用/时序元数据 | title、metadata、history、path/origin/chunk_idx、可选工具痕迹均有真实缺省或展示语义；没有把这些 `.get`/空值回退机械当作必需数据缺失。`UserProfileTool.fetch` 自己保证的 found/message/user_id 则由消费方直接读取。 |

## 验证与边界

- 审核期间运行相关已有回归：**19 passed, 127 deselected**，包含意图坏输出、依赖缺失、显式启用缺凭据、Tavily 必需字段、Dify 和工具错误传播。该次运行在主代理最后的 JSON 修正之前；追加修正的 5 项结果单独记录于上面的主代理证据。
- 对源文件原样 AST 提取的五条工具方法做隔离调用：分别令真实下游接口抛出同一 RuntimeError 实例，**5 条均原异常传播并保留 error 指标**；规则→知识库后备额外 1 条同样通过。
- 上述 AST 提取仅用于避免导入整套服务并触发真实外部初始化，没有重写方法主体。首次临时工具闭包提取漏带 future annotations，装配时报 NameError；补齐源文件本来就有的 annotations 后六条检查通过，该装配错误不是产品缺陷。
- 19 项 pytest 退出码为 0；其退出后出现的第三方 ascii_colors 关闭已关闭日志流告警，与既有报告一致，不把它写成源码业务失败。
- 除已交主代理且复核修复的 Dify JSON 边界外，**无新增可证实发现**。本次不替代全仓最终验证，也未进行真实 DB、LLM、Tavily、DashScope 或 Dify 集成验证。
