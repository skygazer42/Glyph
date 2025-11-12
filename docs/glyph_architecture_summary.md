# GLYPH PROJECT - ARCHITECTURE & DESIGN SUMMARY

## SYSTEM OVERVIEW

```
                         USER INTERFACE LAYER
                    (Web UI / CLI / API Clients)
                              |
                              v
                    ======== NETWORK ==========
                              |
                              v
         ┌─────────────────────────────────────┐
         │  FASTAPI REST SERVER (Port 8000)    │
         │  - /query                           │
         │  - /load-docs                       │
         │  - /api/dsl/* (DSL endpoints)       │
         │  - /api/knowledge/* (KB endpoints)  │
         │  - /health                          │
         └──────────────┬──────────────────────┘
                        |
                        v
         ┌──────────────────────────────────────┐
         │     AGENT SERVICE (Orchestrator)     │
         │  app/agents/service/agent_service.py│
         │                                      │
         │  process_query()                     │
         │  ingest_paths()                      │
         │  initialize()                        │
         └──────────────┬───────────────────────┘
                        |
          ┌─────────────┼─────────────┐
          |             |             |
          v             v             v
       SECURITY     SESSION       REWRITE
       GATEWAY      MANAGER        AGENT
          |             |             |
          └─────────────┼─────────────┘
                        |
                        v
         ┌──────────────────────────────────────┐
         │      INTENT ROUTER & CLASSIFIER      │
         │  (LLM + Rule-based routing)          │
         │                                      │
         │  Classifies into:                    │
         │  - greeting/farewell                 │
         │  - calculation                       │
         │  - policy_inquiry                    │
         │  - summary/graph                     │
         │  - comparison                        │
         │  - sql/database                      │
         │  - clarification                     │
         └──────────────┬───────────────────────┘
                        |
      ┌─────────────────┼─────────────────┐
      |                 |                 |
      v                 v                 v
  DIALOGUE_CHAIN   KB_CHAIN          GRAPH_CHAIN
      |                |                  |
      v                v                  v
 DialogueAgent  KnowledgeAgent      GraphAgent
      |                |                  |
      |         ┌──────┴──────┐           |
      |         v             v           v
      |     Vector      Hierarchical  LightRAG
      |     Search      Index         (Knowledge
      |     (Milvus)    (LlamaIndex)   Graph)
      |         |             |           |
      |         └──────┬──────┘           |
      |                |                  |
      └────────────────┼──────────────────┘
                       |
          ┌────────────┼────────────┐
          |            |            |
          v            v            v
      CALC_CHAIN   COMPARISON   TEXT2SQL_CHAIN
          |        CHAIN            |
          v            |            v
    RuleEngineAgent    |      Text2SQLAgent
          |            v            |
          v    PolicyComparator     v
    PolicyEngine         |      SQL Generator
          |              |            |
          v              v            v
      RULES/       KB + Graph     SQL Executor
      YAML                           |
                                     v
                                  Database
                                  (MySQL)

                        ┌─────────────┘
                        |
                        v
         ┌──────────────────────────────────────┐
         │      FINAL ANSWER COMPOSER            │
         │  - Merge results                      │
         │  - Select by confidence               │
         │  - Early stopping (if threshold met)  │
         │  - Confidence scoring                 │
         │  - Source attribution                 │
         └──────────────┬───────────────────────┘
                        |
                        v
         ┌──────────────────────────────────────┐
         │        RESPONSE FORMATTER             │
         │  - FinalAnswer object                 │
         │  - Metadata (route, intent, timing)   │
         │  - Source documents                   │
         │  - Confidence scores                  │
         └──────────────┬───────────────────────┘
                        |
                        v
         ┌──────────────────────────────────────┐
         │    RESPONSE + HISTORY STORAGE         │
         │  - Chat History (MySQL)               │
         │  - Session Cache (Redis)              │
         │  - Audit Logging                      │
         └──────────────┬───────────────────────┘
                        |
                        v
                    HTTP RESPONSE
                (FinalAnswer JSON)
                        |
                        v
                   USER CLIENT
```

