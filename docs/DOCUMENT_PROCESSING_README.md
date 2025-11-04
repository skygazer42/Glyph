# 增强文档处理系统使用指南

## 概述

Gove项目已升级其文档处理系统，现在支持使用多种先进的文档解析引擎：

- **MinerU2.5** - 通过vLLM接口提供高质量的PDF解析
- **Docling** - IBM开源的文档理解框架
- **LlamaIndex** - 支持多种文档格式的读取器
- **传统库** - PyPDF2、python-docx等作为后备方案

## 特性

### 多引擎支持
- **PDF处理**: MinerU2.5 (优先) → Docling → LlamaIndex → PyPDF2
- **DOCX处理**: Docling (优先) → LlamaIndex → python-docx
- **TXT/MD处理**: 直接读取 → LlamaIndex (备选)

### 高级功能
- ✅ OCR识别（支持中英文）
- ✅ 表格提取和识别
- ✅ 图片和图表提取
- ✅ 公式识别（数学公式）
- ✅ 布局保持
- ✅ 流式处理支持
- ✅ 批量处理
- ✅ 异步并发处理

## 配置

### 1. 环境变量配置

编辑 `.env` 文件，配置相关参数：

```bash
# MinerU配置（vLLM接口）
MINERU_API_KEY=mineru
MINERU_BASE_URL=http://localhost:8000/v1
MINERU_MODEL=Qwen/Qwen2.5-7B-Instruct

# 文档处理配置
ENABLE_OCR=true
ENABLE_TABLE_EXTRACTION=true
ENABLE_IMAGE_EXTRACTION=true
ENABLE_FORMULA_EXTRACTION=true

# MinerU特定配置
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_OCR_ALL_IMAGES=true
MINERU_OCR_DPI=300
MINERU_OUTPUT_FORMAT=markdown
```

### 2. Python配置

系统会自动从 `config/settings.py` 读取配置：

```python
from config.settings import settings

# 使用增强处理器
processor = EnhancedDocumentProcessor({
    "mineru_enabled": True,
    "docling_enabled": True,
    "llamaindex_enabled": True,
    "ocr_enabled": settings.document.enable_ocr,
    "table_extraction": settings.document.enable_table_extraction
})
```

## 安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt

# 特别安装文档处理依赖
pip install docling>=1.10.0
pip install llama-index>=0.10.0
pip install aiohttp>=3.11.0
pip install aiofiles>=24.1.0

# OCR支持（可选）
pip install easyocr
pip install paddleocr
pip install pytesseract
```

## 使用方法

### 1. 基本使用

```python
from knowledge_base.enhanced_document_processor import EnhancedDocumentProcessor

# 初始化处理器
processor = EnhancedDocumentProcessor()

# 提取文本
text = await processor.extract_text("document.pdf")
print(text)

# 提取文本和元数据
metadata = await processor.extract_with_metadata("document.pdf")
print(f"文本长度: {metadata['text_length']}")
print(f"提取方法: {metadata['extraction_method']}")
```

### 2. 使用MinerU适配器

```python
from knowledge_base.mineru_adapter import MinerUAdapter

async with MinerUAdapter() as mineru:
    # 提取单个文档
    result = await mineru.extract_document("document.pdf")
    markdown_text = result["content"]["markdown"]

    # 获取元数据
    metadata = await mineru.get_document_metadata("document.pdf")

    # 批量处理
    results = await mineru.batch_extract(
        ["doc1.pdf", "doc2.pdf"],
        max_concurrent=3
    )

    # 流式处理
    async for chunk in mineru.extract_document_stream("large.pdf"):
        print(chunk)
```

### 3. 在数据加载器中使用

```python
from knowledge_base.data_loader import DataLoader

# 使用增强处理器（默认）
loader = DataLoader(use_enhanced_processor=True)

# 加载文档
documents = await loader.load_all_documents()

# 初始化向量存储
await loader.initialize_vector_store(documents)
```

## API参考

### EnhancedDocumentProcessor

#### 主要方法

- `extract_text(file_path)` - 提取文本
- `extract_with_metadata(file_path)` - 提取文本和元数据
- `test_engines()` - 测试各个引擎是否可用
- `get_supported_formats()` - 获取支持的文件格式

### MinerUAdapter

#### 主要方法

- `extract_document(file_path, options)` - 提取文档
- `extract_document_stream(file_path, options)` - 流式提取
- `get_document_metadata(file_path)` - 获取元数据
- `batch_extract(file_paths, options, max_concurrent)` - 批量提取
- `health_check()` - 健康检查

## 性能优化

### 1. 并发处理

```python
# 设置并发数量
options = {
    "max_concurrent": 5  # 同时处理5个文件
}

results = await mineru.batch_extract(files, options)
```

### 2. 流式处理

对于大文件，使用流式处理：

```python
async for chunk in mineru.extract_document_stream("large.pdf"):
    # 实时处理提取的内容
    process_chunk(chunk)
```

### 3. 选择性提取

```python
# 只提取需要的内容
options = {
    "extract_images": False,  # 不提取图片
    "extract_tables": True,   # 提取表格
    "ocr_all_images": False   # 不对所有图片进行OCR
}
```

## 故障排除

### 1. MinerU连接失败

```bash
# 检查MinerU服务是否运行
curl http://localhost:8000/v1/health

# 查看日志
docker logs mineru-container
```

### 2. OCR识别问题

```python
# 检查OCR引擎
processor.test_engines()
# {'mineru': True, 'docling': True, 'llamaindex': True}
```

### 3. 内存不足

```python
# 降低并发数
options = {"max_concurrent": 1}

# 或分页处理PDF
pages = [1, 2, 3]  # 只处理前3页
result = await mineru.extract_pages("large.pdf", pages)
```

## 最佳实践

1. **优先使用MinerU** - 提供最佳的PDF解析质量
2. **启用OCR** - 对扫描版PDF很重要
3. **批量处理** - 提高处理效率
4. **异步操作** - 避免阻塞主线程
5. **错误处理** - 始终包含try-catch块
6. **内存管理** - 处理大文件时注意内存使用

## 示例脚本

运行测试脚本：

```bash
python test_document_processor.py
```

这将测试所有引擎的可用性，并尝试提取测试文件的内容。

## 更新日志

- **v2.0** - 集成MinerU2.5、Docling和LlamaIndex
- **v1.0** - 基础文档处理功能（PyPDF2、python-docx）

## 许可证

本项目遵循MIT许可证。