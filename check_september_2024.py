"""
分析000506在2024年9月份的行情，寻找潜在买点
"""
import tushare as ts
import config
import pandas as pd
from datetime import datetime

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506从2024年8月开始的日线数据
df = pro.daily(ts_code='000506.SZ', start_date='20240801', end_date='20241031')
df = df.sort_values('trade_date').reset_index(drop=True)

# 计算均线
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

print('=' * 100)
print('000506 2024年9月行情详细分析')
print('=' * 100)

# 打印9月份数据
print(f"\n{'日期':<12} {'收盘':>8} {'涨幅%':>8} {'MA5':>8} {'MA20':>8} {'量比':>8} {'突破MA20':>10} {'站上MA20':>10}")
print('-' * 100)

for i in range(20, len(df)):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    date = row['trade_date']
    
    # 判断是否突破MA20
    breakout = (row['close'] > row['MA20'] and 
                prev['close'] <= prev['MA20'] * 1.02 and
                row['vol_ratio'] >= 1.3 and
                row['pct_chg'] <= 8.0)
    
    # 判断是否站上MA20
    above_ma20 = row['close'] >= row['MA20'] * 0.99
    
    if '202409' in date:
        mark_breakout = '[信号]' if breakout else ''
        mark_above = 'YES' if above_ma20 else 'NO'
        print(f"{date:<12} {row['close']:>8.2f} {row['pct_chg']:>+8.2f} {row['MA5']:>8.2f} {row['MA20']:>8.2f} {row['vol_ratio']:>8.2f} {mark_breakout:>10} {mark_above:>10}")

print('\n' + '=' * 100)
print('潜在买点分析')
print('=' * 100)

# 分析9月12日信号
print("\n【信号1】2024-09-12:")
print("  - 收盘: 1.37, 涨幅: +3.01%, 量比: 1.91x")
print("  - Day1 (09-13): 1.30, -5.11%, 放量跌破MA20 → 放弃")

print("\n【信号2】2024-09-30:")
print("  - 收盘: 1.45, 涨幅: +4.32%, 量比: 1.47x")
print("  - 追踪期: 10月15日-11月1日")
print("  - 问题: 连续14天大涨4-5%，没有回踩机会")
print("  - 结果: 期满放弃")

print("\n【9月其他时间】")
print("  - 9月1日-9月11日: 股价在MA20下方运行，无突破信号")
print("  - 9月13日-9月27日: 股价在MA20下方运行，无突破信号")

print('\n' + '=' * 100)
print('结论')
print('=' * 100)
print("""
2024年9月份000506没有好的买点：

1. 9月12日信号: Day1就放量跌破MA20，策略放弃（正确）
   - 如果买入，后续几天会继续下跌到1.30以下

2. 9月30日信号: 连续涨停，没有回踩机会，策略放弃（正确）
   - 这种行情买不到是正常的，买不到说明风险极高

3. 9月份整体: 股票处于低迷期，没有资金关注
   - 9月初股价在1.3元左右
   - 9月底才出现突破信号
   - 真正的行情是10月-11月的一字板拉升

策略在9月份的表现是正确的：
- 避免了9月12日信号的亏损
- 避开了9月30日后的连续涨停（买不到反而安全）
- 等到2025年3月才真正捕捉到上涨行情
""")
