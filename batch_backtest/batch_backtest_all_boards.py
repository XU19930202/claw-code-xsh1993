#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全板块批量回测脚本
================
目标：策略收益 / 股价区间涨幅 >= 60% 即为合格
回测区间：2024-01-01 ~ 2025-12-31
板块：创业板(300/301) + 科创板(688) + 主板(600/000/001/002/003)

使用方法：
    python batch_backtest_all_boards.py

依赖：在你的Volcengine服务器上运行，需要 tushare, pandas, breakout_strategy_v5_patched
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import tushare as ts

# ============================================================
# 配置区 - 按需修改
# ============================================================
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')  # 从环境变量读取，或直接填写
START_DATE = '20240101'
END_DATE = '20251231'
INITIAL_CAPITAL = 200000  # 20万初始资金

# 每板块选股数量
STOCKS_PER_BOARD = 35  

# 合格阈值：策略收益 / 股价涨幅 >= 60%
CAPTURE_THRESHOLD = 0.60

# 输出目录
OUTPUT_DIR = Path('backtest_results')
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# Tushare 初始化
# ============================================================
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


# ============================================================
# 第一步：板块选股
# ============================================================

def select_stocks_by_board(board_type: str, n: int = 35) -> pd.DataFrame:
    """
    按板块选股，选取有代表性的标的（兼顾大中小市值）
    
    选股逻辑：
    1. 排除ST、退市
    2. 排除上市不足6个月的次新股
    3. 按市值分3档（大/中/小），每档选1/3
    4. 优先选区间内有明显涨幅的（更能检验策略捕获能力）
    
    board_type: 'gem'(创业板) / 'star'(科创板) / 'main'(主板)
    """
    print(f"\n{'='*60}")
    print(f"选股: {board_type} 板块，目标 {n} 只")
    print(f"{'='*60}")
    
    # 获取股票列表
    df = pro.stock_basic(exchange='', list_status='L',
                         fields='ts_code,symbol,name,area,industry,list_date,market')
    
    # 按板块过滤
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
    
    # 排除ST
    df = df[~df['name'].str.contains('ST|退', na=False)]
    
    # 排除上市不足6个月
    cutoff = (datetime.strptime(START_DATE, '%Y%m%d') - timedelta(days=180)).strftime('%Y%m%d')
    df = df[df['list_date'] <= cutoff]
    
    print(f"  {board_name} 可选标的: {len(df)} 只")
    
    # 获取区间涨跌幅（用于选取有代表性的标的）
    results = []
    codes = df['ts_code'].tolist()
    
    # 分批获取行情
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
        time.sleep(0.3)  # Tushare频率限制
        
    if not results:
        print(f"  [警告] {board_name} 未获取到有效数据")
        return pd.DataFrame()
    
    rdf = pd.DataFrame(results)
    
    # 分层选股：确保覆盖不同走势类型
    # 1/3 大涨股（max_gain > 50%）  - 检验策略的趋势捕获能力
    # 1/3 中等股（0% < max_gain <= 50%）- 检验策略的基本盈利能力
    # 1/3 下跌/震荡股（max_gain <= 0% 或 pct_change < 0）- 检验策略的风控能力
    
    n_each = n // 3
    n_extra = n - n_each * 3
    
    big_gainers = rdf[rdf['max_gain'] > 50].nlargest(n_each + n_extra, 'max_gain')
    mid_stocks = rdf[(rdf['max_gain'] > 0) & (rdf['max_gain'] <= 50)].sample(
        n=min(n_each, len(rdf[(rdf['max_gain'] > 0) & (rdf['max_gain'] <= 50)])),
        random_state=42
    )
    weak_stocks = rdf[rdf['pct_change'] < 0].nsmallest(n_each, 'pct_change')
    
    selected = pd.concat([big_gainers, mid_stocks, weak_stocks]).drop_duplicates('ts_code')
    
    # 如果不够数，随机补齐
    if len(selected) < n:
        remaining = rdf[~rdf['ts_code'].isin(selected['ts_code'])]
        extra = remaining.sample(n=min(n - len(selected), len(remaining)), random_state=42)
        selected = pd.concat([selected, extra])
    
    selected = selected.head(n).reset_index(drop=True)
    
    print(f"  已选 {len(selected)} 只:")
    print(f"    大涨(>50%): {len(selected[selected['max_gain']>50])} 只")
    print(f"    中等(0~50%): {len(selected[(selected['max_gain']>0)&(selected['max_gain']<=50)])} 只")
    print(f"    弱势(<0%): {len(selected[selected['pct_change']<0])} 只")
    print(f"    平均区间涨幅: {selected['pct_change'].mean():.1f}%")
    
    return selected


