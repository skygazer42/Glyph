#!/bin/bash

# Milvus Docker 管理脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
COMPOSE_FILE="docker-compose.yaml"
ENV_FILE=".env.docker"

# 检查 Docker 和 Docker Compose
check_prerequisites() {
    echo -e "${YELLOW}检查系统要求...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        echo "请访问 https://docs.docker.com/get-docker/ 安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        # 尝试使用 docker compose（新版本）
        if docker compose version &> /dev/null; then
            alias docker-compose='docker compose'
        else
            echo -e "${RED}错误: Docker Compose 未安装${NC}"
            echo "请访问 https://docs.docker.com/compose/install/ 安装 Docker Compose"
            exit 1
        fi
    fi

    echo -e "${GREEN}✓ Docker 和 Docker Compose 已安装${NC}"
}

# 创建必要的目录
create_directories() {
    echo -e "${YELLOW}创建数据目录...${NC}"
    mkdir -p docker/volumes/{etcd,minio,milvus}
    echo -e "${GREEN}✓ 目录创建完成${NC}"
}

# 启动 Milvus
start() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   启动 Milvus 向量数据库${NC}"
    echo -e "${GREEN}========================================${NC}"

    check_prerequisites
    create_directories

    # 加载环境变量
    if [ -f "$ENV_FILE" ]; then
        export $(cat $ENV_FILE | grep -v '^#' | xargs)
        echo -e "${YELLOW}已加载环境变量: $ENV_FILE${NC}"
    fi

    echo -e "${YELLOW}启动容器...${NC}"
    docker-compose -f $COMPOSE_FILE up -d

    echo -e "${YELLOW}等待服务就绪...${NC}"
    sleep 10

    # 检查服务状态
    if docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
        echo -e "${GREEN}✓ Milvus 启动成功！${NC}"
        echo ""
        echo -e "${GREEN}服务地址：${NC}"
        echo -e "  Milvus: ${GREEN}localhost:19530${NC}"
        echo -e "  Attu 管理界面: ${GREEN}http://localhost:8000${NC}"
        echo -e "  MinIO: ${GREEN}http://localhost:9001${NC} (用户名/密码: minioadmin/minioadmin)"
    else
        echo -e "${RED}✗ 启动失败，请检查日志${NC}"
        docker-compose -f $COMPOSE_FILE logs
        exit 1
    fi
}

# 停止 Milvus
stop() {
    echo -e "${YELLOW}停止 Milvus...${NC}"
    docker-compose -f $COMPOSE_FILE stop
    echo -e "${GREEN}✓ Milvus 已停止${NC}"
}

# 重启 Milvus
restart() {
    echo -e "${YELLOW}重启 Milvus...${NC}"
    stop
    start
}

# 删除 Milvus（保留数据）
down() {
    echo -e "${YELLOW}删除 Milvus 容器（保留数据）...${NC}"
    docker-compose -f $COMPOSE_FILE down
    echo -e "${GREEN}✓ 容器已删除，数据已保留在 docker/volumes 目录${NC}"
}

# 清理所有（包括数据）
clean() {
    echo -e "${RED}警告: 这将删除所有 Milvus 数据！${NC}"
    read -p "确认删除? (y/n): " confirm

    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "${YELLOW}删除容器和数据...${NC}"
        docker-compose -f $COMPOSE_FILE down -v
        rm -rf docker/volumes
        echo -e "${GREEN}✓ 清理完成${NC}"
    else
        echo "操作取消"
    fi
}

# 查看日志
logs() {
    service=$1
    if [ -z "$service" ]; then
        docker-compose -f $COMPOSE_FILE logs -f --tail=100
    else
        docker-compose -f $COMPOSE_FILE logs -f --tail=100 $service
    fi
}

