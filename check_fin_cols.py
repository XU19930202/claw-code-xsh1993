import tushare as ts
import sys
sys.path.insert(0, r'C:\Users\Lenovo\WorkBuddy\20260311213700')
from config import TUSHARE_TOKEN

pro = ts.pro_api(TUSHARE_TOKEN)

# 不指定 fields，看看全字段返回什么
df = pro.cashflow(ts_code="300418.SZ", report_type="1")
print("cashflow 接口所有列：")
print(list(df.columns))
print("\n筹资相关字段：")
fin_cols = [c for c in df.columns if 'fin' in c.lower() or 'cashflow_f' in c.lower()]
print(fin_cols)
if not df.empty:
    row = df[df['end_date'].str.endswith('1231')].head(3)
    print(row[['end_date'] + fin_cols])
