# ChatDB与Gove智能体集成文档

## 概述

本文档描述了如何将ChatDB项目的智能体架构集成到Gove政策问答系统中，实现一个功能更强大、架构更灵活的智能体系统。

## 架构对比

### ChatDB原始架构
- **串行流水线**：严格按照顺序执行
- **单一任务类型**：专注于SQL查询生成
- **固定智能体链**：SchemaRetriever → QueryAnalyzer → SqlGenerator → SqlExplainer → SqlExecutor → VisualizationRecommender
- **主题驱动通信**：基于TopicTypes的消息路由

### GovE原始架构
- **并行路由**：根据意图选择不同处理链
- **多意图支持**：聊天、政策查询、计算、比较等
- **灵活处理链**：kb_chain、graph_chain、hybrid_chain等
- **智能降级**：低置信度时启动备用方案

### 集成后架构
- **混合架构**：结合串行和并行处理
- **智能路由**：意图识别 + 自适应处理
- **模块化设计**：可复用的智能体组件
- **统一接口**：FinalAnswer统一输出格式

## 集成的核心组件

### 1. BaseAgent类 (来自ChatDB)
位置：`/agents/chatdb/base_agent.py`

**功能**：
- 统一的智能体基类
- 流式响应支持
- 错误处理机制
- Markdown格式化工具
- 内存管理

**适配修改**：
- 支持政策数据的Markdown格式化
- 添加`format_policy_as_markdown()`方法
- 集成Gove的消息类型

### 2. AgentFactory类 (来自ChatDB)
位置：`/agents/chatdb/factory.py`

**功能**：
- 智能体注册和管理
- 单例模式支持
- 配置管理
- 缓存机制

**适配修改**：
- 注册Gove的智能体类
- 支持Gove特有的配置
- 添加便捷函数

### 3. Text2SQLAgent（封装 ChatDB 流水线）
位置：`/app/agents/pipeline/text2sql_agent.py`

**新增功能**：
- 统一驱动 ChatDB 的 Schema → Query → SQL → Execute 全流程
- 自动依赖 ORM (`app/persistence`) 查询连接信息
- 输出 `FinalAnswer`，方便 AgentService 汇总 metadata

### 4. AgentService
位置：`/app/agents/service.py`

**新增功能**：
- 统一的改写 → 意图 → 路由流水线
- 内置知识库/图谱/DSL/Text2SQL 调用
- 元数据与诊断信息统一封装
- 兼容 CLI / API / 脚本调用

## 智能体映射

### ChatDB → AgentService 复用关系

| ChatDB 组件 | 现存放位置 | 在统一流水线中的作用 |
|-------------|------------|------------------------|
| `SchemaRetrieverAgent` | `app/agents/chatdb/schema_retriever.py` | Text2SQLAgent 解析 Neo4j 表结构 |
| `QueryAnalyzerAgent` | `app/agents/chatdb/query_analyzer.py` | Text2SQL 语义分析/实体提取 |
| `HybridSqlGeneratorAgent` | `app/agents/chatdb/hybrid_sql_generator.py` | 结合示例/Schema 生成 SQL |
| `SqlExplainerAgent` | `app/agents/chatdb/sql_explainer.py` | 解释 SQL 及执行计划 |
| `SqlExecutorAgent` | `app/agents/chatdb/sql_executor.py` | 执行 SQL，返回结果 |
| `VisualizationRecommenderAgent` | `app/agents/chatdb/visualization_recommender.py` | 给出可视化建议（可选） |

这些组件现在由 `pipeline/Text2SQLAgent` 统一调用，再通过 `AgentService` 的 `text2sql` 路由返回 `FinalAnswer`。

## 新增智能体

### AgentService 新增的统一智能体
- **RewriteAgent** - 口语改写，便于业务理解
- **IntentDetectionTool** - LLM + 规则意图识别
- **KnowledgeAgent** - Milvus 检索 + LLM 摘要
- **GraphAgent** - LightRAG / Neo4j 关系推理，可自动降级为知识检索
- **RuleEngineAgent** - 基于 DSL `PolicyEngine` 的补贴计算
- **Text2SQLAgent** - 封装 ChatDB 流水线，需提供 `connection_id`
- **Dialogue / Clarifier Agents** - 负责寒暄与追问，保持体验一致

