# WorkflowAgent 使用说明

## 场景概述

当用户的问题需要 **多模态解析**（附带图片）或 **个人历史/资料查询** 时，`AgentService` 会将请求路由到 `workflow` 分支，由 `WorkflowAgent` 负责串联多个子能力完成任务。该链路基于 AutoGen GraphFlow，当前包含以下步骤：

1. **Rewrite / Intent**：`AgentService` 先执行改写与意图识别，判断是否命中 `vision_chain`、`user_history_chain` 或包含图片附件。
2. **GraphFlow 团队**：`WorkflowAgent` (`app/agents/pipeline/workflow_agent.py`) 组装 `vision_analyzer → task_router → answer_composer` 三个节点。
3. **工具调用**：`task_router` 通过 FunctionTool 动态选择调用：
   - `VisionTool.describe()`：解析图片中的文字/票据/地点信息。
   - `UserProfileTool.fetch()`：从 `resources/data/user_profiles.json` 读取 mock 用户历史。
   - `KnowledgeAgent.answer()`：向量检索 + 摘要。
   - `RuleEngineAgent.compute()`：执行 DSL 规则计算。
4. **统一答复**：`answer_composer` 汇总前序结果输出最终自然语言答复，并在 `metadata.workflow` 中记录 vision 摘要、用户档案命中、下游调用痕迹等。

## 配置要求

1. **多模态模型**（`.env` 中 `VISION__*` 段）：
   ```ini
   VISION__ENABLED=true
   VISION__MODEL=gpt-4o-mini
   VISION__API_KEY=your_key
   VISION__BASE_URL= # 可选，兼容 OpenAI 风格接口
   VISION__PROMPT_TEMPLATE=...
   ```
   缺省会回退到 `VISION_API_KEY` 或 `OPENAI_API_KEY`。

2. **用户历史数据文件**：
   - 默认路径：`resources/data/user_profiles.json`。
   - 可通过 `.env` 设置 `USER_PROFILE_DB_PATH=/your/path.json`。
   - 文件结构示例：
     ```json
     {
       "12345": {
         "name": "张三",
         "region": "深圳市南山区",
         "level": "白金用户",
         "last_login": "2024-10-01",
         "history": [
           "2023-09 完成以旧换新补贴申请并通过审批",
           "2024-03 参加家电消费券活动"
         ]
       }
     }
     ```

3. **Web Search 兜底（可选）**：`KnowledgeAgent` 仍然支持 `WEB_SEARCH__*` 配置，若 Milvus 未命中则会调用 Tavily 做联网搜索。

## 请求格式

- REST/CLI 调用时，`ChatRequest` / `ChatStreamRequest` 支持 `attachments` 字段（`app/api/schemas.py:148-191`）：
  ```json
  {
    "message": "帮我看看这张票据属于哪个城市，并查询用户 12345 的历史折扣",
    "attachments": [
      {
        "type": "image",
        "path": "/uploads/ticket.png",
        "mime_type": "image/png",
        "metadata": { "label": "发票照片" }
      }
    ]
  }
  ```
- `AgentService` 会把附件写入 Session 与 `FinalAnswer.metadata.attachments`，便于 UI 回显。

## 流程细节

1. **Vision 路径**：`VisionTool` (`app/agents/service/tools.py`) 自动判断本地/远程图片，生成 data-url 并调用 OpenAI 兼容模型，返回摘要写入 `metadata.workflow.vision_summary`。
2. **用户资料路径**：`UserProfileTool` 读取 JSON mock 库，如命中则 `metadata.workflow.user_profile_found=true`，并在最终答复中列出历史事件；如未命中则提示“系统中未找到记录”。
3. **知识 / 规则路径**：若 router 判断需要政策知识或 DSL 计算，会直接复用 `KnowledgeAgent` / `RuleEngineAgent` 的能力；其返回值仍保持 `FinalAnswer` 结构。
4. **回退策略**：GraphFlow 出现异常或所有工具均无结果时，`WorkflowAgent` 会返回兜底提示，metadata 中包含 `workflow.reason`。

## 扩展指引

- **接入真实 API**：将 `UserProfileTool` 的 `_load_from_file` 替换为 HTTP/DB 查询即可，GraphFlow 无需修改。
- **新增节点**：可在 `WorkflowAgent._build_flow` 中加入新的工具/Agent（例如 “合规审核” 节点），只需调整 DiGraph 即可。
- **调试方法**：在 `app/agents/pipeline/workflow_agent.py` 中对 `context`、`workflow_meta` 添加日志；或监控 `FinalAnswer.metadata.workflow` 了解每次路由情况。

## 相关文件

- `app/agents/service/agent_service.py`：路由、attachments 处理。
- `app/agents/service/tools.py`：`VisionTool` / `UserProfileTool` / `WebSearchTool` 实现。
- `app/agents/pipeline/workflow_agent.py`：GraphFlow 逻辑。
- `resources/data/user_profiles.json`：用户历史 mock 数据。
- `app/agents/README.md`：整体 Agent 模块说明。
