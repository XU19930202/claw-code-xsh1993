#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全板块批量回测脚本 - 最终适配版本
================
目标：策略收益 / 股价区间涨幅 >= 60% 即为合格
回测区间：2024-01-01 ~ 2025-12-31
板块：创业板(300/301) + 科创板(688) + 主板(600/000/001/002/003)

使用方法：
    python batch_backtest_all_boards_final.py

依赖：tushare, pandas, 我们的回测模块
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

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tushare as ts
import config

# ============================================================
# 配置区 - 按需修改
# ============================================================
TUSHARE_TOKEN = config.TUSHARE_TOKEN  # 从config文件读取
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
# 第二步：单股回测（适配我们的现有回测函数）
# ============================================================

def run_single_backtest(ts_code: str, stock_name: str, start_date: str, end_date: str) -> dict:
    """
    运行单只股票回测，返回标准化结果
    
    适配我们的backtest函数接口
    修复列名问题：需要匹配'收盘价(元)', '收盘价(前复权)(元)'等
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
        from breakout_strategy_v5_patched import backtest
        
        print(f"    获取 {ts_code} 行情数据...")
        
        # 1. 获取股票数据
        stock_df_raw = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                 fields='ts_code,trade_date,open,high,low,close,vol,amount,pct_chg')
        if stock_df_raw.empty:
            result['error_msg'] = f'未获取到 {ts_code} 的行情数据'
            return result
        
        # 获取复权因子
        adj_df = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        # 数据预处理
        stock_df_raw = stock_df_raw.sort_values('trade_date')
        
        # 合并复权因子
        if not adj_df.empty:
            adj_df = adj_df.sort_values('trade_date')
            stock_df = stock_df_raw.merge(adj_df[['trade_date', 'adj_factor']], on='trade_date', how='left')
            stock_df['adj_factor'] = stock_df['adj_factor'].ffill().bfill()
        else:
            stock_df = stock_df_raw.copy()
            stock_df['adj_factor'] = 1.0
        
        # 按backtest期望的格式准备数据
        # 需要以下列：'交易日期', '收盘价(元)', '收盘价(前复权)(元)', '开盘价(元)', '最高价(元)', '最低价(元)', '涨跌幅(%)', '成交量(万股)'
        
        # 计算前复权价格
        latest_adj = stock_df['adj_factor'].iloc[-1]
        stock_df['close_adj'] = stock_df['close'] * stock_df['adj_factor'] / latest_adj
        stock_df['open_adj'] = stock_df['open'] * stock_df['adj_factor'] / latest_adj
        stock_df['high_adj'] = stock_df['high'] * stock_df['adj_factor'] / latest_adj
        stock_df['low_adj'] = stock_df['low'] * stock_df['adj_factor'] / latest_adj
        
        # 成交量单位转换：手 -> 万股
        stock_df['vol_wan'] = stock_df['vol'] / 10000
        
        # 准备最终的DataFrame
        final_df = pd.DataFrame({
            '交易日期': pd.to_datetime(stock_df['trade_date'], format='%Y%m%d'),
            '收盘价(元)': stock_df['close'].astype(float),
            '收盘价(前复权)(元)': stock_df['close_adj'].astype(float),
            '开盘价(元)': stock_df['open'].astype(float),
            '最高价(元)': stock_df['high'].astype(float),
            '最低价(元)': stock_df['low'].astype(float),
            '涨跌幅(%)': stock_df['pct_chg'].astype(float),
            '成交量(万股)': stock_df['vol_wan'].astype(float)
        })
        
        # 获取上证指数数据
        index_df_raw = pro.index_daily(ts_code='000001.SH', start_date=start_date, end_date=end_date,
                                       fields='ts_code,trade_date,pct_chg')
        if not index_df_raw.empty:
            index_df = pd.DataFrame({
                '交易日期': pd.to_datetime(index_df_raw['trade_date'], format='%Y%m%d'),
                '涨跌幅(%)': index_df_raw['pct_chg'].astype(float)
            })
        else:
            index_df = None
        
        # 2. 提取纯代码数字部分
        code_only = ts_code.split('.')[0]
        
        # 3. 执行回测
        print(f"    执行回测...")
        trades = backtest(
            stock_df=final_df,
            code=code_only,
            index_df=index_df,
            verbose=False,  # 批量模式不打印详细日志
            stock_name=stock_name
        )
        
        # 4. 解析结果
        if not trades:
            result['status'] = 'no_signal'
            result['error_msg'] = '回测期间无交易信号'
            return result
        
        # 计算总收益和统计信息
        final_capital = INITIAL_CAPITAL
        all_returns = []
        
        for trade in trades:
            # 计算每笔交易的收益率
            trade_return_pct = trade.pnl
            all_returns.append(trade_return_pct)
            
            # 计算资金变化（简化处理）
            trade_profit = INITIAL_CAPITAL * (trade_return_pct / 100)
            final_capital += trade_profit
        
        # 计算总收益率
        total_return_pct = (final_capital / INITIAL_CAPITAL - 1) * 100
        
        # 计算胜率
        winning_trades = [r for r in all_returns if r > 0]
        win_rate = len(winning_trades) / len(all_returns) * 100 if all_returns else 0
        
        # 格式化交易记录
        formatted_trades = []
        for i, trade in enumerate(trades, 1):
            formatted_trades.append({
                '序号': i,
                '信号日期': str(trade.signal_date),
                '买入日期': str(trade.buy_date),
                '买入价': trade.buy_price,
                '卖出日期': str(trade.exit_date),
                '卖出价': trade.exit_price,
                '收益%': round(trade.pnl, 2),
                '持有天数': trade.days,
                '交易类型': trade.trade_type,
                '退出原因': getattr(trade, 'exit_reason', '未知'),
            })
        
        result['status'] = 'success'
        result['strategy_return_pct'] = round(total_return_pct, 2)
        result['trade_count'] = len(trades)
        result['win_rate'] = round(win_rate, 1)
        result['max_single_gain'] = max(all_returns) if all_returns else 0
        result['max_single_loss'] = min(all_returns) if all_returns else 0
        result['final_capital'] = round(final_capital, 2)
        result['trades'] = formatted_trades
        
        print(f"    回测完成: {result['strategy_return_pct']:+.1f}%, {len(trades)}笔交易")
        
    except ImportError as e:
        result['error_msg'] = f'导入错误: {e}'
        traceback.print_exc()
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
        
        print(f"\n  {board}: {len(bdf)}只有效标的")
        print(f"    合格: {len(bp)}只 ({rate:.1f}%)")
        print(f"    平均策略收益: {bdf['strategy_return_pct'].mean():+.1f}%")
        print(f"    平均股价涨幅: {bdf['price_change_pct'].mean():+.1f}%")
        
        board_summary.append({
            '板块': board,
            '标的数': len(bdf),
            '合格数': len(bp),
            '合格率': f'{rate:.1f}%',
            '平均策略收益': f'{bdf["strategy_return_pct"].mean():+.1f}%',
            '平均股价涨幅': f'{bdf["price_change_pct"].mean():+.1f}%',
        })
    
    # 保存板块汇总
    summary_df = pd.DataFrame(board_summary)
    summary_df.to_csv(OUTPUT_DIR / 'board_summary.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n{'='*60}")
    print(f"三、失败案例分析")
    print(f"{'='*60}")
    
    failed = valid[~valid['passed']]
    if len(failed) > 0:
        print(f"  未达标标的: {len(failed)} 只")
        
        # 按场景分组
        for scenario in ['上涨+盈利', '上涨+亏损', '下跌+亏损']:
            subset = failed[failed['scenario'] == scenario]
            if len(subset) > 0:
                print(f"    {scenario}: {len(subset)}只")
        
        # 保存失败案例
        failed.to_csv(OUTPUT_DIR / 'failed_cases_analysis.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n{'='*60}")
    print(f"四、后续步骤")
    print(f"{'='*60}")
    print("  1. 运行 generate_report.py 生成Excel报告")
    print("  2. 分析失败案例，针对性优化策略")
    print("  3. 根据板块差异调整参数")


def quick_test():
    """快速测试3只股票，确认适配正确"""
    print("快速适配测试:")
    print("=" * 60)
    
    test_stocks = [
        ('300502.SZ', '新易盛'),   # 创业板 - 已验证过
        ('688220.SZ', '翱捷科技'), # 科创板
        ('600519.SH', '贵州茅台'), # 主板
    ]
    
    for code, name in test_stocks:
        print(f"\n测试: {code} {name}")
        r = run_single_backtest(code, name, '20240101', '20241231')  # 缩短测试时间
        print(f"  状态: {r['status']}")
        print(f"  策略收益: {r['strategy_return_pct']:+.1f}%")
        print(f"  交易数: {r['trade_count']}")
        print(f"  胜率: {r['win_rate']:.1f}%")
        print(f"  错误: {r['error_msg'] or '无'}")
    
    print("\n" + "=" * 60)
    print("如果上面3只都显示 status=success 且收益数据合理，")
    print("就可以运行完整回测了。")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("全板块批量回测系统")
    print("目标: 验证策略有效性 (捕获率 >= 60%)")
    print(f"回测区间: {START_DATE} ~ {END_DATE}")
    print(f"初始资金: {INITIAL_CAPITAL:,}")
    print(f"合格阈值: 捕获率 >= {CAPTURE_THRESHOLD*100:.0f}%")
    print("="*70)
    
    # 询问是否快速测试
    choice = input("\n先运行快速测试 (3只股票)？(y/n): ").strip().lower()
    if choice == 'y':
        quick_test()
        choice2 = input("\n快速测试完成，是否继续运行完整回测？(y/n): ").strip().lower()
        if choice2 != 'y':
            print("已停止运行完整回测")
            return
    
    # 运行三个板块
    all_results = {}
    
    for board_type in ['gem', 'star', 'main']:
        try:
            result_df = run_board_backtest(board_type)
            all_results[board_type] = result_df
        except KeyboardInterrupt:
            print(f"\n用户中断 {board_type} 板块回测")
            break
        except Exception as e:
            print(f"\n{board_type} 板块回测出错: {e}")
            traceback.print_exc()
            continue
    
    # 生成最终报告
    generate_final_report(all_results)
    
    print(f"\n{'='*70}")
    print("批量回测完成!")
    print(f"结果保存在: {OUTPUT_DIR}")
    print(f"运行 generate_report.py 生成Excel报告")
    print("="*70)


if __name__ == '__main__':
    main()