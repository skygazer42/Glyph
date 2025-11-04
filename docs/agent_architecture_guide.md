# Agent架构使用指南

## 概述

本系统采用模块化的Agent架构，通过总控制器（AgentMasterController）统一管理所有Agent的生命周期和协作。每个Agent被视为一个独立的模块，可以灵活组合和编排。

## 核心组件

### 1. AgentMasterController（总控制器）
系统的核心，负责：
- Agent的注册和发现
- 消息总线的管理
- 工作流的编排和执行
- 生命周期管理

### 2. AgentBase（Agent基类）
所有Agent的基础类，提供：
- 统一的消息处理接口
- 状态管理
- 性能指标统计
- 错误处理机制

### 3. AgentRegistry（注册中心）
管理Agent的注册信息：
- Agent类型的注册
- 实例的创建和管理
- 依赖关系的维护

### 4. MessageBus（消息总线）
实现Agent间的通信：
- 异步消息传递
- 消息路由和过滤
- 支持请求-响应模式

### 5. AgentOrchestrator（编排器）
定义和执行工作流：
- 顺序执行
- 并行执行
- 条件分支
- 管道模式

## 使用示例

### 1. 创建自定义Agent

```python
from agents.core.agent_base import AgentBase
from agents.core.message_bus import Message
from models.base import AgentType, MessageType

class MyCustomAgent(AgentBase):
    def __init__(self):
        super().__init__(
            agent_id="my_custom_agent",
            agent_type=AgentType.SPECIALIZED,
            name="My Custom Agent",
            description="自定义Agent示例"
        )
        self.capabilities = ["process_text", "analyze_data"]

    async def process(self, message: Message) -> Optional[Message]:
        """实现核心处理逻辑"""
        try:
            # 获取消息内容
            content = message.content
            action = content.get("action")

            # 处理不同类型的请求
            if action == "process_text":
                result = await self._process_text(content.get("text"))
            elif action == "analyze_data":
                result = await self._analyze_data(content.get("data"))
            else:
                result = {"error": f"Unknown action: {action}"}

            # 返回响应消息
            return message.create_reply(
                content=result,
                sender=self.agent_id
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return message.create_reply(
                content={"error": str(e)},
                sender=self.agent_id
            )

    async def _process_text(self, text: str) -> dict:
        """文本处理逻辑"""
        # 实现具体的处理逻辑
        return {"processed_text": text.upper(), "length": len(text)}

    async def _analyze_data(self, data: dict) -> dict:
        """数据分析逻辑"""
        # 实现具体的数据分析逻辑
        return {"analysis": "Data analyzed successfully"}
```

### 2. 注册和使用Agent

```python
import asyncio
from agents.core.agent_master import AgentMasterController

async def main():
    # 创建总控制器
    controller = AgentMasterController()

    # 初始化控制器
    await controller.initialize()

    # 注册自定义Agent
    controller.register_agent_module(
        agent_id="my_agent",
        agent_class=MyCustomAgent,
        agent_type=AgentType.SPECIALIZED,
        name="My Agent",
        description="我的自定义Agent",
        auto_create=True  # 自动创建实例
    )

    # 处理请求
    request = {
        "action": "process_text",
        "text": "Hello World"
    }

    result = await controller.process_request(request)
    print(f"Result: {result}")

    # 停止控制器
    await controller.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. 创建工作流

```python
from agents.core.orchestrator import Workflow, ExecutionStrategy

# 创建简单顺序工作流
workflow = controller.orchestrator.create_simple_workflow(
    name="text_processing_workflow",
    agent_sequence=[
        "query_analyzer",
        "my_custom_agent",
        "answer_generator"
    ],
    description="文本处理工作流"
)

# 执行工作流
message = Message(
    type=MessageType.USER_QUERY,
    content={"text": "需要处理的文本"},
    sender="user"
)

