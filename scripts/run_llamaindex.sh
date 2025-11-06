#!/bin/bash

# LlamaIndex 分级索引快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
DATA_DIR="/data/temp33/gov/data/process"
STORAGE_DIR="/data/temp33/gov/storage/hierarchical"
CHUNK_SIZE=800
CHUNK_OVERLAP=100

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   LlamaIndex 分级索引系统${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python3 未安装${NC}"
    exit 1
fi

# 显示菜单
show_menu() {
    echo -e "${YELLOW}请选择操作:${NC}"
    echo "1) 构建索引 (从 Markdown 文档构建)"
    echo "2) 测试检索 (运行测试查询)"
    echo "3) 交互查询 (实时查询模式)"
    echo "4) 查看统计 (显示索引信息)"
    echo "5) 重建索引 (清除并重建)"
    echo "6) 安装依赖"
    echo "0) 退出"
    echo ""
    read -p "选择 [0-6]: " choice
}

# 构建索引
build_index() {
    echo -e "${GREEN}开始构建索引...${NC}"
    echo "数据目录: $DATA_DIR"
    echo "存储目录: $STORAGE_DIR"
    echo "切块大小: $CHUNK_SIZE 字符"
    echo "重叠大小: $CHUNK_OVERLAP 字符"
    echo ""

    python3 /data/temp33/gov/scripts/batch_process.py build \
        --data-dir "$DATA_DIR" \
        --storage-dir "$STORAGE_DIR" \
        --chunk-size $CHUNK_SIZE \
        --chunk-overlap $CHUNK_OVERLAP

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 索引构建成功！${NC}"
    else
        echo -e "${RED}❌ 索引构建失败${NC}"
    fi
}

# 测试检索
test_retrieval() {
    echo -e "${GREEN}运行检索测试...${NC}"

    python3 /data/temp33/gov/scripts/batch_process.py test \
        --storage-dir "$STORAGE_DIR" \
        --mode hybrid \
        --top-k 5

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 检索测试完成！${NC}"
    else
        echo -e "${RED}❌ 检索测试失败${NC}"
    fi
}

# 交互查询
interactive_query() {
    echo -e "${GREEN}进入交互查询模式...${NC}"
    echo -e "${YELLOW}提示: 输入 'quit' 或 'exit' 退出${NC}"
    echo ""

    python3 /data/temp33/gov/scripts/batch_process.py query \
        --storage-dir "$STORAGE_DIR" \
        --mode hybrid \
        --top-k 5
}

# 查看统计
show_stats() {
    echo -e "${GREEN}索引统计信息:${NC}"

    python3 /data/temp33/gov/scripts/batch_process.py stats \
        --storage-dir "$STORAGE_DIR"
}

# 重建索引
rebuild_index() {
    echo -e "${YELLOW}警告: 这将删除现有索引！${NC}"
    read -p "确认重建? (y/n): " confirm

    if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
        echo -e "${YELLOW}清除现有索引...${NC}"
        rm -rf "$STORAGE_DIR"/*
        echo -e "${GREEN}开始重建索引...${NC}"
        build_index
    else
        echo "操作取消"
    fi
}

# 安装依赖
install_deps() {
    echo -e "${GREEN}安装 Python 依赖...${NC}"

    cd /data/temp33/gov
    pip install -r requirements.txt

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 依赖安装成功！${NC}"
    else
        echo -e "${RED}❌ 依赖安装失败${NC}"
    fi
}

# 主循环
while true; do
    show_menu

    case $choice in
        1)
            build_index
            ;;
        2)
            test_retrieval
            ;;
        3)
            interactive_query
            ;;
        4)
            show_stats
            ;;
        5)
            rebuild_index
            ;;
        6)
            install_deps
            ;;
        0)
            echo -e "${GREEN}退出系统${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}无效选择，请重试${NC}"
            ;;
    esac

    echo ""
    echo -e "${YELLOW}按 Enter 继续...${NC}"
    read
    clear
done