# 前后端连接完整指南

## 项目架构

本项目采用前后端分离架构：

### 后端（FastAPI）
- **端口**: 8000
- **技术栈**: FastAPI + Python 3.11
- **主要功能**:
  - DSL生成和管理
  - 知识库管理
  - **AI Agent问答** (新增)
  - API文档自动生成

### 前端（Vue 3）
- **端口**: 3000
- **技术栈**: Vue 3 + Vite + Element Plus
- **主要功能**:
  - DSL生成界面
  - 知识库管理界面
  - **AI问答聊天界面** (新增)

## 快速启动

### 方式一：使用启动脚本（推荐）

#### 1. 启动后端
双击运行 `start_backend.bat`

或在命令行中：
```bash
conda activate gov
python api_server.py
```

#### 2. 启动前端
双击运行 `start_frontend.bat`

或在命令行中：
```bash
cd web
npm install  # 首次运行需要
npm run dev
```

### 方式二：使用IDE

#### PyCharm/VSCode (后端)
1. 打开 `api_server.py`
2. 确保使用 `gov` conda环境
3. 运行文件

#### VSCode (前端)
1. 打开终端
2. `cd web`
3. `npm run dev`

## 访问地址

启动成功后，可以访问：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **交互式API**: http://localhost:8000/redoc

## 功能说明

### 1. AI问答功能
- **路由**: `/agent`
- **功能**: 与AI助手实时对话
- **特点**:
  - 实时问答
  - 支持历史对话记录
  - 示例问题快速开始
  - 连接状态监控

### 2. DSL生成
- **路由**: `/dsl`
- **功能**: 从文本生成政策DSL
- **API端点**:
  - `POST /api/dsl/generate` - 生成DSL
  - `POST /api/dsl/save` - 保存DSL
  - `GET /api/dsl/list` - 获取DSL列表

### 3. 知识库管理
- **路由**: `/knowledge`
- **功能**: 文档上传、搜索和管理
- **API端点**:
  - `POST /api/knowledge/upload` - 上传文档
  - `POST /api/knowledge/embed` - 嵌入向量
  - `POST /api/knowledge/search` - 搜索知识库

## API接口

### Agent问答接口

#### 非流式问答
```http
POST /api/agent/chat
Content-Type: application/json

{
  "message": "你好，请介绍一下政策DSL",
  "stream": false
}
```

响应：
```json
{
  "success": true,
  "message": "政策DSL是一种领域特定语言...",
  "metadata": {
    "agent": "PolicyAssistant",
    "model": "deepseek-chat"
  }
}
```

#### 流式问答
```http
POST /api/agent/chat/stream
Content-Type: application/json

{
  "message": "你好"
}
```

响应（Server-Sent Events）：
```
data: {"content": "你", "done": false}
data: {"content": "好", "done": false}
data: {"content": "", "done": true}
```

## 前端架构

```
web/
├── src/
│   ├── api/              # API封装
│   │   ├── index.js      # API定义（含agentApi）
│   │   └── request.js    # Axios配置
│   ├── views/            # 页面组件
│   │   ├── AgentChat.vue      # AI问答页面 (新增)
│   │   ├── DSLGenerator.vue   # DSL生成页面
│   │   └── KnowledgeBase.vue  # 知识库页面
│   ├── components/       # 公共组件
│   ├── router/           # 路由配置
│   ├── App.vue          # 根组件
│   └── main.js          # 入口文件
├── index.html
├── package.json
└── vite.config.js       # Vite配置（含API代理）
```

## 关键配置

### Vite代理配置 (vite.config.js)
```javascript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

### CORS配置 (api_server.py)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 常见问题

### 1. 后端启动失败
**问题**: 端口被占用
```bash
# 检查端口占用
netstat -ano | findstr :8000

# 杀死进程
taskkill /PID <PID> /F
```

### 2. 前端无法连接后端
**检查清单**:
- [ ] 后端是否已启动（访问 http://localhost:8000/api/health）
- [ ] 端口是否正确（前端3000，后端8000）
- [ ] CORS配置是否正确
- [ ] 代理配置是否正确

### 3. Agent问答无响应
**可能原因**:
- DeepSeek API配置错误
- 模型配置缺少必要字段
- 网络连接问题

**解决方案**:
1. 检查 `models/llms.py` 中的API配置
2. 确认model_info包含所有必需字段：
   - vision
   - structured_output
   - function_calling
   - json_output

### 4. 依赖安装问题

**后端依赖**:
```bash
pip install fastapi uvicorn
pip install autogen-agentchat autogen-core "autogen-ext[openai]"
```

**前端依赖**:
```bash
cd web
npm install
```

## 开发调试

### 后端调试
```bash
# 开启调试模式
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

### 前端调试
```bash
cd web
npm run dev
```

浏览器开发者工具：
- Network标签：查看API请求
- Console标签：查看错误日志

## 测试接口

### 使用curl测试
```bash
# 测试健康检查
curl http://localhost:8000/api/health

# 测试Agent问答
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"你好\"}"
```

### 使用Swagger UI
访问 http://localhost:8000/docs 可以直接在浏览器中测试所有API接口。

## 生产部署

### 后端部署
```bash
# 使用gunicorn部署
pip install gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 前端部署
```bash
cd web
npm run build

# 使用nginx托管dist目录
# 配置nginx反向代理到后端API
```

## 更新日志

### v1.1.0 (最新)
- ✅ 新增AI Agent问答功能
- ✅ 完善前后端连接
- ✅ 添加启动脚本
- ✅ 完善文档说明

### v1.0.0
- ✅ DSL生成功能
- ✅ 知识库管理功能
- ✅ 基础前后端架构

## 技术支持

如有问题，请查看：
1. API文档：http://localhost:8000/docs
2. 浏览器Console日志
3. 后端终端日志
