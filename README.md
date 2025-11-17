# Glyph - 政策智能问答系统

<div align="center">

**基于 AutoGen Core 的企业级政策分析与问答系统**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[功能特性](#功能特性) • [快速开始](#快速开始) • [系统架构](#系统架构) • [部署指南](#部署指南) • [开发文档](#开发指南)

</div>

---

## 简介

Glyph 是一个企业级政策智能问答系统，专为政府机构和企业提供精准的政策咨询服务。系统采用多Agent协作架构，结合知识图谱、向量检索和大语言模型，实现政策文档的深度理解和智能问答。

### 核心能力

- **多Agent协作** - 意图识别、知识检索、政策分析、答案生成等专业化智能体
- **混合检索** - 向量检索(Milvus) + 知识图谱(LightRAG) + 规则引擎(DSL)
- **多轮对话** - 上下文理解与会话管理
- **Text2SQL** - 自然语言转SQL查询
- **结构化提取** - 政策要素自动抽取(资格、流程、时间、材料等)
- **置信度评估** - 多维度答案质量评估与早停机制 ([置信度详解](docs/CONFIDENCE_EXPLAINED.md) | [早停机制详解](docs/EARLY_STOP_EXPLAINED.md))
- **RESTful API** - 完整的后端服务接口

---

## 功能特性

### 1. 智能路由系统

```
用户查询 → 意图识别 → 智能路由 → 专业Agent → 答案生成
```

支持的意图类型：
- **政策查询** (`policy_inquiry`) - 资格、流程、截止日期等
- **政策对比** (`comparison`) - 多个政策的对比分析
- **政策摘要** (`summary`) - 政策概述与关键信息提取
- **金额计算** (`calculation`) - 补贴金额估算
- **数据查询** (`database_query`) - SQL数据库查询
- **对话交互** (`chit_chat`) - 问候、闲聊等

### 2. 多引擎检索

| 引擎 | 适用场景 | 技术栈 |
|------|---------|--------|
| **向量检索** | 语义相似度查询 | Milvus + OpenAI/DashScope Embeddings |
| **图谱检索** | 关系推理、概念关联 | LightRAG (Neo4j-like graph) |
| **规则引擎** | 确定性计算、条件判断 | YAML DSL + PolicyEngine |
| **SQL查询** | 结构化数据查询 | ChatDB (Text2SQL) |

**智能早停机制** ⚡:
- **触发条件**: 向量检索置信度 ≥ 80% (可配置 `EARLY_STOP_CONF`)
- **优化效果**: 跳过重排序和深度分析,直接生成答案
- **性能提升**: 响应时间减少 30-50%,API 调用成本降低
- **质量保证**: 仅对高置信度检索结果启用,确保答案准确性

```python
# 示例：高置信度查询触发早停
查询: "家电以旧换新补贴标准是多少？"
检索置信度: 92% ✅
→ 早停触发,跳过重排序
→ 直接生成答案 (节省 ~0.8s)
```

### 3. Agent架构

```mermaid
graph TB
    %% ========================================
    %% 第一层: 问候/闲聊快速检测 → Dialogue
    %% ========================================
    U[👤 用户查询] --> H0{💬 问候/闲聊?}
    H0 -->|✅ 是| D1[💭 DialogueAgent<br/>对话助手<br/><small>问候/寒暄</small>]
    H0 -->|❌ 否| D0{🎯 FAQ 命中?<br/><small>标签/相似度</small>}
    D0 -->|✅ 是<br/><small>直接返回</small>| Z[📤 最终答案<br/><small>路由+引用</small>]

    %% ========================================
    %% 第三层: 智能路由 (黄色系)
    %% ========================================
    D0 -->|❌ 否| S0[📝 SessionManager<br/>上下文管理<br/><small>最近5轮历史</small>]
    S0 --> S1[✏️ RewriteAgent<br/>查询改写<br/><small>业务化 + 缓存</small>]
    S1 --> S2[🗺️ PolicyDomainContext<br/>领域识别<br/><small>地区/关键词/时间</small>]
    S2 --> R0{⚡ FastPath 路由<br/><small>规则+正则匹配</small>}

    %% FastPath 快速路由分支
    R0 -->|🔍 澄清<br/><small>缺少要素</small>| C1[❓ Clarifier<br/>澄清助手<br/><small>三要素清单</small>]
    C1 -.->|重新提问| U

    R0 -->|💰 计算<br/><small>补贴金额</small>| D4[📊 RuleEngine<br/>规则引擎<br/><small>YAML DSL</small>]
    R0 -->|🗄️ SQL<br/><small>数据查询</small>| D5[🔎 Text2SQLAgent<br/>SQL引擎<br/><small>NL→SQL</small>]
    R0 -->|🕸️ 图谱<br/><small>关系推理</small>| D3[🌐 GraphAgent<br/>图谱引擎<br/><small>LightRAG</small>]
    R0 -->|🔧 工作流<br/><small>复杂任务</small>| D6[⚙️ WorkflowAgent<br/>编排引擎<br/><small>并行执行</small>]

    %% FastPath 未命中 → LLM意图分类
    R0 -->|🤔 未知<br/><small>需LLM分类</small>| IR[🧠 IntentRouter<br/>意图识别<br/><small>LLM分类</small>]

    %% ========================================
    %% 第四层: LLM 意图分发 (蓝色系)
    %% ========================================
    IR -->|💬 闲聊| D1
    IR -->|📚 知识| D2[📖 KnowledgeAgent<br/>知识检索<br/><small>向量+重排</small>]
    IR -->|🕸️ 图谱| D3
    IR -->|💰 计算| D4
    IR -->|🗄️ SQL| D5
    IR -->|🔧 工作流| D6

    %% ========================================
    %% 第五层: KnowledgeAgent 子流程 (含早停)
    %% ========================================
    D2 --> K1[🔍 Milvus/LlamaIndex<br/>向量检索<br/><small>Top-K相似文档</small>]
    K1 --> EC{✨ 早停检查<br/>置信度≥80%?<br/><small>EARLY_STOP_CONF</small>}

    EC -->|✅ 是<br/><small>高置信度</small>| KF[⚡ 快速抽取<br/>要点提取<br/><small>节省30-50%时间</small>]
    EC -->|❌ 否<br/><small>需深度分析</small>| K2[🔄 Reranker<br/>重排序<br/><small>+LLM总结</small>]

    KF --> A0[📝 AnswerComposer<br/>答案合成器<br/><small>格式化输出</small>]
    K2 --> A0

    %% ========================================
    %% 第六层: 其他Agent汇入答案合成器
    %% ========================================
    D3 --> G1[🌐 LightRAG<br/>图谱查询<br/><small>Naive/Local/Global/Hybrid</small>]
    G1 --> A0
    D4 --> A0
    D5 --> A0
    D6 --> A0

    %% ========================================
    %% Text2SQLAgent 子流程
    %% ========================================
    subgraph Text2SQL_Subgraph [🔎 Text2SQLAgent 详细流程]
        TS1[📋 Schema Analyzer<br/>表结构分析<br/><small>检索相关表和列</small>]
        TS2[🔧 SQL Generator<br/>SQL生成<br/><small>NL→SQL转换</small>]
        TS3[✅ Query Executor<br/>查询执行<br/><small>安全校验+执行</small>]
        TS4[📊 Result Formatter<br/>结果格式化<br/><small>JSON/表格/图表</small>]

        TS1 --> TS2
        TS2 --> TS3
        TS3 --> TS4

        %% 安全检查子流程
        TS3 --> TS5{🔒 安全检查}
        TS5 -->|❌ 非SELECT查询| TS6[❌ 拒绝执行<br/>仅允许SELECT查询]
        TS5 -->|❌ 注入风险| TS6
        TS5 -->|✅ 通过安全校验| TS7[✅ 执行查询]
        TS7 --> TS4
    end

    D5 -.-> Text2SQL_Subgraph
    Text2SQL_Subgraph -.-> A0

    %% ========================================
    %% 第七层: 统一后处理 (紫色系)
    %% ========================================
    A0 --> P1[🎁 后处理包装器<br/>统一格式化<br/><small>追加路由+引用+元数据</small>]
    D1 --> P1
    P1 --> Z

    %% ========================================
    %% 样式定义 (颜色编码)
    %% ========================================
    %% 问候/闲聊快速检测
    style H0 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px

    %% FAQ 短路 - 绿色
    style U fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style D0 fill:#c8e6c9,stroke:#388e3c,stroke-width:3px

    %% 入口/预处理 - 蓝色系（在 FAQ 未命中后）
    style S0 fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style S1 fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style S2 fill:#bbdefb,stroke:#1565c0,stroke-width:2px

    %% 智能路由 - 黄色系
    style R0 fill:#fff9c4,stroke:#f57f17,stroke-width:3px
    style C1 fill:#ffe0b2,stroke:#ef6c00,stroke-width:2px

    %% LLM意图路由 - 天蓝色
    style IR fill:#e1f5fe,stroke:#0277bd,stroke-width:3px

    %% Agent节点 - 浅色系
    style D1 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style D2 fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    style D3 fill:#e0f2f1,stroke:#00796b,stroke-width:2px
    style D4 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style D5 fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style D6 fill:#f1f8e9,stroke:#558b2f,stroke-width:2px

    %% 知识检索流程
    style K1 fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    style EC fill:#fff9c4,stroke:#f57f17,stroke-width:4px
    style KF fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    style K2 fill:#ffccbc,stroke:#d84315,stroke-width:2px

    %% 图谱节点
    style G1 fill:#e0f2f1,stroke:#00796b,stroke-width:2px

    %% 答案合成与后处理 - 橙色/紫色系
    style A0 fill:#ffe0b2,stroke:#e65100,stroke-width:3px
    style P1 fill:#ede7f6,stroke:#5e35b1,stroke-width:3px

    %% 最终输出 - 绿色高亮
    style Z fill:#a5d6a7,stroke:#1b5e20,stroke-width:4px

    %% Text2SQLAgent 子图样式
    style TS1 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style TS2 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style TS3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style TS4 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style TS5 fill:#ffecb3,stroke:#f57f17,stroke-width:3px
    style TS6 fill:#ffcdd2,stroke:#d32f2f,stroke-width:2px
    style TS7 fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
```

**架构图图例说明**:

| 图标 | 含义 | 说明 |
|-----|------|-----|
| 👤 | 用户入口 | 查询的起点 |
| 📝 📖 🔍 | 处理节点 | 各类Agent和工具 |
| 🎯 ⚡ ✨ | 决策节点 | 路由判断和优化检查 |
| ✅ ❌ | 条件分支 | 判断结果 |
| 💰 🗄️ 🕸️ | 路由标签 | 意图类型 |
| ⚡ | 性能优化 | 早停/快速通道 |
| 📤 | 最终输出 | 返回给用户的答案 |

**颜色编码**:
- 🔵 **蓝色系**: 预处理流程 (Session/Rewrite/Domain)
- 🟢 **绿色**: 快速通道 (FAQ命中/早停)
- 🟡 **黄色**: 智能路由决策 (FastPath/IntentRouter/早停检查)
- 🟣 **紫色**: 后处理包装 (格式化/引用/元数据)
- 🟠 **橙色**: 答案合成器 (最终答案生成)

**性能优化要点**:
1. **三级快速通道**: FAQ直达 → FastPath规则路由 → 知识检索早停
2. **最少LLM调用**: 优先使用规则/正则,仅在必要时调用LLM意图识别
3. **智能缓存**: RewriteAgent内置LRU缓存,减少重复改写
4. **并行执行**: WorkflowAgent支持多Agent并行,提升复杂查询速度

### 路由决策（从快到稳）

1) FAQ 短路（无需改写/模型）
- 原始问题命中 FAQ（标签包含或相似度≥FAQ_THRESHOLD）→ 直接返回。
- 可选：改写后再试一次（`FAQ_RETRY_ON_REWRITE=true`）。

