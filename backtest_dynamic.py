#!/usr/bin/env python3
"""
动态参数回测 - 根据股票名称变化自动切换策略参数
用法: python backtest_dynamic.py <股票代码> [起始日期]
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tushare as ts
import config
from params import get_board_type, get_params
from breakout_strategy_v5_patched import (
    StrategyConfig, prepare_data, scan_signals, run_entry,
    ExitResult, BoardConfig
)


@dataclass
class Board:
    """简化的板块配置"""
    name: str
    limit_up: float
    limit_down: float
    limit_pct: float = 10.0  # 涨跌停幅度百分比


def get_stock_name_on_date(ts_code: str, date: str) -> str:
    """获取指定日期的股票名称"""
    pro = ts.pro_api()
    
    try:
        df = pro.namechange(ts_code=ts_code)
        df['start_date'] = pd.to_datetime(df['start_date'], format='%Y%m%d')
        df['end_date'] = pd.to_datetime(df['end_date'].fillna('20991231'), format='%Y%m%d')
        query_date = pd.to_datetime(date)
        
        for _, row in df.iterrows():
            if row['start_date'] <= query_date <= row['end_date']:
                return row['name']
    except Exception as e:
        print(f"  警告: 查询历史名称失败: {e}")
    
    # 默认返回当前名称
    try:
        df = pro.stock_basic(ts_code=ts_code, fields='name')
        return df.iloc[0]['name'] if not df.empty else ''
    except:
        return ''


def get_board_for_date(ts_code: str, date: str) -> Board:
    """根据日期获取对应的板块配置"""
    name = get_stock_name_on_date(ts_code, date)
    code = ts_code.split('.')[0]
    
    is_st = 'ST' in name.upper()
    
    if code.startswith('688'):
        if is_st:
            return Board(name="科创板ST (±20%)", limit_up=19.5, limit_down=-19.5, limit_pct=20.0)
        else:
            return Board(name="科创板 (±20%)", limit_up=19.5, limit_down=-19.5, limit_pct=20.0)
    elif code.startswith('300') or code.startswith('301'):
        if is_st:
            return Board(name="创业板ST (±20%)", limit_up=19.5, limit_down=-19.5, limit_pct=20.0)
        else:
            return Board(name="创业板 (±20%)", limit_up=19.5, limit_down=-19.5, limit_pct=20.0)
    elif code.startswith('8') or code.startswith('4'):
        return Board(name="北交所 (±30%)", limit_up=29.5, limit_down=-29.5, limit_pct=30.0)
    else:
        if is_st:
            return Board(name="ST主板 (±5%)", limit_up=4.5, limit_down=-4.5, limit_pct=5.0)
        else:
            return Board(name="主板 (±10%)", limit_up=9.5, limit_down=-9.5, limit_pct=10.0)


def get_params_for_date(ts_code: str, date: str, liquidity: float = 3.0):
    """根据日期获取对应的策略参数"""
    name = get_stock_name_on_date(ts_code, date)
    board_type = get_board_type(ts_code.split('.')[0], name)
    return get_params(board_type, liquidity)


def fetch_stock_data(ts_code: str, start_date: datetime = None) -> pd.DataFrame:
    """获取股票历史行情数据"""
    ts.set_token(config.TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=180)
    
    end_str = end_date.strftime('%Y%m%d')
    start_str = start_date.strftime('%Y%m%d')
    
    print(f"正在获取 {ts_code} 的行情数据...")
    
    df = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
    
    if df.empty:
        raise ValueError(f"未获取到 {ts_code} 的数据")
    
    df = df.sort_values('trade_date')
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    
    # 重命名列以匹配策略期望的格式
    df = df.rename(columns={
        'trade_date': '交易日期',
        'open': '开盘价(元)',
        'high': '最高价(元)',
        'low': '最低价(元)',
        'close': '收盘价(元)',
        'vol': '成交量(股)',
        'amount': '成交额(千元)',
        'pct_chg': '涨跌幅(%)'
    })
    
    # 添加前复权价格（这里假设已经是前复权）
    df['收盘价(前复权)(元)'] = df['收盘价(元)']
    
    # 计算技术指标
    df['MA5'] = df['收盘价(元)'].rolling(window=5).mean()
    df['MA20'] = df['收盘价(元)'].rolling(window=20).mean()
    df['MA60'] = df['收盘价(元)'].rolling(window=60).mean()
    df['prev_close'] = df['收盘价(元)'].shift(1)
    
    # 将成交量(股)转换为万股
    df['成交量(万股)'] = df['成交量(股)'] / 10000
    df['vol_ma5'] = df['成交量(万股)'].rolling(window=5).mean()
    df['vol_ratio'] = df['成交量(万股)'] / df['vol_ma5']
    
    return df


def fetch_index_data(start_date: datetime = None) -> pd.DataFrame:
    """获取上证指数数据"""
    ts.set_token(config.TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=180)
    
    df = pro.index_daily(ts_code='000001.SH', 
                         start_date=start_date.strftime('%Y%m%d'),
                         end_date=end_date.strftime('%Y%m%d'))
    
    if df.empty:
        return None
    
    df = df.sort_values('trade_date')
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['MA20'] = df['close'].rolling(window=20).mean()
    
    # 重命名列以匹配策略期望的格式
    df = df.rename(columns={
        'trade_date': '交易日期',
        'close': 'close',
        'pct_chg': '涨跌幅(%)'
    })
    
    return df


def run_exit_dynamic(stock, entry_idx, entry_price, cfg, ts_code, verbose=True):
    """动态出场判断"""
    result = ExitResult()
    result.entry_idx = entry_idx
    result.entry_price = entry_price
    
    below_ma5_count = 0
    below_ma20_count = 0
    gap_streak = 0
    had_limit_up = False
    peak_pnl = 0
    
    for k in range(entry_idx + 1, len(stock)):
        r = stock.iloc[k]
        prev = stock.iloc[k-1]
        d = str(r['交易日期'])[:10]
        
        # 每天获取当前参数
        board = get_board_for_date(ts_code, d)
        p = get_params_for_date(ts_code, d)
        
        close = r['收盘价(元)']
        opn = r['开盘价(元)']
        pct = r['涨跌幅(%)']
        m5 = r['MA5']
        m20 = r['MA20']
        
        pnl = (close - entry_price) / entry_price * 100
        peak_pnl = max(peak_pnl, pnl)
        
        above_ma5 = close >= m5
        above_ma20 = close >= m20
        below_ma5_close = close < m5
        is_up_day = pct > 0
        high_open_low_close = (opn > prev['收盘价(元)'] * 1.01) and (close < opn * 0.99)
        
        # 浮盈回撤止盈
        if p.max_drawdown_from_peak > 0 and peak_pnl > p.max_drawdown_from_peak:
            drawdown = peak_pnl - pnl
            if drawdown >= p.max_drawdown_from_peak:
                result.exit_idx = k
                result.exit_price = close
                result.exit_date = d
                result.exit_reason = '浮盈回撤止盈'
                result.exit_type = 'drawdown'
                result.max_pnl = peak_pnl
                result.log.append(f"  {d} | {close:.2f} {pnl:+.2f}% | 最高+{peak_pnl:.1f}%回落到{drawdown:.1f}% | [EXIT] 浮盈回撤止盈")
                return result
        
        # 跌停熔断（带浮盈保护）
        if pct >= board.limit_up:
            had_limit_up = True
        if had_limit_up and pct <= board.limit_down and pnl < p.profit_tier_2:
            result.exit_idx = k
            result.exit_price = close
            result.exit_date = d
            result.exit_reason = '跌停熔断'
            result.exit_type = 'limit_down'
            result.max_pnl = peak_pnl
            result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [STOP] 跌停熔断")
            return result
        elif had_limit_up and pct <= board.limit_down and pnl >= p.profit_tier_2:
            result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [PROFIT] 跌停但浮盈>{p.profit_tier_2:.0f}%，继续持有")
        
        # MA5/MA20阶段判断
        trend_gap = 1.03  # cfg.trend_gap
        trend_days = 3    # cfg.trend_days
        
        if m5 > m20 * trend_gap:
            gap_streak += 1
        else:
            gap_streak = 0
        
        if gap_streak >= trend_days and above_ma5:
            phase = 'MA5'
        else:
            phase = 'MA20'
        
        # MA5阶段出场
        if phase == 'MA5':
            ma5_stop_days = 2
            
            if pnl >= p.profit_tier_2:
                phase = 'MA20'
                below_ma5_count = 0
                result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [PROFIT] 浮盈>{p.profit_tier_2:.0f}%，回退MA20阶段")
                continue
            elif pnl >= p.profit_tier_1:
                ma5_stop_days = 4
            
            if below_ma5_close and high_open_low_close:
                result.exit_idx = k
                result.exit_price = close
                result.exit_date = d
                result.exit_reason = '高开低走且破MA5'
                result.exit_type = 'ma5'
                result.max_pnl = peak_pnl
                result.log.append(f"  {d} | {close:.2f} 开{opn:.2f} X_MA5({m5:.2f}) | +{pnl:.1f}% | [EXIT] 高开低走且破MA5")
                return result
            
            if not above_ma5:
                if is_up_day:
                    result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) | +{pnl:.1f}% | [OK] 破MA5但收阳")
                    below_ma5_count = 0
                else:
                    below_ma5_count += 1
                    if below_ma5_count >= ma5_stop_days:
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = f'连续{ma5_stop_days}天破MA5且收阴'
                        result.exit_type = 'ma5'
                        result.max_pnl = peak_pnl
                        result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) | +{pnl:.1f}% | [EXIT] 连续{ma5_stop_days}天破MA5且收阴")
                        return result
                    else:
                        tier_info = f"(放宽{ma5_stop_days}天)" if ma5_stop_days > 2 else ""
                        result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) | +{pnl:.1f}% | [!] 破MA5+收阴 第{below_ma5_count}天{tier_info}")
            else:
                below_ma5_count = 0
        
        # MA20阶段出场
        if phase == 'MA20':
            if not above_ma20:
                below_ma20_count += 1
                if below_ma20_count >= 3:
                    result.exit_idx = k
                    result.exit_price = close
                    result.exit_date = d
                    result.exit_reason = '连续3天破MA20止损'
                    result.exit_type = 'ma20'
                    result.max_pnl = peak_pnl
                    result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% X_MA20(连续3天) | +{pnl:.1f}% | [EXIT] 趋势回踩:连续3天破MA20止损")
                    return result
                else:
                    result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% X_MA20(第{below_ma20_count}天) | +{pnl:.1f}% | [!] 趋势回踩:破MA20第{below_ma20_count}天，观察")
            else:
                below_ma20_count = 0
    
    result.max_pnl = peak_pnl
    return result


def backtest_dynamic(stock_df: pd.DataFrame, code: str, ts_code: str, 
                     index_df: pd.DataFrame = None, verbose: bool = True) -> list:
    """动态参数回测主函数"""
    
    cfg = StrategyConfig()
    
    # 准备数据 - 使用原版的prepare_data函数
    stock, idx_map = prepare_data(stock_df, index_df)
    
    start_date = str(stock.iloc[0]['交易日期'])[:10]
    initial_name = get_stock_name_on_date(ts_code, start_date)
    initial_board = get_board_for_date(ts_code, start_date)
    
    if verbose:
        print(f"{'=' * 85}")
        print(f"  {code} 回测 | 动态参数模式")
        print(f"  初始名称: {initial_name} | 板块: {initial_board.name}")
        print(f"  股价: {stock['收盘价(元)'].iloc[0]:.2f} → {stock['收盘价(元)'].iloc[-1]:.2f} "
              f"({(stock['收盘价(元)'].iloc[-1] / stock['收盘价(元)'].iloc[0] - 1) * 100:+.0f}%)")
        print(f"{'=' * 85}")
    
    # 使用初始参数扫描信号
    initial_p = get_params_for_date(ts_code, start_date)
    
    all_signals = scan_signals(stock, cfg, initial_board, initial_p)
    
    if verbose:
        print(f"\n信号池: {len(all_signals)}个")
        for si, stype in all_signals:
            r = stock.iloc[si]
            type_str = "突破" if stype == 'breakout' else "回踩"
            signal_date = str(r['交易日期'])[:10]
            signal_name = get_stock_name_on_date(ts_code, signal_date)
            print(f"  {signal_date} | {r['收盘价(元)']:.2f} "
                  f"涨{r['涨跌幅(%)']:.1f}% 量比{r['vol_ratio']:.2f}x | [{type_str}] | {signal_name}")
    
    trades = []
    last_exit_idx = -1
    
    for si, stype in all_signals:
        if si <= last_exit_idx:
            continue
        
        signal_date = str(stock.iloc[si]['交易日期'])[:10]
        signal_name = get_stock_name_on_date(ts_code, signal_date)
        
        if verbose:
            print(f"\n[+] {'突破信号' if stype == 'breakout' else '趋势回踩信号'} {signal_date} | {stock.iloc[si]['收盘价(元)']:.2f}")
            print(f"  当前名称: {signal_name}")
        
        # 使用信号日的参数进行入场判断
        signal_board = get_board_for_date(ts_code, signal_date)
        signal_p = get_params_for_date(ts_code, signal_date)
        
        entry_result = run_entry(stock, si, idx_map, cfg, signal_board, -1, False, signal_p)
        
        if entry_result.buy_idx is None:
            if verbose:
                print(f"  [-] 未触发入场")
            continue
        
        entry_date = str(stock.iloc[entry_result.buy_idx]['交易日期'])[:10]
        entry_name = get_stock_name_on_date(ts_code, entry_date)
        
        if verbose:
            print(f"\n[-] 第{len(trades)+1}笔 信号:{signal_date} | {'突破买入' if stype == 'breakout' else '趋势回踩'}")
            print(f"  买入: {entry_date} @ {entry_result.buy_price:.2f} ({entry_result.buy_type})")
            if entry_name != signal_name:
                print(f"  注意: 买入时名称已变为 {entry_name}")
        
        # 出场判断 - 使用动态参数
        exit_result = run_exit_dynamic(stock, entry_result.buy_idx, entry_result.buy_price, 
                                       cfg, ts_code, verbose)
        
        if exit_result.exit_idx is not None:
            last_exit_idx = exit_result.exit_idx
            exit_date = str(stock.iloc[exit_result.exit_idx]['交易日期'])[:10]
            exit_name = get_stock_name_on_date(ts_code, exit_date)
            
            trade = {
                'signal_date': signal_date,
                'signal_type': stype,
                'entry_date': entry_date,
                'entry_price': entry_result.buy_price,
                'entry_type': entry_result.buy_type,
                'exit_date': exit_date,
                'exit_price': exit_result.exit_price,
                'exit_reason': exit_result.exit_reason,
                'return': (exit_result.exit_price - entry_result.buy_price) / entry_result.buy_price * 100,
                'hold_days': exit_result.exit_idx - entry_result.buy_idx,
                'max_pnl': exit_result.max_pnl,
                'log': '\n'.join(exit_result.log)
            }
            trades.append(trade)
            
            if verbose:
                print(f"  退出: {exit_date} @ {exit_result.exit_price:.2f} | {exit_result.exit_reason}")
                if exit_name != entry_name:
                    print(f"  注意: 卖出时名称已变为 {exit_name}")
                print(f"  收益: {trade['return']:+.2f}% | 最高浮盈: {exit_result.max_pnl:+.2f}% | 持有{trade['hold_days']}天")
    
    return trades


def print_summary(trades, initial_capital=200000):
    """打印交易汇总"""
    if not trades:
        print("\n没有完成任何交易")
        return
    
    print(f"\n{'=' * 85}")
    print(f"  回测结果汇总")
    print(f"{'=' * 85}")
    
    wins = [t for t in trades if t['return'] > 0]
    losses = [t for t in trades if t['return'] <= 0]
    
    avg_win = sum(t['return'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['return'] for t in losses) / len(losses) if losses else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    print(f"\n  交易: {len(trades)}笔 | 胜率: {len(wins)}/{len(trades)} = {len(wins)/len(trades)*100:.0f}%")
    print(f"  均盈: {avg_win:+.2f}%")
    print(f"  均亏: {avg_loss:+.2f}%")
    print(f"  盈亏比: {profit_factor:.2f}")
    
    capital = initial_capital
    print(f"\n  复利计算({initial_capital/10000:.0f}万本金):")
    print(f"    笔 |       类型 |          买入日 |      买价 |          卖出日 |      卖价 |       收益 |         资金")
    print(f"  {'-' * 85}")
    
    for i, t in enumerate(trades, 1):
        capital *= (1 + t['return'] / 100)
        type_str = t.get('entry_type', 'unknown')[:8]
        symbol = '[+]' if t['return'] > 0 else '[-]'
        print(f"  {symbol} {i:2} | {type_str:>10} |   {t['entry_date']} |    {t['entry_price']:.2f} |   {t['exit_date']} |    {t['exit_price']:.2f} |   {t['return']:+.2f}% |    {capital/10000:.2f}万")
    
    total_return = (capital - initial_capital) / initial_capital * 100
    print(f"  {'-' * 85}")
    print(f"  最终: {capital/10000:.2f}万 | 总收益: {total_return:+.2f}% | 净赚: {(capital-initial_capital)/10000:.2f}万")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python backtest_dynamic.py <股票代码> [起始日期]")
        print("示例: python backtest_dynamic.py 000506 2024-01-01")
        sys.exit(1)
    
    code = sys.argv[1]
    start_date = None
    if len(sys.argv) >= 3:
        try:
            start_date = datetime.strptime(sys.argv[2], '%Y-%m-%d')
            print(f"自定义起始日期: {sys.argv[2]}")
        except ValueError:
            print(f"警告: 日期格式错误 '{sys.argv[2]}'，使用默认180天")
    
    print("=" * 85)
    print(f"  MA20突破回踩策略 v5 - 动态参数回测")
    print("=" * 85)
    
    ts_code = f"{code}.SZ" if code.startswith('0') or code.startswith('3') else f"{code}.SH"
    print(f"\n股票代码: {ts_code}")
    
    try:
        stock_df = fetch_stock_data(ts_code, start_date=start_date)
        index_df = fetch_index_data(start_date=start_date)
        
        print(f"数据范围: {stock_df['交易日期'].min().strftime('%Y-%m-%d')} ~ {stock_df['交易日期'].max().strftime('%Y-%m-%d')}")
        print(f"共 {len(stock_df)} 个交易日")
        
        trades = backtest_dynamic(stock_df, code, ts_code, index_df, verbose=True)
        print_summary(trades)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
