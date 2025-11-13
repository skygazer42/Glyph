import requests
import json
import time

API_URL = "http://localhost:8000/api/agent/chat"

test_cases = [
    # 测试对话路由
    {"id": 1, "question": "你好", "expected": "dialogue"},
    {"id": 2, "question": "谢谢，再见", "expected": "dialogue"},
    
    # 测试知识库路由  
    {"id": 3, "question": "家电以旧换新补贴是多少", "expected": "knowledge"},
    {"id": 4, "question": "济南汽车补贴政策", "expected": "knowledge"},
    
    # 测试澄清路由
    {"id": 5, "question": "这个怎么样", "expected": "clarify"},
    
    # 测试规则计算
    {"id": 6, "question": "买15万的新能源车补贴多少钱", "expected": "rule_engine"},
]

print("="*60)
print("测试基本路由功能")
print("="*60)

for test in test_cases:
    print(f"\n测试 {test['id']}: {test['question']}")
    
    try:
        resp = requests.post(API_URL, json={
            "message": test["question"],
            "session_id": f"test_{test['id']}",
            "user_id": "test"
        }, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            actual_route = data.get("metadata", {}).get("route", "unknown")
            success_mark = "✅" if actual_route == test["expected"] else "❌"
            print(f"  {success_mark} 路由: {actual_route} (期望: {test['expected']})")
            print(f"  回复: {data.get('message', '')[:100]}...")
        else:
            print(f"  ❌ HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    time.sleep(1)

print("\n" + "="*60)
print("测试完成")
