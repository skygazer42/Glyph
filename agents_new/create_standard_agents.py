#!/usr/bin/env python3
"""
创建标准化agent结构
"""

import os
import shutil
from pathlib import Path

def create_agent_structure():
    """创建标准化的agent目录结构"""
    base_dir = Path("/data/temp33/gove/agents_new")

    # 定义所有agent
    agents = [
        "intent_router",
        "chat_agent",
        "calculation_agent",
        "policy_analyzer",
        "policy_comparator",
        "answer_generator",
        "session_manager",
        "policy_retriever",
        "vector_retriever",
        "answer_verifier"
    ]

    print("=== 创建标准化Agent结构 ===\n")

    for agent in agents:
        # 创建agent目录
        agent_dir = base_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)

        # 创建node.py
        node_file = agent_dir / "node.py"
        if not node_file.exists():
            node_content = f'''"""
{agent.replace('_', ' ').title()} Node
"""

class {agent.replace('_', ' ').title().replace(' ', '')}Node:
    """{agent} node implementation"""

    def __init__(self):
        self.name = "{agent}"

    def process(self, request):
        """Process request"""
        pass

# Main class for compatibility
{agent.replace('_', ' ').title().replace(' ', '')} = {agent.replace('_', ' ').title().replace(' ', '')}Node
'''
            with open(node_file, "w", encoding="utf-8") as f:
                f.write(node_content)
            print(f"✓ Created: {agent}/node.py")

        # 创建prompt.py
        prompt_file = agent_dir / "prompt.py"
        if not prompt_file.exists():
            prompt_content = f'''"""
{agent} Prompts
"""

# System prompt
SYSTEM_PROMPT = """You are a helpful AI assistant."""

# Task prompt
TASK_PROMPT = """Please process the following request: {{request}}"""
'''
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt_content)
            print(f"✓ Created: {agent}/prompt.py")

        # 创建tools.py
        tools_file = agent_dir / "tools.py"
        if not tools_file.exists():
            tools_content = f'''"""
{agent} Tools
"""

class {agent.replace('_', ' ').title().replace(' ', '')}Tools:
    """Tools for {agent}"""

    @staticmethod
    def get_tools():
        """Get available tools"""
        return []

    @staticmethod
    def get_tool(tool_name):
        """Get specific tool"""
        return None
'''
            with open(tools_file, "w", encoding="utf-8") as f:
                f.write(tools_content)
            print(f"✓ Created: {agent}/tools.py")

        # 创建__init__.py
        init_file = agent_dir / "__init__.py"
        if not init_file.exists():
            init_content = f'''"""
{agent} module
"""

from .node import *
from .prompt import *
from .tools import *

__all__ = [
    "{agent.replace('_', ' ').title().replace(' ', '')}",
    "get_tools"
]
'''
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(init_content)
            print(f"✓ Created: {agent}/__init__.py")

    # 创建主__init__.py
    main_init = base_dir / "__init__.py"
    if not main_init.exists():
        with open(main_init, "w", encoding="utf-8") as f:
            f.write('''"""
Standardized Agents Module
"""

# Import all agents
from . import intent_router
from . import chat_agent
from . import calculation_agent
from . import policy_analyzer
from . import policy_comparator
from . import answer_generator
from . import session_manager
from . import policy_retriever
from . import vector_retriever
from . import answer_verifier

__all__ = [
    "intent_router",
    "chat_agent",
    "calculation_agent",
    "policy_analyzer",
    "policy_comparator",
    "answer_generator",
    "session_manager",
    "policy_retriever",
    "vector_retriever",
    "answer_verifier"
]

def get_all_agents():
    """Get all available agents"""
    return __all__
''')
        print(f"\n✓ Created: __init__.py (main)")

    print(f"\n✅ Agent结构创建完成！")

def copy_existing_agents():
    """复制现有的agent文件到新结构"""
    print("\n=== 复制现有Agent文件 ===\n")

    base_dir = Path("/data/temp33/gove/agents")
    new_dir = Path("/data/temp33/gove/agents_new")

    # 复制映射
    copy_map = {
        "router/intent_router.py": "intent_router/node.py",
        "specialized/chat_agent.py": "chat_agent/node.py",
        "specialized/calculation_agent.py": "calculation_agent/node.py",
        "analysis/policy_analyzer.py": "policy_analyzer/node.py",
        "analysis/policy_comparator.py": "policy_comparator/node.py",
        "generation/answer_generator.py": "answer_generator/node.py",
        "coordination/session_manager.py": "session_manager/node.py",
        "retrieval/policy_retriever.py": "policy_retriever/node.py",
        "retrieval/vector_retriever.py": "vector_retriever/node.py",
        "verification/answer_verifier.py": "answer_verifier/node.py",
    }

    for old_path, new_path in copy_map.items():
        old_file = base_dir / old_path
        new_file = new_dir / new_path

        if old_file.exists():
            new_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_file, new_file)
            print(f"✓ Copied: {old_path} → {new_path}")

if __name__ == "__main__":
    # 创建标准结构
    create_agent_structure()

    # 复制现有文件
    copy_existing_agents()

    print("\n✅ 所有操作完成！")