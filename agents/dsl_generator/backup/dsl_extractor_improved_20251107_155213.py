"""
DSL 提取器模块 - 改进版
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
        prompt = f"""你是一名政策规则工程师，专门处理政府补贴和消费券政策。请将政策文本提取为结构化JSON。

### 政策文本：
{text}

### 提取要求：

1. **rule_id**: 格式为 Rule_[城市]_[政策类型]_[年份]
   - 政策类型：消费券、汽车补贴、家电补贴、保险补贴等

2. **title**: 政策标题（从文本中提取）

3. **valid_period**: 有效期
   - start: 开始日期 (YYYY-MM-DD)
   - end: 结束日期 (YYYY-MM-DD)

4. **inputs**: 输入参数列表
   示例：
   ```json
   [
     {{"name": "消费金额", "type": "float", "required": true, "description": "消费总金额"}},
     {{"name": "消费类型", "type": "string", "required": true, "description": "零售或餐饮"}}
   ]
   ```

5. **tiers**: 分档规则（重要！）

   对于满减券（满X减Y）：
   ```json
   [
     {{"threshold": 100, "discount": 20, "type": "零售"}},
     {{"threshold": 200, "discount": 40, "type": "零售"}}
   ]
   ```

   对于分档补贴（金额区间）：
   ```json
   [
     {{"range": [100000, 300000], "benefit": 4000, "type": "新能源"}},
     {{"range": [300000, null], "benefit": 5000, "type": "新能源"}}
   ]
   ```

6. **calc**: 计算逻辑
   ```json
   {{
     "type": "满减券",  // 或 "分档补贴"
     "formula": "具体计算公式描述"
   }}
   ```

7. **limits**: 限制条件
   ```json
   {{
     "total_budget": 30000000,  // 总预算（元）
     "per_person_limit": 1,     // 每人限领次数
     "daily_limit": null         // 每日限额
   }}
   ```

8. **conditions**: 申领条件列表
   ```json
   [
     "济南市居民",
     "购买新车",
     "指定时间内"
   ]
   ```

9. **output**: 输出配置
   ```json
   {{
     "status": "QUALIFIED",
     "final_result": "补贴金额",
     "trace_template": "您购买的{{{{vehicle_type}}}}车辆，发票金额{{{{amount}}}}元，可获得{{{{benefit}}}}元补贴"
   }}
   ```

### 注意事项：
- 金额单位：统一转换为元（万元×10000）
- 对于有多种类型的政策（如零售/餐饮），在tiers中用type字段区分
- 如果有多轮补贴活动，提取最新或最完整的一轮
- 返回纯JSON，不要有其他说明文字

### 输出JSON：
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
                    {"role": "system", "content": "你是一个专业的政策规则提取专家，精通JSON格式化。"},
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
        cities = ['济南', '青岛', '烟台', '潍坊', '临沂', '济宁', '淄博', '枣庄', '德州', '威海']
        for city in cities:
            if city in text:
                return city
        return 'Unknown'

    def _extract_policy_type(self, text: str) -> str:
        """提取政策类型"""
        if '汽车' in text or '购车' in text:
            return '汽车补贴'
        elif '家电' in text:
            return '家电补贴'
        elif '消费券' in text:
            return '消费券'
        elif '保险' in text or '首保' in text:
            return '保险补贴'
        elif '餐饮' in text:
            return '餐饮券'
        elif '零售' in text:
            return '零售券'
        else:
            return 'Policy'