"""
分析002656在2024年11月-2025年2月期间的信号情况
"""
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout_strategy_v5 import prepare_data, scan_signals, StrategyConfig, BoardConfig, detect_board
import tushare as ts
import config

# 获取数据
ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

print("正在获取002656数据...")
start_str = '20240101'
end_str = '20260319'

df = pro.daily(ts_code='002656.SZ', start_date=start_str, end_date=end_str)
df = df.sort_values('trade_date').reset_index(drop=True)

# 获取复权因子
adj_df = pro.adj_factor(ts_code='002656.SZ', start_date=start_str, end_date=end_str)
if not adj_df.empty:
    adj_df = adj_df.sort_values('trade_date').reset_index(drop=True)
    df = df.merge(adj_df[['trade_date', 'adj_factor']], on='trade_date', how='left')
    df['adj_factor'] = df['adj_factor'].ffill().bfill()
    latest_adj = df['adj_factor'].iloc[-1]
    df['close_adj'] = df['close'] * df['adj_factor'] / latest_adj
else:
    df['close_adj'] = df['close']

# 重命名列以匹配策略期望的格式
df = df.rename(columns={
    'trade_date': '交易日期',
    'close': '收盘价(元)',
    'close_adj': '收盘价(前复权)(元)',
    'open': '开盘价(元)',
    'high': '最高价(元)',
    'low': '最低价(元)',
    'vol': '成交量(万股)',
    'pct_chg': '涨跌幅(%)'
})
df['换手率(%)'] = 0  # 默认值

stock, idx_map = prepare_data(df)

# 扫描信号
board = detect_board('002656')
cfg = StrategyConfig()
all_signals = scan_signals(stock, cfg, board)

print("=" * 100)
print("002656 信号池分析")
print("=" * 100)

# 找到2024年11月到2025年2月期间的信号
start_date = '2024-11-01'
end_date = '2025-02-28'

print(f"\n【完整信号池】共{len(all_signals)}个信号：")
for si, stype in all_signals:
    r = stock.iloc[si]
    d = str(r['交易日期'])[:10]
    type_str = "突破" if stype == 'breakout' else "回踩"
    print(f"  {d} | 收盘{r['close']:.2f} 涨{r['pct']:+.1f}% | [{type_str}]")

print(f"\n【{start_date} 至 {end_date} 期间的信号】")
count = 0
for si, stype in all_signals:
    r = stock.iloc[si]
    d = str(r['交易日期'])[:10]
    if start_date <= d <= end_date:
        count += 1
        type_str = "突破" if stype == 'breakout' else "回踩"
        ma20 = r['MA20']
        
        # 计算MA20斜率
        if si >= 20:
            ma20_20ago = stock.iloc[si-20]['MA20']
            if pd.notna(ma20_20ago) and ma20_20ago > 0:
                slope = (ma20 - ma20_20ago) / ma20_20ago * 100
            else:
                slope = 0
        else:
            slope = 0
        
        print(f"  {d} | 收盘{r['close']:.2f} MA20:{ma20:.2f} "
              f"MA20斜率(20天):{slope:+.1f}% | [{type_str}]")

if count == 0:
    print("  该期间无信号触发")

# 查看这段时间的股价走势
print(f"\n【{start_date} 至 {end_date} 股价走势】")
mask = (stock['交易日期'] >= start_date) & (stock['交易日期'] <= end_date)
period_df = stock[mask]
if len(period_df) > 0:
    print(f"  期间开盘: {period_df.iloc[0]['close']:.2f}")
    print(f"  期间收盘: {period_df.iloc[-1]['close']:.2f}")
    print(f"  期间涨幅: {(period_df.iloc[-1]['close'] / period_df.iloc[0]['close'] - 1) * 100:+.1f}%")
    print(f"  最高价: {period_df['close'].max():.2f}")
    print(f"  最低价: {period_df['close'].min():.2f}")
    
    # 查看MA20走势
    print(f"\n【MA20走势】")
    print(f"  期初MA20: {period_df.iloc[0]['MA20']:.2f}")
    print(f"  期末MA20: {period_df.iloc[-1]['MA20']:.2f}")
    ma20_change = (period_df.iloc[-1]['MA20'] / period_df.iloc[0]['MA20'] - 1) * 100
    print(f"  MA20变化: {ma20_change:+.1f}%")
