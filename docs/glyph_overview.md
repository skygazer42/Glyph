# GLYPH PROJECT - COMPREHENSIVE OVERVIEW

## 1. PROJECT PURPOSE AND MISSION

### What is Glyph?
Glyph is an intelligent policy question-answering system (政策智能问答系统 v2.0) designed specifically for government policy document analysis. It's a sophisticated multi-agent system built on Microsoft's AutoGen Core framework that can:

- Parse and understand government policy documents
- Extract structured information from policy text
- Generate executable Domain-Specific Language (DSL) rules
- Execute complex policy calculations and subsidy eligibility determinations
- Provide intelligent, context-aware answers about policies
- Handle multi-turn conversations with full conversation history management
- Support multiple knowledge retrieval strategies (vector search, knowledge graphs, hierarchical indexing)

### Target Domain
- Government policy documents (家电补贴, 汽车补贴, 消费券 policies)
- Policy inquiry systems for citizens and enterprises
- Subsidy eligibility verification and benefit calculation
- Multi-language support (Chinese, English)

---

## 2. KEY DIRECTORIES AND THEIR PURPOSES

### Root Level Structure
```
/data/temp33/Glyph/
├── app/                          # Core application code (28,603 LOC)
├── resources/                    # Data and storage resources
├── scripts/                      # Utility and setup scripts
├── templates/                    # DSL generation templates
├── rules/                        # Generated policy rules
├── tests/                        # Test files
├── docs/                         # Documentation
├── examples/                     # Usage examples
├── docker/                       # Docker configuration
└── web/                          # Frontend web application
```

### app/ - Main Application Module

#### app/agents/ (2,800+ LOC)
Multi-agent orchestration and specialized processing agents:

