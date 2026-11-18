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
  python -m scripts.create_tables
  python -m scripts.seed_mysql_text2sql
  python -m scripts.sync_text2sql_schema
  python -m scripts.embed_process_documents --input-dir resources/data/process
  if ! python -m scripts.seed_lightrag --input-dir resources/data/process; then
    echo "LightRAG seed failed; required imports completed, graph setup remains pending."
  fi
  touch "$INIT_FLAG"
  echo "==> Data import finished"
else
  echo "==> Data already initialized, skipping import"
fi

exec uvicorn api_server:app --host 0.0.0.0 --port 8000
