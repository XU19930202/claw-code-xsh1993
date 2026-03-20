import sys
import pandas as pd
import tushare as ts
import config
from datetime import datetime

# 导入回测函数
from breakout_strategy_v5_patched import backtest, get_board_type, get_params

ts.set_token(config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取600289数据
print("正在获取数据...")
df = pro.daily(ts_code='600289.SH', start_date='20240101', end_date='20260319')
df = df.sort_values('trade_date')

# 获取上证指数数据
index_df = pro.index_daily(ts_code='000001.SH', start_date='20240101', end_date='20260319')
index_df = index_df.sort_values('trade_date')

print("开始回测...")
trades = backtest(df, '600289', index_df, verbose=True, stock_name='ST信通')

print("\n\n交易汇总:")
for t in trades:
    if '2024-10-14' in str(t.signal_date):
        print(f"\n=== 第{t.n}笔（10月14日信号）===")
        print(f"买入: {t.buy_date} @ {t.buy_price}")
        print(f"卖出: {t.exit_date} @ {t.exit_price}")
        print(f"收益: {t.pnl:.2f}%")
        print(f"退出原因: {t.exit_reason}")
        print("详细日志:")
        for log in t.log:
            print(f"  {log}")
