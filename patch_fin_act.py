"""
补丁脚本：为 step1 CSV 补充 n_cashflow_fin_act（筹资活动现金流净额）
用法：python patch_fin_act.py 300418.SZ
"""
import sys
import time
import pandas as pd
import tushare as ts
from config import TUSHARE_TOKEN

pro = ts.pro_api(TUSHARE_TOKEN)

ts_code = sys.argv[1] if len(sys.argv) > 1 else "300418.SZ"
csv_path = f"data/{ts_code.replace('.','_')}_step1_cashflow.csv"

df = pd.read_csv(csv_path)
print(f"读取 {csv_path}，共 {len(df)} 行，现有列：{list(df.columns)}")

if "n_cashflow_fin_act" in df.columns:
    print("已存在 n_cashflow_fin_act，无需补丁")
    sys.exit(0)

# 尝试拉取筹资活动净额（Tushare 实际字段名为 n_cash_flows_fnc_act）
fields = "ts_code,end_date,report_type,n_cash_flows_fnc_act"
df_fin = pro.cashflow_vip(ts_code=ts_code, report_type="1", fields=fields)
time.sleep(0.3)
if df_fin.empty:
    df_fin = pro.cashflow(ts_code=ts_code, report_type="1", fields=fields)
    time.sleep(0.3)

if df_fin.empty:
    print("无法获取筹资活动数据，退出")
    sys.exit(1)

df_fin = df_fin[df_fin["end_date"].str.endswith("1231")].copy()
df_fin = df_fin.drop_duplicates(subset="end_date", keep="first")
# 重命名为 skill2 期望的字段名
df_fin = df_fin.rename(columns={"n_cash_flows_fnc_act": "n_cashflow_fin_act"})
df_fin = df_fin[["end_date", "n_cashflow_fin_act"]]
print(f"获取到 {len(df_fin)} 条筹资活动数据")

# 合并
df["end_date"] = df["end_date"].astype(str)
df_fin["end_date"] = df_fin["end_date"].astype(str)
df = df.merge(df_fin, on="end_date", how="left")
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"已补充写入 n_cashflow_fin_act，保存至 {csv_path}")
print(df[["year","n_cashflow_act","n_cashflow_inv_act","n_cashflow_fin_act"]].to_string())
