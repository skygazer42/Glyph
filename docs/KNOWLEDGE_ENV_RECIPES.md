# 知识库 `.env` 配置速查

这份文档只关注一件事：**我在 `.env` 里能怎么配、配成什么效果**，方便你自己调整，完全不需要看具体接口和代码。

可以按优先级理解为三层：

1. 用什么召回模式（只向量 / 分级 + 向量）
2. 切片/分块怎么切（chunk 大小和策略）
3. 回答阶段给 LLM 多长上下文、什么时候早停

---

## 一、召回模式：只用向量库，还是加上分级索引？

### 1. 纯向量召回（Milvus-only，最简单）

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=false
```

- 说明：
  - 所有检索都走 Milvus 向量库，不使用 LlamaIndex 分级索引。
  - 不需要 `LLAMAINDEX_STORAGE_DIR` 目录，不依赖 LlamaIndex 安装。
- 适合场景：
  - 资源有限、先跑通系统；
  - 不关心章节结构，只要大致命中即可。

### 2. 分级索引 + 向量混合（推荐）

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical
```

- 说明：
  - 检索时会先用 LlamaIndex 的“文档/章节/chunk 多级索引”召回，再用 Milvus 向量检索兜底。
  - 要求 `LLAMAINDEX_STORAGE_DIR` 下已经用脚本（如 `scripts/4_embed_documents.py`）构建好了索引。
- 适合场景：
  - 文档比较长、结构清晰（例如成套政策细则）；
  - 希望召回“哪一章哪一条”的相关内容，而不是散乱的句子。

> 小结：  
> - 想简单：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`  
> - 想召回更稳、更懂章节结构：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=true + LLAMAINDEX_STORAGE_DIR=...`

---

## 二、切片/分块策略：一个块多大、怎么切？

以下三个变量控制“构建 LlamaIndex 分级索引时怎么切块”：

```ini
LLAMAINDEX_CHUNK_STRATEGY=sentence        # simple | sentence | keyword_aware
LLAMAINDEX_CHUNK_SIZE=800                 # 每块大致长度（字符级近似）
LLAMAINDEX_CHUNK_OVERLAP=150              # 相邻块的重叠长度
```

### 1. 常用策略解释

- `LLAMAINDEX_CHUNK_STRATEGY`
  - `simple`：固定长度滑动窗口，最简单；
  - `sentence`：按句子边界切 + 窗口重叠（**推荐**，适合中文长文）；
  - `keyword_aware`：围绕关键词（如“补贴标准”“申请条件”等）扩展前后窗口，让关键条款更完整。

- `LLAMAINDEX_CHUNK_SIZE`
  - 数值越大：单块越长，上下文越完整，但块数量变少；
  - 数值越小：单块越短，粒度更细，块数量变多。

- `LLAMAINDEX_CHUNK_OVERLAP`
  - 控制相邻块之间的重叠区域；
  - 重叠增大会减少“被切断在两块中间”的风险，但会增加索引体积。

### 2. 推荐组合示例

**通用推荐（起步配置）**

```ini
LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=800
LLAMAINDEX_CHUNK_OVERLAP=150
```

**想让召回更细（每块短一点）**

```ini
LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=600
LLAMAINDEX_CHUNK_OVERLAP=120
```

**想让上下文更完整（每块长一点）**

```ini
LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=1000
LLAMAINDEX_CHUNK_OVERLAP=200
```

> 注意：改完这三个变量后，需要重新跑一次分级索引构建脚本（例如 `scripts/4_embed_documents.py`），新的切片策略才会生效。

---

## 三、回答阶段：给 LLM 多大上下文、何时“快速返回”？

这两个变量控制 `KnowledgeAgent` 的行为：

```ini
EARLY_STOP_CONF=0.80                # 检索置信度 ≥ 该值时走快速通道
KNOWLEDGE_MAX_CONTEXT_PER_DOC=2500  # 每篇文档给 LLM 的最大字符数
```

