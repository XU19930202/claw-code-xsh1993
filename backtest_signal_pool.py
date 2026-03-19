#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
突破信号池回测系统 v1.0
========================
回测区间: 2026-03-09 起，5个交易日
流程:
  1. 扫描3/9当天的MA20放量突破信号（信号池Day0）
  2. 对每个信号逐日运行决策树（Day1~Day5）
  3. 统计路径分布、买点触发率、盈亏情况
  4. 输出完整复盘报告

部署: 直接在火山引擎服务器运行
依赖: pip install tushare pandas
"""

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"  # ← 填入你的token

# 回测参数
SCAN_DATE = '20260309'           # 信号池建立日（Day0）
TRACK_DAYS = 5                   # 追踪交易日数
LOOKBACK_DAYS = 80               # 回看天数（计算均线用）

# 突破扫描参数
MA_PERIOD = 20
VOL_RATIO_MIN = 1.5              # 放量阈值：当日量/5日均量
PRICE_ABOVE_MA = True            # 收盘价须站上MA20

# 决策树参数
SHRINK_RATIO = 0.8               # 缩量阈值
DOJI_BODY_RATIO = 0.003          # 十字星实体比
SMALL_YANG_MAX_PCT = 2.0         # 小阳线涨幅上限%
MA20_TOLERANCE = 0.01            # MA20容差1%

# 评分参数（简化版7分制）
SCORE_CRITERIA = {
    'vol_strong': 2.0,           # 强放量(>2x)加分
    'above_ma': True,            # 站上MA20
    'above_ma60': True,          # 站上MA60
    'pct_positive': True,        # 当日上涨
    'pct_gt3': True,             # 涨幅>3%
}


# ============================================================
# 数据层
# ============================================================
class DataManager:
    def __init__(self, token):
        ts.set_token(token)
        self.pro = ts.pro_api()
        self._cache = {}

    def get_stock_list(self):
        """获取A股列表（排除ST、退市）"""
        df = self.pro.stock_basic(
            exchange='', list_status='L',
            fields='ts_code,symbol,name,market,list_date'
        )
        # 排除ST
        df = df[~df['name'].str.contains('ST|退')]
        # 排除次新股（上市不足120天）
        cutoff = (datetime.strptime(SCAN_DATE, '%Y%m%d') - timedelta(days=180)).strftime('%Y%m%d')
        df = df[df['list_date'] <= cutoff]
        return df

    def get_daily(self, ts_code, start_date, end_date):
        """获取日线数据（带缓存）"""
        cache_key = f"{ts_code}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,open,high,low,close,vol,amount,pct_chg'
            )
            if df is not None and not df.empty:
                df = df.sort_values('trade_date').reset_index(drop=True)
                self._cache[cache_key] = df
            return df
        except Exception as e:
            return None

    def get_moneyflow(self, ts_code, trade_date):
        """获取单日资金流向"""
        try:
            df = self.pro.moneyflow(
                ts_code=ts_code,
                trade_date=trade_date,
                fields='ts_code,trade_date,buy_elg_amount,sell_elg_amount,buy_lg_amount,sell_lg_amount'
            )
            if df is not None and not df.empty:
                row = df.iloc[0]
                net = ((row['buy_elg_amount'] - row['sell_elg_amount']) +
                       (row['buy_lg_amount'] - row['sell_lg_amount']))
                return net
            return None
        except:
            return None

    def get_trade_cal(self, start_date, end_date):
        """获取交易日历"""
        df = self.pro.trade_cal(
            exchange='SSE',
            start_date=start_date,
            end_date=end_date,
            fields='cal_date,is_open'
        )
        return df[df['is_open'] == 1]['cal_date'].tolist()


# ============================================================
# Step 1: 突破扫描器
# ============================================================
class BreakoutScanner:
    def __init__(self, dm):
        self.dm = dm

    def calc_indicators(self, df):
        """计算技术指标"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(MA_PERIOD).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        df['vol_ma5'] = df['vol'].rolling(5).mean()
        df['vol_ratio'] = df['vol'] / df['vol_ma5']
        return df

    def score_signal(self, row):
        """7分制评分"""
        score = 0
        # 1. 放量 (1-2分)
        if row['vol_ratio'] >= SCORE_CRITERIA['vol_strong']:
            score += 2  # 强放量
        elif row['vol_ratio'] >= VOL_RATIO_MIN:
            score += 1  # 普通放量
        # 2. 站上MA20 (1分)
        if row['close'] > row['ma20']:
            score += 1
        # 3. 站上MA60 (1分)
        if pd.notna(row.get('ma60')) and row['close'] > row['ma60']:
            score += 1
        # 4. 当日上涨 (1分)
        if row['pct_chg'] > 0:
            score += 1
        # 5. 涨幅>3% (1分)
        if row['pct_chg'] > 3:
            score += 1
        # 6. 收盘在当日上半区 (1分)
        if row['high'] > row['low']:
            pos = (row['close'] - row['low']) / (row['high'] - row['low'])
            if pos > 0.5:
                score += 1
        return min(score, 7)

    def scan(self, scan_date):
        """扫描指定日期的MA20放量突破"""
        print(f"\n{'='*60}")
        print(f"  Step 1: 扫描 {scan_date} 的MA20放量突破")
        print(f"{'='*60}")

        stocks = self.dm.get_stock_list()
        print(f"股票池: {len(stocks)}只")

        # 计算日期范围
        start_dt = datetime.strptime(scan_date, '%Y%m%d') - timedelta(days=LOOKBACK_DAYS * 2)
        start_str = start_dt.strftime('%Y%m%d')

        signals = []
        total = len(stocks)

        for i, (_, stock) in enumerate(stocks.iterrows()):
            if (i + 1) % 500 == 0:
                print(f"  扫描进度: {i+1}/{total}")
                time.sleep(0.5)  # API限流

            ts_code = stock['ts_code']
            name = stock['name']

            df = self.dm.get_daily(ts_code, start_str, scan_date)
            if df is None or len(df) < MA_PERIOD + 5:
                continue

            df = self.calc_indicators(df)

            # 取扫描日数据
            scan_row = df[df['trade_date'] == scan_date]
            if scan_row.empty:
                continue
            row = scan_row.iloc[0]

            # 取前一日数据
            scan_idx = scan_row.index[0]
            if scan_idx == 0:
                continue
            prev_row = df.loc[scan_idx - 1]

            # 突破条件
            if pd.isna(row['ma20']) or pd.isna(row['vol_ratio']):
                continue

            # 条件1: 今日收盘站上MA20
            if row['close'] <= row['ma20']:
                continue

            # 条件2: 昨日收盘在MA20下方或附近（突破而非已在上方运行）
            if prev_row['close'] > prev_row['ma20'] * 1.02:
                continue  # 昨天已经明显在MA20上方，不算新突破

            # 条件3: 放量
            if row['vol_ratio'] < VOL_RATIO_MIN:
                continue

            # 评分
            score = self.score_signal(row)

            signals.append({
                'ts_code': ts_code,
                'name': name,
                'scan_date': scan_date,
                'close': round(row['close'], 2),
                'pct_chg': round(row['pct_chg'], 2),
                'vol_ratio': round(row['vol_ratio'], 2),
                'ma20': round(row['ma20'], 2),
                'ma60': round(row['ma60'], 2) if pd.notna(row.get('ma60')) else None,
                'score': score,
            })

            time.sleep(0.05)  # API限流

        # 按评分排序
        signals.sort(key=lambda x: (-x['score'], -x['vol_ratio']))

        print(f"\n扫描完成! 放量突破信号: {len(signals)}只")
        print(f"  7分: {sum(1 for s in signals if s['score']==7)}只")
        print(f"  6分: {sum(1 for s in signals if s['score']==6)}只")
        print(f"  5分: {sum(1 for s in signals if s['score']==5)}只")
        print(f"  ≤4分: {sum(1 for s in signals if s['score']<=4)}只")

        return signals


