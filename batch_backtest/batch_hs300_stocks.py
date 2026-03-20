#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
沪深300股票批量回测脚本
回测300只沪深300成分股，2024.1.1开始
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import concurrent.futures
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# 导入回测核心模块
try:
    from backtest_stock import BacktestStock
    print("✅ 成功导入回测核心模块")
except ImportError as e:
    print(f"❌ 导入回测核心模块失败: {e}")
    sys.exit(1)

# 沪深300股票列表（从用户提供的列表中提取）
hs300_stocks = [
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

print(f"📊 沪深300股票数量: {len(hs300_stocks)}")
print(f"📅 回测周期: 2024-01-01 至 {datetime.now().strftime('%Y-%m-%d')}")

# 回测单个股票的函数
def backtest_single_stock(ts_code, start_date="2024-01-01", end_date=None):
    """回测单个股票"""
    try:
        # 创建回测对象
        backtester = BacktestStock(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        # 加载数据
        df = backtester.load_data()
        if df is None or len(df) < 60:  # 至少需要60个交易日
            return {
                'ts_code': ts_code,
                'status': 'error',
                'error_msg': '数据不足或加载失败'
            }
        
        # 运行回测
        result = backtester.run_backtest()
        
        # 计算收益和超额收益
        start_price = df.loc[df['trade_date'] >= start_date, 'close'].iloc[0] if len(df[df['trade_date'] >= start_date]) > 0 else df['close'].iloc[0]
        end_price = df['close'].iloc[-1]
        price_return = (end_price - start_price) / start_price * 100
        strategy_return = result['total_return'] * 100
        outperformance = strategy_return - price_return
        
        # 获取交易记录
        trades = result.get('trades', [])
        
        return {
            'ts_code': ts_code,
            'status': 'success',
            'price_return': round(price_return, 2),
            'strategy_return': round(strategy_return, 2),
            'outperformance': round(outperformance, 2),
            'num_trades': len(trades),
            'win_rate': round(result.get('win_rate', 0) * 100, 1) if trades else 0,
            'max_drawdown': round(result.get('max_drawdown', 0) * 100, 2),
            'sharpe_ratio': round(result.get('sharpe_ratio', 0), 3),
            'trades': trades
        }
        
    except Exception as e:
        return {
            'ts_code': ts_code,
            'status': 'error',
            'error_msg': str(e)
        }

# 并行回测主函数
def batch_backtest_hs300(max_workers=8):
    """并行回测沪深300股票"""
    print(f"🚀 开始并行回测沪深300股票 (线程数: {max_workers})")
    
    results = []
    success_count = 0
    error_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_stock = {
            executor.submit(backtest_single_stock, stock): stock 
            for stock in hs300_stocks
        }
        
        # 处理结果
        for future in tqdm(
            concurrent.futures.as_completed(future_to_stock), 
            total=len(hs300_stocks),
            desc="回测进度"
        ):
            stock = future_to_stock[future]
            try:
                result = future.result()
                results.append(result)
                
                if result['status'] == 'success':
                    success_count += 1
                    # 打印成功回测的简要信息
                    if success_count % 20 == 0 or success_count == 1:
                        print(f"✅ {result['ts_code']}: 股价{result['price_return']:.1f}%, 策略{result['strategy_return']:.1f}%, 超额{result['outperformance']:.1f}%")
                else:
                    error_count += 1
                    print(f"❌ {result['ts_code']}: {result['error_msg']}")
                    
            except Exception as e:
                error_count += 1
                print(f"❌ {stock}: 回测异常 - {str(e)}")
                results.append({
                    'ts_code': stock,
                    'status': 'error',
                    'error_msg': str(e)
                })
    
    return results, success_count, error_count

# 生成分析报告
def generate_analysis_report(results, success_count, error_count):
    """生成回测分析报告"""
    
    successful_results = [r for r in results if r['status'] == 'success']
    
    if not successful_results:
        print("⚠️ 没有成功的回测结果，无法生成分析报告")
        return
    
    # 基本统计
    price_returns = [r['price_return'] for r in successful_results]
    strategy_returns = [r['strategy_return'] for r in successful_results]
    outperformance_values = [r['outperformance'] for r in successful_results]
    win_rates = [r['win_rate'] for r in successful_results]
    
    # 收益为正的股票数量
    positive_price = sum(1 for x in price_returns if x > 0)
    positive_strategy = sum(1 for x in strategy_returns if x > 0)
    positive_outperformance = sum(1 for x in outperformance_values if x > 0)
    
    # 排序寻找表现最好的和最差的
    sorted_by_strategy = sorted(successful_results, key=lambda x: x['strategy_return'], reverse=True)
    sorted_by_outperformance = sorted(successful_results, key=lambda x: x['outperformance'], reverse=True)
    sorted_by_win_rate = sorted(successful_results, key=lambda x: x['win_rate'], reverse=True)
    
    # 生成报告
    report_lines = []
    report_lines.append("# 沪深300股票批量回测分析报告")
    report_lines.append("")
    report_lines.append(f"## 📊 回测概况")
    report_lines.append(f"- **回测日期**: {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append(f"- **股票总数**: {len(hs300_stocks)}")
    report_lines.append(f"- **成功回测**: {success_count} 只")
    report_lines.append(f"- **失败回测**: {error_count} 只")
    report_lines.append(f"- **成功率**: {success_count/len(hs300_stocks)*100:.1f}%")
    report_lines.append(f"- **回测周期**: 2024-01-01 至 {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append("")
    
    report_lines.append(f"## 📈 整体表现统计")
    report_lines.append("")
    report_lines.append("### 股价表现")
    report_lines.append(f"- **平均涨幅**: {np.mean(price_returns):.2f}%")
    report_lines.append(f"- **中位数涨幅**: {np.median(price_returns):.2f}%")
    report_lines.append(f"- **上涨股票数**: {positive_price} 只 ({positive_price/success_count*100:.1f}%)")
    report_lines.append(f"- **下跌股票数**: {success_count-positive_price} 只")
    report_lines.append("")
    
    report_lines.append("### 策略表现")
    report_lines.append(f"- **平均收益**: {np.mean(strategy_returns):.2f}%")
    report_lines.append(f"- **中位数收益**: {np.median(strategy_returns):.2f}%")
    report_lines.append(f"- **盈利股票数**: {positive_strategy} 只 ({positive_strategy/success_count*100:.1f}%)")
    report_lines.append(f"- **亏损股票数**: {success_count-positive_strategy} 只")
    report_lines.append("")
    
    report_lines.append("### 超额收益")
    report_lines.append(f"- **平均超额**: {np.mean(outperformance_values):.2f}%")
    report_lines.append(f"- **中位数超额**: {np.median(outperformance_values):.2f}%")
    report_lines.append(f"- **跑赢股价**: {positive_outperformance} 只 ({positive_outperformance/success_count*100:.1f}%)")
    report_lines.append(f"- **跑输股价**: {success_count-positive_outperformance} 只")
    report_lines.append("")
    
    report_lines.append("### 交易质量")
    report_lines.append(f"- **平均胜率**: {np.mean(win_rates):.1f}%")
    report_lines.append(f"- **中位数胜率**: {np.median(win_rates):.1f}%")
    report_lines.append(f"- **平均交易次数**: {np.mean([r['num_trades'] for r in successful_results]):.1f}")
    report_lines.append("")
    
    report_lines.append(f"## 🏆 表现最佳股票榜")
    report_lines.append("")
    
    report_lines.append("### 策略收益 Top 10")
    report_lines.append("| 排名 | 股票代码 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易次数 |")
    report_lines.append("|------|----------|----------|----------|----------|------|----------|")
    for i, stock in enumerate(sorted_by_strategy[:10], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock['strategy_return']:.1f}% | {stock['price_return']:.1f}% | {stock['outperformance']:.1f}% | {stock['win_rate']:.1f}% | {stock['num_trades']} |")
    report_lines.append("")
    
    report_lines.append("### 超额收益 Top 10")
    report_lines.append("| 排名 | 股票代码 | 超额收益 | 策略收益 | 股价涨幅 | 胜率 | 交易次数 |")
    report_lines.append("|------|----------|----------|----------|----------|------|----------|")
    for i, stock in enumerate(sorted_by_outperformance[:10], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock['outperformance']:.1f}% | {stock['strategy_return']:.1f}% | {stock['price_return']:.1f}% | {stock['win_rate']:.1f}% | {stock['num_trades']} |")
    report_lines.append("")
    
    report_lines.append("### 胜率最高 Top 10")
    report_lines.append("| 排名 | 股票代码 | 胜率 | 策略收益 | 股价涨幅 | 超额收益 | 交易次数 |")
    report_lines.append("|------|----------|------|----------|----------|----------|----------|")
    for i, stock in enumerate(sorted_by_win_rate[:10], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock['win_rate']:.1f}% | {stock['strategy_return']:.1f}% | {stock['price_return']:.1f}% | {stock['outperformance']:.1f}% | {stock['num_trades']} |")
    report_lines.append("")
    
    report_lines.append(f"## ⚠️ 表现最差股票榜")
    report_lines.append("")
    
    report_lines.append("### 策略收益最差 Top 10")
    report_lines.append("| 排名 | 股票代码 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易次数 |")
    report_lines.append("|------|----------|----------|----------|----------|------|----------|")
    for i, stock in enumerate(sorted_by_strategy[-10:], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock['strategy_return']:.1f}% | {stock['price_return']:.1f}% | {stock['outperformance']:.1f}% | {stock['win_rate']:.1f}% | {stock['num_trades']} |")
    report_lines.append("")
    
    report_lines.append("### 超额收益最差 Top 10")
    report_lines.append("| 排名 | 股票代码 | 超额收益 | 策略收益 | 股价涨幅 | 胜率 | 交易次数 |")
    report_lines.append("|------|----------|----------|----------|----------|------|----------|")
    for i, stock in enumerate(sorted_by_outperformance[-10:], 1):
        report_lines.append(f"| {i} | {stock['ts_code']} | {stock['outperformance']:.1f}% | {stock['strategy_return']:.1f}% | {stock['price_return']:.1f}% | {stock['win_rate']:.1f}% | {stock['num_trades']} |")
    report_lines.append("")
    
    report_lines.append(f"## 📊 收益分布分析")
    report_lines.append("")
    
    # 收益分布统计
    def get_distribution(values, thresholds):
        distribution = {}
        for threshold in thresholds:
            count = sum(1 for v in values if v >= threshold)
            distribution[threshold] = count
        return distribution
    
    price_thresholds = [-30, -20, -10, 0, 10, 20, 30, 40, 50]
    strategy_thresholds = [-30, -20, -10, 0, 10, 20, 30, 40, 50]
    
    price_dist = get_distribution(price_returns, price_thresholds)
    strategy_dist = get_distribution(strategy_returns, strategy_thresholds)
    
    report_lines.append("### 股价涨幅分布")
    report_lines.append("| 涨幅区间 | 股票数量 | 占比 |")
    report_lines.append("|----------|----------|------|")
    for i in range(len(price_thresholds)-1):
        low = price_thresholds[i]
        high = price_thresholds[i+1]
        count = sum(1 for v in price_returns if low <= v < high)
        percent = count/success_count*100
        report_lines.append(f"| {low}% ~ {high}% | {count} | {percent:.1f}% |")
    
    report_lines.append("")
    report_lines.append("### 策略收益分布")
    report_lines.append("| 收益区间 | 股票数量 | 占比 |")
    report_lines.append("|----------|----------|------|")
    for i in range(len(strategy_thresholds)-1):
        low = strategy_thresholds[i]
        high = strategy_thresholds[i+1]
        count = sum(1 for v in strategy_returns if low <= v < high)
        percent = count/success_count*100
        report_lines.append(f"| {low}% ~ {high}% | {count} | {percent:.1f}% |")
    
    report_lines.append("")
    report_lines.append(f"## 💡 投资建议")
    report_lines.append("")
    report_lines.append("### 策略有效性分析")
    report_lines.append("1. **整体表现**: 如果平均超额收益为正，说明策略在沪深300中有效")
    report_lines.append("2. **胜率分析**: 如果平均胜率>50%，说明策略有较好的选股能力")
    report_lines.append("3. **收益分布**: 观察收益分布是否对称，是否存在明显的偏度")
    report_lines.append("")
    report_lines.append("### 操作建议")
    report_lines.append("1. **重点关注股票**: 策略收益Top 10和超额收益Top 10的股票")
    report_lines.append("2. **规避股票**: 策略收益最差Top 10和超额收益最差Top 10的股票")
    report_lines.append("3. **仓位管理**: 建议单只股票仓位不超过3%，组合配置20-30只")
    report_lines.append("4. **风险控制**: 设置止损线，控制最大回撤")
    report_lines.append("")
    report_lines.append("### 策略优化方向")
    report_lines.append("1. **参数优化**: 对MA周期、止损条件等进行优化")
    report_lines.append("2. **选股过滤**: 加入基本面指标过滤，避免亏损股票")
    report_lines.append("3. **动态调仓**: 根据市场环境动态调整策略参数")
    report_lines.append("4. **多策略融合**: 结合其他技术指标，形成复合策略")
    
    return "\n".join(report_lines)

# 主函数
def main():
    print("=" * 80)
    print("📊 沪深300股票批量回测系统")
    print("=" * 80)
    
    # 设置回测参数
    max_workers = 8  # 并行线程数
    
    # 执行并行回测
    start_time = datetime.now()
    results, success_count, error_count = batch_backtest_hs300(max_workers=max_workers)
    end_time = datetime.now()
    
    elapsed_time = (end_time - start_time).total_seconds()
    
    print(f"\n⏱️ 回测完成！耗时: {elapsed_time:.1f}秒")
    print(f"✅ 成功回测: {success_count} 只")
    print(f"❌ 失败回测: {error_count} 只")
    
    # 保存结果到JSON文件
    results_file = "hs300_backtest_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"💾 结果已保存到: {results_file}")
    
    # 生成分析报告
    if success_count > 0:
        report_content = generate_analysis_report(results, success_count, error_count)
        report_file = "hs300_analysis_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"📄 分析报告已保存到: {report_file}")
        
        # 打印简要统计
        successful_results = [r for r in results if r['status'] == 'success']
        if successful_results:
            price_returns = [r['price_return'] for r in successful_results]
            strategy_returns = [r['strategy_return'] for r in successful_results]
            outperformance_values = [r['outperformance'] for r in successful_results]
            
            print(f"\n📊 简要统计:")
            print(f"   平均股价涨幅: {np.mean(price_returns):.2f}%")
            print(f"   平均策略收益: {np.mean(strategy_returns):.2f}%")
            print(f"   平均超额收益: {np.mean(outperformance_values):.2f}%")
            print(f"   策略跑赢比例: {sum(1 for x in outperformance_values if x > 0)/len(outperformance_values)*100:.1f}%")
    
    else:
        print("⚠️ 没有成功的回测结果，无法生成分析报告")
    
    print("\n🎉 批量回测任务完成！")

if __name__ == "__main__":
    main()