"""
分析测试结果并生成报告
"""
import json
import sys

def analyze_results(json_file):
    """分析测试结果JSON文件"""

    with open(json_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    print("=" * 100)
    print("20个问题测试结果分析")
    print("=" * 100)

    for result in results:
        qid = result['id']
        question = result['question']
        category = result['category']
        metadata = result.get('metadata', {})

        print(f"\n{'='*100}")
        print(f"问题 {qid:2d} | 类别: {category:20s}")
        print(f"{'='*100}")
        print(f"问题: {question}")
        print(f"\n路由: {metadata.get('route', 'N/A')}")

        # 显示意图信息
        intent_info = metadata.get('intent', {})
        if intent_info:
            print(f"意图: {intent_info.get('intent', 'N/A')}")
            print(f"子意图: {intent_info.get('sub_intent', 'N/A')}")
            print(f"置信度: {intent_info.get('confidence', 'N/A')}")

        # 显示改写后的查询
        rewritten = metadata.get('rewritten_query', '')
        if rewritten:
            print(f"\n改写查询: {rewritten[:200]}{'...' if len(rewritten) > 200 else ''}")

        # 重要：这里需要从原始API响应中获取message字段
        # 由于我们的测试脚本保存的是answer字段（为空），我们无法恢复原始回答
        # 但我们可以分析元数据中的信息

        # 分析不同类型的处理结果
        if category in ['dialogue', 'faq_cache', 'clarify']:
            print(f"\n处理方式: 对话/FAQ/澄清")

        elif category == 'knowledge':
            doc_count = metadata.get('doc_count', 0)
            doc_origins = metadata.get('doc_origins', [])
            print(f"\n检索到文档数: {doc_count}")
            print(f"文档来源: {', '.join(set(doc_origins))}")

        elif category == 'graph':
            method = metadata.get('method', 'N/A')
            print(f"\n图谱方法: {method}")

        elif category == 'rule_engine':
            if 'engine_result' in metadata:
                engine_result = metadata['engine_result']
                print(f"\n规则引擎结果:")
                print(f"  状态: {engine_result.get('status', 'N/A')}")
                print(f"  最终结果: {engine_result.get('final_result', 'N/A')}")

                # 显示计算细节
                calc_details = engine_result.get('calculation_details', {})
                if calc_details and 'result' in calc_details:
                    res = calc_details['result']
                    print(f"  价格: ¥{res.get('price', 0)}")
                    print(f"  能效等级: {res.get('energy_level', '无')}")
                    print(f"  补贴比例: {res.get('rate', 0)*100}%")
                    print(f"  原始补贴: ¥{res.get('raw_subsidy', 0)}")
                    print(f"  最终补贴: ¥{res.get('final_subsidy', 0)}")

        elif category == 'text2sql':
            print(f"\nText2SQL查询")

        elif category in ['workflow', 'workflow+vision']:
            print(f"\n工作流处理")
            requires_parallel = intent_info.get('requires_parallel', False)
            chains = intent_info.get('chains', [])
            print(f"  需要并行: {requires_parallel}")
            print(f"  处理链: {', '.join(chains)}")

        # 显示置信度
        confidence = metadata.get('confidence', 0)
        print(f"\n最终置信度: {confidence:.2%}")

        # 会话上下文
        conv_context = metadata.get('conversation_context', {})
        if conv_context:
            print(f"会话上下文: 使用历史={conv_context.get('history_used', False)}, "
                  f"历史轮次={conv_context.get('history_turns', 0)}")

    # 统计摘要
    print(f"\n\n{'='*100}")
    print("统计摘要")
    print(f"{'='*100}\n")

    # 按类别统计
    categories = {}
    routes = {}
    intents = {}

    for result in results:
        cat = result['category']
        metadata = result.get('metadata', {})
        route = metadata.get('route', 'N/A')
        intent_info = metadata.get('intent', {})
        intent = intent_info.get('intent', 'N/A')

        categories[cat] = categories.get(cat, 0) + 1
        routes[route] = routes.get(route, 0) + 1
        intents[intent] = intents.get(intent, 0) + 1

    print("按类别分布:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:20s}: {count:2d} 个问题")

    print("\n按路由分布:")
    for route, count in sorted(routes.items(), key=lambda x: -x[1]):
        print(f"  {route:20s}: {count:2d} 次")

    print("\n按意图分布:")
    for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
        print(f"  {intent:20s}: {count:2d} 次")

    # 置信度统计
    confidences = [result.get('metadata', {}).get('confidence', 0) for result in results]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    print(f"\n置信度统计:")
    print(f"  平均置信度: {avg_conf:.2%}")
    print(f"  最高置信度: {max(confidences):.2%}")
    print(f"  最低置信度: {min(confidences):.2%}")

    # 高/低置信度问题
    high_conf = [r for r in results if r.get('metadata', {}).get('confidence', 0) >= 0.8]
    low_conf = [r for r in results if r.get('metadata', {}).get('confidence', 0) < 0.5]

    print(f"\n  高置信度(>=80%): {len(high_conf)} 个问题")
    print(f"  低置信度(<50%):  {len(low_conf)} 个问题")

    if low_conf:
        print(f"\n低置信度问题:")
        for r in low_conf:
            conf = r.get('metadata', {}).get('confidence', 0)
            print(f"    Q{r['id']:2d} ({conf:.1%}): {r['question'][:50]}...")

if __name__ == '__main__':
    json_file = sys.argv[1] if len(sys.argv) > 1 else 'test_results_20251115_094255.json'
    analyze_results(json_file)
