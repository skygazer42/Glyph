# MinerU 适配器使用指南

## 📋 概述

优化后的 MinerU 适配器支持两种运行模式：
1. **官方云服务 API** (https://mineru.net) - 需要 API Key
2. **本地服务 API** (http://localhost:30001) - 需要本地部署

适配器会自动检测并选择合适的模式。

## 🚀 快速开始

### 1. 配置环境变量

```bash
# .env 文件

# 官方 API 配置（如果使用官方服务）
MINERU_API_KEY=your_api_key_here

# 本地服务配置（如果使用本地服务）
MINERU_API_BASE_URL=http://localhost:30001
```

### 2. 基本使用

```python
import asyncio
from knowledge_base.mineru_adapter import MinerUAdapter

async def extract_document():
    # 方式 1: 自动模式（推荐）
    adapter = MinerUAdapter(mode="auto")

    # 方式 2: 指定使用官方 API
    # adapter = MinerUAdapter(mode="official")

    # 方式 3: 指定使用本地服务
    # adapter = MinerUAdapter(mode="local")

    async with adapter:
        # 健康检查
        health = await adapter.health_check()
        print(f"健康状态: {health}")

        # 提取文档
        result = await adapter.extract_document(
            file_path="/path/to/document.pdf",
            options={
                "is_ocr": True,
                "enable_formula": True,
                "enable_table": True,
                "language": "ch"
            }
        )

        if result["success"]:
            print(f"提取成功!")
            print(f"内容长度: {len(result['content'])} 字符")
            print(f"处理时间: {result['processing_time']:.2f}s")

            # 获取 Markdown 内容
            markdown_content = result["content"]

            # 保存到文件
            with open("output.md", "w", encoding="utf-8") as f:
                f.write(markdown_content)
        else:
            print(f"提取失败: {result['error']}")

# 运行
asyncio.run(extract_document())
```

## 📖 功能详解

### 1. 健康检查

```python
async with MinerUAdapter() as adapter:
    health = await adapter.health_check()

    # 返回格式:
    # {
    #     "status": "healthy" | "unhealthy" | "unavailable" | "error",
    #     "message": "状态描述",
    #     "details": {...}
    # }

    if health["status"] == "healthy":
        print("服务可用")
    else:
        print(f"服务不可��: {health['message']}")
```

### 2. 官方 API 模式

```python
adapter = MinerUAdapter(
    mode="official",
    config={
        "api_key": "your_api_key",  # 或从环境变量读取
        "timeout": 600
    }
)

async with adapter:
    result = await adapter.extract_document(
        file_path="document.pdf",
        options={
            # 官方 API 参数
            "is_ocr": True,              # 启用 OCR
            "enable_formula": True,       # 公式识别
            "enable_table": True,         # 表格识别
            "language": "ch",             # 语言: ch/en
            "page_ranges": None           # 页码范围，如 "1-5"
        }
    )
```

**支持的文件类型:**
- PDF: `.pdf`
- Word: `.doc`, `.docx`
- PowerPoint: `.ppt`, `.pptx`
- 图片: `.png`, `.jpg`, `.jpeg`

### 3. 本地服务模式

```python
adapter = MinerUAdapter(
    mode="local",
    config={
        "base_url": "http://localhost:30001",
        "backend": "vlm-http-client",  # 或 "pipeline"
        "language": "ch"
    }
)

async with adapter:
    result = await adapter.extract_document(
        file_path="document.pdf",
        options={
            # 本地服务参数
            "lang_list": ["ch"],          # 语言列表
            "backend": "vlm-http-client", # 后端类型
            "parse_method": "auto",       # 解析方法
            "server_url": None            # VLM 服务器地址（如需要）
        }
    )
```

**支持的文件类型:**
- PDF: `.pdf`
- 图片: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`

**可用后端:**
- `vlm-http-client`: VLM 远程客户端（推荐）
- `pipeline`: 传统 Pipeline 模式

### 4. 批量处理

```python
async with MinerUAdapter() as adapter:
    file_paths = [
        "/path/to/doc1.pdf",
        "/path/to/doc2.pdf",
        "/path/to/doc3.pdf"
    ]

    # 批量提取（并发处理）
    results = await adapter.batch_extract(
        file_paths=file_paths,
        options={"is_ocr": True},
        max_concurrent=3  # 最大并发数
    )

    # 处理结果
    for result in results:
        if result["success"]:
            print(f"✓ {result['metadata']['file_name']}: {len(result['content'])} 字符")
        else:
            print(f"✗ {result['file_path']}: {result['error']}")
```

### 5. 统计信息

```python
result = await adapter.extract_document("document.pdf")
stats = adapter.get_extraction_stats(result)

print(f"""
提取统计:
- 成功: {stats['success']}
- 文本长度: {stats['text_length']} 字符
- 处理时间: {stats['processing_time']:.2f}s
- 文件名: {stats['file_name']}
- 模式: {stats['mode']}
""")
```

### 6. 获取适配器信息

```python
info = adapter.get_info()

print(f"""
适配器信息:
- 模式: {info['mode']}
- 基础 URL: {info['base_url']}
- 已启用: {info['enabled']}
- 有 API Key: {info['has_api_key']}
- 超时: {info['timeout']}s
- 支持的扩展名: {', '.join(info['supported_extensions'])}
""")
```

## 🔧 高级用法

### 1. 自定义配置

```python
custom_config = {
    "enabled": True,
    "api_key": "your_api_key",
    "base_url": "http://localhost:30001",
    "timeout": 600,
    "ocr_all_images": True,
    "extract_images": True,
    "extract_tables": True,
    "extract_formulas": True,
    "language": "ch",
    "backend": "vlm-http-client"
}

adapter = MinerUAdapter(config=custom_config, mode="auto")
```

### 2. 错误处理

```python
async with MinerUAdapter() as adapter:
    try:
        result = await adapter.extract_document("document.pdf")

        if not result["success"]:
            # 处理提取失败
            error = result["error"]
            print(f"提取失败: {error}")

            # 可以尝试重试或使用其他方法

    except FileNotFoundError as e:
        print(f"文件不存在: {e}")
    except RuntimeError as e:
        print(f"服务错误: {e}")
    except TimeoutError as e:
        print(f"处理超时: {e}")
    except Exception as e:
        print(f"未知错误: {e}")
```

### 3. 与文档处理器集成

```python
from knowledge_base.mineru_adapter import MinerUAdapter
from knowledge_base.doc_processor import DocumentProcessor

async def process_documents():
    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        # 提取文档
        result = await adapter.extract_document("policy.pdf")

        if result["success"]:
            # 使用文档处理器进一步处理
            processor = DocumentProcessor()
            markdown_content = result["content"]

            # 解析 Markdown
            parsed_doc = processor.parse_markdown(markdown_content)

            # 进行索引构建等后续处理
            # ...
```

## 📊 性能对比

| 模式 | 优势 | 劣势 | 适用场景 |
|-----|------|------|---------|
| **官方 API** | 无需部署，开箱即用；支持更多格式 | 需要 API Key；有使用限制 | 小规模处理，快速开始 |
| **本地服务** | 无限制；数据隐私；可自定义 | 需要部署服务；占用资源 | 大规模处理，生产环境 |

## ⚙️ 本地服务部署

如果使用本地模式，需要先部署 MinerU 服务：

```bash
# 使用 Docker 部署（推荐）
docker run -d \
  --name mineru-service \
  -p 30001:30001 \
  -e BACKEND=vlm-http-client \
  mineru/magic-pdf:latest

# 检查服务状态
curl http://localhost:30001/openapi.json
```

详细部署文档请参考 MinerU 官方文档。

## 🐛 故障排除

### 1. 连接超时

```python
# 增加超时时间
adapter = MinerUAdapter(config={"timeout": 1200})  # 20 分钟
```

### 2. API Key 无效

```bash
# 检查环境变量
echo $MINERU_API_KEY

# 或在代码中明确指定
adapter = MinerUAdapter(
    mode="official",
    config={"api_key": "your_valid_key"}
)
```

### 3. 本地服务无法连接

```bash
# 检查服务是否运行
curl http://localhost:30001/openapi.json

# 检查端口是否被占用
netstat -tuln | grep 30001

# 重启服务
docker restart mineru-service
```

## 📚 完整示例

```python
import asyncio
from pathlib import Path
from knowledge_base.mineru_adapter import MinerUAdapter

async def batch_process_documents():
    """批量处理政策文档"""
    # 初始化适配器
    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        # 1. 健康检查
        health = await adapter.health_check()
        if health["status"] != "healthy":
            print(f"服务不可用: {health['message']}")
            return

        print(f"✓ 服务健康: {health['message']}")

        # 2. 获取所有 PDF 文件
        data_dir = Path("/data/temp33/gov/data/process")
        pdf_files = list(data_dir.glob("**/*.pdf"))

        print(f"找到 {len(pdf_files)} 个 PDF 文件")

        # 3. 批量处理
        results = await adapter.batch_extract(
            file_paths=[str(f) for f in pdf_files[:10]],  # 前 10 个
            options={
                "is_ocr": True,
                "enable_table": True,
                "enable_formula": True
            },
            max_concurrent=3
        )

        # 4. 统计结果
        success_count = sum(1 for r in results if r["success"])
        total_chars = sum(len(r.get("content", "")) for r in results if r["success"])

        print(f"\n处理完成:")
        print(f"- 成功: {success_count}/{len(results)}")
        print(f"- 总字符数: {total_chars:,}")

        # 5. 保存结果
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        for result in results:
            if result["success"]:
                filename = result["metadata"]["file_name"]
                output_file = output_dir / f"{Path(filename).stem}.md"

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result["content"])

                print(f"✓ 已保存: {output_file}")

# 运行
if __name__ == "__main__":
    asyncio.run(batch_process_documents())
```

## 🎯 最佳实践

1. **使用 auto 模式**: 让适配器自动选择最佳方式
2. **异步处理**: 充分利用异步 IO 提升性能
3. **批量处理**: 对于多个文件，使用 `batch_extract` 并发处理
4. **错误处理**: 总是检查 `result["success"]` 并处理错误
5. **资源管理**: 使用 `async with` 确保正确关闭连接
6. **健康检查**: 在处理前先检查服务健康状态

---

优化后的 MinerU 适配器整合了官方 API 和本地服务的优点，提供统一的接口和更好的错误处理！
