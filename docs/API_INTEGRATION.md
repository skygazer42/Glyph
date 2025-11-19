# Glyph AI问答系统集成文档

## 概述

Glyph 是一个智能政策问答系统，支持多轮对话、多模态输入、知识检索、规则计算等功能。本文档将帮助您快速集成 Glyph 的 AI 问答能力到您的项目中。

## 服务架构

```
前端应用 → HTTP API → Glyph AgentService → 多智能体系统 → 返回结果
```

## 基础信息

- **Base URL**: `http://localhost:8000` (默认)
- **API 前缀**: `/api/v1`
- **主要端点**: `/api/v1/agent/chat`
- **流式端点**: `/api/v1/agent/chat/stream`

## 核心接口

### 1. 普通问答接口

**端点**: `POST /api/v1/agent/chat`

用于一次性问答，等待完整响应后返回。

#### 请求格式

```json
{
  "message": "用户提问内容",
  "session_id": "可选的会话ID，用于多轮对话",
  "user_id": "可选的用户ID",
  "connection_id": "数据库连接ID（Text2SQL场景使用）",
  "text2sql_mode": false,
  "attachments": [
    {
      "type": "image",
      "url": "图片URL或路径",
      "name": "附件名称"
    }
  ]
}
```

#### 响应格式

```json
{
  "success": true,
  "message": "AI的回答内容",
  "session_id": "会话ID",
  "metadata": {
    "route": "路由路径",
    "intent": "意图识别结果",
    "confidence": 0.85,
    "rewritten_query": "改写后的查询",
    "session_id": "会话ID",
    "user_id": "用户ID",
    "connection_id": "数据库连接ID",
    "conversation_context": {
      "history_used": true,
      "history_turns": 3,
      "is_new_session": false
    },
    "domain_context": {
      "keywords": ["关键词"],
      "entities": ["实体"]
    }
  }
}
```

### 2. 流式问答接口

**端点**: `POST /api/v1/agent/chat/stream`

使用 Server-Sent Events (SSE) 实现实时推送，适合长文本生成场景。

#### 请求格式

与普通问答接口相同。

#### 响应格式 (SSE 流)

```
event: session
data: {"session_id": "xxx", "message_count": 1}

event: message
data: {
  "content": "回答内容片段",
  "done": false,
  "session_id": "xxx",
  "metadata": {"route": "knowledge", "intent": "policy_inquiry"}
}

event: done
data: {"content": "", "done": true, "session_id": "xxx"}
```

## 支持的功能特性

### 1. 多轮对话
- 通过 `session_id` 维护对话上下文
- 自动管理会话状态和历史记录

### 2. 多模态输入
- 支持图片附件分析
- 支持文档上传和处理

### 3. 智能路由
系统会自动识别用户意图并路由到最合适的处理模块：

- **knowledge**: 知识库检索问答
- **graph**: 知识图谱关系推理
- **rule_engine**: DSL规则计算（如补贴计算）
- **text2sql**: 自然语言到数据库查询
- **dialogue**: 日常对话
- **workflow**: 多模态协作任务

### 4. 专门场景

#### 政策内容查询
```json
{
  "message": "家电以旧换新补贴政策的具体内容是什么？"
}
```

#### 补贴金额计算
```json
{
  "message": "购买一台8000元的一级能效空调，能补贴多少钱？"
}
```

#### 数据库查询
```json
{
  "message": "查询2025年发布的所有政策",
  "text2sql_mode": true,
  "connection_id": 1
}
```

#### 图片分析
```json
{
  "message": "这张发票包含哪些政策信息？",
  "attachments": [
    {
      "type": "image",
      "url": "/path/to/invoice.jpg"
    }
  ]
}
```

## 快速集成示例

### JavaScript/TypeScript

