#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创业板标的简化验证脚本
"""

import subprocess
import sys
import os
import json

# 创业板标的列表（简化版）
GEM_STOCKS = {
    # 正向测试
    '300502': '新易盛',
    '300750': '宁德时代',
    '300059': '东方财富',
    
    # 反向测试
    '300166': '东方国信',
    '300017': '网宿科技',
}

def extract_results(output):
    """从回测输出中提取关键结果"""
    results = {
        'total_return': 0,
        'trades': 0,
        'win_trades': 0,
        'max_single_return': 0,
        'has_reentry': False
    }
    
    lines = output.split('\n')
    
    # 查找总收益
    for line in lines:
        if '总收益:' in line or 'final PnL' in line:
            # 提取百分比
            for part in line.split():
                if '%' in part:
                    try:
                        pct_str = part.replace('%', '').replace('+', '')
                        results['total_return'] = float(pct_str)
                        break
                    except:
                        pass
    
    # 查找交易次数和胜率
    for line in lines:
        if '交易:' in line and '笔' in line:
            # 提取 "交易: 5笔 | 胜率: 3/5 = 60%"
            parts = line.split('|')
            for part in parts:
                if '笔' in part:
                    try:
                        num = int(part.split('笔')[0].split()[-1])
                        results['trades'] = num
                    except:
                        pass
                if '胜率:' in part:
                    try:
                        # 提取 "3/5"
                        ratio = part.split('胜率:')[1].split('=')[0].strip()
                        win, total = ratio.split('/')
                        results['win_trades'] = int(win)
                    except:
                        pass
    
    # 查找二次上车
    for line in lines:
        if '二次上车' in line:
            results['has_reentry'] = True
    
    return results

def main():
    """主函数"""
    print("创业板参数优化验证")
    print("=" * 80)
    
    all_results = {}
    
    for ts_code, name in GEM_STOCKS.items():
        print(f"\n正在回测 {ts_code} {name}...")
        
        cmd = [sys.executable, 'backtest_stock.py', ts_code, '2024-01-01']
        result = subprocess.run(cmd, capture_output=True, text=True, 
                               cwd=os.getcwd(), encoding='utf-8', errors='ignore')
        
        if result.returncode == 0:
            extracted = extract_results(result.stdout)
            all_results[ts_code] = {
                'name': name,
                **extracted
            }
            
            # 打印简要结果
            print(f"  总收益: {extracted['total_return']:.1f}%")
            print(f"  交易次数: {extracted['trades']}笔")
            print(f"  胜率: {extracted['win_trades']}/{extracted['trades']}")
            print(f"  二次上车: {'是' if extracted['has_reentry'] else '否'}")
        else:
            print(f"  回测失败")
    
    # 汇总分析
    print(f"\n{'='*80}")
    print("汇总分析:")
    print(f"{'='*80}")
    
    total_return_sum = 0
    total_stocks = 0
    positive_stocks = 0
    negative_stocks = 0
    
    for ts_code, data in all_results.items():
        total_stocks += 1
        total_return_sum += data['total_return']
        
        if data['total_return'] > 0:
            positive_stocks += 1
        else:
            negative_stocks += 1
    
    if total_stocks > 0:
        avg_return = total_return_sum / total_stocks
        positive_rate = positive_stocks / total_stocks * 100
        
        print(f"测试标的数量: {total_stocks}")
        print(f"平均总收益: {avg_return:.1f}%")
        print(f"正收益比例: {positive_rate:.1f}% ({positive_stocks}/{total_stocks})")
        
        # 按收益排序
        sorted_results = sorted(all_results.items(), 
                               key=lambda x: x[1]['total_return'], reverse=True)
        
        print(f"\n收益排名:")
        for i, (ts_code, data) in enumerate(sorted_results[:5], 1):
            print(f"{i:2d}. {ts_code} {data['name']:10s} {data['total_return']:7.1f}% "
                  f"({data['trades']}笔, 胜{data['win_trades']})")
    
    # 保存结果
    with open('gem_validation_results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: gem_validation_results.json")

if __name__ == '__main__':
    main()