---

## DETAILED AGENT INTERACTION DIAGRAM

```
                   INPUT QUERY
                       |
                       v
        ┌──────────────────────────────┐
        │   1. REWRITE AGENT           │
        │  - Parse user intent         │
        │  - Add context from history  │
        │  - Normalize language        │
        │  - Return: enhanced query    │
        └──────────────┬───────────────┘
                       |
                       v
        ┌──────────────────────────────┐
        │   2. INTENT ROUTER           │
        │  - Classify intent (LLM)     │
        │  - Determine route           │
        │  - Assess confidence         │
        │  - Return: IntentResult      │
        └──────────────┬───────────────┘
                       |
          ┌────────────┴────────────┐
          |                         |
      HIGH CONFIDENCE         LOW CONFIDENCE
      (Single Route)         (Multiple Routes)
          |                         |
          v                         v
      Execute Best Route    PARALLEL EXECUTION
                           asyncio.gather()
                                 |
          ┌─────────────────────────┴──────────────────┐
          |                                             |
          v                                             v
  ┌──────────────────┐                   ┌──────────────────────┐
  │   ROUTE A        │ EXECUTION TIME    │   ROUTE B            │
  │  - Retrieve      │    (async)        │  - Retrieve          │
  │  - Analyze       │                   │  - Analyze           │
  │  - Generate      │                   │  - Generate          │
  │  - Score         │                   │  - Score             │
  │ Result: Answer A │                   │ Result: Answer B     │
  └────────┬─────────┘                   └──────────┬───────────┘
           |                                        |
           v                                        v
      ConfA=0.85                              ConfB=0.65
           |                                        |
           └────────────┬─────────────────────────┘
                        |
                        v
        ┌──────────────────────────────┐
        │   3. ANSWER SELECTION        │
        │  - Compare confidences       │
        │  - Check early stop          │
        │  - Select best answer        │
        │  - Merge metadata            │
        └──────────────┬───────────────┘
                       |
                       v
        ┌──────────────────────────────┐
        │   4. FINAL ANSWER RETURN     │
        │  - answer: str               │
        │  - confidence: float         │
        │  - sources: [PolicyDoc]      │
        │  - metadata: dict            │
        │  - verification_passed: bool │
        └──────────────┬───────────────┘
                       |
                       v
                  HTTP RESPONSE
```

---

## KNOWLEDGE RETRIEVAL ARCHITECTURE

