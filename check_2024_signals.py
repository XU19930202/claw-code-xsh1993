"""
分析2024年11月到2025年7月期间为什么没有触发交易
"""
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta

# 设置Tushare
pro = ts.pro_api('d0de5cd3a0c8a3d2876451e5dde3ce260b23e80e2e8d9878a0f8a05e')

ts_code = '000506.SZ'

# 获取2024年11月到2025年7月的数据
start_date = '20241101'
end_date = '20250731'

print(f"分析 {ts_code} 从 {start_date} 到 {end_date} 的行情")
print("="*80)

# 获取日线数据
df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
df = df.sort_values('trade_date').reset_index(drop=True)

# 获取换手率数据
try:
    basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if not basic_df.empty:
        basic_df = basic_df.sort_values('trade_date').reset_index(drop=True)
        df = df.merge(basic_df[['trade_date', 'turnover_rate']], on='trade_date', how='left')
except Exception as e:
    print(f"获取换手率失败: {e}")
    df['turnover_rate'] = None

# 计算MA20
df['close'] = df['close'].astype(float)
df['MA20'] = df['close'].rolling(20).mean()
df['vol'] = df['vol'].astype(float)
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']
df['pct_chg'] = df['pct_chg'].astype(float)

print(f"\n数据范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
print(f"价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
print(f"涨幅: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.1f}%")

# 检查每个月的突破信号
print("\n" + "="*80)
print("每月突破信号检查（ST股逻辑：换手率≥5%视为放量）")
print("="*80)

df['year_month'] = df['trade_date'].str[:6]
months = df['year_month'].unique()

for month in sorted(months):
    month_df = df[df['year_month'] == month].copy()
    if len(month_df) < 5:
        continue
    
    month_start = month_df['close'].iloc[0]
    month_end = month_df['close'].iloc[-1]
    month_pct = (month_end / month_start - 1) * 100
    
    print(f"\n【{month}】价格: {month_start:.2f} → {month_end:.2f} ({month_pct:+.1f}%)")
    
    # 检查突破信号
    signals = []
    for i in range(21, len(month_df)):
        row = month_df.iloc[i]
        prev = month_df.iloc[i-1]
        
        if pd.isna(row['MA20']):
            continue
        
        # ST股逻辑：换手率≥5%视为放量
        turnover_rate = row.get('turnover_rate', 0) if pd.notna(row.get('turnover_rate')) else 0
        volume_ok = turnover_rate >= 5.0 if pd.notna(turnover_rate) else row['vol_ratio'] >= 1.3
        
        # 突破条件
        if (row['close'] > row['MA20'] and 
            prev['close'] <= prev['MA20'] * 1.02 and
            volume_ok and
            row['pct_chg'] <= 8.0):
            
            vol_display = f"换手{turnover_rate:.2f}%" if pd.notna(turnover_rate) and turnover_rate > 0 else f"量比{row['vol_ratio']:.2f}x"
            signals.append(f"  {row['trade_date']} | {row['close']:.2f} 涨{row['pct_chg']:+.1f}% {vol_display}")
    
    if signals:
        print("  突破信号:")
        for s in signals:
            print(s)
    else:
        print("  无突破信号")
    
    # 检查为什么没信号
    if not signals:
        # 检查是否一直在MA20上方运行
        above_ma20 = (month_df['close'] > month_df['MA20']).sum()
        total = len(month_df.dropna(subset=['MA20']))
        if total > 0:
            above_pct = above_ma20 / total * 100
            print(f"  统计: 在MA20上方运行 {above_pct:.0f}% 的时间")
        
        # 检查换手率分布
        if 'turnover_rate' in month_df.columns and month_df['turnover_rate'].notna().any():
            avg_turnover = month_df['turnover_rate'].mean()
            max_turnover = month_df['turnover_rate'].max()
            print(f"  换手率: 平均{avg_turnover:.2f}%, 最高{max_turnover:.2f}%")
            if max_turnover < 5.0:
                print(f"  ⚠️  最高换手率{max_turnover:.2f}% < 5%，无法触发突破信号！")

print("\n" + "="*80)
print("总结：为什么这期间没有交易？")
print("="*80)
