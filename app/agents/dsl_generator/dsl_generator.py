"""
DSL 生成器模块
将结构化数据转换为 YAML 格式的 DSL
"""

from copy import deepcopy
from datetime import datetime
import logging
import os
from pathlib import Path
import tempfile
from typing import Dict, Any, List, Optional

import jinja2
import yaml

from .template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


def atomic_write_text(path: Path, content: str) -> None:
    """Replace one owned output file only after the complete write succeeds."""
    if path.is_symlink():
        raise ValueError("DSL output must not be a symbolic link")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class DSLGenerator:
    """DSL 生成器，将结构化数据转换为 DSL YAML"""

    # DSL 模板
    DSL_TEMPLATE = """rule_id: {{ rule_id | tojson }}
policy_source:
  doc_id: {{ policy_source.get('doc_id', '') | tojson }}
  title: {{ policy_source.get('title', '未命名政策') | tojson }}
  {% if policy_source.get('clause') %}clause: {{ policy_source.get('clause') | tojson }}{% endif %}
{% if valid_period %}
valid_period:
  {% if valid_period.get('start') %}start: {{ valid_period.get('start') | tojson }}{% endif %}
  {% if valid_period.get('end') %}end: {{ valid_period.get('end') | tojson }}{% endif %}
{% endif %}

inputs: {{ inputs | tojson }}

{% if limits %}
limits:
  {% for key, value in limits.items() %}
  {{ key | tojson }}: {{ value | tojson }}
  {% endfor %}
{% endif %}

{% if tiers %}
tiers:
{% for tier in tiers %}
  - range: [{{ tier.range[0] | tojson }}, {{ tier.range[1] | tojson }}]
    {% for key, value in tier.items() if key != 'range' %}
    {{ key | tojson }}: {{ value | tojson }}
    {% endfor %}
{% endfor %}
{% endif %}

{% if calc %}
calc:
  {% for key, value in calc.items() %}
  {{ key | tojson }}: {{ value | tojson }}
  {% endfor %}
{% endif %}

output:
  status: {{ output['status'] | tojson }}
  final_result: {{ output['final_result'] | tojson }}
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
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
        self.template_registry = TemplateRegistry()

    def generate(
        self,
        data: Dict[str, Any],
        validate: bool = True,
        template_name: Optional[str] = None,
        auto_detect: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
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
        # 预处理结构化数据
        processed_data = self._preprocess_data(data)

        template_profile = None

        if auto_detect and not template_name:
            template_profile = self.template_registry.detect(processed_data, context)
            if template_profile:
                template_name = template_profile.template_name
                logger.info(f"自动检测到模板类型: {template_profile.name}")

        if template_name and not template_profile:
            template_profile = self.template_registry.get_profile_by_template(template_name)

        # Keep selected template local: the generator can serve overlapping calls.
        template = self.env.get_template(template_name) if template_name else self.builtin_template

        # 模板默认值补齐
        processed_data = self.template_registry.apply_defaults(processed_data, template_profile)

        # 生成 YAML
        yaml_content = self._render_template(template, processed_data)

        # 验证 YAML
        if validate:
            errors = self._validate_yaml(yaml_content)
            if errors:
                raise ValueError("DSL YAML validation failed: " + "; ".join(errors))

        return yaml_content

    @staticmethod
    def _preprocess_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """预处理数据，确保格式正确"""
        processed = deepcopy(data)

        def _sanitize(value: Any) -> Any:
            if isinstance(value, str):
                text = ' '.join(value.replace('\r', ' ').replace('\n', ' ').split())
                if not text or text.lower() in {'none', 'null', '无', '暂无'}:
                    return ''
                return text
            return value

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

        # 统一规则元数据
        if not processed.get('name'):
            processed['name'] = processed['policy_source'].get('title') or processed['rule_id']
        processed['name'] = _sanitize(processed['name'])
        if not processed.get('version'):
            processed['version'] = '1.0'
        if processed.get('template_hint') and 'policy_type' not in processed:
            processed['policy_type'] = processed['template_hint']
        if processed.get('policy_type') and 'template_hint' not in processed:
            processed['template_hint'] = processed['policy_type']
        if 'clause' in processed:
            processed['policy_source']['clause'] = processed.pop('clause')

        # 确保 policy_source 有默认值
        if 'doc_id' not in processed['policy_source']:
            processed['policy_source']['doc_id'] = ''
        if 'title' not in processed['policy_source']:
            processed['policy_source']['title'] = '未命名政策'
        for key in ('doc_id', 'title', 'clause'):
            if key in processed['policy_source']:
                processed['policy_source'][key] = _sanitize(processed['policy_source'][key])

        # 处理 valid_period 结构
        if 'valid_period' not in processed:
            processed['valid_period'] = {}

        # 如果 valid_start 和 valid_end 在顶层，迁移到 valid_period
        if 'valid_start' in processed:
            processed['valid_period']['start'] = processed.pop('valid_start')
        if 'valid_end' in processed:
            processed['valid_period']['end'] = processed.pop('valid_end')

        processed['valid_period'].setdefault('start', None)
        processed['valid_period'].setdefault('end', None)

        # 处理输入变量
        if 'inputs' not in processed:
            processed['inputs'] = []
        else:
            # 将字符串列表转换为字典列表
            if not isinstance(processed['inputs'], list):
                raise ValueError("inputs must be a list")
            if processed['inputs']:
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
                    else:
                        raise ValueError("Each input must be a name or object")
                processed['inputs'] = new_inputs

        # Named templates own their output expressions; the generic template requires them.
        if 'output' in processed:
            output = processed['output']
            if not isinstance(output, dict):
                raise ValueError("output must be an object")
            if 'status' not in output or 'final_result' not in output:
                raise ValueError("output requires status and final_result")
        for tier in processed.get('tiers', []):
            if not isinstance(tier, dict):
                raise ValueError("Each tier must be an object")
            if 'range' not in tier and 'min' in tier and 'max' in tier:
                tier['range'] = [tier.pop('min'), tier.pop('max')]

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

    def detect_template_type(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        根据数据和上下文自动检测最匹配的模板类型。
        """
        profile = self.template_registry.detect(data, context)
        return profile.template_name if profile else None

    def _render_template(self, template: jinja2.Template, data: Dict[str, Any]) -> str:
        """Render only the selected template; missing required data remains an error."""
        if template is self.builtin_template and 'output' not in data:
            raise ValueError("Generic DSL requires explicit output expressions")
        return template.render(**data)

    @staticmethod
    def _validate_yaml(yaml_content: str) -> List[str]:
        """验证生成的 YAML"""
        errors = []

        try:
            # 尝试解析 YAML
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                return ["YAML must contain an object"]

            # 检查必填字段
            required_fields = ['rule_id', 'output']
            for field in required_fields:
                if field not in data:
                    errors.append(f"缺少必填字段: {field}")

            if 'rule_id' in data and not isinstance(data['rule_id'], str):
                errors.append("rule_id must be text")
            inputs = data.get('inputs', [])
            if not isinstance(inputs, list):
                errors.append("inputs must be a list")
            else:
                for i, input_var in enumerate(inputs):
                    if not isinstance(input_var, dict):
                        errors.append(f"输入变量 {i} 格式错误")
                    elif 'name' not in input_var:
                        errors.append(f"输入变量 {i} 缺少 name 字段")
            if 'calc' in data and not isinstance(data['calc'], dict):
                errors.append("calc must be an object")
            output = data.get('output')
            if 'output' in data:
                if not isinstance(output, dict):
                    errors.append("output must be an object")
                else:
                    for field in ('status', 'final_result'):
                        if field not in output or not isinstance(output[field], str):
                            errors.append(f"output.{field} must be text")

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
        errors = self._validate_yaml(yaml_content)
        if errors:
            raise ValueError("DSL YAML validation failed: " + "; ".join(errors))
        if filename is None:
            # 从 YAML 中提取 rule_id 作为文件名
            data = yaml.safe_load(yaml_content)
            rule_id = data['rule_id']
            if not isinstance(rule_id, str) or not rule_id.strip():
                raise ValueError("rule_id must be non-empty text")
            filename = f"{rule_id}.yaml"
        if not filename or Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError("DSL filename must be a single file name")
        file_path = self.output_dir / filename
        atomic_write_text(file_path, yaml_content)
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

    @staticmethod
    def _get_appliance_template(**kwargs) -> Dict[str, Any]:
        """家电补贴模板"""
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Template_Appliance'),
            'doc_id': kwargs.get('doc_id', '济商务字〔2025〕X号'),
            'title': kwargs.get('title', '家电以旧换新补贴实施细则'),
            'inputs': [
                {'name': 'price', 'type': 'float', 'required': True, 'description': '商品价格'},
                {'name': 'energy_level', 'type': 'int', 'required': False, 'description': '能效等级'},
                {'name': 'category', 'type': 'string', 'required': True, 'description': '商品类别'}
            ],
            'limits': {
                'per_item_cap': kwargs.get('cap', 2000),
                'per_user_per_category': {'空调': 3, 'default': 1}
            },
            'calc': {
                'base_rate': kwargs.get('base_rate', 0.15),
                'extra_rate': kwargs.get('extra_rate', 0.05),
                'rate': "calc['base_rate'] + (calc['extra_rate'] if inputs.get('energy_level') is not None and int(inputs['energy_level']) == 1 else 0)",
                'subsidy': "min(float(inputs['price']) * calc['rate'], limits['per_item_cap'])",
            },
            'output': {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 判定能效等级 → {{ inputs.get('energy_level') }}
- 补贴比例 → {{ calc.rate * 100 }}%
- 原始补贴 = {{ inputs.price }} × {{ calc.rate }}
- 封顶后补贴 = min(原始补贴, {{ limits.per_item_cap }}) = {{ calc.subsidy }}"""
            }
        }

    @staticmethod
    def _get_car_template(**kwargs) -> Dict[str, Any]:
        """汽车补贴模板"""
        tiers = kwargs.get('tiers', [
            {'range': [0, 100000], 'package': 1900},
            {'range': [100000, 150000], 'package': 3200},
            {'range': [150000, 250000], 'package': 4800},
            {'range': [250000, 400000], 'package': 6400},
            {'range': [400000, None], 'package': 8500}
        ])
        # Encode the configured first-match ranges with the existing expression
        # language. No loop statements or arbitrary Python execution are needed.
        tier_expression = 'None'
        for index in reversed(range(len(tiers))):
            tier = f'tiers[{index}]'
            amount = "float(inputs['invoice_no_tax'])"
            matches = (f"({tier}['range'][0] is None or {amount} >= {tier}['range'][0]) and "
                       f"({tier}['range'][1] is None or {amount} < {tier}['range'][1])")
            tier_expression = f'{tier} if {matches} else ({tier_expression})'
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Template_Car'),
            'doc_id': kwargs.get('doc_id', '待核实的汽车消费补贴政策'),
            'title': kwargs.get('title', '汽车消费补贴活动'),
            'inputs': [
                {'name': 'invoice_no_tax', 'type': 'float', 'required': True, 'description': '不含税价格'},
                {'name': 'vehicle_type', 'type': 'string', 'required': True, 'description': '车辆类型'}
            ],
            'tiers': tiers,
            'calc': {
                'tier': tier_expression,
                'subsidy': "calc['tier']['package'] if calc['tier'] is not None else 0"
            },
            'output': {
                'status': "{{ 'QUALIFIED' if calc.tier is not none else 'NOT_QUALIFIED' }}",
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 发票不含税价 = {{ inputs.invoice_no_tax }}
- 匹配档位 = {{ calc.tier.range if calc.tier is not none else '无匹配档位' }}
- 礼包总额 = {{ calc.subsidy }}"""
            }
        }

    @staticmethod
    def _get_consumption_template(**kwargs) -> Dict[str, Any]:
        """消费补贴模板"""
        return {
            'rule_id': kwargs.get('rule_id', 'Rule_Template_Consumption'),
            'doc_id': kwargs.get('doc_id', '待核实的消费促进活动政策'),
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
                'subsidy': "min(float(inputs['amount']) * calc['rate'], limits['per_user_limit'])"
            },
            'output': {
                'status': 'QUALIFIED',
                'final_result': '{{ calc.subsidy }}',
                'trace_template': """- 消费金额 = {{ inputs.amount }}
- 补贴比例 = {{ calc.rate * 100 }}%
- 补贴金额 = min(消费金额 × 补贴比例, {{ limits.per_user_limit }}) = {{ calc.subsidy }}"""
            }
        }