## 使用方式

### 1. 使用统一 CLI
```bash
# 交互模式
python scripts/unified_cli.py --interactive

# 演示模式
python scripts/unified_cli.py --demo

# 批量处理
python scripts/unified_cli.py --batch queries.txt

# 查看系统指标
python scripts/unified_cli.py --metrics
```

### 2. 直接使用智能体
```python
from app.agents.service import AgentService

# 创建编排服务
service = AgentService()

# 处理查询
response = await service.process_query("我想申请补贴")
```

### 3. （可选）直接通过工厂创建 ChatDB Agent
```python
from app.agents.chatdb.factory import get_agent_factory

factory = get_agent_factory()
sql_generator = factory.create_agent("HybridSqlGeneratorAgent")
```

## 配置选项

### 智能体配置
```yaml
agents:
  rewrite:
    max_length: 256

  rule_engine:
    rule_dir: "rules"
    max_rules: 5

  knowledge:
    top_k: 5
    threshold: 0.6

  graph:
    enable_lightrag: true

  text2sql:
    enable_examples: true
```

### 路由配置
```yaml
routes:
  knowledge:
    enabled: true
  graph:
    enabled: true
    fallback_to_knowledge: true
  rule_engine:
    enabled: true
  text2sql:
    enabled: true
    requires_connection_id: true
```

## 优势总结

### 技术优势
1. **复用率高**：70%的ChatDB代码可直接复用
2. **架构灵活**：支持串行、并行、自适应处理
3. **扩展性强**：易于添加新的智能体和处理链
4. **维护性好**：模块化设计，职责清晰

### 功能增强
1. **多模态查询**：支持对话、计算、比较等
2. **智能路由**：自动选择最优处理方式
3. **上下文感知**：维护对话历史和状态
4. **流式响应**：实时反馈，用户体验好

### 开发效率
1. **减少重复开发**：避免重新构建基础架构
2. **快速迭代**：基于现有组件快速开发
3. **测试友好**：每个智能体可独立测试
4. **配置化**：通过配置文件调整行为

## 下一步计划

### 短期（1-2周）
- [ ] 完善SqlExecutorAgent适配
- [ ] 实现GraphRetrieverAgent
- [ ] 优化并行处理性能
- [ ] 添加更多测试用例

### 中期（3-4周）
- [ ] 实现智能体热插拔
- [ ] 添加负载均衡机制
- [ ] 集成监控和告警
- [ ] 优化内存使用

### 长期（1-2月）
- [ ] 开发可视化界面
- [ ] 支持多租户
- [ ] 实现智能体市场
- [ ] 添加A/B测试功能

## 示例代码

### 创建自定义智能体
```python
from agents.chatdb.base_agent import BaseAgent

class CustomPolicyAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            agent_id="custom_policy",
            agent_name="CustomPolicyAgent",
            **kwargs
        )

    async def process_request(self, request, context):
        # 自定义处理逻辑
        pass

# 注册到工厂
factory = get_agent_factory()
factory.register_agent_class("CustomPolicyAgent", CustomPolicyAgent)
```

### 创建自定义处理链
```python
# 定义处理链
custom_chain = {
    "mode": ProcessingMode.PARALLEL,
    "agents": ["policy_retriever", "custom_agent"],
    "parallel": True
}

# 在 AgentService 中使用
result = await service.process_query(
    user_query,
    analysis,
    custom_chain
)
```

## 结论

通过集成ChatDB的智能体架构，Gove系统获得了：
1. **更强大的基础架构** - 借鉴ChatDB成熟的框架
2. **更丰富的功能** - 支持多种查询类型和处理模式
3. **更好的开发体验** - 模块化、可配置、易扩展
4. **更高的灵活性** - 支持动态组合和优化

这个集成方案展示了如何有效地结合两个项目的优势，创造出更强大的智能体系统。
