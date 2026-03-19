#!/usr/bin/env python3
"""测试收紧条件逻辑"""
import pandas as pd
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '.')
from breakout_strategy_v5 import backtest, prepare_data, detect_board, StrategyConfig, scan_signals
import tushare as ts
import config

# 获取数据
ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

end_date = datetime.now()
start_date = datetime(2025, 1, 1)
end_str = end_date.strftime('%Y%m%d')
start_str = start_date.strftime('%Y%m%d')

df = pro.daily(ts_code='002261.SZ', start_date=start_str, end_date=end_str)
df = df.sort_values('trade_date').reset_index(drop=True)

adj_df = pro.adj_factor(ts_code='002261.SZ', start_date=start_str, end_date=end_str)
adj_df = adj_df.sort_values('trade_date').reset_index(drop=True)
df = df.merge(adj_df[['trade_date', 'adj_factor']], on='trade_date', how='left')
df['adj_factor'] = df['adj_factor'].ffill().bfill()

latest_adj = df['adj_factor'].iloc[-1]
df['close'] = df['close'] * df['adj_factor'] / latest_adj
df['open'] = df['open'] * df['adj_factor'] / latest_adj
df['high'] = df['high'] * df['adj_factor'] / latest_adj
df['low'] = df['low'] * df['adj_factor'] / latest_adj

df['交易日期'] = pd.to_datetime(df['trade_date'])
df['vol'] = df['vol'] / 100
df['pct'] = df['pct_chg']

# 计算MA和量比
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

# 扫描信号
cfg = StrategyConfig()
board = detect_board('002261')
all_signals = scan_signals(df, cfg, board)

print(f"总信号数: {len(all_signals)}")
print("\n信号日期列表:")
for i, si in enumerate(all_signals):
    row = df.iloc[si]
    print(f"{i+1}. {row['交易日期'].strftime('%m-%d')} | 收盘{row['close']:.2f} 涨{row['pct']:+.1f}%")

print("\n检查7天内连续信号:")
for i in range(1, len(all_signals)):
    curr_date = df.iloc[all_signals[i]]['交易日期']
    prev_date = df.iloc[all_signals[i-1]]['交易日期']
    days_diff = (curr_date - prev_date).days
    if days_diff <= 7:
        print(f"  信号{i}({prev_date.strftime('%m-%d')}) 和 信号{i+1}({curr_date.strftime('%m-%d')}) 相差{days_diff}天")

print("\n模拟信号历史记录过程:")
signal_history = []
for i, si in enumerate(all_signals):
    signal_date = df.iloc[si]['交易日期']
    
    # 检查收紧条件
    strict_mode = False
    if signal_history:
        recent_count = sum(1 for sig in signal_history 
                          if 0 < (signal_date - sig['date']).days <= 7)
        if recent_count >= 1:
            strict_mode = True
            print(f"  信号{i+1}({signal_date.strftime('%m-%d')}): [收紧] 7天内出现{recent_count+1}个信号")
        else:
            print(f"  信号{i+1}({signal_date.strftime('%m-%d')}): 正常")
    else:
        print(f"  信号{i+1}({signal_date.strftime('%m-%d')}): 正常（首个信号）")
    
    # 添加到历史
    signal_history.append({'date': signal_date, 'exit_type': '待处理'})
