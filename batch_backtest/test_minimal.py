#!/usr/bin/env python3
"""最小化测试：测试一只股票的回测适配"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 创建一个简单的回测任务
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

print("测试并行回测适配...")
print("=" * 60)

# 直接测试backtest函数
try:
    from breakout_strategy_v5_patched import backtest
    from params import get_board_type, get_params
    
    print("1. 测试backtest函数导入... 成功")
    
    # 测试一个简单调用
    print("2. 测试简单的回测调用...")
    
    # 获取数据（简化测试）
    import tushare as ts
    import pandas as pd
    import config
    
    ts.set_token(config.TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    # 获取少量数据用于测试
    print("   获取测试数据...")
    stock_df_raw = pro.daily(ts_code=task['ts_code'], 
                            start_date='20240101', 
                            end_date='20240131',  # 只取一个月用于测试
                            fields='ts_code,trade_date,open,high,low,close,vol,amount')
    
    if stock_df_raw.empty:
        print("   获取数据失败")
    else:
        print(f"   获取到 {len(stock_df_raw)} 条数据")
        
        # 重命名列
        stock_df = stock_df_raw.copy()
        stock_df = stock_df.rename(columns={
            'trade_date': '交易日期',
            'open': '开盘价(元)',
            'high': '最高价(元)', 
            'low': '最低价(元)',
            'close': '收盘价(元)',
            'vol': '成交量(万股)',
            'amount': '成交额(万元)'
        })
        
        # 添加其他必需列
        stock_df['收盘价(前复权)(元)'] = stock_df['收盘价(元)']
        stock_df['涨跌幅(%)'] = 0.0  # 简化
        
        # 转换日期格式
        stock_df['交易日期'] = pd.to_datetime(stock_df['交易日期'], format='%Y%m%d')
        
        # 获取指数数据
        index_df_raw = pro.index_daily(ts_code='000001.SH', start_date='20240101', end_date='20240131',
                                      fields='ts_code,trade_date,close')
        index_df = index_df_raw.copy()
        index_df = index_df.rename(columns={'trade_date': '交易日期', 'close': '收盘价'})
        index_df['交易日期'] = pd.to_datetime(index_df['交易日期'], format='%Y%m%d')
        
        # 执行回测
        print("   执行回测...")
        code_only = task['ts_code'].split('.')[0]
        trades = backtest(
            stock_df=stock_df,
            code=code_only,
            index_df=index_df,
            verbose=False,
            stock_name=task['name']
        )
        
        print(f"   回测完成，生成 {len(trades) if trades else 0} 笔交易")
        
        if trades:
            print(f"   第一笔交易收益: {trades[0].pnl:.2f}%")
    
except ImportError as e:
    print(f"导入错误: {e}")
except Exception as e:
    print(f"测试错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("如果上述测试通过，说明适配基本正确")