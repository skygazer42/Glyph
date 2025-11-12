# GLYPH PROJECT - QUICK REFERENCE GUIDE

## EXECUTIVE SUMMARY

**Glyph** is an enterprise-grade intelligent policy question-answering system that combines:
- Multi-agent orchestration (Microsoft AutoGen)
- Vector semantic search (Milvus)
- Knowledge graph reasoning (LightRAG)
- DSL rule engine for policy calculations
- Text-to-SQL database integration
- RESTful API with async processing

---

## KEY COMPONENTS AT A GLANCE

### 1. AGENT SERVICE (Orchestrator)
- **File**: `app/agents/service/agent_service.py`
- **Role**: Main entry point coordinating all agents
- **Methods**: `process_query()`, `ingest_paths()`, `initialize()`

### 2. AGENT TYPES (8 Specialized Agents)

| Agent | Function | Input | Output |
|-------|----------|-------|--------|
| RewriteAgent | Normalize & enhance query | Raw query | Enhanced query |
| KnowledgeAgent | Semantic search + synthesis | Query | Answer with sources |
| GraphAgent | Knowledge graph reasoning | Query | Graph-based answer |
| RuleEngineAgent | Policy calculations | Query + inputs | Computed result |
| Text2SQLAgent | SQL generation & execution | Natural language | Query result |
| DialogueAgent | Conversation management | Query | Chat response |
| ClarifierAgent | Generate clarification Qs | Ambiguous query | Clarifying questions |
| WorkflowAgent | Multi-step workflows | Complex request | Workflow result |

### 3. KNOWLEDGE SYSTEMS

```
Vector Search (Milvus)          Knowledge Graph (LightRAG)
      ↓                               ↓
Policy Documents            Entity relationships
    ↓                               ↓
Embeddings (OpenAI/Dash)    Node/Edge reasoning
    ↓                               ↓
Similarity search            Graph traversal
    ↓                               ↓
Top-K retrieval             Path-based answers
```

### 4. DSL PIPELINE (Policy Rule Generation)

```
Policy Text
    ↓
DSLExtractor (LLM)
    ├─ Detect type (appliance/auto/coupon)
    ├─ Extract structure
    └─ Parse response
    ↓
DSLGenerator (Jinja2)
    ├─ Select template
    ├─ Render YAML
    └─ Validate data
    ↓
PolicyEngine (Rule Execution)
    ├─ Load rules
    ├─ Execute calculations
    └─ Return trace
```

### 5. TEXT-TO-SQL PIPELINE

```
Database Query in Natural Language
    ↓
QueryAnalyzer
    ├─ Extract intent
    ├─ Identify entities
    └─ Determine schema needs
    ↓
SchemaRetriever
    ├─ Get table info
    ├─ Rank by relevance
    └─ Filter columns
    ↓
SQLGenerator
    ├─ Generate SQL
    ├─ Validate syntax
    └─ Execute
    ↓
Result Formatter & Visualization
```

---

## CONFIGURATION HIERARCHY

```
.env (Environment Variables)
    ↓
app/config/app_config.py
    ├─ DatabaseSettings (Milvus, MySQL, Redis, Neo4j)
    ├─ ModelSettings (LLM: API key, base URL, model, temperature)
    ├─ EmbeddingSettings (OpenAI/DashScope/Ollama backend)
    ├─ LlamaIndexSettings (Document chunking strategy & size)
    ├─ LightRAGSettings (KG workdir, embedding model)
    ├─ SystemSettings (Hybrid retrieval, early stop threshold)
    └─ ... more settings
    ↓
app/core/config.py (Singleton access)
    ↓
Components (inject via settings)
```

### Critical Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `LLM_API_KEY` | `sk-xxxxx` | LLM authentication |
| `LLM_BASE_URL` | `https://api.deepseek.com` | LLM endpoint |
| `LLM_MODEL_NAME` | `deepseek-chat` | Model name |
| `EMBEDDING_BACKEND` | `openai` or `dashscope` | Vector model source |
| `DATABASE__MILVUS_HOST` | `localhost` | Milvus server |
| `DATABASE__MYSQL_HOST` | `localhost` | MySQL server |
| `LIGHTRAG_WORKDIR` | `resources/data/lightrag` | KG storage |

