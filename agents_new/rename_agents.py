#!/usr/bin/env python3
"""
Agent重命名脚本 - 将agent文件重命名为标准的node.py
"""

import os
import shutil
from pathlib import Path

# 定义重命名映射
rename_map = {
    # Router
    "router/intent_router.py": "intent_router/node.py",

    # Specialized agents
    "specialized/chat_agent.py": "chat_agent/node.py",
    "specialized/calculation_agent.py": "calculation_agent/node.py",

    # Analysis agents
    "analysis/policy_analyzer.py": "policy_analyzer/node.py",
    "analysis/policy_comparator.py": "policy_comparator/node.py",

    # Generation agents
    "generation/answer_generator.py": "answer_generator/node.py",
    "generation/question_understander.py": "question_understander/node.py",

    # Coordination agents
    "coordination/session_manager.py": "session_manager/node.py",
    "coordination/coordinator.py": "coordinator/node.py",

    # Retrieval agents
    "retrieval/policy_retriever.py": "policy_retriever/node.py",
    "retrieval/vector_retriever.py": "vector_retriever/node.py",
    "retrieval/query_analyzer.py": "query_analyzer/node.py",
    "retrieval/embedding_manager.py": "embedding_manager/node.py",

    # Verification agents
    "verification/answer_verifier.py": "answer_verifier/node.py",

    # Enhanced agents
    "enhanced/intent_router_enhanced.py": "enhanced_intent_router/node.py",
    "enhanced/query_analyzer.py": "enhanced_query_analyzer/node.py",

    # ChatDB agents
    "chatdb/base_agent.py": "chatdb_base/node.py",
    "chatdb/factory.py": "chatdb_base/factory.py"
}

# Prompt模板内容
prompt_templates = {
    "intent_router": """# Intent Router Prompts
INTENT_CLASSIFICATION = \"\"\"You are an intent classification expert...\"\"\"
""",

    "chat_agent": """# Chat Agent Prompts
GREETING_RESPONSE = \"\"\"You are a friendly assistant...\"\"\"
CASUAL_CHAT = \"\"\"You are having a casual conversation...\"\"\"
""",

    "calculation_agent": """# Calculation Agent Prompts
SUBSIDY_CALCULATION = \"\"\"You are a calculation expert...\"\"\"
""",

    "policy_analyzer": """# Policy Analyzer Prompts
POLICY_ANALYSIS = \"\"\"You are a policy analysis expert...\"\"\"
""",

    "policy_comparator": """# Policy Comparator Prompts
POLICY_COMPARISON = \"\"\"You are a policy comparison expert...\"\"\"
""",

    "answer_generator": """# Answer Generator Prompts
ANSWER_GENERATION = \"\"\"You are an answer generation expert...\"\"\"
""",

    "session_manager": """# Session Manager Prompts
SESSION_INIT = \"\"\"Initialize session with context...\"\"\"
""",

    "policy_retriever": """# Policy Retriever Prompts
RETRIEVAL_QUERY = \"\"\"Generate optimal search queries...\"\"\"
""",

    "answer_verifier": """# Answer Verifier Prompts
VERIFICATION_CHECK = \"\"\"You are an answer verification expert...\"\"\"
"""
}

def main():
    """执行重命名操作"""
    base_dir = Path("/data/temp33/gove/agents")
    new_dir = Path("/data/temp33/gove/agents_new")

    print("=== Agent文件重命名 ===\n")

    # 1. 重命名agent文件
    for old_path, new_path in rename_map.items():
        old_file = base_dir / old_path
        new_file = new_dir / new_path

        if old_file.exists():
            # 创建目标目录
            new_file.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(old_file, new_file)
            print(f"✓ {old_path} → {new_path}")
        else:
            print(f"✗ {old_path} (文件不存在)")

    # 2. 创建prompt.py文件
    print("\n=== 创建Prompt文件 ===\n")
    for agent, prompt_content in prompt_templates.items():
        prompt_file = new_dir / agent / "prompt.py"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_content)
        print(f"✓ Created: {agent}/prompt.py")

    # 3. 创建tools.py文件
    print("\n=== 创建Tools文件 ===\n")
    for agent_dir in new_dir.iterdir():
        if agent_dir.is_dir():
            tools_file = agent_dir / "tools.py"
            agent_name = agent_dir.name
class_name = agent_name.title().replace("_", "")

tools_content = f'''# {agent_name} Tools

class {class_name}Tools:
    """Tools for {agent_name} agent"""

    @staticmethod
    def get_tools():
        """Get available tools"""
        return []
'''
            with open(tools_file, "w", encoding="utf-8") as f:
                f.write(tools_content)
            print(f"✓ Created: {agent_dir.name}/tools.py")

    # 4. 创建__init__.py文件
    print("\n=== 创建__init__.py文件 ===\n")
    for agent_dir in new_dir.iterdir():
        if agent_dir.is_dir():
            init_file = agent_dir / "__init__.py"
            agent_name = agent_dir.name
class_name = agent_name.title().replace("_", "")

init_content = f'''"""{agent_name} module"""

from .node import *
from .prompt import *
from .tools import *

__all__ = [
    "get_available_tools"
]

def get_available_tools():
    """Get all available tools for this agent"""
    from .tools import {class_name}Tools
    return {class_name}Tools.get_tools()
'''
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(init_content)
            print(f"✓ Created: {agent_dir.name}/__init__.py")

    # 5. 创建主__init__.py
    main_init = new_dir / "__init__.py"
    with open(main_init, "w", encoding="utf-8") as f:
        f.write('''"""Standardized Agents Module"""

# Import all agents
from . import intent_router
from . import chat_agent
from . import calculation_agent
from . import policy_analyzer
from . import policy_comparator
from . import answer_generator
from . import session_manager
from . import policy_retriever
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
    "answer_verifier"
]
''')
    print(f"\n✓ Created: __init__.py (main)")

    print(f"\n✅ 重命名完成！新结构位于: {new_dir}")

if __name__ == "__main__":
    main()