2) 预处理（仅在不命中 FAQ 时）
- 最近 N 轮上下文（N=CONVERSATION__HISTORY_WINDOW，0 表示关闭记忆）。
- Rewrite 业务化改写（短句/具槽位直返；带 LRU 缓存）。

3) FastPath 路由（不调意图模型，能判就判）
- 有图片/票据且 Vision 开启 → Workflow。
- SQL 关键词 且 有 connection_id → Text2SQL。
- “是否符合/能否享受/是否有资格…” 且缺“类别/能效/价格” → Clarifier（三要素清单）。
- 同时包含“补贴/补助”+ 家电品类 + “价格（…元）” + “能效/水效” → RuleEngine（直接计算）。
- 关系/流程/脉络 → GraphAgent。否则再调用 LLM 意图分类。

4) 检索/生成与早停
- Knowledge：Milvus/LlamaIndex → 置信度≥EARLY_STOP_CONF 先走“要点抽取⚡”，否则再一次 LLM 总结。
- RuleEngine：YAML DSL 计算（输出 trace/封顶校验）。
- Text2SQL：表结构检索→SQL 生成→安全校验（仅 SELECT）→执行。
- Graph/Workflow：按场景执行，失败回退 Knowledge。

5) 统一后处理
- 每条答案尾部统一追加“【路由】xxx”“【引用】…”。metadata 附 routing_debug、domain_context、rule_id/sql/search_query 等。

