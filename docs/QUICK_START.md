# 快速开始指南

## 🚀 5分钟快速部署

### 方法一：自动部署（推荐）

```bash
# 克隆或进入项目目录
cd /data/temp33/gov

# 运行自动部署脚本
bash deploy.sh
```

脚本会自动完成：
- ✅ 检查系统依赖
- ✅ 创建必要目录
- ✅ 配置环境变量
- ✅ 安装Python依赖
- ✅ 启动Docker服务（Milvus + Redis）
- ✅ 初始化数据库
- ✅ 启动后端服务

### 方法二：手动部署

#### 1. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
pip install -r requirements.txt
pip install -r requirements_web.txt
```

#### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件，填入你的API密钥
vim .env
```

必填项：
```bash
JWT_SECRET=your_jwt_secret
OPENAI_API_KEY=your_api_key  # 或使用 DASHSCOPE_API_KEY
LLM_API_KEY=your_llm_api_key
```

#### 3. 启动依赖服务

```bash
# 启动 Milvus 和 Redis
docker-compose up -d

# 等待服务就绪（约30秒）
docker-compose ps
```

#### 4. 启动后端服务

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动后端API
python api_server.py

# 或后台运行
nohup python api_server.py > logs/api_server.log 2>&1 &
```

#### 5. 启动前端服务

```bash
# 进入前端目录
cd web

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 或构建生产版本
npm run build
```

---

## 📋 系统要求

### 硬件要求
- CPU: 4核心或以上
- 内存: 8GB或以上
- 磁盘: 50GB可用空间

### 软件要求
- Python: 3.8+
- Node.js: 16+
- Docker: 20.10+
- Docker Compose: 2.0+

---

## 🧪 功能测试

### 1. 测试安全网关

```bash
cd /data/temp33/gov

# 运行安全网关示例
python agents/security/gateway.py
```

### 2. 测试系统监控

```bash
# 运行监控示例
python agents/monitoring/monitor.py
```

### 3. 测试DSL生成

```bash
# 测试DSL生成器
python tests/test_dsl_generator.py
```

### 4. 测试知识库

```bash
# 测试向量检索
python tests/test_embedding.py

# 测试问答功能
python tests/test_qa.py
```

---

## 🔧 配置说明

### 安全配置

```bash
# .env 文件
JWT_SECRET=<生成一个强密码>
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_PER_MINUTE=60
```

生成JWT密钥：
```bash
openssl rand -hex 32
```

### Milvus配置

```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=policy_docs
```

### 嵌入模型配置

**选项1: 使用OpenAI**
```bash
EMBEDDING_BACKEND=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

**选项2: 使用DashScope**
```bash
EMBEDDING_BACKEND=dashscope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_MODEL=text-embedding-v3
EMBEDDING_DIMENSION=1024
```

### 监控配置

```bash
ENABLE_MONITORING=true
METRICS_INTERVAL=60

ENABLE_ALERTS=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_USERNAME=your_email@gmail.com
```

---

## 📊 API接口

### 健康检查
```bash
curl http://localhost:8000/api/health
```

### DSL生成
```bash
curl -X POST http://localhost:8000/api/dsl/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "济南市家电补贴政策..."
  }'
```

### 知识库搜索
```bash
curl -X POST http://localhost:8000/api/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "家电补贴条件",
    "top_k": 10
  }'
```

### 带认证的请求

```bash
# 1. 获取Token（需要先实现登录接口）
TOKEN="your_jwt_token"

# 2. 使用Token访问
curl -X POST http://localhost:8000/api/dsl/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "..."
  }'
```

---

## 🔍 监控面板

访问监控接口：
```bash
# 获取监控面板数据
curl http://localhost:8000/api/monitor/dashboard

# 获取健康检查
curl http://localhost:8000/api/monitor/health

# 获取指标统计
curl http://localhost:8000/api/monitor/metrics?name=query.duration
```

---

## 🐛 故障排查

### 问题1: Milvus连接失败

```bash
# 检查Milvus状态
docker-compose ps milvus

# 查看Milvus日志
docker-compose logs milvus

# 重启Milvus
docker-compose restart milvus
```

### 问题2: 向量维度不匹配

```bash
# 删除现有集合
python << EOF
from knowledge_base.milvus import MilvusStore
from pymilvus import utility
utility.drop_collection("policy_docs")
print("集合已删除，请重启服务")
EOF
```

### 问题3: 前端无法连接后端

```bash
# 检查后端是否运行
curl http://localhost:8000/api/health

# 检查防火墙
sudo ufw allow 8000
sudo ufw allow 3000

# 检查CORS配置
# 编辑 api_server.py，确认 allow_origins 包含前端地址
```

### 问题4: 速率限制触发

```bash
# 查看速率限制使用情况
python << EOF
from agents.security.gateway import RateLimiter
limiter = RateLimiter()
print(limiter.get_usage("user123"))
EOF

# 调整速率限制（编辑 .env）
RATE_LIMIT_PER_SECOND=20
```

---

## 📚 文档索引

- [完整架构指南](docs/AGENT_ARCHITECTURE_GUIDE.md)
- [架构图表](docs/ARCHITECTURE_DIAGRAMS.md)
- [Web应用文档](README_WEB.md)
- [DSL优化指南](docs/DSL_OPTIMIZATION_GUIDE.md)
- [检索方法对比](docs/RETRIEVAL_METHODS_COMPARISON.md)

---

## 🔐 安全最佳实践

### 生产环境清单

- [ ] 更改默认JWT密钥
- [ ] 配置HTTPS/TLS
- [ ] 启用防火墙
- [ ] 配置速率限制
- [ ] 启用审计日志
- [ ] 定期备份数据
- [ ] 配置告警通知
- [ ] 更新依赖版本
- [ ] 进行安全审计

### 敏感信息保护

```bash
# 不要提交 .env 到版本控制
echo ".env" >> .gitignore

# 使用密钥管理服务（生产环境）
# - AWS KMS
# - Azure Key Vault
# - HashiCorp Vault
```

---

## 📞 获取帮助

- 📖 查看文档：`docs/` 目录
- 🐛 报告问题：GitHub Issues
- 💬 技术支持：support@example.com

---

## 🎉 快速验证

运行完整测试：

```bash
# 1. 测试后端健康
curl http://localhost:8000/api/health

# 2. 测试DSL生成
curl -X POST http://localhost:8000/api/dsl/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "测试政策文本"}'

# 3. 访问前端
# 浏览器打开 http://localhost:3000

# 4. 查看监控
curl http://localhost:8000/api/monitor/dashboard
```

全部成功？恭喜！系统已就绪 🎊

---

**版本**: v1.0.0
**更新日期**: 2025-11-07
**维护团队**: 智能体架构团队
