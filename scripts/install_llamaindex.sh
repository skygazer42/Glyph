#!/bin/bash

# 安装 LlamaIndex 相关依赖

echo "安装 LlamaIndex 核心依赖..."

# 安装 faiss-cpu（不需要 GPU）
pip install faiss-cpu

# 安装 LlamaIndex 核心包
pip install llama-index llama-index-core

# 安装 LlamaIndex 扩展
pip install llama-index-readers-file \
           llama-index-embeddings-openai \
           sentence-transformers

# 如果需要 DashScope 支持
pip install dashscope

echo "依赖安装完成！"