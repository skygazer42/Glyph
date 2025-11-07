#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Milvus 维度自动推断功能
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

def test_dimension_inference():
    """测试不同配置下的维度推断"""
    print("=" * 80)
    print("  Milvus 维度推断测试")
    print("=" * 80)

    from knowledge_base.milvus import MilvusStore

    # 测试 1: DashScope backend，使用默认配置
    print("\n测试 1: DashScope backend（当前 .env 配置）")
    print("-" * 60)
    try:
        store = MilvusStore(
            backend="dashscope",
            collection_name="test_dim_inference_1",
            host="localhost",
            port=19530
        )
        print(f"✓ Backend: {store.backend}")
        print(f"✓ Model: {store.model_name}")
        print(f"✓ 推断维度: {store.embedding_dim}")
        print(f"✓ Collection: {store.collection_name}")

        # 清理
        from pymilvus import utility
        if utility.has_collection("test_dim_inference_1"):
            utility.drop_collection("test_dim_inference_1")
            print("✓ 已清理测试集合")

    except Exception as e:
        print(f"✗ 失败: {e}")

    # 测试 2: OpenAI backend with text-embedding-3-small
    print("\n测试 2: OpenAI backend (text-embedding-3-small)")
    print("-" * 60)
    try:
        store = MilvusStore(
            backend="openai",
            model_name="text-embedding-3-small",
            collection_name="test_dim_inference_2",
            host="localhost",
            port=19530
        )
        print(f"✓ Backend: {store.backend}")
        print(f"✓ Model: {store.model_name}")
        print(f"✓ 推断维度: {store.embedding_dim}")
        print(f"✓ Collection: {store.collection_name}")

        # 清理
        from pymilvus import utility
        if utility.has_collection("test_dim_inference_2"):
            utility.drop_collection("test_dim_inference_2")
            print("✓ 已清理测试集合")

    except Exception as e:
        print(f"✗ 失败: {e}")

    # 测试 3: OpenAI backend with text-embedding-3-large
    print("\n测试 3: OpenAI backend (text-embedding-3-large)")
    print("-" * 60)
    try:
        store = MilvusStore(
            backend="openai",
            model_name="text-embedding-3-large",
            collection_name="test_dim_inference_3",
            host="localhost",
            port=19530
        )
        print(f"✓ Backend: {store.backend}")
        print(f"✓ Model: {store.model_name}")
        print(f"✓ 推断维度: {store.embedding_dim}")
        print(f"✓ Collection: {store.collection_name}")

        # 清理
        from pymilvus import utility
        if utility.has_collection("test_dim_inference_3"):
            utility.drop_collection("test_dim_inference_3")
            print("✓ 已清理测试集合")

    except Exception as e:
        print(f"✗ 失败: {e}")

    # 测试 4: 维度不匹配检测
    print("\n测试 4: 维度不匹配检测")
    print("-" * 60)
    try:
        # 先创建一个1024维的collection
        store1 = MilvusStore(
            backend="dashscope",
            collection_name="test_dim_mismatch",
            host="localhost",
            port=19530
        )
        print(f"✓ 创建了 {store1.embedding_dim}维 的 collection")

        # 尝试用不同维度连接
        print("  尝试用不同维度连接...")
        try:
            store2 = MilvusStore(
                backend="openai",
                model_name="text-embedding-3-small",  # 1536维
                collection_name="test_dim_mismatch",
                host="localhost",
                port=19530
            )
            print("✗ 应该检测到维度不匹配但没有抛出错误")
        except (ValueError, ConnectionError) as ve:
            print(f"✓ 正确检测到维度不匹配")
            # 提取第一行错误信息
            error_msg = str(ve).split('\n')[0]
            print(f"  错误信息: {error_msg[:100]}...")

        # 清理
        from pymilvus import utility
        if utility.has_collection("test_dim_mismatch"):
            utility.drop_collection("test_dim_mismatch")
            print("✓ 已清理测试集合")

    except Exception as e:
        print(f"✗ 测试失败: {str(e)[:100]}")
        # 确保清理
        try:
            from pymilvus import utility
            if utility.has_collection("test_dim_mismatch"):
                utility.drop_collection("test_dim_mismatch")
        except:
            pass

    print("\n" + "=" * 80)
    print("  测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_dimension_inference()
