# 测试文件说明

本目录包含所有测试文件。

## DSL生成相关测试

### 主要测试文件

- **test_complete_dsl.py** - 完整DSL生成和验证测试
  - 测试消费券和家电补贴两种政策类型
  - 验证模板自动检测
  - 验证关键字段完整性
  - **推荐使用此文件进行完整测试**

- **test_api_dsl.py** - API接口DSL生成测试
  - 测试通过API服务生成DSL
  - 需要先启动API服务: `python api_server.py`

- **test_improved_dsl.py** - 增强版DSL提取测试
  - 测试使用外部模板和详细提取
  - 单个消费券政策测试

- **test_batch_dsl.py** - 批量DSL生成测试
  - 从 `data/guize` 目录批量处理政策文件
  - 生成多个规则文件

### 规则执行测试

- **test_rule_exec.py** - 消费券规则执行测试
  - 测试Rule_Test_Consumer_Coupon规则
  - 验证250元消费的优惠计算

- **test_appliance_exec.py** - 家电补贴规则执行测试
  - 测试家电补贴规则
  - 验证8000元空调的补贴计算

- **test_rule_execution.py** - 规则执行示例

## 知识库相关测试

### 主要测试文件

- **test_kb_simple.py** - 简化版知识库召回测试
  - 测试向量检索功能
  - 4个测试查询
  - **推荐使用此文件测试知识库**

- **test_knowledge_base.py** - 知识库完整测试

### 数据处理测试

- **test_document_processor.py** - 文档处理器测试
- **test_integrated_chunking.py** - 集成分块测试
- **test_keyword_chunking.py** - 关键词分块测试
- **test_splitter_comparison.py** - 分块方法对比

### 检索测试

- **test_all_retrieval_methods.py** - 所有检索方法测试
- **test_retrieval_comparison.py** - 检索方法对比
- **test_hybrid_simple.py** - 混合检索简单测试
- **test_llamaindex_hybrid_retrieval.py** - LlamaIndex混合检索
- **test_image_retrieval.py** - 图像检索测试

### 向量化测试

- **test_embedding.py** - 向量化基础测试
- **test_embedding_dim.py** - 向量维度测试
- **test_dimension_inference.py** - 维度推断测试
- **test_embed_simple.py** - 简化版向量化测试

### 问答测试

- **test_qa.py** - 问答系统测试
- **test_qa_simple.py** - 简化版问答测试
- **test_qa_with_rerank.py** - 带重排序的问答测试
- **test_reranker.py** - 重排序器测试

### 真实数据测试

- **test_real_data.py** - 真实数据测试
- **test_real_data_optimized.py** - 优化版真实数据测试

## 配置和环境测试

- **test_config.py** - 配置文件测试
- **test_settings.py** - 设置模块测试
- **test_docker_functionality.py** - Docker功能测试

## 演示文件

- **demo_all_splitters.py** - 所有分块器演示
- **demo_dsl.py** - DSL使用演示
- **demo_sliding_window.py** - 滑动窗口演示
- **example_dsl_usage.py** - DSL使用示例
- **quick_test_dsl.py** - DSL快速测试

## 测试结果文件

- **test_exec_result.json** - 消费券规则执行结果
- **test_appliance_result.json** - 家电补贴规则执行结果

## 运行测试

### DSL生成完整测试
```bash
# 需要先启动API服务
python api_server.py

# 在另一个终端运行测试
cd tests
python test_complete_dsl.py
```

### 知识库召回测试
```bash
# 确保Docker服务已启动
docker-compose up -d

# 运行测试
cd tests
python test_kb_simple.py
```

### 规则执行测试
```bash
# 需要先启动API服务
python api_server.py

# 测试消费券规则
cd tests
python test_rule_exec.py

# 测试家电补贴规则
cd tests
python test_appliance_exec.py
```

## 测试环境要求

- Python 3.8+
- Docker (用于Milvus等服务)
- 已配置 `.env` 文件
- API服务运行在 http://localhost:8000

## 最新测试结果 (2025-11-08)

### ✅ DSL生成测试
- 消费券政策: 使用consumer_coupon模板 ✓
- 家电补贴政策: 使用appliance_subsidy模板 ✓
- 所有关键字段验证通过 ✓

### ✅ 知识库召回测试
- 4个测试查询全部成功 ✓
- 召回分数: 0.6-0.8 ✓

### ✅ 规则执行测试
- 消费券计算: 250元 → 满200减40 → 实付210元 ✓
