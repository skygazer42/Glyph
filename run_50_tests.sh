#!/bin/bash
# 50问测试启动脚本

echo "=========================================="
echo "  50问综合测试 - 启动脚本"
echo "=========================================="
echo ""
echo "请选择测试模式:"
echo "  1) 快速测试 (并行执行, 简化输出)"
echo "  2) 完整测试 (顺序执行, 详细报告)"
echo "  3) 仅测试前10问 (调试用)"
echo ""
read -p "请输入选项 [1-3]: " choice

case $choice in
  1)
    echo ""
    echo "🚀 启动快速测试..."
    python3 test_50_quick.py
    ;;
  2)
    echo ""
    echo "📝 启动完整测试..."
    python3 test_50_comprehensive.py
    ;;
  3)
    echo ""
    echo "🔍 启动前10问测试..."
    python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')

from test_50_quick import QuickTestRunner, QUICK_TEST_CASES

async def test_first_10():
    runner = QuickTestRunner(max_concurrent=2)
    await runner.initialize()

    # 只测试前10个
    from test_50_quick import QUICK_TEST_CASES as cases
    runner.total = 10

    for i in range(0, 10, 2):
        batch = cases[i:min(i+2, 10)]
        await runner.run_batch(batch)
        print(f'进度: {runner.progress}/10')

    runner.print_summary()

asyncio.run(test_first_10())
"
    ;;
  *)
    echo "❌ 无效选项"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo "  测试完成!"
echo "=========================================="