### FAQ 策略（优先短路）

- 命中即答：先用“原始问题”匹配 FAQ，若标签包含命中或相似度 ≥ `FAQ_THRESHOLD`（默认 0.85），直接返回，不走改写/意图/检索。
- 改写后重试（可选）：`FAQ_RETRY_ON_REWRITE=true` 时，原文未命中才对“改写后问题”再尝试一次（提升口语化问法命中率）。
- 标签来源与维护：严格从 `resources/data/process` 文档抽取关键词作为 tags。若需要更新，可手动编辑 `resources/faq/qa_pairs.json`，确保引用真实文档语句，避免臆造。
- 适用场景：固定问法（“发放时间/面额/领取与使用/资料清单/有效期/封顶金额/是否可再次享受” 等）优先挂到 FAQ，减少大模型调用与响应时延。

### 可配置项（.env）

- `FAQ_THRESHOLD=0.85`：FAQ 相似度阈值。
- `FAQ_RETRY_ON_REWRITE=true`：改写后再试一次 FAQ。
- `CONVERSATION__HISTORY_WINDOW=5`：上下文窗口（轮数），设 0 关闭记忆。
- `EARLY_STOP_CONF=0.80`：知识检索早停阈值（≥ 阈值先走“要点抽取⚡”）。
- `WEB_SEARCH__ENABLED=false`：禁用联网兜底（更快更稳）。
- `SYSTEM__HYBRID_RETRIEVAL_ENABLED=true`：启用分级检索（需要本地索引）。

