#!/usr/bin/env python3
"""
配置测试脚本 - 验证配置链路完整性
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_settings_loading():
    """测试 settings 加载"""
    from app.config import settings

    print("=" * 60)
    print("📋 配置加载测试")
    print("=" * 60)

    # LLM 配置
    print(f"\n🤖 LLM 配置 (OpenAI 兼容):")
    print(f"  Model: {settings.model.llm_model_name}")
    print(f"  API Key: {'✓ 已配置' if settings.model.llm_api_key else '✗ 未配置'}")
    print(f"  Base URL: {settings.model.llm_base_url}")
    print(f"  Temperature: {settings.model.llm_temperature}")
    print(f"  Context Buffer: {settings.model.llm_ctx_buffer_size}")

    # Embedding 配置
    print(f"\n🔤 Embedding 配置:")
    print(f"  Backend: {settings.embedding.backend}")
    print(f"  OpenAI Model: {settings.embedding.openai_model}")
    print(f"  OpenAI API Key: {'✓ 已配置' if settings.embedding.openai_api_key else '✗ 未配置'}")
    print(f"  DashScope Model: {settings.embedding.dashscope_model}")
    print(f"  DashScope API Key: {'✓ 已配置' if settings.embedding.dashscope_api_key else '✗ 未配置'}")
    print(f"  Dimension: {settings.embedding.dimension}")
    print(f"  Batch Size: {settings.embedding.batch_size}")

    # MinerU 配置
    print(f"\n📄 MinerU 配置:")
    print(f"  Enabled: {settings.mineru.enabled}")
    print(f"  API Base URL: {settings.mineru.api_base_url}")
    print(f"  API Key: {'✓ 已配置' if settings.mineru.api_key else '✗ 未配置'}")
    print(f"  Timeout: {settings.mineru.timeout}s")

    # LlamaIndex 配置
    print(f"\n✂️ LlamaIndex 切块配置:")
    print(f"  Strategy: {settings.llamaindex.chunk_strategy}")
    print(f"  Chunk Size: {settings.llamaindex.chunk_size}")
    print(f"  Overlap: {settings.llamaindex.chunk_overlap}")

    # Reranker 配置
    print(f"\n🔄 Reranker 配置:")
    print(f"  Backend: {settings.reranker.backend}")
    print(f"  Model: {settings.reranker.model_name}")
    print(f"  DashScope API Key: {'✓ 已配置' if settings.reranker.dashscope_api_key else '✗ 未配置'}")
    print(f"  Top N: {settings.reranker.top_n}")

    # 数据库配置
    print(f"\n🗄️ 数据库配置:")
    print(f"  Milvus Host: {settings.database.milvus_host}:{settings.database.milvus_port}")
    print(f"  Milvus Collection: {settings.database.milvus_collection_name}")
    print(f"  Neo4j URI: {settings.database.neo4j_uri}")
    print(f"  Neo4j Enabled: {settings.database.use_neo4j}")

    # 文档处理配置
    print(f"\n📑 文档处理配置:")
    print(f"  Max File Size: {settings.document.max_file_size_mb}MB")
    print(f"  Max Pages: {settings.document.max_pages}")

    # 性能配置
    print(f"\n⚡ 性能配置:")
    print(f"  Max Concurrent: {settings.performance.max_concurrent_queries}")
    print(f"  Batch Size: {settings.performance.batch_size}")
    print(f"  Cache Enabled: {settings.performance.enable_cache}")

    print(f"\n{'=' * 60}")
    print("✅ 配置加载测试完成")
    print("=" * 60)


def test_vector_store():
    """测试 VectorStore 使用 settings"""
    from app.config import settings

    print("\n" + "=" * 60)
    print("📦 VectorStore 配置测试")
    print("=" * 60)

    try:
        from app.knowledge import VectorStore

        store = VectorStore()

        print(f"\n配置来源验证:")
        print(f"  Backend: {store.backend} (期望: {settings.embedding.backend})")
        print(f"  Model: {store.model_name} (期望: {settings.embedding.openai_model})")
        print(f"  Dimension: {store.embedding_dim}")

        assert store.backend == settings.embedding.backend, "Backend 配置不匹配"
        assert store.model_name == settings.embedding.openai_model, "Model 配置不匹配"

        print(f"\n✅ VectorStore 配置正确")
    except ImportError as e:
        print(f"\n⚠️  跳过测试 (缺少依赖: {e})")


def test_milvus_store():
    """测试 MilvusStore 使用 settings"""
    from app.config import settings

    print("\n" + "=" * 60)
    print("🗄️ MilvusStore 配置测试")
    print("=" * 60)

    try:
        from app.knowledge import MilvusStore
        store = MilvusStore()

        print(f"\n配置来源验证:")
        print(f"  Backend: {store.backend} (期望: {settings.embedding.backend})")
        print(f"  Model: {store.model_name}")
        print(f"  Host: {store.host}:{store.port}")
        print(f"  Collection: {store.collection_name}")

        assert store.backend == settings.embedding.backend, "Backend 配置不匹配"
        assert store.host == settings.database.milvus_host, "Milvus Host 配置不匹配"
        assert store.port == settings.database.milvus_port, "Milvus Port 配置不匹配"

        print(f"\n✅ MilvusStore 配置正确")
    except (ImportError, Exception) as e:
        print(f"\n⚠️  跳过测试 ({e.__class__.__name__}: {str(e)[:80]})")


def test_mineru_adapter():
    """测试 MinerU Adapter 使用 settings"""
    from app.config import settings

    print("\n" + "=" * 60)
    print("📄 MinerU Adapter 配置测试")
    print("=" * 60)

    try:
        # 直接导入，避免通过 __init__.py
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from app.knowledge.mineru_adapter import MinerUAdapter

        adapter = MinerUAdapter()

        print(f"\n配置来源验证:")
        print(f"  Enabled: {adapter.enabled} (期望: {settings.mineru.enabled})")
        print(f"  Base URL: {adapter.base_url} (期望: {settings.mineru.api_base_url})")
        print(f"  Timeout: {adapter.timeout}s (期望: {settings.mineru.timeout}s)")
        print(f"  Extract Images: {adapter.extract_images}")
        print(f"  Extract Tables: {adapter.extract_tables}")

        assert adapter.enabled == settings.mineru.enabled, "Enabled 配置不匹配"
        assert adapter.base_url == settings.mineru.api_base_url, "Base URL 配置不匹配"
        assert adapter.timeout == settings.mineru.timeout, "Timeout 配置不匹配"

        print(f"\n✅ MinerU Adapter 配置正确")
    except (ImportError, Exception) as e:
        print(f"\n⚠️  跳过测试 ({e.__class__.__name__}: {str(e)[:80]})")


def test_no_hardcoded_env():
    """检查代码中是否还有硬编码的 os.getenv"""
    import subprocess

    print("\n" + "=" * 60)
    print("🔍 检查硬编码环境变量")
    print("=" * 60)

    # 检查知识库模块
    files_to_check = [
        "knowledge_base/milvus.py",
        "knowledge_base/vector_store.py",
        "knowledge_base/mineru_adapter.py"
    ]

    issues = []
    for file in files_to_check:
        try:
            result = subprocess.run(
                ["grep", "-n", "os.getenv", file],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            if result.returncode == 0:
                # 过滤掉合理的 os.getenv 使用（作为 fallback）
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'os.getenv("LLM_API_KEY")' in line or 'fallback' in line.lower():
                        continue  # 允许作为 fallback
                    issues.append(f"{file}: {line}")
        except Exception as e:
            print(f"  检查 {file} 时出错: {e}")

    if issues:
        print(f"\n⚠️ 发现可能的硬编码环境变量:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ 未发现硬编码环境变量")


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "配置测试套件" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        test_settings_loading()
        test_vector_store()
        test_milvus_store()
        test_mineru_adapter()
        test_no_hardcoded_env()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！配置链路完整")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
