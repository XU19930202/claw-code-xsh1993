import tushare as ts
import pandas as pd
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取2025年9月数据
df = pro.daily(ts_code='000506.SZ', start_date='20250901', end_date='20251031')
if df.empty:
    print("2025年9月数据不存在，当前数据可能只到2025年或2026年初")
    
    # 检查2025年1月的数据
    df = pro.daily(ts_code='000506.SZ', start_date='20250101', end_date='20250131')
    if not df.empty:
        print(f"\n2025年1月数据存在: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        print("\n2025年1月走势:")
        df = df.sort_values('trade_date')
        print(df[['trade_date', 'close', 'pct_chg']].to_string())
else:
    df = df.sort_values('trade_date')
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    
    # 计算MA20
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA20_20days_ago'] = df['MA20'].shift(20)
    df['MA20_slope'] = (df['MA20'] - df['MA20_20days_ago']) / df['MA20_20days_ago'] * 100
    
    print("2025年9月-10月走势:")
    print(df[['trade_date', 'close', 'pct_chg', 'MA20', 'MA20_slope']].to_string())
