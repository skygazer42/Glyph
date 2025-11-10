"""
提示词管理器 - 统一管理所有智能体的提示词
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from .templates import (
    IntentPrompts,
    ChatPrompts,
    PolicyPrompts,
    CalculationPrompts,
    ComparisonPrompts,
    AnalysisPrompts,
    GenerationPrompts
)


@dataclass
class PromptConfig:
    """提示词配置"""
    name: str
    content: str
    description: str
    version: str = "1.0"
    created_at: str = None
    updated_at: str = None
    tags: list = None
    metadata: dict = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class PromptManager:
    """提示词管理器"""

    def __init__(self, prompt_dir: Optional[str] = None):
        """
        初始化提示词管理器

        Args:
            prompt_dir: 提示词文件存储目录
        """
        self.logger = logging.getLogger(__name__)

        # 设置提示词目录
        if prompt_dir is None:
            prompt_dir = Path(__file__).parent
        else:
            prompt_dir = Path(prompt_dir)

        self.prompt_dir = prompt_dir
        self.cache_file = prompt_dir / "prompt_cache.json"

        # 加载所有提示词
        self.prompts = self._load_all_prompts()

        # 初始化模板类
        self.templates = {
            "intent": IntentPrompts(),
            "chat": ChatPrompts(),
            "policy": PolicyPrompts(),
            "calculation": CalculationPrompts(),
            "comparison": ComparisonPrompts(),
            "analysis": AnalysisPrompts(),
            "generation": GenerationPrompts()
        }

        self.logger.info(f"PromptManager initialized with {len(self.prompts)} prompts")

    def _load_all_prompts(self) -> Dict[str, PromptConfig]:
        """加载所有提示词"""
        prompts = {}

        # 尝试从缓存加载
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, config_data in data.items():
                        prompts[name] = PromptConfig(**config_data)
                self.logger.info("Loaded prompts from cache")
                return prompts
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")

        # 从模板加载
        return self._load_from_templates()

    def _load_from_templates(self) -> Dict[str, PromptConfig]:
        """从模板类加载提示词"""
        prompts = {}

        # 意图识别提示词
        intent_prompts = {
            "intent_classification": IntentPrompts.CLASSIFICATION,
            "entity_extraction": IntentPrompts.ENTITY_EXTRACTION,
            "chain_selection": IntentPrompts.CHAIN_SELECTION
        }

        # 聊天提示词
        chat_prompts = {
            "greeting": ChatPrompts.GREETING,
            "casual_chat": ChatPrompts.CASUAL_CHAT,
            "farewell": ChatPrompts.FAREWELL
        }

        # 政策提示词
        policy_prompts = {
            "retrieval": PolicyPrompts.RETRIEVAL,
            "analysis": PolicyPrompts.ANALYSIS,
            "eligibility_check": PolicyPrompts.ELIGIBILITY_CHECK,
            "deadline_query": PolicyPrompts.DEADLINE_QUERY
        }

        # 计算提示词
        calculation_prompts = {
            "subsidy_calculation": CalculationPrompts.SUBSIDY_CALCULATION,
            "rule_extraction": CalculationPrompts.RULE_EXTRACTION,
            "amount_validation": CalculationPrompts.AMOUNT_VALIDATION
        }

        # 比较提示词
        comparison_prompts = {
            "policy_comparison": ComparisonPrompts.POLICY_COMPARISON,
            "feature_comparison": ComparisonPrompts.FEATURE_COMPARISON,
            "similarity_analysis": ComparisonPrompts.SIMILARITY_ANALYSIS
        }

        # 分析提示词
        analysis_prompts = {
            "content_analysis": AnalysisPrompts.CONTENT_ANALYSIS,
            "structure_extraction": AnalysisPrompts.STRUCTURE_EXTRACTION,
            "key_info_extraction": AnalysisPrompts.KEY_INFO_EXTRACTION
        }

        # 生成提示词
        generation_prompts = {
            "answer_generation": GenerationPrompts.ANSWER_GENERATION,
            "summary_generation": GenerationPrompts.SUMMARY_GENERATION,
            "step_by_step": GenerationPrompts.STEP_BY_STEP
        }

        # 合并所有提示词
        all_prompt_groups = {
            "intent": intent_prompts,
            "chat": chat_prompts,
            "policy": policy_prompts,
            "calculation": calculation_prompts,
            "comparison": comparison_prompts,
            "analysis": analysis_prompts,
            "generation": generation_prompts
        }

        for category, prompts in all_prompt_groups.items():
            for name, content in prompts.items():
                full_name = f"{category}.{name}"
                prompts[full_name] = PromptConfig(
                    name=full_name,
                    content=content,
                    description=f"{category} prompt for {name}",
                    tags=[category]
                )

        # 保存到缓存
        self._save_cache(prompts)

        return prompts

    def _save_cache(self, prompts: Dict[str, PromptConfig]):
        """保存提示词到缓存"""
        try:
            data = {name: asdict(config) for name, config in prompts.items()}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("Saved prompts to cache")
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")

    def get_prompt(self, name: str, **kwargs) -> str:
        """
        获取提示词

        Args:
            name: 提示词名称（格式：category.prompt_name）
            **kwargs: 格式化参数

        Returns:
            格式化后的提示词
        """
        if name not in self.prompts:
            self.logger.warning(f"Prompt not found: {name}")
            return ""

        prompt_config = self.prompts[name]
        content = prompt_config.content

        # 格式化提示词
        if kwargs:
            try:
                content = content.format(**kwargs)
            except KeyError as e:
                self.logger.error(f"Missing format parameter: {e}")

        return content

    def get_prompt_config(self, name: str) -> Optional[PromptConfig]:
        """获取提示词配置"""
        return self.prompts.get(name)

    def list_prompts(self, category: Optional[str] = None, tags: Optional[list] = None) -> Dict[str, PromptConfig]:
        """
        列出提示词

        Args:
            category: 分类筛选
            tags: 标签筛选

        Returns:
            符合条件的提示词列表
        """
        result = {}

        for name, config in self.prompts.items():
            # 分类筛选
            if category and not name.startswith(f"{category}."):
                continue

            # 标签筛选
            if tags and not any(tag in config.tags for tag in tags):
                continue

            result[name] = config

        return result

    def add_prompt(self, config: PromptConfig) -> bool:
        """添加新的提示词"""
        try:
            config.updated_at = datetime.now().isoformat()
            self.prompts[config.name] = config
            self._save_cache(self.prompts)
            self.logger.info(f"Added prompt: {config.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add prompt: {e}")
            return False

    def update_prompt(self, name: str, content: str, description: Optional[str] = None) -> bool:
        """更新提示词"""
        if name not in self.prompts:
            self.logger.error(f"Prompt not found: {name}")
            return False

        try:
            config = self.prompts[name]
            config.content = content
            config.updated_at = datetime.now().isoformat()

            if description:
                config.description = description

            self._save_cache(self.prompts)
            self.logger.info(f"Updated prompt: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update prompt: {e}")
            return False

    def delete_prompt(self, name: str) -> bool:
        """删除提示词"""
        if name not in self.prompts:
            self.logger.error(f"Prompt not found: {name}")
            return False

        try:
            del self.prompts[name]
            self._save_cache(self.prompts)
            self.logger.info(f"Deleted prompt: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete prompt: {e}")
            return False

    def export_prompts(self, file_path: str, category: Optional[str] = None):
        """导出提示词到文件"""
        prompts = self.list_prompts(category=category)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_prompts": len(prompts),
            "prompts": {name: asdict(config) for name, config in prompts.items()}
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Exported {len(prompts)} prompts to {file_path}")

    def import_prompts(self, file_path: str, overwrite: bool = False) -> int:
        """从文件导入提示词"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        imported_count = 0
        for name, config_data in data.get("prompts", {}).items():
            if name in self.prompts and not overwrite:
                continue

            config = PromptConfig(**config_data)
            self.prompts[name] = config
            imported_count += 1

        if imported_count > 0:
            self._save_cache(self.prompts)

        self.logger.info(f"Imported {imported_count} prompts from {file_path}")
        return imported_count

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_prompts": len(self.prompts),
            "categories": {},
            "tags": {},
            "recent_updates": []
        }

        # 统计分类
        for name in self.prompts:
            category = name.split(".")[0]
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

        # 统计标签
        for config in self.prompts.values():
            for tag in config.tags:
                stats["tags"][tag] = stats["tags"].get(tag, 0) + 1

        # 最近更新
        recent = sorted(
            self.prompts.items(),
            key=lambda x: x[1].updated_at,
            reverse=True
        )[:5]

        stats["recent_updates"] = [
            {"name": name, "updated_at": config.updated_at}
            for name, config in recent
        ]

        return stats


# 全局提示词管理器实例
_global_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """获取全局提示词管理器实例"""
    global _global_prompt_manager
    if _global_prompt_manager is None:
        _global_prompt_manager = PromptManager()
    return _global_prompt_manager


def get_prompt(name: str, **kwargs) -> str:
    """快捷方法：获取提示词"""
    return get_prompt_manager().get_prompt(name, **kwargs)