#!/usr/bin/env python3
"""
依赖安装脚本
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """运行命令并处理错误"""
    print(f"\n{'='*50}")
    print(f"安装: {description}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*50}\n")

    try:
        subprocess.run(cmd, check=True)
        print(f"✓ {description} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} 安装失败")
        print(f"错误: {e}")
        return False


def install_python_deps():
    """安装Python依赖"""
    print("\n=== 安装Python依赖 ===")

    # 基础依赖
    base_deps = [
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    ]

    # 文档处理依赖
    doc_deps = [
        [sys.executable, "-m", "pip", "install", "docling>=1.10.0"],
        [sys.executable, "-m", "pip", "install", "llama-index>=0.10.0"],
        [sys.executable, "-m", "pip", "install", "llama-index-readers-file>=0.1.0"],
        [sys.executable, "-m", "pip", "install", "aiohttp>=3.11.0"],
        [sys.executable, "-m", "pip", "install", "aiofiles>=24.1.0"],
        [sys.executable, "-m", "pip", "install", "requests>=2.31.0"]
    ]

    # OCR依赖（可选）
    ocr_deps = [
        [sys.executable, "-m", "pip", "install", "pillow>=10.0.0"],
        [sys.executable, "-m", "pip", "install", "easyocr>=1.7.0"],
        [sys.executable, "-m", "pip", "install", "pytesseract>=0.3.10"]
    ]

    # 安装所有依赖
    all_deps = base_deps + doc_deps + ocr_deps
    descriptions = [
        "升级pip",
        "基础依赖包",
        "Docling文档处理",
        "LlamaIndex框架",
        "LlamaIndex文件读取器",
        "异步HTTP客户端",
        "异步文件操作",
        "HTTP请求库",
        "PIL图像处理",
        "EasyOCR引擎",
        "Tesseract OCR"
    ]

    success_count = 0
    for cmd, desc in zip(all_deps, descriptions):
        if run_command(cmd, desc):
            success_count += 1

    print(f"\n安装完成: {success_count}/{len(all_deps)} 成功")


def install_system_deps():
    """安装系统依赖"""
    print("\n=== 检查系统依赖 ===")

    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version < (3, 8):
        print("✗ 需要Python 3.8或更高版本")
        return False
    else:
        print("✓ Python版本满足要求")

    # 检查系统工具
    tools = {
        "curl": "curl --version",
        "wget": "wget --version",
        "git": "git --version"
    }

    for tool, cmd in tools.items():
        try:
            subprocess.run(cmd.split(), check=True, capture_output=True)
            print(f"✓ {tool} 已安装")
        except:
            print(f"✗ {tool} 未安装，建议安装")


def setup_environment():
    """设置环境"""
    print("\n=== 设置环境 ===")

    # 创建必要的目录
    dirs = [
        "resources/data",
        "resources/data/raw",
        "resources/data/processed",
        "resources/data/test",
        "resources/logs",
        "resources/knowledge_base/vector_store"
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✓ 创建目录: {dir_path}")

    # 检查.env文件
    env_file = Path(".env")
    if not env_file.exists():
        print("✗ .env文件不存在，请根据.env.example创建")
    else:
        print("✓ .env文件已存在")


def main():
    """主函数"""
    print("=== Gove项目依赖安装器 ===")
    print("此脚本将安装所有必要的依赖\n")

    # 询问用户选项
    print("请选择安装选项：")
    print("1. 完整安装（推荐）")
    print("2. 仅安装Python依赖")
    print("3. 仅检查环境")

    choice = input("\n请输入选项 (1-3): ").strip()

    if choice == "1":
        install_system_deps()
        install_python_deps()
        setup_environment()
    elif choice == "2":
        install_python_deps()
    elif choice == "3":
        install_system_deps()
        setup_environment()
    else:
        print("无效选项")

    print("\n=== 安装完成 ===")
    print("\n后续步骤：")
    print("1. 配置.env文件中的API密钥")
    print("2. 启动MinerU服务: python scripts/start_mineru.py")
    print("3. 测试文档处理: python test_document_processor.py")
    print("4. 运行主程序: python unified_main.py --interactive")


if __name__ == "__main__":
    main()