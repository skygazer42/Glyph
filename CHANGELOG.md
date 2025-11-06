# 变更日志

## 2025-01-06 - 配置体系重构与简化

### ✨ 新增功能

- **Milvus 向量数据库支持** - 添加了生产级 Milvus 支持，可替代 FAISS
  - 新增 `knowledge_base/milvus.py` - Milvus 存储类
  - 支持分布式向量检索
  - 支持十亿级向量规模

- **统一配置体系** - 重构为 `.env` → `settings.py` → 模块使用 的标准链路
  - 新增 `EmbeddingSettings` - Embedding API 配置
  - 新增 `LlamaIndexSettings` - 文档切块配置
  - 扩展 `MinerUSettings` - MinerU 2.5 API 配置
  - 所有模块统一使用 `settings` 获取配置

- **配置文档**
  - 新增 `docs/CONFIG_GUIDE.md` - 完整配置指南
  - 新增 `tests/test_config.py` - 配置测试套件
  - 更新 `.env.example` - 完整配置模板

### 🔄 变更

- **简化 LLM 配置** - 统一使用 OpenAI 兼容接口
  - 移除独立的 OpenAI 配置项（`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`）
  - 所有 LLM 调用统一使用 `LLM_*` 配置
  - 支持 DeepSeek、OpenAI、本地部署等所有 OpenAI 兼容 API

- **简化文件命名** - 重命名9个过长的文件名
  - `enhanced_document_processor.py` → `doc_enhanced.py`
  - `document_processor.py` → `doc_processor.py`
  - `agent_orchestrator_service.py` → `orchestrator.py`
  - `autogen_orchestration_demo.py` → `orchestration_demo.py`
  - `intent_router_enhanced.py` → `router.py`
  - `question_understander.py` → `question.py`
  - `install_dependencies.py` → `install_deps.py`
  - `prompt_usage_example.py` → `prompt_example.py`
  - `autogen_orchestrator.py` → `ag_orchestrator.py`

### ❌ 删除

- **移除 Ollama 支持** - 不再支持本地 Ollama 嵌入
- **移除不需要的数据库配置** - 删除 Qdrant、ChromaDB、Pinecone 配置
- **移除 OCR 配置** - 删除独立的 OCR 服务配置
- **移除 Anthropic Claude 配置** - 精简 LLM 配置

### 🐛 修复

- 修复所有硬编码的 `os.getenv()` 调用
- 修复 Pydantic v2 配置兼容性问题
- 统一导入路径

### 📦 依赖

- 新增 `pymilvus>=2.4.0` - Milvus 客户端

### 🔧 配置变更

#### 新增环境变量

```bash
# Embedding 配置
EMBEDDING_BACKEND=openai
EMBEDDING_OPENAI_API_KEY=
EMBEDDING_OPENAI_MODEL=text-embedding-3-small
EMBEDDING_DASHSCOPE_API_KEY=
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v2
EMBEDDING_DIM=1536

# MinerU 2.5
MINERU_ENABLED=false
MINERU_API_BASE_URL=http://localhost:8080
MINERU_API_KEY=
MINERU_TIMEOUT=300

# LlamaIndex 切块
LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=1000
LLAMAINDEX_CHUNK_OVERLAP=200

# Milvus
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
DATABASE__MILVUS_COLLECTION_NAME=policy_documents
```

#### 废弃的环境变量

```bash
# 以下变量已移除，不再使用
OPENAI_API_KEY          # 使用 LLM_API_KEY 代替
OPENAI_BASE_URL         # 使用 LLM_BASE_URL 代替
OPENAI_MODEL            # 使用 LLM_MODEL_NAME 代替
EMBEDDING_OLLAMA_*      # 不再支持 Ollama
DATABASE__QDRANT_*      # 不再支持 Qdrant
DATABASE__CHROMA_*      # 不再支持 ChromaDB
DATABASE__PINECONE_*    # 不再支持 Pinecone
DOCUMENT__OCR_*         # 不再支持独立 OCR 服务
ANTHROPIC_*             # 不再支持 Anthropic Claude
OLLAMA_*                # 不再支持 Ollama
```

### 📝 使用示例

#### 使用 Milvus 替代 FAISS

```python
# 旧方式
from knowledge_base import VectorStore
store = VectorStore()

# 新方式 - Milvus
from knowledge_base import MilvusStore
store = MilvusStore()
```

#### 统一配置方式

```python
# ❌ 旧方式 - 硬编码
import os
api_key = os.getenv("EMBEDDING_OPENAI_API_KEY")

# ✅ 新方式 - 使用 settings
from config.settings import settings
api_key = settings.embedding.openai_api_key
```

### 🧪 测试

运行配置测试：

```bash
python tests/test_config.py
```

### 📚 文档

- [配置指南](docs/CONFIG_GUIDE.md) - 完整配置说明
- [README](README.md) - 项目总览

---

## 迁移指南

### 从旧配置迁移

1. **更新 .env 文件**
   ```bash
   cp .env.example .env.new
   # 将旧的 .env 中的值迁移到 .env.new
   mv .env.new .env
   ```

2. **更新代码中的 import**
   ```python
   # 文件重命名后的导入
   from knowledge_base.doc_enhanced import EnhancedDocumentProcessor
   from knowledge_base.doc_processor import DocumentProcessor
   from services.orchestrator import AgentOrchestratorService
   ```

3. **移除 Ollama 相关配置**
   - 删除 `.env` 中所有 `*OLLAMA*` 变量
   - 如果使用 Ollama，请切换到 OpenAI 或 DashScope

4. **测试配置**
   ```bash
   python tests/test_config.py
   ```

### 破坏性变更

⚠️ **以下变更可能影响现有代码**：

1. **LLM 配置简化** - 移除独立的 OpenAI 配置，统一使用 LLM 配置
   - `OPENAI_API_KEY` → `LLM_API_KEY`
   - `OPENAI_BASE_URL` → `LLM_BASE_URL`
   - `OPENAI_MODEL` → `LLM_MODEL_NAME`
   - `settings.model.openai_*` 字段已移除

2. **文件重命名** - 需要更新所有导入语句

3. **移除 Ollama** - 如果依赖 Ollama，需要切换到其他后端

4. **配置结构变更** - `settings.model.llm_model` → `settings.model.llm_model_name`

---

**完整变更**: https://github.com/your-org/gov/compare/v1.0...v2.0
