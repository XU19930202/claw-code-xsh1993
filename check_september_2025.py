import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取000506在2025年9月的数据
df = pro.daily(ts_code='000506.SZ', start_date='20250901', end_date='20251020')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA20
df['ma20'] = df['close'].rolling(20).mean()

# 计算量比
df['vol_ma20'] = df['vol'].rolling(20).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma20']

print('2025年9月25日-10月17日信号追踪检查：')
print('=' * 80)

# 9月25日信号追踪期（假设信号日是9月25日，追踪14天）
signal_date = pd.Timestamp('2025-09-25')
signal_pct = 2.0  # 假设信号日涨幅约2%
print(f"\n=== 9月25日信号追踪（信号日涨幅约{signal_pct}%）===")
print(f"过热阈值: {signal_pct * 0.8:.1f}% (信号日涨幅的80%)")

for i, row in df.iterrows():
    if row['trade_date'] >= signal_date and row['trade_date'] <= pd.Timestamp('2025-10-17'):
        date_str = row['trade_date'].strftime('%m-%d')
        pct = row['pct_chg']
        close = row['close']
        ma20 = row['ma20']
        vol_ratio = row['vol_ratio']
        
        # 检查条件
        overheat = pct > signal_pct * 0.8
        above_ma20 = close > ma20 * 0.98 if pd.notna(ma20) else False
        
        status = []
        if overheat:
            status.append("过热")
        if not above_ma20:
            status.append("破MA20")
        
        # 检查与MA20的距离
        ma20_distance = (close - ma20) / ma20 * 100 if pd.notna(ma20) and ma20 > 0 else 0
        
        status_str = ", ".join(status) if status else "正常"
        
        print(f"{date_str}: 收{close:.2f} 涨幅{pct:+.1f}% MA20:{ma20:.2f} 距MA20:{ma20_distance:+.1f}% | {status_str}")

# 9月29日信号追踪
signal_date2 = pd.Timestamp('2025-09-29')
signal_pct2 = 6.9  # 信号日涨幅
print(f"\n=== 9月29日信号追踪（信号日涨幅约{signal_pct2}%）===")
print(f"过热阈值: {signal_pct2 * 0.8:.1f}% (信号日涨幅的80%)")

for i, row in df.iterrows():
    if row['trade_date'] >= signal_date2 and row['trade_date'] <= pd.Timestamp('2025-10-17'):
        date_str = row['trade_date'].strftime('%m-%d')
        pct = row['pct_chg']
        close = row['close']
        ma20 = row['ma20']
        vol_ratio = row['vol_ratio']
        
        overheat = pct > signal_pct2 * 0.8
        above_ma20 = close > ma20 * 0.98 if pd.notna(ma20) else False
        
        status = []
        if overheat:
            status.append("过热")
        if not above_ma20:
            status.append("破MA20")
        
        # 检查与MA20的距离
        ma20_distance = (close - ma20) / ma20 * 100 if pd.notna(ma20) and ma20 > 0 else 0
        
        status_str = ", ".join(status) if status else "正常"
        
        print(f"{date_str}: 收{close:.2f} 涨幅{pct:+.1f}% MA20:{ma20:.2f} 距MA20:{ma20_distance:+.1f}% | {status_str}")