---

## API ENDPOINTS

### Agent Query
- `POST /query` - Process single query
- `POST /load-docs` - Ingest documents
- `GET /health` - Health check

### DSL Management
- `POST /api/dsl/generate` - Generate DSL from policy text
- `POST /api/dsl/test` - Test rule execution
- `GET /api/dsl/list` - List all rules
- `GET /api/dsl/{rule_id}` - Get rule details

### Knowledge Base
- `POST /api/knowledge/upload` - Upload documents
- `POST /api/knowledge/embed` - Embed to vector DB
- `POST /api/knowledge/search` - Search documents
- `DELETE /api/knowledge/documents/{doc_id}` - Delete document

---

## DATA FLOW DIAGRAM

```
User Query
    ↓
SecurityGateway (Auth, Rate limit, Validate)
    ↓
SessionManager (Load history, Create context)
    ↓
RewriteAgent (Enhance with context)
    ↓
IntentRouter (Classify intent, LLM or rules)
    ↓
Route Decision:
    ├─ greeting/farewell/chit_chat → DialogueAgent
    ├─ calculation → RuleEngineAgent + optional KB lookup
    ├─ policy_inquiry → KnowledgeAgent (vector search)
    ├─ summary/relationship → GraphAgent (LightRAG)
    ├─ comparison → PolicyComparator + KnowledgeAgent
    ├─ sql/database → Text2SQLAgent
    ├─ unclear → ClarifierAgent
    └─ complex → Parallel execution (asyncio.gather)
    ↓
Agent Execution:
    ├─ Retrieve (KB, Graph, SQL)
    ├─ Analyze (Extract structure, facts)
    ├─ Generate (LLM synthesis)
    ├─ Score (Confidence calculation)
    └─ Trace (Audit trail)
    ↓
Answer Selection (by confidence, early stop threshold)
    ↓
FinalAnswer (text + confidence + sources + metadata)
    ↓
Response (HTTP/WebSocket)
    ↓
ChatHistory Store (Persistence)
```

---

## CLASS HIERARCHY

### BaseAgent Classes

```
PolicyAgentBase (framework/base/base_agent.py)
    ├─ RewriteAgent
    ├─ KnowledgeAgent
    ├─ GraphAgent
    ├─ RuleEngineAgent
    ├─ Text2SQLAgent
    └─ DialogueAgent
```

### Data Models

```
PolicyDocument
├─ id, title, content
├─ source, doc_type
├─ keywords, regions, target_groups
├─ embedding, metadata
└─ retrieval_origin (tracking source)

FinalAnswer
├─ query_id, answer
├─ sources (List[PolicyDocument])
├─ confidence (0.0-1.0)
├─ verification_passed (bool)
├─ metadata (route, intent, timing)
└─ total_processing_time

IntentResult
├─ intent (main classification)
├─ sub_intent (detail)
├─ confidence
├─ chains (recommended paths)
└─ requires_parallel (bool)
```

---

## DEPLOYMENT STACK

### Docker Services (docker-compose.yaml)

```
Milvus Cluster
├─ milvus:19530 (Vector DB)
├─ etcd:2379 (Config)
└─ minio:9000 (Storage)

RelationalDB
├─ mysql:3306 (Metadata, schema, history)

Cache
└─ redis:6379 (Sessions, context)

Python App
└─ FastAPI:8000 (HTTP API)
```

### Database Schema

**policy_documents** (Milvus collection)
- Vector embeddings
- Document metadata
- Semantic search index

**Chat History** (MySQL)
- user_id, session_id
- query, answer, timestamp
- confidence, metadata

**Database Schemas** (MySQL)
- table_name, column_name
- data_type, description
- relevance scores

---

## COMMON WORKFLOWS

### 1. Load & Index Documents

```python
from app.agents.service import AgentService
from app.knowledge.service import KnowledgeService

service = AgentService()
await service.initialize()

# Load documents
stats = await service.ingest_paths(["/path/to/policies"])
# → Embeds docs, builds indices, stores in Milvus + LightRAG
```

