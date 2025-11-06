"""
DSL 生成器模块
将结构化数据转换为 YAML 格式的 DSL
"""

import yaml
import json
import jinja2
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DSLGenerator:
    """DSL 生成器，将结构化数据转换为 DSL YAML"""

    # DSL 模板
    DSL_TEMPLATE = """rule_id: {{ rule_id }}
policy_source:
  doc_id: "{{ doc_id }}"
  title: "{{ title }}"
  {% if clause %}clause: "{{ clause }}"{% endif %}
{% if valid_start or valid_end %}
valid_period:
  {% if valid_start %}start: "{{ valid_start }}"{% endif %}
  {% if valid_end %}end: "{{ valid_end }}"{% endif %}
{% endif %}

inputs:
{% for input in inputs %}
  - name: {{ input.name }}
    type: {{ input.type }}
    required: {{ input.required | lower }}
    {% if input.get('description') %}description: "{{ input.description }}"{% endif %}
{% endfor %}

{% if limits %}
limits:
  {% for key, value in limits.items() %}
  {{ key }}: {{ value }}
  {% endfor %}
{% endif %}

{% if tiers %}
tiers:
{% for tier in tiers %}
  - range: [{{ tier.range[0] }}, {{ tier.range[1] if tier.range[1] else 'null' }}]
    {% for key, value in tier.items() if key != 'range' %}
    {{ key }}: {{ value }}
    {% endfor %}
{% endfor %}
{% endif %}

{% if calc %}
calc:
  {% for key, value in calc.items() %}
  {{ key }}: {% if '\n' in value|string %}|
    {{ value | indent(4) }}
  {% else %}{{ value }}{% endif %}
  {% endfor %}
{% endif %}

output:
  status: "{{ output.status }}"
  final_result: "{{ output.final_result }}"
  {% if output.trace_template %}
  trace_template: |
    {{ output.trace_template | indent(4) }}
  {% endif %}
"""

    def __init__(self, output_dir: str = "rules"):
        """
        初始化 DSL 生成器

        Args:
            output_dir: DSL 文件输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=False,
            undefined=jinja2.StrictUndefined
        )
        self.template = self.env.from_string(self.DSL_TEMPLATE)

    def generate(self, data: Dict[str, Any], validate: bool = True) -> str:
        """
        生成 DSL YAML

        Args:
            data: 结构化数据
            validate: 是否验证生成的 DSL

        Returns:
            生成的 YAML 字符串
        """
        # 预处理数据
        processed_data = self._preprocess_data(data)

        # 生成 YAML
        yaml_content = self._render_template(processed_data)

        # 验证 YAML
        if validate:
            errors = self._validate_yaml(yaml_content)
            if errors:
                logger.warning(f"DSL 验证发现问题: {errors}")

        return yaml_content

    def _preprocess_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """预处理数据，确保格式正确"""
        processed = data.copy()

        # 确保必填字段存在
        if 'rule_id' not in processed:
            processed['rule_id'] = f"Rule_Generated_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if 'doc_id' not in processed:
            processed['doc_id'] = ''

        if 'title' not in processed:
            processed['title'] = '未命名政策'

        # 处理输入变量
        if 'inputs' not in processed:
            processed['inputs'] = []
        else:
            # 确保每个输入都有必要的字段
            for input_var in processed['inputs']:
                if 'required' not in input_var:
                    input_var['required'] = True
                if 'type' not in input_var:
                    input_var['type'] = 'string'

        # 处理输出
        if 'output' not in processed:
            processed['output'] = {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.result }}',
                'trace_template': ''
            }

        # 处理计算逻辑
        if 'calc' in processed and isinstance(processed['calc'], dict):
            # 将复杂的计算逻辑转换为多行字符串
            for key, value in processed['calc'].items():
                if isinstance(value, list):
                    processed['calc'][key] = '\n'.join(value)

        return processed

    def _render_template(self, data: Dict[str, Any]) -> str:
        """渲染模板生成 YAML"""
        try:
            return self.template.render(**data)
        except jinja2.exceptions.UndefinedError as e:
            logger.error(f"模板渲染失败，缺少必要字段: {e}")
            # 提供默认值再次尝试
            data.setdefault('clause', None)
            data.setdefault('valid_start', None)
            data.setdefault('valid_end', None)
            data.setdefault('limits', {})
            data.setdefault('tiers', [])
            data.setdefault('calc', {})
            return self.template.render(**data)

    def _validate_yaml(self, yaml_content: str) -> List[str]:
        """验证生成的 YAML"""
        errors = []

        try:
            # 尝试解析 YAML
            data = yaml.safe_load(yaml_content)

            # 检查必填字段
            required_fields = ['rule_id', 'inputs', 'output']
            for field in required_fields:
                if field not in data:
                    errors.append(f"缺少必填字段: {field}")

            # 检查输入变量格式
            if 'inputs' in data and isinstance(data['inputs'], list):
                for i, input_var in enumerate(data['inputs']):
                    if not isinstance(input_var, dict):
                        errors.append(f"输入变量 {i} 格式错误")
                    elif 'name' not in input_var:
                        errors.append(f"输入变量 {i} 缺少 name 字段")

        except yaml.YAMLError as e:
            errors.append(f"YAML 解析错误: {e}")

        return errors

    def save(self, yaml_content: str, filename: Optional[str] = None) -> Path:
        """
        保存 DSL 到文件

        Args:
            yaml_content: YAML 内容
            filename: 文件名，如果不提供则自动生成

        Returns:
            保存的文件路径
        """
        if not filename:
            # 从 YAML 中提取 rule_id 作为文件名
            try:
                data = yaml.safe_load(yaml_content)
                rule_id = data.get('rule_id', 'unknown')
                filename = f"{rule_id}.yaml"
            except:
                filename = f"rule_{datetime.now().strftime('%Y%m%d%H%M%S')}.yaml"

        file_path = self.output_dir / filename
        file_path.write_text(yaml_content, encoding='utf-8')
        logger.info(f"DSL 已保存到: {file_path}")

        return file_path

    def generate_from_template(self, template_type: str, **kwargs) -> str:
        """
        使用预定义模板生成 DSL

        Args:
            template_type: 模板类型（appliance, car, consumption 等）
            **kwargs: 模板参数

        Returns:
            生成的 YAML 字符串
        """
        templates = {
            'appliance': self._get_appliance_template,
            'car': self._get_car_template,
            'consumption': self._get_consumption_template
        }

        if template_type not in templates:
            raise ValueError(f"不支持的模板类型: {template_type}")

        template_data = templates[template_type](**kwargs)
        return self.generate(template_data)

    def _get_appliance_template(self, **kwargs) -> Dict[str, Any]:
        """家电补贴模板"""
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Jinan_Appliance_2025'),
            'doc_id': kwargs.get('doc_id', '济商务字〔2025〕X号'),
            'title': kwargs.get('title', '家电以旧换新补贴实施细则'),
            'inputs': [
                {'name': 'price', 'type': 'float', 'required': True, 'description': '商品价格'},
                {'name': 'energy_level', 'type': 'int', 'required': False, 'description': '能效等���'},
                {'name': 'category', 'type': 'string', 'required': True, 'description': '商品类别'}
            ],
            'limits': {
                'per_item_cap': kwargs.get('cap', 2000),
                'per_user_per_category': {'空调': 3, 'default': 1}
            },
            'calc': {
                'base_rate': kwargs.get('base_rate', 0.15),
                'extra_rate': kwargs.get('extra_rate', 0.05),
                'subsidy': """rate = base_rate
