#!/usr/bin/env python3
"""
MinerU服务启动脚本
"""

import subprocess
import sys
import time
import requests
import os
from pathlib import Path


def check_docker():
    """检查Docker是否安装"""
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_port(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except:
            return True


def start_mineru_docker():
    """使用Docker启动MinerU"""
    print("使用Docker启动MinerU服务...")

    # Docker运行命令
    docker_cmd = [
        "docker", "run", "-d",
        "--name", "mineru-server",
        "-p", "8000:8000",
        "-v", f"{Path.cwd()}/data:/app/data",
        "--gpus", "all",  # 如果有GPU
        "openmmlab/mineru:2.5-latest"
    ]

    # 如果没有GPU，移除GPU参数
    try:
        subprocess.run(["nvidia-smi"], check=True, capture_output=True)
    except:
        docker_cmd.remove("--gpus")
        docker_cmd.remove("all")

    try:
        subprocess.run(docker_cmd, check=True)
        print("✓ MinerU Docker容器已启动")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Docker启动失败: {e}")
        return False


def start_mineru_local():
    """本地启动MinerU（需要预先安装）"""
    print("本地启动MinerU服务...")

    # 检查是否安装了MinerU
    try:
        import mineru
        print("✓ 检测到MinerU已安装")
    except ImportError:
        print("✗ MinerU未安装，请先安装：")
        print("  pip install mineru")
        return False

    # 启动服务脚本
    server_script = """
import uvicorn
from mineru.api import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

    # 写入临时脚本
    script_path = Path("mineru_server.py")
    script_path.write_text(server_script)

    try:
        # 启动服务
        subprocess.Popen([sys.executable, str(script_path)])
        print("✓ MinerU服务已启动")
        return True
    except Exception as e:
        print(f"✗ 启动失败: {e}")
        return False


def wait_for_service(max_wait=60):
    """等待服务启动"""
    print("等待MinerU服务启动...")

    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8000/health", timeout=1)
            if response.status_code == 200:
                print("✓ MinerU服务已就绪")
                return True
        except:
            pass

        time.sleep(1)
        print(f"  等待中... ({i+1}/{max_wait})")

    print("✗ 服务启动超时")
    return False


def main():
    """主函数"""
    print("=== MinerU服务启动器 ===\n")

    # 检查端口
    if check_port(8000):
        print("✗ 端口8000已被占用")
        print("  请先停止占用端口的进程或使用其他端口")
        return

    # 创建数据目录
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # 选择启动方式
    print("\n请选择启动方式：")
    print("1. Docker启动（推荐）")
    print("2. 本地启动")
    print("3. 仅检查服务状态")

    choice = input("\n请输入选项 (1-3): ").strip()

    if choice == "1":
        # Docker启动
        if not check_docker():
            print("✗ 未检测到Docker，请先安装Docker")
            return

        if start_mineru_docker():
            wait_for_service()

    elif choice == "2":
        # 本地启动
        if start_mineru_local():
            wait_for_service()

    elif choice == "3":
        # 检查状态
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✓ MinerU服务正在运行")
                print(f"  响应: {response.json()}")
            else:
                print(f"✗ 服务响应异常: {response.status_code}")
        except:
            print("✗ MinerU服务未运行")

    else:
        print("无效选项")


if __name__ == "__main__":
    main()