### 2. Process Query

```python
response = await service.process_query(
    "家电补贴申请条件是什么？",
    session_id="user_123",
    connection_id=None  # For DB queries
)
# → Orchestrates agents, returns FinalAnswer
```

### 3. Generate & Execute DSL Rule

```python
from app.agents.dsl_generator import DSLExtractor, DSLGenerator, PolicyEngine

# Extract structure
extractor = DSLExtractor()
dsl_data = extractor.extract(policy_text)

# Generate YAML
generator = DSLGenerator()
generator.generate(dsl_data, output_file="rule.yaml")

# Execute rule
engine = PolicyEngine()
result = engine.execute(
    rule_id="Rule_Appliance",
    inputs={"appliance_price": 5000, "energy_grade": "A"}
)
```

### 4. Text-to-SQL Query

```python
from app.agents.pipeline.text2sql_agent import Text2SQLAgent

agent = Text2SQLAgent()
answer = await agent.query_database(
    query="去年销售最高的产品是什么？",
    connection_id=1  # Database connection
)
```

---

## PERFORMANCE TIPS

### Optimization Strategies

1. **Batch Embeddings**: Use `embedding_batch_size` in config
2. **Vector Index**: Milvus auto-indexing with HNSW
3. **Hierarchical Index**: Enable for large document sets
4. **Early Stopping**: Set `EARLY_STOP_CONF=0.8` for early termination
5. **Caching**: Redis for frequent queries
6. **Parallel Agents**: Async execution with `asyncio.gather()`
7. **Reranking**: Optional DashScope reranker for top-k refinement

### Scaling

- **Vector DB**: Milvus Cluster mode for 100M+ vectors
- **App**: Scale Python instances horizontally (stateless)
- **Cache**: Redis cluster for session persistence
- **LLM**: Rate limiting via proxy/load balancer

---

## DEBUGGING & MONITORING

### Logging Levels

```python
from app.core.logging_manager import configure

configure(level="DEBUG")  # Detailed traces
configure(level="INFO")   # Normal operation
configure(level="WARNING") # Issues only
```

### Key Log Points

- `agent_service.py`: Query orchestration flows
- `intent_router/`: Intent classification decisions
- `knowledge/`: Retrieval hit rates & latencies
- `dsl_generator/`: Extraction & generation progress
- `chatdb/`: SQL generation & execution

### Health Checks

```bash
# Milvus
curl http://localhost:9091/healthz

# MySQL
mysqladmin ping -h localhost -u root -p

# Redis
redis-cli ping

# FastAPI
curl http://localhost:8000/health
```

---

## COMMON ISSUES

| Issue | Cause | Solution |
|-------|-------|----------|
| Embedding dim mismatch | Model changed | Delete collection, rebuild |
| Milvus connection fail | Service not running | `docker-compose up -d milvus` |
| LLM API timeout | Rate limit | Increase timeout in config |
| Low retrieval accuracy | Small doc chunks | Adjust `LLAMAINDEX_CHUNK_SIZE` |
| Memory overflow | Large models | Use smaller embedding model |

---

## PROJECT STATISTICS

- **Total Files**: 244 Python files
- **Code Size**: 28,603 LOC (app/ only)
- **Agent Types**: 8+ specialized
- **API Endpoints**: 15+
- **Test Files**: 15+
- **Dependencies**: 40+
- **Docker Services**: 5

---

## DEVELOPMENT ENTRY POINTS

### Start Development Server
```bash
# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up -d

# Run app
python api_server.py
# OR
uvicorn app.main:app --reload

# Access API docs
http://localhost:8000/docs
```

### CLI Usage
```bash
# Interactive mode
python scripts/unified_cli.py --interactive

# Batch processing
python scripts/unified_cli.py --batch queries.txt

# Load documents
python scripts/unified_cli.py --load-docs ./resources/data/process

# Demo
python scripts/unified_cli.py --demo
```

### Running Tests
```bash
pytest tests/
pytest tests/test_complete_dsl.py -v
pytest tests/test_hybrid_simple.py -v
```