if energy_level == 1:
    rate += extra_rate
raw = price * rate
min(raw, per_item_cap)"""
            },
            'output': {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 判定能效等级 → {{ energy_level }}
- 补贴比例 → {{ rate * 100 }}%
- 原始补贴 = {{ price }} × {{ rate }} = {{ price * rate }}
- 封顶后补贴 = min({{ price * rate }}, {{ per_item_cap }}) = {{ calc.subsidy }}"""
            }
        }

    def _get_car_template(self, **kwargs) -> Dict[str, Any]:
        """汽车补贴模板"""
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Jinan_Car_2025'),
            'doc_id': kwargs.get('doc_id', '济南市汽车消费补贴公告'),
            'title': kwargs.get('title', '汽车消费补贴活动'),
            'inputs': [
                {'name': 'invoice_no_tax', 'type': 'float', 'required': True, 'description': '不含税价格'},
                {'name': 'vehicle_type', 'type': 'string', 'required': True, 'description': '车辆类型'}
            ],
            'tiers': kwargs.get('tiers', [
                {'range': [0, 100000], 'package': 1900},
                {'range': [100000, 150000], 'package': 3200},
                {'range': [150000, 250000], 'package': 4800},
                {'range': [250000, 400000], 'package': 6400},
                {'range': [400000, None], 'package': 8500}
            ]),
            'calc': {
                'tier': """for t in tiers:
    lo, hi = t.range
    if (lo is None or invoice_no_tax >= lo) and (hi is None or invoice_no_tax < hi):
        return t
return None""",
                'subsidy': '{{ tier.package }}'
            },
            'output': {
                'status': "{{ 'QUALIFIED' if tier else 'NOT_QUALIFIED' }}",
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 发票不含税价 = {{ invoice_no_tax }}
- 匹配档位 = {{ tier.range }}
- 礼包总额 = {{ tier.package }}"""
            }
        }

    def _get_consumption_template(self, **kwargs) -> Dict[str, Any]:
        """消费补贴模板"""
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Jinan_Consumption_2025'),
            'doc_id': kwargs.get('doc_id', '济南市消费促进活动通知'),
            'title': kwargs.get('title', '消费促进补贴活动'),
            'inputs': [
                {'name': 'amount', 'type': 'float', 'required': True, 'description': '消费金额'},
                {'name': 'merchant_type', 'type': 'string', 'required': True, 'description': '商户类型'}
            ],
            'limits': {
                'daily_limit': kwargs.get('daily_limit', 10000),
                'per_user_limit': kwargs.get('per_user_limit', 500)
            },
            'calc': {
                'rate': kwargs.get('rate', 0.1),
                'subsidy': 'min(amount * rate, per_user_limit)'
            },
            'output': {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 消费金额 = {{ amount }}
- 补贴比例 = {{ rate * 100 }}%
- 补贴金额 = min({{ amount * rate }}, {{ per_user_limit }}) = {{ calc.subsidy }}"""
            }
        }