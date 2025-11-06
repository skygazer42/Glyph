# MinerU 配置完整指南

本文档总结了项目中 MinerU 文档解析的完整配置。

## 📁 相关文件

### 配置文件
- `.env` - 环境变量配置（主配置文件）
- `config/settings.py` - Python 配置类（`MinerUSettings`）

### 文档
- `docs/MINERU_ADAPTER_USAGE.md` - MinerU 适配器使用指南
- `docs/MINERU_CONFIG_EXAMPLES.md` - 配置示例（各种场景）
- 本文档 - 配置总结

### 代码文件
- `knowledge_base/mineru_adapter.py` - MinerU 适配器核心实现
- `examples/mineru_test.py` - 功能测试脚本
- `scripts/check_mineru_config.py` - 配置验证脚本

---

## ⚡ 快速开始

### 1. 选择运行模式

MinerU 支持三种运行模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `official` | 使用官方云服务 API | 快速开始、小规模处理 |
| `local` | 使用本地部署服务 | 大规模处理、数据隐私 |
| `auto` | 自动选择（推荐） | 灵活切换、通用场景 |

### 2. 配置 `.env` 文件

#### 官方 API 模式

```bash
MINERU_ENABLED=true
MINERU_MODE=official
MINERU_API_KEY=your_api_key_here
```

#### 本地服务模式

```bash
MINERU_ENABLED=true
MINERU_MODE=local
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=vlm-http-client
```

#### 自动模式（推荐）

```bash
MINERU_ENABLED=true
MINERU_MODE=auto
# 设置 API Key 则用官方，不设置则用本地
MINERU_API_KEY=
MINERU_API_BASE_URL=http://localhost:30001
```

### 3. 验证配置

```bash
# 验证配置是否正确
python scripts/check_mineru_config.py

# 运行功能测试
python examples/mineru_test.py
```

### 4. 开始使用

```python
from knowledge_base.mineru_adapter import MinerUAdapter

async def main():
    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        result = await adapter.extract_document("document.pdf")
        if result["success"]:
            print(result["content"])

import asyncio
asyncio.run(main())
```

---

## 📋 完整配置项

### 基础配置

```bash
# 是否启用 MinerU
MINERU_ENABLED=true

# 运行模式: official, local, auto
MINERU_MODE=auto

# 请求超时（秒）
MINERU_TIMEOUT=600

# 默认语言: ch, en
MINERU_LANGUAGE=ch
```

### 官方 API 配置

```bash
# 官方 API 密钥（从 https://mineru.net 获取）
MINERU_API_KEY=

# 官方 API 地址（通常不需要修改）
MINERU_OFFICIAL_BASE_URL=https://mineru.net/api/v4
```

### 本地服务配置

```bash
# 本地服务地址
MINERU_API_BASE_URL=http://localhost:30001

# 后端类型: vlm-http-client（推荐）, pipeline
MINERU_BACKEND=vlm-http-client

# VLM 服务器地址（backend=vlm-http-client 时需要）
MINERU_VLM_SERVER_URL=
```

### 解析选项

```bash
# 提取图片
MINERU_EXTRACT_IMAGES=true

# 提取表格
MINERU_EXTRACT_TABLES=true

# 提取公式
MINERU_EXTRACT_FORMULAS=true

# 对所有图片进行 OCR
MINERU_OCR_ALL_IMAGES=true
```

### 性能配置

```bash
# 批量处理最大并发数
MINERU_MAX_CONCURRENT=3
```

---

## 🎯 使用场景

### 场景 1: 快速测试

```bash
# .env
MINERU_ENABLED=true
MINERU_MODE=official
MINERU_API_KEY=your_test_key
```

**优点**: 无需部署，立即使用
**限制**: API 调用限制

### 场景 2: 生产环境

```bash
# .env
MINERU_ENABLED=true
MINERU_MODE=local
MINERU_API_BASE_URL=http://mineru-service:30001
MINERU_MAX_CONCURRENT=10
```

**优点**: 无限制，高性能
**要求**: 需要部署服务

### 场景 3: 开发环境

```bash
# .env
MINERU_ENABLED=true
MINERU_MODE=auto
MINERU_API_BASE_URL=http://localhost:30001
MINERU_MAX_CONCURRENT=1
```

**优点**: 灵活切换，便于调试

---

## 🔧 配置在代码中的使用

### 通过 Settings 访问配置

