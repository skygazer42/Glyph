#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 DashScope Embedding 维度"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("EMBEDDING_DASHSCOPE_API_KEY")
model = os.getenv("EMBEDDING_DASHSCOPE_MODEL", "text-embedding-v3")
dimension = int(os.getenv("EMBEDDING_DASHSCOPE_DIMENSION", "1536"))

print(f"API Key: {api_key[:20]}...")
print(f"Model: {model}")
print(f"Requested Dimension: {dimension}")

url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "model": model,
    "input": {"texts": ["测试文本"]},
    "parameters": {"dimension": dimension}
}

print("\n发送请求...")
response = requests.post(url, headers=headers, json=data, timeout=30)

print(f"状态码: {response.status_code}")
print(f"响应: {response.text[:500]}")

if response.status_code == 200:
    result = response.json()
    embedding = result["output"]["embeddings"][0]["embedding"]
    actual_dim = len(embedding)

    print(f"\n实际返回维度: {actual_dim}")
    print(f"是否匹配: {'✓' if actual_dim == dimension else '✗'}")
else:
    print("\n请求失败，尝试不带dimension参数...")

    data2 = {
        "model": model,
        "input": {"texts": ["测试文本"]}
    }

    response2 = requests.post(url, headers=headers, json=data2, timeout=30)
    print(f"状态码: {response2.status_code}")

    if response2.status_code == 200:
        result = response2.json()
        embedding = result["output"]["embeddings"][0]["embedding"]
        actual_dim = len(embedding)
        print(f"默认维度: {actual_dim}")
