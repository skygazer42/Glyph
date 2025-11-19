# Glyph 智能问答系统部署指南

## 概述

本文档详细介绍Glyph系统的完整部署流程，包括Docker部署、原生部署以及Windows和Linux系统的差异说明。

## 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                    Glyph 系统架构                         │
├─────────────────────────────────────────────────────────┤
│  Frontend (Vue.js)                                      │
│  API Server (FastAPI)                                   │
│  ├─ AgentService (多智能体系统)                          │
│  ├─ Knowledge Retrieval (Milvus + LlamaIndex)           │
│  ├─ Rule Engine (DSL Policy Engine)                     │
│  └─ LightRAG (Knowledge Graph)                          │
├─────────────────────────────────────────────────────────┤
│  External Services (Docker)                             │
│  ├─ MySQL 8.0 (关系数据库)                               │
│  ├─ Milvus 2.4 (向量数据库)                             │
│  ├─ Redis (缓存/会话)                                   │
│  ├─ Etcd (Milvus元数据)                                 │
│  └─ MinIO (Milvus对象存储)                              │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 方式一：Docker Compose 部署（推荐）

#### 1. 环境准备

**系统要求：**
- CPU: 4核心以上
- 内存: 8GB以上
- 硬盘: 50GB以上可用空间
- 操作系统: Linux/macOS/Windows (Docker Desktop)

**安装Docker：**

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# CentOS/RHEL
sudo yum install -y docker-ce docker-ce-cli containerd.io

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. 克隆项目

```bash
git clone <your-repo-url>
cd Glyph
```

#### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量（必须配置API Key）
nano .env
```

**关键配置项：**
```bash
# LLM 配置（必须）
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=deepseek-v3.2-exp

# Embedding 配置
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_API_KEY=your-dashscope-key

# Vision 配置（可选）
VISION__ENABLED=true
VISION__API_KEY=your-vision-api-key

# Web Search 配置（可选）
WEB_SEARCH__ENABLED=true
WEB_SEARCH__TAVILY_API_KEY=your-tavily-key
```

#### 4. 启动基础服务

```bash
# 启动外部依赖服务（MySQL, Milvus, Redis等）
docker-compose up -d

# 等待服务启动完成（约2-3分钟）
docker-compose ps
```

#### 5. 安装Python依赖

```bash
# 创建Python虚拟环境
python3 -m venv glyph-env
source glyph-env/bin/activate  # Linux/macOS
# glyph-env\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

#### 6. 初始化数据

```bash
# 执行数据初始化脚本
chmod +x scripts/init_data.sh
./scripts/init_data.sh
```

**初始化脚本说明：**
1. 创建数据库表结构
2. 初始化MySQL示例数据
3. 同步Text2SQL元数据
4. 初始化Milvus集合
5. 构建LlamaIndex文档索引
6. 嵌入文档到Milvus向量库
7. 可选：初始化LightRAG知识图谱

#### 7. 启动API服务

```bash
# 方式一：直接启动
python api_server.py

# 方式二：使用uvicorn（推荐）
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

#### 8. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 测试API
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

### 方式二：原生部署

#### 1. 安装依赖服务

**MySQL 8.0:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mysql-server-8.0

# CentOS/RHEL
sudo yum install mysql-server

# 启动服务
sudo systemctl start mysql
sudo systemctl enable mysql

# 创建数据库
mysql -u root -p
CREATE DATABASE policy_db;
CREATE USER 'glyph'@'localhost' IDENTIFIED BY 'glyph';
GRANT ALL PRIVILEGES ON policy_db.* TO 'glyph'@'localhost';
FLUSH PRIVILEGES;
```

**Redis:**
```bash
# Ubuntu/Debian
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis

# 启动服务
sudo systemctl start redis
sudo systemctl enable redis
```

**Milvus:**
```bash
# 下载并安装Milvus
wget https://github.com/milvus-io/milvus/releases/download/v2.3.3/milvus-standalone-docker-compose.yml -O docker-compose.yml
docker-compose up -d
```

#### 2. 配置环境变量

同Docker部署，修改 `.env` 文件中的数据库连接地址：

```bash
DATABASE__MYSQL_HOST=localhost
DATABASE__MYSQL_PORT=3306
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
```

#### 3. 安装和初始化

```bash
# 创建虚拟环境并安装依赖
python3 -m venv glyph-env
source glyph-env/bin/activate
pip install -r requirements.txt

# 初始化数据
./scripts/init_data.sh

# 启动服务
python api_server.py
```

## Windows 部署特殊说明

### 1. 环境准备

