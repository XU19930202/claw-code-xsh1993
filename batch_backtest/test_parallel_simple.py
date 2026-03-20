#!/usr/bin/env python3
"""测试简化版并行脚本的单股票回测"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("测试简化版并行脚本...")
print("=" * 60)

# 直接测试backtest_worker_simple函数
try:
    import batch_backtest_parallel_simple as btp
    
    # 创建一个测试任务
    task = {
        'ts_code': '300211.SZ',
        'name': '亿通科技',
        'industry': '计算机',
        'price_change': -17.0,
        'max_gain': 25.0,
        'board_name': '创业板',
        'start_date': '20240101',
        'end_date': '20251231',
        'initial_capital': 200000,
    }
    
    print(f"测试股票: {task['ts_code']} {task['name']}")
    print(f"预期股价变化: {task['price_change']}%")
    
    # 测试backtest_worker_simple
    result = btp.backtest_worker_simple(task)
    
    print("\n回测结果:")
    print(f"状态: {result['status']}")
    print(f"策略收益: {result['strategy_return_pct']:.2f}%")
    print(f"交易数: {result['trade_count']}")
    print(f"场景: {result['scenario']}")
    print(f"是否合格: {result['passed']}")
    print(f"错误信息: {result['error_msg'] or '无'}")
    
    # 测试适配函数
    print("\n测试适配函数...")
    backtest_func = btp.get_adapted_backtest_function()
    simple_result = backtest_func(task['ts_code'], task['name'], task['start_date'], task['end_date'])
    
    print(f"适配函数状态: {simple_result['status']}")
    print(f"适配函数收益: {simple_result['strategy_return_pct']:.2f}%")
    
except Exception as e:
    print(f"测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")