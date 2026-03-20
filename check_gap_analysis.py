"""
分析2024年11月到2025年7月期间为什么没有触发交易
使用backtest_stock.py的数据获取方式
"""
import sys
sys.path.insert(0, 'c:/Users/Lenovo/WorkBuddy/20260311213700')

from backtest_stock import fetch_stock_data
import pandas as pd
from datetime import datetime

# 删除重复的导入
# from datetime import datetime  # 已在上面的导入中包含

ts_code = '000506.SZ'

print(f"分析 {ts_code} 2024年11月到2025年7月期间的信号情况")
print("="*80)

# 获取数据
df = fetch_stock_data(ts_code, start_date=datetime(2024, 7, 1))

# 筛选2024年11月到2025年7月
df['date'] = pd.to_datetime(df['交易日期'])
mask = (df['date'] >= '2024-11-01') & (df['date'] <= '2025-07-31')
period_df = df[mask].copy()

print(f"\n数据范围: {period_df['date'].min().strftime('%Y-%m-%d')} ~ {period_df['date'].max().strftime('%Y-%m-%d')}")
print(f"交易日数: {len(period_df)} 天")
print(f"价格: {period_df['close'].iloc[0]:.2f} → {period_df['close'].iloc[-1]:.2f}")
print(f"涨幅: {(period_df['close'].iloc[-1] / period_df['close'].iloc[0] - 1) * 100:.1f}%")

# 计算MA20
period_df['MA20'] = period_df['close'].rolling(20).mean()
period_df['vol_ma5'] = period_df['成交量(万股)'].rolling(5).mean()
period_df['vol_ratio'] = period_df['成交量(万股)'] / period_df['vol_ma5']

# 检查每个月的情况
period_df['year_month'] = period_df['date'].dt.strftime('%Y-%m')
months = period_df['year_month'].unique()

print("\n" + "="*80)
print("每月行情与信号分析")
print("="*80)

for month in sorted(months):
    month_df = period_df[period_df['year_month'] == month].copy()
    if len(month_df) < 5:
        continue
    
    month_start = month_df['close'].iloc[0]
    month_end = month_df['close'].iloc[-1]
    month_high = month_df['close'].max()
    month_low = month_df['close'].min()
    month_pct = (month_end / month_start - 1) * 100
    
    print(f"\n【{month}】")
    print(f"  价格: {month_start:.2f} → {month_end:.2f} (高{month_high:.2f} 低{month_low:.2f}) 涨幅:{month_pct:+.1f}%")
    
    # 检查突破信号（ST股逻辑：换手率≥5%）
    signals = []
    for i in range(21, len(month_df)):
        row = month_df.iloc[i]
        prev = month_df.iloc[i-1]
        
        if pd.isna(row['MA20']):
            continue
        
        # ST股逻辑
        turnover_rate = row.get('换手率(%)', 0) if pd.notna(row.get('换手率(%)')) else 0
        volume_ok = turnover_rate >= 5.0 if pd.notna(turnover_rate) and turnover_rate > 0 else row['vol_ratio'] >= 1.3
        
        # 突破条件
        if (row['close'] > row['MA20'] and 
            prev['close'] <= prev['MA20'] * 1.02 and
            volume_ok and
            row['涨跌幅(%)'] <= 8.0):
            
            vol_display = f"换手{turnover_rate:.2f}%" if pd.notna(turnover_rate) and turnover_rate > 0 else f"量比{row['vol_ratio']:.2f}x"
            signals.append(f"    {row['date'].strftime('%m-%d')} | 收{row['close']:.2f} 涨{row['涨跌幅(%)']:+.1f}% {vol_display}")
    
    if signals:
        print(f"  突破信号 ({len(signals)}个):")
        for s in signals[:5]:  # 最多显示5个
            print(s)
        if len(signals) > 5:
            print(f"    ... 还有{len(signals)-5}个")
    else:
        print("  突破信号: 无")
        
        # 分析为什么没有信号
        above_ma20 = (month_df['close'] > month_df['MA20']).sum()
        total_valid = month_df['MA20'].notna().sum()
        if total_valid > 0:
            above_pct = above_ma20 / total_valid * 100
            print(f"  分析: 在MA20上方运行 {above_pct:.0f}% 的时间")
            
        if above_pct > 80:
            print(f"  [!] 股价一直在MA20上方强势运行，没有'突破'机会！")
        elif above_pct < 20:
            print(f"  [!] 股价一直在MA20下方弱势运行，无法突破！")
        
        # 检查换手率
        if '换手率(%)' in month_df.columns and month_df['换手率(%)'].notna().any():
            avg_turnover = month_df['换手率(%)'].mean()
            max_turnover = month_df['换手率(%)'].max()
            print(f"  换手率: 平均{avg_turnover:.2f}%, 最高{max_turnover:.2f}%")
            if max_turnover < 5.0:
                print(f"  [!] 最高换手率{max_turnover:.2f}% < 5%，无法触发放量突破！")

print("\n" + "="*80)
print("【核心问题分析】")
print("="*80)

# 检查整体趋势
overall_start = period_df['close'].iloc[0]
overall_end = period_df['close'].iloc[-1]
print(f"\n1. 整体趋势：{overall_start:.2f} → {overall_end:.2f} (+{(overall_end/overall_start-1)*100:.0f}%)")

# 检查MA20关系
above_count = (period_df['close'] > period_df['MA20']).sum()
total_count = period_df['MA20'].notna().sum()
if total_count > 0:
    above_ratio = above_count / total_count * 100
    print(f"2. MA20关系：在MA20上方运行 {above_ratio:.1f}% 的时间")
    
    if above_ratio > 70:
        print("   → 股价太强了！一直在MA20上方，没有'突破'的机会")
        print("   → 策略需要'从下方突破MA20'才能触发信号")

# 检查换手率分布
if '换手率(%)' in period_df.columns and period_df['换手率(%)'].notna().any():
    high_turnover = (period_df['换手率(%)'] >= 5.0).sum()
    total_turnover = period_df['换手率(%)'].notna().sum()
    if total_turnover > 0:
        high_ratio = high_turnover / total_turnover * 100
        print(f"\n3. 换手率：≥5%的天数占 {high_ratio:.1f}%")
        if high_ratio < 10:
            print("   → 换手率太低！无法满足ST股突破条件（换手≥5%）")

print("\n" + "="*80)