```
                    KNOWLEDGE SERVICE
                  (app/knowledge/service.py)
                           |
           ┌───────────────┼───────────────┐
           |               |               |
           v               v               v
        VECTOR          HIERARCHICAL     GRAPH
        STORE           INDEX            STORE
         |               |               |
         v               v               v
      MILVUS         LLAMAINDEX       LIGHTRAG
         |               |               |
         |               |               |
     ┌───┴───┐       ┌───┴───┐       ┌──┴───┐
     v       v       v       v       v      v
    
    EMBEDDING MODELS (Multiple Backends)
    ├─ OpenAI (text-embedding-3-small, dim=1536)
    ├─ DashScope (text-embedding-v3, dim=1024)
    └─ Ollama (local, configurable dim)
    
    STORAGE ARCHITECTURE
    
    Milvus Collection: "policy_documents"
    ├─ id: String (primary key)
    ├─ embedding: Float32 vector (1024 or 1536)
    ├─ title: String
    ├─ content: String (varchar max)
    ├─ source: String
    ├─ doc_type: String
    ├─ keywords: Array<String>
    ├─ regions: Array<String>
    ├─ target_groups: Array<String>
    └─ metadata: JSON
    
    LlamaIndex Storage: resources/data/llamaindex
    ├─ index_store/ (node indices)
    ├─ vector_store/ (vectors)
    └─ docstore/ (document data)
    
    LightRAG Storage: resources/data/lightrag
    ├─ entities/ (node definitions)
    ├─ relationships/ (edges)
    └─ index/ (graph indices)
    
    RETRIEVAL PIPELINE
    
    Query Input
        |
        v
    Embed Query
    (Same model as docs)
        |
        v
    ┌───────────────────────────────┐
    │  PARALLEL RETRIEVAL           │
    │  (if hybrid_retrieval=true)   │
    │                               │
    │  Vector Search (Milvus)       │
    │  ├─ Top-K: 10                 │
    │  ├─ Threshold: 0.7            │
    │  └─ Return: scores, docs      │
    │                               │
    │  Hierarchical Search          │
    │  ├─ Chunk-level search        │
    │  ├─ Document-level retrieval  │
    │  └─ Return: organized docs    │
    │                               │
    │  Graph Traversal (LightRAG)   │
    │  ├─ Entity extraction         │
    │  ├─ Relationship traversal    │
    │  └─ Return: connected docs    │
    └───────────────────────────────┘
        |
        v
    OPTIONAL: RERANKING
    (DashScope Rerank API)
        ├─ Input: top-20 docs
        ├─ Rerank by relevance
        └─ Return: top-5 refined
        |
        v
    MERGE RESULTS
        ├─ Deduplication
        ├─ Score fusion
        │  (vector_score * 0.6 + rerank_score * 0.4)
        └─ Return: final top-K
        |
        v
    AGENT PROCESSING
        ├─ Extract facts
        ├─ Structure data
        ├─ Analyze content
        └─ Score confidence
```

---

## DSL GENERATION & RULE ENGINE FLOW

```
                     POLICY DOCUMENT
                            |
                            v
                  ┌──────────────────────┐
                  │  DSL EXTRACTOR       │
                  │  (dsl_extractor.py)  │
                  └──────────────┬───────┘
                                 |
                    ┌────────────┴────────────┐
                    |                        |
                    v                        v
            TYPE DETECTION          BUILD PROMPTS
            ├─ appliance            ├─ coupon_prompt
            ├─ auto                 ├─ appliance_prompt
            └─ coupon               └─ auto_prompt
                |                        |
                └────────────┬───────────┘
                             |
                             v
                        CALL LLM
                    (Structured extraction)
                             |
                             v
                   ┌──────────────────────┐
                   │  DSL GENERATOR       │
                   │  (dsl_generator.py)  │
                   └──────────────┬───────┘
                                  |
                    ┌─────────────┴──────────────┐
                    |                           |
                    v                           v
            TEMPLATE SELECTION        DATA VALIDATION
            ├─ consumer_coupon.j2    ├─ Type check
            ├─ appliance_subsidy.j2  ├─ Range validation
            └─ auto_subsidy.j2       └─ Required fields
                |                        |
                └────────────┬───────────┘
                             |
                             v
                      JINJA2 RENDERING
                    (dsl_generator.py)
                             |
                             v
                        YAML OUTPUT
                            |
                            v
        ┌───────────────────────────────────┐
        │  GENERATED RULE YAML              │
        │                                   │
        │  rule_id: Rule_Appliance_001      │
        │  policy_source:                   │
        │    doc_id: "gov_2025_001"         │
        │    title: "2025年家电补贴政策"     │
        │  inputs:                          │
        │    - name: appliance_price        │
        │      type: float                  │
        │    - name: energy_grade           │
        │      type: string                 │
        │  limits:                          │
        │    max_subsidy: 5000.0            │
        │  tiers:                           │
        │    - range: [0, 2000]             │
        │      subsidy_rate: 0.0            │
        │    - range: [2000, 5000]          │
        │      subsidy_rate: 0.2            │
        │  calc:                            │
        │    base_subsidy: |                │
        │      tier[0].subsidy_rate *       │
        │      appliance_price              │
        │  output:                          │
        │    status: "{{ result.status }}"  │
        │    final_result: "{{ result }}"   │
        └───────────────────────────────────┘
                        |
                        v
                   SAVE TO FILE
                (rules/Rule_*.yaml)
                        |
                        v
        ┌───────────────────────────────────┐
        │     POLICY ENGINE                 │
        │   (rule_engine.py)                │
        │                                   │
        │  LOAD RULES                       │
        │  ├─ Scan rules/ directory         │
        │  ├─ Parse YAML files              │
        │  └─ Cache in memory               │
        │                                   │
        │  EXECUTE RULE(rule_id, inputs)    │
        │  ├─ Validate inputs               │
        │  ├─ Evaluate calc expressions     │
        │  │  (Jinja2 + context)            │
        │  ├─ Apply limits/tiers            │
        │  ├─ Generate trace                │
        │  └─ Return result                 │
        └──────────────┬────────────────────┘
                       |
                       v
        ┌───────────────────────────────────┐
        │     EXECUTION RESULT              │
        │                                   │
        │  {                                │
        │    "status": "SUCCESS",           │
        │    "final_result": 1000.0,        │
        │    "trace": [                     │
        │      "Input: price=5000, ...",    │
        │      "Matched tier: 2000-5000",   │
        │      "Rate: 0.2",                 │
        │      "Calculation: 5000*0.2=1000" │
        │    ]                              │
        │  }                                │
        └───────────────────────────────────┘
```