# ============================================================
# 第二步：单股回测（适配你的现有回测函数）
# ============================================================

def run_single_backtest(ts_code: str, stock_name: str, start_date: str, end_date: str) -> dict:
    """
    运行单只股票回测，返回标准化结果
    
    需要根据你的实际回测函数接口来适配！
    下面提供了两种常见接口的适配方式。
    """
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
        # 方式A：使用 breakout_strategy_v5_patched.backtest()
        # 取消注释并根据你的实际函数签名调整
        # ====================================================
        from breakout_strategy_v5_patched import backtest
        from params import get_board_type, get_params
        
        board_type = get_board_type(ts_code, stock_name)
        p = get_params(board_type)
        
        # 调用回测（根据你的实际函数签名调整参数）
        trades, summary = backtest(
            code=ts_code,
            stock_name=stock_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=INITIAL_CAPITAL,
        )
        
        # 解析结果（根据你的返回值格式调整）
        if summary:
            result['status'] = 'success'
            result['strategy_return_pct'] = summary.get('total_return_pct', 0.0)
            result['trade_count'] = summary.get('trade_count', len(trades) if trades else 0)
            result['win_rate'] = summary.get('win_rate', 0.0)
            result['final_capital'] = summary.get('final_capital', INITIAL_CAPITAL)
            result['trades'] = trades if trades else []
            
            if trades:
                gains = [t.get('return_pct', 0) for t in trades]
                result['max_single_gain'] = max(gains) if gains else 0
                result['max_single_loss'] = min(gains) if gains else 0
        else:
            result['status'] = 'no_signal'
            result['error_msg'] = '回测期间无交易信号'
        
        # ====================================================
        # 方式B：使用 backtest_stock.py 命令行方式
        # 如果方式A不可用，取消注释下面的代码
        # ====================================================
        # import subprocess
        # cmd = f'python backtest_stock.py {ts_code} --start {start_date} --end {end_date}'
        # proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        # # 解析stdout输出...
        # result['status'] = 'success'
        
    except ImportError as e:
        result['error_msg'] = f'导入错误: {e}'
    except Exception as e:
        result['error_msg'] = f'{type(e).__name__}: {e}'
        traceback.print_exc()
    
    return result


# ============================================================
# 第三步：计算捕获率
# ============================================================

def calculate_capture_ratio(strategy_return: float, price_change: float) -> dict:
    """
    计算策略的涨幅捕获率
    
    核心指标：strategy_return / price_change
    
    分几种情况：
    1. 股价上涨 + 策略盈利 → 捕获率 = 策略收益/股价涨幅（越高越好）
    2. 股价上涨 + 策略亏损 → 捕获率 = 负值（策略失败）
    3. 股价下跌 + 策略亏损 → 看策略是否亏得比股价少（风控能力）
    4. 股价下跌 + 策略盈利 → 捕获率 = 正无穷（策略很好，逆势盈利）
    5. 股价持平             → 直接看策略是否盈利
    """
    info = {
        'strategy_return': strategy_return,
        'price_change': price_change,
        'capture_ratio': None,
        'scenario': '',
        'passed': False,
    }
    
    if abs(price_change) < 1.0:
        # 股价基本持平，只看策略是否盈利
        info['scenario'] = '股价持平'
        info['capture_ratio'] = None
        info['passed'] = strategy_return > 0
        
    elif price_change > 0:
        # 股价上涨
        ratio = strategy_return / price_change
        info['capture_ratio'] = round(ratio, 4)
        if strategy_return > 0:
            info['scenario'] = '上涨+盈利'
            info['passed'] = ratio >= CAPTURE_THRESHOLD
        else:
            info['scenario'] = '上涨+亏损'
            info['passed'] = False
            
    else:
        # 股价下跌
        if strategy_return >= 0:
            info['scenario'] = '下跌+盈利'
            info['passed'] = True  # 逆势盈利，直接合格
            info['capture_ratio'] = float('inf')
        else:
            info['scenario'] = '下跌+亏损'
            # 策略亏损是否小于股价跌幅？
            info['passed'] = abs(strategy_return) < abs(price_change) * 0.5
            info['capture_ratio'] = strategy_return / price_change  # >1说明亏得比股价还多
    
    return info