**service/**
- `agent_service.py` - Main orchestrator that wires together the agent pipeline
- `tools.py` - Tool implementations (KnowledgeTool, VisionTool, WebSearchTool, UserProfileTool)
- `chat_history_store.py` - Conversation history management

**pipeline/** - High-level agent processors
- `rewrite_agent.py` - Query rewriting for business context
- `knowledge_agent.py` - Knowledge retrieval + LLM synthesis
- `graph_agent.py` - Knowledge graph traversal (LightRAG)
- `rule_agent.py` - DSL rule execution
- `text2sql_agent.py` - Database query generation
- `dialog_agent.py` - Dialogue management & clarification
- `workflow_agent.py` - Multi-step workflow orchestration

**dsl_generator/** - Policy DSL generation pipeline
- `dsl_extractor.py` - LLM-based extraction of policy structures
- `dsl_generator.py` - YAML DSL file generation using Jinja2 templates
- `dsl_generator_domain.py` - Domain-specific DSL configuration
- `rule_engine.py` - PolicyEngine for executing DSL rules
- `template_registry.py` - Registry for DSL templates
- `document_parser.py` - Parse policy documents
- `dsl_runtime_helpers.py` - Runtime utilities for rule execution

**chatdb/** (16 files) - Text-to-SQL conversion
- `text2sql_service.py` - Main service orchestrator
- `sql_generator.py` - SQL generation from natural language
- `query_analyzer.py` - Query understanding and analysis
- `schema_retriever.py` - Database schema handling
- `hybrid_sql_generator.py` - Multi-path SQL generation strategy

**packs/** - Specialized processing modules
- `intent_router/` - Intent classification and routing
- `policy_analysis/` - Structured policy information extraction
- `answer_generator/` - Template-based answer generation
- `query_analyzer/` - Query understanding

**framework/** - Core agent framework
- `base/` - Base agent types and abstractions
- `core/` - Orchestration, message bus, agent registry
- `monitoring/` - Agent activity monitoring
- `security/` - Security gateway and validation
- `common/` - Session management, embedding, model clients
- `coordination/` - Session manager and coordinator

#### app/knowledge/ (1,000+ LOC)
Knowledge retrieval and indexing systems:

- `milvus.py` - Vector database wrapper for Milvus (distributed vector search)
- `service.py` - High-level knowledge service (gateway for ingestion/querying)
- `hierarchical_index.py` - Hierarchical document indexing
- `llamaindex_integration.py` - LlamaIndex integration for document chunking
- `llamaindex_hybrid_retrieval.py` - Hybrid retrieval combining semantic and dense search
- `image_retrieval.py` - Image-based document retrieval
- `rerank.py` - Re-ranking retrieved documents (DashScope integration)
- `mineru_adapter.py` - Layout-aware document parsing
- `rapid_ocr_processor.py` - OCR for document images
- `doc_enhanced.py` - Enhanced document representation
- `hybrid_retrieval.py` - Multiple retrieval strategy combinations

#### app/api/ - FastAPI REST Interface (500+ LOC)
REST API endpoints:

- `endpoints/agent.py` - Agent query endpoints
- `endpoints/dsl.py` - DSL generation & testing endpoints
- `endpoints/knowledge.py` - Knowledge base management endpoints
- `schemas.py` - Request/response data schemas
- `deps.py` - Dependency injection

#### app/config/ (600+ LOC)
Configuration management:

- `app_config.py` - Main configuration (Database, Model, Embedding, LlamaIndex, LightRAG settings)
- `autogen.py` - AutoGen framework configuration

#### app/core/ (500+ LOC)
Core infrastructure:

- `config.py` - Configuration loading
- `llms.py` - LLM model initialization
- `model_clients.py` - Model client factories
- `logging_manager.py` - Centralized logging
- `security.py` - Security utilities

#### app/models/ (400+ LOC)
Data models:

- `base.py` - Core domain models (FinalAnswer, PolicyDocument, PolicyType, etc.)
- `llms.py` - LLM configuration models
- `chat_history.py` - Chat history storage model
- `schema_table.py`, `schema_column.py`, `schema_relationship.py` - Database schema models
- `db_connection.py` - Database connection configuration
- `value_mapping.py` - Value mapping for database operations

#### app/persistence/ (400+ LOC)
Data persistence layer:

- `db/` - Database access layer
  - `dbaccess.py` - Generic database operations
  - `base.py`, `session.py` - SQLAlchemy session management
- `crud/` - CRUD operations for each model type
  - `crud_chat_history.py`, `crud_db_connection.py`, `crud_schema_*.py`

#### app/domains/ (300+ LOC)
Domain-specific configurations:

- `schemas.py` - Domain schemas
- `manager.py` - Domain manager
- `prompt_catalog.py` - Prompt templates for different domains

#### app/utils/ (200+ LOC)
Utility functions:

- `config.py` - Configuration utilities
- `document_loader.py` - Load documents from various formats

### resources/ - Data and Storage

```
resources/
├── data/
│   ├── guize/                    # Policy documents
│   ├── process/                  # Processed documents
│   ├── lightrag/                 # LightRAG knowledge graph storage
│   └── vector_store/             # Vector index caches
├── database/
│   ├── initialize_db.py
│   └── seed_data/                # Database initialization
├── knowledge_base/
│   └── documents/                # Document storage
├── logs/                         # Application logs
└── storage/                      # Persistent storage
```

### templates/ - DSL Templates
Jinja2 templates for DSL generation:

- `consumer_coupon.yaml.j2` - Consumer voucher policy template
- `appliance_subsidy.yaml.j2` - Appliance subsidy template
- `auto_subsidy.yaml.j2` - Automobile subsidy template

### scripts/ - Utility Scripts
- `unified_cli.py` - Main CLI interface (interactive/batch/demo modes)
- `embed_documents.py` - Document embedding pipeline
- `test_qa.py` - QA testing
- `test_hierarchical_index.py` - Hierarchical indexing tests
- `check_config.py` - Configuration validation
- `batch_process.py` - Batch document processing
- `verify_milvus.py` - Milvus database verification

### tests/ - Test Suite (15+ test files)
- Embedding tests, retrieval comparison tests
- DSL generation and execution tests
- Document processing tests
- Integration tests

---

## 3. TECHNOLOGIES AND FRAMEWORKS

### Core Frameworks
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent Orchestration** | Microsoft AutoGen Core (v0.4.0+) | Multi-agent system architecture |
| **LLM Integration** | OpenAI-compatible APIs | Language model integration (DeepSeek, DashScope) |
| **Vector Database** | Milvus v2.3.3 | Distributed vector search & storage |
| **Knowledge Graph** | LightRAG | Knowledge graph construction & retrieval |
| **Document Processing** | LlamaIndex (llamaindex) | Document chunking, embedding, indexing |
| **OCR** | RapidOCR | Optical character recognition |
| **Web Framework** | FastAPI | REST API server |
| **Database** | MySQL 8.0 | Relational data storage |
| **Cache** | Redis 7 | Session & cache management |
| **PDF Processing** | PyMuPDF | PDF document parsing |

### Key Libraries
- **autogen-core**, **autogen-agentchat**, **autogen-ext[openai]** - Agent framework
- **pymilvus** - Milvus Python client
- **llama-index*** - Document processing pipeline
- **lightrag-hku** - Knowledge graph operations
- **dashscope** - DashScope API integration
- **fastapi**, **uvicorn** - Web framework
- **pydantic**, **pydantic-settings** - Data validation
- **numpy**, **pandas** - Data processing
- **jinja2** - Template engine for DSL generation
- **pyyaml** - YAML parsing/generation
- **loguru** - Advanced logging
- **asyncio** - Async runtime

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **etcd** - Configuration store (for Milvus)
- **MinIO** - Object storage (for Milvus)

---

## 4. MAIN PYTHON MODULES AND THEIR FUNCTIONS

### High-Level Flow

#### AgentService (entry point)
Located: `app/agents/service/agent_service.py`

```
User Query
    ↓
AgentService.process_query()
    ↓
RewriteAgent (Query rewriting)
    ↓
IntentRouter (Intent detection)
    ↓
Pipeline Agents (Parallel execution)
    ├→ DialogueAgent (greetings/chit-chat)
    ├→ KnowledgeAgent (semantic retrieval + LLM synthesis)
    ├→ GraphAgent (knowledge graph traversal)
    ├→ RuleEngineAgent (DSL rule execution)
    ├→ Text2SQLAgent (database queries)
    └→ ClarifierAgent (ambiguous queries)
    ↓
FinalAnswer (with confidence & sources)
```

### Core Agents (Pipeline-level)

| Agent | Purpose | Location | Key Methods |
|-------|---------|----------|------------|
| **RewriteAgent** | Query normalization & context enhancement | `pipeline/rewrite_agent.py` | `rewrite()` |
| **KnowledgeAgent** | Semantic search + LLM summarization | `pipeline/knowledge_agent.py` | `answer()` |
| **GraphAgent** | Knowledge graph retrieval via LightRAG | `pipeline/graph_agent.py` | `answer()` |
| **RuleEngineAgent** | DSL rule selection & execution | `pipeline/rule_agent.py` | `compute()` |
| **Text2SQLAgent** | Text-to-SQL conversion | `pipeline/text2sql_agent.py` | `query_database()` |
| **DialogueAgent** | Conversation management | `pipeline/dialog_agent.py` | `respond()` |
| **ClarifierAgent** | Generate clarification questions | `pipeline/dialog_agent.py` | `clarify()` |
| **WorkflowAgent** | Multi-step workflows | `pipeline/workflow_agent.py` | `execute_workflow()` |

### Knowledge Management

#### KnowledgeService
Location: `app/knowledge/service.py`

Core methods:
- `index_documents()` - Ingest documents into vector DB + hierarchical index
- `search()` - Retrieve documents by semantic similarity
- `search_hierarchical()` - Advanced hierarchical retrieval
- `delete_documents()` - Remove documents

#### MilvusStore
Location: `app/knowledge/milvus.py`

Core methods:
- `add_documents()` - Insert vectors into Milvus collection
- `search()` - Similarity search with top-k filtering
- `delete_documents()` - Remove documents by ID
- `update_metadata()` - Update document metadata

#### LlamaIndexIntegration
Location: `app/knowledge/llamaindex_integration.py`

Features:
- Document chunking strategies (sentence, semantic, fixed)
- Multi-embedding support (OpenAI, DashScope, Ollama)
- Hierarchical document indexing
- Batch embedding

### DSL Generation Pipeline

#### DSLExtractor
Location: `app/agents/dsl_generator/dsl_extractor.py`

Process:
1. Detect policy type (appliance/auto/coupon)
2. Build type-specific LLM prompts
3. Call LLM to extract structured information
4. Parse and validate extracted data

Key methods:
- `extract()` - Main extraction method
- `_detect_policy_type()` - Classify policy document
- `_build_*_prompt()` - Type-specific prompts
- `_parse_response()` - Response parsing

#### DSLGenerator
Location: `app/agents/dsl_generator/dsl_generator.py`

Features:
- Jinja2-based template rendering
- YAML output generation
- Input validation and preprocessing
- External template loading

Key methods:
- `generate()` - Generate YAML DSL from extracted data
- `save()` - Save DSL to file
- `detect_template_type()` - Auto-detect template type

#### PolicyEngine (Rule Engine)
Location: `app/agents/dsl_generator/rule_engine.py`

Capabilities:
- Load and cache YAML rules
- Execute rules with input validation
- Support Jinja2 expressions in calculations
- Provide execution traces for interpretability

Key methods:
- `execute()` - Execute a rule with inputs
- `get_rule_info()` - Retrieve rule metadata
- `_load_all_rules()` - Initialize rules from files
- `_evaluate_calc()` - Evaluate calculation expressions

### Text-to-SQL Pipeline

#### Text2SQLService
Location: `app/agents/chatdb/text2sql_service.py`

Orchestrates:
- Query analysis (intent, entities, requirements)
- Schema retrieval and ranking
- SQL generation (single-path or hybrid)
- Execution and visualization

#### QueryAnalyzer
Location: `app/agents/chatdb/query_analyzer.py`

Functions:
- Extract query intent
- Identify entities and values
- Determine required columns/tables
- Assess query complexity

#### SchemaRetriever
Location: `app/agents/chatdb/schema_retriever.py`

Features:
- Retrieve database schema information
- Rank relevant tables by semantic similarity
- Filter by column usage patterns

#### SQLGenerator
Location: `app/agents/chatdb/sql_generator.py`

Generates:
- Single SQL query (primary strategy)
- Validation queries
- Alternative queries (fallback)

### API Layer

#### Agent Endpoints
Location: `app/api/endpoints/agent.py`

Endpoints:
- `POST /api/agent/query` - Process query
- `POST /api/agent/chat` - Chat interface
- `GET /api/agent/sessions/{session_id}` - Session management

#### DSL Endpoints
Location: `app/api/endpoints/dsl.py`

Endpoints:
- `POST /api/dsl/generate` - Generate DSL from text
- `POST /api/dsl/test` - Test rule execution
- `GET /api/dsl/list` - List all rules
- `POST /api/dsl/save` - Save generated DSL

#### Knowledge Endpoints
Location: `app/api/endpoints/knowledge.py`

Endpoints:
- `POST /api/knowledge/upload` - Upload documents
- `POST /api/knowledge/embed` - Embed documents
- `POST /api/knowledge/search` - Search documents
- `DELETE /api/knowledge/documents/{doc_id}` - Delete document

---

## 5. ARCHITECTURAL ORGANIZATION

### Six-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  1. USER INTERACTION LAYER                          │
│     Web UI / FastAPI / CLI / WebSocket              │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  2. SECURITY GATEWAY LAYER                          │
│     Auth | Authorization | Rate Limiting | Audit    │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  3. ORCHESTRATION LAYER                             │
│     AgentService | SessionManager | Workflow        │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  4. ROUTING LAYER                                   │
│     IntentRouter | LLMClassifier | SessionManager   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  5. AGENT LAYER                                     │
│  Retrieval|Analysis|Generation|Validation|Calculate │
│  Compare|Chat|Clarify|Rule Execute|Text2SQL         │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  6. INFRASTRUCTURE LAYER                            │
│     MessageBus | AgentRegistry | Orchestrator       │
│     Milvus | Redis | MySQL | LightRAG              │
└─────────────────────────────────────────────────────┘
```

### Query Processing Flow

```
1. Query Reception
   ↓
2. Input Validation & Security Check
   ↓
3. Session Creation/Retrieval
   ↓
4. Query Rewriting (context enhancement)
   ↓
5. Intent Detection & Classification
   ├─ greeting/farewell/chit_chat → dialogue_chain
   ├─ calculation → calculation_chain (with optional KB lookup)
   ├─ policy_inquiry → kb_chain (knowledge base retrieval)
   ├─ summary/relationship/context → graph_chain (LightRAG)
   ├─ comparison → comparison_chain
   ├─ sql/database_query → text2sql_chain
   └─ clarification needed → clarify_chain
   ↓
6. Chain Execution
   - Single chain (high confidence)
   - Parallel chains (low confidence or ambiguous)
   ↓
7. Agent Processing
   ├─ Knowledge retrieval (Milvus + hierarchical index)
   ├─ Document analysis & fact extraction
   ├─ Answer generation with LLM
   ├─ Confidence scoring
   └─ Source attribution
   ↓
8. Answer Composition
   - Merge results from multiple chains
   - Select best answer (by confidence & early stopping)
   ↓
9. Final Answer
   - Answer text
   - Confidence score (0-1)
   - Source documents
   - Metadata (route, intent, timing)
   ↓
10. Response Return & Logging
```

### Data Models

#### Core Data Structures

**PolicyDocument** (`app/models/base.py`)
- `id`: Document identifier
- `title`: Document title
- `content`: Full text content
- `source`: Document source (government agency)
- `doc_type`: Policy category
- `keywords`: Extracted keywords
- `regions`: Geographic applicability
- `target_groups`: Intended audience
- `embedding`: Vector representation
- `metadata`: Additional attributes

**FinalAnswer**
- `query_id`: Unique query ID
- `answer`: Generated answer text
- `sources`: List of source documents
- `confidence`: Confidence score (0-1)
- `verification_passed`: Boolean confidence
- `metadata`: Route, intent, timing info
- `total_processing_time`: Execution time

**IntentResult**
- `intent`: Primary intent classification
- `sub_intent`: Detailed intent type
- `confidence`: Classification confidence
- `chains`: Recommended processing chains
- `requires_parallel`: Parallel execution flag

### Configuration System

#### Settings Hierarchy
```
Environment Variables (.env)
    ↓
app/config/app_config.py (Pydantic models)
    ├─ DatabaseSettings (Neo4j, Milvus, MySQL)
    ├─ ModelSettings (LLM configuration)
    ├─ EmbeddingSettings (Vector model backend)
    ├─ LlamaIndexSettings (Document chunking)
    ├─ LightRAGSettings (Knowledge graph)
    └─ ... more settings
    ↓
app/core/config.py (Config wrapper)
    ↓
Individual components (read via injection)
```

#### Key Configuration Options
- **LLM**: API Key, Base URL, Model Name, Temperature, Context Size
- **Embeddings**: Backend (OpenAI/DashScope/Ollama), Dimension, Batch Size
- **Vector DB**: Host, Port, Collection Name, Database Name
- **Document Processing**: Chunk Strategy, Size, Overlap
- **Knowledge Graph**: Workdir, Embedding Model, Max Tokens
- **Conversation**: Max Turns, History Window Size

### Async Architecture

The system heavily utilizes Python's **asyncio**:
- All I/O operations (DB, API, embeddings) are non-blocking
- Agents communicate asynchronously
- Parallel chain execution using `asyncio.gather()`
- Semaphore-based concurrency control for resource limits

Example pattern:
```python
async def process_query(query: str):
    # Parallel execution
    kb_result, graph_result = await asyncio.gather(
        kb_chain.answer(query),
        graph_chain.answer(query),
        return_exceptions=True
    )
    # Select best result
    return max([kb_result, graph_result], key=lambda x: x.confidence)
```

### Integration Points

#### External Services
- **LLM APIs**: OpenAI, DashScope (Aliyun), DeepSeek
- **Embedding APIs**: OpenAI Embeddings, DashScope Embeddings, Ollama (local)
- **Reranking**: DashScope Rerank API
- **Web Search**: Tavily API (optional)
- **Vision/Image**: GPT-4V or local vision models (optional)

#### Databases
- **Milvus**: Vector similarity search (primary)
- **MySQL**: Metadata, schema, chat history
- **Redis**: Session caching, conversation context
- **Neo4j**: Alternative knowledge graph (optional)

---

## 6. PROJECT STATISTICS

- **Total Python Files**: 244
- **Total Lines of Code**: 28,603 LOC (in app/ directory alone)
- **Main Agent Types**: 8+ specialized agents
- **Supported Backends**: OpenAI, DashScope, DeepSeek, Ollama
- **Database Engines**: Milvus, MySQL, Redis, Neo4j
- **Test Files**: 15+ test modules
- **API Endpoints**: 15+ REST endpoints

---

## 7. KEY FEATURES AND CAPABILITIES

### Intelligent Query Understanding
- Multi-language support (Chinese, English)
- Intent classification with confidence scoring
- Query rewriting for context enhancement
- Clarification question generation for ambiguous queries

### Knowledge Retrieval
- Vector semantic search (Milvus)
- Knowledge graph traversal (LightRAG)
- Hierarchical document indexing
- Re-ranking with DashScope
- Hybrid retrieval strategies

### Policy Analysis
- Automatic policy type detection
- Structured information extraction
- DSL generation in YAML format
- Rule-based policy execution

### Subsidy Calculation
- Complex calculation logic support
- Tiered benefit computation
- Eligibility verification
- Interpretable execution traces

### Multi-Agent Orchestration
- Specialized agent teams for different query types
- Parallel execution with early stopping
- Confidence-based answer selection
- Complete audit trail of decisions

### Conversation Management
- Multi-turn dialogue support
- Session persistence
- Context window management
- User profile tracking

### API & Integration
- RESTful API with streaming responses
- WebSocket support for real-time updates
- Database schema auto-discovery
- Text-to-SQL for structured queries

---

## 8. DEPLOYMENT ARCHITECTURE

### Containerized Services
Via docker-compose.yaml:
- **Milvus Standalone** (v2.3.3) - Vector database
- **etcd** - Configuration store
- **MinIO** - Object storage
- **MySQL 8.0** - Relational database
- **Redis 7** - Cache & session store

### Runtime Stack
- **Python 3.8+** application
- **FastAPI** web server
- **Uvicorn** ASGI server
- **Pydantic** validation
- **Asyncio** async runtime

### Production Considerations
- Rate limiting via security gateway
- Request authentication & authorization
- Audit logging of all operations
- Health check endpoints
- Graceful shutdown procedures
- Error handling with fallback chains

---

## 9. DEVELOPMENT & TESTING

### Test Coverage
- Unit tests for core components
- Integration tests for full pipelines
- DSL generation and execution tests
- Knowledge retrieval tests
- Text-to-SQL tests

### Example Test Locations
- `/data/temp33/Glyph/tests/test_complete_dsl.py` - Full DSL workflow
- `/data/temp33/Glyph/tests/test_hybrid_simple.py` - Hybrid retrieval
- `/data/temp33/Glyph/tests/test_appliance_exec.py` - Appliance policy rules
- `/data/temp33/Glyph/tests/test_image_retrieval.py` - Image search

### CLI Interface
`scripts/unified_cli.py` provides:
- Interactive mode - real-time policy queries
- Batch mode - process query files
- Demo mode - pre-loaded examples
- Document loading - ingest policy documents

---

## 10. FILE PATH REFERENCE

### Core Modules Locations
```
/data/temp33/Glyph/
├── app/agents/service/agent_service.py          # Main orchestrator
├── app/agents/pipeline/                         # Agent implementations
├── app/agents/dsl_generator/                    # DSL generation
├── app/agents/chatdb/                           # Text-to-SQL
├── app/knowledge/                               # Knowledge management
├── app/api/endpoints/                           # REST API
├── app/config/app_config.py                     # Configuration
├── app/core/                                    # Infrastructure
├── app/models/base.py                           # Data models
├── app/main.py                                  # FastAPI app
├── api_server.py                                # API entry point
├── scripts/unified_cli.py                       # CLI entry point
├── docker-compose.yaml                         # Docker services
└── requirements.txt                             # Dependencies
```