# ============================================================
# Step 2: 决策树追踪器
# ============================================================
class DecisionTreeTracker:
    def __init__(self, dm):
        self.dm = dm

    def classify_day(self, row, ma20_val):
        """分类单日走势"""
        is_up = row['pct_chg'] >= 0
        vol_ratio = row['vol_ratio'] if 'vol_ratio' in row else 1.0
        is_vol_up = vol_ratio >= 1.2
        is_shrink = vol_ratio <= SHRINK_RATIO
        body_ratio = abs(row['close'] - row['open']) / row['close'] if row['close'] > 0 else 0
        is_doji = body_ratio < DOJI_BODY_RATIO
        above_ma20 = row['close'] >= ma20_val * (1 - MA20_TOLERANCE)

        if is_vol_up and not is_up:
            return 'vol_down', '放量下跌', above_ma20
        elif is_vol_up and is_up:
            return 'vol_up', '放量上涨', above_ma20
        elif is_up and is_doji:
            return 'shrink_doji', '缩量十字星', above_ma20
        elif is_up and not is_vol_up:
            if row['pct_chg'] <= SMALL_YANG_MAX_PCT:
                return 'shrink_small_yang', '缩量小阳', above_ma20
            else:
                return 'shrink_up', '缩量上涨', above_ma20
        elif not is_up and is_doji:
            return 'shrink_doji_down', '缩量十字星(阴)', above_ma20
        else:
            return 'shrink_down', '缩量下跌', above_ma20

    def track_signal(self, signal, trade_dates_after):
        """追踪单个信号"""
        ts_code = signal['ts_code']
        scan_date = signal['scan_date']

        # 获取追踪期数据
        start_dt = datetime.strptime(scan_date, '%Y%m%d') - timedelta(days=10)
        end_dt = datetime.strptime(trade_dates_after[-1], '%Y%m%d') + timedelta(days=5)
        df = self.dm.get_daily(ts_code, start_dt.strftime('%Y%m%d'), end_dt.strftime('%Y%m%d'))

        if df is None or df.empty:
            return {**signal, 'status': 'ERROR', 'msg': '数据获取失败', 'daily_log': []}

        # 计算指标
        df['ma20'] = df['close'].rolling(MA_PERIOD).mean()
        df['vol_ma5'] = df['vol'].rolling(5).mean()
        df['vol_ratio'] = df['vol'] / df['vol_ma5']

        # 逐日追踪
        result = {**signal, 'daily_log': [], 'status': 'TRACKING'}
        pullback_mode = False
        buy_signal_day = None
        buy_price = None

        for td in trade_dates_after:
            day_data = df[df['trade_date'] == td]
            if day_data.empty:
                continue

            row = day_data.iloc[0]
            ma20_val = row['ma20'] if pd.notna(row['ma20']) else signal['ma20']
            vol_ratio = row['vol_ratio'] if pd.notna(row['vol_ratio']) else 1.0

            day_type, day_desc, above_ma20 = self.classify_day(row, ma20_val)

            log = {
                'date': td,
                'close': round(row['close'], 2),
                'open': round(row['open'], 2),
                'pct_chg': round(row['pct_chg'], 2),
                'vol_ratio': round(vol_ratio, 2),
                'ma20': round(ma20_val, 2),
                'type': day_type,
                'desc': day_desc,
                'above_ma20': above_ma20,
            }

            # 路径C: 放量跌 → 放弃
            if day_type == 'vol_down':
                log['decision'] = '❌ 放量下跌，放弃'
                result['daily_log'].append(log)
                result['status'] = 'ABANDON'
                result['abandon_reason'] = '放量下跌'
                break

            # 连续跌破MA20 → 放弃
            if not above_ma20:
                prev_logs = result['daily_log']
                if prev_logs and not prev_logs[-1].get('above_ma20', True):
                    log['decision'] = '❌ 连续跌破MA20，放弃'
                    result['daily_log'].append(log)
                    result['status'] = 'ABANDON'
                    result['abandon_reason'] = '连续跌破MA20'
                    break
                else:
                    log['decision'] = '⚠️ 跌破MA20，观察'
                    result['daily_log'].append(log)
                    continue

            # 路径A: 放量涨或缩量涨 → 买入
            if day_type in ('vol_up', 'shrink_up') and above_ma20 and not pullback_mode:
                if day_type == 'shrink_up':
                    log['decision'] = '✅ 缩量上涨，可介入'
                    result['buy_quality'] = '优质(缩量涨)'
                else:
                    log['decision'] = '✅ 放量上涨，可介入'
                    result['buy_quality'] = '标准(放量涨)'
                result['daily_log'].append(log)
                result['status'] = 'BUY'
                buy_signal_day = td
                buy_price = row['close']
                result['buy_date'] = td
                result['buy_price'] = round(buy_price, 2)
                break

            # 路径B: 缩量回踩 → 等待企稳
            if day_type in ('shrink_down', 'shrink_doji', 'shrink_doji_down', 'shrink_small_yang') and above_ma20:
                pullback_mode = True
                # 检查企稳信号
                is_doji = abs(row['close'] - row['open']) / row['close'] < DOJI_BODY_RATIO
                is_small_yang = 0 < row['pct_chg'] <= SMALL_YANG_MAX_PCT
                is_shrink = vol_ratio <= SHRINK_RATIO

                if above_ma20 and (is_doji or is_small_yang) and is_shrink:
                    log['decision'] = '✅ 回踩企稳确认，最优买点！'
                    result['daily_log'].append(log)
                    result['status'] = 'BUY'
                    result['buy_quality'] = '最优(回踩确认)'
                    buy_signal_day = td
                    buy_price = row['close']
                    result['buy_date'] = td
                    result['buy_price'] = round(buy_price, 2)
                    break
                else:
                    log['decision'] = '⏳ 回踩中，等待企稳'
                    result['daily_log'].append(log)
                    continue

            # 其他
            log['decision'] = '⏳ 继续观察'
            result['daily_log'].append(log)

        # 追踪期满未触发
        if result['status'] == 'TRACKING':
            result['status'] = 'EXPIRED'

        # 计算买入后收益（如果触发了买入）
        if buy_signal_day and buy_price:
            # 计算买入后到追踪期末的收益
            remaining_dates = [d for d in trade_dates_after if d > buy_signal_day]
            if remaining_dates:
                last_date = remaining_dates[-1]
                last_data = df[df['trade_date'] == last_date]
                if not last_data.empty:
                    exit_price = last_data.iloc[0]['close']
                    result['exit_price'] = round(exit_price, 2)
                    result['exit_date'] = last_date
                    result['pnl_pct'] = round((exit_price - buy_price) / buy_price * 100, 2)
                else:
                    result['pnl_pct'] = 0.0
            else:
                result['pnl_pct'] = 0.0

            # 计算买入后最大回撤和最大盈利
            post_buy = df[df['trade_date'] > buy_signal_day]
            post_buy = post_buy[post_buy['trade_date'].isin(trade_dates_after)]
            if not post_buy.empty:
                result['max_gain'] = round((post_buy['high'].max() - buy_price) / buy_price * 100, 2)
                result['max_drawdown'] = round((post_buy['low'].min() - buy_price) / buy_price * 100, 2)

        return result


