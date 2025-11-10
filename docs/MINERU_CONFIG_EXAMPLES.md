# MinerU 配置示例

本文档提供不同场景下的 MinerU 配置示例。

## 📋 配置项说明

### 基础配置

| 配置项 | 说明 | 默认值 | 可选值 |
|--------|------|--------|--------|
| `MINERU_ENABLED` | 是否启用 MinerU | `false` | `true`, `false` |
| `MINERU_MODE` | 运行模式 | `auto` | `official`, `local`, `auto` |
| `MINERU_TIMEOUT` | 请求超时时间（秒） | `600` | 整数 |
| `MINERU_LANGUAGE` | 默认语言 | `ch` | `ch`, `en` |

### 官方 API 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MINERU_API_KEY` | 官方 API 密钥 | 空 |
| `MINERU_OFFICIAL_BASE_URL` | 官方 API 地址 | `https://mineru.net/api/v4` |

### 本地服务配置

| 配置项 | 说明 | 默认值 | 可选值 |
|--------|------|--------|--------|
| `MINERU_API_BASE_URL` | 本地服务地址 | `http://localhost:30001` | URL |
| `MINERU_BACKEND` | 本地服务后端 | `vlm-http-client` | `vlm-http-client`, `pipeline` |
| `MINERU_VLM_SERVER_URL` | VLM 服务器地址 | 空 | URL |

### 解析选项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MINERU_EXTRACT_IMAGES` | 提取图片 | `true` |
| `MINERU_EXTRACT_TABLES` | 提取表格 | `true` |
| `MINERU_EXTRACT_FORMULAS` | 提取公式 | `true` |
| `MINERU_OCR_ALL_IMAGES` | 对所有图片进行 OCR | `true` |

### 批量处理

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MINERU_MAX_CONCURRENT` | 最大并发数 | `3` |

---

## 🚀 场景 1: 使用官方云服务 API

适用于：
- 快速开始，无需部署
- 小规模文档处理
- 测试和开发

### 配置 `.env`

```bash
# 基础配置
MINERU_ENABLED=true
MINERU_MODE=official

# 官方 API 配置
MINERU_API_KEY=your_mineru_api_key_here

# 通用配置
MINERU_TIMEOUT=600
MINERU_LANGUAGE=ch

# 文档解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
MINERU_OCR_ALL_IMAGES=true

# 批量处理
MINERU_MAX_CONCURRENT=3
```

### 获取 API Key

1. 访问 [MinerU 官网](https://mineru.net)
2. 注册/登录账号
3. 进入控制台获取 API Key

### 使用示例

```python
from knowledge_base.mineru_adapter import MinerUAdapter

# 自动使用官方 API（因为配置了 API Key）
adapter = MinerUAdapter(mode="auto")

# 或显式指定官方模式
adapter = MinerUAdapter(mode="official")
```

---

## 🖥️ 场景 2: 使用本地服务

适用于：
- 大规模文档处理
- 数据隐私要求
- 生产环境

### 配置 `.env`

```bash
# 基础配置
MINERU_ENABLED=true
MINERU_MODE=local

# 本地服务配置
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=vlm-http-client
MINERU_VLM_SERVER_URL=http://localhost:8080

# 通用配置
MINERU_TIMEOUT=600
MINERU_LANGUAGE=ch

# 文档解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
MINERU_OCR_ALL_IMAGES=true

# 批量处理
MINERU_MAX_CONCURRENT=5
```

### 部署本地服务

#### 使用 Docker（推荐）

```bash
# 拉取镜像
docker pull mineru/magic-pdf:latest

# 启动服务
docker run -d \
  --name mineru-service \
  -p 30001:30001 \
  -e BACKEND=vlm-http-client \
  mineru/magic-pdf:latest

# 检查服务
curl http://localhost:30001/openapi.json
```

#### 手动部署

```bash
# 克隆仓库
git clone https://github.com/opendatalab/MinerU.git
cd MinerU

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m magic_pdf.http_server --port 30001 --backend vlm-http-client
```

### 使用示例

```python
from knowledge_base.mineru_adapter import MinerUAdapter

# 自动使用本地服务（因为没有 API Key）
adapter = MinerUAdapter(mode="auto")

# 或显式指定本地模式
adapter = MinerUAdapter(mode="local")
```

---

## 🔄 场景 3: 自动模式（推荐）

适用于：
- 灵活切换
- 开发和生产环境共用配置
- 最佳实践

### 配置 `.env`

```bash
# 基础配置
MINERU_ENABLED=true
MINERU_MODE=auto

# 官方 API 配置（可选）
# 如果设置了 API Key，自动使用官方 API
MINERU_API_KEY=

# 本地服务配置（备用）
# 如果没有 API Key，自动使用本地服务
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=vlm-http-client

# 通用配置
MINERU_TIMEOUT=600
MINERU_LANGUAGE=ch

# 文档解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
MINERU_OCR_ALL_IMAGES=true

# 批量处理
MINERU_MAX_CONCURRENT=3
```

### 工作原理

```
自动模式流程：

1. 检查 MINERU_API_KEY
   ├─ 有 API Key → 使用官方 API
   └─ 无 API Key → 使用本地服务

2. 动态选择配置
   ├─ 官方 API: MINERU_OFFICIAL_BASE_URL
   └─ 本地服务: MINERU_API_BASE_URL
```

### 使用示例

```python
from knowledge_base.mineru_adapter import MinerUAdapter

# 自动模式（推荐）
adapter = MinerUAdapter(mode="auto")