### 多轮对话记忆（可开关）

- 目的：让追问更连贯（类似 ChatGPT），例如“我是否符合？”→“二级能效空调 8000 元。”→“怎么办理？”。
- 策略：仅拼接“最近 N 轮≈2N 条消息”摘要到改写提示，避免提示过长与幻觉；
- 配置：`CONVERSATION__HISTORY_WINDOW=N`（默认 5；设 0 关闭记忆）。

### 延迟与成本优化
- 最少调用原则：FastPath + Rewrite 缓存 + 知识早停，能不用模型就不用。
- 控制上下文长度：仅拼接最近 N 轮，避免超长提示引发幻觉与耗时。
- 只允许安全 SQL：拒绝 DML/DDL/多语句/UNION，降低数据库风险与执行时间。


**14个核心Agent及其分工**:

| Agent | 功能 | 输出 |
|-------|------|------|
| **RewriteAgent** | 查询标准化与改写 | 结构化查询 |
| **IntentRouter** | 意图识别与路由决策 | 路由目标+置信度 |
| **DialogueAgent** | 闲聊、问候等对话交互 | 对话回复 |
| **KnowledgeAgent** | 向量检索+重排+政策分析 | 结构化政策信息 |
| **GraphAgent** | LightRAG图谱推理 | 实体关系网络 |
| **RuleEngine** | YAML DSL规则计算 | 补贴金额/资格判断 |
| **Text2SQLAgent** | 自然语言→SQL→执行 | 数据库查询结果 |
| **WorkflowAgent** | 多Agent并行协调 | 融合多源结果 |
| **PolicyAnalyzer** | 政策要素提取 | 资格/流程/金额/时间 |
| **PolicyComparator** | 多政策对比分析 | 对比表格 |
| **AnswerGenerator** | 答案生成与优化 | 最终答案+置信度 |
| **QueryAnalyzer** | 查询深度分析 | 查询特征向量 |
| **Clarifier** | 澄清与歧义消解 | 澄清问题 |
| **QuestionBuilder** | 问题构建 | 结构化问题 |

---

## 快速开始

### 环境要求

- Python 3.9 或更高版本
- MySQL 8.0（Text2SQL/会话存储）
- Milvus 2.4（向量检索）
- Node.js 18+（前端调试时需要）
- 8GB 以上内存，建议开启虚拟内存或使用 GPU 进行批量嵌入

### 本地安装步骤

1. **克隆代码并安装依赖**
   ```bash
   git clone <your-repo-url>
   cd Glyph
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **配置 `.env`**
   ```bash
   cp .env.example .env
   ```
   至少需要设置以下项：
   - `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME`
   - `EMBEDDING_BACKEND` 及对应的 API Key（OpenAI 或 DashScope）
   - `DATABASE__MYSQL_*` 与 `DATABASE__MILVUS_*`
   - `LIGHTRAG_WORKDIR`（默认即可）

3. **启动 MySQL 并初始化表**
   ```bash
   python scripts/1_create_tables.py
   ```

4. **启动 Milvus（示例使用官方 docker-compose）**
   ```bash
   wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
   docker-compose up -d
   ```

5. **启动 API**
   ```bash
   python api_server.py
   # 默认监听 http://localhost:8000
   ```

6. **健康检查**
   ```bash
   curl http://localhost:8000/health
   ```

### 使用 Docker 构建与运行

```bash
# 在项目根目录构建镜像（需要自行提供 Dockerfile）
docker build -t glyph-policy-qa:latest .

# 以 .env 中的配置启动容器
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name glyph-api \
  glyph-policy-qa:latest

# 进入容器以执行嵌入/导入脚本
docker exec -it glyph-api bash

