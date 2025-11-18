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
python scripts/1_create_tables.py

echo "==> Step 2/7: Seeding MySQL policy/Text2SQL data (auto-applying schema)"
python scripts/2_seed_mysql_text2sql.py

echo "==> Step 3/7: Syncing Text2SQL schema metadata"
python scripts/7_sync_text2sql_schema.py

echo "==> Step 4/7: Initializing Milvus collection"
python scripts/3_init_milvus.py

LAM_INDEX_ENABLED=$(python <<'PY'
from app.config import settings
print("true" if getattr(getattr(settings, "system", settings), "hybrid_retrieval_enabled", False) else "false")
PY
)

if [[ "$LAM_INDEX_ENABLED" == "true" ]]; then
  echo "==> Step 5/7: Building LlamaIndex hierarchical index (DashScope embedding assumed)"
  python scripts/4_embed_documents.py \
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
python scripts/5_embed_process_documents.py --input-dir resources/data/process

echo "==> Step 7/7: Seeding LightRAG (optional)"
if ! python scripts/6_seed_lightrag.py --input-dir resources/data/process; then
  echo "⚠️  LightRAG 种子导入失败，可能缺少 lightrag-hku 或配置。可忽略此步骤。"
fi

echo "✅ 数据初始化完成"
