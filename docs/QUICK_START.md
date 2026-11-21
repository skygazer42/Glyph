# 快速启动指南

在仓库根目录执行命令。默认开发方式是 Docker 运行 MySQL、Milvus 和 Redis，本地运行 Python API 与 Vue 网页；以下批量资料导入步骤由使用者显式执行。另行配置 `LIGHTRAG_SEED_DATA_DIR` 时，AgentService 初始化会检查种子清单并可能自动导入图谱。

## 环境与配置

建议使用 Python 3.10、Node.js 20+、Conda 和 Docker Compose。运行依赖见 [requirements.txt](../requirements.txt)，前端依赖见 [package.json](../web/package.json)。

首次使用时创建配置；已有 `.env` 时编辑原文件，避免覆盖本地密钥。

```powershell
Copy-Item .env.example .env
```

[模板](../.env.example) 包含 40 个逐项中文注释的字段。首先填写：

| 配置 | 如何填写 |
| --- | --- |
| `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME` | 对话模型密钥、兼容接口地址和模型名；AgentChat 工具编排需要服务支持工具调用。 |
| `EMBEDDING_BACKEND` 与对应字段 | `openai` 使用 OpenAI 兼容向量接口，`dashscope` 使用百炼原生向量服务；只填写所选后端的配置。 |
| `EMBEDDING_DIM` | 与实际模型输出及 Milvus 集合维度一致。不能通过更换维度继续使用不兼容的已有集合。 |
| `DATABASE__MYSQL_*` | 与实际 MySQL 连接一致。开发 Compose 在新建数据卷时创建 `glyph / glyph` 应用账号、`policy_db` 数据库，并映射到本机 `3307` 端口。 |
| `SECURITY__API_DEFAULT_USERNAME`、`SECURITY__API_DEFAULT_PASSWORD` | 自行设置工作人员账号和强密码，项目没有内置登录账号。 |
| `SECURITY__JWT_SECRET_KEY` | 至少 32 个 UTF-8 字节的随机签名密钥，工作人员登录与公众会话都需要。 |

开发 Compose 的数据库密码是本地开发示例，部署时须同步调整 Compose 和应用配置；已有数据卷的账号密码不会因修改初始化环境变量自动变化。HTTPS 部署设置 `SECURITY__AUTH_COOKIE_SECURE=true`。[完整认证说明](AUTHENTICATION.md)

### 使用硅基流动

在 `.env` 中将以下项目替换为所选模型和自己的密钥。密钥占位文字需要替换，不作为有效配置。

```dotenv
LLM_API_KEY=填写自己的密钥
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL_NAME=填写当前可用且支持工具调用的对话模型名
EMBEDDING_BACKEND=openai
EMBEDDING_OPENAI_API_KEY=填写自己的密钥
EMBEDDING_OPENAI_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_OPENAI_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
```

模型可用性、配额及权限以服务方当前账号为准。更换向量模型时，即使维度相同也应重建对应索引，避免混用不同模型的向量。

## 启动本地应用

创建 Python 环境并安装依赖：

```powershell
conda create -n glyph python=3.10 -y
conda activate glyph
python -m pip install -r requirements.txt
```

启动依赖服务；Milvus 的 etcd 和 MinIO 也会一并启动。

```powershell
docker compose -f docker-compose.dev.yaml config --quiet
docker compose -f docker-compose.dev.yaml up -d
docker compose -f docker-compose.dev.yaml ps
```

等待 MySQL 和 Milvus 可用，再创建 ORM 表并启动完整 API：

```powershell
python -m scripts.create_tables
python -m uvicorn api_server:app --reload --env-file .env
```

`create_tables` 创建缺失的 ORM 表，不迁移已有表结构，也不导入全部业务资料。另一套 `app/main.py` API 保留不同协议；当前网页应连接 `api_server:app`。

新开终端，在仓库根目录启动网页：

```powershell
npm --prefix web ci
npm --prefix web run dev
```

