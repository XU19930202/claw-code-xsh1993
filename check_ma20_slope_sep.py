import tushare as ts
import pandas as pd
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取2025年8-10月数据（需要往前20天计算MA20斜率）
df = pro.daily(ts_code='000506.SZ', start_date='20250801', end_date='20251031')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA20
df['MA20'] = df['close'].rolling(20).mean()

# 计算MA20的20天斜率（百分比）
df['MA20_20days_ago'] = df['MA20'].shift(20)
df['MA20_slope'] = (df['MA20'] - df['MA20_20days_ago']) / df['MA20_20days_ago'] * 100

print("000506 2025年9月-10月 MA20斜率分析（主板策略 ma20_slope_filter=0.05即5%）：")
print("=" * 90)
print(f"{'日期':<12} {'收盘':<8} {'MA20':<8} {'MA20斜率':<12} {'>5%?':<8} {'备注':<30}")
print("-" * 90)

for i, row in df.iterrows():
    if row['trade_date'] >= pd.Timestamp('2025-09-01'):
        date_str = row['trade_date'].strftime('%m-%d')
        slope = row['MA20_slope']
        
        if pd.notna(slope):
            above_threshold = '是' if slope >= 5.0 else '否'
        else:
            above_threshold = 'N/A'
        
        # 标记关键日期
        remark = ""
        if row['trade_date'] == pd.Timestamp('2025-09-25'):
            remark = "突破信号日"
        elif row['trade_date'] == pd.Timestamp('2025-09-29'):
            remark = "突破信号日"
        elif row['trade_date'] == pd.Timestamp('2025-10-09'):
            remark = "涨停+9.9%"
        elif row['trade_date'] == pd.Timestamp('2025-10-10'):
            remark = "涨停+7.3%"
        elif row['trade_date'] == pd.Timestamp('2025-10-13'):
            remark = "涨停+9.8%"
        
        slope_str = f"{slope:>+7.2f}%" if pd.notna(slope) else "    N/A"
        print(f"{date_str:<12} {row['close']:<8.2f} {row['MA20']:<8.2f} {slope_str:<12} {above_threshold:<8} {remark:<30}")
