# 项目结构与命名

## 目录职责

```text
Glyph/
├── api_server.py                  前端使用的完整 /api/* 服务入口
├── app/
│   ├── main.py                    独立的 /query 等已有 API 入口
│   ├── api/                       HTTP 路由、请求契约和依赖装配
│   ├── agents/                    智能体、编排、规则与 Text2SQL
│   ├── config/                    应用及 AgentService 配置与默认值
│   ├── core/                      认证、日志与模型客户端
│   ├── domains/                   业务领域与政策规则
│   ├── knowledge/
│   │   ├── document_processor.py  文档解析处理（MinerU / LlamaIndex）
│   │   ├── document_workspace.py  原文、解析缓存、预览和处理配置
│   │   └── …                      文档加载、索引、检索与存储后端
│   ├── models/                    ORM 与政策领域模型
│   ├── schemas/                   共享输入输出契约
│   ├── persistence/               数据库连接、事务与 CRUD
│   └── utils/                     跨模块资源生命周期等工具
├── web/
│   ├── src/
│   │   ├── layouts/               应用外壳；WorkspaceLayout 为后台布局
│   │   ├── views/                 路由页面：咨询、登录、知识库、图谱、规则
│   │   ├── components/
│   │   │   ├── brand/             平台品牌图标
│   │   │   ├── consultation/      咨询操作、记录、附件、依据与测算结果
│   │   │   ├── knowledge/         知识库导入与文档工作区
│   │   │   ├── rules/             规则编辑布局
│   │   │   └── …                  可复用组件
│   │   ├── assets/                SVG 等静态资源
│   │   ├── api/                   HTTP 客户端与接口调用
│   │   ├── composables/           Vue 组合逻辑
│   │   ├── stores/                Pinia 状态与认证
│   │   ├── router/                路由及工作人员访问控制
│   │   ├── styles/
│   │   │   ├── global.css         全局基础样式
│   │   │   ├── variables.css      颜色、字体等设计变量
│   │   │   ├── workspace-layout.css  后台外壳
│   │   │   ├── consultation.css   咨询页面
│   │   │   └── knowledge-workspace.css  文档工作区
│   │   └── utils/                 展示转换与导航等纯工具
│   └── scripts/                   静态检查器和前端回归脚本
├── scripts/                       CLI、初始化与运维命令
├── tests/                         Python 自动化测试
├── docs/                          当前文档、计划和历史审查记录
├── docker/                        容器入口脚本
├── examples/                      独立示例及外部参考
├── resources/
│   └── data/                      本地资料总目录（见该目录的 README.md）
│       ├── raw/                   搜集原件、官网网页、附件与用户原包
│       ├── process/               解析正文与处理结果
│       ├── policy_catalog/        来源、核验、导入清单与范围说明
│       ├── research/              从临时目录归档的检索与复核证据
│       ├── exports/               运行资料的本地导出快照
│       └── local-inventory.json   逐文件大小与 SHA-256 总清单
├── rules/                         现有规则资源
├── templates/                     规则模板
├── uploads/                       用户上传与文档处理产物
├── temp/                          临时运行数据
├── .env.example                   40 项常用配置模板
├── docker-compose.yaml            完整应用与依赖服务
└── docker-compose.dev.yaml        本地开发使用的独立依赖服务
```

后端模型、CRUD 合并和内部依赖方向沿用 [Python 代码与目录约定](PYTHON_STRUCTURE.md)。具有独立资源生命周期的解析器、数据库和检索后端分别保留，不为统一目录外观合并它们。

## 文件命名

- Python 文件、函数和变量使用 `snake_case`；文件名表示职责，例如 `document_processor.py`、`agent_cli.py`。
- Vue 组件和路由页面使用 `PascalCase.vue`。组件放到实际功能所有者目录，跨页面的品牌放在 `brand/`，应用布局放在 `layouts/`。
- CSS 使用职责明确的 `kebab-case.css`，避免含义过宽的 `modules.css`。
- 当前路由页面名继续使用 `AgentChat.vue`、`StaffLogin.vue`、`KnowledgeBase.vue`、`KnowledgeGraph.vue`、`DSLGenerator.vue`；对应 URL 和认证规则不随目录整理改变。
- 不添加纯转发的旧路径兼容文件。外部 Python 调用方及本地命令需要按下表更新。

## 本轮迁移

