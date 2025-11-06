# MinerU 配置更新说明

## 📋 更新内容

本次更新完善了 MinerU 文档解析的配置系统，支持官方 API 和本地服务两种模式。

### 1. 配置文件更新

#### `.env` 文件
添加了完整的 MinerU 配置项：

```bash
# 新增配置项
MINERU_MODE=auto                    # 运行模式（官方/本地/自动）
MINERU_LANGUAGE=ch                  # 默认语言
MINERU_BACKEND=vlm-http-client      # 本地服务后端类型
MINERU_VLM_SERVER_URL=              # VLM 服务器地址
MINERU_MAX_CONCURRENT=3             # 批量处理并发数
MINERU_OFFICIAL_BASE_URL=...        # 官方 API 地址

# 优化配置项
MINERU_TIMEOUT=600                  # 超时从 300s 提升到 600s
```

#### `config/settings.py`
更新了 `MinerUSettings` 类：

```python
class MinerUSettings(BaseSettings):
    # 新增字段
    mode: str                          # 运行模式
    official_base_url: str            # 官方 API URL
    backend: str                       # 本地服务后端
    vlm_server_url: Optional[str]     # VLM 服务器
    language: str                      # 默认语言
    max_concurrent: int               # 批量并发数

    # 新增方法
    def get_effective_base_url(self) -> str
    def get_effective_mode(self) -> str
```

### 2. 适配器优化

`knowledge_base/mineru_adapter.py` 完全重写：

- ✅ 支持官方云服务 API
- ✅ 支持本地服务 API
- ✅ 自动模式选择
- ✅ 完善的健康检查
- ✅ 异步批量处理
- ✅ 详细的错误处理

### 3. 新增文档

| 文档 | 说明 |
|------|------|
| `docs/MINERU_CONFIGURATION.md` | 配置完整指南 |
| `docs/MINERU_ADAPTER_USAGE.md` | 适配器使用指南 |
| `docs/MINERU_CONFIG_EXAMPLES.md` | 6 种场景配置示例 |

### 4. 新增工具

| 工具 | 功能 |
|------|------|
| `scripts/check_mineru_config.py` | 配置验证脚本 |
| `examples/mineru_test.py` | 功能测试脚本 |

---

## 🚀 如何使用

### 快速开始

1. **配置环境变量**（`.env` 文件）

   ```bash
   # 启用 MinerU
   MINERU_ENABLED=true

   # 选择模式
   MINERU_MODE=auto

   # 官方 API（可选）
   MINERU_API_KEY=your_key

   # 本地服务（可选）
   MINERU_API_BASE_URL=http://localhost:30001
   ```

2. **验证配置**

   ```bash
   python scripts/check_mineru_config.py
   ```

3. **运行测试**

   ```bash
   python examples/mineru_test.py
   ```

4. **开始使用**

   ```python
   from knowledge_base.mineru_adapter import MinerUAdapter

   adapter = MinerUAdapter(mode="auto")
   async with adapter:
       result = await adapter.extract_document("file.pdf")
   ```

---

## 📊 配置对比

### 旧版配置（v1.0）

```bash
MINERU_ENABLED=false
MINERU_API_BASE_URL=http://localhost:8080
MINERU_API_KEY=
MINERU_TIMEOUT=300
```

**问题**：
- ❌ 只支持单一服务地址
- ❌ 无法区分官方/本地模式
- ❌ 配置项不完整
- ❌ 缺少批量处理配置

### 新版配置（v2.0）

```bash
# 基础配置
MINERU_ENABLED=true
MINERU_MODE=auto                    # 🆕 模式选择

# 官方 API 配置
MINERU_API_KEY=                     # 🆕 官方 API 支持
MINERU_OFFICIAL_BASE_URL=...        # 🆕

# 本地服务配置
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=vlm-http-client      # 🆕 后端类型
MINERU_VLM_SERVER_URL=              # 🆕

# 通用配置
MINERU_TIMEOUT=600                  # ✨ 提升到 600s
MINERU_LANGUAGE=ch                  # 🆕 语言设置
MINERU_MAX_CONCURRENT=3             # 🆕 并发控制
```

**改进**：
- ✅ 支持双模式
- ✅ 灵活配置
- ✅ 完整的配置项
- ✅ 性能优化

