# 02 现代政务平台实施计划

> **For agentic workers:** Use oil-ui-pro 的原型工程化与多页铺开流程，按本计划的共享接口实施。用户已明确授权直接替换，沿用当前功能分支，不另设确认停顿。

**Goal:** 将用户选定的 R11 02 布局实现到实际 Vue 前端，并提供知识库、文档、图谱、规则、后台问答与公众咨询的清晰入口。

**Architecture:** 后台共享 WorkspaceLayout 横向导航；公众咨询使用独立页头。后台与公众复用 AgentChat 的请求、会话、附件和来源处理，仅通过 workspace 属性区分展示。页面仍消费现有 API，不在生产页面放入演示数据。

**Tech Stack:** Vue 3、Vue Router、Element Plus、Axios、ECharts、Vite。

**Spec:** `docs/frontend-audit/modern-implementation.md`；已选原型 `.oil-ui/glyph-government-r11/explore/02-modern.html`。

## Global Constraints

- 保留 Glyph 标记、现有 API、SSE、会话、附件、文档版本核对与配置保存合同。
- 微软雅黑界面15px/24px，公众与政策正文18px/32px；白色顶栏、蓝色当前项、浅灰画布。
- 使用既有依赖，不引入第二套组件库；不复制原型中的样本数据和手写控件。
- 原文件使用现有原页/原文件能力，不伪造页码、摘录、当前有效性或后台进度。
- 不提交或合并；在已授权的当前功能分支提供可运行结果。

## Review Focus

- 切换公众/后台与会话时，停止旧请求，旧响应不覆盖新页面或新会话。
- 长文档名、长来源、手机宽度下导航与处理控件不被裁切。
- 文档查看不触发解析或入库；保存失败保留草稿。
- 图谱无数据/接口失败可恢复，实体详情随当前数据和选择更新。
- 公众界面不显示数据库配置；工作人员可在后台问答使用原有数据库查询能力。

## Task 1：共享外壳与变量

Files: `web/src/App.vue`、`web/src/router/index.js`、`web/src/components/workbench/WorkspaceLayout.vue`、`web/src/styles/variables.css`、`web/src/styles/modules.css`。

- [x] 统一后台横向导航：`/workbench`、`/knowledge`、`/graph`、`/dsl`；公众入口为`/agent`，根地址仍进入公众咨询。
- [x] WorkspaceLayout 只负责后台页头、导航与内容区域；用路由meta标题、统一tokens及Element Plus。
- [x] 路由视图按path隔离生命周期；知识库query变化仍保留当前组件。
- [x] 验证：现有 `npm run check` 与实际路由导航。

## Task 2：知识库与文档工作区

Files: `KnowledgeBase.vue`、`KnowledgeDocumentWorkspace.vue`、`KnowledgeImportDialog.vue`、`knowledge-workspace.css`。

Consumes: Task 1 的 WorkspaceLayout 与 `--wb-*`。

- [x] 资料入口采用宽筛选与表格，正文与入库状态分别可辨。
- [x] 文档内原文、解析、切块、索引保留实际功能与版本核对，更新阅读字号与宽度。
- [x] 验证：资料筛选、进入/返回文档、只读预览、保存失败及手机布局；检索返回保留上下文。

## Task 3：图谱与规则

Files: `KnowledgeGraph.vue`、`DSLGenerator.vue`。

Consumes: Task 1 的外壳与tokens；保留当前数据规范化、邻接图与DSL API。

- [x] 图谱提供可读关系画布、选中实体说明与真实来源标识，保留搜索/邻域/缩放/复位。
- [x] 规则按原文、规则输出与输入测试组织；只使用接口实际结果，不伪装发布或审批。
- [x] 验证：实体选择、搜索后复位、空/失败状态、规则生成/测试/保存交互与窄屏；新增参数失效、保存确认和错误详情回归。

## Task 4：公众与后台问答

Files: `AgentChat.vue`、`workbench.css`；必要时调整既有依据与结果组件样式。

Interface: AgentChat `workspace: Boolean = false`；`/workbench`传true，`/agent`传false。

- [x] 公众独立品牌页头和18px正文；后台沿用横向导航，提供会话管理、附件与数据库设置。
- [x] 保留原有请求/存储逻辑；公众不请求或呈现数据库连接，公众请求不携带工作人员所选连接。
- [x] 空态、逐步输出、失败保留、停止、历史答复来源均可观察。
- [x] 验证：普通及流式回答、两类入口与会话、引用展开、停止/失败与手机输入区域。保留原有输入法处理，本轮未做物理输入法设备测试。

## Task 5：全貌交付与复核

- [x] 提供全貌查看页和实际运行路由；桌面/手机截图查看后台、文档、图谱、规则与两种问答。
- [x] 运行 `npm run check`、现有数据边界检查；用隔离接口资料验证前端，不将样本写入生产。
- [x] 主Agent查看截图后，完成独立视觉、UX及代码复核，修复影响使用的问题。
- [x] 更新DESIGN.md、实施记录与决定笔记，明确实际服务联调边界。

结果与证据见 `docs/frontend-audit/modern-implementation.md`；全貌入口为 http://127.0.0.1:8001/preview/preview.html 。实际8000后端未启动，隔离验证不等同于真实模型、数据库、解析或向量服务联调。
