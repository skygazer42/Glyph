#!/usr/bin/env python3
"""
MinerU 配置验证脚本

检查配置是否正确并提供建议
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def check_basic_config():
    """检查基础配置"""
    print("=" * 60)
    print("1. 基础配置")
    print("=" * 60)

    print(f"\n✓ MinerU 已启用: {settings.mineru.enabled}")
    print(f"✓ 运行模式: {settings.mineru.mode}")
    print(f"✓ 超时设置: {settings.mineru.timeout}s")
    print(f"✓ 默认语言: {settings.mineru.language}")
    print(f"✓ 批量并发: {settings.mineru.max_concurrent}")

    if not settings.mineru.enabled:
        print("\n⚠️  MinerU 未启用，请在 .env 中设置 MINERU_ENABLED=true")
        return False

    return True


def check_mode_config():
    """检查模式配置"""
    print("\n" + "=" * 60)
    print("2. 运行模式配置")
    print("=" * 60)

    effective_mode = settings.mineru.get_effective_mode()
    effective_url = settings.mineru.get_effective_base_url()

    print(f"\n配置模式: {settings.mineru.mode}")
    print(f"有效模式: {effective_mode}")
    print(f"Base URL: {effective_url}")

    if settings.mineru.mode == "auto":
        if settings.mineru.api_key:
            print("\n✓ 自动模式：检测到 API Key，将使用官方 API")
        else:
            print("\n✓ 自动模式：未检测到 API Key，将使用本地服务")

    return True


def check_official_api_config():
    """检查官方 API 配置"""
    print("\n" + "=" * 60)
    print("3. 官方 API 配置")
    print("=" * 60)

    effective_mode = settings.mineru.get_effective_mode()

    if effective_mode == "official" or settings.mineru.api_key:
        print(f"\nAPI Key: {'已设置 ✓' if settings.mineru.api_key else '未设置 ✗'}")
        print(f"官方 URL: {settings.mineru.official_base_url}")

        if not settings.mineru.api_key:
            print("\n⚠️  使用官方 API 需要设置 MINERU_API_KEY")
            print("   1. 访问 https://mineru.net")
            print("   2. 注册并获取 API Key")
            print("   3. 在 .env 中设置: MINERU_API_KEY=your_key")
            return False

        # 检查 API Key 格式
        if len(settings.mineru.api_key) < 20:
            print("\n⚠️  API Key 看起来不正确（太短）")
            return False

        print("\n✓ 官方 API 配置完整")
        return True
    else:
        print("\n⊘ 当前不使用官方 API")
        return True


def check_local_service_config():
    """检查本地服务配置"""
    print("\n" + "=" * 60)
    print("4. 本地服务配置")
    print("=" * 60)

    effective_mode = settings.mineru.get_effective_mode()

    if effective_mode == "local":
        print(f"\n本地服务 URL: {settings.mineru.api_base_url}")
        print(f"后端类型: {settings.mineru.backend}")

        if settings.mineru.backend == "vlm-http-client":
            if settings.mineru.vlm_server_url:
                print(f"VLM 服务器: {settings.mineru.vlm_server_url}")
            else:
                print("\n⚠️  使用 vlm-http-client 后端建议设置 MINERU_VLM_SERVER_URL")

        print("\n提示：确保本地服务已启动")
        print(f"  测试命令: curl {settings.mineru.api_base_url}/openapi.json")

        return True
    else:
        print("\n⊘ 当前不使用本地服务")
        return True


def check_extraction_options():
    """检查解析选项"""
    print("\n" + "=" * 60)
    print("5. 文档解析选项")
    print("=" * 60)

    options = {
        "提取图片": settings.mineru.extract_images,
        "提取表格": settings.mineru.extract_tables,
        "提取公式": settings.mineru.extract_formulas,
        "OCR 图片": settings.mineru.ocr_all_images,
    }

    print()
    for name, enabled in options.items():
        status = "✓ 已启用" if enabled else "✗ 已禁用"
        print(f"{status}: {name}")

    enabled_count = sum(options.values())
    if enabled_count == 0:
        print("\n⚠️  所有解析选项都已禁用，可能无法提取有效内容")
        return False

    return True


def check_performance_config():
    """检查性能配置"""
    print("\n" + "=" * 60)
    print("6. 性能配置")
    print("=" * 60)

    print(f"\n最大并发数: {settings.mineru.max_concurrent}")
    print(f"请求超时: {settings.mineru.timeout}s")

    if settings.mineru.max_concurrent > 10:
        print("\n⚠️  并发数较高，确保系统资源充足")
    elif settings.mineru.max_concurrent < 1:
        print("\n✗ 并发数不能小于 1")
        return False

    if settings.mineru.timeout < 60:
        print("\n⚠️  超时时间较短，大文件可能处理失败")

    return True


def provide_recommendations():
    """提供配置建议"""
    print("\n" + "=" * 60)
    print("7. 配置建议")
    print("=" * 60)

    effective_mode = settings.mineru.get_effective_mode()

    print("\n根据当前配置，推荐以下设置：\n")

    if effective_mode == "official":
        print("【官方 API 模式】")
        print("✓ 适合：小规模处理、快速开始")
        print("✓ 注意：注意 API 调用限制和费用")
        print("✓ 建议：")
        print("  - 监控 API 使用量")
        print("  - 设置合理的并发数（3-5）")
        print("  - 为大文件增加超时时间")
    else:
        print("【本地服务模式】")
        print("✓ 适合：大规模处理、数据隐私")
        print("✓ 注意：需要部署和维护服务")
        print("✓ 建议：")
        print("  - 确保服务稳定运行")
        print("  - 根据硬件调整并发数")
        print("  - 配置健康检查和监控")

    print("\n通用建议：")
    print("  - 使用 mode=auto 灵活切换")
    print("  - 在生产环境启用完整的解析选项")
    print("  - 根据文档类型调整超时时间")
    print("  - 批量处理时注意资源占用")


def print_summary(results):
    """打印检查总结"""
    print("\n" + "=" * 60)
    print("配置检查总结")
    print("=" * 60)

    passed = sum(results.values())
    total = len(results)

    print(f"\n通过: {passed}/{total}\n")

    for check_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")

    if passed == total:
        print("\n🎉 配置检查全部通过！")
        print("\n下一步：")
        print("  1. 运行测试: python examples/mineru_test.py")
        print("  2. 查看文档: docs/MINERU_ADAPTER_USAGE.md")
        print("  3. 开始使用: from app.knowledge.mineru_adapter import MinerUAdapter")
    else:
        print(f"\n⚠️  {total - passed} 项检查未通过，请查看上述详情并修正")
        print("\n参考文档：")
        print("  - 配置示例: docs/MINERU_CONFIG_EXAMPLES.md")
        print("  - 使用指南: docs/MINERU_ADAPTER_USAGE.md")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MinerU 配置验证")
    print("=" * 60)

    results = {
        "基础配置": check_basic_config(),
        "运行模式": check_mode_config(),
        "官方 API": check_official_api_config(),
        "本地服务": check_local_service_config(),
        "解析选项": check_extraction_options(),
        "性能配置": check_performance_config(),
    }

    provide_recommendations()
    print_summary(results)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 配置验证失败: {e}")
        sys.exit(1)
