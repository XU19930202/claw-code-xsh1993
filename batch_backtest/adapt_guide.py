#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
适配指南 & 快速启动
===================
这个文件帮你快速适配回测脚本到你的现有代码

核心：只需修改 run_single_backtest() 函数，让它调用你的回测逻辑

运行步骤：
    1. 把整个 batch_backtest/ 文件夹复制到你的 Volcengine 项目目录
    2. 修改下面的适配代码
    3. python batch_backtest_all_boards.py
    4. python generate_report.py
"""

# ============================================================
# 步骤1：确认你的回测函数签名
# ============================================================
# 
# 请先在你的服务器上测试这几行代码，确认能正常导入和调用：
#
# >>> from breakout_strategy_v5_patched import backtest
# >>> from params import get_board_type, get_params
# >>>
# >>> # 测试一只股票
# >>> result = backtest('300502.SZ', '新易盛', '20240101', '20251231', 200000)
# >>> print(type(result))  # 看返回值类型
# >>> print(result)         # 看返回值内容
#
# 然后根据返回值格式，修改下面的适配函数


# ============================================================
# 步骤2：适配函数模板
# ============================================================
# 
# 把下面的函数复制替换 batch_backtest_all_boards.py 中的 run_single_backtest()
#

def run_single_backtest(ts_code, stock_name, start_date, end_date):
    """
    【你需要修改这个函数】
    
    返回值格式（必须）：
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
        # ====================================================
        # 模板A：如果 backtest() 返回 (trades_list, summary_dict)
        # ====================================================
        from breakout_strategy_v5_patched import backtest
        
        trades, summary = backtest(
            code=ts_code,
            stock_name=stock_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=INITIAL_CAPITAL,
        )
        
        if summary:
            result['status'] = 'success'
            result['strategy_return_pct'] = summary.get('total_return_pct', 0.0)
            result['trade_count'] = summary.get('trade_count', len(trades or []))
            result['win_rate'] = summary.get('win_rate', 0.0)
            result['final_capital'] = summary.get('final_capital', INITIAL_CAPITAL)
            
            if trades:
                gains = [t.get('return_pct', 0) for t in trades]
                result['max_single_gain'] = max(gains) if gains else 0
                result['max_single_loss'] = min(gains) if gains else 0
        else:
            result['status'] = 'no_signal'

        # ====================================================
        # 模板B：如果 backtest() 只打印结果，需要从stdout捕获
        # ====================================================
        # import subprocess, re
        # cmd = f'python backtest_stock.py {ts_code} --start {start_date} --end {end_date}'
        # proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        # output = proc.stdout
        # 
        # # 从输出中提取关键数据（根据你的输出格式调整正则）
        # m = re.search(r'总收益[：:]\s*([+-]?\d+\.?\d*)%', output)
        # if m:
        #     result['status'] = 'success'
        #     result['strategy_return_pct'] = float(m.group(1))
        # 
        # m = re.search(r'交易\s*(\d+)\s*笔', output)
        # if m:
        #     result['trade_count'] = int(m.group(1))
        # 
        # m = re.search(r'胜率[：:]\s*(\d+\.?\d*)%', output)
        # if m:
        #     result['win_rate'] = float(m.group(1))

        # ====================================================
        # 模板C：如果回测函数直接返回最终资金
        # ====================================================
        # final = backtest(ts_code, start_date, end_date, INITIAL_CAPITAL)
        # result['status'] = 'success'
        # result['strategy_return_pct'] = (final / INITIAL_CAPITAL - 1) * 100
        # result['final_capital'] = final

    except ImportError as e:
        result['error_msg'] = f'导入错误: {e}. 请确认在正确的目录下运行'
    except Exception as e:
        result['error_msg'] = f'{type(e).__name__}: {e}'
    
    return result


# ============================================================
# 步骤3：快速测试（先跑3只确认没问题）
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
        print(f"  错误: {r['error_msg'] or '无'}")
    
    print("\n" + "=" * 60)
    print("如果上面3只都显示 status=success 且收益数据合理，")
    print("就可以运行完整回测了: python batch_backtest_all_boards.py")


if __name__ == '__main__':
    quick_test()