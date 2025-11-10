"""
领域配置中心 - 管理不同政策领域的提示词和模板
"""

from pathlib import Path
from typing import Dict, List, Any
import json
import yaml

from app.prompts.domain_catalog import get_domain_prompt

class DomainConfig:
    """领域配置管理器"""

    def __init__(self):
        self.domains = {
            "汽车补贴": {
                "detect_keywords": ["汽车", "购车", "新能源", "燃油车", "发票不含税", "乘用车", "绿牌"],
                "prompt_key": "auto_subsidy",
                "dsl_template": "templates/auto_subsidy.yaml.j2",
                "schema": "AutoSubsidySchema",
                "examples": ["汽车消费补贴活动公告"],
                "normalization": {
                    "NEV": ["新能源", "纯电动", "插电式混合动力", "插混", "增程式", "燃料电池", "绿色号牌"],
                    "ICE": ["燃油车", "汽油车", "柴油车", "传统动力"],
                    "ex_tax": ["不含税价", "不含税金额", "裸车价"],
                    "24:00": "次日00:00"  # 时间边界处理
                }
            },

            "家电补贴": {
                "detect_keywords": ["家电", "能效", "水效", "空调", "冰箱", "洗衣机", "热水器", "电视"],
                "prompt_key": "appliance_subsidy",
                "dsl_template": "templates/appliance_subsidy.yaml.j2",
                "schema": "ApplianceSubsidySchema",
                "examples": ["家电消费补贴实施细则"],
                "normalization": {
                    "energy_level_1": ["一级能效", "1级能效", "能效1级"],
                    "energy_level_2": ["二级能效", "2级能效", "能效2级"],
                    "per_item_cap": ["单件上限", "每件上限", "单品封顶"]
                }
            },

            "消费券": {
                "detect_keywords": ["消费券", "满减", "满元减", "零售券", "餐饮券", "泉城购"],
                "prompt_key": "consumer_coupon",
                "dsl_template": "templates/consumer_coupon.yaml.j2",
                "schema": "ConsumerCouponSchema",
                "examples": ["泉城购消费券发放活动公告"],
                "normalization": {
                    "retail": ["零售", "零售消费券"],
                    "dining": ["餐饮", "餐饮消费券"],
                    "threshold": ["满", "消费满", "满足金额"],
                    "discount": ["减", "减免", "优惠金额"]
                }
            },

            "以旧换新": {
                "detect_keywords": ["以旧换新", "旧品回收", "换新补贴", "旧机换新", "家电回收"],
                "prompt_key": "trade_in",
                "dsl_template": "templates/trade_in.yaml.j2",
                "schema": "TradeInSchema",
                "examples": ["家电以旧换新补贴实施细则"],
                "normalization": {
                    "trade_in": ["以旧换新", "换新", "回收换新"],
                    "old_device": ["旧机", "旧品", "旧家电", "回收品"],
                    "subsidy_rate": ["补贴比例", "补贴率", "返现比例"]
                }
            },

            "保险补贴": {
                "detect_keywords": ["保险", "首保", "商业险", "交强险", "车险补贴"],
                "prompt_key": "insurance_subsidy",
                "dsl_template": "templates/insurance_subsidy.yaml.j2",
                "schema": "InsuranceSubsidySchema",
                "examples": ["新车首保消费券活动公告"],
                "normalization": {
                    "commercial": ["商业保险", "商业险", "商险"],
                    "compulsory": ["交强险", "强制保险"],
                    "first_insurance": ["首保", "首次投保", "新车保险"]
                }
            }
        }

    def detect_domain(self, text: str) -> str:
        """
        根据文本内容自动检测政策领域

        Args:
            text: 政策文本

        Returns:
            检测到的领域名称，如果无法识别返回None.

        """
        # 统计各领域关键词匹配数
        scores = {}
        for domain, config in self.domains.items():
            score = sum(1 for keyword in config["detect_keywords"] if keyword in text)
            if score > 0:
                scores[domain] = score

        # 返回得分最高的领域
        if scores:
            return max(scores, key=scores.get)
        return None

    def get_domain_config(self, domain: str) -> Dict[str, Any]:
        """获取指定领域的配置"""
        return self.domains.get(domain)

    def normalize_term(self, domain: str, term: str) -> str:
        """
        术语标准化

        Args:
            domain: 领域名称
            term: 待标准化的术语

        Returns:
            标准化后的术语
        """
        config = self.get_domain_config(domain)
        if not config:
            return term

        normalization = config.get("normalization", {})

        # 查找term属于哪个标准术语
        for standard, variants in normalization.items():
            if isinstance(variants, list):
                if term in variants:
                    return standard
            elif term == variants:
                return standard

        return term

    def get_prompt_template(self, domain: str) -> str:
        """获取领域的提示词模板"""
        config = self.get_domain_config(domain)
        if not config:
            return None

        prompt_key = config.get("prompt_key")
        if prompt_key:
            template = get_domain_prompt(prompt_key)
            if template:
                return template

        template_path = Path(config.get("prompt_template", "")) if config.get("prompt_template") else None
        if template_path and template_path.exists():
            return template_path.read_text(encoding='utf-8')
        return None

    def get_dsl_template(self, domain: str) -> str:
        """获取领域的DSL模板"""
        config = self.get_domain_config(domain)
        if not config:
            return None

        template_path = Path(config["dsl_template"])
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        return None

    def list_domains(self) -> List[str]:
        """列出所有已配置的领域"""
        return list(self.domains.keys())

    def add_domain(self, name: str, config: Dict[str, Any]):
        """动态添加新领域"""
        self.domains[name] = config

    def save_config(self, path: str = "config/domains.yaml"):
        """保存配置到文件"""
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.domains, f, allow_unicode=True)

    def load_config(self, path: str = "config/domains.yaml"):
        """从文件加载配置"""
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.domains = yaml.safe_load(f)

# 全局实例
domain_config = DomainConfig()