# 查看实际使用的模式
info = adapter.get_info()
print(f"实际模式: {info['mode']}")
print(f"Base URL: {info['base_url']}")
```

---

## 🔧 场景 4: 开发环境配置

适用于：
- 本地开发
- 调试和���试
- 快速迭代

### 配置 `.env.development`

```bash
# 启用详细日志
DEBUG=true
VERBOSE=true
VERBOSE_DEBUG=true

# MinerU 开发配置
MINERU_ENABLED=true
MINERU_MODE=local
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=pipeline  # 使用更简单的 pipeline 模式
MINERU_TIMEOUT=300  # 短超时便于快速失败

# 减少批量并发以便调试
MINERU_MAX_CONCURRENT=1

# 只提取必要内容以加快速度
MINERU_EXTRACT_IMAGES=false
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=false
MINERU_OCR_ALL_IMAGES=false
```

### 使用开发配置

```bash
# 加载开发配置
export ENV_FILE=.env.development

# 或在代码中指定
python -m uvicorn app.main:app --env-file .env.development
```

---

## 🏭 场景 5: 生产环境配置

适用于：
- 正式环境
- 高可用性要求
- 大规模处理

### 配置 `.env.production`

```bash
# 禁用调试
DEBUG=false
VERBOSE=false

# MinerU 生产配置
MINERU_ENABLED=true
MINERU_MODE=official  # 或 local，根据部署决定

# 官方 API（如果使用）
MINERU_API_KEY=${MINERU_API_KEY}  # 从环境变量或密钥管理服务读取

# 本地服务（如果使用）
MINERU_API_BASE_URL=http://mineru-service:30001
MINERU_BACKEND=vlm-http-client
MINERU_VLM_SERVER_URL=http://vlm-service:8080

# 生产配置
MINERU_TIMEOUT=900  # 更长的超时
MINERU_LANGUAGE=ch
MINERU_MAX_CONCURRENT=10  # 高并发

# 完整的解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
MINERU_OCR_ALL_IMAGES=true
```

### 生产环境最佳实践

1. **使用密钥管理**
   ```bash
   # 从 K8s Secret 读取
   MINERU_API_KEY=$(kubectl get secret mineru-secret -o jsonpath='{.data.api-key}' | base64 -d)
   ```

2. **健康检查**
   ```python
   async def startup_check():
       adapter = MinerUAdapter()
       health = await adapter.health_check()
       if health["status"] != "healthy":
           raise RuntimeError(f"MinerU 不可用: {health['message']}")
   ```

3. **监控和日志**
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)

   # 记录处理统计
   stats = adapter.get_extraction_stats(result)
   logger.info(f"处理完成: {stats}")
   ```

---

## 🧪 场景 6: 混合配置（高级）

同时使用官方 API 和本地服务，根据文件大小自动选择。

### 配置

```bash
# 两种模式都配置
MINERU_MODE=auto
MINERU_API_KEY=your_api_key
MINERU_API_BASE_URL=http://localhost:30001
```

### 智能路由示例

```python
async def process_document_smart(file_path: str):
    """根据文件大小选择处理方式"""
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    if file_size_mb < 10:
        # 小文件用官方 API
        adapter = MinerUAdapter(mode="official")
    else:
        # 大文件用本地服务
        adapter = MinerUAdapter(mode="local")

    async with adapter:
        return await adapter.extract_document(file_path)
```

---

## 📊 配置对比

| 特性 | 官方 API | 本地服务 |
|------|----------|----------|
| 部署难度 | 无需部署 ⭐⭐⭐⭐⭐ | 需要部署 ⭐⭐ |
| 使用成本 | 按量计费 💰💰 | 免费（硬件成本）💰 |
| 处理速度 | 中等 ⚡⚡⚡ | 快（本地）⚡⚡⚡⚡ |
| 数据隐私 | 云端处理 🔒 | 完全私有 🔒🔒🔒🔒 |
| 并发限制 | 有限制 📊 | 仅受硬件限制 📊📊📊📊 |
| 支持格式 | 更多 📄📄📄📄 | PDF、图片 📄📄 |

---

## 🔍 故障排查

### 检查配置是否生效

```python
from config.settings import settings

print(f"MinerU 已启用: {settings.mineru.enabled}")
print(f"运行模式: {settings.mineru.mode}")
print(f"有效模式: {settings.mineru.get_effective_mode()}")
print(f"Base URL: {settings.mineru.get_effective_base_url()}")
print(f"超时: {settings.mineru.timeout}s")
```

### 测试连接

```python
import asyncio
from knowledge_base.mineru_adapter import MinerUAdapter

async def test_connection():
    adapter = MinerUAdapter()
    async with adapter:
        health = await adapter.health_check()
        print(health)

asyncio.run(test_connection())
```

### 常见问题

1. **API Key 无效**
   ```bash
   # 检查 API Key 是否正确设置
   echo $MINERU_API_KEY

   # 确认没有多余的空格或引号
   MINERU_API_KEY=your_key_without_quotes
   ```

2. **本地服务无法连接**
   ```bash
   # 检查服务是否运行
   curl http://localhost:30001/openapi.json

   # 检查端口是否正确
   netstat -tuln | grep 30001
   ```

3. **超时错误**
   ```bash
   # 增加超时时间
   MINERU_TIMEOUT=1200  # 20 分钟
   ```

---

## 📚 相关文档

- [MinerU 适配器使用指南](./MINERU_ADAPTER_USAGE.md)
- [MinerU 官方文档](https://github.com/opendatalab/MinerU)
- [配置文件说明](../config/settings.py)

---

选择合适的配置场景，让 MinerU 发挥最大效用！