### 1. `EARLY_STOP_CONF` —— 要不要“早停”

- 作用：
  - 当检索置信度（根据相似度分数估算） ≥ `EARLY_STOP_CONF` 时，走“早停路径”：
    - 优先用简单规则从首篇文档中抽取关键点；
    - 抽不到再用一次性 LLM 总结；
    - 不再做额外的重排/深度分析。

- 调参建议：
  - 想“更快、更省”：把它调低一点，例如：
    ```ini
    EARLY_STOP_CONF=0.70
    ```
  - 想“更稳、更谨慎”：把它调高一点，例如：
    ```ini
    EARLY_STOP_CONF=0.90
    ```

### 2. `KNOWLEDGE_MAX_CONTEXT_PER_DOC` —— 一篇文档给多少内容

- 作用：
  - 控制每篇文档在送入 LLM 之前的最大截断长度；
  - 例如设 `2500`，则每篇文档最多截取 2500 个字符参与回答。

- 调参建议（要结合模型上下文来调）：
  - 如果 LLM 是 4k 上下文：
    ```ini
    KNOWLEDGE_MAX_CONTEXT_PER_DOC=1500  # 或 1200–1800 区间
    ```
  - 如果 LLM 是 16k 上下文：
    ```ini
    KNOWLEDGE_MAX_CONTEXT_PER_DOC=2500  # 或 2500–3500 区间
    ```
  - 如果你发现答案“啰嗦但不聚焦”，可以尝试先降这个值，而不是马上改召回逻辑。

---

## 四、几套常用“整套组合”

### 1. 最简模式（只用向量库，快速起步）

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=false

EARLY_STOP_CONF=0.80
KNOWLEDGE_MAX_CONTEXT_PER_DOC=2000
```

- 效果：
  - 不需要 LlamaIndex 索引，删掉也没关系；
  - 所有召回走 Milvus，逻辑最简单。

### 2. 推荐生产模式（分级索引 + 向量混合）

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical

LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=800
LLAMAINDEX_CHUNK_OVERLAP=150

EARLY_STOP_CONF=0.80
KNOWLEDGE_MAX_CONTEXT_PER_DOC=2500
```

- 效果：
  - 同时利用“章节结构 + 向量相似度”，召回更稳定；
  - 对大部分政策问答场景是比较均衡的配置。

### 3. 高精度模式（模型上下文大、对复杂问答要求高）

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical

LLAMAINDEX_CHUNK_STRATEGY=sentence
LLAMAINDEX_CHUNK_SIZE=800
LLAMAINDEX_CHUNK_OVERLAP=200

EARLY_STOP_CONF=0.90
KNOWLEDGE_MAX_CONTEXT_PER_DOC=3200
```

- 效果：
  - 更少早停，更多问题会走“重排 + 深度总结”；
  - 单文档上下文更长，更适合复杂条款、对比分析类问题。

---

## 五、实用调参顺序建议

每次只改一两类参数，避免一口气全动看不出效果：

1. **先选召回模式**：  
   - 没有 LlamaIndex 或资源有限：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`  
   - 资源允许、想召回更稳：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=true` + 配好 `LLAMAINDEX_STORAGE_DIR`
2. **再调切片参数**（只在 Hybrid 下有用）：  
   - 从 `LLAMAINDEX_CHUNK_SIZE=800 / OVERLAP=150` 起步，看召回是否太碎或太宽，再微调。
3. **最后调回答阶段行为**：  
   - 用 `EARLY_STOP_CONF` + `KNOWLEDGE_MAX_CONTEXT_PER_DOC` 找到“速度/成本/质量”的平衡点。

只要你围绕这几个变量调整，就能控制知识库的绝大部分行为，而不用碰代码。调整完 `.env` 之后：

- 改召回模式/早停/上下文长度 → 重启后端服务即可；
- 改切片/分块策略 → 需要重跑一次分级索引构建脚本，让新的切片生效。 