默认网页地址为 [localhost:3000](http://localhost:3000/)，后端接口文档为 [localhost:8000/docs](http://localhost:8000/docs)。Vite 端口被占用时可能选择下一个端口，以实际终端输出为准。

前端通过同源 `/api` 代理访问后端，默认目标为 `http://localhost:8000`。如果后端使用其他端口，在 `web/.env.development.local` 设置 `GLYPH_API_PROXY_TARGET=http://127.0.0.1:实际端口` 并重启 Vite；已有 `.env.local` 或 `.env.development.local` 时先核对其覆盖值。

## 初始化与资料导入

空向量集合需要先入库资料，创建数据库表不会使政策自动可检索。可从工作人员知识库上传 PDF、DOCX、TXT 或 Markdown，核对解析结果后显式入库。

完整采集语料仅保存在本机，不随源码提交。源码克隆不包含本地原包、官网附件和完整来源清单；可上传自己的政策资料，或先恢复已有的 `resources/data/` 归档。目录职责与清单见[本地资料总目录](../resources/data/README.md)。

需要批量导入已有本地归档时，先用少量资料检查解析范围。下面的预览命令不写入向量库：

```powershell
python -m scripts.embed_process_documents --input-dir resources/data/process --limit 10 --dry-run
```

确认输入目录和模型配置后执行向量化。该步骤会调用向量服务并写入当前配置的集合；`--limit 10` 仅导入读取顺序中的前 10 份资料。

```powershell
python -m scripts.embed_process_documents --input-dir resources/data/process --limit 10
```

其他能力按用途单独建立：

| 需要什么 | 命令与效果 |
| --- | --- |
| Text2SQL 的政策业务数据 | `python -m scripts.seed_mysql_text2sql`：根据来源目录写入政策和 FAQ 数据及相应业务表；随后执行 `python -m scripts.sync_text2sql_schema` 登记连接并刷新结构元数据。 |
| LlamaIndex 分级索引 | `python -m scripts.embed_documents --data-dir resources/data/process --storage-dir resources/storage/hierarchical --no-llm`：显式构建索引后再开启 `SYSTEM__HYBRID_RETRIEVAL_ENABLED`。 |
| LightRAG 图谱 | `python -m scripts.seed_lightrag --input-dir resources/data/process`：调用模型与向量服务构建图谱，写入配置指定的工作目录；图谱页读取其中的 GraphML。 |
| 常州专项来源与分段导入 | 查看 [资料目录](../resources/data/policy_catalog/README.md) 和 [专项导入脚本](../scripts/import_changzhou_policies.py)，按对应清单和核验步骤执行。 |

整套初始化还可使用 `./scripts/init_data.ps1 -NoPrompt`（Windows）或 `bash scripts/init_data.sh`（Bash）。它们会依次执行建表、业务数据、元数据、向量及图谱操作，部分步骤失败可能继续运行；应检查各步输出，不能只凭脚本结束判断全部入库成功。重复导入、重建索引和清库属于不同操作，不用删除数据来解决普通启动问题。

网页切块预览与脚本分段导入不是同一写入路径。当前网页入库按整篇解析正文写入；按文档覆盖 OCR 和网页构建分级索引尚未开放。[实际能力边界](TECH_STACK_OVERVIEW.md#文档工作区与索引)

## 完整容器编排

[docker-compose.yaml](../docker-compose.yaml) 定义 MySQL、Milvus、Redis、API 和 Nginx 网页。当前文件的 `web.build.context` 为 `./web`，而 `dockerfile` 为 `./web/Dockerfile`；Compose 按构建上下文解析 Dockerfile，因此完整构建前需将该字段调整为 `Dockerfile`。

完成上述路径调整并填好 `.env` 后，可校验和启动：

```powershell
docker compose config --quiet
docker compose up -d --build web
docker compose logs -f api
```

容器网页默认在 [localhost:8080](http://localhost:8080/)。[容器入口](../docker/entrypoint.sh) 在缺少 `/app/.initialized` 时执行建表、业务资料、向量及图谱初始化；这会调用模型服务并写数据。LightRAG 导入失败允许继续启动，因此 API 可访问不代表图谱已构建完成。

该初始化标记位于容器文件系统，重建容器后可能重新执行初始化；它不是已建立数据库的迁移版本。当前入口等待数据库时使用固定开发用 root 凭据，调整数据库凭据时还需要同步该入口。生产部署前应核对这些初始化行为，不能将此开发编排视为已验证的生产升级流程。

## CLI 与检查

在已激活的 Python 环境中运行命令行咨询：

```powershell
python -m scripts.agent_cli --help
python -m scripts.agent_cli --interactive
```

检查 API 进程与前端：

```powershell
Invoke-RestMethod http://localhost:8000/api/health
npm --prefix web run check
npm --prefix web run build
```

`/api/health` 只返回进程标识和版本，不检测 MySQL、Milvus、图谱或模型服务。前端 `check` 检查语法、Vue 编译与依赖声明一致性，不替代浏览器交互验收。

需要运行 Python 测试时，先在开发环境安装 [requirements-dev.txt](../requirements-dev.txt)，再运行 `python -m pytest tests -q`。网络用例默认排除；不同测试还可能需要额外服务，实际检查范围以测试配置和运行输出为准。