---

## 🎯 主要特性

### 1. 双模式支持

| 特性 | 官方 API | 本地服务 |
|------|----------|----------|
| 部署 | 无需部署 | 需要部署 |
| 成本 | 按量计费 | 免费 |
| 限制 | 有限制 | 无限制 |
| 格式 | PDF, Word, PPT, 图片 | PDF, 图片 |

### 2. 自动模式

```
mode=auto 工作流程：

检查 API Key
  ├─ 有 Key → 使用官方 API
  └─ 无 Key → 使用本地服务
```

### 3. 健康检查

```python
health = await adapter.health_check()
# 返回: {status, message, details}
```

针对不同模式实现不同的检查逻辑。

### 4. 批量处理

```python
results = await adapter.batch_extract(
    file_paths=["doc1.pdf", "doc2.pdf"],
    max_concurrent=3
)
```

支持并发处理多个文档。

---

## 📈 性能优化

1. **超时时间**: `300s` → `600s`（提升 100%）
2. **批量处理**: 新增并发控制（`max_concurrent`）
3. **异步 IO**: 完全异步实现
4. **连接复用**: 使用 session 管理

---

## 🔧 迁移指南

### 从旧版迁移

如果你使用的是旧版配置，按以下步骤迁移：

1. **更新 `.env` 文件**

   ```bash
   # 旧版
   MINERU_API_BASE_URL=http://localhost:8080

   # 新版（向后兼容）
   MINERU_MODE=local
   MINERU_API_BASE_URL=http://localhost:8080
   ```

2. **更新代码**（可选）

   旧版代码仍可工作，但建议更新：

   ```python
   # 旧版（仍可用）
   adapter = MinerUAdapter()

   # 新版（推荐）
   adapter = MinerUAdapter(mode="auto")
   ```

3. **验证配置**

   ```bash
   python scripts/check_mineru_config.py
   ```

### 配置兼容性

✅ **向后兼容**: 旧版配置仍然有效
✅ **渐进式升级**: 可逐步添加新配置项
✅ **默认值**: 新配置项都有合理的默认值

---

## 🐛 常见问题

### Q1: 旧代码还能用吗？

**A**: 能。新版完全���后兼容，旧代码无需修改即可运行。

### Q2: 必须更新配置吗？

**A**: 不必须。但建议添加新配置项以获得更好的功能。

### Q3: 如何验证配置正确？

**A**: 运行 `python scripts/check_mineru_config.py`

### Q4: 模式选择有什么建议？

**A**:
- 开发环境：`mode=auto`（灵活）
- 生产环境：明确指定 `official` 或 `local`

### Q5: 配置优先级是什么？

**A**:
1. 代码传入的 config 参数（最高）
2. 环境变量（.env）
3. settings.py 默认值（最低）

---

## 📚 详细文档

| 文档 | 内容 |
|------|------|
| [MINERU_CONFIGURATION.md](./MINERU_CONFIGURATION.md) | 配置完整指南 |
| [MINERU_ADAPTER_USAGE.md](./MINERU_ADAPTER_USAGE.md) | API 使用文档 |
| [MINERU_CONFIG_EXAMPLES.md](./MINERU_CONFIG_EXAMPLES.md) | 场景配置示例 |

---

## ✅ 检查清单

使用前请确认：

- [ ] 已更新 `.env` 文件
- [ ] 已运行配置验证脚本
- [ ] 已查看相关文档
- [ ] 已运行功能测试
- [ ] 理解模式选择
- [ ] 了解配置优先级

---

## 🎉 总结

这次更新带来了：

1. ✨ **灵活的模式选择**: 官方/本地/自动
2. ✨ **完善的配置系统**: 详细且可扩展
3. ✨ **丰富的文档**: 6 种场景示例
4. ✨ **实用的工具**: 验证和测试脚本
5. ✨ **向后兼容**: 无需修改旧代码
6. ✨ **性能优化**: 更快更稳定

现在就开始使用新的 MinerU 配置吧！

---

**有问题？**

1. 运行配置验证: `python scripts/check_mineru_config.py`
2. 查看文档: `docs/MINERU_*.md`
3. 运行测试: `python examples/mineru_test.py`
