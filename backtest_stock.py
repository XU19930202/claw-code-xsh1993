#!/usr/bin/env python3
"""
股票回测入口脚本
用法: python backtest_stock.py <股票代码或名称>

示例:
    python backtest_stock.py 601689
    python backtest_stock.py 拓普集团
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# 添加项目目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout_strategy_v5 import backtest, print_summary, detect_board
import tushare as ts
import config


def get_ts_code(code_or_name: str) -> str:
    """
    将股票代码或名称转换为ts_code格式
    """
    ts.set_token(config.TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    # 如果已经是代码格式（纯数字）
    if code_or_name.isdigit():
        code = code_or_name
        # 自动补全交易所后缀
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"
        elif code.startswith('4') or code.startswith('8'):
            return f"{code}.BJ"
        else:
            return code
    
    # 如果是名称，查询ts_code
    try:
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        match = df[df['name'] == code_or_name]
        if not match.empty:
            return match.iloc[0]['ts_code']
        # 尝试模糊匹配
        match = df[df['name'].str.contains(code_or_name, na=False)]
        if not match.empty:
            print(f"找到匹配: {match.iloc[0]['name']} ({match.iloc[0]['ts_code']})")
            return match.iloc[0]['ts_code']
    except Exception as e:
        print(f"查询股票名称失败: {e}")
    
    return code_or_name


def fetch_stock_data(ts_code: str, days: int = 180) -> pd.DataFrame:
    """
    获取股票历史行情数据
    """
    config = Config()
    ts.set_token(config.tushare_token)
    pro = ts.pro_api()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    end_str = end_date.strftime('%Y%m%d')
    start_str = start_date.strftime('%Y%m%d')
    
    print(f"正在获取 {ts_code} 的行情数据...")
    
    # 获取日线数据
    df = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
    
    if df.empty:
        raise ValueError(f"未获取到 {ts_code} 的数据")
    
    # 按日期排序
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    # 计算前复权价格
    # 获取最新复权因子
    adj_df = pro.adj_factor(ts_code=ts_code, start_date=start_str, end_date=end_str)
    if not adj_df.empty:
        adj_df = adj_df.sort_values('trade_date').reset_index(drop=True)
        df = df.merge(adj_df[['trade_date', 'adj_factor']], on='trade_date', how='left')
        df['adj_factor'] = df['adj_factor'].fillna(method='ffill').fillna(method='bfill')
        
        # 计算前复权价格
        latest_adj = df['adj_factor'].iloc[-1]
        df['close_adj'] = df['close'] * df['adj_factor'] / latest_adj
        df['open_adj'] = df['open'] * df['adj_factor'] / latest_adj
        df['high_adj'] = df['high'] * df['adj_factor'] / latest_adj
        df['low_adj'] = df['low'] * df['adj_factor'] / latest_adj
    else:
        df['close_adj'] = df['close']
        df['open_adj'] = df['open']
        df['high_adj'] = df['high']
        df['low_adj'] = df['low']
    
    # 重命名列以匹配策略要求
    df['交易日期'] = pd.to_datetime(df['trade_date'])
    df['收盘价(元)'] = df['close']
    df['收盘价(前复权)(元)'] = df['close_adj']
    df['开盘价(元)'] = df['open_adj']
    df['最高价(元)'] = df['high_adj']
    df['最低价(元)'] = df['low_adj']
    df['涨跌幅(%)'] = df['pct_chg']
    df['成交量(万股)'] = df['vol'] / 100  # 手 -> 万股
    
    return df


def fetch_index_data(days: int = 180) -> pd.DataFrame:
    """
    获取上证指数数据
    """
    config = Config()
    ts.set_token(config.tushare_token)
    pro = ts.pro_api()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    end_str = end_date.strftime('%Y%m%d')
    start_str = start_date.strftime('%Y%m%d')
    
    df = pro.index_daily(ts_code='000001.SH', start_date=start_str, end_date=end_str)
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    df['交易日期'] = pd.to_datetime(df['trade_date'])
    df['涨跌幅(%)'] = df['pct_chg']
    
    return df


def main():
    if len(sys.argv) < 2:
        print("用法: python backtest_stock.py <股票代码或名称>")
        print("示例: python backtest_stock.py 601689")
        print("      python backtest_stock.py 拓普集团")
        sys.exit(1)
    
    code_or_name = sys.argv[1]
    
    print("=" * 85)
    print(f"  MA20突破回踩策略 v5 - 股票回测")
    print("=" * 85)
    
    # 获取ts_code
    ts_code = get_ts_code(code_or_name)
    code = ts_code.split('.')[0]
    
    print(f"\n股票代码: {ts_code}")
    
    try:
        # 获取数据
        stock_df = fetch_stock_data(ts_code)
        index_df = fetch_index_data()
        
        print(f"数据范围: {stock_df['交易日期'].min().strftime('%Y-%m-%d')} ~ {stock_df['交易日期'].max().strftime('%Y-%m-%d')}")
        print(f"共 {len(stock_df)} 个交易日")
        
        # 执行回测
        trades = backtest(stock_df, code, index_df, verbose=True)
        
        # 打印汇总
        print_summary(trades)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