---

## TEXT-TO-SQL PIPELINE

```
                   NATURAL LANGUAGE QUERY
                   "销售最多的产品是什么?"
                            |
                            v
        ┌─────────────────────────────────┐
        │  QUERY ANALYZER                 │
        │  (query_analyzer.py)            │
        │                                 │
        │  ├─ Intent: "list_top"          │
        │  ├─ Entities: ["product"]       │
        │  ├─ Metric: ["sales_count"]     │
        │  ├─ Order: "descending"         │
        │  └─ Limit: 1                    │
        └──────────────┬──────────────────┘
                       |
                       v
        ┌─────────────────────────────────┐
        │  SCHEMA RETRIEVER               │
        │  (schema_retriever.py)          │
        │                                 │
        │  ├─ Get database schema         │
        │  ├─ Rank tables by relevance    │
        │  │  (semantic similarity)       │
        │  ├─ Select columns              │
        │  └─ Return: [                   │
        │      {table: "products",        │
        │       columns: ["id", "name",   │
        │                  "sales"]},     │
        │      ...                        │
        │    ]                            │
        └──────────────┬──────────────────┘
                       |
                       v
        ┌─────────────────────────────────┐
        │  SQL GENERATOR                  │
        │  (sql_generator.py)             │
        │                                 │
        │  ├─ Strategy 1: Direct SQL      │
        │  │  SELECT name, sales          │
        │  │  FROM products               │
        │  │  ORDER BY sales DESC         │
        │  │  LIMIT 1                     │
        │  │                              │
        │  └─ Strategy 2: Hybrid          │
        │     (if confidence < threshold) │
        │     ├─ Generate alternative 1  │
        │     ├─ Generate alternative 2  │
        │     └─ Execute all & merge     │
        └──────────────┬──────────────────┘
                       |
                       v
        ┌─────────────────────────────────┐
        │  SQL EXECUTOR                   │
        │  (sql_executor.py)              │
        │                                 │
        │  ├─ Validate SQL syntax         │
        │  ├─ Check permissions           │
        │  ├─ Execute on database         │
        │  ├─ Handle errors with fallback │
        │  └─ Return: result set          │
        └──────────────┬──────────────────┘
                       |
                       v
        ┌─────────────────────────────────┐
        │  VISUALIZATION RECOMMENDER      │
        │  (visualization_recommender.py) │
        │                                 │
        │  ├─ Analyze result type         │
        │  ├─ Recommend chart type        │
        │  │  (bar/line/table/etc)        │
        │  └─ Return: viz config          │
        └──────────────┬──────────────────┘
                       |
                       v
        ┌─────────────────────────────────┐
        │  RESPONSE FORMATTER             │
        │                                 │
        │  {                              │
        │    "answer": "iPhone 13最畅销", │
        │    "data": [{                   │
        │      "name": "iPhone 13",       │
        │      "sales": 15000             │
        │    }],                          │
        │    "sql_generated": "...",      │
        │    "visualization": {           │
        │      "type": "bar",             │
        │      "x_axis": "product_name",  │
        │      "y_axis": "sales"          │
        │    }                            │
        │  }                              │
        └─────────────────────────────────┘
```

