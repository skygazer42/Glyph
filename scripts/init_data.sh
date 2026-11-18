#!/usr/bin/env bash
#
# Initialize the local knowledge base using DashScope embeddings by default.
# Steps:
#   1. Create database tables (ORM metadata, chat history, etc.)
#   2. Seed MySQL/Text2SQL policy data
#   3. Sync Text2SQL schema metadata (SchemaTable/SchemaColumn/SchemaRelationship)
#   4. Ensure Milvus collection exists
#   5. Build LlamaIndex hierarchical index from resources/data/process
#   6. Embed the same documents into Milvus
#   7. Seed LightRAG (optional; skip automatically if dependencies are missing)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Step 1/7: Creating database tables"
python -m scripts.create_tables

echo "==> Step 2/7: Seeding MySQL policy/Text2SQL data (auto-applying schema)"
python -m scripts.seed_mysql_text2sql

echo "==> Step 3/7: Syncing Text2SQL schema metadata"
python -m scripts.sync_text2sql_schema

echo "==> Step 4/7: Initializing Milvus collection"
python -m scripts.init_milvus

LAM_INDEX_ENABLED=$(python <<'PY'
from app.config.app_config import settings
print("true" if settings.system.hybrid_retrieval_enabled else "false")
PY
)

if [[ "$LAM_INDEX_ENABLED" == "true" ]]; then
  echo "==> Step 5/7: Building LlamaIndex hierarchical index (DashScope embedding assumed)"
  python -m scripts.embed_documents \
    --data-dir resources/data/process \
    --storage-dir resources/storage/hierarchical \
    --no-llm || {
    echo "⚠️  LlamaIndex 构建失败，请确认 OPENAI_API_KEY 或 DashScope 配置可用。"
    exit 1
  }
else
  echo "==> Step 5/7: Skipping LlamaIndex build (SYSTEM__HYBRID_RETRIEVAL_ENABLED=false)"
fi

echo "==> Step 6/7: Embedding documents into Milvus"
python -m scripts.embed_process_documents --input-dir resources/data/process

echo "==> Step 7/7: Seeding LightRAG (optional)"
if ! python -m scripts.seed_lightrag --input-dir resources/data/process; then
  echo "⚠️  LightRAG 种子导入失败，可能缺少 lightrag-hku 或配置。可忽略此步骤。"
fi

echo "✅ 数据初始化完成"
