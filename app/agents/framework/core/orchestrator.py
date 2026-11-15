"""
Agent Orchestrator - Agent编排器
"""

import asyncio
from anyio import fail_after
from typing import Dict, List, Any, Optional, Callable, Set
from enum import Enum
import logging
from datetime import datetime
from uuid import uuid4

from ..models.base import MessageType
from .agent_base import AgentBase
from .message_bus import Message, MessageBus
from .agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"     # 并行执行
    PIPELINE = "pipeline"     # 管道执行
    CONDITIONAL = "conditional"  # 条件执行


class WorkflowStep:
    """工作流步骤"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        config: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
        timeout: float = 30.0
    ):
        self.agent_id = agent_id
        self.name = name
        self.condition = condition  # 执行条件
        self.config = config or {}
        self.retry_count = retry_count
        self.timeout = timeout
        self.dependencies: Set[str] = set()  # 依赖的步骤
        self.outputs: Set[str] = set()       # 输出的步骤


class Workflow:
    """工作流定义"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: Dict[str, WorkflowStep] = {}
        self.execution_strategy = ExecutionStrategy.SEQUENTIAL
        self.default_config: Dict[str, Any] = {}
        self.created_at = datetime.now()

    def add_step(self, step: WorkflowStep) -> "Workflow":
        """添加步骤"""
        self.steps[step.name] = step
        return self

    def add_dependency(self, step_name: str, depends_on: str) -> "Workflow":
        """添加步骤依赖"""
        if step_name not in self.steps or depends_on not in self.steps:
            raise ValueError("Both dependency steps must exist in the workflow")
        self.steps[step_name].dependencies.add(depends_on)
        self.steps[depends_on].outputs.add(step_name)
        return self

    def set_strategy(self, strategy: ExecutionStrategy) -> "Workflow":
        """设置执行策略"""
        self.execution_strategy = strategy
        return self


