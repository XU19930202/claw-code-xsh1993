import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289数据
df = pro.daily(ts_code='600289.SH', start_date='20240901', end_date='20241130')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['vol_ma5'] = df['vol'].rolling(5).mean()
df['vol_ratio'] = df['vol'] / df['vol_ma5']

# 找到10月25日数据
row = df[df['trade_date'] == '2024-10-25'].iloc[0]
print('2024-10-25 数据:')
print(f'  收盘: {row["close"]}')
print(f'  涨幅: {row["pct_chg"]}%')
print(f'  MA5: {row["MA5"]}')
print(f'  MA20: {row["MA20"]}')
print(f'  量比: {row["vol_ratio"]}')
print(f'  成交量: {row["vol"]}')

# 检查10月14日-10月25日的走势
print('\n10月14日-10月25日走势:')
buy_price = 1.43
for _, r in df[(df['trade_date'] >= '2024-10-14') & (df['trade_date'] <= '2024-10-25')].iterrows():
    pnl = (r['close'] - buy_price) / buy_price * 100
    print(f"{r['trade_date'].strftime('%m-%d')}: 收{r['close']:.2f} 涨幅{r['pct_chg']:+.1f}% 浮盈{pnl:+.1f}%")