---

## DATA PERSISTENCE ARCHITECTURE

```
                        APPLICATION
                            |
            ┌───────────────┼───────────────┐
            |               |               |
            v               v               v
        VECTOR STORE    RELATIONAL DB    CACHE LAYER
            |               |               |
            v               v               v
        ┌─────────┐     ┌─────────┐    ┌─────────┐
        │ MILVUS  │     │ MYSQL   │    │ REDIS   │
        │ v2.3.3  │     │ v8.0    │    │ v7      │
        └────┬────┘     └────┬────┘    └────┬────┘
             |               |              |
             v               v              v
    
    MILVUS STORAGE HIERARCHY
    
    Cluster
    ├─ RootCoord (metadata)
    ├─ MetaStore (via etcd)
    │  └─ Collection definitions
    │     └─ Fields, schema
    ├─ DataNode (insert/delete)
    ├─ QueryNode (search)
    └─ ObjectStorage (via MinIO)
       └─ Segment snapshots
    
    Collection: "policy_documents"
    ├─ Partitions
    │  ├─ "2025_appliance"
    │  ├─ "2025_auto"
    │  └─ "2025_coupon"
    └─ Segments (auto-managed)
       ├─ Growing (insertions)
       └─ Sealed (indexed)
    
    MYSQL SCHEMA
    
    Tables:
    ├─ chat_history
    │  ├─ id (PK)
    │  ├─ user_id
    │  ├─ session_id
    │  ├─ query (text)
    │  ├─ answer (longtext)
    │  ├─ confidence (float)
    │  ├─ metadata (JSON)
    │  ├─ created_at (timestamp)
    │  └─ updated_at (timestamp)
    │
    ├─ db_connections
    │  ├─ id (PK)
    │  ├─ name
    │  ├─ connection_string
    │  ├─ db_type (mysql/postgres/etc)
    │  └─ metadata (JSON)
    │
    ├─ schema_tables
    │  ├─ id (PK)
    │  ├─ connection_id (FK)
    │  ├─ table_name
    │  ├─ description
    │  ├─ row_count
    │  └─ last_updated
    │
    ├─ schema_columns
    │  ├─ id (PK)
    │  ├─ table_id (FK)
    │  ├─ column_name
    │  ├─ data_type
    │  ├─ nullable
    │  └─ description
    │
    └─ value_mappings
       ├─ id (PK)
       ├─ column_id (FK)
       ├─ value
       ├─ description
       └─ example_queries
    
    REDIS CACHE STRUCTURE
    
    Keys:
    ├─ session:{session_id}
    │  └─ Value: {user_id, created_at, context}
    │
    ├─ chat_history:{session_id}
    │  └─ Value: [list of recent messages]
    │
    ├─ embedding_cache:{doc_id}
    │  └─ Value: cached embedding vector
    │
    └─ query_result:{query_hash}
       └─ Value: cached answer (expires in 1 hour)
    
    TTL STRATEGY
    ├─ Session: 24 hours
    ├─ Chat history: 7 days
    ├─ Embeddings: permanent
    └─ Query results: 1 hour
```

---

