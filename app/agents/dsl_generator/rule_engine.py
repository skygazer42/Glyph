"""
规则引擎模块
执行 DSL 定义的政策规则
"""

import ast
import logging
import operator
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import jinja2
from jinja2.sandbox import SandboxedEnvironment
import yaml

import app.agents.dsl_generator.subsidy_calculations as subsidy_calculations
import app.agents.dsl_generator.trade_in_calculations as trade_in_calculations
import app.agents.dsl_generator.housing_calculations as housing_calculations
import app.agents.dsl_generator.provident_fund_calculations as provident_calculations
import app.agents.dsl_generator.changzhou_vehicle_calculations as vehicle_calculations
import app.agents.dsl_generator.changzhou_benefit_calculations as benefit_calculations
from app.agents.dsl_generator.rule_verification import RuleVerificationRegistry

logger = logging.getLogger(__name__)


class PolicyEngine:
    """政策规则引擎"""

    def __init__(self, rule_dir: Optional[str] = "rules"):
        """
        初始化规则引擎

        Args:
            rule_dir: 规则文件目录；None 用于不读写文件的草稿试算
        """
        self.rule_dir = Path(rule_dir) if rule_dir is not None else None
        if self.rule_dir is not None:
            self.rule_dir.mkdir(parents=True, exist_ok=True)
        self.rules: Dict[str, Dict[str, Any]] = {}
        self.env = SandboxedEnvironment(
            loader=jinja2.BaseLoader(),
            autoescape=False,
            undefined=jinja2.StrictUndefined,
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
        self.review_registry = RuleVerificationRegistry()
        if self.rule_dir is None:
            return
        rules: Dict[str, Dict[str, Any]] = {}

        if not self.rule_dir.exists():
            raise FileNotFoundError(f"规则目录不存在: {self.rule_dir}")

        for file_path in self.rule_dir.glob("*.yaml"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    rule_data = yaml.safe_load(f)
                    if not isinstance(rule_data, dict) or not isinstance(rule_data['rule_id'], str):
                        raise ValueError(f"规则文件必须包含rule_id: {file_path}")
                    rules[rule_data['rule_id']] = rule_data
                    logger.info(f"加载规则: {rule_data['rule_id']}")
            except Exception as e:
                logger.error(f"加载规则文件 {file_path} 失败: {e}", exc_info=True)
                raise
        self.rules = rules

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
        review = self.review_registry.review(rule)
        if review['status'] == 'needs_review':
            return {
                'status': 'MANUAL_REVIEW',
                'message': review['message'],
                'rule_id': rule_id,
                'policy_source': rule.get('policy_source', {}),
                'verification': review,
            }
        return self.execute_rule(rule, inputs, user_state)

    def execute_rule(self, rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """试算给定版本并标注核验状态；编辑草稿不能继承旧版本的核验结论。"""
        result = self._execute_rule(rule, inputs, user_state)
        review = self.review_registry.review(rule)
        if review['status'] == 'manual_only' and result['status'] in {'CALCULATED', 'QUALIFIED', 'SUCCESS', 'VALID'}:
            result = {
                'rule_id': rule['rule_id'],
                'status': 'MANUAL_REVIEW',
                'message': '此入口仅核实公开条件，个人金额依据尚不完整，暂不提供金额。',
                'policy_source': rule.get('policy_source', {}),
            }
        result['verification'] = review
        return result

    def _execute_rule(self, rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """校验业务日期及输入后计算，不写入规则目录或改变已加载规则。"""
        rule_id = rule['rule_id']

        try:
            try:
                self._extract_reference_date(inputs)
            except ValueError as error:
                return {
                    'status': 'INVALID_INPUT',
                    'message': '业务日期缺失或格式错误',
                    'errors': [str(error)],
                    'rule_id': rule_id,
                    'policy_source': rule.get('policy_source', {}),
                }
            # 检查规则有效期
            if not self._is_valid_period(rule, inputs):
                return {
                    'status': 'EXPIRED',
                    'message': '业务日期不在所选规则的适用期内',
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

            return self._execute_calculation(rule, inputs, user_state)
        except Exception as e:
            logger.error(f"执行规则 {rule_id} 时出错: {e}", exc_info=True)
            return {
                'status': 'ERROR',
                'message': f'执行错误: {str(e)}',
                'rule_id': rule_id
            }

    def _is_valid_period(self, rule: Dict[str, Any], inputs: Optional[Dict[str, Any]] = None) -> bool:
        """检查规则是否在有效期内"""
        inputs = inputs or {}
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
            if value is None:
                continue
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                parsed = self._parse_date_string(value)
                if parsed is None:
                    raise ValueError(f"参数 {key} 应为有效的ISO日期或时间")
                return parsed
            raise ValueError(f"参数 {key} 应为日期、时间或ISO日期文本")
        return None

    @staticmethod
    def _parse_date_string(value: str) -> Optional[date]:
        """尝试解析 ISO 日期/时间."""
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
        except ValueError:
            return None

    @staticmethod
    def _validate_inputs(rule: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """验证输入参数"""
        errors = []

        input_specs = rule.get('inputs', [])
        for spec in input_specs:
            name = spec['name']
            required = spec.get('required', True)
            input_type = spec.get('type', 'string')

            # 检查必填参数
            if required and (name not in inputs or inputs[name] is None):
                errors.append(f"缺少必填参数: {name}")
                continue

            # 检查类型
            if name in inputs:
                value = inputs[name]
                if value is not None:
                    if input_type in {'float', 'number'}:
                        try:
                            if isinstance(value, bool) or not isfinite(float(value)):
                                raise ValueError("Expected a finite number")
                        except (ValueError, TypeError, OverflowError):
                            errors.append(f"参数 {name} 应为浮点数")
                    elif input_type in {'int', 'integer'}:
                        try:
                            integer = int(value)
                            if isinstance(value, bool) or integer != float(value):
                                raise ValueError("Expected an integer")
                        except (ValueError, TypeError, OverflowError):
                            errors.append(f"参数 {name} 应为整数")
                    elif input_type in {'bool', 'boolean'}:
                        if not isinstance(value, bool):
                            errors.append(f"参数 {name} 应为布尔值")
                    elif input_type == 'string':
                        if not isinstance(value, str):
                            errors.append(f"参数 {name} 应为字符串")

        return errors

    def _execute_calculation(self, rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行规则计算"""
        context = self._build_eval_context(rule, inputs, user_state)

        # 执行计算逻辑
        calc_result: Dict[str, Any] = {}
        calc_spec = rule.get('calc', {})
        for key, expr in calc_spec.items():
            calc_result[key] = self._eval_expression(expr, {**context, 'calc': calc_result})

        context['calc'] = calc_result

        # 生成输出
        output_spec = rule['output']

        # 计算状态
        status_expr = output_spec['status']
        status = self._eval_template(status_expr, context)

        # 计算最终结果
        result_expr = output_spec['final_result']
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

    def _eval_expression(self, expr: Any, context: Dict[str, Any]) -> Any:
        """Evaluate the DSL's arithmetic, comparisons, mapping access and helpers.

        Rules can be generated from documents, so Python execution and arbitrary
        object access are deliberately outside this expression language.
        """
        if not isinstance(expr, str):
            return expr
        if '{{' in expr or '{%' in expr:
            return self._eval_template(expr, context)
        node = ast.parse(expr, mode='eval').body
        return self._evaluate_node(node, context)

    def _evaluate_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        """递归解释已支持的表达式节点和显式函数表；不支持的 AST 结构由本方法拒绝。"""
        functions: Dict[str, Callable[..., Any]] = {'min': min, 'max': max, 'abs': abs, 'round': round,
                     'len': len, 'sum': sum, 'int': int, 'float': float,
                     'str': str, 'bool': bool}
        binary: Dict[type, Callable[..., Any]] = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv,
                  ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                  ast.Pow: operator.pow}
        comparisons: Dict[type, Callable[..., Any]] = {ast.Eq: operator.eq, ast.NotEq: operator.ne,
                       ast.Lt: operator.lt, ast.LtE: operator.le,
                       ast.Gt: operator.gt, ast.GtE: operator.ge,
                       ast.Is: operator.is_, ast.IsNot: operator.is_not,
                       ast.In: lambda a, b: a in b,
                       ast.NotIn: lambda a, b: a not in b}
        def evaluate(value: ast.AST) -> Any:
            return self._evaluate_node(value, context)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and not node.id.startswith('_'):
            return context[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [evaluate(item) for item in node.elts]
            return tuple(values) if isinstance(node, ast.Tuple) else set(values) if isinstance(node, ast.Set) else values
        if isinstance(node, ast.Dict) and all(key is not None for key in node.keys):
            return {evaluate(key): evaluate(node.values[index]) for index, key in enumerate(node.keys) if key is not None}
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            return binary[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp):
            unary: Dict[type, Callable[..., Any]] = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
            if type(node.op) in unary:
                return unary[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BoolOp):
            value = evaluate(node.values[0])
            for child in node.values[1:]:
                if (isinstance(node.op, ast.And) and not value) or (isinstance(node.op, ast.Or) and value):
                    return value
                value = evaluate(child)
            return value
        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for index, operation in enumerate(node.ops):
                child = node.comparators[index]
                right = evaluate(child)
                if type(operation) not in comparisons or not comparisons[type(operation)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return evaluate(node.body if evaluate(node.test) else node.orelse)
        if isinstance(node, ast.Subscript):
            return evaluate(node.value)[evaluate(node.slice)]
        if isinstance(node, ast.Attribute) and not node.attr.startswith('_'):
            value = evaluate(node.value)
            if isinstance(value, dict):
                return value[node.attr]
        if isinstance(node, ast.Call) and not any(keyword.arg is None for keyword in node.keywords):
            function: Callable[..., Any]
            if isinstance(node.func, ast.Name):
                if node.func.id not in functions:
                    raise ValueError(f'Unsupported DSL function: {node.func.id}')
                function = functions[node.func.id]
            elif isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if isinstance(owner, ast.Name) and owner.id == 'dsl_helpers':
                    helpers: Dict[str, Callable[..., Any]] = {
                        'appliance_subsidy': subsidy_calculations.appliance_subsidy,
                        'auto_subsidy': subsidy_calculations.auto_subsidy,
                        'consumer_coupon': subsidy_calculations.consumer_coupon,
                        'appliance_subsidy_2026': trade_in_calculations.appliance_subsidy_2026,
                        'digital_subsidy_2026': trade_in_calculations.digital_subsidy_2026,
                        'changzhou_smart_goods_2026': trade_in_calculations.changzhou_smart_goods_2026,
                        'auto_trade_in_2026': trade_in_calculations.auto_trade_in_2026,
                        'changzhou_renovation_2026': housing_calculations.changzhou_renovation_2026,
                        'changzhou_property_fee_2026': housing_calculations.changzhou_property_fee_2026,
                        'changzhou_home_purchase_2026': housing_calculations.changzhou_home_purchase_2026,
                        'changzhou_provident_contribution_2026': provident_calculations.changzhou_provident_contribution_2026,
                        'changzhou_provident_loan_2026': provident_calculations.changzhou_provident_loan_2026,
                        'changzhou_provident_repayment_2026': provident_calculations.changzhou_provident_repayment_2026,
                        'changzhou_provident_interest_subsidy_2026': provident_calculations.changzhou_provident_interest_subsidy_2026,
                        'changzhou_provident_hardship_subsidy_2026': provident_calculations.changzhou_provident_hardship_subsidy_2026,
                        'changzhou_provident_rent_2026': provident_calculations.changzhou_provident_rent_2026,
                        'changzhou_provident_purchase_withdrawal_2026': provident_calculations.changzhou_provident_purchase_withdrawal_2026,
                        'changzhou_auto_trade_in_2026': vehicle_calculations.changzhou_auto_trade_in_2026,
                        'changzhou_nev_purchase_tax_2026': vehicle_calculations.changzhou_nev_purchase_tax_2026,
                        'changzhou_electric_bicycle_2026': vehicle_calculations.changzhou_electric_bicycle_2026,
                        'changzhou_childcare_annual_2026': benefit_calculations.changzhou_childcare_annual_2026,
                        'changzhou_childcare_transition_2026': benefit_calculations.changzhou_childcare_transition_2026,
                        'changzhou_employment_jobsearch_2026': benefit_calculations.changzhou_employment_jobsearch_2026,
                        'changzhou_talent_support_2026': benefit_calculations.changzhou_talent_support_2026,
                    }
                    if node.func.attr not in helpers:
                        raise ValueError(f'Unsupported DSL helper: {node.func.attr}')
                    function = helpers[node.func.attr]
                elif node.func.attr == 'get':
                    mapping = evaluate(owner)
                    if not isinstance(mapping, dict):
                        raise ValueError('DSL get() requires a mapping')
                    function = mapping.get
                else:
                    raise ValueError(f'Unsupported DSL method: {node.func.attr}')
            else:
                raise ValueError('Unsupported DSL callable')
            return function(*[evaluate(arg) for arg in node.args],
                            **{keyword.arg: evaluate(keyword.value) for keyword in node.keywords if keyword.arg is not None})
        raise ValueError(f'Unsupported DSL expression: {type(node).__name__}')

    @staticmethod
    def _build_eval_context(rule: Dict[str, Any], inputs: Dict[str, Any], user_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
            'eligibility',
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
        if '{{' in template_str or '{%' in template_str:
            return self.env.from_string(template_str).render(**context)
        return template_str

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
            limit = per_user_per_category.get('default')
        if limit is None:
            return {'allowed': True, 'limit': None, 'remaining': None}

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
                'title': rule.get('name') or rule.get('policy_source', {}).get('title', '未命名'),
                'doc_id': rule.get('policy_source', {}).get('doc_id', ''),
                'valid_period': rule.get('valid_period', {}),
                'is_active': self._is_valid_period(rule, inputs={}),
                'verification': self.review_registry.review(rule),
            })
        return rules_list

    def get_rule_info(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取规则详细信息"""
        if rule_id in self.rules:
            rule = self.rules[rule_id].copy()
            rule['is_active'] = self._is_valid_period(rule, inputs={})
            rule['verification'] = self.review_registry.review(rule)
            return rule
        return None
