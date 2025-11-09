# 快速开始指南 - AI政策助手

## 🎉 恭喜！前后端连接已完成

你现在拥有一个完整的前后端分离的AI政策助手系统！

## 📋 功能列表

### ✅ 已完成功能

1. **AI问答系统** (新增)
   - 实时对话
   - 历史记录
   - 示例问题
   - 连接状态监控

2. **DSL生成系统**
   - 从文本生成政策DSL
   - 保存和管理DSL规则
   - 测试DSL规则

3. **知识库管理**
   - 文档上传
   - 向量搜索
   - 文档管理

## 🚀 启动方式

### 方式一：使用启动脚本（推荐）

**Windows系统**:
1. 双击 `start_backend.bat` 启动后端
2. 双击 `start_frontend.bat` 启动前端
3. 浏览器访问 http://localhost:3000

### 方式二：命令行启动

**启动后端（端口8000）**:
```bash
# 激活conda环境
conda activate gov

# 启动后端服务
python api_server.py
```

**启动前端（端口3000）**:
```bash
# 进入web目录
cd web

# 首次运行需要安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 🌐 访问地址

启动成功后，在浏览器中访问：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **交互式API文档**: http://localhost:8000/redoc

## 📱 使用指南

### 1. AI问答功能

打开前端后，默认进入AI问答页面：

1. **快速开始**：点击右侧的示例问题
2. **输入问题**：在底部输入框输入你的问题
3. **发送消息**：点击"发送"按钮或按 Ctrl+Enter
4. **查看回复**：AI助手会实时回答你的问题

**示例对话**：
```
用户: 什么是政策DSL？
AI: 政策DSL（Domain-Specific Language）是一种专门用于政策制定、描述或执行的编程语言...
```

### 2. DSL生成功能

点击顶部菜单"DSL生成"：

1. 输入政策文本
2. 点击"生成DSL"
3. 查看生成的YAML格式规则
4. 保存或编辑生成的DSL

### 3. 知识库管理

点击顶部菜单"知识库管理"：

1. 上传政策文档
2. 将文档嵌入向量库
3. 搜索相关政策信息

## 🔧 技术架构

### 后端技术栈
- **框架**: FastAPI
- **AI引擎**: AutoGen + DeepSeek
- **向量数据库**: Milvus
- **文档解析**: LlamaIndex

### 前端技术栈
- **框架**: Vue 3 + Vite
- **UI组件**: Element Plus
- **状态管理**: Pinia
- **HTTP客户端**: Axios

### API端点

#### Agent问答
```
POST /api/agent/chat              # 非流式问答
POST /api/agent/chat/stream       # 流式问答
```

#### DSL管理
```
POST /api/dsl/generate            # 生成DSL
POST /api/dsl/save                # 保存DSL
GET  /api/dsl/list                # 获取DSL列表
GET  /api/dsl/{rule_id}           # 获取DSL详情
POST /api/dsl/test                # 测试DSL
```

#### 知识库
```
POST   /api/knowledge/upload      # 上传文档
POST   /api/knowledge/embed       # 嵌入向量
POST   /api/knowledge/search      # 搜索知识库
GET    /api/knowledge/documents   # 获取文档列表
DELETE /api/knowledge/documents/{id}  # 删除文档
```

## 🐛 常见问题

### 1. 后端启动失败

**问题**: 端口8000被占用
```bash
# Windows查看端口占用
netstat -ano | findstr :8000

# 关闭占用端口的进程
taskkill //PID <进程ID> //F
```

### 2. 前端无法访问后端

**检查清单**:
- [ ] 后端是否已启动（访问 http://localhost:8000/api/health）
- [ ] 查看浏览器控制台是否有错误
- [ ] 确认端口号正确（前端3000，后端8000）

### 3. AI回复速度慢

**原因**: DeepSeek API调用需要时间
**解决**: 这是正常现象，通常需要5-15秒

### 4. 依赖安装失败

**后端依赖**:
```bash
pip install -r requirements.txt
```

**前端依赖**:
```bash
cd web
npm install
```

## 📊 测试结果

### API测试
```bash
# 测试健康检查
curl http://localhost:8000/api/health
# 返回: {"status":"healthy","service":"政策DSL生成和知识库管理系统"}

# 测试Agent问答
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
# 返回: {"success":true,"message":"您好！我是小政...","metadata":{...}}
```

### 功能验证
✅ 后端API正常启动
✅ Agent问答接口响应正常
✅ 前端路由配置完成
✅ API代理配置正确
✅ CORS配置正常

## 📝 下一步

### 建议改进方向

1. **增强AI功能**
   - 添加流式响应支持
   - 集成知识库检索
   - 支持多轮对话

2. **优化用户体验**
   - 添加打字机效果
   - 保存对话历史到本地
   - 支持导出对话记录

3. **扩展功能**
   - 添加用户认证
   - 支持多语言
   - 添加数据统计面板

## 🎯 核心文件说明

### 后端核心文件
- `api_server.py` (第340-416行): Agent问答API实现
- `models/llms.py` (第6-16行): 模型配置

### 前端核心文件
- `web/src/views/AgentChat.vue`: AI问答页面
- `web/src/api/index.js` (第145-159行): Agent API调用
- `web/src/router/index.js`: 路由配置
- `web/src/App.vue` (第12-14行): 菜单配置

### 配置文件
- `web/vite.config.js`: Vite配置（API代理）
- `.env`: 环境变量配置

## 💡 使用技巧

1. **快速测试**: 使用Swagger UI (http://localhost:8000/docs) 直接测试API
2. **调试模式**: 打开浏览器开发者工具查看网络请求
3. **日志查看**: 后端终端会显示所有API请求日志

## 📞 获取帮助

如有问题，请查看：
1. 完整文档: `README_SETUP.md`
2. API文档: http://localhost:8000/docs
3. 项目文档: `docs/` 目录

---

**版本**: v1.1.0
**最后更新**: 2025-11-09
**状态**: ✅ 测试通过，可以正常使用
