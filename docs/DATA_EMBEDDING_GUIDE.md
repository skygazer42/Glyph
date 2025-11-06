# 数据嵌入和验证指南

## 📋 系统架构

```
PDF 文档
  ↓
MinerU 2.5 解析
  ↓
Markdown + 图片
  ↓
分级索引构建
  ├─ 一级：文档摘要
  ├─ 二级：章节摘要 (LLM 生成)
  └─ 三级：具体 Chunks
  ↓
向量嵌入 (DashScope)
  ↓
存储到 Milvus
  ↓
用户查询
  ├─ 向量检索
  ├─ 重排序 (DashScope Reranker)
  └─ 返回结果 + 相关图片
```

## 🚀 快速开始

### 1. 启动服务

```bash
# 启动 Milvus 和 Neo4j
docker-compose up -d

# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

服务地址：
- **Milvus**: localhost:19530
- **Attu (Milvus 管理界面)**: http://localhost:8000
- **Neo4j 浏览器**: http://localhost:7474 (neo4j/password123)
- **MinIO**: http://localhost:9001 (minioadmin/minioadmin)

### 2. 嵌入数据

```bash
# 方式 1: 使用嵌入脚本
python scripts/embed_documents.py

# 方式 2: 使用 batch_process.py (如果有)
python scripts/batch_process.py build \
    --data-dir /data/temp33/gov/data/process \
    --storage-dir ./storage/policy_index \
    --use-llm \
    --enable-images
```

脚本功能：
- ✅ 自动扫描 `/data/temp33/gov/data/process` 目录
- ✅ 读取所有 Markdown 文件
- ✅ 构建三级索引
- ✅ 使用 LLM 生成章节摘要
- ✅ 提取图片信息
- ✅ 嵌入到 Milvus

### 3. 验证数据

```bash
# 运行验证脚本
python scripts/verify_milvus.py
```

验证内容：
- ✅ Milvus 连接状态
- ✅ 集合列表
- ✅ 数据统计
- ✅ 索引信息
- ✅ 示例数据

## 📊 配置说明

当前系统配置 (已在 .env 中配置):

```bash
# LLM 配置
LLM_MODEL_NAME=qwen-turbo
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-2229a283d4304f6f90b7bccb1324ec0f

# Embedding 配置
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3
EMBEDDING_DIM=1024

# Reranker 配置
RERANKER_BACKEND=dashscope
RERANKER_MODEL=gte-rerank-v2

# Milvus 配置
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
DATABASE__MILVUS_COLLECTION_NAME=policy_documents
```

## 🔍 检索模式

系统支持三种检索模式：

### 1. 混合模式 (推荐)

```python
results = retriever.retrieve(
    query="家电补贴申请条件",
    retrieval_mode="hybrid",
    top_k=10,
    use_rerank=True
)
```

**特点**：
- 同时从三个级别检索
- 结果融合去重
- 使用 Reranker 优化排序
- 适合大多数查询场景

### 2. 层级模式

```python
results = retriever.retrieve(
    query="申请流程说明",
    retrieval_mode="hierarchical",
    top_k=10
)
```

**特点**：
- 逐级递进检索
- 先找文档 → 再找章节 → 最后找块
- 适合结构化查询

### 3. 直接模式

```python
results = retriever.retrieve(
    query="具体材料清单",
    retrieval_mode="direct",
    top_k=10
)
```

**特点**：
- 直接从 chunks 检索
- 速度最快
- 适合精确查询

## 🖼️ 图片检索

```python
# 图文混合检索
results = retriever.retrieve_with_images(
    query="申请二维码",
    top_k=10,
    image_only=False  # False=文本+图片，True=只要图片
)

# 结果包含
{
    'text_nodes': [...],      # 文本结果
    'image_results': [        # 图片结果
        {
            'path': 'images/qr_code.png',
            'caption': '图：扫码申请',
            'is_qrcode': True,
            'qr_content': 'https://apply.gov.cn',
            'alt_text': '申请二维码',
            'width': 800,
            'height': 800
        }
    ],
    'total_images': 3
}
```

## 🧪 测试示例

### Python API

```python
from knowledge_base.hierarchical_index import HierarchicalRetriever

# 初始化检索器
retriever = HierarchicalRetriever(
    storage_dir="./storage/policy_index",
    use_rerank="dashscope",
    enable_images=True
)

# 测试查询
test_queries = [
    "家电补贴申请条件是什么？",
    "手机以旧换新需要什么材料？",
    "汽车消费券如何领取？",
    "申请二维码在哪里？"  # 会返回图片
]

for query in test_queries:
    print(f"\n查询: {query}")

    # 文本检索
    results = retriever.retrieve(
        query=query,
        top_k=5,
        retrieval_mode="hybrid",
        use_rerank=True
    )

    print(f"找到 {len(results)} 个结果:")
    for i, node in enumerate(results[:3], 1):
        title = node.metadata.get('title', '未知')
        node_type = node.metadata.get('type', 'chunk')
        print(f"  {i}. [{node_type}] {title}")
        print(f"     {node.text[:100]}...")

    # 图片检索
    img_results = retriever.retrieve_with_images(
        query=query,
        top_k=3
    )

    if img_results['total_images'] > 0:
        print(f"\n  相关图片 ({img_results['total_images']} 张):")
        for img in img_results['image_results'][:2]:
            print(f"    - {img['path']}")
            if img['caption']:
                print(f"      说明: {img['caption']}")
```

## 📈 性能优化

### 1. 批量处理

```bash
# 使用更高的并发数
PERFORMANCE__BATCH_SIZE=20
PERFORMANCE__MAX_CONCURRENT_QUERIES=10
```

### 2. 缓存配置

```bash
# 启用缓存
PERFORMANCE__ENABLE_CACHE=true
PERFORMANCE__CACHE_TTL=3600
```

### 3. Milvus 优化

```bash
# 调整缓存大小
MILVUS_CACHE_SIZE=16GB
MILVUS_INSERT_BUFFER_SIZE=2GB

# 调整索引参数
MILVUS_NLIST=2048
MILVUS_NPROBE=32
```

## 🔧 故障排除

### 1. Docker 服务未启动

```bash
# 检查状态
docker-compose ps

# 查看日志
docker-compose logs standalone

# 重启服务
docker-compose restart
```

### 2. Milvus 连接失败

```bash
# 检查端口
netstat -tuln | grep 19530

# 测试连接
curl http://localhost:9091/healthz
```

### 3. 嵌入失败

```bash
# 检查配置
python -c "from config.settings import settings; print(settings.embedding)"

# 检查 API Key
echo $EMBEDDING_DASHSCOPE_API_KEY
```

### 4. 数据不存在

```bash
# 检查数据目录
ls -lh /data/temp33/gov/data/process

# 检查 Markdown 文件
find /data/temp33/gov/data/process -name "*.md"
```

## 📚 相关文档

- [分级索引说明](./hierarchical_index.py)
- [MinerU 配置](./MINERU_CONFIGURATION.md)
- [Milvus 部署](./MILVUS_DEPLOYMENT.md)
- [图片检索](./IMAGE_RETRIEVAL.md)

## 🎯 下一步

1. ✅ 启动服务
2. ✅ 运行嵌入脚本
3. ✅ 验证数据
4. ⏭️ 集成到 API 服务
5. ⏭️ 添加前端界面

---

**有问题？**

1. 查看日志: `docker-compose logs -f`
2. 运行验证: `python scripts/verify_milvus.py`
3. 检查配置: `python scripts/check_mineru_config.py`
