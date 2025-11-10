"""
规则引擎模块
执行 DSL 定义的政策规则
"""

import yaml
import json
import jinja2
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import re

from app.agents.dsl_generator.dsl_runtime_helpers import DSLRuntimeHelpers

logger = logging.getLogger(__name__)


class PolicyEngine:
    """政策规则引擎"""

    def __init__(self, rule_dir: str = "rules"):
        """
        初始化规则引擎

        Args:
            rule_dir: 规则文件目录
        """
        self.rule_dir = Path(rule_dir)
        self.rule_dir.mkdir(exist_ok=True)
        self.rules = {}
        self.env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=False
        )
        self.env.globals.update({
            'str': str,
            'int': int,
            'float': float,
            'len': len,
            'min': min,
            'max': max,
            'round': round,
            'abs': abs
        })
        self._load_all_rules()

    def _load_all_rules(self):
        """加载所有规则文件"""
        self.rules = {}

        if not self.rule_dir.exists():
            logger.warning(f"规则目录不存在: {self.rule_dir}")
            return

        for file_path in self.rule_dir.glob("*.yaml"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    rule_data = yaml.safe_load(f)
                    if rule_data and 'rule_id' in rule_data:
                        self.rules[rule_data['rule_id']] = rule_data
                        logger.info(f"加载规则: {rule_data['rule_id']}")
            except Exception as e:
                logger.error(f"加载规则文件 {file_path} 失败: {e}")

    def reload_rules(self):
        """重新加载所有规则（热更新）"""
        self._load_all_rules()

    def execute(self, rule_id: str, inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行指定规则

        Args:
            rule_id: 规则ID
            inputs: 输入参数
            user_state: 用户状态（用于限购等）

        Returns:
            执行结果
        """
        # 检查规则是否存在
        if rule_id not in self.rules:
            return {
                'status': 'ERROR',
                'message': f'规则不存在: {rule_id}',
                'rule_id': rule_id
            }

        rule = self.rules[rule_id]

        # 检查规则有效期
        if not self._is_valid_period(rule, inputs):
            return {
                'status': 'EXPIRED',
                'message': '政策已过期',
                'rule_id': rule_id,
                'policy_source': rule.get('policy_source', {})
            }

        # 验证输入参数
        validation_errors = self._validate_inputs(rule, inputs)
        if validation_errors:
            return {
                'status': 'INVALID_INPUT',
                'message': '输入参数错误',
                'errors': validation_errors,
                'rule_id': rule_id
            }

        # 执行计算
        try:
            result = self._execute_calculation(rule, inputs, user_state)
            return result
        except Exception as e:
            logger.error(f"执行规则 {rule_id} 时出错: {e}")
            return {
                'status': 'ERROR',
                'message': f'执行错误: {str(e)}',
                'rule_id': rule_id
            }

    def _is_valid_period(self, rule: Dict[str, Any], inputs: Dict[str, Any]) -> bool:
        """检查规则是否在有效期内"""
        valid_period = rule.get('valid_period')
        if not valid_period:
            return True

        ref_date = self._extract_reference_date(inputs) or date.today()

        # 检查开始时间
        start_value = valid_period.get('start')
        if start_value:
            start_date = datetime.strptime(start_value, '%Y-%m-%d').date()
            if ref_date < start_date:
                return False

        # 检查结束时间
        end_value = valid_period.get('end')
        if end_value:
            end_date = datetime.strptime(end_value, '%Y-%m-%d').date()
            if ref_date > end_date:
                return False

        return True

    def _extract_reference_date(self, inputs: Dict[str, Any]) -> Optional[date]:
        """从输入中提取与有效期相关的时间."""
        candidates = ['claim_time', 'purchase_time', 'invoice_time', 'apply_time']
        for key in candidates:
            value = inputs.get(key)
            if not value:
                continue
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                parsed = self._parse_date_string(value)
                if parsed:
                    return parsed
        return None

    def _parse_date_string(self, value: str) -> Optional[date]:
        """尝试解析 ISO 日期/时间."""
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
        except Exception:
            pass
        try:
            return datetime.strptime(value[:10], '%Y-%m-%d').date()
        except Exception:
            return None

    def _validate_inputs(self, rule: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """验证输入参数"""
        errors = []

        input_specs = rule.get('inputs', [])
        for spec in input_specs:
            name = spec['name']
            required = spec.get('required', True)
            input_type = spec.get('type', 'string')

            # 检查必填参数
            if required and name not in inputs:
                errors.append(f"缺少必填参数: {name}")
                continue

            # 检查类型
            if name in inputs:
                value = inputs[name]
                if value is not None:
                    if input_type == 'float':
                        try:
                            float(value)
                        except (ValueError, TypeError):
                            errors.append(f"参数 {name} 应为浮点数")
                    elif input_type == 'int':
                        try:
                            int(value)
                        except (ValueError, TypeError):
                            errors.append(f"参数 {name} 应为整数")
                    elif input_type == 'string':
                        if not isinstance(value, str):
                            errors.append(f"参数 {name} 应为字符串")

        return errors

    def _execute_calculation(self, rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行规则计算"""
        context = self._build_eval_context(rule, inputs, user_state)

        # 执行计算逻辑
        calc_result = {}
        calc_spec = rule.get('calc', {})

        for key, expr in calc_spec.items():
            try:
                # 使用安全的表达式求值
                value = self._eval_expression(expr, {**context, 'calc': calc_result})
                calc_result[key] = value
                context['calc'] = calc_result
            except Exception as e:
                logger.error(f"计算 {key} 时出错: {e}")
                calc_result[key] = None

        context['calc'] = calc_result

        # 生成输出
        output_spec = rule.get('output', {})

        # 计算状态
        status_expr = output_spec.get('status', 'QUALIFIED')
        status = self._eval_template(status_expr, context)

        # 计算最终结果
        result_expr = output_spec.get('final_result', '')
        final_result = self._eval_template(result_expr, context)

        # 生成追踪信息
        trace = []
        trace_template = output_spec.get('trace_template', '')
        if trace_template:
            trace_lines = self._eval_template(trace_template, context).strip().split('\n')
            for i, line in enumerate(trace_lines, 1):
                trace.append({
                    'step': i,
                    'description': line.strip(' -')
                })

        return {
            'rule_id': rule['rule_id'],
            'status': status,
            'final_result': final_result,
            'policy_source': rule.get('policy_source', {}),
            'explainability_trace': trace,
            'calculation_details': calc_result
        }

    def _eval_expression(self, expr: str, context: Dict[str, Any]) -> Any:
        """安全地执行表达式"""
        if isinstance(expr, (int, float, bool)):
            return expr

        if not isinstance(expr, str):
            return expr

        # 简单的数学表达式
        if re.match(r'^[\d\.\+\-\*\/\(\)\s]+$', expr):
            try:
                return eval(expr)
            except:
                return expr

        # 复杂表达式使用受限的环境执行
        safe_globals = {
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'len': len,
            'sum': sum,
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'None': None,
            'True': True,
            'False': False,
            'dsl_helpers': DSLRuntimeHelpers
        }

        # 合并上下文
        safe_globals.update(context)

        try:
            # 使用 compile 和 eval 执行
            compiled = compile(expr, '<string>', 'eval')
            return eval(compiled, safe_globals, {})
        except:
            # 如果执行失败，尝试作为模板处理
            return self._eval_template(expr, context)

    def _build_eval_context(self, rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Assemble the evaluation context exposed to DSL expressions."""
        user_state = user_state or {}
        ctx = {
            'inputs': inputs,
            'user_state': user_state,
            'context': user_state,  # backwards compatible alias for helper callables
            'limits': rule.get('limits', {}),
            'tiers': rule.get('tiers', []),
            'rule': rule
        }

        optional_sections = [
            'windows',
            'budget',
            'matching',
            'efficiency_rates',
            'category_limits',
            'per_item_cap',
            'special_rules',
            'valid_period',
            'distribution',
            'usage_limits',
            'coupon_types',
            'platform',
            'price_basis',
            'policy_source'
        ]

        for key in optional_sections:
            value = rule.get(key)
            if key == 'special_rules':
                value = value or {}
            ctx[key] = value

        return ctx

    def _eval_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """使用 Jinja2 模板引擎求值"""
        try:
            # 处理简单的变量替换
            if '{{' in template_str and '}}' in template_str:
                template = self.env.from_string(template_str)
                return template.render(**context)
            else:
                # 没有模板标记，直接返回
                return template_str
        except Exception as e:
            logger.error(f"模板求值失败: {e}")
            return str(template_str)

    def check_limits(self, rule_id: str, user_id: str, category: str, user_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查用户限额

        Args:
            rule_id: 规则ID
            user_id: 用户ID
            category: 商品类别
            user_state: 用户状态

        Returns:
            检查结果
        """
        if rule_id not in self.rules:
            return {'allowed': False, 'reason': '规则不存在'}

        rule = self.rules[rule_id]
        limits = rule.get('limits', {})

        # 检查每用户每类别限额
        per_user_per_category = limits.get('per_user_per_category', {})
        if category in per_user_per_category:
            limit = per_user_per_category[category]
        else:
            limit = per_user_per_category.get('default', 1)

        # 获取当前计数
        key = f"{category}_count"
        current_count = user_state.get(key, 0)

        if current_count >= limit:
            return {
                'allowed': False,
                'reason': f'{category} 类别已达到限购数量 {limit}',
                'current_count': current_count,
                'limit': limit
            }

        return {
            'allowed': True,
            'current_count': current_count,
            'limit': limit,
            'remaining': limit - current_count
        }

    def list_rules(self) -> List[Dict[str, Any]]:
        """列出所有可用规则"""
        rules_list = []
        for rule_id, rule in self.rules.items():
            rules_list.append({
                'rule_id': rule_id,
                'title': rule.get('policy_source', {}).get('title', '未命名'),
                'doc_id': rule.get('policy_source', {}).get('doc_id', ''),
                'valid_period': rule.get('valid_period', {}),
                'is_active': self._is_valid_period(rule)
            })
        return rules_list

    def get_rule_info(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取规则详细信息"""
        if rule_id in self.rules:
            rule = self.rules[rule_id].copy()
            rule['is_active'] = self._is_valid_period(rule)
            return rule
        return None
