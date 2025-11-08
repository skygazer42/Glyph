"""
DSL 提取器模块（优化版）
使用项目配置中的 LLM 从政策文本中提取结构化信息并生成 DSL
"""

import os
import sys
import json
import yaml
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

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

        if use_project_config:
            # 使用项目配置
            try:
                from config.settings import settings
                self.settings = settings
                logger.info(f"使用项目配置: LLM={settings.model.llm_model_name}")
            except ImportError:
                logger.warning("无法导入项目配置，使用默认设置")
                self.settings = None
                self.use_project_config = False

    def extract(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        从文本中提取 DSL 结构

        Args:
            text: 政策文本
            metadata: 额外的元数据信息

        Returns:
            提取的 DSL 结构
        """
        # 构建提示词
        prompt = self._build_prompt(text, metadata)

        # 调用 LLM
        response = self._call_llm(prompt)

        # 解析响应
        dsl_data = self._parse_response(response, text, metadata)

        return dsl_data

    def _build_prompt(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """构建 LLM 提示词"""
        # 先检测政策类型
        policy_type = self._detect_policy_type(text)

        if policy_type == 'appliance':
            return self._build_appliance_prompt(text, metadata)
        elif policy_type == 'auto':
            return self._build_auto_prompt(text, metadata)
        else:
            return self._build_coupon_prompt(text, metadata)

    def _detect_policy_type(self, text: str) -> str:
        """检测政策类型"""
        if any(keyword in text for keyword in ['家电', '以旧换新', '空调', '冰箱', '电视', '洗衣机', '能效']):
            return 'appliance'
        elif any(keyword in text for keyword in ['汽车', '购车', '新车', '车辆', '发票']):
            return 'auto'
        else:
            return 'coupon'

    def _build_appliance_prompt(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
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

    def _build_auto_prompt(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
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

    def _build_coupon_prompt(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
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
        if self.use_project_config and self.settings:
            # 使用项目配置调用 LLM
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=self.settings.model.llm_api_key,
                    base_url=self.settings.model.llm_base_url
                )

                response = client.chat.completions.create(
                    model=self.settings.model.llm_model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专业的政策规则提取专家，擅长从政策文本中提取结构化信息。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.settings.model.llm_temperature or 0.1,
                    max_tokens=2000
                )

                return response.choices[0].message.content

            except Exception as e:
                logger.error(f"使用项目配置调用 LLM 失败: {e}")
                # 降级到规则提取
                return self._extract_with_rules(prompt)
        else:
            # 不使用项目配置，直接使用规则提取
            logger.info("使用内置规则提取")
            return self._extract_with_rules(prompt)

    def _extract_with_rules(self, text: str) -> str:
        """使用规则提取（不依赖 LLM）"""
        result = {
            "rule_id": "Rule_Jinan_Policy_2025",
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
        policy_type = self._extract_policy_type(text)
        year = datetime.now().year
        result['rule_id'] = f"Rule_{city}_{policy_type}_{year}"

        # 添加输出配置
        result['output'] = {
            'status': 'QUALIFIED',
            'final_result': '{{ calc.subsidy }}' if 'base_rate' in result.get('calc', {}) else '{{ result }}',
            'trace_template': '- 计算完成'
        }

        return json.dumps(result, ensure_ascii=False)

    def _parse_response(self, response: str, original_text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            # 尝试解析 JSON
            data = json.loads(response)
        except json.JSONDecodeError:
            # 如果不是有效的 JSON，尝试提取 JSON 部分
            json_pattern = r'\{[\s\S]*\}'
            json_match = re.search(json_pattern, response)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except:
                    data = {}
            else:
                data = {}

        # 补充缺失的字段
        if not data.get('rule_id'):
            # 生成规则 ID
            city = self._extract_city(original_text)
            policy_type = self._extract_policy_type(original_text)
            year = datetime.now().year
            data['rule_id'] = f"Rule_{city}_{policy_type}_{year}"

        # 检测政策类型并补充必要字段
        policy_type = self._detect_policy_type(original_text)

        if policy_type == 'appliance':
            # 家电补贴必要字段
            if 'efficiency_rates' not in data:
                data['efficiency_rates'] = {
                    'base_rate': 0.15,
                    'level_1_bonus': 0.05,
                    'no_label_rate': 0.10
                }
            if 'category_limits' not in data:
                data['category_limits'] = {
                    'per_category': {},
                    'total_items': None
                }
            if 'per_item_cap' not in data:
                data['per_item_cap'] = 2000

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
                        data[field] = ['AMOUNT']
                    elif field == 'tiers':
                        data[field] = []
                    elif field == 'distribution':
                        data[field] = {'method': 'auto_claim', 'total_quota': None, 'quota_per_person': None}
                    elif field == 'usage_limits':
                        data[field] = {'valid_days': 30, 'merchant_scope': None, 'product_scope': None, 'stacking': {}}
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

        # 确保基本字段存在
        if 'policy_source' not in data:
            data['policy_source'] = {}
        if 'valid_period' not in data:
            data['valid_period'] = {}

        # 确保 inputs 是正确格式的列表
        if 'inputs' in data and isinstance(data['inputs'], list):
            fixed_inputs = []
            for inp in data['inputs']:
                if isinstance(inp, dict) and 'name' in inp and 'type' in inp:
                    if 'required' not in inp:
                        inp['required'] = True
                    fixed_inputs.append(inp)
                elif isinstance(inp, str):
                    fixed_inputs.append({
                        'name': inp,
                        'type': 'string',
                        'required': True
                    })
            if fixed_inputs:
                data['inputs'] = fixed_inputs

        return data

    def _extract_city(self, text: str) -> str:
        """提取城市名称"""
        cities = ['济南', '青岛', '烟台', '潍坊', '临沂', '淄博', '济宁', '泰安']
        for city in cities:
            if city in text:
                return city
        return 'Unknown'

    def _extract_policy_type(self, text: str) -> str:
        """提取政策类型"""
        types = {
            '家电': 'Appliance',
            '汽车': 'Car',
            '消费': 'Consumption',
            '以旧换新': 'TradeIn',
            '补贴': 'Subsidy',
            '优惠': 'Discount'
        }
        for keyword, policy_type in types.items():
            if keyword in text:
                return policy_type
        return 'General'

    def validate_dsl(self, dsl_data: Dict[str, Any]) -> List[str]:
        """
        验证 DSL 数据的完整性和正确性

        Args:
            dsl_data: DSL 数据

        Returns:
            错误信息列表
        """
        errors = []

        # 检查必填字段
        required_fields = ['rule_id', 'inputs', 'output']
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