```python
from config.settings import settings

# 检查是否启用
if settings.mineru.enabled:
    # 获取有效模式
    mode = settings.mineru.get_effective_mode()

    # 获取有效 URL
    url = settings.mineru.get_effective_base_url()

    print(f"MinerU: {mode} @ {url}")
```

### 动态配置适配器

```python
from knowledge_base.mineru_adapter import MinerUAdapter

# 使用全���配置
adapter = MinerUAdapter()

# 或自定义配置
adapter = MinerUAdapter(
    config={
        "api_key": "custom_key",
        "timeout": 1200,
        "max_concurrent": 5
    },
    mode="official"
)
```

### 配置优先级

```
1. 代码中传入的 config 参数（最高优先级）
2. 环境变量 (.env 文件)
3. settings.py 中的默认值（最低优先级）
```

---

## 📊 配置检查清单

使用配置验证脚本进行检查：

```bash
python scripts/check_mineru_config.py
```

该脚本会检查：

- ✓ 基础配置（启用状态、模式、超时等）
- ✓ 运行模式（自动检测、有效模式）
- ✓ 官方 API（Key 有效性）
- ✓ 本地服务（URL、后端类型）
- ✓ 解析选项（功能启用状态）
- ✓ 性能配置（并发数、超时）

并提供配置���议。

---

## 🐛 常见问题

### 1. 如何知道使用的是哪种模式？

```python
adapter = MinerUAdapter(mode="auto")
info = adapter.get_info()
print(f"实际模式: {info['mode']}")
```

### 2. 如何切换模式？

修改 `.env` 文件中的 `MINERU_MODE`，或在代码中指定：

```python
# 使用官方 API
adapter = MinerUAdapter(mode="official")

# 使用本地服务
adapter = MinerUAdapter(mode="local")
```

### 3. API Key 在哪里获取？

1. 访问 https://mineru.net
2. 注册账号并登录
3. 进入控制台获取 API Key

### 4. 如何部署本地服务？

参考 `docs/MINERU_CONFIG_EXAMPLES.md` 中的"场景 2: 使用本地服务"。

### 5. 配置不生效怎么办？

```bash
# 1. 检查配置
python scripts/check_mineru_config.py

# 2. 验证环境变量
python -c "from config.settings import settings; print(settings.mineru)"

# 3. 运行测试
python examples/mineru_test.py
```

---

## 📚 详细文档

| 文档 | 内容 |
|------|------|
| [MINERU_ADAPTER_USAGE.md](./MINERU_ADAPTER_USAGE.md) | 适配器使用指南、API 文档、示例代码 |
| [MINERU_CONFIG_EXAMPLES.md](./MINERU_CONFIG_EXAMPLES.md) | 6 种场景的详细配置示例 |
| [check_mineru_config.py](../scripts/check_mineru_config.py) | 配置���证脚本 |
| [mineru_test.py](../examples/mineru_test.py) | 功能测试脚本 |

---

## 🔄 配置更新记录

### v2.0 (最新) - 双模式支持

- ✨ 新增官方 API 支持
- ✨ 新增本地服务支持
- ✨ 新增自动模式
- ✨ 新增配置验证工具
- ✨ 新增详细文档

### 主要改进

1. **灵活的模式选择**: `official`, `local`, `auto`
2. **统一的 API 接口**: 无论哪种模式，使用方式一致
3. **完善的错误处理**: 详细的错误信息和状态码
4. **健康检查**: 启动前自动检查服务可用性
5. **批量处理**: 支持并发处理多个文档
6. **配置验证**: 自动检查配置并提供建议

---

## 💡 最佳实践

1. **开发环境使用 auto 模式**
   ```bash
   MINERU_MODE=auto
   ```

2. **生产环境明确指定模式**
   ```bash
   MINERU_MODE=official  # 或 local
   ```

3. **使用配置验证**
   ```bash
   python scripts/check_mineru_config.py
   ```

4. **监控处理统计**
   ```python
   stats = adapter.get_extraction_stats(result)
   logger.info(f"处理统计: {stats}")
   ```

5. **异常处理**
   ```python
   try:
       result = await adapter.extract_document(file_path)
   except Exception as e:
       logger.error(f"提取失败: {e}")
   ```

---

## 🎉 总结

MinerU 配置已完全更新，支持：

- ✅ 官方云服务 API
- ✅ 本地服务部署
- ✅ 自动模式选择
- ✅ 完善的文档和工具
- ✅ 生产级错误处理

选择适合你的场景，开始使用吧！

有问题请参考详细文档或运行配置验证脚本。
