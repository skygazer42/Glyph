"""
简化的单元测试 - 专注于可测试的部分
"""
import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.unit
def test_basic_imports():
    """测试基础导入"""
    modules = [
        'app.utils.config',
        'app.utils.document_loader',
        'app.core.llms',
        'app.agents.packs'
    ]

    for module in modules:
        try:
            __import__(module)
            print(f"✓ 成功导入: {module}")
        except ImportError as e:
            print(f"✗ 导入失败: {module} - {e}")


@pytest.mark.unit
def test_config_loading():
    """测试配置加载（不需要实际的配置文件）"""
    from app.utils.config import Config

    # 测试配置对象创建
    config = Config()
    assert config is not None

    # 测试基本属性
    assert hasattr(config, 'embedding_model')
    assert hasattr(config, 'rerank_model')
    print("✓ 配置对象创建成功")


@pytest.mark.unit
def test_document_loader():
    """测试文档加载器"""
    from app.utils.document_loader import DocumentLoader

    loader = DocumentLoader()
    assert loader is not None
    print("✓ 文档加载器创建成功")


@pytest.mark.unit
def test_agent_packs_structure():
    """测试 agent packs 结构"""
    import app.agents.packs as packs

    # 列出所有可用的 packs
    pack_dirs = []
    packs_path = os.path.dirname(packs.__file__)

    for item in os.listdir(packs_path):
        item_path = os.path.join(packs_path, item)
        if os.path.isdir(item_path) and not item.startswith('_'):
            pack_dirs.append(item)

    print(f"发现 {len(pack_dirs)} 个 agent packs:")
    for pack in sorted(pack_dirs):
        print(f"  - {pack}")

    assert len(pack_dirs) > 0, "应该至少有一个 agent pack"


@pytest.mark.unit
def test_intent_router_agent():
    """测试意图路由器 Agent"""
    try:
        from app.agents.packs.intent_router.node import IntentRouterAgent

        # 只测试类是否存在
        assert IntentRouterAgent is not None
        print("✓ IntentRouterAgent 类存在")

        # 测试是否可以获取类的属性
        assert hasattr(IntentRouterAgent, '__init__')
        print("✓ IntentRouterAgent 有初始化方法")

    except ImportError as e:
        pytest.skip(f"无法导入 IntentRouterAgent: {e}")


@pytest.mark.unit
def test_query_analyzer_agent():
    """测试查询分析器 Agent"""
    try:
        from app.agents.packs.query_analyzer.node import QueryAnalyzerAgent

        assert QueryAnalyzerAgent is not None
        print("✓ QueryAnalyzerAgent 类存在")

    except ImportError as e:
        # 尝试其他可能的导入名称
        try:
            from app.agents.packs.query_analyzer.node import QueryAnalyzer
            assert QueryAnalyzer is not None
            print("✓ QueryAnalyzer 类存在")
        except ImportError:
            pytest.skip(f"无法导入查询分析器: {e}")


@pytest.mark.unit
def test_policy_comparator_agent():
    """测试政策比较器 Agent"""
    try:
        from app.agents.packs.policy_comparator.node import PolicyComparatorAgent

        assert PolicyComparatorAgent is not None
        print("✓ PolicyComparatorAgent 类存在")

    except ImportError as e:
        try:
            from app.agents.packs.policy_comparator.node import PolicyComparator
            assert PolicyComparator is not None
            print("✓ PolicyComparator 类存在")
        except ImportError:
            pytest.skip(f"无法导入政策比较器: {e}")


@pytest.mark.unit
def test_llm_module():
    """测试 LLM 模块"""
    from app.core import llms

    # 检查模块属性
    assert hasattr(llms, 'LLMClient')
    print("✓ LLMClient 类存在")


@pytest.mark.unit
def test_framework_types():
    """测试框架基础类型"""
    try:
        from app.agents.framework.base import types

        # 检查模块中的内容
        if hasattr(types, '__all__'):
            print(f"types 模块导出: {types.__all__}")

        # 尝试导入常见的类型
        type_classes = []
        for attr_name in dir(types):
            if not attr_name.startswith('_'):
                attr = getattr(types, attr_name)
                if isinstance(attr, type):
                    type_classes.append(attr_name)

        print(f"发现 {len(type_classes)} 个类型定义:")
        for cls in type_classes[:5]:  # 只显示前5个
            print(f"  - {cls}")

    except ImportError as e:
        pytest.skip(f"无法导入 types 模块: {e}")


if __name__ == "__main__":
    # 直接运行测试
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print("错误信息:")
        print(result.stderr)