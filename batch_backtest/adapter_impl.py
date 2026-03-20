#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
适配函数实现 - 根据我们的backtest接口定制

核心：修改 run_single_backtest() 函数，让它正确调用我们的回测逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
import traceback

# 导入我们的回测模块
import tushare as ts
import config
from breakout_strategy_v5_patched import backtest, print_summary, detect_board
from params import get_board_type, get_params


def run_single_backtest(ts_code, stock_name, start_date, end_date):
    """
    运行单只股票回测，返回标准化结果
    
    适配我们的backtest函数接口：
    backtest(stock_df, code, index_df, verbose=True, stock_name='') -> List[Trade]
    
    返回值格式：
    {
        'ts_code': str,
        'name': str,
        'status': 'success' | 'no_signal' | 'error',
        'strategy_return_pct': float,  # 总收益百分比，如 +287.25
        'trade_count': int,
        'win_rate': float,             # 胜率百分比，如 60.0
        'max_single_gain': float,      # 最大单笔盈利%
        'max_single_loss': float,      # 最大单笔亏损%
        'final_capital': float,
        'trades': list,
        'error_msg': str,
    }
    """
    INITIAL_CAPITAL = 200000
    
    result = {
        'ts_code': ts_code,
        'name': stock_name,
        'status': 'error',
        'strategy_return_pct': 0.0,
        'trade_count': 0,
        'win_rate': 0.0,
        'max_single_gain': 0.0,
        'max_single_loss': 0.0,
        'final_capital': INITIAL_CAPITAL,
        'trades': [],
        'error_msg': '',
    }
    
    try:
        # 初始化Tushare
        ts.set_token(config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        
        print(f"    获取 {ts_code} 行情数据...")
        
        # 1. 获取股票数据
        stock_df_raw = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                 fields='ts_code,trade_date,open,high,low,close,vol,amount')
        if stock_df_raw.empty:
            result['error_msg'] = f'未获取到 {ts_code} 的行情数据'
            return result
        
        # 数据预处理（与backtest_stock.py保持一致）
        stock_df_raw = stock_df_raw.sort_values('trade_date')
        stock_df = stock_df_raw.copy()
        
        # 重命名列
        stock_df = stock_df.rename(columns={
            'trade_date': '交易日期',
            'open': '开盘价',
            'high': '最高价', 
            'low': '最低价',
            'close': '收盘价',
            'vol': '成交量',
            'amount': '成交额'
        })
        
        # 转换日期格式
        stock_df['交易日期'] = pd.to_datetime(stock_df['交易日期'], format='%Y%m%d')
        
        # 获取上证指数数据
        index_df_raw = pro.index_daily(ts_code='000001.SH', start_date=start_date, end_date=end_date,
                                       fields='ts_code,trade_date,close')
        index_df = index_df_raw.copy()
        index_df = index_df.rename(columns={'trade_date': '交易日期', 'close': '收盘价'})
        index_df['交易日期'] = pd.to_datetime(index_df['交易日期'], format='%Y%m%d')
        
        # 2. 提取纯代码数字部分
        code_only = ts_code.split('.')[0]
        
        # 3. 执行回测
        print(f"    执行回测...")
        trades = backtest(
            stock_df=stock_df,
            code=code_only,
            index_df=index_df,
            verbose=False,  # 批量模式不打印详细日志
            stock_name=stock_name
        )
        
        # 4. 解析结果
        if not trades:
            result['status'] = 'no_signal'
            result['error_msg'] = '回测期间无交易信号'
            return result
        
        # 计算总收益和统计信息
        final_capital = INITIAL_CAPITAL
        all_returns = []
        
        for trade in trades:
            # 计算每笔交易的收益率
            trade_return_pct = trade.pnl
            all_returns.append(trade_return_pct)
            
            # 计算资金变化（简化处理）
            trade_profit = INITIAL_CAPITAL * (trade_return_pct / 100)
            final_capital += trade_profit
        
        # 计算总收益率
        total_return_pct = (final_capital / INITIAL_CAPITAL - 1) * 100
        
        # 计算胜率
        winning_trades = [r for r in all_returns if r > 0]
        win_rate = len(winning_trades) / len(all_returns) * 100 if all_returns else 0
        
        # 格式化交易记录
        formatted_trades = []
        for i, trade in enumerate(trades, 1):
            formatted_trades.append({
                '序号': i,
                '信号日期': str(trade.signal_date),
                '买入日期': str(trade.buy_date),
                '买入价': trade.buy_price,
                '卖出日期': str(trade.exit_date),
                '卖出价': trade.exit_price,
                '收益%': round(trade.pnl, 2),
                '持有天数': trade.days,
                '交易类型': trade.trade_type,
                '退出原因': getattr(trade, 'exit_reason', '未知'),
            })
        
        result['status'] = 'success'
        result['strategy_return_pct'] = round(total_return_pct, 2)
        result['trade_count'] = len(trades)
        result['win_rate'] = round(win_rate, 1)
        result['max_single_gain'] = max(all_returns) if all_returns else 0
        result['max_single_loss'] = min(all_returns) if all_returns else 0
        result['final_capital'] = round(final_capital, 2)
        result['trades'] = formatted_trades
        
        print(f"    回测完成: {result['strategy_return_pct']:+.1f}%, {len(trades)}笔交易")
        
    except ImportError as e:
        result['error_msg'] = f'导入错误: {e}. 请确认在正确的目录下运行'
        traceback.print_exc()
    except Exception as e:
        result['error_msg'] = f'{type(e).__name__}: {e}'
        traceback.print_exc()
    
    return result


# ============================================================
# 快速测试（先跑3只确认没问题）
# ============================================================

def quick_test():
    """快速测试3只股票，确认适配正确"""
    test_stocks = [
        ('300502.SZ', '新易盛'),   # 创业板 - 已验证过
        ('688220.SZ', '翱捷科技'), # 科创板
        ('600519.SH', '贵州茅台'), # 主板
    ]
    
    print("快速适配测试:")
    print("=" * 60)
    
    for code, name in test_stocks:
        print(f"\n测试: {code} {name}")
        r = run_single_backtest(code, name, '20240101', '20251231')
        print(f"  状态: {r['status']}")
        print(f"  策略收益: {r['strategy_return_pct']:+.1f}%")
        print(f"  交易数: {r['trade_count']}")
        print(f"  胜率: {r['win_rate']:.1f}%")
        print(f"  错误: {r['error_msg'] or '无'}")
    
    print("\n" + "=" * 60)
    print("如果上面3只都显示 status=success 且收益数据合理，")
    print("就可以运行完整回测了: python batch_backtest_all_boards.py")


if __name__ == '__main__':
    quick_test()