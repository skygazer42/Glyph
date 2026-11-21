"""
DSL 提取器模块（优化版）
使用项目配置中的 LLM 从政策文本中提取结构化信息并生成 DSL
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config.app_config import settings


class ExtractedInput(BaseModel):
    """政策提取结果中的输入声明，严格校验公共字段并保留领域扩展字段。"""

    model_config = ConfigDict(strict=True, extra="allow")
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    required: bool = True
    description: str | None = None


class ExtractedPolicySource(BaseModel):
    """可缺省的政策出处字段，未提取到的文号、标题或条款保留 None。"""

    model_config = ConfigDict(strict=True, extra="allow")
    doc_id: str | None = None
    title: str | None = None
    clause: str | None = None


class ExtractedValidity(BaseModel):
    """可缺省的起止日期，非空值须为年月日格式且开始不晚于结束。"""

    model_config = ConfigDict(strict=True, extra="allow")
    start: str | None = None
    end: str | None = None

    @field_validator("start", "end")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is not None:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        return value

    @model_validator(mode="after")
    def validate_order(self):
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("Policy start must not follow end")
        return self


class ExtractedPolicy(BaseModel):
    # Domains have distinct calculation sections; validate the shared external envelope here.
    """校验模型返回的共享政策外壳；领域计算字段作为扩展数据保留。"""

    model_config = ConfigDict(strict=True, extra="allow")
    rule_id: str | None = None
    inputs: list[ExtractedInput] = Field(default_factory=list)
    policy_source: ExtractedPolicySource = Field(default_factory=ExtractedPolicySource)
    valid_period: ExtractedValidity = Field(default_factory=ExtractedValidity)


logger = logging.getLogger(__name__)


class DSLExtractor:
    """使用 LLM 提取政策文本并生成 DSL"""

    def __init__(self, use_project_config: bool = True):
        """
        初始化 DSL 提取器

        Args:
            use_project_config: 是否使用项目配置，默认为 True
        """
        self.use_project_config = use_project_config
        self.settings = settings
        if use_project_config:
            logger.info("使用项目配置: LLM=%s", settings.model.llm_model_name)

    def extract(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        从文本中提取 DSL 结构

        Args:
            text: 政策文本
            metadata: 额外的元数据信息

        Returns:
            提取的 DSL 结构
        """
        # 调用 LLM
        if self.use_project_config:
            response = self._call_llm(self._build_prompt(text))
        else:
            response = self._extract_with_rules(text)

        # 解析响应
        dsl_data = self._parse_response(response, text, metadata)

        return dsl_data

    def _build_prompt(self, text: str) -> str:
        """构建 LLM 提示词"""
        # 先检测政策类型
        policy_type = self._detect_policy_type(text)

        if policy_type == 'appliance':
            return self._build_appliance_prompt(text)
        elif policy_type == 'auto':
            return self._build_auto_prompt(text)
        else:
            return self._build_coupon_prompt(text)


    @staticmethod
    def _detect_policy_type(text: str) -> str:
        """检测政策类型"""
        if any(keyword in text for keyword in ['家电', '以旧换新', '能效', '空调', '冰箱', '洗衣机']):
            return 'appliance'
        if any(keyword in text for keyword in ['汽车', '购车', '乘用车', '车辆', '发票']):
            return 'auto'
        return 'coupon'


    @staticmethod
    def _build_appliance_prompt(text: str) -> str:
        """构建家电补贴提示词"""
        prompt = f"""你是一名政策规则工程师，任务是将家电补贴政策文本提取为JSON格式。

请从以下政策文本中提取关键信息：

### 需要提取的字段：

**基本信息:**
1. rule_id: 规则ID（格式：Rule_[城市]_家电补贴_[年份]）
2. name: 规则简短名称
3. version: 版本号（默认 "1.0"）
4. policy_source: {{doc_id, title}}

**有效期:**
5. valid_period: {{start, end}} (YYYY-MM-DD格式)

**能效补贴率:**
6. efficiency_rates: 能效补贴率配置
   - base_rate: 基础补贴率（二级能效，如0.15表示15%）
   - level_1_bonus: 一级能效额外补贴（如0.05表示额外5%）
   - no_label_rate: 无能效标识补贴率（如0.10）

**类别限额:**
7. category_limits: 类别限制
   - per_category: 每个类别的限购数量，如 {{"空调": 3, "冰箱": 2, "其他": 1}}
   - total_items: 总限购数量（可选）

**单品补贴上限:**
8. per_item_cap: 单件商品最高补贴金额（数值，如2000）

**输入参数:**
9. inputs:
   - price (float, required): 商品销售价格
   - energy_level (integer, optional): 能效等级(1/2/null)
   - category (string, required): 家电类别

### 政策文本：
{text}

### 输出要求：
1. 严格返回 JSON 格式
2. 百分比转换为小数（如15%→0.15）
3. 金额为数值类型
4. 类别限额要提取每个类别的具体数量

### 输出 JSON：
"""
        return prompt

    @staticmethod
    def _build_auto_prompt(text: str) -> str:
        """构建汽车补贴提示词"""
        prompt = f"""你是一名政策规则工程师，任务是将汽车补贴政策文本提取为JSON格式。

请从以下政策文本中提取关键信息：

### 需要提取的字段：

**基本信息:**
1. rule_id, name, version, policy_source

**有效期:**
2. valid_period: {{start, end}}

**分档信息:**
3. tiers: 价格分档，每档包含:
   - powertrain: 动力类型 NEV 或 ICE，必须从原文提取
   - range: [最低价, 最高价] (最高价可以是null表示无上限)
   - subsidy: 该档位的补贴金额
   - name: 档位名称（可选）

**输入参数:**
4. inputs:
   - invoice_no_tax (float, required): 发票不含税价格
   - vehicle_type (string, required): 车辆类型

### 政策文本：
{text}

### 输出 JSON：
"""
        return prompt

    @staticmethod
    def _build_coupon_prompt(text: str) -> str:
        """构建消费券提示词"""
        prompt = f"""你是一名政策规则工程师，任务是将消费券政策文本提取为JSON格式。

请从以下政策文本中提取关键信息：

### 需要提取的字段：

**基本信息:**
1. rule_id: 规则ID（格式：Rule_[城市]_消费券_[年份]）
2. name: 规则简短名称
3. version: 版本号（默认 "1.0"）
4. policy_source: {{doc_id, title}}

**有效期:**
5. valid_period: {{start, end}} (YYYY-MM-DD格式)

**券种类型:**
6. coupon_types: ["AMOUNT"] 或 ["PERCENT"]

**分档信息:**
7. tiers: 分档列表，每个档位:
   - type: AMOUNT 或 PERCENT
   - threshold: 门槛金额
   - discount: 优惠金额或折扣比例
   - name: 档位名称
   - cap: 封顶金额（PERCENT类型可选）

**发放规则:**
8. distribution:
   - method: auto_claim/manual/code
   - total_quota: 总额度
   - quota_per_person: 每人限领数量

**使用限制:**
9. usage_limits:
   - valid_days: 有效天数
   - merchant_scope: 商户范围
   - product_scope: 商品范围
   - stacking: {{with_merchant_discount, with_other_coupons}}

**平台信息:**
10. platform:
   - claim_platform: 领取平台
   - payment_methods: 支付方式列表

**输入参数:**
11. inputs:
   - consumption_amount (float, required): 消费金额
   - coupon_type (string, required): 券种类型
   - claim_time (string, required): 使用时间
   - user_id (string, required): 用户ID
   - merchant_id (string, optional): 商户ID
   - product_id (string, optional): 商品ID
   - using_other_coupon (boolean, optional): 是否使用其他券
   - has_merchant_discount (boolean, optional): 是否叠加商户优惠

### 政策文本：
{text}

### 输出要求：
1. 严格返回 JSON 格式
2. 百分比转换为小数（如15%→0.15）
3. inputs中的type要准确

### 输出 JSON：
"""
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        with OpenAI(
            api_key=self.settings.model.llm_api_key,
            base_url=self.settings.model.llm_base_url,
        ) as client:
            response = client.chat.completions.create(
                model=self.settings.model.llm_model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的政策规则提取专家，擅长从政策文本中提取结构化信息。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1 if self.settings.model.llm_temperature is None else self.settings.model.llm_temperature,
                max_tokens=2000,
            )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response contains no text")
        return content

    def _extract_with_rules(self, text: str) -> str:
        """使用规则提取（不依赖 LLM）"""
        result: Dict[str, Any] = {
            "rule_id": "Rule_Template_Policy",
            "doc_id": None,
            "title": None,
            "clause": None,
            "valid_start": None,
            "valid_end": None,
            "inputs": [],
            "limits": {},
            "tiers": [],
            "calc": {},
            "conditions": [],
            "result": {},
            "output": {}  # 添加 output 字段
        }

        # 提取文档编号
        doc_id_pattern = r'[A-Za-z0-9\u4e00-\u9fa5]+[〔【\[][\d]+[〕】\]][\d]+号'
        doc_id_match = re.search(doc_id_pattern, text)
        if doc_id_match:
            result['doc_id'] = doc_id_match.group()

        # 提取标题
        title_pattern = r'[《]([^》]+)[》]|^(.{1,50}(?:实施细则|管理办法|通知|公告|方案|实施方案))'
        title_match = re.search(title_pattern, text, re.MULTILINE)
        if title_match:
            result['title'] = title_match.group(1) or title_match.group(2)

        # 提取时间
        date_pattern = r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})[日]?'
        dates = re.findall(date_pattern, text)
        if dates:
            if len(dates) >= 1:
                year, month, day = dates[0]
                result['valid_start'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            if len(dates) >= 2:
                year, month, day = dates[-1]
                result['valid_end'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        # 提取金额限制
        cap_pattern = r'[每单封顶上限不超过]+[为是]?(\d+(?:\.\d+)?)[元万]'
        cap_match = re.search(cap_pattern, text)
        if cap_match:
            cap_value = float(cap_match.group(1))
            if '万' in cap_match.group():
                cap_value *= 10000
            result['limits']['per_item_cap'] = cap_value

        # 提取补贴比例
        rate_patterns = [
            r'补贴[比例率]?[为是]?(\d+(?:\.\d+)?)[%％]',
            r'补贴销售价格的(\d+(?:\.\d+)?)[%％]',
            r'(\d+(?:\.\d+)?)[%％]的?补贴'
        ]

        for pattern in rate_patterns:
            rate_match = re.search(pattern, text)
            if rate_match:
                result['calc']['base_rate'] = float(rate_match.group(1)) / 100
                break

        # 提取分档信息
        tier_patterns = [
            r'(\d+(?:\.\d+)?)[万元]?[至到\-](\d+(?:\.\d+)?)[万元]?',
            r'满(\d+)[元]?[减送](\d+)[元]?'
        ]

        for pattern in tier_patterns:
            tier_matches = re.finditer(pattern, text)
            for match in tier_matches:
                low = float(match.group(1))
                high = float(match.group(2))
                if '万' in match.group():
                    low *= 10000
                    high *= 10000
                result['tiers'].append({
                    'range': [low, high],
                    'benefit': high if '减' in text else None
                })

        # 生成基本输入变量
        result['inputs'] = [
            {"name": "price", "type": "float", "required": True, "description": "商品价格"},
            {"name": "category", "type": "string", "required": True, "description": "商品类别"}
        ]

        # 检查是否有能效相关内容
        if '能效' in text or '等级' in text:
            result['inputs'].append(
                {"name": "energy_level", "type": "int", "required": False, "description": "能效等级"}
            )

        # 根据提取的信息改进 rule_id
        city = self._extract_city(text)
        policy_label = self._extract_policy_type(text)
        year = datetime.now().year
        result['rule_id'] = f"Rule_{city}_{policy_label}_{year}"
        result['name'] = result.get('title') or result['rule_id']
        result['version'] = '1.0'
        domain_hint = self._detect_policy_type(text)
        result['policy_type'] = domain_hint
        result['template_hint'] = domain_hint

        # 添加输出配置
        result['output'] = {
            'status': 'QUALIFIED',
            'final_result': '{{ calc.subsidy }}' if 'base_rate' in result.get('calc', {}) else '{{ result }}',
            'trace_template': '- 计算完成'
        }

        return json.dumps(result, ensure_ascii=False)

    def _parse_response(self, response: str, original_text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """解析 LLM 响应"""
        metadata = metadata or {}

        def normalize_date(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            digits = re.findall(r'\d+', value)
            if len(digits) >= 3:
                year, month, day = digits[:3]
                return f"{year}-{int(month):02d}-{int(day):02d}"
            return None

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match is None:
                raise ValueError("LLM响应未包含JSON对象") from None
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError as exc:
                raise ValueError("LLM响应格式错误") from exc
        if not isinstance(data, dict):
            raise ValueError("LLM响应必须是JSON对象")

        data = ExtractedPolicy.model_validate(data).model_dump(exclude_unset=True)

        # 补充缺失的字段
        if not data.get('rule_id'):
            # 生成规则 ID
            city = self._extract_city(original_text)
            policy_type = self._extract_policy_type(original_text)
            year = datetime.now().year
            data['rule_id'] = f"Rule_{city}_{policy_type}_{year}"

        # 检测政策类型并补充必要字段
        policy_type = self._detect_policy_type(original_text)
        if 'policy_type' not in data:
            data['policy_type'] = policy_type
        if 'template_hint' not in data:
            data['template_hint'] = policy_type

        if policy_type == 'appliance':
            # 家电补贴必要字段
            if 'efficiency_rates' not in data:
                extracted_rate = data.get('calc', {}).get('base_rate')
                if extracted_rate is None:
                    raise ValueError("Missing policy efficiency_rates.base_rate")
                data['efficiency_rates'] = {'base_rate': extracted_rate}
            if data['efficiency_rates'].get('base_rate') is None:
                raise ValueError("Missing policy efficiency_rates.base_rate")
            if data.get('per_item_cap') is None:
                extracted_cap = data.get('limits', {}).get('per_item_cap')
                if extracted_cap is None:
                    raise ValueError("Missing policy per_item_cap")
                data['per_item_cap'] = extracted_cap
            if 'category_limits' not in data:
                data['category_limits'] = {'per_category': {}, 'total_items': None}

            # 确保inputs正确
            if 'inputs' not in data or not data['inputs']:
                data['inputs'] = [
                    {'name': 'price', 'type': 'float', 'required': True, 'description': '商品销售价格'},
                    {'name': 'energy_level', 'type': 'integer', 'required': False, 'description': '能效等级(1/2/null)'},
                    {'name': 'category', 'type': 'string', 'required': True, 'description': '家电类别'}
                ]

        elif policy_type == 'coupon':
            # 消费券必要字段
            required_fields = ['coupon_types', 'tiers', 'distribution', 'usage_limits', 'platform']
            for field in required_fields:
                if field not in data:
                    if field == 'coupon_types':
                        data[field] = []
                    elif field == 'tiers':
                        data[field] = []
                    elif field == 'distribution':
                        data[field] = {}
                    elif field == 'usage_limits':
                        data[field] = {}
                    elif field == 'platform':
                        data[field] = {'claim_platform': None, 'payment_methods': []}

            # 确保inputs正确
            if 'inputs' not in data or not data['inputs']:
                data['inputs'] = [
                    {'name': 'consumption_amount', 'type': 'float', 'required': True},
                    {'name': 'coupon_type', 'type': 'string', 'required': True},
                    {'name': 'claim_time', 'type': 'string', 'required': True},
                    {'name': 'user_id', 'type': 'string', 'required': True}
                ]
            needs_tiers = not data.get('tiers') or any(
                isinstance(tier, dict) and 'discount' not in tier for tier in data.get('tiers', [])
            )
            if needs_tiers:
                parsed_tiers = self._extract_coupon_tiers(original_text)
                if parsed_tiers:
                    data['tiers'] = parsed_tiers
            if not data.get('coupon_types'):
                data['coupon_types'] = list(dict.fromkeys(tier['type'] for tier in data.get('tiers', [])))

        # 确保基本字段存在
        if 'policy_source' not in data:
            data['policy_source'] = {}
        if 'valid_period' not in data:
            data['valid_period'] = {}

        policy_source = data['policy_source']
        if metadata.get('doc_id') and not policy_source.get('doc_id'):
            policy_source['doc_id'] = metadata['doc_id']
        if metadata.get('title') and not policy_source.get('title'):
            policy_source['title'] = metadata['title']
        if metadata.get('clause') and not policy_source.get('clause'):
            policy_source['clause'] = metadata['clause']

        if not data.get('name'):
            data['name'] = policy_source.get('title') or data['rule_id']
        if not data.get('version'):
            data['version'] = metadata.get('version') or '1.0'

        valid_period = data['valid_period']
        meta_dates = metadata.get('dates') or []
        if meta_dates:
            start_hint = normalize_date(meta_dates[0])
            if start_hint and not valid_period.get('start'):
                valid_period['start'] = start_hint
            end_hint = normalize_date(meta_dates[-1])
            if end_hint and not valid_period.get('end'):
                valid_period['end'] = end_hint
        data['valid_period'] = ExtractedValidity.model_validate(valid_period).model_dump(exclude_unset=True)

        return data

    @staticmethod
    def _extract_city(text: str) -> str:
        """提取城市名称"""
        cities = ['常州', '溧阳', '南京', '苏州', '无锡', '镇江', '济南', '青岛', '烟台', '潍坊', '临沂', '淄博', '济宁', '泰安']
        for city in cities:
            if city in text:
                return city
        if any(district in text for district in ['天宁区', '钟楼区', '新北区', '武进区', '金坛区', '常州经开区', '常州经济开发区']):
            return '常州'
        return 'Unknown'

    @staticmethod
    def _extract_coupon_tiers(text: str) -> List[Dict[str, Any]]:
        """Parse patterns such as 满100减20 to build coupon tiers."""
        pattern = r'(?:满)?(\d+(?:\.\d+)?)\s*元?\s*(?:减|抵)(\d+(?:\.\d+)?)\s*元'
        tiers: List[Dict[str, Any]] = []
        seen = set()
        for match in re.finditer(pattern, text):
            threshold = float(match.group(1))
            discount = float(match.group(2))
            key = (threshold, discount)
            if key in seen:
                continue
            seen.add(key)
            name = None
            if threshold.is_integer() and discount.is_integer():
                name = f"满{int(threshold)}减{int(discount)}"
            tiers.append({
                "type": "AMOUNT",
                "threshold": threshold,
                "discount": discount,
                "name": name
            })
        return tiers


    @staticmethod
    def _extract_policy_type(text: str) -> str:
        """提取政策类型"""
        checks = [
            (['消费券', '代金券', '优惠券'], 'Consumption'),
            (['家电', '以旧换新', '能效', '空调', '冰箱'], 'Appliance'),
            (['汽车', '购车', '乘用车', '车辆', '新车'], 'Car'),
            (['消费', '零售', '餐饮', '促销'], 'Consumption'),
            (['以旧换新'], 'TradeIn'),
            (['补贴'], 'Subsidy'),
            (['优惠', '折扣'], 'Discount'),
        ]
        for keywords, label in checks:
            for keyword in keywords:
                if keyword in text:
                    return label
        return 'General'



    @staticmethod
    def validate_dsl(dsl_data: Dict[str, Any]) -> List[str]:
        """
        验证 DSL 数据的完整性和正确性

        Args:
            dsl_data: DSL 数据

        Returns:
            错误信息列表
        """
        errors = []

        # 检查必填字段
        required_fields = ['rule_id', 'inputs']
        if dsl_data.get('policy_type') not in {'appliance', 'auto', 'coupon'}:
            required_fields.append('output')
        for field in required_fields:
            if field not in dsl_data or not dsl_data[field]:
                errors.append(f"缺少必填字段: {field}")

        # 检查输入变量
        if 'inputs' in dsl_data:
            for i, input_var in enumerate(dsl_data['inputs']):
                if not isinstance(input_var, dict):
                    errors.append(f"输入变量 {i} 格式错误")
                elif 'name' not in input_var:
                    errors.append(f"输入变量 {i} 缺少 name 字段")
                elif 'type' not in input_var:
                    errors.append(f"输入变量 {i} 缺少 type 字段")

        # 检查日期格式
        date_fields = ['valid_start', 'valid_end']
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        for field in date_fields:
            if field in dsl_data and dsl_data[field]:
                if not re.match(date_pattern, dsl_data[field]):
                    errors.append(f"{field} 日期格式错误，应为 YYYY-MM-DD")

        return errors