# 停止并移除
docker stop glyph-api && docker rm glyph-api
```

（如需同时运行 MySQL、Milvus，可在宿主机或独立容器中启动，保持 `.env` 中的地址可达。）

### 导入示例数据

1. **生成 Text2SQL 数据库**
   ```bash
   sqlite3 resources/sql/policy_demo.db < resources/sql/policy_demo.sql
   python scripts/register_text2sql_connection.py  # 记录返回的 connection_id
   ```

2. **初始化知识库（DashScope 默认配置）**
   ```bash
   bash scripts/init_data.sh
   ```
   该脚本会依次运行 `scripts/1_create_tables.py`、`scripts/2_seed_mysql_text2sql.py`（自动应用 `policy_qa_schema.sql`）、`scripts/3_init_milvus.py`、`scripts/4_embed_documents.py`（构建 LlamaIndex 索引）、`scripts/5_embed_process_documents.py`（写入 Milvus），并尝试执行 `scripts/6_seed_lightrag.py`，保证 MySQL/Milvus/LightRAG 三条链路都初始化完成；若 `.env` 中 `SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`，会自动跳过 LlamaIndex 构建步骤。

3. **（可选）只需单独更新 LightRAG 可再次执行**
   ```bash
   python scripts/6_seed_lightrag.py --input-dir resources/data/process
   ```

4. **验证数据是否生效**
   - `python scripts/unified_cli.py --interactive` 可快速检索文档
   - `sqlite3 resources/sql/policy_demo.db ".tables"` 检查表已生成
   - `mysql -u root -p policy_db -e "SHOW TABLES"` 确认 `chatsession/chatmessage` 等表存在

### 自动化验证

1. **界面层脚本**
   ```bash
   ./run_50_tests.sh   # 选择模式 2 可顺序测试 42 条问题
   ```
   运行完成后会生成 `test_results_50_questions.{json,md}`，可用于校验路由与答案。

2. **单元与集成测试**
   ```bash
   pytest tests -q
   ```

3. **手动接口检查**
   ```bash
   curl -X POST http://localhost:8000/api/agent/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "家电以旧换新的补贴标准是什么？", "session_id": "demo"}'
   ```

### 交互式CLI

```bash
# 启动交互模式
python scripts/unified_cli.py --interactive

# 示例对话
> 家电以旧换新能补贴多少钱？

【政策分析】
补贴标准：
- 家电以旧换新最高补贴 2000 元
- 按新家电价格的 15% 补贴
- 不同品类补贴标准不同

来源：《济南市家电以旧换新实施细则》
置信度: 92.5%
```

---

## 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   用户接口层                          │
│  FastAPI REST API │ CLI │ 批处理接口                 │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│              AgentService (核心服务层)                │
│  • 会话管理  • 意图路由  • Agent编排  • 结果聚合      │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌───────▼──────┐
│  Agent Pipeline │  │ Tools Layer  │
│                 │  │              │
│ • RewriteAgent │  │ • KnowledgeTool (Milvus)  │
│ • IntentRouter │  │ • IntentTool (LLM分类)    │
│ • DialogueAgent│  │ • WebSearchTool (Tavily) │
│ • KnowledgeAgent│ │ • VisionTool (GPT-4V)    │
│ • GraphAgent   │  │ • UserProfileTool        │
│ • RuleEngine   │  │                          │
│ • Text2SQLAgent│  │                          │
│ • PolicyAnalyzer│ │                          │
│ • AnswerGenerator│ │                        │
└─────────────────┘  └─────────────────────────┘
         │
┌────────▼──────────────────────────────────────────┐
│                   存储层                           │
│  Milvus (向量) │ MySQL (结构化) │ LightRAG (图谱) │
└───────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术选型 |
|------|---------|
| **Web框架** | FastAPI 0.100+ |
| **Agent框架** | AutoGen Core |
| **LLM** | DeepSeek/OpenAI/Compatible APIs |
| **向量数据库** | Milvus 2.4+ |
| **关系数据库** | MySQL 8.0+ |
| **图数据库** | LightRAG (内置) |
| **嵌入模型** | OpenAI text-embedding-3 / DashScope |
| **重排序** | DashScope gte-rerank-v2 (可选) |

---

## 核心组件

### 1. RewriteAgent - 查询改写

**功能**: 将用户原始查询改写为结构化、明确的查询

```python
# 用户: "想买家电"
# 改写后: "家电以旧换新政策的申请条件和补贴标准"
```

### 2. IntentRouter - 意图路由

**功能**: 识别用户意图并选择合适的处理链路

**路由规则** (app/agents/service/agent_service.py:362-402):

```python
def _resolve_route(intent, query, ...):
    if intent == "chit_chat": return "dialogue"
    if intent == "calculation": return "rule_engine"
    if intent == "summary": return "graph"
    if intent == "comparison": return "knowledge"
    if looks_like_sql(query): return "text2sql"
    return "knowledge"  # 默认
