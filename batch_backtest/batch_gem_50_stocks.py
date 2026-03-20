"""
批量回测50只科创板股票（2024.1.1开始）
基于并行回测系统
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
import config

# 科创板股票列表（来自图片）
GEM_STOCKS = [
    "688041.SH", "688981.SH", "688256.SH", "688008.SH", "688012.SH",
    "688521.SH", "688111.SH", "688271.SH", "688072.SH", "688525.SH",
    "688777.SH", "688120.SH", "688126.SH", "688122.SH", "688469.SH",
    "688249.SH", "688036.SH", "688099.SH", "688047.SH", "688396.SH",
    "688223.SH", "688169.SH", "689009.SH", "688213.SH", "688599.SH",
    "688578.SH", "688220.SH", "688608.SH", "688702.SH", "688375.SH",
    "688506.SH", "688183.SH", "688472.SH", "688617.SH", "688234.SH",
    "688065.SH", "688188.SH", "688082.SH", "688114.SH", "688187.SH",
    "688303.SH", "688009.SH", "688538.SH", "688297.SH", "688728.SH",
    "688278.SH", "688349.SH", "688568.SH", "688361.SH", "688027.SH"
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

def backtest_single_stock(ts_code, stock_name=None):
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
                'price_change': 0
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
        
        # 使用创业板策略（科创板适用创业板参数）
        trades = backtest(df, ts_code[:6], None, verbose=False, stock_name=stock_name)
        
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
            'price_change': 0
        }

def batch_backtest_gem_stocks(stock_list=None, max_workers=4):
    """批量回测科创板股票"""
    if stock_list is None:
        stock_list = GEM_STOCKS
    
    print(f"\n{'='*80}")
    print(f"批量回测科创板股票 (共{len(stock_list)}只)")
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
        
        print(f"开始回测{total}只科创板股票...\n")
        
        for future in tqdm(concurrent.futures.as_completed(future_to_stock), 
                          total=total, desc="回测进度"):
            ts_code = future_to_stock[future]
            try:
                result = future.result()
                results.append(result)
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
    
    # 输出失败详情
    if failed_results:
        print(f"\n[失败股票详情]")
        for r in failed_results:
            print(f"  {r['ts_code']}: {r.get('error', '未知错误')}")
    
    # 保存结果到文件
    output_file = "gem_50_stocks_backtest_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[结果保存]")
    print(f"  详细结果已保存到: {output_file}")
    
    return results

def generate_summary_report(results):
    """生成汇总报告"""
    successful_results = [r for r in results if r['status'] == 'success']
    
    if not successful_results:
        return "无成功回测结果"
    
    # 创建DataFrame便于分析
    df_results = pd.DataFrame(successful_results)
    
    # 计算排序
    df_results = df_results.sort_values('total_pnl', ascending=False)
    
    # 生成报告
    report_lines = []
    report_lines.append("# 科创板50只股票回测汇总报告")
    report_lines.append(f"## 回测周期: 2024-01-01 至 {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append(f"## 股票数量: {len(successful_results)} 只 (成功率: {len(successful_results)/len(results)*100:.1f}%)")
    report_lines.append("")
    
    # 整体统计
    report_lines.append("## 整体表现统计")
    report_lines.append(f"- **平均策略收益**: {df_results['total_pnl'].mean():.2f}%")
    report_lines.append(f"- **平均股价涨幅**: {df_results['price_change'].mean():.2f}%")
    report_lines.append(f"- **平均超额收益**: {df_results['outperformance'].mean():.2f}%")
    report_lines.append(f"- **平均胜率**: {df_results['win_rate'].mean():.1f}%")
    report_lines.append(f"- **平均交易数**: {df_results['trades'].mean():.1f}")
    
    profitable_count = len(df_results[df_results['total_pnl'] > 0])
    outperforming_count = len(df_results[df_results['outperformance'] > 0])
    report_lines.append(f"- **盈利股票比例**: {profitable_count}/{len(df_results)} ({profitable_count/len(df_results)*100:.1f}%)")
    report_lines.append(f"- **跑赢基准比例**: {outperforming_count}/{len(df_results)} ({outperforming_count/len(df_results)*100:.1f}%)")
    report_lines.append("")
    
    # 最佳表现股票
    report_lines.append("## 🏆 最佳表现股票 (按策略收益)")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易数 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|--------|")
    
    for i, row in df_results.head(10).iterrows():
        report_lines.append(f"| {i+1} | {row['ts_code']} | {row.get('stock_name', 'N/A')} | {row['total_pnl']:.2f}% | {row['price_change']:.2f}% | {row['outperformance']:.2f}% | {row['win_rate']:.1f}% | {row['trades']} |")
    
    report_lines.append("")
    
    # 最差表现股票
    report_lines.append("## ⚠️ 最差表现股票 (按策略收益)")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易数 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|--------|")
    
    for i, row in df_results.tail(10).iterrows():
        report_lines.append(f"| {i+1} | {row['ts_code']} | {row.get('stock_name', 'N/A')} | {row['total_pnl']:.2f}% | {row['price_change']:.2f}% | {row['outperformance']:.2f}% | {row['win_rate']:.1f}% | {row['trades']} |")
    
    report_lines.append("")
    
    # 最佳超额收益股票
    df_outperformance = df_results.sort_values('outperformance', ascending=False)
    report_lines.append("## 🎯 最佳超额收益股票 (跑赢基准最多)")
    report_lines.append("| 排名 | 股票代码 | 股票名称 | 策略收益 | 股价涨幅 | 超额收益 | 胜率 | 交易数 |")
    report_lines.append("|------|----------|----------|----------|----------|----------|------|--------|")
    
    for i, row in df_outperformance.head(10).iterrows():
        report_lines.append(f"| {i+1} | {row['ts_code']} | {row.get('stock_name', 'N/A')} | {row['total_pnl']:.2f}% | {row['price_change']:.2f}% | {row['outperformance']:.2f}% | {row['win_rate']:.1f}% | {row['trades']} |")
    
    report_lines.append("")
    
    # 分析结论
    report_lines.append("## 📊 分析结论")
    
    avg_pnl = df_results['total_pnl'].mean()
    avg_outperformance = df_results['outperformance'].mean()
    
    if avg_pnl > 0 and avg_outperformance > 0:
        report_lines.append(f"✅ **策略总体有效**: 平均收益{avg_pnl:.2f}%，平均超额收益{avg_outperformance:.2f}%，策略在科创板整体表现良好。")
    elif avg_pnl > 0:
        report_lines.append(f"⚠️ **策略收益为正但未跑赢基准**: 平均收益{avg_pnl:.2f}%，但未能跑赢股价涨幅。")
    else:
        report_lines.append(f"❌ **策略整体表现不佳**: 平均收益{avg_pnl:.2f}%，策略在科创板效果有限。")
    
    # 成功率统计
    success_rate = profitable_count / len(df_results) * 100
    if success_rate > 60:
        report_lines.append(f"✅ **高成功率**: {success_rate:.1f}%的股票实现盈利，策略稳定性较好。")
    elif success_rate > 40:
        report_lines.append(f"⚠️ **中等成功率**: {success_rate:.1f}%的股票实现盈利，策略有一定效果但不稳定。")
    else:
        report_lines.append(f"❌ **低成功率**: 仅{success_rate:.1f}%的股票实现盈利，策略适用性有限。")
    
    # 建议
    report_lines.append("")
    report_lines.append("## 💡 投资建议")
    
    if avg_outperformance > 0 and success_rate > 50:
        report_lines.append("1. **策略值得继续使用**: 在科创板整体表现良好，可以考虑持续应用。")
        report_lines.append("2. **重点配置优秀股票**: 关注策略收益前10名的股票，这些股票策略效果最好。")
        report_lines.append("3. **规避表现差股票**: 避免配置策略收益后10名的股票，策略在这些股票上效果不佳。")
    else:
        report_lines.append("1. **策略需要优化**: 在科创板整体表现一般，建议调整参数或优化策略逻辑。")
        report_lines.append("2. **选择性应用**: 仅在对策略表现好的股票上使用，避免全覆盖。")
        report_lines.append("3. **考虑市场环境**: 科创板波动较大，需结合市场环境调整策略。")
    
    report_lines.append("4. **风险控制**: 设置单日最大亏损和月度最大回撤限制。")
    report_lines.append("5. **定期回测**: 每月重新评估策略有效性。")
    
    report = "\n".join(report_lines)
    
    # 保存报告
    report_file = "gem_50_stocks_summary_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"汇总报告已保存到: {report_file}")
    
    return report

def main():
    """主函数"""
    print("科创板50只股票批量回测系统启动...")
    
    # 执行批量回测
    results = batch_backtest_gem_stocks(GEM_STOCKS, max_workers=8)
    
    # 生成汇总报告
    report = generate_summary_report(results)
    
    print(f"\n{'='*80}")
    print("批量回测任务完成!")
    print("请查看以下文件:")
    print("  1. gem_50_stocks_backtest_results.json - 详细回测结果")
    print("  2. gem_50_stocks_summary_report.md - 汇总分析报告")
    print(f"{'='*80}")

if __name__ == "__main__":
    # 设置Tushare token
    ts.set_token(config.TUSHARE_TOKEN)
    main()