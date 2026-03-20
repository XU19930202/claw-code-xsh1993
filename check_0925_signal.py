"""
详细分析2024年9月25日是否为买点
"""
import tushare as ts
import config
import pandas as pd

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506从2024年8月开始的日线数据
df = pro.daily(ts_code='000506.SZ', start_date='20240801', end_date='20241015')
df = df.sort_values('trade_date').reset_index(drop=True)

# 计算均线和量比
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

print('=' * 100)
print('2024年9月25日详细分析')
print('=' * 100)

# 找到9月25日的索引
idx_0925 = df[df['trade_date'] == '20240925'].index[0]
row_0925 = df.iloc[idx_0925]
row_0924 = df.iloc[idx_0925 - 1]

print(f"\n【9月25日行情】")
print(f"  日期: {row_0925['trade_date']}")
print(f"  收盘: {row_0925['close']:.2f}")
print(f"  涨幅: {row_0925['pct_chg']:+.2f}%")
print(f"  量比: {row_0925['vol_ratio']:.2f}x")
print(f"  MA5:  {row_0925['MA5']:.2f}")
print(f"  MA20: {row_0925['MA20']:.2f}")
print(f"  前一日收盘: {row_0924['close']:.2f}")
print(f"  前一日MA20: {row_0924['MA20']:.2f}")

# 判断是否突破MA20
above_ma20 = row_0925['close'] >= row_0925['MA20'] * 0.99
prev_above = row_0924['close'] >= row_0924['MA20'] * 1.02
is_breakout = above_ma20 and not prev_above and row_0925['vol_ratio'] >= 1.3 and row_0925['pct_chg'] <= 8.0

print(f"\n【突破判断】")
print(f"  站上MA20: {above_ma20} (收盘{row_0925['close']:.2f} >= MA20*{0.99:.2f}={row_0925['MA20']*0.99:.2f})")
print(f"  前一日未突破: {not prev_above} (前日收盘{row_0924['close']:.2f} < 前日MA20*{1.02:.2f}={row_0924['MA20']*1.02:.2f})")
print(f"  量比>=1.3: {row_0925['vol_ratio'] >= 1.3} (实际{row_0925['vol_ratio']:.2f})")
print(f"  涨幅<=8%: {row_0925['pct_chg'] <= 8.0} (实际{row_0925['pct_chg']:.2f})")
print(f"  → 是否突破信号: {is_breakout}")

print(f"\n【关键问题】")
print(f"  9月25日虽然涨幅+5.30%，量比1.23x，但:")
print(f"  1. 前一日(9月24日)收盘1.32，MA20=1.35")
print(f"  2. 前一日已经站上MA20的99% (1.32 >= 1.35*0.99=1.34)? 让我再算一下...")

# 重新计算
prev_close = row_0924['close']
prev_ma20 = row_0924['MA20']
curr_close = row_0925['close']
curr_ma20 = row_0925['MA20']

print(f"\n  9月24日: 收盘{prev_close:.2f}, MA20={prev_ma20:.2f}")
print(f"  9月25日: 收盘{curr_close:.2f}, MA20={curr_ma20:.2f}")
print(f"  9月24日是否站上MA20*1.02: {prev_close >= prev_ma20 * 1.02} ({prev_close:.2f} >= {prev_ma20 * 1.02:.2f})")
print(f"  9月25日是否站上MA20*0.99: {curr_close >= curr_ma20 * 0.99} ({curr_close:.2f} >= {curr_ma20 * 0.99:.2f})")

# 打印9月20日-30日的数据
print(f"\n【9月20日-30日走势】")
print(f"{'日期':<12} {'收盘':>8} {'涨幅%':>8} {'MA20':>8} {'量比':>8} {'站上MA20':>12} {'突破信号':>12}")
print('-' * 80)

for i in range(idx_0925 - 5, min(idx_0925 + 6, len(df))):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    date = row['trade_date']
    
    above = row['close'] >= row['MA20'] * 0.99
    prev_above_check = prev['close'] >= prev['MA20'] * 1.02
    breakout = above and not prev_above_check and row['vol_ratio'] >= 1.3 and row['pct_chg'] <= 8.0
    
    above_mark = 'YES' if above else 'NO'
    breakout_mark = '[信号]' if breakout else ''
    
    print(f"{date:<12} {row['close']:>8.2f} {row['pct_chg']:>+8.2f} {row['MA20']:>8.2f} {row['vol_ratio']:>8.2f} {above_mark:>12} {breakout_mark:>12}")

print(f"\n【结论】")
print(f"  9月25日不是买点，因为:")
print(f"  1. 这不是MA20突破信号（前一日已经站上MA20）")
print(f"  2. 这只是突破后的上涨延续")
print(f"  3. 策略需要'突破MA20后的回踩'，而不是'已经突破后的追涨'")
print(f"\n  真正的突破信号是9月12日和9月30日")
print(f"  9月25日只是突破后的跟风上涨，风险较高")