```

### 3. KnowledgeAgent - 知识库检索

**检索流程**:
1. 向量检索 (Milvus) - 语义相似度Top-K
2. 重排序 (可选) - DashScope Reranker
3. 政策分析 - 结构化信息提取
4. 答案生成 - 模板化/LLM生成

### 4. GraphAgent - 图谱检索

**基于 LightRAG**:
- **Naive**: 简单文本匹配
- **Local**: 局部子图检索
- **Global**: 全局图谱推理
- **Hybrid**: 混合模式

**初始化状态**:
```bash
✅ LightRAG 已初始化
✅ 文档索引: 12 篇
✅ 数据目录: resources/data/lightrag/
```

### 5. RuleEngine - 规则引擎

**基于 YAML DSL**:

```yaml
# resources/dsl/rules/济南_家电补贴_2025.yaml
policy_meta:
  id: Rule_济南_家电补贴_2025
  name: 济南市2025年家电以旧换新补贴政策

eligibility:
  conditions:
    - field: user_location
      operator: in
      value: [济南市, 历下区, 市中区]
    - field: old_appliance_years
      operator: ">="
      value: 5

calculation:
  base_amount: 0
  rules:
    - condition: new_price >= 3000
      formula: "new_price * 0.15"
      max: 2000
```

### 6. Text2SQLAgent - 自然语言转SQL

**功能**: 将自然语言查询转换为SQL查询并执行

**处理流程图**:

```mermaid
graph TB
    Q[用户查询] --> D5[🔎 Text2SQLAgent<br/>SQL引擎<br/><small>NL→SQL</small>]

    D5 --> S1[📋 Schema Analyzer<br/>表结构分析<br/><small>检索相关表和列</small>]
    S1 --> S2[🔧 SQL Generator<br/>SQL生成<br/><small>NL→SQL转换</small>]
    S2 --> S3[✅ Query Executor<br/>查询执行<br/><small>安全校验+执行</small>]
    S3 --> S4[📊 Result Formatter<br/>结果格式化<br/><small>JSON/表格/图表</small>]
    S4 --> A[最终答案]

    style D5 fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style S1 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style S2 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style S3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style S4 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style A fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px
```

**流程说明** (app/agents/chatdb/):

```
用户查询 → Schema分析 → SQL生成 → 安全校验 → 执行 → 结果格式化
```

#### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **Schema Analyzer** | schema_retriever.py | 表结构检索与分析 |
| **SQL Generator** | sql_generator.py | NL→SQL转换 |
| **Hybrid Generator** | hybrid_sql_generator.py | 规则+LLM混合生成 |
| **Query Executor** | sql_executor.py | 安全执行SQL |
| **Result Formatter** | visualization_recommender.py | 结果格式化与可视化 |
| **Query Analyzer** | query_analyzer.py | 查询意图分析 |
| **Domain Context** | domain_zh_gov.py | 政策领域增强 |

#### 工作流程

**1. Schema分析阶段**:
```python
# 检索相关表结构
schema_context = retrieve_relevant_schema(
    query="家电类政策有哪些？",
    connection_id=1
)
# 返回: {
#   "tables": ["policies"],
#   "columns": ["id", "title", "category", "publish_date"],
#   "relationships": []
# }
```

**2. SQL生成阶段**:
```python
# 领域增强
domain_hints = {
    "time_window": parse_time_window(query),  # "近三个月"
    "aggregation": infer_aggregation(query),  # COUNT/SUM
    "order_by": "desc_time"
}

# 生成SQL
sql = generate_sql(
    query=query,
    schema_context=schema_context,
    domain_hints=domain_hints
)
# 生成: SELECT title, publish_date FROM policies
#       WHERE category = '家电'
#       ORDER BY publish_date DESC LIMIT 10;
```

**3. 安全校验阶段**:
```python
# 校验SQL安全性
if not validate_sql(sql):
    raise SecurityError("不安全的SQL")

# 安全规则:
# ✅ 仅允许 SELECT
# ❌ 拒绝 DML (INSERT/UPDATE/DELETE)
# ❌ 拒绝 DDL (CREATE/DROP/ALTER)
# ❌ 拒绝 UNION (防止注入)
# ❌ 拒绝多语句 (防止批量操作)
```

**4. 执行与格式化**:
```python
# 执行查询
result = execute_query(sql, connection_id, timeout=30)

# 格式化输出
formatted = format_result(
    result=result,
    query=query,
    sql=sql
)
# 返回: {
#   "data": [...],
#   "table": "| 标题 | 发布日期 |\n...",
#   "visualization": {"type": "table"},
#   "sql": "SELECT ...",
#   "row_count": 5
# }
```

#### 示例查询

**基础查询**:
```
用户: "一共有多少个政策文件？"
SQL: SELECT COUNT(*) FROM policies;
结果: {"count": 42}
```

**条件查询**:
```
用户: "家电类政策有哪些？"
SQL: SELECT title, publish_date FROM policies
     WHERE category = '家电'
     ORDER BY publish_date DESC LIMIT 10;
