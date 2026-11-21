# 第三轮运行时与跨模块复核

本轮沿用两名子智能体，主代理负责运行时、跨模块契约及统一验证。清理前先写 [plan.md](plan.md)，并执行已有运行时、监控与集成回归。逐文件说明及最终源码哈希见 [root-files.json](root-files.json)；这份清单覆盖 39 个现存文件，另记录删除的旧 memory 模块。它结合前轮全文阅读和本轮调用方、字段生产者及主流程复核，不声称静态工具能证明代码容易维护。

| 规则 | 位置 | 具体修正 |
| --- | --- | --- |
| NAM-001 / FUN-002 | AgentService、AgentChat router/team、monitor、policy_domain | `started_at` 表达计时起点；`_get_or_create_agent` / `_get_or_create_team` 表达实际懒建；`_append_citations` 表达追加引用；百分位插值、地区替换与工具标签使用实际对象名称。 |
| NAM-003 / ERR-001 | tools、autogen_memory_store、monitor | requests、TavilyClient、MultiModalConversation、Redis、psutil 与 SMTP 直接导入；删除用 None 假装必需依赖可用的状态。缺依赖直接暴露导入错误。 |
| DAT-001 / DAT-004 | tools、AgentService、session stores | 固定意图、领域上下文、检索结果及评分直接读取，不虚构标题或零分；会话写入必须已有会话，缺失明确失败。 |
| DAT-002 / DAT-005 | WebSearchTool、VisionTool、KnowledgeTool | 自动未配置或显式禁用保留真实可选语义；显式启用但缺凭据立即报错。配置缺省由签名与配置层决定，删除重复 `_enabled` 状态。 |
| ERR-001 | AgentService 工具闭包、Dify 检索 | 五条工具路径记录错误指标后重新抛出，不返回伪成功文本；Dify 请求异常走既有本地检索回退，但明确排除同属 RequestException 的 InvalidJSONError，真实坏 JSON 与字段错误直接暴露。 |
| FUN-003 / DES 最小实现 | factory、base_agent、orchestrator、chat_history_store | 必需 answer_generator 使用必填协议参数；删除无职责转发、重复 context 默认化、闲置 model_client / graph_db 状态。保留真实框架回调、公开导出与不同调度策略。 |
| DES 最小实现 | app/agents/service/memory.py | 全仓源码、测试、导出与当前产品文档没有消费者，删除该旧模块；实际 AutoGen memory store 保留。 |

## 保留的判空有实际来源

- 模型覆盖参数的 None 表示未提供；temperature=0、seed=0 仍原样传递。
- 会话或认证查询未命中、可选地区/时间窗口、未注册 verifier、广播 recipient、队列等待超时分别属于真实业务协议。
- 未创建或已关闭的模型、ListMemory、cleanup task 等资源有明确生命周期；动态 handler 判断来自真实子类注册协议。
- 会话标题是可选展示信息；引用 metadata 的 path/origin/chunk_idx 本来可缺，不能当作 PolicyDocument 的必需字段。它们与必需 answer/content/score 的契约不同。
- 自动种子导入、主答案保存后的辅助 memory 写入仍采用既有部分成功策略，记录异常；主保存、显式导入和工具失败保持可见。

## 回归与证据

清理前运行既有 71 项测试；本轮根分区增加显式启用缺配置、缺必需响应字段、工具异常传播、Dify 响应/传输错误区分、非法工具预算和不存在会话写入等有意义的行为覆盖。最后追加真实 JSON 响应回归之前的 91 项结果见 [root-final.txt](root-final.txt)；包含最终源码及新增回归的全仓结果以 [metadata.json](metadata.json) 和 [pytest.txt](pytest.txt) 为准。

改源前失败证据分别保留在 `root-tools-before.txt`、`root-config-before.txt`、`root-dify-before.txt`、`root-session-before.txt`。`root-before.txt` 同时包含初期测试装配错误，不能把其中所有失败都当作产品缺陷。Redis 与 psutil 顶层导入后，相应替身在导入前装配，未为测试给产品增加兼容分支。

最后只读交叉检查用真实 requests.Response.json() 发现异常继承边界的遗漏。新增回归先在旧实现上确认 DID NOT RAISE，再修正边界；[改前失败](root-dify-json-before.txt) 与 [Dify 五项通过](root-dify-json-after.txt) 均保留。普通 ValueError 替身不能证明 requests 自身 JSONDecodeError 的传播，这个差别已在回归中覆盖。

统一验证与限制见 [当前总报告](../README.md)。未调用真实外部业务服务，未安装依赖、提交、部署、迁移或修改前端。第三方 ascii_colors 在 pytest 退出时仍可能输出关闭日志流告警，测试退出码及断言结果另有原始记录。
