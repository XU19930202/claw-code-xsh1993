import pandas as pd
import tushare as ts
import config

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289在2024年9-11月的数据
df = pro.daily(ts_code='600289.SH', start_date='20240901', end_date='20241130')
df = df.sort_values('trade_date')
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 计算MA5和MA20
df['MA5'] = df['close'].rolling(5).mean()
df['MA20'] = df['close'].rolling(20).mean()
df['pct'] = df['pct_chg']

# 找到买入日
buy_date = '2024-10-14'
buy_price = 1.43
buy_idx = df[df['trade_date'] == buy_date].index[0]

print(f'模拟第3笔交易出场逻辑（买入@{buy_price}）')
print('=' * 80)

# 模拟run_exit逻辑
phase = 'MA20'
below_ma5_count = 0
gap_streak = 0
cfg_trend_days = 3
cfg_trend_gap = 1.03

for k in range(buy_idx + 1, min(buy_idx + 60, len(df))):
    r = df.iloc[k]
    d = r['trade_date'].strftime('%m-%d')
    m5 = r['MA5'] if pd.notna(r['MA5']) else 0
    m20 = r['MA20'] if pd.notna(r['MA20']) else 0
    pct = r['pct']
    close = r['close']
    pnl = (close - buy_price) / buy_price * 100
    above_ma5 = close >= m5 if m5 > 0 else False
    above_ma20 = close >= m20 if m20 > 0 else False
    gap = (m5 / m20 - 1) * 100 if m20 > 0 else 0
    below_ma5_close = close < m5 if m5 > 0 else False
    is_up_day = pct > 0
    
    # 阶段切换逻辑
    if m5 > m20 * cfg_trend_gap:
        gap_streak += 1
    else:
        gap_streak = 0
    
    if phase == 'MA20' and gap_streak >= cfg_trend_days and above_ma5:
        phase = 'MA5'
        below_ma5_count = 0
        print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [UP] 进入MA5阶段")
        continue
    
    if phase == 'MA5' and m5 < m20:
        phase = 'MA20'
        below_ma5_count = 0
        gap_streak = 0
        print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [DOWN] 回退MA20阶段")
        continue
    
    # MA5阶段出场逻辑（带动态止损）
    if phase == 'MA5':
        # 浮盈保护：浮盈越大，对MA5越宽容
        ma5_stop_days = 2  # 默认连续2天破MA5止损
        tier_info = ""
        
        if pnl >= 15:  # profit_tier_2
            print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [PROFIT] 浮盈>15%，回退MA20阶段")
            phase = 'MA20'
            below_ma5_count = 0
            continue
        elif pnl >= 8:  # profit_tier_1
            ma5_stop_days = 4  # 放宽到4天
            tier_info = "(放宽4天)"
        
        if not above_ma5:
            if is_up_day:
                print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [OK] 破MA5但收阳")
                below_ma5_count = 0
            else:
                below_ma5_count += 1
                if below_ma5_count >= ma5_stop_days:
                    print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [EXIT] 连续{ma5_stop_days}天破MA5且收阴{tier_info}")
                    break
                else:
                    print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [!] 破MA5+收阴 第{below_ma5_count}天{tier_info}")
        else:
            if below_ma5_count > 0:
                print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [OK] 站回MA5")
            below_ma5_count = 0
    
    # MA20阶段出场逻辑
    elif phase == 'MA20':
        if not above_ma20:
            print(f"{d} | {close:.2f} {pct:+.1f}% | +{pnl:.1f}% | [!] 破MA20")