# ============================================================
# 第四步：主流程
# ============================================================

def run_board_backtest(board_type: str) -> pd.DataFrame:
    """运行单个板块的批量回测"""
    board_names = {'gem': '创业板', 'star': '科创板', 'main': '主板'}
    board_name = board_names.get(board_type, board_type)
    
    print(f"\n{'#'*70}")
    print(f"# 板块回测: {board_name}")
    print(f"# 时间: {START_DATE} ~ {END_DATE}")
    print(f"# 合格线: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print(f"{'#'*70}")
    
    # 1. 选股
    stocks = select_stocks_by_board(board_type, STOCKS_PER_BOARD)
    if stocks.empty:
        print(f"  [跳过] {board_name} 无有效标的")
        return pd.DataFrame()
    
    # 保存选股结果
    stocks.to_csv(OUTPUT_DIR / f'{board_type}_selected_stocks.csv', index=False, encoding='utf-8-sig')
    
    # 2. 逐只回测
    all_results = []
    total = len(stocks)
    
    for idx, row in stocks.iterrows():
        code = row['ts_code']
        name = row['name']
        price_change = row['pct_change']
        max_gain = row['max_gain']
        
        print(f"\n  [{idx+1}/{total}] {code} {name}")
        print(f"    区间涨幅: {price_change:+.1f}% | 最大涨幅: {max_gain:+.1f}%")
        
        # 运行回测
        bt_result = run_single_backtest(code, name, START_DATE, END_DATE)
        
        strategy_return = bt_result['strategy_return_pct']
        
        # 计算捕获率
        capture = calculate_capture_ratio(strategy_return, price_change)
        
        # 合并结果
        row_result = {
            'board': board_name,
            'ts_code': code,
            'name': name,
            'industry': row.get('industry', ''),
            'price_change_pct': price_change,
            'max_gain_pct': max_gain,
            'strategy_return_pct': round(strategy_return, 2),
            'capture_ratio': capture['capture_ratio'],
            'scenario': capture['scenario'],
            'passed': capture['passed'],
            'trade_count': bt_result['trade_count'],
            'win_rate': bt_result['win_rate'],
            'max_single_gain': bt_result['max_single_gain'],
            'max_single_loss': bt_result['max_single_loss'],
            'status': bt_result['status'],
            'error_msg': bt_result['error_msg'],
        }
        all_results.append(row_result)
        
        # 实时打印
        status_icon = '✓' if capture['passed'] else '✗'
        ratio_str = f"{capture['capture_ratio']:.1%}" if capture['capture_ratio'] is not None and capture['capture_ratio'] != float('inf') else capture['scenario']
        print(f"    策略收益: {strategy_return:+.1f}% | 捕获率: {ratio_str} [{status_icon}]")
        print(f"    交易: {bt_result['trade_count']}笔 | 胜率: {bt_result['win_rate']:.0f}%")
        
        time.sleep(0.2)  # 避免API频率限制
    
    rdf = pd.DataFrame(all_results)
    
    # 保存详细结果
    rdf.to_csv(OUTPUT_DIR / f'{board_type}_backtest_detail.csv', index=False, encoding='utf-8-sig')
    
    # 3. 打印板块汇总
    print_board_summary(rdf, board_name)
    
    return rdf


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
    print(f"  回测失败: {len(rdf)-len(valid)}")
    
    if len(success) > 0:
        passed = success[success['passed']]
        pass_rate = len(passed) / len(success) * 100
        
        print(f"\n  ---- 核心指标 ----")
        print(f"  合格数: {len(passed)} / {len(success)}")
        print(f"  ★ 合格率: {pass_rate:.1f}% (目标 >= 60%)")
        print(f"  平均策略收益: {success['strategy_return_pct'].mean():+.1f}%")
        print(f"  平均股价涨幅: {success['price_change_pct'].mean():+.1f}%")
        
        # 分场景统计
        for scenario in ['上涨+盈利', '上涨+亏损', '下跌+盈利', '下跌+亏损', '股价持平']:
            subset = success[success['scenario'] == scenario]
            if len(subset) > 0:
                sp = len(subset[subset['passed']])
                print(f"    {scenario}: {len(subset)}只, 合格{sp}只")
        
        print(f"\n  ---- 收益分布 ----")
        print(f"  最佳: {success['strategy_return_pct'].max():+.1f}% ({success.loc[success['strategy_return_pct'].idxmax(), 'name']})")
        print(f"  最差: {success['strategy_return_pct'].min():+.1f}% ({success.loc[success['strategy_return_pct'].idxmin(), 'name']})")
        print(f"  中位数: {success['strategy_return_pct'].median():+.1f}%")
        print(f"  盈利标的: {len(success[success['strategy_return_pct']>0])} / {len(success)}")
        
        # 捕获率分布（仅上涨+盈利场景）
        up_profit = success[success['scenario'] == '上涨+盈利']
        if len(up_profit) > 0:
            ratios = up_profit['capture_ratio'].dropna()
            print(f"\n  ---- 捕获率分布 (上涨股) ----")
            print(f"  平均: {ratios.mean():.1%}")
            print(f"  中位: {ratios.median():.1%}")
            print(f"  >=60%: {len(ratios[ratios>=0.6])}/{len(ratios)}")
            print(f"  >=80%: {len(ratios[ratios>=0.8])}/{len(ratios)}")
            print(f"  >=100%: {len(ratios[ratios>=1.0])}/{len(ratios)}")


# ============================================================
# 第五步：全板块汇总 + 最终报告
# ============================================================

def generate_final_report(all_boards: dict):
    """生成最终报告"""
    all_data = []
    for board_type, rdf in all_boards.items():
        if not rdf.empty:
            all_data.append(rdf)
    
    if not all_data:
        print("无有效数据，无法生成报告")
        return
    
    combined = pd.concat(all_data, ignore_index=True)
    combined.to_csv(OUTPUT_DIR / 'all_boards_backtest_detail.csv', index=False, encoding='utf-8-sig')
    
    valid = combined[combined['status'] == 'success']
    
    print(f"\n{'#'*70}")
    print(f"# 全 板 块 回 测 最 终 报 告")
    print(f"# 时间: {START_DATE} ~ {END_DATE}")
    print(f"# 合格线: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print(f"{'#'*70}")
    
    # 总览
    print(f"\n{'='*60}")
    print(f"一、总体概览")
    print(f"{'='*60}")
    print(f"  总标的数: {len(combined)}")
    print(f"  有效回测: {len(valid)}")
    
    if len(valid) > 0:
        passed_all = valid[valid['passed']]
        overall_rate = len(passed_all) / len(valid) * 100
        
        print(f"  合格数: {len(passed_all)} / {len(valid)}")
        print(f"\n  ★★★ 总体合格率: {overall_rate:.1f}% {'✓ 达标' if overall_rate >= 60 else '✗ 未达标'} ★★★")
        print(f"  (目标: >= 60%)")
    
    # 按板块
    print(f"\n{'='*60}")
    print(f"二、分板块结果")
    print(f"{'='*60}")
    
    board_summary = []
    for board in ['创业板', '科创板', '主板']:
        bdf = valid[valid['board'] == board]
        if len(bdf) == 0:
            continue
        bp = bdf[bdf['passed']]
        rate = len(bp) / len(bdf) * 100
        avg_ret = bdf['strategy_return_pct'].mean()
        avg_price = bdf['price_change_pct'].mean()
        
        verdict = '✓ 达标' if rate >= 60 else '✗ 未达标'
        print(f"\n  {board}:")
        print(f"    有效标的: {len(bdf)}")
        print(f"    合格率: {rate:.1f}% {verdict}")
        print(f"    平均策略收益: {avg_ret:+.1f}%")
        print(f"    平均股价涨幅: {avg_price:+.1f}%")
        
        board_summary.append({
            'board': board,
            'total': len(bdf),
            'passed': len(bp),
            'pass_rate': round(rate, 1),
            'avg_strategy_return': round(avg_ret, 1),
            'avg_price_change': round(avg_price, 1),
            'verdict': verdict,
        })
    
    # 最终判定
    print(f"\n{'='*60}")
    print(f"三、最终判定")
    print(f"{'='*60}")
    
    if len(valid) > 0:
        overall_rate = len(valid[valid['passed']]) / len(valid) * 100
        if overall_rate >= 60:
            print(f"\n  ★ 策略整体合格率 {overall_rate:.1f}% >= 60%")
            print(f"  ★ 结论: 当前参数体系有效，策略可继续优化细节")
            print(f"\n  建议下一步:")
            print(f"    1. 对不合格标的做case study，分析失败原因")
            print(f"    2. 检查是否有板块/行业维度的系统性偏差")
            print(f"    3. 在合格基础上进一步提升捕获率到70%+")
        else:
            print(f"\n  ★ 策略整体合格率 {overall_rate:.1f}% < 60%")
            print(f"  ★ 结论: 当前参数体系需要重大调整")
            
            # 分析哪个板块拖后腿
            for bs in board_summary:
                if bs['pass_rate'] < 60:
                    print(f"\n  → {bs['board']} 合格率仅 {bs['pass_rate']}%，是拖后腿的板块")
            
            print(f"\n  建议调整方向:")
            print(f"    1. 检查入场信号是否过于宽松（伪突破过多）")
            print(f"    2. 检查止损是否过于敏感（过早离场）")
            print(f"    3. 检查是否需要按行业/市值分层调参")
            print(f"    4. 考虑引入大盘环境过滤器")
    
    # 保存板块汇总
    if board_summary:
        pd.DataFrame(board_summary).to_csv(
            OUTPUT_DIR / 'board_summary.csv', index=False, encoding='utf-8-sig')
    
    # 生成TOP10和BOTTOM10
    if len(valid) > 0:
        print(f"\n{'='*60}")
        print(f"四、收益排行")
        print(f"{'='*60}")
        
        print(f"\n  TOP 10 最佳:")
        top10 = valid.nlargest(10, 'strategy_return_pct')
        for _, r in top10.iterrows():
            cr = f"{r['capture_ratio']:.0%}" if r['capture_ratio'] is not None and r['capture_ratio'] != float('inf') else r['scenario']
            print(f"    {r['ts_code']} {r['name']:6s} | 策略{r['strategy_return_pct']:+7.1f}% | 股价{r['price_change_pct']:+7.1f}% | 捕获{cr}")
        
        print(f"\n  BOTTOM 10 最差:")
        bot10 = valid.nsmallest(10, 'strategy_return_pct')
        for _, r in bot10.iterrows():
            cr = f"{r['capture_ratio']:.0%}" if r['capture_ratio'] is not None and r['capture_ratio'] != float('inf') else r['scenario']
            print(f"    {r['ts_code']} {r['name']:6s} | 策略{r['strategy_return_pct']:+7.1f}% | 股价{r['price_change_pct']:+7.1f}% | 捕获{cr}")
    
    print(f"\n{'#'*70}")
    print(f"# 报告生成完毕")
    print(f"# 详细数据: {OUTPUT_DIR}/all_boards_backtest_detail.csv")
    print(f"# 板块汇总: {OUTPUT_DIR}/board_summary.csv")
    print(f"{'#'*70}")
    
    return combined


# ============================================================
# 主入口
# ============================================================

def main():
    print(f"全板块批量回测")
    print(f"时间: {START_DATE} ~ {END_DATE}")
    print(f"目标: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print(f"每板块: {STOCKS_PER_BOARD} 只标的")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_boards = {}
    
    for board_type in ['gem', 'star', 'main']:
        try:
            rdf = run_board_backtest(board_type)
            all_boards[board_type] = rdf
        except Exception as e:
            print(f"\n[错误] {board_type} 板块回测失败: {e}")
            traceback.print_exc()
            all_boards[board_type] = pd.DataFrame()
    
    # 生成最终报告
    combined = generate_final_report(all_boards)
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return combined


if __name__ == '__main__':
    main()
