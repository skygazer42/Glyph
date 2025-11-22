#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/app"
INIT_FLAG="${APP_ROOT}/.initialized"

cd "$APP_ROOT"

echo "==> Starting Glyph API container"

# Wait for MySQL to be reachable
until python - <<'PY'
import sys
import pymysql
try:
    conn = pymysql.connect(
        host="mysql",
        port=3306,
        user="root",
        password="mysql",
        connect_timeout=3,
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
do
  echo "Waiting for MySQL..."
  sleep 3
done

if [ ! -f "$INIT_FLAG" ]; then
  echo "==> Running initial data import"
  set +e
  python scripts/1_create_tables.py
  python scripts/2_seed_mysql_text2sql.py
  python scripts/7_sync_text2sql_schema.py
  python scripts/5_embed_process_documents.py --input-dir resources/data/process
  python scripts/6_seed_lightrag.py --input-dir resources/data/process
  set -e
  touch "$INIT_FLAG"
  echo "==> Data import finished"
else
  echo "==> Data already initialized, skipping import"
fi

exec uvicorn api_server:app --host 0.0.0.0 --port 8000
