#!/usr/bin/env python3
"""分析2024年9月30日信号的追踪过程"""

import tushare as ts
import config
import pandas as pd
from datetime import datetime

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506从2024年9月30日开始的日线数据
df = pro.daily(ts_code='000506.SZ', start_date='20240930', end_date='20241115')
df = df.sort_values('trade_date').reset_index(drop=True)

# 计算指标
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

# 信号日数据
signal_row = df[df['trade_date'] == '20240930'].iloc[0]
signal_price = signal_row['close']
signal_pct = signal_row['pct_chg']

print('=' * 100)
print('2024年9月30日信号追踪分析')
print('=' * 100)
print(f"\n信号日: 2024-09-30")
print(f"  收盘价: {signal_price:.2f}")
print(f"  涨幅: {signal_pct:+.2f}%")
print(f"  MA20: {signal_row['MA20']:.2f}")
print(f"  量比: {signal_row['vol_ratio']:.2f}x")
print()

# 追踪14天
print('=' * 100)
print('14天追踪期详情')
print('=' * 100)
print(f"{'Day':<5} {'日期':<12} {'收盘':>8} {'涨幅%':>8} {'MA20':>8} {'量比':>8} {'状态':<30}")
print('-' * 100)

signal_idx = df[df['trade_date'] == '20240930'].index[0]
had_decline = False

for day in range(1, 15):
    idx = signal_idx + day
    if idx >= len(df):
        break
    
    row = df.iloc[idx]
    date = row['trade_date']
    close = row['close']
    pct = row['pct_chg']
    ma20 = row['MA20']
    vr = row['vol_ratio']
    
    # 判断是否站上MA20
    above_ma20 = close >= ma20 * 0.985
    
    # 判断是否经历过下跌
    if pct < -0.3:
        had_decline = True
    
    # 判断各种条件
    not_vol_up = vr < 1.2
    is_small_yang = 0 < pct <= 5.0
    is_doji = abs(close - row['open']) / close < 0.005 if close > 0 else False
    extreme_shrink = vr < 0.7
    momentum_decay = (0 <= pct <= signal_pct / 3) if signal_pct > 0 else False
    stabilized = had_decline or momentum_decay
    
    # 判断买入条件
    status = []
    if above_ma20 and extreme_shrink and stabilized:
        status.append("[极度缩量企稳] 可买入!")
    elif above_ma20 and not_vol_up and (is_small_yang or is_doji) and stabilized:
        status.append("[回踩/动能衰减] 可买入!")
    elif not above_ma20:
        status.append("[!破MA20]")
    elif pct > 5:
        status.append("[过热]")
    elif pct > 0 and vr >= 1.2:
        status.append("[放量上涨]")
    elif pct > 0 and not stabilized:
        status.append("[未企稳-无下跌/衰减]")
    else:
        status.append("[等企稳]")
    
    # 补充信息
    info = []
    if had_decline:
        info.append("已下跌")
    if stabilized:
        info.append("已企稳")
    if momentum_decay:
        info.append("动能衰减")
    
    status_str = " ".join(status) + " | " + " ".join(info)
    
    print(f"{day:<5} {date:<12} {close:>8.2f} {pct:>+8.2f} {ma20:>8.2f} {vr:>8.2f} {status_str:<30}")

print()
print('=' * 100)
print('结论分析')
print('=' * 100)
print("""
问题核心：股价连续涨停式上涨，没有出现"回踩企稳"的机会！

入场条件回顾：
1. 极度缩量企稳：量比<0.7 + 站上MA20 + 经历过下跌/动能衰减
2. 回踩确认：不放量(<1.2) + 小阳/十字星 + 站上MA20 + 经历过下跌
3. 动能衰减：涨幅≤信号日1/3 + 不放量 + 站上MA20

实际情况：
- Day1-Day14：股价从1.52涨到2.87，连续上涨
- 每天都是大涨(+4%到+5%)，没有出现"小阳/十字星"
- 量比从0.04到3.66，大部分时间不满足"极度缩量<0.7"
- 最关键：没有出现过"下跌"(had_decline=False)，所以不满足"stabilized"条件

为什么策略这样设计？
- 突破后不追涨，等回踩确认
- 如果一直不回踩，说明可能是假突破或一字板，风险高
- 放弃这种"买不到"的行情，等待更安全的入场点

后续：
- 11月29日出现下一个信号，但Day1就放量跌破MA20被放弃
- 直到2025年3月才真正捕捉到上涨行情
""")
