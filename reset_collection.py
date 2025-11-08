"""
清理并重建 Milvus 集合
"""

import os
from pymilvus import connections, utility
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("DATABASE__MILVUS_HOST", "localhost")
port = int(os.getenv("DATABASE__MILVUS_PORT", "19530"))
collection_name = os.getenv("DATABASE__MILVUS_COLLECTION_NAME", "policy_documents")

print(f"连接到 Milvus: {host}:{port}")

connections.connect(
    alias="default",
    host=host,
    port=str(port)
)

# 检查集合是否存在
if utility.has_collection(collection_name):
    print(f"删除现有集合: {collection_name}")
    utility.drop_collection(collection_name)
    print("[OK] 集合已删除")
else:
    print(f"集合 {collection_name} 不存在")

connections.disconnect("default")
print("[OK] 完成!")
