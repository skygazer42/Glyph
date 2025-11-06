# 文档解析架构说明

## 📋 正确的分工理解

### MinerU 2.5 - 文档解析器（主要）
**功能**: 完整的 PDF 文档解析
- 输入: PDF 文档
- 输出:
  - ✅ Markdown 格式的文本
  - ✅ 提取的图片（保留原图）
  - ✅ 表格（转换为 Markdown 表格）
  - ✅ 公式（转换为 LaTeX）
  - ✅ 文档结构（标题、段落、列表）
  - ✅ 布局信息

**适用场景**:
- PDF 文档解析
- 学术论文处理
- 技术文档转换
- 政策文件解析

### RapidOCR/PaddleOCR - OCR 引擎（辅助）
**功能**: 图片中的文字识别
- 输入: 单张图片
- 输出: 识别出的文字

**适用场景**:
- MinerU 提取的图片中的文字识别
- 用户单独上传的图片 OCR
- 扫描件文字提取
- 图表中的文字识别

## 🔄 正确的工作流程

```
用户上传 PDF 文档
        ↓
    MinerU 2.5 解析
        ↓
    ┌───────────────────────┐
    │  输出                  │
    ├───────────────────────┤
    │ • Markdown 文本       │
    │ • 提取的图片 (多张)   │
    │ • 表格 (Markdown)     │
    │ • 公式 (LaTeX)        │
    └───────────────────────┘
        ↓
    (可选) 对提取的图片进行 OCR
        ↓
    RapidOCR 识别图片文字
        ↓
    ┌───────────────────────┐
    │  整合                  │
    ├───────────────────────┤
    │ • Markdown 文本       │
    │ • 图片 + OCR 文字     │
    │ • 表格                │
    │ • 公式                │
    └───────────────────────┘
        ↓
    分级索引构建 (3级)
        ↓
    向量嵌入 (DashScope)
        ↓
    存储到 Milvus + Neo4j
        ↓
    用户查询
        ↓
    两阶段召回 (向量 + Reranker)
        ↓
    LLM 生成回答 (qwen-turbo)
```

## ⚙️ 配置说明

### .env 配置

```bash
# ============================================
# 主文档解析器: MinerU 2.5
# ============================================
DOCUMENT_PROCESSOR=mineru
MINERU_ENABLED=true

# MinerU 运行模式
MINERU_MODE=auto  # official, local, auto

# 官方 API（如果有 API Key）
MINERU_API_KEY=your_key_here
MINERU_OFFICIAL_BASE_URL=https://mineru.net/api/v4

# 本地服务（如果本地部署）
MINERU_API_BASE_URL=http://localhost:30001
MINERU_BACKEND=vlm-http-client

# 文档解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
MINERU_OCR_ALL_IMAGES=true

# ============================================
# OCR 引擎: RapidOCR（辅助）
# ============================================
OCR_ENGINE=rapid_ocr
RAPIDOCR_ENABLED=true
RAPIDOCR_DET_BOX_THRESH=0.3
RAPIDOCR_MODEL_DIR=./models
```

## 🎯 使用示例

### 场景 1: 解析完整 PDF 文档

```python
from knowledge_base.mineru_adapter import MinerUAdapter

# 初始化 MinerU
mineru = MinerUAdapter()

# 解析 PDF
result = mineru.parse_pdf(
    pdf_path="policy_document.pdf",
    output_dir="./output/md"
)

print(f"Markdown: {result['markdown_path']}")
print(f"图片数量: {len(result['images'])}")
print(f"表格数量: {result['tables_count']}")
```

### 场景 2: 对提取的图片进行 OCR

```python
from knowledge_base.rapid_ocr_processor import create_processor

# 创建 OCR 处理器
ocr = create_processor()

# 对 MinerU 提取的图片进行 OCR
for img_path in result['images']:
    text = ocr.process_image(img_path)
    print(f"{img_path}: {text}")
```

### 场景 3: 完整流程（推荐）

