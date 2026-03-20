#!/usr/bin/env python3
"""测试并行回测基本功能"""

import sys
import os
import pandas as pd

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("测试并行回测基本功能...")
print("=" * 60)

try:
    # 导入并行脚本中的函数
    from batch_backtest_parallel import backtest_worker, _calc_capture
    
    # 创建一个测试任务
    task = {
        'ts_code': '300502.SZ',  # 使用缓存中已有的股票
        'name': '新易盛',
        'industry': '通信设备',
        'price_change': 25.0,  # 模拟25%上涨
        'max_gain': 35.0,
        'board_name': '创业板',
        'start_date': '20240101',
        'end_date': '20251231',
        'initial_capital': 200000,
    }
    
    print(f"测试股票: {task['ts_code']} {task['name']}")
    print(f"预期股价变化: {task['price_change']}%")
    
    # 测试backtest_worker
    print("\n测试backtest_worker...")
    result = backtest_worker(task)
    
    print("\n回测结果:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # 测试捕获率计算函数
    print("\n测试捕获率计算...")
    test_cases = [
        (15.0, 10.0),   # 上涨+盈利，捕获率66.7%
        (15.0, -5.0),   # 上涨+亏损
        (-10.0, 5.0),   # 下跌+盈利
        (-10.0, -4.0),  # 下跌+亏损，亏损少于跌幅一半
        (-10.0, -8.0),  # 下跌+亏损，亏损多于跌幅一半
        (0.5, 2.0),     # 股价持平，策略盈利
    ]
    
    for price_change, strategy_return in test_cases:
        capture = _calc_capture(strategy_return, price_change)
        print(f"  股价{price_change:+.1f}% | 策略{strategy_return:+.1f}% → 场景:{capture['scenario']} 合格:{capture['passed']} 捕获率:{capture['capture_ratio']}")
    
    # 检查缓存文件
    cache_file = os.path.join('backtest_cache', '300502_SZ.parquet')
    if os.path.exists(cache_file):
        print(f"\n缓存文件存在: {cache_file}")
        df = pd.read_parquet(cache_file)
        print(f"  数据行数: {len(df)}")
        print(f"  日期范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
        print(f"  列名: {', '.join(df.columns.tolist())}")
    else:
        print(f"\n警告: 缓存文件不存在，需要先下载数据")
        
except Exception as e:
    print(f"\n测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")