# 查看状态
status() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Milvus 服务状态${NC}"
    echo -e "${GREEN}========================================${NC}"

    docker-compose -f $COMPOSE_FILE ps

    echo ""
    echo -e "${YELLOW}健康检查:${NC}"

    # 检查 Milvus
    if curl -s http://localhost:9091/healthz > /dev/null; then
        echo -e "  Milvus: ${GREEN}✓ 健康${NC}"
    else
        echo -e "  Milvus: ${RED}✗ 不健康${NC}"
    fi

    # 检查 MinIO
    if curl -s http://localhost:9000/minio/health/live > /dev/null; then
        echo -e "  MinIO: ${GREEN}✓ 健康${NC}"
    else
        echo -e "  MinIO: ${RED}✗ 不健康${NC}"
    fi

    # 检查 Attu
    if curl -s http://localhost:8000 > /dev/null; then
        echo -e "  Attu: ${GREEN}✓ 可访问${NC}"
    else
        echo -e "  Attu: ${RED}✗ 不可访问${NC}"
    fi
}

# 备份数据
backup() {
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="backups/milvus_$timestamp"

    echo -e "${YELLOW}备份 Milvus 数据到 $backup_dir...${NC}"

    mkdir -p $backup_dir

    # 停止服务
    echo -e "${YELLOW}停止服务...${NC}"
    docker-compose -f $COMPOSE_FILE stop standalone

    # 复制数据
    echo -e "${YELLOW}复制数据...${NC}"
    cp -r docker/volumes $backup_dir/

    # 重启服务
    echo -e "${YELLOW}重启服务...${NC}"
    docker-compose -f $COMPOSE_FILE start standalone

    # 压缩备份
    echo -e "${YELLOW}压缩备份...${NC}"
    tar -czf "$backup_dir.tar.gz" -C backups "milvus_$timestamp"
    rm -rf $backup_dir

    echo -e "${GREEN}✓ 备份完成: $backup_dir.tar.gz${NC}"
}

# 恢复数据
restore() {
    backup_file=$1

    if [ -z "$backup_file" ]; then
        echo -e "${RED}错误: 请指定备份文件${NC}"
        echo "用法: $0 restore <backup_file.tar.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}错误: 备份文件不存在: $backup_file${NC}"
        exit 1
    fi

    echo -e "${RED}警告: 这将覆盖现有数据！${NC}"
    read -p "确认恢复? (y/n): " confirm

    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "${YELLOW}停止服务...${NC}"
        docker-compose -f $COMPOSE_FILE down

        echo -e "${YELLOW}清理现有数据...${NC}"
        rm -rf docker/volumes

        echo -e "${YELLOW}解压备份...${NC}"
        tar -xzf $backup_file -C .
        backup_name=$(basename $backup_file .tar.gz)

        echo -e "${YELLOW}恢复数据...${NC}"
        mv backups/$backup_name/volumes docker/
        rm -rf backups/$backup_name

        echo -e "${YELLOW}重启服务...${NC}"
        start

        echo -e "${GREEN}✓ 数据恢复完成${NC}"
    else
        echo "操作取消"
    fi
}

# 显示帮助
show_help() {
    cat << EOF
Milvus Docker 管理工具

用法: $0 <command> [options]

命令:
    start       启动 Milvus 服务
    stop        停止 Milvus 服务
    restart     重启 Milvus 服务
    status      查看服务状态
    logs        查看日志
    down        删除容器（保留数据）
    clean       清理所有（包括数据）
    backup      备份数据
    restore     恢复数据
    help        显示帮助

示例:
    $0 start                # 启动服务
    $0 logs                 # 查看所有日志
    $0 logs standalone      # 查看 Milvus 日志
    $0 backup              # 备份数据
    $0 restore backup.tar.gz  # 恢复备份

服务端口:
    - Milvus: 19530
    - Attu 管理界面: 8000
    - MinIO: 9000/9001
EOF
}

# 主函数
main() {
    case "$1" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        down)
            down
            ;;
        clean)
            clean
            ;;
        logs)
            logs $2
            ;;
        status)
            status
            ;;
        backup)
            backup
            ;;
        restore)
            restore $2
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            show_help
            ;;
        *)
            echo -e "${RED}未知命令: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"