```javascript
class GlyphClient {
  constructor(baseURL = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  async chat(message, options = {}) {
    const payload = {
      message,
      session_id: options.sessionId || null,
      user_id: options.userId || null,
      text2sql_mode: options.text2sqlMode || false,
      connection_id: options.connectionId || null,
      attachments: options.attachments || []
    };

    const response = await fetch(`${this.baseURL}/api/v1/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    return await response.json();
  }

  // 流式聊天
  async chatStream(message, options = {}, onChunk) {
    const payload = {
      message,
      session_id: options.sessionId || null,
      user_id: options.userId || null,
      text2sql_mode: options.text2sqlMode || false,
      connection_id: options.connectionId || null,
      attachments: options.attachments || []
    };

    const response = await fetch(`${this.baseURL}/api/v1/agent/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          if (onChunk) onChunk(data);
        }
      }
    }
  }
}

// 使用示例
const glyph = new GlyphClient();

// 普通问答
glyph.chat('家电补贴政策是什么？')
  .then(response => {
    console.log('回答:', response.message);
    console.log('路由:', response.metadata.route);
  });

// 流式问答
glyph.chatStream('请详细介绍一下补贴政策', {}, (chunk) => {
  if (chunk.content) {
    console.log('内容片段:', chunk.content);
  }
  if (chunk.done) {
    console.log('流式响应结束');
  }
});
```

### Python

```python
import requests
import json
from typing import Optional, List, Dict, Any

class GlyphClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        text2sql_mode: bool = False,
        connection_id: Optional[int] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        url = f"{self.base_url}/api/v1/agent/chat"
        payload = {
            "message": message,
            "session_id": session_id,
            "user_id": user_id,
            "text2sql_mode": text2sql_mode,
            "connection_id": connection_id,
            "attachments": attachments or []
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

# 使用示例
if __name__ == "__main__":
    glyph = GlyphClient()

    # 基本问答
    result = glyph.chat("家电以旧换新的补贴标准是多少？")
    print(f"回答: {result['message']}")
    print(f"路由: {result['metadata']['route']}")

    # 补贴计算
    result = glyph.chat(
        "买一台8000元的一级能效空调能补贴多少？",
        session_id="user123_session"
    )
    print(f"计算结果: {result['message']}")

    # 带图片的查询
    result = glyph.chat(
        "这张发票能享受什么补贴？",
        attachments=[{
            "type": "image",
            "url": "/path/to/invoice.jpg",
            "name": "发票"
        }]
    )
    print(f"图片分析结果: {result['message']}")
```

### cURL

```bash
# 基本问答
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "家电以旧换新补贴政策是什么？"
  }'

# 多轮对话（带session_id）
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "那具体怎么申请？",
    "session_id": "user_session_123"
  }'

# 补贴计算
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "购买一台6000元的二级能效冰箱，能补贴多少钱？",
    "session_id": "calc_session"
  }'

# 图片分析
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "这张图片包含什么信息？",
    "attachments": [
      {
        "type": "image",
        "url": "/uploads/invoice.jpg",
        "name": "发票图片"
      }
    ]
  }'
```

## 会话管理

### 获取会话信息
```bash
GET /api/v1/agent/sessions/{session_id}
```

### 获取会话历史
```bash
GET /api/v1/agent/sessions/{session_id}/messages?limit=10
```

### 删除会话
```bash
DELETE /api/v1/agent/sessions/{session_id}
```

## 错误处理

常见错误响应格式：

```json
{
  "detail": "错误详情信息"
}
```

### 常见错误码
- `400`: 请求参数错误
- `404`: 会话不存在
- `500`: 服务器内部错误

## 部署和配置

### 环境变量配置

```bash
# 基础配置
PORT=8000
HOST=0.0.0.0

# 数据库配置
DATABASE_URL=mysql://user:password@localhost/glyph_db

# LLM配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1

# 向量数据库
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Redis缓存
REDIS_URL=redis://localhost:6379

# 文件上传
UPLOAD_DIR=./resources/uploads
MAX_FILE_SIZE=10485760  # 10MB
```

### Docker 部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  glyph-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql://user:pass@mysql:3306/glyph
      - MILVUS_HOST=milvus
      - REDIS_URL=redis://redis:6379
    depends_on:
      - mysql
      - milvus
      - redis
```

## 性能优化建议

1. **使用会话管理**: 合理使用 `session_id` 避免重复上下文加载
2. **流式响应**: 长文本场景使用流式接口提升用户体验
3. **缓存策略**: 系统内置FAQ缓存，常见问题响应更快
4. **并发控制**: 合理控制并发请求数避免资源过载

## 常见使用场景

### 政务服务机器人
```javascript
// 政策咨询
glyph.chat("2025年有哪些新的惠民政策？");

// 资格查询
glyph.chat("我符合以旧换新的条件吗？");

// 补贴计算
glyph.chat("买家电能补贴多少钱？");
```

### 企业内部知识库
```javascript
// 规章制度查询
glyph.chat("公司的报销政策是什么？");

// 流程指导
glyph.chat("怎么申请差旅报销？");
```

### 客服智能问答
```javascript
// 产品咨询
glyph.chat("这款产品有什么功能？");

// 故障排查
glyph.chat("设备无法启动怎么办？");
```

## 联系支持

- **项目地址**: [Glyph GitHub仓库]
- **文档更新**: 请关注项目文档更新
- **问题反馈**: 通过GitHub Issues提交问题

---

*本文档基于Glyph系统当前版本编写，如有更新请参考最新版本。*