class AgentOrchestrator:
    """Agent编排器 - 管理Agent的协作和执行流程"""

    def __init__(
        self,
        registry: AgentRegistry,
        message_bus: MessageBus
    ):
        self.registry = registry
        self.message_bus = message_bus
        self.workflows: Dict[str, Workflow] = {}
        self.running_workflows: Dict[str, Dict[str, Any]] = {}
        self.execution_stats: Dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time": 0.0
        }

    def register_workflow(self, workflow: Workflow) -> None:
        """注册工作流"""
        self.workflows[workflow.name] = workflow
        logger.info(f"Registered workflow: {workflow.name}")

    def create_simple_workflow(
        self,
        name: str,
        agent_sequence: List[str],
        description: str = ""
    ) -> Workflow:
        """
        创建简单顺序工作流

        Args:
            name: 工作流名称
            agent_sequence: Agent执行序列
            description: 描述

        Returns:
            Workflow: 创建的工作流
        """
        workflow = Workflow(name, description)

        # 创建步骤
        for i, agent_id in enumerate(agent_sequence):
            step = WorkflowStep(
                agent_id=agent_id,
                name=f"step_{i}",
                timeout=30.0
            )
            workflow.add_step(step)

        # 添加依赖关系
        for i in range(len(agent_sequence) - 1):
            workflow.add_dependency(f"step_{i+1}", f"step_{i}")

        self.register_workflow(workflow)
        return workflow

    def create_conditional_workflow(
        self,
        name: str,
        branches: Dict[str, List[str]],
        default_branch: Optional[str] = None,
        description: str = ""
    ) -> Workflow:
        """
        创建条件分支工作流

        Args:
            name: 工作流名称
            branches: 条件分支 {条件名: Agent序列}
            default_branch: 默认分支
            description: 描述

        Returns:
            Workflow: 创建的工作流
        """
        workflow = Workflow(name, description)
        workflow.set_strategy(ExecutionStrategy.CONDITIONAL)
        if default_branch is not None:
            if default_branch not in branches:
                raise ValueError(f"Unknown default branch: {default_branch}")
            workflow.default_config["branch"] = default_branch

        # 为每个分支创建步骤
        for branch_name, agent_sequence in branches.items():
            def selected(ctx: Dict[str, Any], branch: str = branch_name) -> bool:
                return ctx.get("branch") == branch
            for i, agent_id in enumerate(agent_sequence):
                step_name = f"{branch_name}_step_{i}"
                step = WorkflowStep(
                    agent_id=agent_id,
                    name=step_name,
                    condition=selected
                )
                workflow.add_step(step)

                if i > 0:
                    workflow.add_dependency(
                        f"{branch_name}_step_{i}",
                        f"{branch_name}_step_{i-1}"
                    )

        # 注册工作流
        self.register_workflow(workflow)
        return workflow

    async def execute_workflow(
        self,
        workflow_name: str,
        initial_message: Message,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """
        执行工作流

        Args:
            workflow_name: 工作流名称
            initial_message: 初始消息
            context: 执行上下文

        Returns:
            Optional[Message]: 最终结果
        """
        if workflow_name not in self.workflows:
            logger.error(f"Workflow {workflow_name} not found")
            return None

        workflow = self.workflows[workflow_name]
        context = {**workflow.default_config, **(context if context is not None else {})}
        execution_id = f"{workflow_name}_{uuid4()}"

        logger.info(f"Starting workflow execution: {execution_id}")

        # 记录执行开始
        self.running_workflows[execution_id] = {
            "workflow": workflow_name,
            "start_time": datetime.now(),
            "status": "running",
            "current_step": None,
            "context": context
        }

        try:
            # 根据策略执行
            if workflow.execution_strategy in {
                ExecutionStrategy.SEQUENTIAL,
                ExecutionStrategy.PIPELINE,
                ExecutionStrategy.CONDITIONAL,
            }:
                result = await self._execute_sequential(workflow, initial_message, context)
            elif workflow.execution_strategy == ExecutionStrategy.PARALLEL:
                result = await self._execute_parallel(workflow, initial_message, context)
            else:
                raise ValueError(f"Unknown execution strategy: {workflow.execution_strategy}")

            # 更新统计
            if result is None:
                raise RuntimeError("Workflow completed without a result")
            self._update_stats(True, (datetime.now() - self.running_workflows[execution_id]["start_time"]).total_seconds())
            self.running_workflows[execution_id]["status"] = "completed"
            self.running_workflows[execution_id]["end_time"] = datetime.now()

            return result

        except asyncio.CancelledError:
            self.running_workflows[execution_id]["status"] = "cancelled"
            raise
        except Exception as e:
            logger.exception("Workflow execution failed")
            self._update_stats(False, (datetime.now() - self.running_workflows[execution_id]["start_time"]).total_seconds())
            self.running_workflows[execution_id]["status"] = "failed"
            self.running_workflows[execution_id]["error"] = str(e)
            return None

        finally:
            # 清理执行记录（保留最近100个）
            if len(self.running_workflows) > 100:
                for key, record in list(self.running_workflows.items()):
                    if len(self.running_workflows) <= 100:
                        break
                    if record["status"] != "running":
                        del self.running_workflows[key]

    async def _execute_sequential(
        self,
        workflow: Workflow,
        initial_message: Message,
        context: Dict[str, Any]
    ) -> Optional[Message]:
        """顺序执行工作流"""
        current_message = initial_message
        execution_order = self._get_execution_order(workflow)

        for step_name in execution_order:
            step = workflow.steps[step_name]

            # 检查条件
            if step.condition is not None and not step.condition(context):
                logger.info(f"Skipping step {step_name} due to condition")
                continue

            # 获取Agent实例
            agent = await self.registry.get_instance(step.agent_id)
            if agent is None:
                raise ValueError(f"Agent {step.agent_id} not found for step {step_name}")

            # 执行步骤
            result = await self._execute_step_with_retry(
                agent, current_message, step
            )
            if result is None:
                logger.error(f"Step {step_name} failed")
                return None
            current_message = result

            # 更新上下文
            context.update(current_message.content.get("context", {}))

        return current_message

    async def _execute_parallel(
        self,
        workflow: Workflow,
        initial_message: Message,
        context: Dict[str, Any]
    ) -> Optional[Message]:
        """并行执行工作流"""
        pending = self._get_execution_order(workflow)
        completed: set[str] = set()
        current_message = initial_message
        while pending:
            ready = [name for name in pending if workflow.steps[name].dependencies <= completed]
            tasks = []
            try:
                for name in ready:
                    step = workflow.steps[name]
                    if step.condition is not None and not step.condition(context):
                        continue
                    agent = await self.registry.get_instance(step.agent_id)
                    if agent is None:
                        raise ValueError(f"Agent {step.agent_id} not found for step {name}")
                    tasks.append(asyncio.create_task(self._execute_step_with_retry(agent, current_message, step)))
                results = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                with fail_after(5, shield=True):
                    await asyncio.gather(*tasks, return_exceptions=True)
                raise
            merged_content = dict(current_message.content)
            for result in results:
                if result is not None:
                    merged_content.update(result.content)
                    context.update(result.content.get("context", {}))
            current_message = Message(MessageType.DATA, merged_content, "orchestrator", recipient="user")
            completed.update(ready)
            pending = [name for name in pending if name not in completed]
        return current_message

    async def _execute_step_with_retry(
        self,
        agent: AgentBase,
        message: Message,
        step: WorkflowStep
    ) -> Optional[Message]:
        """执行步骤（带重试）"""
        for attempt in range(step.retry_count + 1):
            try:
                logger.debug(f"Executing step {step.name}, attempt {attempt + 1}")

                # 设置超时
                result = await asyncio.wait_for(
                    agent.handle_message(message),
                    timeout=step.timeout
                )
                if result is None or result.type == MessageType.ERROR_MESSAGE:
                    raise RuntimeError(f"Required step {step.name} did not produce a successful result")
                return result

            except asyncio.TimeoutError:
                logger.warning(f"Step {step.name} timed out")
                if attempt == step.retry_count:
                    raise
                await asyncio.sleep(1)

            except Exception:
                logger.exception("Step %s failed", step.name)
                if attempt == step.retry_count:
                    raise
                await asyncio.sleep(1)

        return None

    def _get_execution_order(self, workflow: Workflow) -> List[str]:
        """获取步骤执行顺序（拓扑排序）"""
        # 简单实现：按依赖关系排序
        visited: set[str] = set()
        visiting: set[str] = set()
        order: list[str] = []

        def visit(step_name: str):
            if step_name in visited:
                return
            if step_name in visiting:
                raise ValueError(f"Cycle in workflow dependencies at {step_name}")
            if step_name not in workflow.steps:
                raise ValueError(f"Unknown dependency step: {step_name}")
            visiting.add(step_name)

            # 先访问依赖
            for dep in sorted(workflow.steps[step_name].dependencies):
                visit(dep)
            visiting.remove(step_name)
            visited.add(step_name)
            order.append(step_name)

        for step_name in workflow.steps:
            visit(step_name)

        return order

    def _update_stats(self, success: bool, execution_time: float) -> None:
        """更新执行统计"""
        self.execution_stats["total_executions"] += 1
        if success:
            self.execution_stats["successful_executions"] += 1
        else:
            self.execution_stats["failed_executions"] += 1

        # 更新平均执行时间
        total = self.execution_stats["total_executions"]
        current_avg = self.execution_stats["avg_execution_time"]
        self.execution_stats["avg_execution_time"] = (
            (current_avg * (total - 1) + execution_time) / total
        )

    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流执行状态"""
        return self.running_workflows.get(execution_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取编排器统计信息"""
        return {
            "registered_workflows": len(self.workflows),
            "running_workflows": len(
                [w for w in self.running_workflows.values() if w["status"] == "running"]
            ),
            "execution_stats": self.execution_stats
        }