| 原路径 | 当前路径 |
| --- | --- |
| `web/src/components/workbench/WorkspaceLayout.vue` | `web/src/layouts/WorkspaceLayout.vue` |
| `web/src/components/workbench/PlatformMark.vue` | `web/src/components/brand/PlatformMark.vue` |
| `web/src/components/workbench/ConsultationActions.vue` | `web/src/components/consultation/ConsultationActions.vue` |
| `web/src/components/workbench/PolicyEvidence.vue` | `web/src/components/consultation/PolicyEvidence.vue` |
| `web/src/components/workbench/SubsidyResultCard.vue` | `web/src/components/consultation/SubsidyResultCard.vue` |
| `web/src/components/SessionManager.vue` | `web/src/components/consultation/SessionManager.vue` |
| `web/src/components/FileUploader.vue` | `web/src/components/consultation/FileUploader.vue` |
| `web/src/components/Text2SQLResult.vue` | `web/src/components/consultation/Text2SQLResult.vue` |
| `web/src/styles/modules.css` | `web/src/styles/workspace-layout.css` |
| `web/src/styles/workbench.css` | `web/src/styles/consultation.css` |
| `app/knowledge/doc_enhanced.py` | `app/knowledge/document_processor.py` |
| `scripts/unified_cli.py` | `scripts/agent_cli.py` |
| `docker-compose_dev.yaml` | `docker-compose.dev.yaml` |

已删除没有路由或应用调用的旧首页 `HomePage.vue`、其专属 `SystemAnnouncement.vue`、旧侧栏 `WorkbenchSidebar.vue` 及其专属 `GlyphMark.vue`。当前咨询、知识库、图谱和规则页面继续使用现有实现。

历史审查目录、设计截图和旧计划记录当时的文件路径，不批量改写。维护当前代码时以本表为准。

## 启动入口

在仓库根目录执行：

```bash
# 本机开发的数据库等依赖服务
docker compose -f docker-compose.dev.yaml up -d

# 前端使用的完整后端 API
python -m uvicorn api_server:app --reload --env-file .env

# 前端开发服务器
npm --prefix web run dev

# 命令行咨询
python -m scripts.agent_cli --interactive

# 完整 Docker 应用
docker compose up -d --build web
```

`app/main.py` 提供另一套已有协议，与 `api_server.py` 的路由、认证和响应不同，分别保留。数据初始化和归档命令继续位于 `scripts/`，使用 `python -m scripts.<模块>`；本次目录整理不运行这些数据操作。

## 配置模板

`.env.example` 保留 40 个常用字段，每项上方有中文注释。实际 `.env` 和 `.env.*.local` 是本地运行配置，整理模板不会修改它们。

下面 10 项从模板省略，沿用已有代码默认值；确有需要时仍可在 `.env` 中覆盖，无需修改配置类：

| 字段 | 代码默认值 |
| --- | --- |
| `DATABASE__MILVUS_DB_NAME` | `default` |
| `DATABASE__MILVUS_COLLECTION_NAME` | `policy_documents` |
| `MINERU_MODE` | `auto`，有密钥用官方服务，否则用本地服务 |
| `MINERU_API_BASE_URL` | `http://localhost:30001` |
| `LLAMAINDEX_CHUNK_SIZE` | `1000` |
| `LLAMAINDEX_CHUNK_OVERLAP` | `200` |
| `RERANKER_BACKEND` | `dashscope` |
| `RERANKER_MODEL` | `gte-rerank-v2` |
| `RERANKER_ENDPOINT` | `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank` |
| `KNOWLEDGE_MAX_CONTEXT_PER_DOC` | `6000` |

其余进阶配置的实际默认值位于 `app/config/` 及对应功能的环境变量读取处。模板继续显式关闭视觉、MinerU、混合检索、重排和联网等可选能力，启用前填写所需配置。

Docker 构建排除本地覆盖配置、工具状态、设计过程产物、前端构建结果和临时数据；运行时业务资料仍沿用原目录和挂载方式。

## 本地资料管理

[资料总目录](../resources/data/README.md) 统一说明原件、解析件、来源清单和研究证据。采集数据、导出快照、向量索引和上传文件由 Git 忽略；总清单仅本地保留。已被 Git 跟踪的历史样例不会因新增忽略规则自动取消跟踪，本轮没有修改索引或历史。

`uploads/`、`resources/faq/` 和现有 LightRAG 工作目录继续作为应用运行位置，避免改变文档 ID、来源路径和模型配置；FAQ 在 `data/exports/` 另留快照。Docker Compose 通过现有 `resources/` 与 `uploads/` 挂载读取这些本地资料，不将完整采集语料打入镜像。
