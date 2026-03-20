#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
沪深300股票批量回测脚本 v2
回测300只沪深300成分股，2024.1.1开始
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import concurrent.futures
import time
import json
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

import config

# 沪深300股票列表（从用户提供的列表中提取）
HS300_STOCKS = [
    "600519.SH", "300750.SZ", "601318.SH", "601899.SH", "300308.SZ", "600036.SH", 
    "000333.SZ", "300502.SZ", "600900.SH", "601166.SH", "300059.SZ", "600030.SH", 
    "002475.SZ", "600276.SH", "688256.SH", "688041.SH", "002594.SZ", "603259.SH", 
    "688981.SH", "601398.SH", "601138.SH", "601211.SH", "300274.SZ", "603993.SH", 
    "002371.SZ", "000858.SZ", "603986.SH", "688008.SH", "300476.SZ", "601288.SH", 
    "601328.SH", "600309.SH", "300394.SZ", "600150.SH", "000651.SZ", "600887.SH", 
    "000725.SZ", "600111.SH", "688012.SH", "600089.SH", "600919.SH", "000338.SZ", 
    "601816.SH", "601601.SH", "601088.SH", "300124.SZ", "600031.SH", "603019.SH", 
    "002028.SZ", "600000.SH", "002230.SZ", "002714.SZ", "601688.SH", "000063.SZ", 
    "601857.SH", "000792.SZ", "603799.SH", "002415.SZ", "000425.SZ", "002050.SZ", 
    "300760.SZ", "002463.SZ", "601012.SH", "002384.SZ", "600406.SH", "601600.SH", 
    "000001.SZ", "603501.SH", "601668.SH", "002142.SZ", "000100.SZ", "600660.SH", 
    "601229.SH", "600690.SH", "600016.SH", "601919.SH", "600028.SH", "600489.SH", 
    "601225.SH", "002352.SZ", "601728.SH", "601127.SH", "600938.SH", "600547.SH", 
    "600941.SH", "300498.SZ", "300442.SZ", "300408.SZ", "600183.SH", "600926.SH", 
    "002460.SZ", "000568.SZ", "601169.SH", "600522.SH", "601888.SH", "600809.SH", 
    "300014.SZ", "600050.SH", "601766.SH", "600893.SH", "002916.SZ", "601988.SH", 
    "601628.SH", "600010.SH", "601939.SH", "002625.SZ", "300033.SZ", "002027.SZ", 
    "601985.SH", "300433.SZ", "688111.SH", "601009.SH", "600584.SH", "000408.SZ", 
    "002241.SZ", "600104.SH", "000977.SZ", "600176.SH", "000807.SZ", "688271.SH", 
    "601390.SH", "000630.SZ", "601336.SH", "600019.SH", "601006.SH", "600999.SH", 
    "600585.SH", "000776.SZ", "601100.SH", "601818.SH", "600362.SH", "002709.SZ", 
    "603288.SH", "600905.SH", "601689.SH", "002466.SZ", "600426.SH", "002600.SZ", 
    "600160.SH", "000625.SZ", "601658.SH", "600346.SH", "002049.SZ", "300418.SZ", 
    "600958.SH", "600989.SH", "601872.SH", "000938.SZ", "000975.SZ", "605499.SH", 
    "000538.SZ", "000157.SZ", "601669.SH", "600436.SH", "600219.SH", "300015.SZ", 
    "600438.SH", "600115.SH", "600048.SH", "601825.SH", "002001.SZ", "600760.SH", 
    "002493.SZ", "601377.SH", "600570.SH", "002311.SZ", "600875.SH", "002179.SZ", 
    "000166.SZ", "601916.SH", "600795.SH", "601360.SH", "000768.SZ", "600015.SH", 
    "688126.SH", "300803.SZ", "601058.SH", "601838.SH", "002938.SZ", "002074.SZ", 
    "601995.SH", "600415.SH", "600029.SH", "600066.SH", "002648.SZ", "600372.SH", 
    "002601.SZ", "002736.SZ", "605117.SH", "601998.SH", "600009.SH", "002236.SZ", 
    "603893.SH", "600482.SH", "603296.SH", "600460.SH", "002920.SZ", "300316.SZ", 
    "001979.SZ", "601877.SH", "601077.SH", "600026.SH", "000301.SZ", "601117.SH", 
    "002422.SZ", "601186.SH", "600233.SH", "600196.SH", "002252.SZ", "688036.SH", 
    "601868.SH", "301236.SZ", "000002.SZ", "601788.SH", "002304.SZ", "688047.SH", 
    "600886.SH", "600011.SH", "601901.SH", "601881.SH", "601698.SH", "601111.SH", 
    "600188.SH", "000963.SZ", "000661.SZ", "601066.SH", "003816.SZ", "300347.SZ", 
    "600741.SH", "300759.SZ", "688396.SH", "688223.SH", "300782.SZ", "300661.SZ", 
    "688169.SH", "601878.SH", "601800.SH", "600588.SH", "300251.SZ", "000786.SZ", 
    "600674.SH", "601898.SH", "601319.SH", "000895.SZ", "601021.SH", "600039.SH", 
    "601633.SH", "600515.SH", "002459.SZ", "603369.SH", "302132.SZ", "601618.SH", 
    "000617.SZ", "600600.SH", "301269.SZ", "688506.SH", "300896.SZ", "688472.SH", 
    "600023.SH", "600085.SH", "600845.SH", "300866.SZ", "000983.SZ", "300832.SZ", 
    "300122.SZ", "600918.SH", "600027.SH", "001965.SZ", "000596.SZ", "000876.SZ", 
    "601607.SH", "000999.SZ", "600803.SH", "600061.SH", "300628.SZ", "603260.SH", 
    "300413.SZ", "000708.SZ", "601238.SH", "600930.SH", "600025.SH", "300999.SZ", 
    "601059.SH", "601018.SH", "688082.SH", "600161.SH", "603392.SH", "688303.SH", 
    "688187.SH", "601456.SH", "688009.SH", "600018.SH", "603195.SH", "601236.SH", 
    "601808.SH", "601136.SH", "300979.SZ", "601298.SH", "600377.SH", "001391.SZ"
]

