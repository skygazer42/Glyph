# 清和知识库正式实现

用户2026-11-15在第09轮知识库四视图确认“可以实现了”。本轮迁移正式Vue知识库，并补其必要读取、字符切块和持久配置接口；不替换其它模块、不新增依赖。已有大量未提交文件，保留所有既有工作。

## 原型与项目映射

| 原型对象 | 现有项目 | 实现选择 |
| --- | --- | --- |
| 浅蓝灰导航/顶栏/品牌 | WorkspaceLayout/WorkbenchSidebar/GlyphMark | 用现成的，保留项目外壳与响应式抽屉 |
| 主蓝/字族/边框/圆角/间距 | variables.css 的 --wb-*、--spacing-*、--text-* | 用现成的，知识库工作面改白色 |
| 按钮/输入/下拉/表格/分页 | Element Plus | 用现成的 |
| 标签/tooltip/轻反馈/对话框 | Element Plus | 用现成的，关键反馈同时靠近操作显示 |
| 原文/解析/切块/索引视图 | 原KnowledgeBase详情对话框不足 | 新建 KnowledgeDocumentWorkspace 组件，父页负责列表/路由 |
| 导入配置和保留File草稿 | FileUploader自动上传不适合确认配置与分阶段恢复 | 新建 KnowledgeImportDialog，复用el-upload行为；真实请求结果驱动状态 |
| 真实请求/取消/错误 | knowledgeApi + axios request | 现成的加一个变体：工作区端点、显式取消与就地错误 |
| 原文件/页图/正文/字符预览/配置版本 | FastAPI已有upload/parse/embed | 现成的加一个变体：受控读取、源/解析版本、配置CAS与预览端点 |

## 落地顺序及验收

1. 完成接口契约与版本边界；不把内部文件路径当成公开URL。
2. 并行迁移导入、文档四视图与资料/检索页，复用Vue/Element Plus，不照搬原型脚本。
3. 离线API行为测试、前端编译检查、真实本地服务读取联通及浏览器流程验证。
4. 1440×900与390×844实际截图、与获批原型对照；独立一轮代码/视觉和UX核验，修复已知阻断。

上传、解析、保存配置与入库各有独立状态。载入页面不调用外部解析或向量写入；不替用户重建索引或删除资料。服务能力未开放的OCR/分级索引明确禁用，不冒充执行成功。测试使用临时资料/临时目录，不改用户已有PDF正文或索引。

## 写法规约对应

沿用 frontend-coding-guidelines 的 VUE-007/008（script setup与props/emits）、STA-001/002（服务器事实与局部草稿）、ASY-001/API-001（取消与现有请求客户端）、ERR-001/002（失败保留、成功确认）。新增声明按组件/请求/文档/切块领域命名；不为迁移引入通用状态框架。

## 最终实现与简化

- `web/src/views/KnowledgeBase.vue`：真实资料列表、筛选、手机资料卡、文档处理摘要、语义检索及路由上下文。移除旧详情弹窗，将文档处理集中到四视图工作区；概览直接从文档事实派生，避免为了显示计数初始化外部向量服务。
- `web/src/components/knowledge/KnowledgeDocumentWorkspace.vue`、`web/src/styles/knowledge-workspace.css`：原文分页/缩放/来源收起、完整解析正文对照、服务端字符切块与重叠、方案版本保存与读回、明确解析及入库。手机先读解析正文，原页按需对照；切块配置默认生成后收起，紧凑选择紧邻块全文。
- `web/src/components/knowledge/KnowledgeImportDialog.vue`：文件校验、批次和草稿、刷新重新选择、真实上传及配置/解析的分阶段重试；保留上传 ID，后续失败不会重复上传。不自动入库。
- `web/src/api/index.js`、`web/src/api/request.js`：复用 Axios 客户端，新增读取/预览/保存合同、取消与局部错误；AbortSignal 只传请求配置。
- `web/src/components/workbench/WorkspaceLayout.vue`、`web/src/styles/modules.css`：仅知识库工作面与上下文说明调整，沿用全局外壳、品牌和导航。
- `app/api/endpoints/knowledge.py`、`app/api/schemas.py`、`app/knowledge/document_workspace.py`：受控原文件、真实 PDF 页图、完整缓存正文、Unicode 字符预览、源与解析版本、OS 锁和配置 CAS。上传失败仅回滚本次创建且身份未变的文件；重新解析改变正文后入库标记失效。
- `app/knowledge/milvus.py`：现有实体构造增加显式 `upsert` 选项，默认插入行为保持。工作区用稳定文档 ID 和文档锁，重复入库、写入完成但标记失败后的重试不会生成新 ID，不重建共享分级索引。
- `tests/test_knowledge_workspace.py`：48 项离线 HTTP/存储回归，覆盖版本冲突、路径、真实页图、配置并发、上传恢复和入库幂等。
- `web/vite.config.js`、开发机 `web/.env.development.local`：代理可由 `GLYPH_API_PROXY_TARGET` 指定，缺省仍使用 8000。本机 8000 无法绑定，当前新增后端运行在 8002，正式前端 3001 代理到该进程；未停止原有 8001 服务。
- `DESIGN.md`：标明仅知识库已迁移第 09 轮，其余模块维持原实现。未新增依赖，未提交或重置其它已有变更。

