#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创业板标的交叉验证脚本
正向测试：创业板大牛股（回调后创新高）
反向测试：创业板伪突破标的（回调后未创新高）
"""

import subprocess
import sys
import os
from datetime import datetime
import pandas as pd

# 创业板标的列表
GEM_STOCKS = {
    # 正向测试：大牛股（回调后创新高）
    '300502': '新易盛',          # AI算力龙头，已验证
    '300750': '宁德时代',        # 新能源龙头，回调后创新高
    '300059': '东方财富',        # 券商龙头，趋势性强
    '300124': '汇川技术',        # 工业自动化龙头
    '300274': '阳光电源',        # 光伏逆变器龙头
    
    # 反向测试：伪突破标的（回调后未创新高或继续下跌）
    '300166': '东方国信',        # 曾经大牛，但后来持续下跌
    '300017': '网宿科技',        # CDN龙头，但趋势已坏
    '300253': '卫宁健康',        # 医疗信息化，趋势震荡
    '300033': '同花顺',          # 金融软件，波动大
    '300014': '亿纬锂能',        # 锂电池，回调深
}

def run_backtest(ts_code, start_date='2024-01-01', end_date=None):
    """运行单个股票回测"""
    cmd = [sys.executable, 'backtest_stock.py', ts_code, start_date]
    if end_date:
        cmd.append(end_date)
    
    print(f"\n{'='*80}")
    print(f"回测: {ts_code} {GEM_STOCKS[ts_code]}")
    print(f"{'='*80}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    
    # 提取关键信息
    output = result.stdout
    
    # 查找总收益
    total_return = None
    for line in output.split('\n'):
        if '总收益' in line or 'final PnL' in line:
            total_return = line.strip()
            break
    
    # 查找交易次数
    trades_count = 0
    for line in output.split('\n'):
        if '第' in line and '笔' in line and '买入' in line:
            trades_count += 1
    
    # 查找最大单笔收益
    max_trade_return = 0
    for line in output.split('\n'):
        if '收益:' in line and '%' in line:
            try:
                # 提取收益百分比
                parts = line.split('收益:')
                if len(parts) > 1:
                    pct_str = parts[1].split('%')[0].strip()
                    pct = float(pct_str)
                    if pct > max_trade_return:
                        max_trade_return = pct
            except:
                pass
    
    return {
        'ts_code': ts_code,
        'name': GEM_STOCKS[ts_code],
        'output': output[-1000:],  # 只保留最后1000字符
        'total_return': total_return,
        'trades_count': trades_count,
        'max_trade_return': max_trade_return,
        'success': result.returncode == 0
    }

def main():
    """主函数"""
    print("创业板参数优化交叉验证")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试标的数量: {len(GEM_STOCKS)}")
    
    results = []
    
    # 运行所有回测
    for i, ts_code in enumerate(GEM_STOCKS.keys(), 1):
        print(f"\n[{i}/{len(GEM_STOCKS)}] 开始回测 {ts_code}...")
        result = run_backtest(ts_code)
        results.append(result)
    
    # 分析结果
    print(f"\n{'='*80}")
    print("创业板交叉验证结果汇总")
    print(f"{'='*80}")
    
    df_data = []
    for r in results:
        # 解析总收益
        total_pct = 0
        if r['total_return']:
            try:
                # 从字符串中提取百分比
                import re
                match = re.search(r'([+-]?\d+\.?\d*)\s*%', r['total_return'])
                if match:
                    total_pct = float(match.group(1))
            except:
                pass
        
        df_data.append({
            '代码': r['ts_code'],
            '名称': r['name'],
            '总收益%': total_pct,
            '交易次数': r['trades_count'],
            '最大单笔收益%': r['max_trade_return'],
            '成功': 'OK' if r['success'] else 'FAIL'
        })
    
    df = pd.DataFrame(df_data)
    
    # 按总收益排序
    df = df.sort_values('总收益%', ascending=False)
    
    print("\n回测结果排名:")
    print(df.to_string(index=False))
    
    # 统计分析
    print(f"\n{'='*80}")
    print("统计分析:")
    print(f"{'='*80}")
    
    positive = df[df['总收益%'] > 0]
    negative = df[df['总收益%'] <= 0]
    
    print(f"正收益标的: {len(positive)}/{len(df)} ({len(positive)/len(df)*100:.1f}%)")
    print(f"负收益标的: {len(negative)}/{len(df)} ({len(negative)/len(df)*100:.1f}%)")
    
    if len(positive) > 0:
        avg_positive = positive['总收益%'].mean()
        max_positive = positive['总收益%'].max()
        print(f"正收益平均: {avg_positive:.1f}%")
        print(f"正收益最大: {max_positive:.1f}%")
    
    if len(negative) > 0:
        avg_negative = negative['总收益%'].mean()
        min_negative = negative['总收益%'].min()
        print(f"负收益平均: {avg_negative:.1f}%")
        print(f"负收益最小: {min_negative:.1f}%")
    
    # 保存结果到文件
    output_file = f"gem_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n详细结果已保存到: {output_file}")
    
    return df

if __name__ == '__main__':
    main()