## CONFIGURATION & DEPENDENCY INJECTION

```
Environment (.env)
├─ LLM_*
├─ EMBEDDING_*
├─ DATABASE__*
├─ LIGHTRAG_*
└─ SYSTEM_*
    |
    v
app/config/app_config.py
├─ DatabaseSettings (Pydantic)
├─ ModelSettings
├─ EmbeddingSettings
├─ LlamaIndexSettings
├─ LightRAGSettings
├─ SystemSettings
├─ WebSearchSettings
└─ VisionSettings
    |
    v
app/core/config.py (Config singleton)
    |
    v
app/core/llms.py (LLM initialization)
    ├─ create_openai_client()
    └─ create_model_client() → OpenAIChatCompletionClient
    |
    v
app/core/model_clients.py (Model client factory)
    |
    v
app/knowledge/milvus.py (Vector store)
├─ Embedding backend selector
├─ Connection pool
└─ Collection initialization
    |
    v
app/agents/service/agent_service.py (Dependency assembly)
├─ KnowledgeService
├─ All pipeline agents
└─ Tools
    |
    v
FastAPI app.main.py / api_server.py
```

---

## CONCURRENT EXECUTION MODEL

```
                      USER QUERY
                           |
                           v
                    ASYNC ORCHESTRATOR
                           |
                ┌──────────┴──────────┐
                |                     |
                v                     v
           INTENT CHECK         CONFIDENCE ASSESS
                |                     |
                v                     v
         Single Intent      Multi Intent / Low Conf
                |                     |
         Single Path                 |
                |         ┌───────────┴─────────────┐
                |         |                         |
                v         v                         v
         Execute A    asyncio.gather()         Early Stop?
                |    (Chain A, Chain B)            |
                |         |                    Yes/No
                |         v                        |
                |    ┌─────────────┐               |
                |    │  Chain A    │ Finishes first
                |    │ Conf: 0.92  │ (>threshold)
                |    └─────────────┘              |
                |         |                        |
                |    ┌─────────────┐               |
                |    │  Chain B    │ Still running
                |    │ (60% done)  │               |
                |    └─────────────┘              |
                |         |                        |
                |    Return A (early stop)         |
                |    Cancel B                      |
                |         |                        |
                └────────┬┤ (or wait for both)
                         |
                         v
              SELECT BEST (highest conf)
                         |
                         v
                   FINAL ANSWER
```

---

## ERROR HANDLING & FALLBACK CHAIN

```
              PRIMARY EXECUTION PATH
                       |
                       v
                 Try Agent A
                       |
          ┌────────────┴────────────┐
          |                         |
        Success?               Timeout/Error?
          |                         |
          v                         v
      Return                   FALLBACK 1:
      Result              Try Alternative Agent
                                  |
                      ┌───────────┴───────────┐
                      |                       |
                    Success?            Timeout/Error?
                      |                       |
                      v                       v
                  Return                 FALLBACK 2:
                  Result              Use Cached Result
                                            |
                              ┌─────────────┴──────────┐
                              |                        |
                            Found?               Not Found?
                              |                        |
                              v                        v
                          Return                  FALLBACK 3:
                          Cached                 Generic Response
                                                      |
                                                      v
                                                 "I apologize..."
                                                 (Low confidence)
```

---

## SUMMARY STATISTICS

- **Total Modules**: 244 Python files
- **Total LOC**: 28,603 lines
- **Main Agent Classes**: 8+
- **Supporting Framework Classes**: 30+
- **Data Models**: 10+
- **API Endpoints**: 15+
- **Supported DB Backends**: 4 (Milvus, MySQL, Redis, Neo4j)
- **Supported LLM Backends**: 3+ (OpenAI, DashScope, DeepSeek)
- **Supported Embedding Backends**: 3+ (OpenAI, DashScope, Ollama)
- **Docker Services**: 5 (Milvus, etcd, MinIO, MySQL, Redis)