result = await controller.orchestrator.execute_workflow(
    "text_processing_workflow",
    message
)
```

### 4. 使用模块化Agent

系统提供了三个核心模块：

#### AgentBuilder（构建器）
用于动态创建和管理Agent：

```python
# 发送构建请求
builder_message = Message(
    type=MessageType.DATA,
    content={
        "action": "create",
        "agent_type": "retriever",
        "config": {
            "name": "my_retriever",
            "vector_store": "chroma",
            "embedding_model": "text-embedding-ada-002"
        }
    },
    sender="user",
    recipient="agent_builder"
)

# 通过消息总线发送
await controller.message_bus.publish(builder_message)
```

#### AgentPromptManager（提示词管理器）
管理Agent的提示词模板：

```python
# 创建新的提示词
prompt_message = Message(
    type=MessageType.DATA,
    content={
        "action": "create",
        "prompt_id": "custom_analyzer",
        "agent_type": "analyzer",
        "template": "请分析以下内容：{content}",
        "variables": ["content"],
        "description": "内容分析提示词"
    },
    sender="user",
    recipient="agent_prompt_manager"
)

await controller.message_bus.publish(prompt_message)
```

#### AgentStateManager（状态管理器）
管理Agent和会话的状态：

```python
# 保存状态
state_message = Message(
    type=MessageType.DATA,
    content={
        "action": "set",
        "state_id": "user_123_context",
        "content": {
            "user_preference": "detailed",
            "last_query": "政策查询",
            "session_data": {"step": 2, "progress": 0.5}
        },
        "session_id": "session_456",
        "ttl": 3600  # 1小时后过期
    },
    sender="user",
    recipient="agent_state_manager"
)

await controller.message_bus.publish(state_message)
```

## 最佳实践

### 1. Agent设计原则
- **单一职责**：每个Agent只负责一个特定功能
- **无状态**：尽量设计无状态Agent，状态通过StateManager管理
- **异步处理**：所有I/O操作都应该是异步的
- **错误处理**：妥善处理异常，返回有意义的错误信息

### 2. 消息设计
- **清晰的类型**：使用合适的MessageType
- **结构化内容**：消息内容应该是结构化的字典
- **包含上下文**：必要时包含会话ID和追踪信息

### 3. 工作流设计
- **模块化**：将复杂流程拆分为可复用的工作流
- **错误恢复**：设计合适的错误处理和恢复机制
- **性能优化**：合理使用并行执行减少延迟

### 4. 配置管理
- **外部化配置**：将配置项放在外部文件或环境变量
- **版本控制**：对配置变更进行版本管理
- **动态更新**：支持运行时更新配置

## 扩展指南

### 添加新的Agent类型

1. 在`models/base.py`中添加新的AgentType
2. 继承AgentBase创建新Agent类
3. 实现process方法
4. 注册到控制器

### 创建新的工作流模式

1. 在AgentOrchestrator中添加新的ExecutionStrategy
2. 实现对应的执行逻辑
3. 在Workflow类中添加配置选项

### 集成外部服务

1. 在Agent中通过配置获取服务凭证
2. 使用异步HTTP客户端调用外部API
3. 实现合适的重试和超时机制

## 性能优化建议

1. **使用连接池**：对于数据库和HTTP客户端使用连接池
2. **实现缓存**：对频繁访问的数据实现缓存
3. **批量处理**：尽可能批量处理消息
4. **监控指标**：收集和分析性能指标
5. **资源限制**：设置合理的超时和资源限制

## 故障排查

1. **查看日志**：使用适当的日志级别记录关键信息
2. **健康检查**：定期检查Agent和系统组件的健康状态
3. **消息追踪**：实现消息的追踪和审计功能
4. **性能分析**：使用工具分析性能瓶颈

## 总结

这个模块化的Agent架构提供了：
- **灵活性**：Agent可以独立开发和部署
- **可扩展性**：容易添加新功能和工作流
- **可维护性**：清晰的职责分离和模块化设计
- **可复用性**：Agent和工作流可以在不同场景复用

通过总控制器的统一管理，实现了Agent间的有效协作和系统的整体协调。