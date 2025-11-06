# Milvus 部署指南

## 📋 概述

本指南介绍如何使用 Docker Compose 部署 Milvus 向量数据库，用于政策文档的向量存储和检索。

## 🚀 快速开始

### 1. 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB 内存
- 20GB 可用磁盘空间

### 2. 一键启动

```bash
# 启动 Milvus
./scripts/milvus.sh start

# 查看状态
./scripts/milvus.sh status
```

启动后可访问：
- **Milvus 服务**: `localhost:19530`
- **Attu 管理界面**: `http://localhost:8000`
- **MinIO 对象存储**: `http://localhost:9001`

### 3. 基本操作

```bash
# 停止服务
./scripts/milvus.sh stop

# 重启服务
./scripts/milvus.sh restart

# 查看日志
./scripts/milvus.sh logs

# 查看 Milvus 日志
./scripts/milvus.sh logs standalone
```

## 📦 组件说明

### 架构组件

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    etcd     │     │    MinIO    │     │    Attu     │
│  (元数据)    │     │  (对象存储)  │     │  (管理界面)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────┬───────┘                    │
                   │                             │
            ┌──────▼──────┐                     │
            │   Milvus    │◄────────────────────┘
            │ Standalone  │
            └─────────────┘
```

### 服务说明

| 服务 | 端口 | 说明 |
|-----|------|------|
| Milvus | 19530 | 向量数据库主服务 |
| Attu | 8000 | Web 管理界面 |
| MinIO | 9000/9001 | 对象存储服务 |
| etcd | 2379 | 元数据存储 |

## 🔧 配置说明

### 环境变量 (`.env.docker`)

```bash
# Milvus 版本
MILVUS_VERSION=v2.4.0

# 性能配置
MILVUS_CACHE_SIZE=8GB          # 缓存大小
MILVUS_INSERT_BUFFER_SIZE=1GB  # 插入缓冲区

# 集合配置
MILVUS_COLLECTION_NAME=policy_documents
MILVUS_INDEX_TYPE=IVF_FLAT    # 索引类型
MILVUS_METRIC_TYPE=IP          # 相似度度量（内积）
```

### 索引类型选择

| 数据规模 | 推荐索引 | 说明 |
|---------|---------|------|
| < 10万 | FLAT | 暴力搜索，精度最高 |
| 10-100万 | IVF_FLAT | 聚类索引，平衡精度和速度 |
| > 100万 | IVF_SQ8 | 量化索引，节省内存 |
| > 1000万 | HNSW | 图索引，高速检索 |

## 📊 集成到项目

### 1. 更新项目配置

编辑 `.env` 文件：

```bash
# Milvus 配置
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
DATABASE__MILVUS_COLLECTION_NAME=policy_documents
DATABASE__MILVUS_USE_SECURE=false
```

### 2. 使用 Milvus 存储

```python
from knowledge_base.milvus import MilvusStore

# 初始化 Milvus 存储
store = MilvusStore(
    collection_name="policy_documents",
    host="localhost",
    port=19530
)

# 添加文档
await store.add_documents(documents)

# 搜索
results = await store.search("查询文本", top_k=10)
```

### 3. 切换存储后端

在 `config/settings.py` 中启用 Milvus：

```python
# 使用 Milvus 而不是 FAISS
DATABASE__USE_MILVUS=true
```

## 🔍 管理界面 (Attu)

### 访问 Attu

1. 浏览器打开 `http://localhost:8000`
2. 连接信息：
   - Host: `milvus-standalone`
   - Port: `19530`

### Attu 功能

- 查看集合和分区
- 监控查询性能
- 管理索引
- 数据可视化
- 执行向量搜索

## 🗄️ 数据管理

### 备份数据

```bash
# 创建备份
./scripts/milvus.sh backup

# 备份文件保存在 backups/ 目录
ls backups/
```

### 恢复数据

```bash
# 从备份恢复
./scripts/milvus.sh restore backups/milvus_20240101_120000.tar.gz
```

### 数据持久化

数据存储在 `docker/volumes/` 目录：
- `etcd/`: 元数据
- `minio/`: 对象存储
- `milvus/`: 向量索引

## 🔐 安全配置

### 生产环境建议

1. **修改默认密码**
   ```bash
   # .env.docker
   MINIO_ACCESS_KEY=your_access_key
   MINIO_SECRET_KEY=your_secret_key
   ```

2. **配置防火墙**
   - 只开放必要端口
   - 限制访问来源

3. **启用 TLS**
   - 配置 HTTPS 访问
   - 使用安全连接

## 📈 性能优化

### 1. 内存配置

根据数据规模调整：
```yaml
environment:
  MILVUS_CACHE_SIZE: 16GB  # 大数据集增加缓存
  MILVUS_INSERT_BUFFER_SIZE: 2GB
```

### 2. 索引参数

```python
# 构建索引时
index_params = {
    "metric_type": "IP",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 2048}  # 增加聚类数
}

# 搜索时
search_params = {
    "metric_type": "IP",
    "params": {"nprobe": 32}  # 增加搜索范围
}
```

### 3. 批量操作

```python
# 批量插入提高效率
batch_size = 10000
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    collection.insert(batch)
```

## 🐛 故障排除

### 常见问题

#### 1. 容器启动失败

```bash
# 检查端口占用
netstat -tuln | grep -E "19530|9000|2379"

# 查看错误日志
./scripts/milvus.sh logs
```

#### 2. 连接超时

```bash
# 检查服务健康状态
./scripts/milvus.sh status

# 重启服务
./scripts/milvus.sh restart
```

#### 3. 磁盘空间不足

```bash
# 检查磁盘使用
du -sh docker/volumes/*

# 清理旧数据
docker system prune -a
```

### 日志位置

- Milvus 日志: `docker-compose logs standalone`
- MinIO 日志: `docker-compose logs minio`
- etcd 日志: `docker-compose logs etcd`

## 📊 监控

### Prometheus 集成（可选）

添加到 `docker-compose.yaml`:

```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
```

### Grafana 仪表板（可选）

```yaml
grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

## 🔄 升级指南

### 升级 Milvus 版本

1. 备份数据
   ```bash
   ./scripts/milvus.sh backup
   ```

2. 更新版本
   ```bash
   # 编辑 .env.docker
   MILVUS_VERSION=v2.4.1
   ```

3. 重新部署
   ```bash
   ./scripts/milvus.sh down
   ./scripts/milvus.sh start
   ```

## 📚 相关资源

- [Milvus 官方文档](https://milvus.io/docs)
- [Attu 使用指南](https://github.com/zilliztech/attu)
- [性能调优指南](https://milvus.io/docs/performance_tuning.md)
- [API 参考](https://milvus.io/api-reference/pymilvus/v2.4.x/About.md)

## 💡 最佳实践

1. **定期备份**: 每周至少备份一次
2. **监控资源**: 关注内存和磁盘使用
3. **索引优化**: 根据数据规模调整索引类型
4. **批量操作**: 使用批量插入提高效率
5. **连接池**: 生产环境使用连接池

## 🆘 获取帮助

如遇到问题：
1. 查看日志: `./scripts/milvus.sh logs`
2. 检查状态: `./scripts/milvus.sh status`
3. 参考官方文档
4. 提交 Issue