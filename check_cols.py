import pandas as pd
df = pd.read_csv('data/300418_SZ_step1_cashflow.csv')
print("列名：", list(df.columns))
print(df[['year','n_cashflow_act','n_cashflow_inv_act']].head(3))
