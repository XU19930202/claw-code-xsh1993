#!/usr/bin/env python3
"""检查002261的信号日期"""
import pandas as pd
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '.')
from breakout_strategy_v5 import detect_board, StrategyConfig
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
df['vol'] = df['vol'] / 100  # 转换为万股

# 扫描信号
cfg = StrategyConfig()
board = detect_board('002261')

# 计算MA和量比
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']
df['pct'] = df['pct_chg']

# 找出信号 - 使用与策略相同的逻辑
signals = []
for i in range(21, len(df)):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    ma20 = row['MA20']
    prev_ma20 = prev['MA20']
    vr = row['vol_ratio']
    
    if pd.isna(ma20) or pd.isna(vr):
        continue
    
    # 突破条件：今日收盘 > MA20，前日收盘 <= MA20*1.02
    # 量比 >= 门槛，涨幅 <= 板块上限
    if (row['close'] > ma20
            and prev['close'] <= prev_ma20 * 1.02
            and vr >= cfg.vol_min
            and row['pct'] <= board.signal_max_pct):
        signals.append({
            'date': row['交易日期'],
            'close': row['close'],
            'pct': row['pct'],
            'vol_ratio': row['vol_ratio']
        })

print('信号列表:')
for i, s in enumerate(signals):
    date_str = s['date'].strftime('%m-%d')
    print(f"{i+1}. {date_str} | {s['close']:.2f} 涨{s['pct']:+.1f}% 量比{s['vol_ratio']:.2f}x")

print()
print('检查7天内连续信号:')
for i in range(1, len(signals)):
    days_diff = (signals[i]['date'] - signals[i-1]['date']).days
    if days_diff <= 7:
        d1 = signals[i-1]['date'].strftime('%m-%d')
        d2 = signals[i]['date'].strftime('%m-%d')
        print(f"发现: {d1} 和 {d2} 相差{days_diff}天")
