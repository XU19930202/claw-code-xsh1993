"""
分析2024年11月29日信号为什么没有触发买入
"""
import sys
sys.path.insert(0, 'c:/Users/Lenovo/WorkBuddy/20260311213700')

from backtest_stock import fetch_stock_data
from breakout_strategy_v5 import scan_signals, run_entry, StrategyConfig, BoardConfig, prepare_data
import pandas as pd
from datetime import datetime

ts_code = '000506.SZ'

print(f"分析 2024-11-29 信号为什么没有触发买入")
print("="*80)

# 获取数据
df = fetch_stock_data(ts_code, start_date=datetime(2024, 7, 1))

# 准备数据
stock, idx_map = prepare_data(df)

# 找到2024-11-29的索引
target_date = '2024-11-29'
signal_idx = None
for idx, row in stock.iterrows():
    if str(row['交易日期'])[:10] == target_date:
        signal_idx = idx
        break

if signal_idx is None:
    print(f"未找到 {target_date} 的数据")
    exit()

print(f"\n信号日 {target_date} 数据:")
signal_row = stock.iloc[signal_idx]
print(f"  收盘价: {signal_row['close']:.2f}")
print(f"  涨幅: {signal_row['pct']:+.2f}%")
print(f"  MA20: {signal_row['MA20']:.2f}")
print(f"  量比: {signal_row['vol_ratio']:.2f}x")
if 'turnover_rate' in signal_row and pd.notna(signal_row['turnover_rate']):
    print(f"  换手率: {signal_row['turnover_rate']:.2f}%")
print(f"  股价/MA20: {signal_row['close']/signal_row['MA20']:.2f}x")

# 检查后续追踪期
cfg = StrategyConfig()
board = BoardConfig('主板', 0.1, -0.1, 8.0, 3.0)

print(f"\n追踪期分析 (共{cfg.track_days}天):")
print("-"*80)

for day_n in range(1, cfg.track_days + 1):
    j = signal_idx + day_n
    if j >= len(stock):
        break
    
    r = stock.iloc[j]
    d = str(r['交易日期'])[:10]
    m20 = r['MA20'] if pd.notna(r['MA20']) else signal_row['MA20']
    v = r['vol_ratio'] if pd.notna(r['vol_ratio']) else 1.0
    pct = r['pct']
    close = r['close']
    above = close >= m20 * cfg.ma20_tolerance
    
    # ST股判断
    is_st = True  # 强制ST股
    
    # 极度缩量判断（分档）
    turnover_rate = r.get('turnover_rate') if 'turnover_rate' in r else None
    if is_st and pd.notna(turnover_rate):
        if close > m20 * 1.5:
            shrink_threshold = 2.0
            mode = "趋势"
        else:
            shrink_threshold = 3.0
            mode = "突破"
        extreme_shrink = turnover_rate < shrink_threshold
        vol_display = f"换手{turnover_rate:.2f}% ({mode}<{shrink_threshold}%)"
    else:
        extreme_shrink = v < cfg.extreme_shrink
        vol_display = f"量比{v:.2f}x"
    
    # 企稳判断
    had_decline = False  # 简化处理
    momentum_decay = (0 <= pct <= signal_row['pct'] / 2) if signal_row['pct'] > 0 else False
    stabilized = had_decline or momentum_decay
    
    status = []
    if not above:
        status.append("破MA20")
    if extreme_shrink:
        status.append("极度缩量")
    if stabilized:
        status.append("企稳")
    
    status_str = " | ".join(status) if status else "-"
    
    print(f"Day{day_n:2d} {d} | 收{close:.2f} {pct:+.2f}% {vol_display} | 站上MA20:{above} | {status_str}")

print("\n" + "="*80)
print("结论：")
print("如果期间没有'极度缩量+企稳'的组合，就不会触发买入")
print("="*80)