结果: [{"title": "济南市家电补贴政策", "publish_date": "2024-01-15"}, ...]
```

**时间范围查询**:
```
用户: "列出近三个月发布的政策标题及来源"
SQL: SELECT title, source, publish_date FROM policies
     WHERE publish_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
     ORDER BY publish_date DESC;
```

**聚合统计**:
```
用户: "按政策类型统计数量"
SQL: SELECT category, COUNT(*) as count FROM policies
     GROUP BY category
     ORDER BY count DESC;
结果: [
  {"category": "家电", "count": 15},
  {"category": "汽车", "count": 12},
  ...
]
```

#### 领域增强

**时间表达解析**:
- "最近3个月" → `>= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)`
- "2024年" → `>= '2024-01-01' AND < '2025-01-01'`
- "今年" → 当前年份范围

**术语映射**:
- "家电补贴" → `policy_type = '家电以旧换新'`
- "济南市" → `region = '济南市'`
- "发放情况" → 推断需要 `status` 字段

**意图推断**:
- "有多少" → 建议使用 `COUNT(*)` 聚合
- "列出" → 建议使用 `SELECT ... LIMIT`
- "统计" → 建议使用 `GROUP BY`

#### 配置项

```bash
# Text2SQL 配置
TEXT2SQL__MAX_TABLES=5          # 最大检索表数
TEXT2SQL__MAX_COLUMNS=50        # 最大列数
TEXT2SQL__QUERY_TIMEOUT=30      # 查询超时(秒)
TEXT2SQL__MAX_ROWS=1000         # 最大返回行数
TEXT2SQL__ENABLE_CACHE=true     # 启用缓存
TEXT2SQL__CACHE_TTL=3600        # 缓存过期时间(秒)

# 安全配置
TEXT2SQL__ALLOW_DML=false       # 禁止 DML 操作
TEXT2SQL__ALLOW_DDL=false       # 禁止 DDL 操作
TEXT2SQL__ALLOW_UNION=false     # 禁止 UNION 查询
```

#### 详细文档

完整的 Text2SQL 实现文档请参考: [app/agents/chatdb/README.md](app/agents/chatdb/README.md)

---

## 配置说明

### 完整 .env 配置

```bash
# ==================== LLM 配置 ====================
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_NAME=deepseek-chat
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=120

# ==================== 嵌入配置 ====================
# 向量检索嵌入 (KnowledgeTool)
EMBEDDING_BACKEND=openai  # openai | dashscope
EMBEDDING_OPENAI_API_KEY=sk-xxx
EMBEDDING_OPENAI_MODEL=text-embedding-3-small
EMBEDDING_DASHSCOPE_API_KEY=sk-xxx
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3

# LightRAG 嵌入 (GraphAgent)
EMBEDDING_DASHSCOPE_API_KEY=sk-xxx
EMBEDDING_DASHSCOPE_DIMENSION=1024

# ==================== Reranker 配置 (可选) ====================
RERANKER_BACKEND=dashscope
DASHSCOPE_API_KEY=sk-xxx
RERANKER_MODEL=gte-rerank-v2
RERANKER_TOP_N=5
RERANKER_STRATEGY=replace  # replace | fuse

# ==================== Milvus 配置 ====================
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
DATABASE__MILVUS_COLLECTION_NAME=policy_documents
DATABASE__MILVUS_USER=
DATABASE__MILVUS_PASSWORD=
DATABASE__MILVUS_DB_NAME=default
DATABASE__MILVUS_USE_SECURE=false

# ==================== MySQL 配置 ====================
DATABASE__MYSQL_HOST=localhost
DATABASE__MYSQL_PORT=3306
DATABASE__MYSQL_USER=root
DATABASE__MYSQL_PASSWORD=your_password
DATABASE__MYSQL_DATABASE=policy_qa

# ==================== LightRAG 配置 ====================
LIGHTRAG_WORKDIR=resources/data/lightrag
LIGHTRAG_QUERY_MODE=hybrid  # naive | local | global | hybrid
LIGHTRAG_EMBED_RETRY=3

# ==================== 多轮对话配置 ====================
CONVERSATION__MAX_TURNS=20
CONVERSATION__HISTORY_WINDOW=5

