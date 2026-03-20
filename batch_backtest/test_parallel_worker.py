#!/usr/bin/env python3
"""测试backtest_worker函数是否能正常工作"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 模拟一个任务
task = {
    'ts_code': '300211.SZ',
    'name': '亿通科技',
    'industry': '计算机',
    'price_change': -17.0,  # 股价下跌17%
    'max_gain': 25.0,      # 最高涨幅25%
    'board_name': '创业板',
    'start_date': '20240101',
    'end_date': '20251231',
    'initial_capital': 200000,
}

print("测试backtest_worker函数...")
print(f"股票: {task['ts_code']} {task['name']}")
print(f"预期股价变化: {task['price_change']}%")

# 导入batch_backtest_parallel模块
try:
    import batch_backtest_parallel as btp
    # 手动测试backtest_worker
    result = btp.backtest_worker(task)
    
    print("\n回测结果:")
    print(f"状态: {result['status']}")
    print(f"策略收益: {result['strategy_return_pct']:.2f}%")
    print(f"交易数: {result['trade_count']}")
    print(f"场景: {result['scenario']}")
    print(f"是否合格: {result['passed']}")
    print(f"错误信息: {result['error_msg'] or '无'}")
    
    # 检查是否有缓存数据
    cache_dir = btp.CACHE_DIR
    cache_file = cache_dir / f"{task['ts_code'].replace('.', '_')}.parquet"
    print(f"\n缓存文件: {cache_file}")
    print(f"缓存文件存在: {cache_file.exists()}")
    
except Exception as e:
    print(f"测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()