# ============================================================
# Step 3: 回测报告生成器
# ============================================================
class BacktestReporter:
    def __init__(self, signals, results, trade_dates):
        self.signals = signals
        self.results = results
        self.trade_dates = trade_dates

    def generate(self):
        """生成完整回测报告"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  突破信号池回测报告")
        lines.append(f"  信号日(Day0): {SCAN_DATE}")
        lines.append(f"  追踪期: {self.trade_dates[0]} ~ {self.trade_dates[-1]}")
        lines.append(f"  追踪天数: {len(self.trade_dates)}天")
        lines.append("=" * 70)

        # 1. 信号池概况
        lines.append(f"\n📊 信号池概况")
        lines.append(f"  扫描日期: {SCAN_DATE}")
        lines.append(f"  信号总数: {len(self.signals)}只")
        lines.append(f"  高分(≥6): {sum(1 for s in self.signals if s['score']>=6)}只")

        # 2. 路径分布
        status_counts = {}
        for r in self.results:
            s = r['status']
            status_counts[s] = status_counts.get(s, 0) + 1

        lines.append(f"\n📈 路径分布")
        emoji_map = {'BUY': '🟢', 'ABANDON': '🔴', 'EXPIRED': '⚪', 'TRACKING': '🔵', 'ERROR': '❗'}
        text_map = {'BUY': '买入触发', 'ABANDON': '信号失败', 'EXPIRED': '追踪期满', 'TRACKING': '追踪中', 'ERROR': '错误'}
        for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
            pct = c / len(self.results) * 100
            lines.append(f"  {emoji_map.get(s, '?')} {text_map.get(s, s)}: {c}只 ({pct:.1f}%)")

        # 3. 买入信号详情
        buy_results = [r for r in self.results if r['status'] == 'BUY']
        if buy_results:
            lines.append(f"\n🟢 买入信号详情 ({len(buy_results)}只)")
            lines.append("-" * 70)

            total_pnl = 0
            win_count = 0
            for r in buy_results:
                pnl = r.get('pnl_pct', 0)
                total_pnl += pnl
                if pnl > 0:
                    win_count += 1

                lines.append(f"  {r['name']}({r['ts_code']}) | "
                             f"信号日收盘:{r['close']} | "
                             f"评分:{r['score']}/7 | "
                             f"买点:{r.get('buy_quality', 'N/A')}")
                lines.append(f"    买入日:{r.get('buy_date', 'N/A')} | "
                             f"买入价:{r.get('buy_price', 'N/A')} | "
                             f"退出价:{r.get('exit_price', 'N/A')} | "
                             f"收益:{pnl:+.2f}%")
                if 'max_gain' in r:
                    lines.append(f"    最大盈利:{r['max_gain']:+.2f}% | "
                                 f"最大回撤:{r['max_drawdown']:+.2f}%")

                # 逐日记录
                for d in r['daily_log']:
                    lines.append(f"    {d['date']} | 收:{d['close']} | "
                                 f"{d['pct_chg']:+.2f}% | "
                                 f"量比:{d['vol_ratio']:.1f}x | "
                                 f"{'✓MA20' if d['above_ma20'] else '✗MA20'}")
                    lines.append(f"      → {d['decision']}")
                lines.append("")

            # 汇总统计
            lines.append(f"  --- 买入信号汇总 ---")
            lines.append(f"  触发数: {len(buy_results)}只")
            lines.append(f"  胜率: {win_count}/{len(buy_results)} = {win_count/len(buy_results)*100:.1f}%")
            lines.append(f"  平均收益: {total_pnl/len(buy_results):+.2f}%")
            if win_count > 0:
                avg_win = np.mean([r.get('pnl_pct', 0) for r in buy_results if r.get('pnl_pct', 0) > 0])
                lines.append(f"  平均盈利: {avg_win:+.2f}%")
            lose_count = len(buy_results) - win_count
            if lose_count > 0:
                avg_loss = np.mean([r.get('pnl_pct', 0) for r in buy_results if r.get('pnl_pct', 0) <= 0])
                lines.append(f"  平均亏损: {avg_loss:+.2f}%")
                if avg_loss != 0:
                    lines.append(f"  盈亏比: {abs(avg_win/avg_loss) if win_count > 0 else 0:.2f}")

        # 4. 放弃信号详情
        abandon_results = [r for r in self.results if r['status'] == 'ABANDON']
        if abandon_results:
            lines.append(f"\n🔴 信号失败详情 ({len(abandon_results)}只)")
            lines.append("-" * 70)
            for r in abandon_results:
                lines.append(f"  {r['name']}({r['ts_code']}) | "
                             f"评分:{r['score']}/7 | "
                             f"放弃原因:{r.get('abandon_reason', 'N/A')}")
                for d in r['daily_log']:
                    lines.append(f"    {d['date']} | 收:{d['close']} | "
                                 f"{d['pct_chg']:+.2f}% | → {d['decision']}")
                lines.append("")

        # 5. 按评分分层统计
        lines.append(f"\n📊 分层统计（按信号日评分）")
        lines.append("-" * 70)
        for min_score in [7, 6, 5]:
            subset = [r for r in self.results if r['score'] >= min_score]
            if not subset:
                continue
            buy_sub = [r for r in subset if r['status'] == 'BUY']
            abandon_sub = [r for r in subset if r['status'] == 'ABANDON']
            lines.append(f"  评分≥{min_score}: {len(subset)}只 | "
                         f"买入:{len(buy_sub)} | 放弃:{len(abandon_sub)} | "
                         f"买入率:{len(buy_sub)/len(subset)*100:.1f}%")
            if buy_sub:
                avg_pnl = np.mean([r.get('pnl_pct', 0) for r in buy_sub])
                wr = sum(1 for r in buy_sub if r.get('pnl_pct', 0) > 0) / len(buy_sub) * 100
                lines.append(f"    → 平均收益:{avg_pnl:+.2f}% | 胜率:{wr:.1f}%")

        # 6. 关键发现
        lines.append(f"\n💡 关键发现")
        lines.append("-" * 70)
        total = len(self.results)
        buy_rate = len(buy_results) / total * 100 if total > 0 else 0
        abandon_rate = len(abandon_results) / total * 100 if total > 0 else 0
        lines.append(f"  信号→买入转化率: {buy_rate:.1f}%")
        lines.append(f"  信号→放弃率: {abandon_rate:.1f}%")

        if buy_results:
            # 最优买点类型
            quality_counts = {}
            for r in buy_results:
                q = r.get('buy_quality', 'N/A')
                quality_counts[q] = quality_counts.get(q, 0) + 1
            lines.append(f"  买点类型分布:")
            for q, c in quality_counts.items():
                lines.append(f"    {q}: {c}只")

            # 买入日距离信号日的天数分布
            day_gaps = []
            for r in buy_results:
                if r.get('buy_date'):
                    gap = self.trade_dates.index(r['buy_date']) + 1 if r['buy_date'] in self.trade_dates else 0
                    day_gaps.append(gap)
            if day_gaps:
                lines.append(f"  买入日距信号日: 平均{np.mean(day_gaps):.1f}天 | "
                             f"最快Day{min(day_gaps)} | 最慢Day{max(day_gaps)}")

        report = '\n'.join(lines)
        return report


# ============================================================
# 主程序
# ============================================================
def run_backtest():
    print("=" * 60)
    print("  突破信号池回测系统 v1.0")
    print(f"  信号日: {SCAN_DATE}")
    print(f"  追踪天数: {TRACK_DAYS}")
    print("=" * 60)

    # 初始化
    dm = DataManager(TUSHARE_TOKEN)

    # 获取交易日历
    end_dt = datetime.strptime(SCAN_DATE, '%Y%m%d') + timedelta(days=TRACK_DAYS * 3)
    trade_dates = dm.get_trade_cal(SCAN_DATE, end_dt.strftime('%Y%m%d'))
    trade_dates.sort()

    # 信号日之后的交易日
    trade_dates_after = [d for d in trade_dates if d > SCAN_DATE][:TRACK_DAYS]
    print(f"\n交易日历:")
    print(f"  信号日(Day0): {SCAN_DATE}")
    for i, td in enumerate(trade_dates_after):
        print(f"  Day{i+1}: {td}")

    # Step 1: 扫描突破信号
    scanner = BreakoutScanner(dm)
    signals = scanner.scan(SCAN_DATE)

    if not signals:
        print("[WARNING] No breakout signals found, backtest ended")
        return

    # 显示信号池
    print(f"\n[Signal Pool] (Top 20):")
    for i, s in enumerate(signals[:20], 1):
        print(f"  #{i:2d} {s['name']:8s}({s['ts_code']:12s}) "
              f"Close:{s['close']:7.2f} {s['pct_chg']:+5.1f}% "
              f"VolRatio:{s['vol_ratio']:4.1f}x Score:{s['score']}/7")

    # Step 2: 决策树追踪
    print(f"\n{'='*60}")
    print(f"  Step 2: Decision Tree Tracking ({len(signals)} stocks)")
    print(f"{'='*60}")

    tracker = DecisionTreeTracker(dm)
    results = []

    for i, signal in enumerate(signals):
        if (i + 1) % 10 == 0:
            print(f"  Tracking progress: {i+1}/{len(signals)}")
        r = tracker.track_signal(signal, trade_dates_after)
        results.append(r)
        time.sleep(0.1)

    # Step 3: 生成报告
    reporter = BacktestReporter(signals, results, trade_dates_after)
    report = reporter.generate()

    print("\n" + report)

    # 保存报告
    report_file = f"backtest_report_{SCAN_DATE}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[REPORT SAVED] {report_file}")

    # 保存详细数据
    results_df = pd.DataFrame(results)
    csv_file = f"backtest_data_{SCAN_DATE}.csv"
    results_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"[DATA SAVED] {csv_file}")

    return results


if __name__ == '__main__':
    if not TUSHARE_TOKEN:
        print("[WARNING] Please enter TUSHARE_TOKEN at the top of the script first")
        print("   Then run: python backtest_signal_pool.py")
    else:
        results = run_backtest()
