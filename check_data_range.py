import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取最新数据
df = pro.daily(ts_code='000506.SZ', start_date='20250101', end_date='20261231')
df = df.sort_values('trade_date')
print(f"数据范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
print(f"\n最近10天:")
print(df[['trade_date', 'close', 'pct_chg']].tail(10).to_string())
