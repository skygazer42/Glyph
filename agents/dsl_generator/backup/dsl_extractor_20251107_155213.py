"""
DSL 提取器模块
使用 LLM 从政策文本中提取结构化信息并生成 DSL
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DSLExtractor:
    """使用 LLM 提取政策文本并生成 DSL"""

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None):
        """
        初始化 DSL 提取器

        Args:
            api_key: API密钥，如果不提供则从环境变量读取
            api_base: API基础URL，默认使用OpenAI
        """
        # 优先使用 LLM_API_KEY，兼容 OPENAI_API_KEY
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.api_base = api_base or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.model = os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL", "gpt-4-turbo-preview")

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
        prompt = f"""你是一名政策规则工程师，任务是将自然语言政策文���，结构化提取为 JSON 格式的政策数据。

请从以下政策文本中提取关键信息，并返回 JSON 格式：

### 需要提取的字段：
1. rule_id: 规则ID（格式：Rule_[城市]_[类型]_[年份]）
2. doc_id: 文档编号
3. title: 政策标题
4. clause: 条款位置
5. valid_start: 开始时间（YYYY-MM-DD）
6. valid_end: 结束时间（YYYY-MM-DD）
7. inputs: 输入变量列表
8. limits: 限额限制
9. tiers: 分档信息
10. calc: 计算逻辑
11. conditions: 条件判断
12. result: 结果输出

### 政策文本：
{text}

### 额外信息：
{json.dumps(metadata or {}, ensure_ascii=False, indent=2)}

### 输出要求：
1. 严格返回 JSON 格式，不要包含任何其他说明
2. 金额单位统一为"元"
3. 百分比转换为小数（如 15% -> 0.15）
4. 时间格式为 YYYY-MM-DD
5. 如果某个字段无法确定，使用 null 值

### 输出 JSON：
"""
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        try:
            # 尝试使用 OpenAI API (新版本)
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的政策规则提取专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except ImportError:
            # 如果没有安装 openai，使用内置的规则提取
            logger.warning("OpenAI 库未安装，使用内置规则提取")
            return self._extract_with_rules(prompt)

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            # 降级到规则提取
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
            "result": {}
        }

        # 提取文档编号
        doc_id_pattern = r'[A-Za-z0-9\u4e00-\u9fa5]+[〔【\[][\d]+[〕】\]][\d]+号'
        doc_id_match = re.search(doc_id_pattern, text)
        if doc_id_match:
            result['doc_id'] = doc_id_match.group()

        # 提取标题
        title_pattern = r'[《]([^》]+)[》]|^(.{1,50}(?:实施细则|管理办法|通知|公告|方案))'
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
        rate_pattern = r'补贴[比例率]?[为是]?(\d+(?:\.\d+)?)[%％]'
        rate_match = re.search(rate_pattern, text)
        if rate_match:
            result['calc']['base_rate'] = float(rate_match.group(1)) / 100

        # 提取分档信息
        tier_pattern = r'(\d+(?:\.\d+)?)[万元]?[至到\-](\d+(?:\.\d+)?)[万元]?'
        tier_matches = re.finditer(tier_pattern, text)
        for match in tier_matches:
            low = float(match.group(1))
            high = float(match.group(2))
            if '万' in match.group():
                low *= 10000
                high *= 10000
            result['tiers'].append({
                'range': [low, high],
                'benefit': None
            })

        # 生成基本输入变量
        result['inputs'] = [
            {"name": "price", "type": "float", "required": True},
            {"name": "category", "type": "string", "required": True}
        ]

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

        # 确保必要字段存在
        required_fields = ['doc_id', 'title', 'inputs', 'limits', 'calc', 'output']
        for field in required_fields:
            if field not in data:
                if field == 'inputs':
                    data[field] = []
                elif field in ['limits', 'calc']:
                    data[field] = {}
                elif field == 'output':
                    # 添加默认的输出结构
                    data[field] = {
                        'status': 'QUALIFIED',
                        'final_result': '{{ calc.result }}',
                        'trace_template': ''
                    }
                else:
                    data[field] = None

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
                if 'name' not in input_var:
                    errors.append(f"输入变量 {i} 缺少 name 字段")
                if 'type' not in input_var:
                    errors.append(f"输入变量 {i} 缺少 type 字段")

        # 检查日期格式
        date_fields = ['valid_start', 'valid_end']
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        for field in date_fields:
            if field in dsl_data and dsl_data[field]:
                if not re.match(date_pattern, dsl_data[field]):
                    errors.append(f"{field} 日期格式错误，应为 YYYY-MM-DD")

        return errors