def prepare_stock_data(ts_code, start_date="20240101", end_date=None):
    """准备单只股票的回测数据"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    try:
        pro = ts.pro_api()
        
        # 获取日线数据
        daily_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_df.empty:
            return None, f"{ts_code}: 无日线数据"
        
        # 获取换手率数据
        try:
            basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        except:
            basic_df = None
        
        # 准备数据
        column_mapping = {
            'ts_code': 'ts_code',
            'trade_date': '交易日期',
            'open': '开盘价(元)',
            'high': '最高价(元)',
            'low': '最低价(元)',
            'close': '收盘价(元)',
            'vol': '成交量(万股)',  # 转换为万股
            'amount': '成交额(万元)',
            'pct_chg': '涨跌幅(%)'
        }
        
        df = daily_df.rename(columns=column_mapping)
        df['成交量(万股)'] = df['成交量(万股)'] / 100  # 手→万股
        df['交易日期'] = pd.to_datetime(df['交易日期'], format='%Y%m%d')
        df['收盘价(前复权)(元)'] = df['收盘价(元)']
        
        # 合并换手率
        if basic_df is not None and not basic_df.empty:
            basic_df['交易日期'] = pd.to_datetime(basic_df['trade_date'], format='%Y%m%d')
            df = df.merge(basic_df[['交易日期', 'turnover_rate', 'volume_ratio']], 
                         on='交易日期', how='left')
            df['换手率(%)'] = df['turnover_rate'].fillna(0)
        else:
            df['换手率(%)'] = 0
        
        return df, None
        
    except Exception as e:
        return None, f"{ts_code}: {str(e)}"

def backtest_single_stock(ts_code, stock_name=None, board_type=None):
    """回测单只股票"""
    try:
        # 准备数据
        df, error = prepare_stock_data(ts_code, start_date="20240101")
        if error:
            return {
                'ts_code': ts_code,
                'status': 'error',
                'error': error,
                'trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'price_change': 0,
                'outperformance': 0,
                'data_points': 0
            }
        
        if stock_name is None:
            # 获取股票名称
            try:
                pro = ts.pro_api()
                stock_info = pro.stock_basic(ts_code=ts_code)
                stock_name = stock_info['name'].iloc[0] if not stock_info.empty else ts_code
            except:
                stock_name = ts_code
        
        # 执行回测
        from breakout_strategy_v5_patched import backtest
        
        # 确定股票类型，选择相应策略
        if board_type is None:
            # 自动判断板块类型
            if ts_code.startswith('688') or ts_code.startswith('689'):  # 科创板
                board_type = '创业板'  # 科创板使用创业板参数
            elif ts_code.startswith('300'):  # 创业板
                board_type = '创业板'
            elif ts_code.startswith('00') or ts_code.startswith('30'):  # 深市
                board_type = '主板'  # 深市主板
            else:  # 沪市
                board_type = '主板'
        
        # 执行回测
        trades = backtest(df, ts_code[:6], board_type, verbose=False, stock_name=stock_name)
        
        # 计算结果
        total_pnl = sum(trade.pnl for trade in trades) if trades else 0
        winning_trades = sum(1 for trade in trades if trade.pnl > 0) if trades else 0
        win_rate = (winning_trades / len(trades)) * 100 if trades else 0
        
        # 计算股价变化
        if len(df) > 0:
            start_price = df['收盘价(元)'].iloc[0]
            end_price = df['收盘价(元)'].iloc[-1]
            price_change = ((end_price - start_price) / start_price) * 100
        else:
            price_change = 0
        
        return {
            'ts_code': ts_code,
            'stock_name': stock_name,
            'status': 'success',
            'board_type': board_type,
            'trades': len(trades) if trades else 0,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'price_change': price_change,
            'outperformance': total_pnl - price_change,
            'data_points': len(df)
        }
        
    except Exception as e:
        return {
            'ts_code': ts_code,
            'status': 'error',
            'error': f"回测异常: {str(e)}",
            'trades': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'price_change': 0,
            'outperformance': 0,
            'data_points': 0
        }

def batch_backtest_hs300_stocks(stock_list=None, max_workers=8):
    """批量回测沪深300股票"""
    if stock_list is None:
        stock_list = HS300_STOCKS
    
    print(f"\n{'='*80}")
    print(f"批量回测沪深300股票 (共{len(stock_list)}只)")
    print(f"回测周期: 2024-01-01 至 {datetime.now().strftime('%Y-%m-%d')}")
    print(f"并行线程数: {max_workers}")
    print(f"{'='*80}\n")
    
    results = []
    start_time = time.time()
    
    # 设置Tushare token
    ts.set_token(config.TUSHARE_TOKEN)
    
    # 并行执行回测
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_stock = {executor.submit(backtest_single_stock, ts_code): ts_code 
                          for ts_code in stock_list}
        
        # 使用tqdm显示进度
        completed = 0
        total = len(stock_list)
        
        print(f"开始回测{total}只沪深300股票...\n")
        
        for future in tqdm(concurrent.futures.as_completed(future_to_stock), 
                          total=total, desc="回测进度"):
            ts_code = future_to_stock[future]
            try:
                result = future.result()
                results.append(result)
                
                # 每完成20个显示一次进度
                completed += 1
                if completed % 20 == 0 or completed == total:
                    success_count = sum(1 for r in results if r['status'] == 'success')
                    error_count = completed - success_count
                    print(f"  已处理: {completed}/{total} | 成功: {success_count} | 失败: {error_count}")
                    
            except Exception as e:
                results.append({
                    'ts_code': ts_code,
                    'status': 'error',
                    'error': f"执行异常: {str(e)}"
                })
    
    # 计算统计信息
    successful_results = [r for r in results if r['status'] == 'success']
    failed_results = [r for r in results if r['status'] == 'error']
    
    elapsed_time = time.time() - start_time
    
    # 输出统计信息
    print(f"\n{'='*80}")
    print(f"批量回测完成!")
    print(f"总耗时: {elapsed_time:.1f}秒")
    print(f"成功: {len(successful_results)} 只")
    print(f"失败: {len(failed_results)} 只")
    print(f"{'='*80}")
    
    if successful_results:
        # 计算整体统计
        total_trades = sum(r['trades'] for r in successful_results)
        avg_pnl = np.mean([r['total_pnl'] for r in successful_results])
        avg_win_rate = np.mean([r['win_rate'] for r in successful_results])
        avg_price_change = np.mean([r['price_change'] for r in successful_results])
        avg_outperformance = np.mean([r['outperformance'] for r in successful_results])
        
        # 统计盈利股票数量
        profitable_stocks = sum(1 for r in successful_results if r['total_pnl'] > 0)
        outperforming_stocks = sum(1 for r in successful_results if r['outperformance'] > 0)
        
        print(f"\n[整体统计]")
        print(f"  平均每只股票交易数: {total_trades/len(successful_results):.1f}")
        print(f"  平均策略收益: {avg_pnl:.2f}%")
        print(f"  平均股价涨幅: {avg_price_change:.2f}%")
        print(f"  平均超额收益: {avg_outperformance:.2f}%")
        print(f"  平均胜率: {avg_win_rate:.1f}%")
        print(f"  盈利股票数: {profitable_stocks}/{len(successful_results)} ({profitable_stocks/len(successful_results)*100:.1f}%)")
        print(f"  跑赢基准数: {outperforming_stocks}/{len(successful_results)} ({outperforming_stocks/len(successful_results)*100:.1f}%)")
        
        # 按板块统计
        board_stats = {}
        for r in successful_results:
            board = r.get('board_type', '未知')
            if board not in board_stats:
                board_stats[board] = {'count': 0, 'total_pnl': 0, 'total_price_change': 0}
            board_stats[board]['count'] += 1
            board_stats[board]['total_pnl'] += r['total_pnl']
            board_stats[board]['total_price_change'] += r['price_change']
        
        if board_stats:
            print(f"\n[按板块统计]")
            for board, stats in board_stats.items():
                count = stats['count']
                avg_board_pnl = stats['total_pnl'] / count
                avg_board_price = stats['total_price_change'] / count
                print(f"  {board}: {count}只 | 平均策略{avg_board_pnl:.2f}% | 平均股价{avg_board_price:.2f}%")
    
    # 输出失败详情
    if failed_results:
        print(f"\n[失败股票详情]")
        for r in failed_results[:20]:  # 只显示前20个失败
            print(f"  {r['ts_code']}: {r.get('error', '未知错误')}")
        if len(failed_results) > 20:
            print(f"  还有{len(failed_results)-20}个失败项未显示...")
    
    # 保存结果到文件
    output_file = "hs300_backtest_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[结果保存]")
    print(f"  详细结果已保存到: {output_file}")
    
    return results

def generate_detailed_report(results):
    """生成详细报告"""
    successful_results = [r for r in results if r['status'] == 'success']
    
    if not successful_results:
        return "⚠️ 没有成功的回测结果，无法生成分析报告"
    
    # 按不同指标排序
    sorted_by_strategy = sorted(successful_results, key=lambda x: x['total_pnl'], reverse=True)
    sorted_by_outperformance = sorted(successful_results, key=lambda x: x['outperformance'], reverse=True)
    sorted_by_win_rate = sorted(successful_results, key=lambda x: x['win_rate'], reverse=True)
    
    report_lines = []
    report_lines.append("# 沪深300股票批量回测详细分析报告")
    report_lines.append("")
    report_lines.append(f"## 📊 回测概况")
    report_lines.append(f"- **回测日期**: {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append(f"- **股票总数**: {len(results)}")
    report_lines.append(f"- **成功回测**: {len(successful_results)} 只")
    report_lines.append(f"- **失败回测**: {len(results) - len(successful_results)} 只")
    report_lines.append(f"- **回测周期**: 2024-01-01 至 {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append("")
    
    # 基本统计
    total_trades = sum(r['trades'] for r in successful_results)
    avg_trades = total_trades / len(successful_results)
    avg_pnl = np.mean([r['total_pnl'] for r in successful_results])
    avg_price = np.mean([r['price_change'] for r in successful_results])
    avg_out = np.mean([r['outperformance'] for r in successful_results])
    avg_win = np.mean([r['win_rate'] for r in successful_results])
    
    profitable = sum(1 for r in successful_results if r['total_pnl'] > 0)
    profitable_pct = profitable / len(successful_results) * 100
    outperforming = sum(1 for r in successful_results if r['outperformance'] > 0)
    outperforming_pct = outperforming / len(successful_results) * 100
    
    report_lines.append(f"## 📈 整体表现统计")
    report_lines.append("")
    report_lines.append("| 指标 | 数值 | 备注 |")
    report_lines.append("|------|------|------|")
    report_lines.append(f"| 平均交易次数 | {avg_trades:.1f} | 每只股票平均交易笔数 |")
    report_lines.append(f"| 平均策略收益 | {avg_pnl:.2f}% | 所有股票策略收益平均值 |")
    report_lines.append(f"| 平均股价涨幅 | {avg_price:.2f}% | 所有股票股价涨幅平均值 |")
    report_lines.append(f"| 平均超额收益 | {avg_out:.2f}% | 策略收益减去股价涨幅的平均值 |")
    report_lines.append(f"| 平均胜率 | {avg_win:.1f}% | 所有股票胜率平均值 |")
    report_lines.append(f"| 盈利股票比例 | {profitable_pct:.1f}% | {profitable}/{len(successful_results)}只 |")
    report_lines.append(f"| 跑赢基准比例 | {outperforming_pct:.1f}% | {outperforming}/{len(successful_results)}只 |")
    report_lines.append("")
    
    report_lines.append(f"## 🏆 表现最佳股票榜")
    report_lines.append("")
    
    report_lines.append("### 策略收益 Top 20")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易次数 | 板块 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|----------|------|")
    for i, stock in enumerate(sorted_by_strategy[:20], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock.get('stock_name', '')} | {stock['total_pnl']:.1f}% | {stock['price_change']:.1f}% | {stock['outperformance']:.1f}% | {stock['win_rate']:.1f}% | {stock['trades']} | {stock.get('board_type', '')} |")
    report_lines.append("")
    
    report_lines.append("### 超额收益 Top 20")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 超额收益 | 策略收益 | 股价涨幅 | 胜率 | 交易次数 | 板块 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|----------|------|")
    for i, stock in enumerate(sorted_by_outperformance[:20], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock.get('stock_name', '')} | {stock['outperformance']:.1f}% | {stock['total_pnl']:.1f}% | {stock['price_change']:.1f}% | {stock['win_rate']:.1f}% | {stock['trades']} | {stock.get('board_type', '')} |")
    report_lines.append("")
    
    report_lines.append("### 胜率最高 Top 20")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 胜率 | 策略收益 | 股价涨幅 | 超额收益 | 交易次数 | 板块 |")
    report_lines.append("|------|----------|----------|------|----------|----------|----------|----------|------|")
    for i, stock in enumerate(sorted_by_win_rate[:20], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock.get('stock_name', '')} | {stock['win_rate']:.1f}% | {stock['total_pnl']:.1f}% | {stock['price_change']:.1f}% | {stock['outperformance']:.1f}% | {stock['trades']} | {stock.get('board_type', '')} |")
    report_lines.append("")
    
    report_lines.append(f"## ⚠️ 表现最差股票榜")
    report_lines.append("")
    
    report_lines.append("### 策略收益最差 Top 20")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易次数 | 板块 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|----------|------|")
    for i, stock in enumerate(sorted_by_strategy[-20:], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock.get('stock_name', '')} | {stock['total_pnl']:.1f}% | {stock['price_change']:.1f}% | {stock['outperformance']:.1f}% | {stock['win_rate']:.1f}% | {stock['trades']} | {stock.get('board_type', '')} |")
    report_lines.append("")
    
    report_lines.append("### 超额收益最差 Top 20")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 超额收益 | 策略收益 | 股价涨幅 | 胜率 | 交易次数 | 板块 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|----------|------|")
    for i, stock in enumerate(sorted_by_outperformance[-20:], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock.get('stock_name', '')} | {stock['outperformance']:.1f}% | {stock['total_pnl']:.1f}% | {stock['price_change']:.1f}% | {stock['win_rate']:.1f}% | {stock['trades']} | {stock.get('board_type', '')} |")
    report_lines.append("")
    
    report_lines.append(f"## 💡 投资建议")
    report_lines.append("")
    report_lines.append("### 策略有效性评估")
    if avg_out > 0:
        report_lines.append(f"1. ✅ **策略整体有效**: 平均超额收益为 **{avg_out:.2f}%**，说明策略能够跑赢市场")
    else:
        report_lines.append(f"1. ❌ **策略整体无效**: 平均超额收益为 **{avg_out:.2f}%**，未能跑赢市场")
    
    if profitable_pct > 50:
        report_lines.append(f"2. ✅ **盈利股票占多数**: {profitable_pct:.1f}%的股票实现盈利")
    else:
        report_lines.append(f"2. ❌ **盈利股票较少**: 仅{profitable_pct:.1f}%的股票实现盈利")
    
    if outperforming_pct > 50:
        report_lines.append(f"3. ✅ **多数股票跑赢基准**: {outperforming_pct:.1f}%的股票跑赢股价")
    else:
        report_lines.append(f"3. ❌ **多数股票跑输基准**: 仅{outperforming_pct:.1f}%的股票跑赢股价")
    report_lines.append("")
    
    report_lines.append("### 操作建议")
    report_lines.append("1. **重点配置**: 策略收益Top 20和超额收益Top 20的股票")
    report_lines.append("2. **规避股票**: 策略收益最差Top 20的股票")
    report_lines.append("3. **仓位管理**: 单只股票仓位不超过3%，组合配置20-30只")
    report_lines.append("4. **板块倾向**: 关注表现较好的板块")
    report_lines.append("")
    
    report_lines.append("### 策略优化方向")
    report_lines.append("1. **参数优化**: 对不同板块使用不同的参数设置")
    report_lines.append("2. **选股过滤**: 增加基本面指标，避开亏损股票")
    report_lines.append("3. **动态调仓**: 根据市场环境调整策略参数")
    report_lines.append("4. **组合策略**: 结合其他指标形成复合策略")
    report_lines.append("")
    
    report_lines.append(f"## 📊 数据分布分析")
    report_lines.append("")
    
    # 收益分布统计
    price_bins = [-50, -30, -20, -10, -5, 0, 5, 10, 20, 30, 50, 100, 200]
    strategy_bins = [-50, -30, -20, -10, -5, 0, 5, 10, 20, 30, 50, 100, 200]
    
    price_dist = np.histogram([r['price_change'] for r in successful_results], bins=price_bins)[0]
    strategy_dist = np.histogram([r['total_pnl'] for r in successful_results], bins=strategy_bins)[0]
    
    report_lines.append("### 股价涨幅分布")
    report_lines.append("| 涨幅区间 | 股票数量 | 占比 |")
    report_lines.append("|----------|----------|------|")
    for i in range(len(price_bins)-1):
        low = price_bins[i]
        high = price_bins[i+1]
        count = price_dist[i]
        percent = count/len(successful_results)*100
        report_lines.append(f"| {low}% ~ {high}% | {count} | {percent:.1f}% |")
    
    report_lines.append("")
    report_lines.append("### 策略收益分布")
    report_lines.append("| 收益区间 | 股票数量 | 占比 |")
    report_lines.append("|----------|----------|------|")
    for i in range(len(strategy_bins)-1):
        low = strategy_bins[i]
        high = strategy_bins[i+1]
        count = strategy_dist[i]
        percent = count/len(successful_results)*100
        report_lines.append(f"| {low}% ~ {high}% | {count} | {percent:.1f}% |")
    
    return "\n".join(report_lines)

def main():
    print("=" * 80)
    print("沪深300股票批量回测系统 v2")
    print("=" * 80)
    
    # 检查股票数量
    print(f"沪深300股票数量: {len(HS300_STOCKS)}")
    
    # 设置并行线程数
    max_workers = 8
    
    # 执行批量回测
    results = batch_backtest_hs300_stocks(max_workers=max_workers)
    
    # 生成详细报告
    if sum(1 for r in results if r['status'] == 'success') > 0:
        report_content = generate_detailed_report(results)
        
        # 保存报告
        report_file = "hs300_detailed_analysis_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"\n📄 详细分析报告已保存到: {report_file}")
        
        # 打印简要总结
        successful_results = [r for r in results if r['status'] == 'success']
        if successful_results:
            avg_pnl = np.mean([r['total_pnl'] for r in successful_results])
            avg_price = np.mean([r['price_change'] for r in successful_results])
            avg_out = np.mean([r['outperformance'] for r in successful_results])
            profitable_pct = sum(1 for r in successful_results if r['total_pnl'] > 0)/len(successful_results)*100
            outperforming_pct = sum(1 for r in successful_results if r['outperformance'] > 0)/len(successful_results)*100
            
            print(f"\n📊 最终总结:")
            print(f"  平均策略收益: {avg_pnl:.2f}%")
            print(f"  平均股价涨幅: {avg_price:.2f}%")
            print(f"  平均超额收益: {avg_out:.2f}%")
            print(f"  盈利股票比例: {profitable_pct:.1f}%")
            print(f"  跑赢基准比例: {outperforming_pct:.1f}%")
    
    print("\n🎉 沪深300批量回测任务完成!")

if __name__ == "__main__":
    main()