```python
# 1. MinerU 解析文档
result = mineru.parse_pdf("document.pdf")

# 2. 读取 Markdown
with open(result['markdown_path'], 'r') as f:
    markdown_text = f.read()

# 3. 对图片进行 OCR（可选）
ocr = create_processor()
image_texts = {}
for img_path in result['images']:
    image_texts[img_path] = ocr.process_image(img_path)

# 4. 整合所有内容
full_content = markdown_text + "\n\n# 图片识别文字\n"
for img_path, text in image_texts.items():
    full_content += f"\n## {img_path}\n{text}\n"

# 5. 构建索引
from knowledge_base.hierarchical_index import HierarchicalIndexBuilder

builder = HierarchicalIndexBuilder(
    use_llm=True,
    enable_images=True
)

index = builder.build_from_markdown(
    markdown_content=full_content,
    images=result['images']
)

# 6. 查询
retriever = index.as_retriever(
    retrieval_mode="hybrid",
    use_rerank=True
)

results = retriever.retrieve(
    query="补贴标准是什么？",
    top_k=5
)
```

## 📊 功能对比

| 功能 | MinerU 2.5 | RapidOCR |
|------|-----------|----------|
| **定位** | 文档解析器 | OCR 引擎 |
| **输入** | PDF 文档 | 单张图片 |
| **输出** | Markdown + 图片 + 表格 + 公式 | 纯文字 |
| **结构识别** | ✅ 支持 | ❌ 不支持 |
| **表格提取** | ✅ 支持 | ❌ 不支持 |
| **公式识别** | ✅ 支持 | ❌ 不支持 |
| **图片提取** | ✅ 支持 | ❌ 不支持 |
| **文字识别** | ⚠️ 依赖 OCR | ✅ 专业 |
| **部署难度** | 中等 | 简单 |
| **API 费用** | 需要/可选 | 免费 |

## 🔧 最佳实践

### 推荐配置

1. **主流程**: MinerU 2.5
   - 用于解析所有 PDF 文档
   - 获取完整的文档结构

2. **OCR 引擎**: RapidOCR
   - 作为 MinerU 的 OCR 后端
   - 或独立处理用户上传的图片

3. **向量检索**: Milvus
   - 存储文档和图片的向量

4. **召回优化**: Reranker
   - 两阶段召回提升精度

5. **知识图谱**: Neo4j
   - 存储文档关系

### 常见问题

**Q: 能不能只用 RapidOCR，不用 MinerU？**
A: 不推荐。RapidOCR 只能识别文字，无法提取表格、公式、图片，也不能保留文档结构。

**Q: MinerU 必须使用官方 API 吗？**
A: 不是。可以本地部署 MinerU 服务，或使用 auto 模式自动选择。

**Q: RapidOCR 和 PaddleOCR 有什么区别？**
A: RapidOCR 是基于 PaddleOCR 的轻量化版本，使用 ONNX 模型，部署更简单，速度更快。

**Q: 图片必须进行 OCR 吗？**
A: 不是必须的。如果图片本身已经被索引（通过文件名、caption 等），可以不做 OCR。

## 🚀 部署建议

### 开发环境
```bash
# MinerU: 使用官方 API（如果有 Key）
MINERU_MODE=official
MINERU_API_KEY=your_key

# OCR: 使用 RapidOCR
OCR_ENGINE=rapid_ocr
```

### 生产环境
```bash
# MinerU: 本地部署服务
MINERU_MODE=local
MINERU_API_BASE_URL=http://mineru-service:30001

# OCR: RapidOCR（高性能机器可用 PaddleOCR）
OCR_ENGINE=rapid_ocr
```

## 📝 总结

- ✅ **MinerU 2.5** = 主文档解析器（PDF → Markdown + 图片 + 表格 + 公式）
- ✅ **RapidOCR** = 辅助 OCR 引擎（图片 → 文字）
- ✅ 两者互补，不可替代
- ✅ MinerU 处理文档结构，RapidOCR 处理图片文字
- ✅ 结合使用，达到最佳效果

---

**关键点**: MinerU 负责"文档解析"，RapidOCR 负责"图片 OCR"，它们是不同层次的工具！
