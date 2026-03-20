#!/usr/bin/env python3
"""
检查000506在2025年9月的MA20斜率
"""
import tushare as ts
import pandas as pd
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506数据
df = pro.daily(ts_code='000506.SZ', start_date='20250901', end_date='20251031')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA20
df['MA20'] = df['close'].rolling(20).mean()

# 计算MA20的20天斜率（百分比）
df['MA20_20days_ago'] = df['MA20'].shift(20)
df['MA20_slope'] = (df['MA20'] - df['MA20_20days_ago']) / df['MA20_20days_ago'] * 100

print("000506 2025年9月-10月 MA20斜率分析：")
print("=" * 80)
print(f"{'日期':<12} {'收盘':<8} {'MA20':<8} {'MA20斜率':<12} {'>5%?':<8}")
print("-" * 80)

for i, row in df.iterrows():
    if pd.notna(row['MA20_slope']):
        date_str = row['trade_date'].strftime('%m-%d')
        slope = row['MA20_slope']
        above_threshold = '是' if slope >= 5.0 else '否'
        print(f"{date_str:<12} {row['close']:<8.2f} {row['MA20']:<8.2f} {slope:>+8.2f}%    {above_threshold:<8}")
