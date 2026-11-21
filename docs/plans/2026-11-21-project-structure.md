# Glyph 配置与项目结构整理计划

**Goal:** 将配置模板精简到 40 个有独立中文注释的常用字段，让文件名和目录准确表达维护职责，保持现有路由、API 与数据行为。

**Architecture:** 延续 `docs/PYTHON_STRUCTURE.md` 已有后端分层，不合并两套 ASGI 应用。前端按真实职责划分布局、品牌和咨询组件，直接迁移并更新调用方，不添加旧路径转发层。

**Tech Stack:** Python / FastAPI、Vue 3 / Vite、Docker Compose；不新增依赖。

## 范围与约束

- 当前工作区有大量未提交修改，移动当前文件内容，不从 Git HEAD 重建文件。
- 实际 `.env`、本地模型覆盖配置、上传文件、数据库、政策与规则资料保持原样。
- 历史审计报告和截图保留旧路径，现行文档与可执行检查同步新路径。
- 不自动提交，不执行数据初始化、迁移或外部模型调用。

## 迁移清单

| 原路径 | 新路径 | 原因 |
| --- | --- | --- |
| `web/src/components/workbench/WorkspaceLayout.vue` | `web/src/layouts/WorkspaceLayout.vue` | 后台应用布局 |
| `web/src/components/workbench/PlatformMark.vue` | `web/src/components/brand/PlatformMark.vue` | 登录、咨询、后台复用品牌 |
| `web/src/components/workbench/ConsultationActions.vue` | `web/src/components/consultation/ConsultationActions.vue` | 咨询操作 |
| `web/src/components/workbench/PolicyEvidence.vue` | `web/src/components/consultation/PolicyEvidence.vue` | 咨询依据 |
| `web/src/components/workbench/SubsidyResultCard.vue` | `web/src/components/consultation/SubsidyResultCard.vue` | 测算结果 |
| `web/src/components/SessionManager.vue` | `web/src/components/consultation/SessionManager.vue` | 咨询记录 |
| `web/src/components/FileUploader.vue` | `web/src/components/consultation/FileUploader.vue` | 咨询附件 |
| `web/src/components/Text2SQLResult.vue` | `web/src/components/consultation/Text2SQLResult.vue` | 咨询数据结果 |
| `web/src/styles/modules.css` | `web/src/styles/workspace-layout.css` | 后台布局样式 |
| `web/src/styles/workbench.css` | `web/src/styles/consultation.css` | 咨询界面样式 |
| `app/knowledge/doc_enhanced.py` | `app/knowledge/document_processor.py` | 多引擎文档处理职责 |
| `scripts/unified_cli.py` | `scripts/agent_cli.py` | AgentService 命令入口 |
| `docker-compose_dev.yaml` | `docker-compose.dev.yaml` | 开发依赖服务命名 |

## 执行顺序与验证

1. 保存当前 Git 状态和相关文件内容指纹到 `.omx/state/project-structure/`，记录原有修改。
2. 跑现有离线回归、前端脚本测试和生产构建；记录静态检查器的既有 SVG 失败。
3. 精简 `.env.example`：删除 10 项已有明确代码默认值的设置，每个保留字段上方写中文用途与单位。隔离真实 `.env` 验证配置加载及被省略默认值。
4. 移动前端文件，同步全部现行导入和样式引用；保留路由 URL、DOM 类名、Teleport 目标及其生命周期。继续保留独立可复用组件，不为减少文件数合并无关职责。
5. 移动后端处理器、CLI 和 Compose 文件，同步测试装载路径、代码导入及当前启动文档。
6. 修复检查器对 SVG 的解析覆盖，复用已有 Vue DOM 解析器，未知文件类型继续报错。
   删除经源码、路由和配置引用核对均无入口的 `HomePage.vue`、`SystemAnnouncement.vue`、`WorkbenchSidebar.vue` 和其专属 `GlyphMark.vue`；保留其他通用组件。Docker 构建排除本地密钥覆盖文件及过程产物，README 以单一模板为准，移除重复配置大块。
7. 重跑同批回归、前端静态检查/测试/构建、CLI `--help`、Compose 配置校验与改动文件静态检查；核对无失效内部引用、无新增依赖、敏感文件指纹不变。
8. 将实际结果、目录约定及入口写入 `docs/PROJECT_STRUCTURE.md` 和 README。

## 验证命令

```powershell
python -m pytest tests/test_package_imports.py tests/test_knowledge_workspace.py tests/test_python_guidelines_api_config.py tests/test_python_guidelines_knowledge_pipeline.py tests/test_python_guidelines_tooling.py -q
node --test web/scripts/*.test.mjs
node web/scripts/check.mjs
cd web
npm run build
cd ..
python -m scripts.agent_cli --help
docker compose -f docker-compose.dev.yaml config --quiet
```

前端没有配置独立 lint 或 TypeScript 检查；使用现有语法、Vue 编译及生产构建，不声称存在未运行的检查。现有后端失败先与基线比较，再判断是否属于本次整理。

## 改动前基线

- 选定后端回归：319 通过、7 失败；其中 5 项为既有测试未创建解析或状态目录，2 项为 Milvus 测试替身维度不匹配。完整输出位于 `.omx/state/project-structure/pytest.before.log`。
- 前端 11 个脚本测试通过；Vite 生产构建通过，有既有大包提示。
- 前端静态检查器在现有 `assets/platform-mark.svg` 处失败；本次修复该格式覆盖。

## 完成与验证结果

- 13 项迁移完成；迁移文件逐个反向归一化引用后与本轮初始内容指纹一致。删除 4 个无入口的旧文件，没有添加转发层或依赖。
- 模板 40 个唯一字段均有独立中文注释；35 个配置模型字段和 5 个直接读取的开关全部识别，10 个省略项的默认值在隔离真实 `.env` 的进程中验证。
- 前端脚本 11 项及政策展示契约 3 项通过；55 个维护文件的静态检查通过，生产构建通过，保留既有的大包提示。
- 8 个改动 Python 文件 Ruff 通过；4 个应用模块 Python 3.10 语法检查通过。Mypy 在关闭第三方 `import-untyped` 诊断后通过；当前环境缺少 `requests` 类型桩，未安装新依赖。
- CLI `--help` 和开发 Compose 配置校验通过，未启动容器或执行数据操作。
- 后端同批回归为 318 通过、8 失败。原有 7 项继续失败；额外出现的并发用例也在逐文件匹配初始指纹的旧代码副本中复现，属于既有不稳定项。本轮不改文档锁和测试替身行为。
- `.env`、`.env.siliconflow.local` 和前端依赖声明指纹不变。过程中另有工作更新了 `faq_responder.py`、`retire_changzhou_files.ps1`、`seed_mysql_text2sql.py`，本轮没有写入或撤销它们。
- 完整机器可读结果：`.omx/state/project-structure/verification.json`。未运行全量后端测试、浏览器交互验收、数据库迁移或真实模型调用。
