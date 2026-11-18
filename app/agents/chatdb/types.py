"""
智能体类型定义和常量
"""
from enum import Enum
from typing import Dict


class AgentTypes(Enum):
    """智能体类型枚举"""
    SCHEMA_RETRIEVER = "schema_retriever"
    QUERY_ANALYZER = "query_analyzer"
    SQL_GENERATOR = "sql_generator"
    SQL_EXPLAINER = "sql_explainer"
    SQL_EXECUTOR = "sql_executor"
    VISUALIZATION_RECOMMENDER = "visualization_recommender"


class TopicTypes(Enum):
    """主题类型枚举"""
    SCHEMA_RETRIEVER = "schema_retriever"
    QUERY_ANALYZER = "query_analyzer"
    SQL_GENERATOR = "sql_generator"
    SQL_EXPLAINER = "sql_explainer"
    SQL_EXECUTOR = "sql_executor"
    VISUALIZATION_RECOMMENDER = "visualization_recommender"
    STREAM_OUTPUT = "stream_output"


class DatabaseTypes(Enum):
    """数据库类型枚举"""
    MYSQL = "MySQL"
    POSTGRESQL = "PostgreSQL"
    SQLITE = "SQLite"
    ORACLE = "Oracle"
    SQL_SERVER = "SQL Server"


# 智能体名称映射
AGENT_NAMES: Dict[str, str] = {
    AgentTypes.SCHEMA_RETRIEVER.value: "表结构检索智能体",
    AgentTypes.QUERY_ANALYZER.value: "查询分析智能体",
    AgentTypes.SQL_GENERATOR.value: "SQL生成智能体",
    AgentTypes.SQL_EXPLAINER.value: "SQL解释智能体",
    AgentTypes.SQL_EXECUTOR.value: "SQL执行智能体",
    AgentTypes.VISUALIZATION_RECOMMENDER.value: "可视化推荐智能体"
}

# 默认数据库类型
DEFAULT_DB_TYPE = DatabaseTypes.MYSQL.value
