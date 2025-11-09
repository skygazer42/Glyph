"""
AutoGen配置管理类
"""
from typing import Dict, Any, List, Optional
from config import settings


# 模型配置
MODEL_CONFIG = {
    "model": settings.model.llm_model_name,
    "base_url": settings.model.llm_base_url,
    "api_key": settings.model.llm_api_key,
    "temperature": settings.model.llm_temperature,
    "max_tokens": 4096,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
}

# 流式配置
STREAMING_CONFIG = {
    "enable_typing_effect": True,
    "typing_speed": 30,
    "enable_markdown": True,
}

# Agent配置
AGENT_CONFIGS = {
    "policy_assistant": {
        "name": "PolicyAssistant",
        "description": "政策问答助手，能够回答各种政策相关问题",
        "system_message": "你是一个专业的政策咨询助手，名叫小政。你能够回答用户关于政策的各种问题。请用简洁、专业的语言回答。",
    },
    "dsl_generator": {
        "name": "DSLGenerator",
        "description": "DSL生成助手，能够从文本生成政策DSL",
        "system_message": "你是DSL生成助手，擅长将政策文本转换为结构化的DSL格式。",
    },
    "knowledge_expert": {
        "name": "KnowledgeExpert",
        "description": "知识库专家，能够搜索和管理政策知识库",
        "system_message": "你是知识库专家，擅长搜索和分析政策文档。",
    },
}


class AutoGenConfig:
    """AutoGen配置管理类"""

    @staticmethod
    def get_base_config() -> Dict[str, Any]:
        """获取AutoGen基础配置"""
        return {
            "enabled": settings.autogen.enabled,
            "cache_enabled": settings.autogen.cache_enabled,
            "cache_duration": settings.autogen.cache_duration,
            "max_rounds": settings.autogen.max_rounds,
            "timeout": settings.autogen.timeout,
            "model_config": MODEL_CONFIG,
            "streaming_config": STREAMING_CONFIG,
        }

    @staticmethod
    def get_agent_configs() -> Dict[str, Dict[str, Any]]:
        """获取智能体配置"""
        return AGENT_CONFIGS

    @staticmethod
    def get_model_client_config() -> Dict[str, Any]:
        """获取模型客户端配置"""
        return {
            "model": settings.model.llm_model_name,
            "api_key": settings.model.llm_api_key,
            "base_url": settings.model.llm_base_url,
            "max_tokens": MODEL_CONFIG["max_tokens"],
            "temperature": settings.model.llm_temperature,
            "top_p": MODEL_CONFIG.get("top_p", 1.0),
            "frequency_penalty": MODEL_CONFIG.get("frequency_penalty", 0.0),
            "presence_penalty": MODEL_CONFIG.get("presence_penalty", 0.0),
        }

    @staticmethod
    def get_performance_config() -> Dict[str, Any]:
        """获取性能配置"""
        return {
            "parallel_execution": True,
            "max_concurrent_agents": 3,
            "agent_timeout": 60,
            "team_timeout": settings.autogen.timeout,
            "memory_limit": "1GB",
        }

    @staticmethod
    def get_monitoring_config() -> Dict[str, Any]:
        """获取监控配置"""
        return {
            "enable_metrics": settings.autogen.enable_metrics,
            "track_performance": True,
            "track_costs": True,
            "log_conversations": True,
            "export_format": "json",
        }

    @staticmethod
    def validate_config() -> Dict[str, bool]:
        """验证配置有效性"""
        validation_results = {
            "api_key_valid": bool(settings.model.llm_api_key),
            "agents_configured": len(AGENT_CONFIGS) > 0,
            "streaming_enabled": STREAMING_CONFIG.get("enable_typing_effect", False),
            "model_configured": bool(settings.model.llm_model_name),
        }

        return validation_results

    @staticmethod
    def get_environment_specific_config() -> Dict[str, Any]:
        """获取环境特定配置"""
        if settings.autogen.is_development:
            return {
                "debug_mode": True,
                "verbose_logging": True,
                "enable_profiling": True,
                "mock_responses": False,
            }
        elif settings.autogen.is_production:
            return {
                "debug_mode": False,
                "verbose_logging": False,
                "enable_profiling": False,
                "mock_responses": False,
                "optimize_performance": True,
            }
        else:  # testing
            return {
                "debug_mode": True,
                "verbose_logging": True,
                "enable_profiling": False,
                "mock_responses": True,
            }

    @staticmethod
    def get_agent_specific_config(agent_type: str) -> Dict[str, Any]:
        """获取特定智能体的配置"""
        base_config = AGENT_CONFIGS.get(agent_type, AGENT_CONFIGS["policy_assistant"])

        # 合并全局配置
        config = {
            **base_config,
            "model_config": AutoGenConfig.get_model_client_config(),
            "performance": {
                "timeout": 60,
                "max_retries": 3,
                "memory_limit": "256MB",
            },
        }

        return config
