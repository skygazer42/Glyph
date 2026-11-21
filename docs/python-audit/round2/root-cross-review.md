# 根分区独立交叉复核

复核依据：`python-coding-guidelines` 的 ERR-004、LOG-004、ASY-005/006/008/009、RES-005。只检查具体适用的强制项及真实生命周期边界；未调用外部服务。根业务源码由主代理修改；交叉复核器仅修改自己负责的 LoggingManager、其现有 API 回归和分区证据。

## 发现、修正与证据

| 位置 | 规则及实际触发 | 修正与验证 |
| --- | --- | --- |
| `app/agents/service/tools.py`，KnowledgeTool 初始化与关闭 | 初始化线程尚未结束时调用 `aclose()`，初始化分支关闭新服务后仍向等待者返回该对象。以原源码类 AST、线程事件和隔离服务复现：`pending_caller_received_service=True`、`received_service_already_closed=True`。 | 主代理在 `get_service()` 等待后重新检查关闭状态，并报告该竞态先红后绿；此前单次构造、调用方取消后仍持有初始化任务、同步入口阻止重复初始化的边界保留。 |
| `app/core/logging_manager.py`，两个异常事件接口 | LOG-004。实际 AutoGen 0.7.5 事件构造器只保存 `str(exception)`，原包装器不传 `exc_info`，丢失堆栈。 | 显式传 `(type(exception), exception, exception.__traceback__)`。真实 `StreamHandler` 在 `except` 外记录异常的两组回归先红后绿，断言 traceback、失败函数名和异常文本。 |
| `app/agents/framework/base/base_agent.py` 后台任务回调/停止；`core/agent_master.py` 创建任务停止；`core/agent_registry.py` 多项关闭失败日志 | LOG-004。只把异常格式化为字符串会丢失后台失败堆栈；注册中心最终异常链只保留首个失败，其他失败仍需独立定位。 | 主代理已补显式异常 tuple；按各自真实异常对象记录堆栈。 |
| `app/agents/framework/core/agent_registry.py`，`shutdown_all()` 外层 gather | ASY-009。每个子协程内部已有 shield，仍不能防止父 gather 在子协程开始前取消它。以原方法 AST 在已取消 AnyIO scope 中直接调用，得到 `shutdown_ran_under_cancelled_caller_scope=False`，实例映射已清空。 | 主代理为外层 gather 增加共享有界 shield helper，并报告真实注册中心回归先红 `closed=[]` 后绿 `closed=['closed']`。`AgentMaster.stop()` 的创建任务 gather 同样加 helper。 |
| `app/agents/framework/common/session_manager.py`，`stop()` 的 `except CancelledError: pass` | ASY-005。该分支混淆预期的子任务取消与调用方取消。以原方法 AST、真实 `asyncio.sleep` 子任务和 `loop.call_soon(stopping.cancel)` 复现：`stop_returned_normally_after_caller_cancel=True`、`cancel_requested=1`、`is_cancelled=False`。 | 主代理已通过 helper 包裹 `gather(..., return_exceptions=True)`，仅忽略结果中的子任务 CancelledError，其余 BaseException 传播；调用方取消不再被 except 吞掉。两组参数回归先红后绿，交叉复核器独立重跑通过。 |

## 确认保留的契约

- `AgentService.process_query_stream()` 在实际流消费作用域内确定关闭后端流，并在同一任务/ContextVar 作用域重置请求状态。Router/Team 生产者自身的 `finally` 也使用共享有界清理，覆盖取消发生在生产者 `__anext__` 内的情况。
- ERR-004：自动 LightRAG 种子导入在 `HEAD` 已是可选启动辅助操作；配置缺省、未启用、目录缺失及无可解析文档均显式跳过，导入失败已有 warning 后继续。当前线程边界和 traceback 修正未新增业务降级。
- ERR-004：助手 AutoGen memory 写入在 `HEAD` 已有独立 warning 降级，且先完成 `session_store.add_answer()`；memory 模块明确使用本地、非持久化 ListMemory。主会话保存失败仍传播。保留既有辅助旁路，不据风格删除。
- `LoggingManager` 的通用接口是标准 logging 的 `info`/`warning`/`error`；没有 `exception()` 方法。检查范围未发现误用 `logging_manager.exception()`。
- 有界清理是框架支持的协作式取消预算；不宣称可以强制中止阻塞线程、无限内部 shield 或未遵守取消协议的第三方资源。

## 独立执行的复验

- API + ChatDB 分区：68 项行为回归通过；其中新增两组真实日志 traceback 回归先红后绿。
- 根分区聚焦复验：`python -X utf8 -m pytest tests/test_python_guidelines_runtime.py -k 'knowledge or registry_shutdown or session_stop' -q`，7 通过、44 未选择；包含初始化/取消/同步入口竞态、关闭时禁止发布已关闭服务、取消父 scope 关闭注册中心、区分子任务与调用方取消。
- 分区 81 个 Python 文件：mypy `--check-untyped-defs` 零错误；Ruff E4/E7/E9/F/B/ASYNC 零错误；Python 3.10 AST、compile 和分区 `git diff --check` 通过。
- 两份分区报告及 81 文件 LF 归一化 SHA256 清单已刷新并逐文件核对。证据位于 `docs/python-audit/round2/api/`。
- 根分区最终完整回归由主代理执行；本记录区分独立复现与主代理提供的修复复验结果，不将旧 `final/` 证据作为本轮通过依据。
