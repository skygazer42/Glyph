# Glyph 完整部署指南

本文档提供了Glyph政策智能问答系统的完整部署流程，包括从源码构建到系统测试的所有步骤。

## 目录

1. [环境准备](#环境准备)
2. [Docker服务部署](#docker服务部署)
3. [Conda环境配置](#conda环境配置)
4. [Python依赖安装](#python依赖安装)
5. [数据库初始化](#数据库初始化)
6. [数据导入](#数据导入)
7. [配置文件设置](#配置文件设置)
8. [启动服务](#启动服务)
9. [API测试](#api测试)
10. [常见问题](#常见问题)

## 环境准备

### 系统要求

- **操作系统**: Linux (Ubuntu 20.04+) / macOS (10.15+) / Windows 10+
- **CPU**: 4核心以上
- **内存**: 8GB以上（推荐16GB）
- **存储**: 50GB以上可用空间
- **GPU**: 可选，用于加速向量计算

### 必要软件安装

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y git docker.io docker-compose python3.10

# macOS (使用Homebrew)
brew install git docker docker-compose python@3.10

# Windows
# 安装 Git for Windows、Docker Desktop、Python 3.10
```

## Docker服务部署

Glyph系统依赖以下Docker服务：
- Milvus (向量数据库)
- MySQL (关系数据库)
- Redis (缓存)

### 1. 克隆项目

```bash
git clone https://github.com/your-org/glyph.git
cd glyph
```

### 2. 启动Docker服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f
```

### 3. 验证服务

```bash
# 检查Milvus
curl http://localhost:19530/health

# 检查MySQL
docker-compose exec mysql mysql -uroot -p123456 -e "SHOW DATABASES;"

# 检查Redis
docker-compose exec redis redis-cli ping
```

## Conda环境配置

### 1. 安装Miniconda

如果尚未安装Conda：

```bash
# Linux
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# macOS
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
bash Miniconda3-latest-MacOSX-x86_64.sh
```

### 2. 创建Conda环境

```bash
# 创建Python 3.10环境
conda create -n glyph python=3.10 -y

# 激活环境
conda activate glyph

# 验证Python版本
python --version
```

## Python依赖安装

### 1. 升级pip

```bash
pip install --upgrade pip
```

### 2. 安装项目依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# 如果有GPU，安装CUDA版本的PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

### 3. 验证安装

```bash
# 验证FastAPI
pip show fastapi

# 验证AutoGen
pip show autogen-core

# 验证数据库连接
python -c "import pymysql; import redis; from pymilvus import connections; print('All dependencies installed successfully')"
```

## 数据库初始化

### 1. MySQL数据库初始化

```bash
# 进入项目目录
cd /path/to/glyph

# 执行初始化脚本
python scripts/init_database.py

# 或手动执行SQL
docker-compose exec mysql mysql -uroot -p123456 < resources/database/glyph_init.sql
```

### 2. Milvus集合创建

```bash
# 创建Milvus集合
python scripts/create_milvus_collections.py
```

## 数据导入

项目提供了多个数据导入脚本，根据需要执行：

### 1. 导入政策文档

```bash
# 导入PDF政策文档
python scripts/data_ingestion.py \
    --input_dir resources/data/policy_docs \
    --batch_size 10

# 导入特定格式数据
python scripts/import_policy_data.py \
    --file resources/data/policy_sample.json
```

### 2. 构建知识库

```bash
# 生成文档向量
python scripts/generate_embeddings.py \
    --input_dir resources/knowledge_base \
    --model text-embedding-ada-002

# 构建LightRAG知识图谱
python scripts/build_lightrag.py \
    --input_dir resources/data \
    --output_dir resources/lightrag
```

### 3. 导入测试数据

```bash
# 导入测试用户数据
python scripts/import_test_data.py

# 导入DSL规则示例
python scripts/scripts/dsl/import_dsl_examples.py
```

## 配置文件设置

### 1. 复制环境配置

```bash
# 复制环境变量模板
cp .env.example .env
```

### 2. 编辑配置文件

```bash
# 使用vim或nano编辑
vim .env
```

配置示例：

```bash
# LLM API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=glyph

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=False
SECRET_KEY=your_secret_key_here

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/glyph.log
```

### 3. 创建日志目录

```bash
mkdir -p logs
chmod 755 logs
```

## 启动服务

### 1. 启动后端API服务

```bash
# 方式1：使用uvicorn启动
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# 方式2：使用gunicorn（生产环境）
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 api_server:app

# 方式3：使用Python直接运行
python api_server.py
```

### 2. 启动前端服务（可选）

```bash
# 进入前端目录
cd web

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 或构建生产版本
npm run build
npm run preview
```

### 3. 验证服务启动

```bash
# 检查API健康状态
curl http://localhost:8000/health

# 查看API文档
# 浏览器访问: http://localhost:8000/docs
```

## API测试

### 1. 准备测试环境

```bash
# 安装测试工具
pip install httpie pytest

# 创建测试脚本
cat > test_api.sh << 'EOF'
#!/bin/bash

API_BASE="http://localhost:8000/api/v1"

echo "=== 测试Glyph API ==="
```

### 2. 执行基础API测试

```bash
# 创建测试脚本
cat > test_apis.py << 'EOF'
import requests
import json

API_BASE = "http://localhost:8000/api/v1"

def test_health():
    """测试健康检查接口"""
    response = requests.get(f"{API_BASE}/health")
    print(f"Health Check: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_agent_chat():
    """测试智能体对话接口"""
    data = {
        "message": "什么是小微企业税收优惠政策？",
        "user_id": "test_user_001",
        "session_id": "test_session_001"
    }
    response = requests.post(f"{API_BASE}/agent/chat", json=data)
    print(f"Agent Chat: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result.get('answer', '')[:100]}...")
        print(f"Confidence: {result.get('confidence', 0)}")
    else:
        print(f"Error: {response.text}")
    print()

def test_knowledge_search():
    """测试知识搜索接口"""
    data = {
        "query": "税收优惠",
        "top_k": 5,
        "threshold": 0.7
    }
    response = requests.post(f"{API_BASE}/knowledge/search", json=data)
    print(f"Knowledge Search: {response.status_code}")
    if response.status_code == 200:
        results = response.json()
        print(f"Found {len(results.get('results', []))} results")
    print()

def test_dsl_generate():
    """测试DSL生成接口"""
    data = {
        "policy_description": "年营业额不超过100万的企业享受50%的税收减免",
        "policy_type": "tax_policy"
    }
    response = requests.post(f"{API_BASE}/dsl/generate", json=data)
    print(f"DSL Generate: {response.status_code}")
    if response.status_code == 200:
        dsl = response.json()
        print(f"Generated DSL:\n{json.dumps(dsl, indent=2, ensure_ascii=False)}")
    print()

if __name__ == "__main__":
    print("开始API测试...\n")
    test_health()
    test_agent_chat()
    test_knowledge_search()
    test_dsl_generate()
    print("API测试完成！")
EOF

# 执行测试
python test_apis.py
```

### 3. 使用curl测试

```bash
# 测试健康检查
curl -X GET http://localhost:8000/health

# 测试智能体对话
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "什么是高新技术企业认定标准？",
    "user_id": "test_user",
    "session_id": "test_session"
  }'

# 测试知识检索
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "研发费用加计扣除",
    "top_k": 3
  }'

# 测试DSL生成
curl -X POST http://localhost:8000/api/v1/dsl/generate \
  -H "Content-Type: application/json" \
  -d '{
    "policy_description": "研发投入超过销售收入5%的企业，可享受15%的所得税优惠",
    "policy_type": "tax_incentive"
  }'
```

### 4. 运行完整测试套件

```bash
# 运行项目单元测试
pytest tests/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行性能测试
python scripts/performance_test.py
```

## 高级配置

### 1. 配置Nginx反向代理（生产环境）

```nginx
# /etc/nginx/sites-available/glyph
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /path/to/glyph/web/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

### 2. 配置系统服务

```bash
# 创建systemd服务文件
sudo vim /etc/systemd/system/glyph.service
```

```ini
[Unit]
Description=Glyph Policy Q&A System
After=network.target

[Service]
Type=simple
User=glyph
WorkingDirectory=/opt/glyph
Environment=PATH=/opt/glyph/conda/bin
ExecStart=/opt/glyph/conda/bin/python api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 启用并启动服务
sudo systemctl enable glyph
sudo systemctl start glyph
sudo systemctl status glyph
```

## 监控和日志

### 1. 查看应用日志

```bash
# 实时查看日志
tail -f logs/glyph.log

# 查看错误日志
grep -i error logs/glyph.log

# 查看API访问日志
tail -f logs/access.log
```

### 2. 监控系统资源

```bash
# 查看Docker服务资源使用
docker stats

# 查看系统资源
htop

# 查看MySQL连接
docker-compose exec mysql mysql -uroot -p123456 -e "SHOW PROCESSLIST;"
```

## 常见问题

### Q1: Docker服务启动失败

**解决方案：**
```bash
# 检查Docker服务
sudo systemctl status docker

# 重新构建容器
docker-compose down
docker-compose up -d --build

# 清理Docker缓存
docker system prune -a
```

### Q2: Python依赖安装失败

**解决方案：**
```bash
# 更新conda
conda update conda

# 使用清华镜像源
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 单独安装问题依赖
pip install --no-deps package_name
```

### Q3: API响应慢

**解决方案：**
1. 检查网络连接
2. 优化批量处理大小
3. 启用缓存
4. 增加worker进程数

### Q4: 内存不足

**解决方案：**
1. 增加系统内存
2. 优化向量维度
3. 使用分批处理
4. 配置Redis缓存

### Q5: Milvus连接失败

**解决方案：**
```bash
# 检查Milvus服务
docker-compose ps milvus

# 重启Milvus
docker-compose restart milvus

# 查看Milvus日志
docker-compose logs milvus
```

## 部署检查清单

- [ ] Docker服务正常运行
- [ ] Conda环境创建成功
- [ ] Python依赖安装完成
- [ ] 数据库初始化完成
- [ ] 测试数据导入成功
- [ ] 环境变量配置正确
- [ ] API服务启动成功
- [ ] 所有API测试通过
- [ ] 日志记录正常
- [ ] 监控系统配置完成

## 性能优化建议

1. **向量搜索优化**：
   - 使用GPU加速
   - 调整索引类型
   - 优化向量维度

2. **并发处理优化**：
   - 增加worker进程
   - 使用连接池
   - 启用异步处理

3. **缓存策略**：
   - 启用Redis缓存
   - 缓存常用查询结果
   - 使用CDN加速

4. **数据库优化**：
   - 添加适当索引
   - 定期清理日志
   - 优化查询语句

## 安全建议

1. **API安全**：
   - 启用HTTPS
   - 配置API密钥认证
   - 实施速率限制

2. **数据安全**：
   - 加密敏感数据
   - 定期备份数据
   - 限制数据库访问权限

3. **系统安全**：
   - 定期更新依赖
   - 使用最小权限原则
   - 启用防火墙

---

## 联系支持

如果在部署过程中遇到问题，请：

1. 查看[常见问题](#常见问题)部分
2. 检查项目文档：`/docs/`
3. 提交Issue：https://github.com/your-org/glyph/issues
4. 联系技术支持：support@glyph.com

**部署成功后，您可以通过以下地址访问：**
- API文档：http://localhost:8000/docs
- Web界面：http://localhost:3000（如果启动了前端）
- API健康检查：http://localhost:8000/health