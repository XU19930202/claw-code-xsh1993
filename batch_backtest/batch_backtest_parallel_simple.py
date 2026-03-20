#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版并行回测脚本 - 直接调用已验证的适配函数
===========================================
使用我们之前验证过的 batch_backtest_all_boards_final.py 中的适配逻辑
"""

import os
import sys
import time
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool, cpu_count

import pandas as pd
import tushare as ts

# ============================================================
# 配置区
# ============================================================
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')
START_DATE = '20240101'
END_DATE = '20251231'
INITIAL_CAPITAL = 200000

STOCKS_PER_BOARD = 35
CAPTURE_THRESHOLD = 0.60

# 并行配置
DEFAULT_WORKERS = min(8, cpu_count() - 1)  # 留1核给系统

# 目录
OUTPUT_DIR = Path('backtest_results')
OUTPUT_DIR.mkdir(exist_ok=True)

if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# ============================================================
# 直接导入已验证的适配函数
# ============================================================

def get_adapted_backtest_function():
    """获取已验证的适配回测函数"""
    import sys
    import os
    # 确保可以导入batch_backtest_all_boards_final
    sys.path.insert(0, os.path.dirname(__file__))
    
    try:
        # 导入已验证的适配函数
        from batch_backtest_all_boards_final import run_single_backtest
        return run_single_backtest
    except ImportError:
        # 如果导入失败，使用简化版本
        print("警告：无法导入已验证的适配函数，使用简化版本")
        return _simple_backtest_adaptor

def _simple_backtest_adaptor(ts_code, stock_name, start_date, end_date):
    """简化版适配函数（备份）"""
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
        # 使用subprocess调用我们之前验证过的回测脚本
        import subprocess
        import re
        
        # 使用之前成功的回测命令
        cmd = f"cd .. && python backtest_stock.py {ts_code}"
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if proc.returncode == 0:
            output = proc.stdout
            
            # 从输出中提取关键数据
            m = re.search(r'总收益[：:]\s*([+-]?\d+\.?\d*)%', output)
            if m:
                result['status'] = 'success'
                result['strategy_return_pct'] = float(m.group(1))
            
            m = re.search(r'交易\s*(\d+)\s*笔', output)
            if m:
                result['trade_count'] = int(m.group(1))
            
            m = re.search(r'胜率[：:]\s*(\d+\.?\d*)%', output)
            if m:
                result['win_rate'] = float(m.group(1))
            
            # 从输出中提取最终资金（简化）
            # 这里可以根据实际输出格式调整
            if result['strategy_return_pct'] != 0:
                result['final_capital'] = INITIAL_CAPITAL * (1 + result['strategy_return_pct']/100)
        else:
            result['error_msg'] = f'回测失败: {proc.stderr[:100]}'
            
    except Exception as e:
        result['error_msg'] = f'{type(e).__name__}: {e}'
    
    return result

# ============================================================
# 并行工作函数
# ============================================================

def backtest_worker_simple(task: dict) -> dict:
    """
    简化的并行工作函数
    """
    ts_code = task['ts_code']
    stock_name = task['name']
    board_name = task['board_name']
    price_change = task['price_change']
    max_gain = task['max_gain']
    start_date = task['start_date']
    end_date = task['end_date']
    initial_capital = task['initial_capital']
    
    # 获取适配的回测函数
    backtest_func = get_adapted_backtest_function()
    
    # 执行回测
    result = backtest_func(ts_code, stock_name, start_date, end_date)
    
    # 添加额外字段
    result['board'] = board_name
    result['price_change_pct'] = price_change
    result['max_gain_pct'] = max_gain
    
    # 计算捕获率
    strategy_return = result['strategy_return_pct']
    capture = _calc_capture(strategy_return, price_change)
    
    result['capture_ratio'] = capture['capture_ratio']
    result['scenario'] = capture['scenario']
    result['passed'] = capture['passed']
    
    return result

def _calc_capture(strategy_return: float, price_change: float) -> dict:
    """计算捕获率"""
    info = {'capture_ratio': None, 'scenario': '', 'passed': False}
    
    if abs(price_change) < 1.0:
        info['scenario'] = '股价持平'
        info['passed'] = strategy_return > 0
    elif price_change > 0:
        ratio = strategy_return / price_change
        info['capture_ratio'] = round(ratio, 4)
        if strategy_return > 0:
            info['scenario'] = '上涨+盈利'
            info['passed'] = ratio >= CAPTURE_THRESHOLD
        else:
            info['scenario'] = '上涨+亏损'
            info['passed'] = False
    else:
        if strategy_return >= 0:
            info['scenario'] = '下跌+盈利'
            info['passed'] = True
            info['capture_ratio'] = float('inf')
        else:
            info['scenario'] = '下跌+亏损'
            info['passed'] = abs(strategy_return) < abs(price_change) * 0.5
            info['capture_ratio'] = strategy_return / price_change
    
    return info

# ============================================================
# 并行回测主函数（复用原并行脚本的逻辑）
# ============================================================

def run_parallel_backtest_simple(stocks_df: pd.DataFrame, board_type: str, 
                                 n_workers: int = DEFAULT_WORKERS) -> pd.DataFrame:
    """简化版并行回测"""
    board_names = {'gem': '创业板', 'star': '科创板', 'main': '主板'}
    board_name = board_names.get(board_type, board_type)
    
    # 构建任务列表
    tasks = []
    for _, row in stocks_df.iterrows():
        tasks.append({
            'ts_code': row['ts_code'],
            'name': row['name'],
            'industry': row.get('industry', ''),
            'price_change': row['pct_change'],
            'max_gain': row['max_gain'],
            'board_name': board_name,
            'start_date': START_DATE,
            'end_date': END_DATE,
            'initial_capital': INITIAL_CAPITAL,
        })
    
    total = len(tasks)
    print(f"\n  并行回测: {total} 只股票 × {n_workers} 进程")
    print(f"  CPU核心: {cpu_count()} | 使用: {n_workers}")
    
    t0 = time.time()
    results = []
    completed = 0
    
    with Pool(processes=n_workers) as pool:
        # 使用imap_unordered获取实时进度
        for result in pool.imap_unordered(backtest_worker_simple, tasks):
            completed += 1
            
            # 实时进度
            icon = 'Y' if result['passed'] else 'N'
            ret = result['strategy_return_pct']
            elapsed = time.time() - t0
            eta = elapsed / completed * (total - completed) if completed > 0 else 0
            
            print(f"  [{completed:3d}/{total}] {result['ts_code']} {result['name']:6s} "
                  f"| 策略{ret:+7.1f}% | {result['scenario']:6s} [{icon}] "
                  f"| 耗时{elapsed:.0f}s ETA {eta:.0f}s")
            
            results.append(result)
    
    elapsed = time.time() - t0
    print(f"\n  回测完成: {total} 只, 耗时 {elapsed:.1f}s "
          f"(平均 {elapsed/total:.1f}s/只)")
    
    rdf = pd.DataFrame(results)
    rdf.to_csv(OUTPUT_DIR / f'{board_type}_backtest_detail.csv', index=False, encoding='utf-8-sig')
    
    return rdf

# ============================================================
# 主入口（复用原并行脚本的选股和报告逻辑）
# ============================================================

def main_simple():
    """简化版主入口"""
    parser = argparse.ArgumentParser(description='简化版并行回测')
    parser.add_argument('--workers', '-w', type=int, default=DEFAULT_WORKERS,
                        help=f'并行进程数 (默认{DEFAULT_WORKERS})')
    parser.add_argument('--boards', nargs='+', default=['gem', 'star', 'main'],
                        choices=['gem', 'star', 'main'],
                        help='要回测的板块 (默认全部)')
    args = parser.parse_args()
    
    n_workers = args.workers
    
    print(f"{'#'*70}")
    print(f"# 简化版并行回测")
    print(f"# 时间: {START_DATE} ~ {END_DATE}")
    print(f"# 并行: {n_workers} 进程 (CPU {cpu_count()}核)")
    print(f"# 板块: {', '.join(args.boards)}")
    print(f"# 合格线: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print(f"# 开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")
    
    # 注意：简化版不包含数据缓存，每次重新获取数据
    # 这样虽然慢一些，但更可靠
    
    t_start = time.time()
    
    for board_type in args.boards:
        board_names = {'gem': '创业板', 'star': '科创板', 'main': '主板'}
        print(f"\n{'#'*70}")
        print(f"# {board_names[board_type]}")
        print(f"{'#'*70}")
        
        try:
            # 选股逻辑复用原并行脚本
            from batch_backtest_parallel import select_stocks_by_board
            stocks = select_stocks_by_board(board_type, STOCKS_PER_BOARD)
            
            if stocks.empty:
                print("  选股失败，跳过该板块")
                continue
            
            stocks.to_csv(OUTPUT_DIR / f'{board_type}_selected_stocks.csv', 
                         index=False, encoding='utf-8-sig')
            
            # 并行回测
            t_board = time.time()
            rdf = run_parallel_backtest_simple(stocks, board_type, n_workers)
            board_time = time.time() - t_board
            
            print(f"\n  板块耗时: {board_time:.1f}s")
            
        except Exception as e:
            print(f"\n[错误] {board_type}: {e}")
            traceback.print_exc()
    
    total_time = time.time() - t_start
    print(f"\n总耗时: {total_time:.1f}s ({total_time/60:.1f}分钟)")
    print(f"结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main_simple()