## 最终验收证据

- 根任务运行 `python -X utf8 -m pytest tests/test_knowledge_workspace.py tests/test_python_guidelines_api_config.py tests/test_python_guidelines_knowledge_pipeline.py -q`：**217 passed**（12.95 秒）。退出时既有第三方 `ascii_colors` 关闭日志流警告不影响退出码。
- Ruff 检查指定 5 文件通过；Mypy 检查 4 个生产文件通过（`--follow-imports=silent --ignore-missing-imports --disable-error-code import-untyped`）；Bandit 和 compileall 通过。
- 最终 `npm run check --silent`：45 个维护源码通过，包括 27 个 Vue SFC。项目没有独立配置的前端 lint、TypeScript 类型检查或语义静态分析器，不以语法编译替代这些声明。
- 根任务实际浏览器 **32 项通过**：真实列表、PDF 翻页、TXT 导入/纯文本解析、草稿刷新、完整正文、Unicode 重叠、预览失效、保存读回、断网后中文反馈和重试、手机折叠/选择/原页适配。保存与检索失败通过隔离浏览器拦截请求验证；未调用外部向量检索或嵌入。详见 `.oil-ui/knowledge-implementation/verification/result.json`；可复跑脚本 `.oil-ui/knowledge-implementation/verify.mjs` 只创建和清理自身命名的 TXT。
- 标准取证包含资料、原文、解析、切块、索引及导入，1440×900 / 390×844 共 12 张，所有 `report.json` 均无 issues / lint。截图位于 `.oil-ui/knowledge-implementation/shots/`，原型—正式工程并排图为 `.oil-ui/knowledge-implementation/comparison/stitch.png`。
- 独立视觉评审指出的手机原页裁切、解析顺序与切块阅读优先级均已修正，由根重新查看实际图并操作验证。独立 UX 主路径、刷新读回与失败恢复完成，唯一 P3 英文网络错误已改为中文并通过真实浏览器故障复验。首轮报告：`knowledge-implementation-visual-review.md`、`knowledge-implementation-ux-review.md`。
- 自建联调及 UX 文档已清理，列表恢复原有 5 份资料；没有解析或入库既有用户文档。清理证据见 `.oil-ui/knowledge-implementation/ux/cleanup-evidence.json`。

## 能力与验证边界

原文/正文不能可靠逐页对应时展示完整正文，并明确不提供猜测页码。字符预览和配置不等于向量 token 切分或实际向量记录数。当前独立 OCR 控制、分级构建与后台持久任务队列没有对本工作区开放。

入库使用真实 Milvus upsert 链路，并有离线合同与失败回归；本轮没有实际调用外部 MinerU、模型、Milvus 或付费服务。历史随机 UUID 向量未查询、删除或迁移，新幂等机制不承诺自动清理已有重复向量。浏览器草稿保存文件元数据和选项，刷新后尚未上传的 File 内容需要用户重新选择。
