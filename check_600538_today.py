#!/usr/bin/env python3
"""
600538 今日信号分析
"""
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from breakout_strategy_v5 import get_board_type, get_params, check_trend_pullback, check_extreme_shrink, check_above_ma20
import config

# 初始化Tushare
pro = ts.pro_api(config.TUSHARE_TOKEN)

ts_code = '600538.SH'

# 获取最近120天数据
df = pro.daily(ts_code=ts_code, start_date='20251001')
df = df.sort_values('trade_date').reset_index(drop=True)

# 获取换手率数据
df_basic = pro.daily_basic(ts_code=ts_code, start_date='20251001')
df_basic = df_basic.sort_values('trade_date').reset_index(drop=True)
df = df.merge(df_basic[['trade_date', 'turnover_rate']], on='trade_date', how='left')

# 计算均线
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['MA60'] = df['close'].rolling(60).mean()

# 计算量比
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

# 计算涨跌幅
df['pct'] = df['pct_chg']

# 获取最新数据
latest = df.iloc[-1]
prev = df.iloc[-2]

print('=' * 70)
print(f'[分析] {ts_code} 今日信号分析 | {latest["trade_date"]}')
print('=' * 70)
print(f'\n[价格] 当前价格: {latest["close"]:.2f}元')
print(f'[价格] 昨日收盘: {prev["close"]:.2f}元')
print(f'[价格] 今日涨跌: {latest["pct"]:+.2f}%')
print(f'[成交] 换手率: {latest["turnover_rate"]:.2f}%')
print(f'[成交] 量比: {latest["vol_ratio"]:.2f}x')
print(f'\n[均线] 均线状态:')
print(f'   MA5:  {latest["MA5"]:.2f}')
print(f'   MA20: {latest["MA20"]:.2f}')
print(f'   MA60: {latest["MA60"]:.2f}')

# 判断趋势
ma20_slope = (latest['MA20'] - df.iloc[-21]['MA20']) / df.iloc[-21]['MA20'] if len(df) >= 21 else 0
is_stage2 = latest['MA20'] > latest['MA60'] and latest['MA20'] > df.iloc[-21]['MA20']

print(f'\n[趋势] 趋势判断:')
print(f'   Stage 2 (MA20>MA60且上升): {"是" if is_stage2 else "否"}')
print(f'   MA20 20日斜率: {ma20_slope*100:.2f}%')

# 获取板块参数
p = get_params('main')

# 判断信号
close = latest['close']
ma20 = latest['MA20']
ma60 = latest['MA60']
ma20_20d_ago = df.iloc[-21]['MA20'] if len(df) >= 21 else None
vol_ratio = latest['vol_ratio']
turnover = latest['turnover_rate']

print(f'\n' + '=' * 70)
print('[信号检测]')
print('=' * 70)

# 1. 突破信号
volume_ok = vol_ratio >= p.signal_vol_ratio
breakthrough = close > ma20 and prev['close'] <= prev['MA20'] * 1.02
print(f'\n[1] MA20放量突破信号:')
print(f'   今日收盘 > MA20: {"是" if close > ma20 else "否"} ({close:.2f} vs {ma20:.2f})')
print(f'   昨日收盘 <= MA20*1.02: {"是" if prev["close"] <= prev["MA20"] * 1.02 else "否"}')
print(f'   量比 >= {p.signal_vol_ratio}: {"是" if volume_ok else "否"} ({vol_ratio:.2f}x)')
print(f'   涨幅 <= {p.signal_max_pct}%: {"是" if latest["pct"] <= p.signal_max_pct else "否"} ({latest["pct"]:.2f}%)')
is_breakout = breakthrough and volume_ok and latest["pct"] <= p.signal_max_pct
print(f'   => 突破信号: {"[触发]" if is_breakout else "[未触发]"}')

# 2. 趋势回踩信号
print(f'\n[2] 趋势回踩信号:')
pullback_ok = check_trend_pullback(p, close, ma20, ma60, ma20_20d_ago, vol_ratio, turnover)
print(f'   Stage 2趋势: {"是" if is_stage2 else "否"}')
print(f'   MA20斜率 >= {p.ma20_slope_min*100}%: {"是" if ma20_slope >= p.ma20_slope_min else "否"} ({ma20_slope*100:.2f}%)')
print(f'   股价接近MA20 (±5%): {"是" if ma20*0.95 <= close <= ma20*1.05 else "否"}')
print(f'   缩量 (量比 < {p.pullback_vol_ratio}): {"是" if vol_ratio < p.pullback_vol_ratio else "否"} ({vol_ratio:.2f}x)')
print(f'   => 回踩信号: {"[触发]" if pullback_ok else "[未触发]"}')

# 3. 极度缩量企稳
print(f'\n[3] 极度缩量企稳:')
shrink_ok = vol_ratio < p.shrink_vol_ratio
above_ma20 = close >= ma20 * p.ma20_tolerance
print(f'   量比 < {p.shrink_vol_ratio}: {"是" if shrink_ok else "否"} ({vol_ratio:.2f}x)')
print(f'   站上MA20: {"是" if above_ma20 else "否"}')
print(f'   => 缩量企稳: {"[是]" if (shrink_ok and above_ma20) else "[否]"}')

print(f'\n' + '=' * 70)
print('[结论]')
print('=' * 70)

signals = []
if is_breakout:
    signals.append('MA20放量突破')
if pullback_ok:
    signals.append('趋势回踩')
if shrink_ok and above_ma20:
    signals.append('极度缩量企稳')

if signals:
    print(f'[机会] 今日有信号: {", ".join(signals)}')
else:
    print('[观望] 今日无买入信号')
    print('\n[建议] 当前状态: 观望')
    if close < ma20:
        print(f'   - 股价低于MA20，等待突破或回踩企稳')
    elif vol_ratio >= p.shrink_vol_ratio:
        print(f'   - 量能未缩量，等待缩量企稳')
    elif not is_stage2:
        print(f'   - 趋势未确立，等待Stage 2形成')
