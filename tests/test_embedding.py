#!/usr/bin/env python3
"""测试embedding配置"""

import sys
import os
from pathlib import Path

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if key in os.environ:
        del os.environ[key]

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# UTF-8输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from config.settings import settings
from llama_index.core import Settings as LISettings
from llama_index.embeddings.openai import OpenAIEmbedding

# 强制读取环境变量
import os
embedding_backend = os.getenv("EMBEDDING_BACKEND", "openai")

print("="*60)
print("Embedding配置测试")
print("="*60)

print("\n[1] 配置信息:")
print(f"   Backend (from env): {embedding_backend}")
print(f"   Backend (from settings): {settings.embedding.backend}")
print(f"   DashScope Model: {settings.embedding.dashscope_model}")
print(f"   DashScope API Key: {settings.embedding.dashscope_api_key[:10]}...")

print("\n[2] 配置LlamaIndex embedding (使用DashScope)...")
# 使用text-embedding-ada-002作为兼容的model type
LISettings.embed_model = OpenAIEmbedding(
    model="text-embedding-ada-002",  # 使用兼容的model type
    api_key=settings.embedding.dashscope_api_key,
    api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
print("   完成")

print("\n[3] 测试嵌入...")
try:
    test_text = "这是一个测试文本"
    embedding = LISettings.embed_model.get_text_embedding(test_text)
    print(f"   成功! 向量维度: {len(embedding)}")
    print(f"   向量前5个元素: {embedding[:5]}")
except Exception as e:
    print(f"   失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("测试完成")
print("="*60)
