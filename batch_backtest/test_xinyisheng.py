#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新易盛（300502.SZ）回测脚本
"""

import os
import sys
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta

# 添加父目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入回测函数
from breakout_strategy_v5_patched import backtest

def backtest_xinyisheng():
    """回测新易盛股票"""
    print("=" * 60)
    print("新易盛（300502.SZ）回测报告")
    print("=" * 60)
    
    # 设置参数
    ts_code = "300502.SZ"  # 新易盛
    code_only = "300502"
    stock_name = "新易盛"
    
    # 设置回测日期范围
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365*2)).strftime("%Y%m%d")  # 最近2年
    
    print(f"回测范围: {start_date} - {end_date}")
    print(f"股票代码: {ts_code} ({stock_name})")
    print()
    
    # 初始化Tushare Pro
    try:
        pro = ts.pro_api()
        print("[OK] Tushare Pro API连接成功")
    except Exception as e:
        print(f"[ERROR] Tushare Pro API连接失败: {e}")
        return
    
    # 获取日线数据
    print("下载日线数据...")
    try:
        daily_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if daily_df.empty:
            print(f"[ERROR] 未获取到{stock_name}的日线数据")
            return
            
        print(f"[OK] 获取到{daily_df.shape[0]}个交易日数据")
        
    except Exception as e:
        print(f"[ERROR] 获取日线数据失败: {e}")
        return
    
    # 获取换手率数据
    print("下载换手率数据...")
    try:
        basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                  fields='trade_date,turnover_rate,volume_ratio')
        
        print(f"[OK] 获取到换手率数据: {basic_df.shape[0]}行")
        
    except Exception as e:
        print(f"[ERROR] 获取换手率数据失败: {e}")
        basic_df = None
    
    # 准备数据
    print("准备回测数据...")
    
    # 重命名列（适配回测函数）
    column_mapping = {
        'ts_code': 'ts_code',
        'trade_date': '交易日期',
        'open': '开盘价(元)',
        'high': '最高价(元)',
        'low': '最低价(元)',
        'close': '收盘价(元)',
        'vol': '成交量(万股)',  # 注意：Tushare的vol是手，后面会转换为万股
        'amount': '成交额(万元)',
        'pct_chg': '涨跌幅(%)'
    }
    
    df = daily_df.rename(columns=column_mapping)
    
    # 转换成交量单位：手 → 万股
    df['成交量(万股)'] = df['成交量(万股)'] / 100
    
    # 转换日期格式
    df['交易日期'] = pd.to_datetime(df['交易日期'], format='%Y%m%d')
    
    # 添加前复权收盘价列（简化处理，与前收盘价相同）
    df['收盘价(前复权)(元)'] = df['收盘价(元)']
    
    # 合并换手率数据
    if basic_df is not None and not basic_df.empty:
        basic_df['交易日期'] = pd.to_datetime(basic_df['trade_date'], format='%Y%m%d')
        df = df.merge(basic_df[['交易日期', 'turnover_rate', 'volume_ratio']], 
                     on='交易日期', how='left')
        df['换手率(%)'] = df['turnover_rate'].fillna(0)
    else:
        df['换手率(%)'] = 0
    
    print(f"[OK] 数据准备完成，总数据行数: {df.shape[0]}")
    print()
    
    # 执行回测
    print("执行回测...")
    try:
        trades = backtest(
            stock_df=df,
            code=code_only,
            index_df=None,  # 不使用指数数据
            verbose=True,   # 显示详细日志
            stock_name=stock_name
        )
        
        print("=" * 60)
        print("回测结果")
        print("=" * 60)
        
        if trades:
            # 计算总收益
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.pnl > 0)
            losing_trades = total_trades - winning_trades
            total_pnl = sum(t.pnl for t in trades)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
            
            # 计算策略表现
            print(f"交易总数: {total_trades} 笔")
            print(f"胜率: {winning_trades}/{total_trades} = {winning_trades/total_trades*100:.1f}%")
            print(f"盈亏比: {total_pnl:.2f}% (总收益)")
            print(f"平均单笔收益: {avg_pnl:.2f}%")
            print()
            
            # 显示详细交易记录
            print("详细交易记录:")
            print("-" * 80)
            for i, trade in enumerate(trades):
                trade_type = "买入" if trade.pnl >= 0 else "卖出"
                pnl_sign = "+" if trade.pnl >= 0 else ""
                print(f"{i+1:2d}. {trade.signal_date}: {trade_type}@{trade.buy_price:.2f}")
                print(f"    退出: {trade.exit_date} @{trade.exit_price:.2f} | 持有天数: {trade.days}")
                print(f"    收益: {pnl_sign}{trade.pnl:.2f}% | 最大收益: {trade.max_pnl:.2f}%")
                print()
            
            print("-" * 80)
            
            # 策略总结
            if total_pnl > 0:
                print(f"[+] 策略表现: 盈利，总收益 {total_pnl:.2f}%")
            else:
                print(f"[-] 策略表现: 亏损，总收益 {total_pnl:.2f}%")
                
        else:
            print("在回测期间没有生成交易信号")
            
    except Exception as e:
        print(f"[ERROR] 回测执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("回测完成")
    print("=" * 60)

if __name__ == "__main__":
    backtest_xinyisheng()