# ==================== 性能优化配置 ====================
EARLY_STOP_CONF=0.80  # 早停置信度阈值
ANALYZER_CONCURRENCY=3  # 政策分析并发数
```

---

## 性能优化

### 1. 向量检索优化

```python
# 使用 Reranker 提升准确率
RERANKER_BACKEND=dashscope
RERANKER_STRATEGY=fuse  # 融合向量分数和重排分数
RERANK_WEIGHT=0.7
FAISS_WEIGHT=0.3
```

### 2. LightRAG 优化

```bash
# 选择合适的查询模式
LIGHTRAG_QUERY_MODE=hybrid  # 混合模式，平衡速度和准确率
```

### 3. 并发控制

```python
# 限制分析并发数，避免API限流
ANALYZER_CONCURRENCY=3
```

---

## 测试

### 运行测试套件

```bash
# 单元测试
pytest tests/

# 集成测试
pytest tests/integration/

# Agent场景测试
python test_agent_scenarios.py

# LightRAG检索测试
python test_lightrag_retrieval.py
```

### 测试报告

查看 `AGENT_TEST_REPORT.md` 获取最新测试结果。

---

## 部署指南

### Docker 部署

```bash
# 构建镜像
docker build -t glyph-policy-qa:latest .

# 启动服务
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name glyph-api \
  glyph-policy-qa:latest
```

### 生产环境建议

1. **使用 Gunicorn/Uvicorn workers**:
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

2. **Nginx 反向代理**:
```nginx
upstream glyph_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://glyph_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **监控与日志**:
- 使用 Prometheus + Grafana 监控
- 集成 ELK/Loki 日志系统
- 配置健康检查端点 `/health`

---

## 开发指南

### 添加新的 Agent

1. **创建 Agent 类**:

```python
# app/agents/packs/my_agent/node.py
from app.agents.framework.base.base_agent import PolicyAgentBase
from app.models.base import AgentType, MessageType

class MyCustomAgent(PolicyAgentBase):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.CUSTOM,
            name="MyCustomAgent",
            description="自定义Agent功能描述"
        )

    async def _handle_user_query(self, message, ctx):
        # 处理用户查询
        return result

    async def _handle_query_analysis(self, message, ctx):
        # 处理查询分析
        return result
```

2. **注册到 AgentService**:

```python
# app/agents/service/agent_service.py
from app.agents.packs.my_agent.node import MyCustomAgent

class AgentService:
    def __init__(self):
        # ...
        self.my_custom_agent = MyCustomAgent()
```

3. **添加路由规则**:

```python
# app/agents/service/agent_service.py
def _resolve_route(self, intent_result, ...):
    if intent == "my_custom_intent":
        return "my_custom"
    # ...
```

### 添加新的意图

```python
# app/models/base.py
class QueryIntent(str, Enum):
    # 现有意图...
    MY_CUSTOM_INTENT = "my_custom_intent"
```

### 添加新的 DSL 规则

```yaml
# resources/dsl/rules/my_policy.yaml
policy_meta:
  id: Rule_MyPolicy_2025
  name: 自定义政策规则

eligibility:
  conditions:
    - field: age
      operator: ">="
      value: 18

calculation:
  rules:
    - condition: income < 50000
      formula: "base_amount * 1.5"
```

---

## 维护工具

### 清理临时文件

```bash
# 预览将删除的文件
bash scripts/clean.sh

# 实际执行清理
bash scripts/clean.sh --no-dry-run --yes
```

### 数据库维护

```bash
# 备份 MySQL
mysqldump -u root -p policy_qa > backup.sql

# 重建 Milvus collection
python scripts/rebuild_milvus.py
```

---

## 已知问题

### LightRAG 嵌入函数异步问题

**问题**: LightRAG 文档处理时出现 `TypeError: object list can't be used in 'await' expression`

**影响**: 部分文档的高级处理（知识图谱构建）失败，但基础检索功能正常

**状态**: 已识别，待修复

**解决方案**: 将嵌入函数改为异步函数

### 路由逻辑限制

**问题**: 当前只有 `summary` 意图才会路由到 LightRAG

**影响**: LightRAG 未被充分利用

**建议**: 扩展路由条件，将更多政策查询路由到 graph

---

## Roadmap

- [ ] 修复 LightRAG 异步嵌入问题
- [ ] 优化路由策略，提升 LightRAG 使用率
- [ ] 增加政策对比的可视化展示
- [ ] 支持多租户与权限管理
- [ ] 添加政策变更监控与通知
- [ ] 开发管理后台
- [ ] 支持更多数据源（PDF、Excel等）

---

## 贡献指南

我们欢迎所有形式的贡献！

### 贡献流程

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8
- 添加类型注解
- 编写单元测试
- 更新文档

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [AutoGen](https://github.com/microsoft/autogen) - 多Agent协作框架
- [LightRAG](https://github.com/HKUDS/LightRAG) - 轻量级知识图谱检索
- [Milvus](https://milvus.io/) - 向量数据库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Web框架
- [DeepSeek](https://www.deepseek.com/) - 大语言模型

---

 
 
<div align="center">


Made with care by the Glyph Team

</div>
