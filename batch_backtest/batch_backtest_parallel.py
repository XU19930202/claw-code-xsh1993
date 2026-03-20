#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全板块批量回测脚本 - 多进程并行版
==================================
利用CPU多核并行加速，14核18线程的Ultra 5 125H可以开8个回测进程

架构设计：
  阶段1: 串行下载数据（Tushare有频率限制，并行反而会被封）
  阶段2: 多进程并行计算（策略回测是纯CPU计算，完美并行）
  阶段3: 汇总结果 + 生成报告

使用方法：
    python batch_backtest_parallel.py              # 默认8进程
    python batch_backtest_parallel.py --workers 4   # 指定4进程
    python batch_backtest_parallel.py --skip-download # 跳过数据下载（已有缓存时）
"""

import os
import sys
import json
import time
import argparse
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from multiprocessing import Pool, cpu_count, Manager
from functools import partial

import pandas as pd
import numpy as np
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
CACHE_DIR = Path('backtest_cache')     # K线数据缓存
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


# ============================================================
# 阶段1: 数据预下载（串行，带缓存）
# ============================================================

def download_kline(ts_code: str, start_date: str, end_date: str) -> bool:
    """下载单只股票K线并缓存到本地parquet文件"""
    cache_file = CACHE_DIR / f'{ts_code.replace(".", "_")}.parquet'
    
    if cache_file.exists():
        return True
    
    try:
        # 多取60天历史用于计算MA等指标
        ext_start = (datetime.strptime(start_date, '%Y%m%d') - timedelta(days=90)).strftime('%Y%m%d')
        
        df = pro.daily(
            ts_code=ts_code,
            start_date=ext_start,
            end_date=end_date,
            fields='ts_code,trade_date,open,high,low,close,vol,amount,pct_chg'
        )
        
        if df is None or len(df) < 60:
            return False
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        df.to_parquet(cache_file, index=False)
        return True
        
    except Exception as e:
        print(f"    [下载失败] {ts_code}: {e}")
        return False


def batch_download(stocks_df: pd.DataFrame, start_date: str, end_date: str):
    """批量下载所有股票数据"""
    codes = stocks_df['ts_code'].tolist()
    total = len(codes)
    success = 0
    
    print(f"\n  数据预下载: {total} 只股票")
    print(f"  缓存目录: {CACHE_DIR}")
    
    for i, code in enumerate(codes):
        cache_file = CACHE_DIR / f'{code.replace(".", "_")}.parquet'
        if cache_file.exists():
            success += 1
            continue
        
        ok = download_kline(code, start_date, end_date)
        if ok:
            success += 1
        
        # 进度条
        pct = (i + 1) / total * 100
        bar = '█' * int(pct // 5) + '░' * (20 - int(pct // 5))
        print(f"\r  [{bar}] {i+1}/{total} ({pct:.0f}%) 缓存命中/成功: {success}", end='', flush=True)
        
        time.sleep(0.15)  # Tushare频率限制
    
    print(f"\n  下载完成: {success}/{total} 成功")
    return success


# ============================================================
# 阶段2: 并行回测（纯CPU计算，不访问网络）
# ============================================================

def backtest_worker(task: dict) -> dict:
    """
    单个回测任务（在子进程中执行）
    
    task 包含:
      ts_code, name, industry, price_change, max_gain, 
      board_name, start_date, end_date, initial_capital
    """
    ts_code = task['ts_code']
    stock_name = task['name']
    board_name = task['board_name']
    price_change = task['price_change']
    max_gain = task['max_gain']
    start_date = task['start_date']
    end_date = task['end_date']
    initial_capital = task['initial_capital']
    
    # 回测结果模板
    bt = {
        'ts_code': ts_code,
        'name': stock_name,
        'status': 'error',
        'strategy_return_pct': 0.0,
        'trade_count': 0,
        'win_rate': 0.0,
        'max_single_gain': 0.0,
        'max_single_loss': 0.0,
        'final_capital': initial_capital,
        'error_msg': '',
    }
    
    try:
        # ====================================================
        # 使用缓存数据调用回测函数（适配实际接口）
        # ====================================================
        import sys
        import os
        import pandas as pd
        import tushare as ts
        # 添加上级目录到Python路径
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        
        from breakout_strategy_v5_patched import backtest
        import config
        
        # 加载缓存数据
        cache_file = CACHE_DIR / f'{ts_code.replace(".", "_")}.parquet'
        if not cache_file.exists():
            bt['error_msg'] = f'缓存文件不存在: {cache_file}'
            return _format_result(bt, price_change, board_name, task)
        
        # 读取缓存数据
        df_cache = pd.read_parquet(cache_file)
        
        # 过滤指定日期范围
        df_filtered = df_cache[(df_cache['trade_date'] >= start_date) & 
                              (df_cache['trade_date'] <= end_date)].copy()
        
        if df_filtered.empty:
            bt['error_msg'] = f'缓存数据中没有指定日期范围的数据'
            return _format_result(bt, price_change, board_name, task)
        
        # 重命名列（适配backtest函数期望的列名格式）
        df_filtered = df_filtered.rename(columns={
            'trade_date': '交易日期',
            'open': '开盘价(元)',
            'high': '最高价(元)', 
            'low': '最低价(元)',
            'close': '收盘价(元)',
            'vol': '成交量(万股)',
            'amount': '成交额(万元)',
            'pct_chg': '涨跌幅(%)'
        })
        
        # 计算前复权收盘价（使用简单方法）
        # 注意：实际的复权计算更复杂，这里简化处理
        df_filtered['收盘价(前复权)(元)'] = df_filtered['收盘价(元)']
        
        # 转换成交量单位：手 → 万股（parquet文件中的vol是手，需要转换为万股）
        df_filtered['成交量(万股)'] = df_filtered['成交量(万股)'] / 100
        
        # 转换日期格式
        df_filtered['交易日期'] = pd.to_datetime(df_filtered['交易日期'], format='%Y%m%d')
        
        # 获取上证指数数据
        if 'TUSHARE_TOKEN' in dir(config):
            ts.set_token(config.TUSHARE_TOKEN)
            pro = ts.pro_api()
            
            # 获取指数数据
            index_df_raw = pro.index_daily(ts_code='000001.SH', start_date=start_date, end_date=end_date,
                                           fields='ts_code,trade_date,pct_chg')
            if not index_df_raw.empty:
                index_df = pd.DataFrame({
                    '交易日期': pd.to_datetime(index_df_raw['trade_date'], format='%Y%m%d'),
                    '涨跌幅(%)': index_df_raw['pct_chg'].astype(float)
                })
            else:
                index_df = None
            
        # 获取换手率数据
        basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                   fields='trade_date,turnover_rate,volume_ratio')
        if basic_df is not None and not basic_df.empty:
            basic_df['交易日期'] = pd.to_datetime(basic_df['trade_date'], format='%Y%m%d')
            df_filtered = df_filtered.merge(basic_df[['交易日期', 'turnover_rate', 'volume_ratio']], 
                                           on='交易日期', how='left')
            df_filtered['换手率(%)'] = df_filtered['turnover_rate']
            # 填充NaN值为0
            df_filtered['换手率(%)'] = df_filtered['换手率(%)'].fillna(0)
        else:
            df_filtered['换手率(%)'] = 0
        
        # 提取纯代码数字部分
        code_only = ts_code.split('.')[0]
        
        # 执行回测（根据实际函数签名）
        trades = backtest(
            stock_df=df_filtered,
            code=code_only,
            index_df=index_df,
            verbose=False,  # 批量模式不打印详细日志
            stock_name=stock_name
        )
        
        # 解析结果
        if not trades:
            bt['status'] = 'no_signal'
            bt['error_msg'] = '回测期间无交易信号'
        else:
            bt['status'] = 'success'
            
            # 计算总收益和统计信息
            final_capital = initial_capital
            all_returns = []
            
            for trade in trades:
                # 计算每笔交易的收益率
                trade_return_pct = trade.pnl
                all_returns.append(trade_return_pct)
                
                # 计算资金变化（简化处理）
                trade_profit = initial_capital * (trade_return_pct / 100)
                final_capital += trade_profit
            
            # 计算总收益率
            total_return_pct = (final_capital / initial_capital - 1) * 100
            
            # 计算胜率
            winning_trades = [r for r in all_returns if r > 0]
            win_rate = len(winning_trades) / len(all_returns) * 100 if all_returns else 0
            
            bt['strategy_return_pct'] = total_return_pct
            bt['trade_count'] = len(trades)
            bt['win_rate'] = win_rate
            bt['final_capital'] = final_capital
            bt['max_single_gain'] = max(all_returns) if all_returns else 0
            bt['max_single_loss'] = min(all_returns) if all_returns else 0
            
    except Exception as e:
        bt['error_msg'] = f'{type(e).__name__}: {e}'
    
    return _format_result(bt, price_change, board_name, task)


def _format_result(bt: dict, price_change: float, board_name: str, task: dict) -> dict:
    """格式化回测结果"""
    # 计算捕获率
    strategy_return = bt['strategy_return_pct']
    capture = _calc_capture(strategy_return, price_change)
    
    # 组装最终结果
    result = {
        'board': board_name,
        'ts_code': bt['ts_code'],
        'name': bt['name'],
        'industry': task.get('industry', ''),
        'price_change_pct': price_change,
        'max_gain_pct': task.get('max_gain', 0),
        'strategy_return_pct': round(strategy_return, 2),
        'capture_ratio': capture['capture_ratio'],
        'scenario': capture['scenario'],
        'passed': capture['passed'],
        'trade_count': bt['trade_count'],
        'win_rate': bt['win_rate'],
        'max_single_gain': bt['max_single_gain'],
        'max_single_loss': bt['max_single_loss'],
        'status': bt['status'],
        'error_msg': bt['error_msg'],
    }
    
    return result


def _calc_capture(strategy_return: float, price_change: float) -> dict:
    """计算捕获率（子进程可调用的纯函数）"""
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


def run_parallel_backtest(stocks_df: pd.DataFrame, board_type: str, 
                          n_workers: int = DEFAULT_WORKERS) -> pd.DataFrame:
    """多进程并行回测一个板块"""
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
    
    # ★ 核心：多进程并行 ★
    results = []
    completed = 0
    
    with Pool(processes=n_workers) as pool:
        # imap_unordered: 谁先完成谁先返回，可以实时打印进度
        for result in pool.imap_unordered(backtest_worker, tasks):
            completed += 1
            
            # 实时进度（使用ASCII字符避免编码问题）
            icon = 'Y' if result['passed'] else 'N'
            ret = result['strategy_return_pct']
            elapsed = time.time() - t0
            eta = elapsed / completed * (total - completed)
            
            print(f"  [{completed:3d}/{total}] {result['ts_code']} {result['name']:6s} "
                  f"| 策略{ret:+7.1f}% | {result['scenario']:6s} [{icon}] "
                  f"| 耗时{elapsed:.0f}s ETA {eta:.0f}s")
            
            results.append(result)
    
    elapsed = time.time() - t0
    print(f"\n  回测完成: {total} 只, 耗时 {elapsed:.1f}s "
          f"(平均 {elapsed/total:.1f}s/只, 串行预估 {elapsed/total*total*n_workers/total:.0f}s)")
    
    rdf = pd.DataFrame(results)
    rdf.to_csv(OUTPUT_DIR / f'{board_type}_backtest_detail.csv', index=False, encoding='utf-8-sig')
    
    return rdf


# ============================================================
# 选股（复用原版逻辑）
# ============================================================

def select_stocks_by_board(board_type: str, n: int = 35) -> pd.DataFrame:
    """按板块选股，分层抽样保证覆盖不同走势"""
    print(f"\n{'='*60}")
    print(f"选股: {board_type} 板块，目标 {n} 只")
    print(f"{'='*60}")
    
    df = pro.stock_basic(exchange='', list_status='L',
                         fields='ts_code,symbol,name,area,industry,list_date,market')
    
    if board_type == 'gem':
        mask = df['ts_code'].str.startswith(('300', '301'))
        board_name = '创业板'
    elif board_type == 'star':
        mask = df['ts_code'].str.startswith('688')
        board_name = '科创板'
    elif board_type == 'main':
        mask = (df['ts_code'].str.startswith(('600', '601', '603', '605',
                                               '000', '001', '002', '003')))
        board_name = '主板'
    else:
        raise ValueError(f"未知板块: {board_type}")
    
    df = df[mask].copy()
    df = df[~df['name'].str.contains('ST|退', na=False)]
    
    cutoff = (datetime.strptime(START_DATE, '%Y%m%d') - timedelta(days=180)).strftime('%Y%m%d')
    df = df[df['list_date'] <= cutoff]
    
    print(f"  {board_name} 可选标的: {len(df)} 只")
    
    # 获取区间涨跌幅
    results = []
    codes = df['ts_code'].tolist()
    
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        for code in batch:
            try:
                kline = pro.daily(ts_code=code, start_date=START_DATE, end_date=END_DATE,
                                  fields='ts_code,trade_date,open,close')
                if kline is None or len(kline) < 60:
                    continue
                kline = kline.sort_values('trade_date')
                first_close = kline.iloc[0]['close']
                last_close = kline.iloc[-1]['close']
                max_close = kline['close'].max()
                pct_change = (last_close / first_close - 1) * 100
                max_gain = (max_close / first_close - 1) * 100
                results.append({
                    'ts_code': code,
                    'name': df[df['ts_code']==code]['name'].values[0],
                    'industry': df[df['ts_code']==code]['industry'].values[0],
                    'first_close': first_close,
                    'last_close': last_close,
                    'max_close': max_close,
                    'pct_change': round(pct_change, 2),
                    'max_gain': round(max_gain, 2),
                })
            except Exception:
                continue
        time.sleep(0.3)

    if not results:
        return pd.DataFrame()
    
    rdf = pd.DataFrame(results)
    
    n_each = n // 3
    n_extra = n - n_each * 3
    
    big_gainers = rdf[rdf['max_gain'] > 50].nlargest(n_each + n_extra, 'max_gain')
    mid_stocks = rdf[(rdf['max_gain'] > 0) & (rdf['max_gain'] <= 50)].sample(
        n=min(n_each, len(rdf[(rdf['max_gain'] > 0) & (rdf['max_gain'] <= 50)])),
        random_state=42
    )
    weak_stocks = rdf[rdf['pct_change'] < 0].nsmallest(n_each, 'pct_change')
    
    selected = pd.concat([big_gainers, mid_stocks, weak_stocks]).drop_duplicates('ts_code')
    
    if len(selected) < n:
        remaining = rdf[~rdf['ts_code'].isin(selected['ts_code'])]
        extra = remaining.sample(n=min(n - len(selected), len(remaining)), random_state=42)
        selected = pd.concat([selected, extra])
    
    selected = selected.head(n).reset_index(drop=True)
    
    print(f"  已选 {len(selected)} 只:")
    print(f"    大涨(>50%): {len(selected[selected['max_gain']>50])} 只")
    print(f"    中等(0~50%): {len(selected[(selected['max_gain']>0)&(selected['max_gain']<=50)])} 只")
    print(f"    弱势(<0%): {len(selected[selected['pct_change']<0])} 只")
    
    return selected


# ============================================================
# 汇总报告（复用原版 + 速度对比）
# ============================================================

def print_board_summary(rdf: pd.DataFrame, board_name: str):
    """打印板块回测汇总"""
    if rdf.empty:
        return
    valid = rdf[rdf['status'].isin(['success', 'no_signal'])]
    success = valid[valid['status'] == 'success']
    
    print(f"\n{'='*70}")
    print(f"{board_name} 回测汇总")
    print(f"{'='*70}")
    print(f"  标的总数: {len(rdf)}")
    print(f"  有效回测: {len(valid)} (有信号: {len(success)}, 无信号: {len(valid)-len(success)})")
    
    if len(success) > 0:
        passed = success[success['passed']]
        pass_rate = len(passed) / len(success) * 100
        
        print(f"\n  ---- 核心指标 ----")
        print(f"  合格数: {len(passed)} / {len(success)}")
        print(f"  ★ 合格率: {pass_rate:.1f}% (目标 >= 60%)")
        print(f"  平均策略收益: {success['strategy_return_pct'].mean():+.1f}%")
        print(f"  平均股价涨幅: {success['price_change_pct'].mean():+.1f}%")
        
        for scenario in ['上涨+盈利', '上涨+亏损', '下跌+盈利', '下跌+亏损', '股价持平']:
            subset = success[success['scenario'] == scenario]
            if len(subset) > 0:
                sp = len(subset[subset['passed']])
                print(f"    {scenario}: {len(subset)}只, 合格{sp}只")
        
        print(f"\n  ---- 收益分布 ----")
        print(f"  最佳: {success['strategy_return_pct'].max():+.1f}% ({success.loc[success['strategy_return_pct'].idxmax(), 'name']})")
        print(f"  最差: {success['strategy_return_pct'].min():+.1f}% ({success.loc[success['strategy_return_pct'].idxmin(), 'name']})")
        print(f"  中位数: {success['strategy_return_pct'].median():+.1f}%")
        
        up_profit = success[success['scenario'] == '上涨+盈利']
        if len(up_profit) > 0:
            ratios = up_profit['capture_ratio'].dropna()
            ratios = ratios[~ratios.apply(lambda x: x == float('inf') or (isinstance(x, float) and np.isinf(x)))]
            if len(ratios) > 0:
                print(f"\n  ---- 捕获率分布 (上涨股) ----")
                print(f"  平均: {ratios.mean():.1%}")
                print(f"  中位: {ratios.median():.1%}")
                print(f"  >=60%: {len(ratios[ratios>=0.6])}/{len(ratios)}")
                print(f"  >=80%: {len(ratios[ratios>=0.8])}/{len(ratios)}")


def generate_final_report(all_boards: dict):
    """全板块汇总报告"""
    all_data = [rdf for rdf in all_boards.values() if not rdf.empty]
    if not all_data:
        print("无有效数据")
        return
    
    combined = pd.concat(all_data, ignore_index=True)
    combined.to_csv(OUTPUT_DIR / 'all_boards_backtest_detail.csv', index=False, encoding='utf-8-sig')
    
    valid = combined[combined['status'] == 'success']
    
    print(f"\n{'#'*70}")
    print(f"# 全 板 块 回 测 最 终 报 告")
    print(f"{'#'*70}")
    
    if len(valid) > 0:
        passed_all = valid[valid['passed']]
        overall_rate = len(passed_all) / len(valid) * 100
        
        print(f"\n  总标的: {len(combined)} | 有效: {len(valid)} | 合格: {len(passed_all)}")
        print(f"\n  ★★★ 总体合格率: {overall_rate:.1f}% {'[达标]' if overall_rate >= 60 else '[未达标]'} ★★★")
        
        # 分板块
        print(f"\n  分板块:")
        board_summary = []
        for board in ['创业板', '科创板', '主板']:
            bdf = valid[valid['board'] == board]
            if len(bdf) == 0:
                continue
            bp = bdf[bdf['passed']]
            rate = len(bp) / len(bdf) * 100
            verdict = '[Y]' if rate >= 60 else '[N]'
            print(f"    {board}: {len(bp)}/{len(bdf)} = {rate:.1f}% {verdict} "
                  f"| 平均策略{bdf['strategy_return_pct'].mean():+.1f}%")
            board_summary.append({
                'board': board, 'total': len(bdf), 'passed': len(bp),
                'pass_rate': round(rate, 1),
                'avg_strategy_return': round(bdf['strategy_return_pct'].mean(), 1),
            })
        
        pd.DataFrame(board_summary).to_csv(
            OUTPUT_DIR / 'board_summary.csv', index=False, encoding='utf-8-sig')
        
        # TOP/BOTTOM
        print(f"\n  TOP 5:")
        for _, r in valid.nlargest(5, 'strategy_return_pct').iterrows():
            print(f"    {r['ts_code']} {r['name']:6s} | 策略{r['strategy_return_pct']:+.1f}% | 股价{r['price_change_pct']:+.1f}%")
        
        print(f"\n  BOTTOM 5:")
        for _, r in valid.nsmallest(5, 'strategy_return_pct').iterrows():
            print(f"    {r['ts_code']} {r['name']:6s} | 策略{r['strategy_return_pct']:+.1f}% | 股价{r['price_change_pct']:+.1f}%")
        
        # 最终判定
        print(f"\n{'='*70}")
        if overall_rate >= 60:
            print(f"  结论: 策略有效 (合格率{overall_rate:.1f}% >= 60%)")
            print(f"  建议: 对不合格标的做case study，进一步优化到70%+")
        else:
            print(f"  结论: 需要调整 (合格率{overall_rate:.1f}% < 60%)")
            for bs in board_summary:
                if bs['pass_rate'] < 60:
                    print(f"  → {bs['board']} 仅 {bs['pass_rate']}% 需重点优化")
    
    return combined


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='全板块批量回测 (多进程并行)')
    parser.add_argument('--workers', '-w', type=int, default=DEFAULT_WORKERS,
                        help=f'并行进程数 (默认{DEFAULT_WORKERS})')
    parser.add_argument('--skip-download', action='store_true',
                        help='跳过数据下载（使用缓存）')
    parser.add_argument('--boards', nargs='+', default=['gem', 'star', 'main'],
                        choices=['gem', 'star', 'main'],
                        help='要回测的板块 (默认全部)')
    args = parser.parse_args()
    
    n_workers = args.workers
    
    print(f"{'#'*70}")
    print(f"# 全板块批量回测 - 多进程并行版")
    print(f"# 时间: {START_DATE} ~ {END_DATE}")
    print(f"# 并行: {n_workers} 进程 (CPU {cpu_count()}核)")
    print(f"# 板块: {', '.join(args.boards)}")
    print(f"# 合格线: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print(f"# 开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")
    
    t_start = time.time()
    all_boards = {}
    
    for board_type in args.boards:
        board_names = {'gem': '创业板', 'star': '科创板', 'main': '主板'}
        print(f"\n{'#'*70}")
        print(f"# {board_names[board_type]}")
        print(f"{'#'*70}")
        
        try:
            # 1. 选股
            stocks = select_stocks_by_board(board_type, STOCKS_PER_BOARD)
            if stocks.empty:
                all_boards[board_type] = pd.DataFrame()
                continue
            stocks.to_csv(OUTPUT_DIR / f'{board_type}_selected_stocks.csv', 
                         index=False, encoding='utf-8-sig')
            
            # 2. 预下载数据
            if not args.skip_download:
                batch_download(stocks, START_DATE, END_DATE)
            
            # 3. 并行回测 ★
            t_board = time.time()
            rdf = run_parallel_backtest(stocks, board_type, n_workers)
            board_time = time.time() - t_board
            
            # 4. 板块汇总
            print_board_summary(rdf, board_names[board_type])
            print(f"\n  板块耗时: {board_time:.1f}s")
            
            all_boards[board_type] = rdf
            
        except Exception as e:
            print(f"\n[错误] {board_type}: {e}")
            traceback.print_exc()
            all_boards[board_type] = pd.DataFrame()
    
    # 5. 全板块汇总
    combined = generate_final_report(all_boards)
    
    total_time = time.time() - t_start
    print(f"\n总耗时: {total_time:.1f}s ({total_time/60:.1f}分钟)")
    print(f"结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return combined


if __name__ == '__main__':
    main()