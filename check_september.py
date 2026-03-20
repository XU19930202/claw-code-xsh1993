import pandas as pd
import tushare as ts
import config
from datetime import datetime, timedelta

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506在2024年8-10月的数据（往前多取20天用于计算MA20）
df = pro.daily(ts_code='000506.SZ', start_date='20240801', end_date='20241010')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA20
df['ma20'] = df['close'].rolling(20).mean()
df['ma20_slope'] = (df['ma20'] - df['ma20'].shift(5)) / df['ma20'].shift(5) * 100  # 5日斜率

# 计算量比
df['vol_ma20'] = df['vol'].rolling(20).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma20']

print('2024年9月模式B检查（趋势回踩条件）：')
print('=' * 80)
for i, row in df.iterrows():
    if row['trade_date'] >= pd.Timestamp('2024-09-18') and row['trade_date'] <= pd.Timestamp('2024-09-29'):
        close = row['close']
        ma20 = row['ma20']
        pct = row['pct_chg']
        slope = row['ma20_slope']
        vol_ratio = row['vol_ratio']
        
        # 模式B条件检查
        above_ma20 = close > ma20 * 0.98 if pd.notna(ma20) else False
        had_decline = pct < 0
        extreme_shrink = vol_ratio < 0.5 if pd.notna(vol_ratio) else False
        
        date_str = row['trade_date'].strftime('%m-%d')
        ma20_threshold = ma20 * 0.98 if pd.notna(ma20) else 0
        print(f"{date_str} | Close:{close:.2f} MA20:{ma20:.2f} Chg:{pct:+.1f}%")
        print(f"  Above MA20(0.98x): {above_ma20} ({close:.2f} vs {ma20_threshold:.2f})")
        print(f"  Had decline: {had_decline} | Extreme shrink: {extreme_shrink} (vol_ratio {vol_ratio:.2f})")
        print(f"  MA20 slope(5d): {slope:.2f}%")
        print()
