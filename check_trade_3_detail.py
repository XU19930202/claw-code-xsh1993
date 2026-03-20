import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289在2024年10月的数据
df = pro.daily(ts_code='600289.SH', start_date='20241014', end_date='20241110')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA5和MA20
df['ma5'] = df['close'].rolling(5).mean()
df['ma20'] = df['close'].rolling(20).mean()

buy_price = 1.43

print('第3笔交易详细分析（买入@1.43）：')
print('=' * 80)

for i, row in df.iterrows():
    date_str = row['trade_date'].strftime('%m-%d')
    close = row['close']
    pnl = (close - buy_price) / buy_price * 100
    ma5 = row['ma5']
    
    # 判断tier
    if pnl >= 15:
        tier = '>15% (MA20)'
    elif pnl >= 8:
        tier = '8-15% (4天)'
    else:
        tier = '<8% (2天)'
    
    # 判断是否破MA5
    below_ma5 = close < ma5 if pd.notna(ma5) else False
    status = '破MA5' if below_ma5 else 'OK'
    
    print(f"{date_str} | Close:{close:.2f} PnL:{pnl:+.2f}% | {tier} | {status}")
