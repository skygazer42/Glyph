# Python 示例

从仓库根目录按模块执行，不需要修改 `sys.path`。

| 模块 | 用途 |
| --- | --- |
| `python -m examples.autogen_streaming` | 流式与非流式 AssistantAgent 调用；搜索工具是需自行接入的占位示例 |
| `python -m examples.autogen_agent_tools` | 专家 Agent 作为工具 |
| `python -m examples.autogen_team_tools` | 写作团队作为工具 |
| `python -m examples.image_search_demo` | 已构建索引中的图片检索 |
| `python -m examples.mineru_demo` | MinerU 手动演示，需要实际解析服务和配置 |

`ag_builder.py`、`ag_workflow.py`、`ag_prompt.py` 和 `enterprise_agents.py` 是可选编排示例，不由应用入口自动加载。

`r2r/` 单独保存 R2R 的 Agent、RAG、研究流程源码参考。它依赖本仓库没有提供的外部 `core`、`shared` 包和原项目运行上下文，不是安装本应用依赖后即可独立运行的示例；不要将其导入生产应用包。

2026-11-17 仅整理源码和路径，以上命令未在本轮执行。
