# 标准化Agent结构

## 目录结构

每个agent都有统一的目录结构：

```
agent_name/
├── node.py      # Agent的主要实现代码
├── prompt.py    # Agent使用的提示词
├── tools.py     # Agent的工具函数
└── __init__.py  # 模块初始化文件
```

## 命名规范

- **node.py** - 所有Agent的主类文件统一命名为node.py
- **prompt.py** - 提示词管理
- **tools.py** - 工具函数集合
- **目录名** - 使用下划线分隔的小写命名，如：policy_analyzer

## Agent列表

1. **intent_router** - 意图路由Agent
2. **chat_agent** - 聊天对话Agent
3. **calculation_agent** - 计算处理Agent
4. **policy_analyzer** - 政策分析Agent
5. **policy_comparator** - 政策对比Agent
6. **answer_generator** - 答案生成Agent
7. **session_manager** - 会话管理Agent
8. **policy_retriever** - 政策检索Agent
9. **vector_retriever** - 向量检索Agent
10. **answer_verifier** - 答案验证Agent

## 使用方式

```python
# 导入agent
from agents_new import intent_router

# 使用agent
agent = intent_router.IntentRouter()
result = agent.process(request)
```

## 迁移说明

- 原来的agents目录保持不变
- 新的agents_new目录采用标准化命名
- 可以逐步迁移到新结构