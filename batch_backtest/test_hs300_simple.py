#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
沪深300股票简单回测测试脚本
先测试几只关键股票
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime
import config

# 测试几只关键股票
TEST_STOCKS = [
    "600519.SH",  # 贵州茅台
    "300750.SZ",  # 宁德时代
    "601318.SH",  # 中国平安
    "600036.SH",  # 招商银行
    "000333.SZ",  # 美的集团
]

def prepare_stock_data_simple(ts_code, start_date="20240101", end_date=None):
    """准备单只股票的回测数据 - 简化版"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    try:
        pro = ts.pro_api()
        
        # 获取日线数据
        daily_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_df.empty:
            return None, f"{ts_code}: 无日线数据"
        
        # 获取股票名称
        try:
            stock_info = pro.stock_basic(ts_code=ts_code)
            stock_name = stock_info['name'].iloc[0] if not stock_info.empty else ts_code
        except:
            stock_name = ts_code
        
        # 准备数据 - 使用更简单的列映射
        df = daily_df.copy()
        
        # 重命名列
        df = df.rename(columns={
            'trade_date': '交易日期',
            'open': '开盘价(元)',
            'high': '最高价(元)',
            'low': '最低价(元)',
            'close': '收盘价(元)',
            'vol': '成交量(手)',
            'amount': '成交额(元)',
            'pct_chg': '涨跌幅(%)'
        })
        
        # 转换日期格式
        df['交易日期'] = pd.to_datetime(df['交易日期'], format='%Y%m%d')
        
        # 添加必要的列
        df['收盘价(前复权)(元)'] = df['收盘价(元)']
        df['成交量(万股)'] = df['成交量(手)'] / 100  # 手→万股
        df['成交额(万元)'] = df['成交额(元)'] / 10000  # 元→万元
        df['换手率(%)'] = 0  # 简化处理
        
        # 只保留必要的列
        required_columns = [
            '交易日期', '开盘价(元)', '最高价(元)', '最低价(元)', '收盘价(元)',
            '收盘价(前复权)(元)', '成交量(万股)', '成交额(万元)', '涨跌幅(%)', '换手率(%)'
        ]
        
        df = df[required_columns].sort_values('交易日期')
        
        return df, stock_name, None
        
    except Exception as e:
        return None, None, f"{ts_code}: {str(e)}"

def test_single_stock(ts_code):
    """测试单只股票"""
    print(f"\n测试 {ts_code}")
    print("-" * 60)
    
    # 准备数据
    df, stock_name, error = prepare_stock_data_simple(ts_code, start_date="20240101")
    if error:
        print(f"错误: {error}")
        return None
    
    print(f"股票名称: {stock_name}")
    print(f"数据期间: {df['交易日期'].min().strftime('%Y-%m-%d')} 到 {df['交易日期'].max().strftime('%Y-%m-%d')}")
    print(f"数据行数: {len(df)}")
    
    # 计算股价变化
    start_price = df['收盘价(元)'].iloc[0]
    end_price = df['收盘价(元)'].iloc[-1]
    price_change = ((end_price - start_price) / start_price) * 100
    print(f"股价变化: {start_price:.2f} → {end_price:.2f} ({price_change:+.2f}%)")
    
    try:
        # 执行回测
        from breakout_strategy_v5_patched import backtest
        
        # 执行回测 - 第三个参数应该是大盘指数数据，这里传None
        trades = backtest(df, ts_code[:6], None, verbose=False, stock_name=stock_name)
        
        if trades:
            total_pnl = sum(trade.pnl for trade in trades)
            winning_trades = sum(1 for trade in trades if trade.pnl > 0)
            win_rate = (winning_trades / len(trades)) * 100
            avg_pnl = total_pnl / len(trades)
            
            print(f"回测成功!")
            print(f"  交易次数: {len(trades)}")
            print(f"  胜率: {win_rate:.1f}% ({winning_trades}胜/{len(trades)-winning_trades}负)")
            print(f"  总收益: {total_pnl:+.2f}%")
            print(f"  平均收益/笔: {avg_pnl:+.2f}%")
            print(f"  超额收益: {total_pnl - price_change:+.2f}%")
            
            # 显示前3笔交易
            print(f"\n  前3笔交易详情:")
            for i, trade in enumerate(trades[:3]):
                print(f"    交易{i+1}: {trade.signal_date} buy@{trade.buy_price:.2f} → {trade.exit_date} exit@{trade.exit_price:.2f} | 收益: {trade.pnl:+.2f}%")
            
            result = {
                'ts_code': ts_code,
                'stock_name': stock_name,
                'status': 'success',
                'trades': len(trades),
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'price_change': price_change,
                'outperformance': total_pnl - price_change
            }
        else:
            print(f"回测完成，但未生成任何交易")
            result = {
                'ts_code': ts_code,
                'stock_name': stock_name,
                'status': 'success',
                'trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'price_change': price_change,
                'outperformance': -price_change
            }
        
    except Exception as e:
        print(f"回测失败: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        result = {
            'ts_code': ts_code,
            'status': 'error',
            'error': str(e)
        }
    
    return result

def main():
    print("沪深300关键股票回测测试")
    print("=" * 60)
    
    # 设置Tushare token
    ts.set_token(config.TUSHARE_TOKEN)
    
    results = []
    
    for ts_code in TEST_STOCKS:
        result = test_single_stock(ts_code)
        if result:
            results.append(result)
    
    # 总结
    if results:
        print(f"\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        
        successful_results = [r for r in results if r.get('status') == 'success']
        if successful_results:
            avg_pnl = np.mean([r.get('total_pnl', 0) for r in successful_results])
            avg_price = np.mean([r.get('price_change', 0) for r in successful_results])
            avg_out = np.mean([r.get('outperformance', 0) for r in successful_results])
            
            print(f"测试股票数: {len(results)}")
            print(f"成功回测: {len(successful_results)}")
            print(f"平均策略收益: {avg_pnl:.2f}%")
            print(f"平均股价涨幅: {avg_price:.2f}%")
            print(f"平均超额收益: {avg_out:.2f}%")
            
            # 排序显示
            if successful_results:
                sorted_results = sorted(successful_results, key=lambda x: x.get('total_pnl', 0), reverse=True)
                print(f"\n策略收益排名:")
                for i, r in enumerate(sorted_results):
                    print(f"  {i+1}. {r['ts_code']} {r.get('stock_name', '')}: 策略{r.get('total_pnl', 0):.1f}%, 股价{r.get('price_change', 0):.1f}%, 超额{r.get('outperformance', 0):.1f}%")

if __name__ == "__main__":
    main()