import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289在2024年9-11月的数据（往前多取20天用于计算MA20）
df = pro.daily(ts_code='600289.SH', start_date='20240901', end_date='20241130')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA5和MA20
df['ma5'] = df['close'].rolling(5).mean()
df['ma20'] = df['close'].rolling(20).mean()

buy_price = 1.43
buy_date = '2024-10-14'

print('第3笔交易阶段分析（买入@1.43）：')
print('=' * 80)
print("判断MA5阶段条件: MA5 > MA20 × 1.03 且股价 > MA5")
print('=' * 80)

gap_streak = 0
for i, row in df.iterrows():
    date_str = row['trade_date'].strftime('%m-%d')
    close = row['close']
    pct = row['pct_chg']
    ma5 = row['ma5']
    ma20 = row['ma20']
    
    if pd.notna(ma5) and pd.notna(ma20) and ma20 > 0:
        gap = (ma5 / ma20 - 1) * 100
        above_ma5 = close >= ma5
        
        # 判断是否满足MA5阶段条件
        if gap >= 3.0 and above_ma5:
            gap_streak += 1
            status = f"MA5阶段条件满足(连续{gap_streak}天)"
        else:
            if gap_streak > 0:
                status = f"MA5阶段中断"
            else:
                status = "MA20阶段"
            gap_streak = 0
        
        print(f"{date_str} | Close:{close:.2f} MA5:{ma5:.2f} MA20:{ma20:.2f} Gap:{gap:.1f}% | {status}")
    else:
        print(f"{date_str} | Close:{close:.2f} MA5/MA20未计算")
