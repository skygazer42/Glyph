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
  doc_id: "{{ policy_source.get('doc_id', '') }}"
  title: "{{ policy_source.get('title', '未命名政策') }}"
  {% if policy_source.get('clause') %}clause: "{{ policy_source.get('clause') }}"{% endif %}
{% if valid_period %}
valid_period:
  {% if valid_period.get('start') %}start: "{{ valid_period.get('start') }}"{% endif %}
  {% if valid_period.get('end') %}end: "{{ valid_period.get('end') }}"{% endif %}
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
  status: "{{ output.get('status', 'QUALIFIED') }}"
  final_result: "{{ output.get('final_result', '') }}"
  {% if output.get('trace_template') %}
  trace_template: |
    {{ output.get('trace_template') | indent(4) }}
  {% endif %}
"""

    def __init__(self, output_dir: str = "rules", template_dir: str = "templates"):
        """
        初始化 DSL 生成器

        Args:
            output_dir: DSL 文件输出目录
            template_dir: Jinja2模板目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.template_dir = Path(template_dir)

        # 设置Jinja2环境,支持加载外部模板
        if self.template_dir.exists():
            self.env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(self.template_dir)),
                autoescape=False,
                undefined=jinja2.ChainableUndefined
            )
            logger.info(f"使用外部模板目录: {self.template_dir}")
        else:
            self.env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                autoescape=False,
                undefined=jinja2.ChainableUndefined
            )
            logger.warning(f"模板目录不存在: {self.template_dir}, 使用内置模板")

        # 内置模板
        self.builtin_template = self.env.from_string(self.DSL_TEMPLATE)
        self.template = self.builtin_template

    def generate(self, data: Dict[str, Any], validate: bool = True, template_name: Optional[str] = None, auto_detect: bool = False) -> str:
        """
        生成 DSL YAML

        Args:
            data: 结构化数据
            validate: 是否验证生成的 DSL
            template_name: 外部模板文件名(如 "consumer_coupon.yaml.j2"),如果为None则使用内置模板
            auto_detect: 是否自动检测模板类型

        Returns:
            生成的 YAML 字符串
        """
        # 预处理数据
        processed_data = self._preprocess_data(data)

        # 自动检测模板类型
        if auto_detect and not template_name:
            template_name = self.detect_template_type(processed_data)
            if template_name:
                logger.info(f"自动检测到模板类型: {template_name}")

        # 选择模板
        if template_name:
            try:
                self.template = self.env.get_template(template_name)
                logger.info(f"使用外部模板: {template_name}")
            except jinja2.TemplateNotFound:
                logger.warning(f"模板文件不存在: {template_name}, 使用内置模板")
                self.template = self.builtin_template
        else:
            self.template = self.builtin_template
            logger.info("使用内置模板")

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

        # 处理 policy_source 结构
        if 'policy_source' not in processed:
            processed['policy_source'] = {}

        # 如果 doc_id 和 title 在顶层，迁移到 policy_source
        if 'doc_id' in processed:
            processed['policy_source']['doc_id'] = processed.pop('doc_id')
        if 'title' in processed:
            processed['policy_source']['title'] = processed.pop('title')
        if 'clause' in processed:
            processed['policy_source']['clause'] = processed.pop('clause')

        # 确保 policy_source 有默认值
        if 'doc_id' not in processed['policy_source']:
            processed['policy_source']['doc_id'] = ''
        if 'title' not in processed['policy_source']:
            processed['policy_source']['title'] = '未命名政策'

        # 处理 valid_period 结构
        if 'valid_period' not in processed:
            processed['valid_period'] = {}

        # 如果 valid_start 和 valid_end 在顶层，迁移到 valid_period
        if 'valid_start' in processed:
            processed['valid_period']['start'] = processed.pop('valid_start')
        if 'valid_end' in processed:
            processed['valid_period']['end'] = processed.pop('valid_end')

        # 处理输入变量
        if 'inputs' not in processed:
            processed['inputs'] = []
        else:
            # 将字符串列表转换为字典列表
            if processed['inputs'] and isinstance(processed['inputs'], list):
                new_inputs = []
                for item in processed['inputs']:
                    if isinstance(item, str):
                        # 字符串转换为字典
                        new_inputs.append({
                            'name': item,
                            'type': 'string',
                            'required': True,
                            'description': f'输入参数: {item}'
                        })
                    elif isinstance(item, dict):
                        # 确保字典有必要的字段
                        if 'required' not in item:
                            item['required'] = True
                        if 'type' not in item:
                            item['type'] = 'string'
                        new_inputs.append(item)
                processed['inputs'] = new_inputs

        # 处理输出
        if 'output' not in processed or not isinstance(processed.get('output'), dict):
            processed['output'] = {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.result }}',
                'trace_template': ''
            }
        else:
            # 确保 output 字典包含必要的字段
            if 'status' not in processed['output']:
                processed['output']['status'] = 'QUALIFIED'
            if 'final_result' not in processed['output']:
                processed['output']['final_result'] = '{{ calc.result }}'
            if 'trace_template' not in processed['output']:
                processed['output']['trace_template'] = ''

        # 处理分档信息 (tiers)
        if 'tiers' in processed and isinstance(processed['tiers'], list):
            new_tiers = []
            for tier in processed['tiers']:
                if isinstance(tier, dict):
                    # 确保有 range 字段
                    if 'range' not in tier:
                        # 尝试从其他字段推断
                        if 'min' in tier and 'max' in tier:
                            tier['range'] = [tier.pop('min'), tier.pop('max')]
                        else:
                            tier['range'] = [0, None]
                    new_tiers.append(tier)
            processed['tiers'] = new_tiers

        # 处理计算逻辑
        if 'calc' in processed:
            if isinstance(processed['calc'], str):
                # 如果 calc 是字符串，转换为字典
                processed['calc'] = {
                    'formula': processed['calc']
                }
            elif isinstance(processed['calc'], dict):
                # 将复杂的计算逻辑转换为多行字符串
                for key, value in processed['calc'].items():
                    if isinstance(value, list):
                        processed['calc'][key] = '\n'.join(value)

        return processed

    def detect_template_type(self, data: Dict[str, Any]) -> Optional[str]:
        """
        根据数据自动检测应该使用的模板类型

        Args:
            data: 结构化数据

        Returns:
            模板文件名,如果无法确定则返回None
        """
        title = data.get('title', '') or data.get('policy_source', {}).get('title', '') or ''

        # 根据标题关键词判断模板类型
        if any(keyword in title for keyword in ['消费券', '优惠券', '代金券', '零售', '餐饮']):
            return 'consumer_coupon.yaml.j2'
        elif any(keyword in title for keyword in ['汽车', '购车', '新车', '车辆']):
            return 'auto_subsidy.yaml.j2'
        elif any(keyword in title for keyword in ['家电', '以旧换新', '空调', '冰箱', '电视']):
            return 'appliance_subsidy.yaml.j2'

        # 根据数据结构特征判断
        if 'coupon_types' in data or 'distribution' in data:
            return 'consumer_coupon.yaml.j2'

        return None

    def _render_template(self, data: Dict[str, Any]) -> str:
        """渲染模板生成 YAML"""
        try:
            return self.template.render(**data)
        except jinja2.exceptions.UndefinedError as e:
            logger.error(f"模板渲染失败，缺少必要字段: {e}")
            # 提供默认值再次尝试
            data.setdefault('policy_source', {})
            data['policy_source'].setdefault('doc_id', '')
            data['policy_source'].setdefault('title', '未命名政策')
            data['policy_source'].setdefault('clause', None)

            data.setdefault('valid_period', {})
            data.setdefault('limits', {})
            data.setdefault('tiers', [])
            data.setdefault('calc', {})
            data.setdefault('output', {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.result }}',
                'trace_template': ''
            })
            # 确保 output 是字典并包含必要字段
            if isinstance(data.get('output'), dict):
                data['output'].setdefault('status', 'QUALIFIED')
                data['output'].setdefault('final_result', '{{ calc.result }}')
                data['output'].setdefault('trace_template', '')
            try:
                return self.template.render(**data)
            except Exception as e2:
                logger.error(f"模板渲染再次失败: {e2}")
                raise

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