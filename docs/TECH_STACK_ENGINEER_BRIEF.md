# 智策通核心技术概览

## 多源融合
- 知识库+图谱+规则
##  动态更新
 - 使用n8n 定时抓取济南政策，并保存至 本地
## 文档解析与预处理

- 文档解析：MinerU 2.6 系列（PDF / Office → Markdown），支持在线 / 本地模式。  
- PDF 解析与图片处理：PyMuPDF + OCR（RapidOCR）辅助提取表格、图片文字。  
- 增强管线：优先尝试 MinerU，失败时回退本地解析，统一输出结构化文档对象。

## 检索与索引

- 向量检索：Milvus 2.4+，搭配 OpenAI / DashScope 等嵌入模型，用于语义 Top-K 检索。  
- 分层索引：LlamaIndex 分层快速索引（doc / section / chunk / summary 四层），提高长文档定位精度。  
- 分块策略（可配置）：
  - simple：按 token/字符长度滑窗分块；
  - sentence：按句子边界分句，再滑窗拼接；
  - keyword_aware：对包含关键政策词（补贴标准/申请条件等）的区域做语义扩展分块。
- 早停策略：基于检索置信度（EARLY_STOP_CONF）决定是否走“直接回答”通路以节省 LLM 调用。
- 支持向量召回，索引召回，BM25，以及混合召回

## 知识图谱与关系推理

- 图谱引擎：LightRAG（轻量级知识图谱）用于构建政策实体、地区、主体、上位文献等关系。  
- 查询模式：支持 naive / local / global / hybrid 多种图谱检索模式。  
- 场景：政策脉络、上下级文件追溯、流程链路推理等。

## 多智能体编排（AutoGen）

- 多 Agent 架构：基于 AutoGen Core 思路，将系统拆分为 RewriteAgent、IntentRouter、KnowledgeAgent、GraphAgent、RuleEngine、Text2SQLAgent 等专业智能体。  
-  分父图和子图 联调
- 意图支持槽位填充，快速路由
- 编排方式：集中路由服务负责意图识别、FastPath 规则路由、多路并发调用与结果聚合。  
- 会话能力：支持多轮对话上下文注入、业务化改写和 FAQ 短路。
- 安全护栏，sql验证
- 回答模式支持链路推理输出

## 规则引擎与 DSL

- 规则描述：YAML DSL 表达政策 ID、适用地区/人群、金额区间、封顶规则等。  
- 规则执行：RuleEngine 读取 DSL 做资格判断与补贴金额计算，结果可追溯、输出稳定。  
- 适用场景：家电以旧换新、消费券等“算得清楚”的业务政策。

## 结构化数据与 Text2SQL

- 数据存储：MySQL 8.0，用于存放结构化政策表、元数据和聊天记录。  
- Text2SQL：自然语言 → SQL → 安全执行，仅允许 SELECT，拒绝 DML/DDL/UNION。  
- 多智能体，原则上支持20张表联调
- 领域增强：结合时间表达解析、地区识别、聚合意图（COUNT/SUM/GROUP BY）提升 SQL 质量。

## 大模型与重排序

- LLM：支持 DeepSeek / OpenAI 兼容接口，用于意图分类、答案生成和复杂推理。  
- 嵌入模型：OpenAI text-embedding-3 / DashScope 等，为 Milvus 和 LlamaIndex 提供向量表示。  
- Reranker：DashScope gte-rerank-v2（可选），对初始检索结果做语义重排序。
- 支持vllm

## 服务与前端

- 服务框架：FastAPI 提供 RESTful API、健康检查和 CLI 接入。  
- 前端技术：Vue 3 + Vite + Element Plus + Pinia + D3，用于知识库管理、规则编辑和知识图谱可视化。  
- 安全与工程：.env 配置隔离环境，支持 Docker 部署、自动化测试与问题集回归验证。
