"""
pytest 配置和 fixtures
"""
import pytest
import socket
import sys


def check_network_permission():
    """检查是否可以创建网络连接"""
    try:
        # 尝试创建一个socket连接到本地端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        # 不实际连接，只是检查是否可以创建socket
        sock.close()
        return True
    except (PermissionError, OSError) as e:
        if "Operation not permitted" in str(e) or isinstance(e, PermissionError):
            return False
        return True


# 全局变量：网络是否可用
NETWORK_AVAILABLE = check_network_permission()


def pytest_configure(config):
    """pytest 启动时的配置"""
    if not NETWORK_AVAILABLE:
        print("\n" + "=" * 60)
        print("警告: 检测到沙箱环境，网络连接被限制")
        print("将自动跳过需要网络的测试")
        print("=" * 60 + "\n")


def pytest_collection_modifyitems(config, items):
    """修改测试项集合，自动为需要网络的测试添加跳过标记"""
    skip_network = pytest.mark.skip(reason="沙箱环境禁止网络连接")

    for item in items:
        # 如果没有网络权限，跳过带有 requires_network 标记的测试
        if not NETWORK_AVAILABLE:
            if "requires_network" in item.keywords:
                item.add_marker(skip_network)

            # 自动检测某些明显需要网络的测试
            if any(keyword in item.nodeid for keyword in ["test_api", "test_docker", "api_server"]):
                item.add_marker(skip_network)


@pytest.fixture
def skip_if_no_network():
    """条件跳过 fixture"""
    if not NETWORK_AVAILABLE:
        pytest.skip("网络连接在当前环境中不可用")


@pytest.fixture
def mock_api_response():
    """模拟 API 响应的 fixture"""
    def _mock_response(status_code=200, json_data=None, text=""):
        class MockResponse:
            def __init__(self):
                self.status_code = status_code
                self.text = text
                self._json_data = json_data or {}

            def json(self):
                return self._json_data

        return MockResponse()

    return _mock_response