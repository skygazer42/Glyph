#!/usr/bin/env bash
#
# Initialize the local knowledge base using DashScope embeddings by default.
# Steps:
#   1. Create database tables
#   2. Seed MySQL/Text2SQL data
#   3. Ensure Milvus collection exists
#   4. Build LlamaIndex hierarchical index from resources/data/process
#   5. Embed the same documents into Milvus
#   6. Seed LightRAG (optional; skip automatically if dependencies are missing)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Step 1/6: Creating database tables"
python scripts/1_create_tables.py

echo "==> Step 2/6: Seeding MySQL policy/Text2SQL data (auto-applying schema)"
python scripts/2_seed_mysql_text2sql.py

echo "==> Step 3/6: Initializing Milvus collection"
python scripts/3_init_milvus.py

LAM_INDEX_ENABLED=$(python <<'PY'
from app.config import settings
print("true" if getattr(getattr(settings, "system", settings), "hybrid_retrieval_enabled", False) else "false")
PY
)

if [[ "$LAM_INDEX_ENABLED" == "true" ]]; then
  echo "==> Step 4/6: Building LlamaIndex hierarchical index (DashScope embedding assumed)"
  python scripts/4_embed_documents.py \
    --data-dir resources/data/process \
    --storage-dir resources/storage/hierarchical \
    --no-llm || {
    echo "⚠️  LlamaIndex 构建失败，请确认 OPENAI_API_KEY 或 DashScope 配置可用。"
    exit 1
  }
else
  echo "==> Step 4/6: Skipping LlamaIndex build (SYSTEM__HYBRID_RETRIEVAL_ENABLED=false)"
fi

echo "==> Step 5/6: Embedding documents into Milvus"
python scripts/5_embed_process_documents.py --input-dir resources/data/process

echo "==> Step 6/6: Seeding LightRAG (optional)"
if ! python scripts/6_seed_lightrag.py --input-dir resources/data/process; then
  echo "⚠️  LightRAG 种子导入失败，可能缺少 lightrag-hku 或配置。可忽略此步骤。"
fi

echo "✅ 数据初始化完成"
