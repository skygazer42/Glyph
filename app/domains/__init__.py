"""
领域知识管理模块

此模块负责：
- 领域识别和关键词匹配
- 领域配置和模板管理
- 术语标准化
- 数据结构定义
"""

from .manager import DomainConfig, domain_config
from .schemas import (
    # 枚举类型
    PowertrainType,
    TimeWindow,
    ApplianceCategory,
    CouponType,

    # Schema类
    AutoSubsidySchema,
    ApplianceSubsidySchema,
    ConsumerCouponSchema,
    TradeInSchema,
    InsuranceSubsidySchema,

    # 工具函数
    SCHEMA_REGISTRY,
    get_schema_for_domain,
)

__all__ = [
    # 领域配置管理
    'DomainConfig',
    'domain_config',

    # 枚举类型
    'PowertrainType',
    'TimeWindow',
    'ApplianceCategory',
    'CouponType',

    # Schema类
    'AutoSubsidySchema',
    'ApplianceSubsidySchema',
    'ConsumerCouponSchema',
    'TradeInSchema',
    'InsuranceSubsidySchema',

    # 工具
    'SCHEMA_REGISTRY',
    'get_schema_for_domain',
]
