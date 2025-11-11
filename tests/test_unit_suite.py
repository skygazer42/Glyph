"""
单元测试套件 - 不需要外部服务依赖
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAgentModels:
    """测试 Agent 模型"""

    @pytest.mark.unit
    def test_model_imports(self):
        """测试模型导入"""
        try:
            from app.agents.models import BaseModel
            from app.agents.framework.models import ResponseModel
            assert True
        except ImportError as e:
            pytest.fail(f"模型导入失败: {e}")

    @pytest.mark.unit
    def test_base_types(self):
        """测试基础类型定义"""
        from app.agents.framework.base.types import AgentState, Message

        # 测试消息创建
        msg = Message(content="test message", role="user")
        assert msg.content == "test message"
        assert msg.role == "user"

        # 测试状态创建
        state = AgentState()
        assert state is not None


class TestDSLGenerator:
    """测试 DSL 生成器（不需要 API）"""

    @pytest.mark.unit
    def test_dsl_generator_init(self):
        """测试 DSL 生成器初始化"""
        from app.agents.packs.dsl_generator.node import DSLGeneratorNode

        generator = DSLGeneratorNode()
        assert generator is not None
        assert hasattr(generator, 'generate')

    @pytest.mark.unit
    def test_dsl_generation_basic(self):
        """测试基础 DSL 生成"""
        from app.agents.packs.dsl_generator.node import DSLGeneratorNode

        generator = DSLGeneratorNode()

        test_text = """
        消费券补贴政策
        满100减20元
        活动时间：2025年1月1日至2025年3月31日
        """

        result = generator.generate(test_text)

        assert result is not None
        assert 'rule_id' in result
        assert 'name' in result
        assert result['name'] is not None

    @pytest.mark.unit
    def test_dsl_generation_complex(self):
        """测试复杂政策的 DSL 生成"""
        from app.agents.packs.dsl_generator.node import DSLGeneratorNode

        generator = DSLGeneratorNode()

        test_text = """
        家电补贴政策
        一级能效补贴20%，二级能效补贴15%
        单件最高补贴2000元
        空调限购3台，冰箱限购2台
        活动期限：2025年全年
        """

        result = generator.generate(test_text)

        assert result is not None
        assert 'subsidies' in result
        assert 'purchase_limits' in result
        assert 'valid_period' in result


class TestIntentRouter:
    """测试意图路由器"""

    @pytest.mark.unit
    def test_intent_router_init(self):
        """测试意图路由器初始化"""
        from app.agents.packs.intent_router.node import IntentRouterNode

        router = IntentRouterNode()
        assert router is not None
        assert hasattr(router, 'route')

    @pytest.mark.unit
    def test_intent_routing(self):
        """测试意图路由功能"""
        from app.agents.packs.intent_router.node import IntentRouterNode

        router = IntentRouterNode()

        # 测试不同的查询意图
        queries = [
            "济南有什么消费券？",
            "家电补贴怎么申请？",
            "补贴政策有哪些？"
        ]

        for query in queries:
            result = router.route(query)
            assert result is not None
            assert 'intent' in result or 'route' in result


class TestQueryAnalyzer:
    """测试查询分析器"""

    @pytest.mark.unit
    def test_query_analyzer_init(self):
        """测试查询分析器初始化"""
        from app.agents.packs.query_analyzer.node import QueryAnalyzerNode

        analyzer = QueryAnalyzerNode()
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze')

    @pytest.mark.unit
    def test_query_analysis(self):
        """测试查询分析功能"""
        from app.agents.packs.query_analyzer.node import QueryAnalyzerNode

        analyzer = QueryAnalyzerNode()

        query = "济南市2025年家电补贴政策是什么？"
        result = analyzer.analyze(query)

        assert result is not None
        # 根据实际返回结构调整断言
        assert isinstance(result, (dict, list, str))


class TestPolicyComparator:
    """测试政策比较器"""

    @pytest.mark.unit
    def test_policy_comparator_init(self):
        """测试政策比较器初始化"""
        from app.agents.packs.policy_comparator.node import PolicyComparatorNode

        comparator = PolicyComparatorNode()
        assert comparator is not None
        assert hasattr(comparator, 'compare')

    @pytest.mark.unit
    def test_policy_comparison(self):
        """测试政策比较功能"""
        from app.agents.packs.policy_comparator.node import PolicyComparatorNode

        comparator = PolicyComparatorNode()

        policy1 = {
            'name': '消费券政策',
            'subsidies': [{'amount': 20, 'threshold': 100}]
        }

        policy2 = {
            'name': '家电补贴政策',
            'subsidies': [{'rate': 0.2, 'max_amount': 2000}]
        }

        result = comparator.compare([policy1, policy2])
        assert result is not None


class TestConfigLoading:
    """测试配置加载"""

    @pytest.mark.unit
    def test_config_import(self):
        """测试配置模块导入"""
        from app.utils.config import Config

        config = Config()
        assert config is not None

    @pytest.mark.unit
    def test_llm_config(self):
        """测试 LLM 配置"""
        from app.core.llms import get_llm_client

        # 使用 mock 避免实际创建 LLM 连接
        with patch('app.core.llms.OpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            client = get_llm_client()
            assert client is not None


class TestDocumentLoader:
    """测试文档加载器"""

    @pytest.mark.unit
    def test_document_loader_import(self):
        """测试文档加载器导入"""
        from app.utils.document_loader import DocumentLoader

        loader = DocumentLoader()
        assert loader is not None

    @pytest.mark.unit
    def test_document_parsing(self):
        """测试文档解析功能"""
        from app.utils.document_loader import DocumentLoader

        loader = DocumentLoader()

        # 测试文本解析
        test_text = "这是一个测试文档"
        result = loader.parse_text(test_text)
        assert result is not None


@pytest.mark.unit
def test_imports_consistency():
    """测试导入一致性"""
    modules_to_test = [
        'app.agents.framework.base.types',
        'app.agents.packs',
        'app.core.llms',
        'app.utils.config'
    ]

    for module_name in modules_to_test:
        try:
            __import__(module_name)
        except ImportError as e:
            pytest.fail(f"无法导入模块 {module_name}: {e}")


if __name__ == "__main__":
    # 运行单元测试
    pytest.main([__file__, '-v', '-m', 'unit'])