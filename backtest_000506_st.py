#!/usr/bin/env python3
"""
回测000506在*ST中润期间(2024.1.1-2025.6.27)使用ST策略
"""
import sys
sys.path.insert(0, '.')
from backtest_stock import backtest, print_summary
from datetime import datetime
import tushare as ts
import pandas as pd
import config

# 设置日期范围
start_date = datetime(2024, 1, 1)
end_date = datetime(2025, 6, 27)

code = '000506'
ts_code = '000506.SZ'

print('=' * 85)
print(f'  MA20突破回踩策略 v5 - 股票回测 (ST策略)')
print('=' * 85)
print(f'\n股票代码: {ts_code}')
print(f'回测期间: 2024-01-01 ~ 2025-06-27 (*ST中润期间)')

# 获取数据
ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取股票数据
df = pro.daily(ts_code=ts_code, start_date='20240101', end_date='20250627')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算技术指标
df['MA5'] = df['close'].rolling(window=5).mean()
df['MA20'] = df['close'].rolling(window=20).mean()
df['MA60'] = df['close'].rolling(window=60).mean()
df['prev_close'] = df['close'].shift(1)
df['vol_ma5'] = df['vol'].rolling(window=5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']
df['成交量(万股)'] = df['vol'] / 10000

# 获取换手率数据
try:
    daily_basic = pro.daily_basic(ts_code=ts_code, start_date='20240101', end_date='20250627')
    daily_basic = daily_basic.sort_values('trade_date')
    daily_basic['trade_date'] = pd.to_datetime(daily_basic['trade_date'])
    df = df.merge(daily_basic[['trade_date', 'turnover_rate']], on='trade_date', how='left')
    df['换手率(%)'] = df['turnover_rate']
except:
    df['换手率(%)'] = 0.0  # 如果没有换手率数据，设为0

# 重命名列
df['收盘价(元)'] = df['close']
df['收盘价(前复权)(元)'] = df['close']
df['开盘价(元)'] = df['open']
df['最高价(元)'] = df['high']
df['最低价(元)'] = df['low']
df['成交量(股)'] = df['vol']
df['成交额(千元)'] = df['amount']
df['涨跌幅(%)'] = df['pct_chg']
df['交易日期'] = df['trade_date']

start_str = df['交易日期'].min().strftime('%Y-%m-%d')
end_str = df['交易日期'].max().strftime('%Y-%m-%d')
print(f'数据范围: {start_str} ~ {end_str}')
print(f'共 {len(df)} 个交易日')

# 强制使用ST策略
stock_name = '*ST中润(历史)'
print(f'股票名称: {stock_name} (强制使用ST参数)')

# 执行回测
trades = backtest(df, code, None, verbose=True, stock_name=stock_name)
print_summary(trades)