**安装Docker Desktop:**
1. 访问 [Docker Desktop官网](https://www.docker.com/products/docker-desktop/)
2. 下载并安装Docker Desktop for Windows
3. 启动Docker Desktop，确保状态为"Running"

**安装Python:**
1. 访问 [Python官网](https://www.python.org/downloads/)
2. 下载Python 3.9+版本
3. 安装时勾选"Add Python to PATH"

**安装Git:**
1. 访问 [Git官网](https://git-scm.com/download/win)
2. 下载并安装Git for Windows

### 2. 部署步骤

```powershell
# 克隆项目
git clone <your-repo-url>
cd Glyph

# 创建虚拟环境
python -m venv glyph-env
glyph-env\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动基础服务
docker-compose up -d

# 配置环境变量
copy .env.example .env
# 使用记事本编辑.env文件，填入API Keys
notepad .env

# 运行数据初始化（需要WSL或Git Bash）
# 或者在PowerShell中使用：
bash scripts/init_data.sh

# 启动服务
python api_server.py
```

### 3. Windows特殊配置

**文件路径问题：**
Windows使用反斜杠路径，需要修改 `.env` 文件中的路径配置：

```bash
# Windows路径格式
USER_PROFILE_DB_PATH=resources\data\user_profiles.json
LOG_DIR=resources\logs
LLAMAINDEX_STORAGE_DIR=resources\storage\hierarchical
LIGHTRAG_WORKDIR=resources\data\lightrag
```

**PowerShell执行脚本：**
如果没有bash环境，可以手动执行初始化步骤：

```powershell
# 1. 创建数据库表
python scripts/1_create_tables.py

# 2. 初始化MySQL数据
python scripts/2_seed_mysql_text2sql.py

# 3. 同步Text2SQL模式
python scripts/7_sync_text2sql_schema.py

# 4. 初始化Milvus
python scripts/3_init_milvus.py

# 5. 构建索引
python scripts/4_embed_documents.py --data-dir resources/data/process --storage-dir resources/storage/hierarchical

# 6. 嵌入文档
python scripts/5_embed_process_documents.py --input-dir resources/data/process
```

## 生产环境配置

### 1. 性能优化

**系统配置：**
```bash
# 增加文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 优化内存配置
echo "vm.max_map_count=262144" >> /etc/sysctl.conf
sysctl -p
```

**Docker配置优化：**
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: policy_db
    volumes:
      - mysql_data:/var/lib/mysql
      - ./mysql.cnf:/etc/mysql/conf.d/mysql.cnf
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  milvus:
    image: milvusdb/milvus:v2.3.3
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

### 2. 安全配置

**API安全：**
```bash
# 修改默认密钥
SECURITY__JWT_SECRET=your-super-secret-jwt-key-here
SECURITY__API_DEFAULT_PASSWORD=your-secure-password

# 启用HTTPS（使用Nginx反向代理）
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**数据库安全：**
```bash
# 修改默认密码
MYSQL_ROOT_PASSWORD=your-strong-password
DATABASE__MYSQL_PASSWORD=your-mysql-password
```

### 3. 监控配置

**日志配置：**
```bash
# 启用详细日志
DEBUG=false
VERBOSE=true
LOG_DIR=/var/log/glyph

# 配置日志轮转
sudo vim /etc/logrotate.d/glyph
```

**健康检查：**
```bash
# 创建健康检查脚本
cat > health_check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost:8000/health || exit 1
mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD || exit 1
redis-cli ping || exit 1
EOF

chmod +x health_check.sh
```

## 故障排除

### 常见问题

**1. Docker服务启动失败**
```bash
# 检查Docker状态
sudo systemctl status docker

# 检查端口占用
sudo netstat -tulpn | grep :3306
sudo netstat -tulpn | grep :19530

# 清理Docker资源
docker system prune -a
```

**2. Python依赖安装失败**
```bash
# 升级pip
pip install --upgrade pip

# 清理缓存
pip cache purge

# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

**3. Milvus连接失败**
```bash
# 检查Milvus状态
docker logs milvus

# 检查网络连接
curl http://localhost:19530/health

# 重启Milvus服务
docker-compose restart milvus
```

**4. API Key配置错误**
```bash
# 验证API Key有效性
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('LLM API Key:', os.getenv('LLM_API_KEY')[:10] + '...')
print('Embedding API Key:', os.getenv('EMBEDDING_DASHSCOPE_API_KEY')[:10] + '...')
"
```

### 日志查看

```bash
# 查看应用日志
tail -f resources/logs/agent.log

# 查看Docker服务日志
docker-compose logs -f mysql
docker-compose logs -f milvus
docker-compose logs -f redis

# 查看系统日志
sudo journalctl -u docker -f
```

### 性能调优

**1. 数据库优化**
```sql
-- MySQL优化
SET GLOBAL innodb_buffer_pool_size = 1073741824;  -- 1GB
SET GLOBAL max_connections = 1000;
SET GLOBAL query_cache_size = 67108864;  -- 64MB
```

**2. Milvus优化**
```yaml
# milvus.yaml
common:
  DiskIndex.MaxDegree: 16
  DiskIndex.SearchCacheBudgetGBRatio: 0.125
```

**3. 应用优化**
```bash
# 增加并发数
PERFORMANCE__MAX_CONCURRENT_QUERIES=10

# 调整超时时间
PERFORMANCE__QUERY_TIMEOUT=60

# 启用缓存
PERFORMANCE__ENABLE_CACHE=true
PERFORMANCE__CACHE_TTL=7200
```

## 部署验证清单

- [ ] Docker环境已安装并运行
- [ ] 所有外部服务（MySQL, Redis, Milvus）已启动
- [ ] 环境变量配置正确（API Keys已填写）
- [ ] Python依赖安装完成
- [ ] 数据初始化脚本执行成功
- [ ] API服务启动无错误
- [ ] 健康检查接口返回正常
- [ ] 示例API调用成功
- [ ] 前端可以正常访问后端API

## 维护和更新

### 备份策略

```bash
# 数据库备份
mysqldump -u glyph -p policy_db > backup_$(date +%Y%m%d).sql

# Milvus数据备份
docker exec milvus milvus-cli backup create -n backup_$(date +%Y%m%d)

# 配置文件备份
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env resources/
```

### 更新流程

```bash
# 1. 备份当前数据
./backup.sh

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 运行数据库迁移（如果有）
python scripts/migrate.py

# 5. 重新初始化数据（如果需要）
./scripts/init_data.sh

# 6. 重启服务
docker-compose restart
pkill -f api_server.py
python api_server.py &
```

---

*如果您在部署过程中遇到问题，请参考故障排除章节或提交Issue获取支持。*