"""
创业板压力测试脚本
测试三类标的：
1. 假突破真出货标的
2. 高波动小盘股
3. 稳健白马股（作为基准）
"""

import sys
import pandas as pd
from backtest_stock import main
import io
import contextlib
from datetime import datetime

# 测试标的清单
test_cases = {
    # 1. 假突破真出货标的（需要验证）
    "300123": "亚光科技 - 可能的假突破案例",
    
    # 2. 高波动小盘股（市值50亿以下）
    "300077": "国民技术 - 小市值高波动",
    "300031": "宝通科技 - 小市值高换手",
    
    # 3. 稳健白马股（作为基准）
    "300750": "宁德时代 - 创业板龙头",
    "300059": "东方财富 - 金融科技白马",
    
    # 4. 之前测试的优秀案例（作为对比）
    "300502": "新易盛 - 成功优化案例",
    "300308": "中际旭创 - 最新测试案例"
}

def run_backtest_single(code: str, start_date: str = "2024-01-01"):
    """运行单个标的的回测"""
    print(f"\n{'='*60}")
    print(f"测试: {code} {test_cases[code]}")
    print(f"{'='*60}")
    
    try:
        # 重定向输出
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            sys.argv = ['backtest_stock.py', code, start_date]
            main()
        
        result = output.getvalue()
        
        # 提取关键信息
        lines = result.split('\n')
        
        # 查找关键指标
        total_pnl = 0
        trade_count = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        
        for line in lines:
            if '总收益' in line or 'final PnL' in line:
                # 提取百分比
                import re
                match = re.search(r'[+-]?\d+\.\d+%', line)
                if match:
                    total_pnl = float(match.group().replace('%', ''))
            
            if '交易:' in line and '胜率:' in line:
                parts = line.split('|')
                for part in parts:
                    if '交易:' in part:
                        trade_count = int(part.split(':')[1].strip().split()[0])
                    if '胜率:' in part:
                        win_rate = float(part.split(':')[1].strip().split('%')[0])
                    if '均盈:' in part:
                        avg_win = float(part.split(':')[1].strip().replace('%', ''))
                    if '均亏:' in part:
                        avg_loss = float(part.split(':')[1].strip().replace('%', ''))
                    if '盈亏比:' in part:
                        profit_factor = float(part.split(':')[1].strip())
        
        # 提取交易记录
        trades = []
        in_trade_section = False
        
        for line in lines:
            if '交易记录' in line or '交易明细' in line:
                in_trade_section = True
                continue
            
            if in_trade_section and line.strip() and '---' not in line and '最终:' not in line:
                trades.append(line.strip())
        
        # 计算最大回撤
        max_drawdown = 0
        if len(trades) > 0:
            # 简单方法：找出最大的亏损
            losses = []
            for trade in trades:
                if '%' in trade:
                    # 提取收益
                    import re
                    match = re.search(r'[+-]?\d+\.\d+%', trade)
                    if match:
                        pnl = float(match.group().replace('%', ''))
                        if pnl < 0:
                            losses.append(abs(pnl))
            
            if losses:
                max_drawdown = max(losses)
        
        return {
            'code': code,
            'name': test_cases[code],
            'total_pnl': total_pnl,
            'trade_count': trade_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'trade_details': trades[:5]  # 前5笔交易
        }
        
    except Exception as e:
        print(f"回测失败: {e}")
        return None

def main():
    print("🔄 创业板参数压力测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"参数设置: 浮盈回撤25%，二次上车涨幅限制150%")
    
    results = []
    
    # 运行所有测试
    for code in test_cases:
        result = run_backtest_single(code)
        if result:
            results.append(result)
    
    # 输出总结
    print(f"\n{'='*80}")
    print("📊 压力测试结果总结")
    print(f"{'='*80}")
    
    # 按类别分组
    groups = {
        '假突破标的': [],
        '高波动小盘': [],
        '稳健白马': [],
        '优化案例': []
    }
    
    for r in results:
        if r['code'] in ['300123']:
            groups['假突破标的'].append(r)
        elif r['code'] in ['300077', '300031']:
            groups['高波动小盘'].append(r)
        elif r['code'] in ['300750', '300059']:
            groups['稳健白马'].append(r)
        else:
            groups['优化案例'].append(r)
    
    # 输出各组的平均表现
    for group_name, group_results in groups.items():
        if not group_results:
            continue
            
        print(f"\n🔹 {group_name} (共{len(group_results)}个)")
        print("-" * 40)
        
        avg_pnl = sum(r['total_pnl'] for r in group_results) / len(group_results)
        avg_win_rate = sum(r['win_rate'] for r in group_results) / len(group_results)
        avg_profit_factor = sum(r['profit_factor'] for r in group_results) / len(group_results)
        avg_max_drawdown = sum(r['max_drawdown'] for r in group_results) / len(group_results)
        
        print(f"平均总收益: {avg_pnl:+.1f}%")
        print(f"平均胜率: {avg_win_rate:.1f}%")
        print(f"平均盈亏比: {avg_profit_factor:.2f}")
        print(f"平均最大回撤: {avg_max_drawdown:.1f}%")
        
        # 最佳和最差
        best = max(group_results, key=lambda x: x['total_pnl'])
        worst = min(group_results, key=lambda x: x['total_pnl'])
        
        print(f"最佳: {best['code']} {best['name']} - {best['total_pnl']:+.1f}%")
        print(f"最差: {worst['code']} {worst['name']} - {worst['total_pnl']:+.1f}%")
    
    # 风险收益分析
    print(f"\n{'='*80}")
    print("📈 风险收益分析")
    print(f"{'='*80}")
    
    all_pnls = [r['total_pnl'] for r in results]
    all_drawdowns = [r['max_drawdown'] for r in results]
    
    print(f"总收益范围: {min(all_pnls):+.1f}% ~ {max(all_pnls):+.1f}%")
    print(f"回撤范围: {min(all_drawdowns):.1f}% ~ {max(all_drawdowns):.1f}%")
    
    # 胜率分布
    win_rates = [r['win_rate'] for r in results]
    print(f"胜率分布: {min(win_rates):.1f}% ~ {max(win_rates):.1f}%")
    
    # 参数有效性评估
    print(f"\n{'='*80}")
    print("✅ 参数优化效果评估")
    print(f"{'='*80}")
    
    print("1. 浮盈回撤25%: ")
    print("   - 预期效果: 避免从+40%坐回MA20止损")
    print("   - 验证指标: 观察最大回撤是否控制在合理范围")
    
    print("\n2. 二次上车涨幅限制150%: ")
    print("   - 预期效果: 避免在主升浪末端接盘")
    print("   - 验证指标: 观察小盘股二次上车成功率")
    
    print("\n3. 创业板专用参数: ")
    print("   - MA20容忍度97%，关闭浮盈回撤 → 已调整为25%")
    print("   - 预期效果: 适应创业板大牛股的宽幅回调特征")

if __name__ == "__main__":
    main()