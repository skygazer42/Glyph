# AG-UI 问答与来源交互实现计划

**目标：** 将用户已确认的 AG-UI 接入、真实进度反馈和正文引用跳转落到现有 Vue / AutoGen 工程中，并合并同一政策的重复来源。

**范围：** 改流程与加功能，同时整理截图指出的等待区和来源区；沿用现有政务字体、配色、导航和权限体系，不重做整个页面。用户已在上一轮方案后明确要求接入并完善引用，因此直接执行。

## 设计与协议

- 新增 `/api/agent/ag-ui`，使用官方 Python `ag-ui-protocol` 的 RunAgentInput、类型化事件和编码器。现有 API 保留兼容。
- Vue 继续使用现有 fetch / Cookie / CSRF，通过标准 AG-UI 生命周期、步骤、工具、文本事件更新状态；业务会话、来源和最终权威答复通过有名字的 CUSTOM 事件传递。
- 处理阶段来自业务执行边界，显示当前阶段、耗时与停止；不模拟检索条数或假进度。中断取消服务端任务，不重放工具。
- 等待消息隐藏复制、完成时间等结果操作。模型支持时消费真实内容增量，最终内容按权威快照替换，避免片段与全文重复拼接。
- 正文 `[资料1]` / `[1]` 引用生成安全的原生超链接，保留原编号与来源索引；普通点击打开对应依据，修饰键 / 新标签打开可用原文链接。无可用来源时保留文本，不伪造 URL。
- 来源按原文身份合并，标题只显示一次，片段在组内收起；不同原文不因同名合并。依据面板显示可核对摘录和原文入口。

## 并行实现边界

1. AG-UI 路由与适配：新路由、官方 SDK、权限与断连测试。
2. 服务进度：请求级 ContextVar 通知、真实阶段与工具事件、来源元数据，保留普通问答行为。
3. 引用与来源：安全格式化、稳定分组、来源组件与对应前端测试。
4. 主代理：Vue AG-UI 客户端与消息状态、等待界面、整合、浏览器验收及最终验证。

共享通知接口约定：`app.agents.service.progress.capture_progress(callback)` 为同步上下文管理器；`emit_progress(event_type, **data)` 推送 dict，含 `type` 与 data。事件为 `step_started/step_finished`（name、label）、`tool_started/tool_finished`（tool_call_id、name，可选 args / result）、`sources`（sources）。没有监听者时不改变业务行为。

AG-UI CUSTOM 事件约定：`glyph.session` 的 value 包含客户端可用 session_id；`glyph.sources` 包含 sources；`glyph.answer` 包含最终 content、metadata、session_id。RUN_STARTED / RUN_FINISHED 的关联标识跟随该次输入。只信任服务端认证派生的访问权限。

## 验证

- Python：标准事件序列与 ID、运行失败、来源到达、最终快照、取消清理；公众签名会话、工作人员 CSRF、附件与私有工具隔离；进度上下文并发隔离。
- JavaScript：流分片解析、最终快照无重复、断流/错误/取消；来源去重保留编号、引用跳转、危险 URL / HTML、长标题与中文条款。
- 前端现有静态检查、构建和适用脚本回归；Python 相关 pytest / Ruff / 类型检查。
- 浏览器：等待、正文流入、同文多片段、引用点击、原文打开、停止、失败重试、窄屏；真实界面截图复核。
- 不迁移数据库，不更改既有语料和密钥。只新增接入官方 AG-UI 所需依赖。
