import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289在2024年10月的数据
df = pro.daily(ts_code='600289.SH', start_date='20241014', end_date='20241130')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA5和MA20
df['ma5'] = df['close'].rolling(5).mean()
df['ma20'] = df['close'].rolling(20).mean()

print('2024年10月14日-11月 600289走势（第3笔交易期间）：')
print('=' * 80)

for i, row in df.iterrows():
    date_str = row['trade_date'].strftime('%m-%d')
    close = row['close']
    pct = row['pct_chg']
    ma5 = row['ma5']
    ma20 = row['ma20']
    
    # 检查是否破MA5
    below_ma5 = close < ma5 if pd.notna(ma5) else False
    below_ma5_str = 'Y' if below_ma5 else 'N'
    
    print(f"{date_str} | Close:{close:.2f} Chg:{pct:+.1f}% MA5:{ma5:.2f} MA20:{ma20:.2f} BelowMA5:{below_ma5_str}")
