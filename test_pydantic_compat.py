#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 PolicyDocument 和 FinalAnswer 的 Pydantic v2 兼容性
"""

import sys
import io
from uuid import uuid4
from datetime import datetime

# 设置UTF-8编码输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from app.models.base import PolicyDocument, FinalAnswer, PolicyType

# 创建一个测试 PolicyDocument
test_doc = PolicyDocument(
    id=uuid4(),
    title="测试政策",
    content="这是测试内容",
    summary="摘要",
    source="测试机构",
    doc_type=PolicyType.SUBSIDY,
    publish_date=datetime.now(),
    relevant_departments=["部门1"],
    target_groups=["群体1"],
    regions=["地区1"],
    keywords=["关键词1"],
    metadata={"test": "value"}
)

print(f"✅ PolicyDocument 创建成功: {test_doc.title}")
print(f"类型: {type(test_doc)}")
print(f"ID: {test_doc.id}")

# 测试序列化
try:
    doc_dict = test_doc.model_dump()
    print(f"\n✅ PolicyDocument 序列化成功")
    print(f"序列化后的类型: {type(doc_dict)}")
except Exception as e:
    print(f"\n❌ PolicyDocument 序列化失败: {e}")
    import traceback
    traceback.print_exc()

# 创建 FinalAnswer
try:
    final_answer = FinalAnswer(
        query_id=uuid4(),
        answer="这是测试答案",
        sources=[test_doc],  # 传入 PolicyDocument 实例
        confidence=0.9,
        metadata={"test": "metadata"}
    )
    print(f"\n✅ FinalAnswer 创建成功")
    print(f"Sources 数量: {len(final_answer.sources)}")
    print(f"第一个source类型: {type(final_answer.sources[0])}")
except Exception as e:
    print(f"\n❌ FinalAnswer 创建失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 FinalAnswer 序列化
try:
    answer_dict = final_answer.model_dump()
    print(f"\n✅ FinalAnswer 序列化成功")
    print(f"序列化后的类型: {type(answer_dict)}")
    print(f"sources 类型: {type(answer_dict['sources'])}")
    if answer_dict['sources']:
        print(f"第一个source类型: {type(answer_dict['sources'][0])}")
except Exception as e:
    print(f"\n❌ FinalAnswer 序列化失败: {e}")
    import traceback
    traceback.print_exc()

# 测试从字典创建
try:
    print(f"\n测试从字典创建 FinalAnswer...")
    dict_data = {
        'query_id': uuid4(),
        'answer': '字典创建的答案',
        'sources': [doc_dict],  # 使用序列化后的字典
        'confidence': 0.8,
        'metadata': {'test': 'dict'}
    }
    final_from_dict = FinalAnswer(**dict_data)
    print(f"✅ 从字典创建 FinalAnswer 成功")
except Exception as e:
    print(f"❌ 从字典创建 FinalAnswer 失败: {e}")
    import traceback
    traceback.print_exc()
