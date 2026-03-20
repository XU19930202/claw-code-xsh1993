#!/usr/bin/env python3
"""分析2024年9月30日信号的追踪过程"""

import tushare as ts
import config
import pandas as pd

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取更长的历史数据以计算MA20
df = pro.daily(ts_code='000506.SZ', start_date='20240801', end_date='20241115')
df = df.sort_values('trade_date').reset_index(drop=True)

# 计算指标
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

# 找到信号日
signal_idx = df[df['trade_date'] == '20240930'].index[0]
signal_row = df.iloc[signal_idx]
signal_price = signal_row['close']
signal_pct = signal_row['pct_chg']
signal_ma20 = signal_row['MA20']

print('=' * 110)
print('2024年9月30日信号追踪分析')
print('=' * 110)
print(f"\n信号日: 2024-09-30")
print(f"  收盘价: {signal_price:.2f}")
print(f"  涨幅: {signal_pct:+.2f}%")
print(f"  MA20: {signal_ma20:.2f}")
print(f"  量比: {signal_row['vol_ratio']:.2f}x")
print()

# 追踪14天
print('=' * 110)
print('14天追踪期详情 (2024-10-15 至 2024-11-01)')
print('=' * 110)
print(f"{'Day':<5} {'日期':<12} {'收盘':>8} {'涨幅%':>8} {'MA20':>8} {'量比':>8} {'站上MA20':>10} {'分析':<40}")
print('-' * 110)

had_decline = False
momentum_decay_triggered = False

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
    above_ma20 = close >= ma20 * 0.985 if pd.notna(ma20) else False
    above_str = "YES" if above_ma20 else "NO"
    
    # 判断是否经历过下跌
    if pct < -0.3:
        had_decline = True
    
    # 判断动能衰减
    momentum_decay = (0 <= pct <= signal_pct / 3) if signal_pct > 0 else False
    if momentum_decay:
        momentum_decay_triggered = True
    
    stabilized = had_decline or momentum_decay_triggered
    
    # 判断各种条件
    not_vol_up = vr < 1.2
    is_small_yang = 0 < pct <= 5.0
    is_doji = abs(close - row['open']) / close < 0.005 if close > 0 else False
    extreme_shrink = vr < 0.7
    
    # 分析状态
    analysis = []
    if above_ma20 and extreme_shrink and stabilized:
        analysis.append("[OK] 极度缩量企稳-可买入!")
    elif above_ma20 and not_vol_up and (is_small_yang or is_doji) and stabilized:
        analysis.append("[OK] 回踩/动能衰减-可买入!")
    elif not above_ma20:
        analysis.append("[X] 破MA20")
    elif not stabilized:
        if not had_decline and not momentum_decay_triggered:
            analysis.append("[WAIT] 未经历下跌/动能衰减")
        if pct > signal_pct / 3:
            analysis.append(f"[WAIT] 涨幅{pct:.1f}% > 信号日1/3({signal_pct/3:.1f}%)")
    elif pct > 5:
        analysis.append("[WAIT] 过热(涨幅>5%)")
    elif vr >= 1.2:
        analysis.append("[WAIT] 放量上涨")
    else:
        analysis.append("[WAIT] 等待")
    
    # 补充标记
    marks = []
    if had_decline:
        marks.append("[已跌]")
    if momentum_decay:
        marks.append("[动能衰减]")
    if stabilized:
        marks.append("[已企稳]")
    
    analysis_str = " | ".join(analysis) + " " + " ".join(marks)
    
    print(f"{day:<5} {date:<12} {close:>8.2f} {pct:>+8.2f} {ma20:>8.2f} {vr:>8.2f} {above_str:>10} {analysis_str:<40}")

print()
print('=' * 110)
print('核心问题总结')
print('=' * 110)
print("""
数据观察：
- 股价从1.52元(Day1)一路涨到2.87元(Day14)，接近翻倍！
- 每天都是大涨(+4.76%到+5.30%)，没有一天下跌
- 全程都站在MA20上方

为什么没触发买入？

1. [没有经历过下跌]
   - 14天内涨幅每天都是正的
   - had_decline = False
   - 不满足"回踩确认"的第一个条件

2. [没有出现动能衰减]
   - 信号日涨幅+4.32%，1/3约等于1.44%
   - 但后续每天涨幅都是4-5%，远大于1.44%
   - momentum_decay = False
   - 不满足"动能衰减"条件

3. [极度缩量条件不满足]
   - 极度缩量需要量比<0.7
   - 但实际量比在0.08-3.66之间波动
   - 大部分时间不满足

4. [小阳线条件不满足]
   - 小阳线要求涨幅<=5%
   - 虽然大部分满足，但前两个条件不满足，这个也没用

策略逻辑：
策略设计原则是"突破后不追涨，等回踩确认"。
这个信号的问题是一路上涨不回头，没有给"低吸"的机会。
从结果看确实错过了大行情，但按照策略规则，这种"买不到"的行情
本来就应该放弃，等待下一个更安全的入场点。

改进思考：
对于这种连续涨停的妖股，是否需要增加"追涨"机制？
比如：如果连续3天站上MA20且每天涨幅>3%，说明趋势很强，
可以考虑在Day3或Day4追入？
但这会增加风险，需要谨慎评估。
""")
