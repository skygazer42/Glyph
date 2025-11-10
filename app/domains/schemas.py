"""
领域Schema定义 - 为不同政策类型定义专用的数据结构
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

# ==================== 汽车补贴 Schema ====================

class PowertrainType(str, Enum):
    """动力类型"""
    NEV = "NEV"  # 新能源
    ICE = "ICE"  # 燃油车

class TimeWindow(BaseModel):
    """时间窗口"""
    start: str
    end: str

class AutoSubsidyTier(BaseModel):
    """汽车补贴分档"""
    powertrain: PowertrainType
    min_ex_tax: float = Field(description="最低不含税价(元)")
    max_ex_tax: Optional[float] = Field(None, description="最高不含税价(元),None表示无上限")
    open_interval: str = Field(default="[min, max)", description="区间类型")
    subsidy: float = Field(description="补贴金额(元)")

class AutoSubsidySchema(BaseModel):
    """汽车补贴政策Schema"""
    rule_id: str = Field(pattern=r"^Rule_\w+_Car_\d{4}$")
    name: str
    version: str = "1.0"

    policy_source: Dict[str, Any]

    # 三个时间窗口
    windows: Dict[str, Any] = Field(description="购车/申报/修改三个时间窗口")

    # 预算配置
    budget: Dict[str, Any] = Field(description="总预算和分配方式")

    # 价格基准
    price_basis: str = Field(default="ex_tax", description="价格基准(不含税)")

    # 资格条件
    eligibility: Dict[str, Any]

    # 分档匹配
    matching: Dict[str, Any] = Field(description="动力类型定义和分档表")

    # 限制条件
    limits: Dict[str, Any]

    # 输出配置
    output: Dict[str, Any]

    notes: Optional[str] = None

# ==================== 家电补贴 Schema ====================

class ApplianceCategory(str, Enum):
    """家电类别"""
    空调 = "空调"
    冰箱 = "冰箱"
    洗衣机 = "洗衣机"
    热水器 = "热水器"
    电视 = "电视"

class ApplianceSubsidySchema(BaseModel):
    """家电补贴政策Schema"""
    rule_id: str = Field(pattern=r"^Rule_\w+_Appliance_\d{4}$")
    name: str
    version: str = "1.0"

    policy_source: Dict[str, Any]
    valid_period: Dict[str, Any]

    # 能效补贴率
    efficiency_rates: Dict[str, float] = Field(
        description="能效等级对应补贴率",
        example={"2级及以上": 0.15, "1级额外": 0.05}
    )

    # 类别限额
    category_limits: Dict[str, Any]

    # 单品上限
    per_item_cap: float

    # 计算逻辑
    calc: Dict[str, Any]

    output: Dict[str, Any]

# ==================== 消费券 Schema ====================

class CouponType(str, Enum):
    """消费券类型"""
    零售 = "retail"
    餐饮 = "dining"

class CouponTier(BaseModel):
    """消费券满减档位"""
    threshold: float = Field(description="满足金额(元)")
    discount: float = Field(description="减免金额(元)")
    type: CouponType

class ConsumerCouponSchema(BaseModel):
    """消费券政策Schema"""
    rule_id: str = Field(pattern=r"^Rule_\w+_Coupon_\d{4}$")
    name: str
    version: str = "1.0"

    policy_source: Dict[str, Any]
    valid_period: Dict[str, Any]

    # 券种配置
    coupon_types: List[CouponType]

    # 满减档位
    tiers: List[CouponTier]

    # 发放规则
    distribution: Dict[str, Any] = Field(
        description="发放规则",
        example={"method": "lottery", "quota_per_person": 5}
    )

    # 使用限制
    usage_limits: Dict[str, Any]

    output: Dict[str, Any]

# ==================== 以旧换新 Schema ====================

class TradeInSchema(BaseModel):
    """以旧换新政策Schema"""
    rule_id: str = Field(pattern=r"^Rule_\w+_TradeIn_\d{4}$")
    name: str
    version: str = "1.0"

    policy_source: Dict[str, Any]
    valid_period: Dict[str, Any]

    # 产品类别
    product_categories: List[str]

    # 旧品回收标准
    trade_in_criteria: Dict[str, Any] = Field(
        description="旧品回收标准",
        example={"min_years": 5, "condition": "working"}
    )

    # 新品补贴率
    subsidy_rates: Dict[str, float]

    # 补贴上限
    caps: Dict[str, float]

    # 叠加规则
    stacking_rules: Dict[str, bool] = Field(
        description="是否可叠加其他优惠",
        example={"with_energy_subsidy": True}
    )

    output: Dict[str, Any]

# ==================== 保险补贴 Schema ====================

class InsuranceSubsidySchema(BaseModel):
    """保险补贴政策Schema"""
    rule_id: str = Field(pattern=r"^Rule_\w+_Insurance_\d{4}$")
    name: str
    version: str = "1.0"

    policy_source: Dict[str, Any]
    valid_period: Dict[str, Any]

    # 保险金额分档
    insurance_tiers: List[Dict[str, Any]]

    # 补贴计算
    calc: Dict[str, Any]

    output: Dict[str, Any]

# ==================== Schema 注册表 ====================

SCHEMA_REGISTRY = {
    "汽车补贴": AutoSubsidySchema,
    "家电补贴": ApplianceSubsidySchema,
    "消费券": ConsumerCouponSchema,
    "以旧换新": TradeInSchema,
    "保险补贴": InsuranceSubsidySchema,
}

def get_schema_for_domain(domain: str):
    """根据领域获取对应的Schema"""
    return SCHEMA_REGISTRY.get(domain)