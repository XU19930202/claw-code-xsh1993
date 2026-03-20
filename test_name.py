import tushare as ts
import config
import pandas as pd

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 测试名称查询
df = pro.namechange(ts_code='000506.SZ')
print('名称变更记录:')
print(df[['name', 'start_date', 'end_date']].head(10))

# 测试特定日期
query_date = pd.Timestamp('2024-10-01')
df['start_date'] = pd.to_datetime(df['start_date'], format='%Y%m%d')
df['end_date'] = pd.to_datetime(df['end_date'].fillna('20991231'), format='%Y%m%d')

for _, row in df.iterrows():
    if row['start_date'] <= query_date <= row['end_date']:
        print(f"2024-10-01 的名称是: {row['name']}")
        break
