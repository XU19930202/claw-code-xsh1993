#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
突破后买点决策树 - Breakout Follow-through Decision Tree
=========================================================
功能：对已筛选出的MA20放量突破信号，自动追踪后续走势，
      分类标注当前所处阶段，输出可操作的买入/观察/放弃建议。

决策树逻辑：
  突破日：放量突破MA20（已由前序脚本筛出）
  ↓
  次日起观察（最多追踪N个交易日）：
  ├─ 路径A：放量涨 或 缩量涨 → ✅ 可介入（缩量涨更优）
  ├─ 路径B：缩量跌但未破MA20 → ⏳ 等待回踩确认
  │   └─ 回踩企稳信号：缩量十字星/小阳线 + 收盘站上MA20 → ✅ 回踩买点
  └─ 路径C：放量跌 或 跌破MA20 → ❌ 放弃

交叉验证（可选）：
  - 主力资金净流入（moneyflow大单+超大单）
  - 个股vs板块相对强度

作者：基于用户交易框架定制
"""

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
import requests
warnings.filterwarnings('ignore')


# ============================================================
# 配置区
# ============================================================
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"

# 决策树参数
VOLUME_RATIO_THRESHOLD = 1.2    # 放量判定：当日成交量 / 5日均量
SHRINK_RATIO_THRESHOLD = 0.8    # 缩量判定：当日成交量 / 5日均量
DOJI_BODY_RATIO = 0.003         # 十字星判定：|开-收|/收 < 0.3%
SMALL_YANG_MAX = 0.02           # 小阳线判定：涨幅 < 2%
TRACK_DAYS = 5                  # 突破后最多追踪交易日数
MA_PERIOD = 20                  # 均线周期

# 资金流验证
ENABLE_MONEYFLOW = True         # 是否启用资金流交叉验证


# ============================================================
# 数据获取
# ============================================================
class DataFetcher:
    def __init__(self, token):
        ts.set_token(token)
        self.pro = ts.pro_api()

    def get_daily_data(self, ts_code, start_date, end_date):
        """获取日线数据"""
        df = self.pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,trade_date,open,high,low,close,vol,amount,pct_chg'
        )
        if df is not None and not df.empty:
            df = df.sort_values('trade_date').reset_index(drop=True)
        return df

    def get_moneyflow(self, ts_code, start_date, end_date):
        """获取资金流向数据"""
        try:
            df = self.pro.moneyflow(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,buy_elg_amount,sell_elg_amount,buy_lg_amount,sell_lg_amount'
            )
            if df is not None and not df.empty:
                df = df.sort_values('trade_date').reset_index(drop=True)
                # 主力净流入 = (超大单买-超大单卖) + (大单买-大单卖)
                df['main_net_inflow'] = (
                    (df['buy_elg_amount'] - df['sell_elg_amount']) +
                    (df['buy_lg_amount'] - df['sell_lg_amount'])
                )
            return df
        except Exception as e:
            print(f"  ⚠️ 资金流数据获取失败: {e}")
            return None

    def get_index_daily(self, index_code, start_date, end_date):
        """获取指数日线，用于计算相对强度"""
        df = self.pro.index_daily(
            ts_code=index_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,trade_date,close,pct_chg'
        )
        if df is not None and not df.empty:
            df = df.sort_values('trade_date').reset_index(drop=True)
        return df


# ============================================================
# 决策树核心引擎
# ============================================================
class BreakoutDecisionTree:
    """突破后买点决策树"""

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def _calc_indicators(self, df):
        """计算技术指标"""
        df = df.copy()
        # MA20
        df['ma20'] = df['close'].rolling(MA_PERIOD).mean()
        # 5日均量
        df['vol_ma5'] = df['vol'].rolling(5).mean()
        # 量比（相对5日均量）
        df['vol_ratio'] = df['vol'] / df['vol_ma5']
        # 实体比例（判断十字星）
        df['body_ratio'] = abs(df['close'] - df['open']) / df['close']
        return df

    def _classify_day(self, row, prev_row):
        """
        分类单日走势
        返回: (类型, 描述)
        类型: 'vol_up', 'vol_down', 'shrink_up', 'shrink_down',
              'doji_stable', 'small_yang_stable'
        """
        is_up = row['pct_chg'] >= 0
        is_volume_up = row['vol_ratio'] >= VOLUME_RATIO_THRESHOLD
        is_shrink = row['vol_ratio'] <= SHRINK_RATIO_THRESHOLD
        is_doji = row['body_ratio'] < DOJI_BODY_RATIO
        is_small_yang = (0 < row['pct_chg'] <= SMALL_YANG_MAX * 100) and not is_doji
        above_ma20 = row['close'] >= row['ma20'] * 0.99  # 允许1%容差

        if is_volume_up and is_up:
            return 'vol_up', '放量上涨'
        elif is_volume_up and not is_up:
            return 'vol_down', '放量下跌'
        elif is_up and not is_volume_up:
            if is_doji:
                return 'shrink_doji_up', '缩量十字星(偏阳)'
            else:
                return 'shrink_up', '缩量上涨'
        else:  # 下跌且非放量
            if is_doji:
                return 'shrink_doji_down', '缩量十字星(偏阴)'
            else:
                return 'shrink_down', '缩量下跌'

    def _check_pullback_confirm(self, row):
        """检查是否出现回踩企稳信号"""
        above_ma20 = row['close'] >= row['ma20'] * 0.99
        is_doji = row['body_ratio'] < DOJI_BODY_RATIO
        is_small_yang = (0 < row['pct_chg'] <= SMALL_YANG_MAX * 100)
        is_shrink = row['vol_ratio'] <= SHRINK_RATIO_THRESHOLD

        if above_ma20 and is_shrink and (is_doji or is_small_yang):
            return True
        return False

    def analyze_stock(self, ts_code, breakout_date, stock_name=""):
        """
        分析单只股票的突破后走势

        参数:
            ts_code: 股票代码 (如 '300246.SZ')
            breakout_date: 突破日期 (如 '20260315')
            stock_name: 股票名称（可选，用于显示）

        返回:
            dict: 分析结果
        """
        display_name = f"{stock_name}({ts_code})" if stock_name else ts_code

        # 获取突破日前后的数据（前30天用于计算均线，后N天用于追踪）
        start_dt = datetime.strptime(breakout_date, '%Y%m%d') - timedelta(days=60)
        end_dt = datetime.strptime(breakout_date, '%Y%m%d') + timedelta(days=TRACK_DAYS * 2 + 5)
        start_str = start_dt.strftime('%Y%m%d')
        end_str = end_dt.strftime('%Y%m%d')

        df = self.fetcher.get_daily_data(ts_code, start_str, end_str)
        if df is None or df.empty:
            return {'code': ts_code, 'name': stock_name, 'status': 'ERROR', 'msg': '数据获取失败'}

        df = self._calc_indicators(df)

        # 定位突破日
        breakout_idx = df[df['trade_date'] == breakout_date].index
        if len(breakout_idx) == 0:
            return {'code': ts_code, 'name': stock_name, 'status': 'ERROR', 'msg': f'未找到突破日{breakout_date}数据'}
        breakout_idx = breakout_idx[0]
        breakout_row = df.loc[breakout_idx]

        # 突破日后的交易日
        follow_days = df.loc[breakout_idx + 1:].head(TRACK_DAYS)

        if follow_days.empty:
            return {
                'code': ts_code,
                'name': stock_name,
                'status': 'WAITING',
                'signal': '🕐 突破刚发生，等待次日数据',
                'breakout_date': breakout_date,
                'breakout_close': round(breakout_row['close'], 2),
                'breakout_vol_ratio': round(breakout_row['vol_ratio'], 2),
                'days_tracked': 0,
                'daily_log': []
            }

        # ============ 逐日决策 ============
        result = {
            'code': ts_code,
            'name': stock_name,
            'breakout_date': breakout_date,
            'breakout_close': round(breakout_row['close'], 2),
            'breakout_vol_ratio': round(breakout_row['vol_ratio'], 2),
            'ma20_at_breakout': round(breakout_row['ma20'], 2),
            'daily_log': [],
            'days_tracked': len(follow_days),
        }

        status = 'TRACKING'  # TRACKING → BUY / PULLBACK_WAIT / ABANDON
        pullback_mode = False  # 进入回踩等待模式
        buy_signal_day = None

        for i, (idx, row) in enumerate(follow_days.iterrows()):
            prev_row = df.loc[idx - 1] if idx > 0 else breakout_row
            day_type, day_desc = self._classify_day(row, prev_row)
            above_ma20 = row['close'] >= row['ma20'] * 0.99

            day_log = {
                'date': row['trade_date'],
                'close': round(row['close'], 2),
                'pct_chg': round(row['pct_chg'], 2),
                'vol_ratio': round(row['vol_ratio'], 2),
                'ma20': round(row['ma20'], 2),
                'type': day_type,
                'desc': day_desc,
                'above_ma20': above_ma20,
            }

            # ---- 路径C：放量跌 或 跌破MA20 → 放弃 ----
            if day_type == 'vol_down':
                day_log['decision'] = '❌ 放量下跌，假突破信号，放弃'
                result['daily_log'].append(day_log)
                status = 'ABANDON'
                result['abandon_reason'] = '放量下跌'
                break

            if not above_ma20 and not pullback_mode:
                # 第一次跌破MA20，还给一天观察机会
                pullback_mode = False
                day_log['decision'] = '⚠️ 跌破MA20，再观察一日'
                result['daily_log'].append(day_log)
                # 检查下一日是否收回
                continue

            if not above_ma20 and i > 0:
                # 连续跌破MA20
                prev_log = result['daily_log'][-1] if result['daily_log'] else None
                if prev_log and not prev_log.get('above_ma20', True):
                    day_log['decision'] = '❌ 连续跌破MA20，放弃'
                    result['daily_log'].append(day_log)
                    status = 'ABANDON'
                    result['abandon_reason'] = '连续跌破MA20'
                    break

            # ---- 路径A：放量涨 或 缩量涨 → 可介入 ----
            if day_type in ('vol_up', 'shrink_up') and above_ma20 and not pullback_mode:
                if day_type == 'shrink_up':
                    day_log['decision'] = '✅ 缩量上涨，惜售信号强，可介入（优质买点）'
                    result['buy_quality'] = '优质'
                else:
                    day_log['decision'] = '✅ 放量上涨，突破确认，可介入'
                    result['buy_quality'] = '标准'
                result['daily_log'].append(day_log)
                status = 'BUY'
                buy_signal_day = row['trade_date']
                break

            # ---- 路径B：缩量跌 → 进入回踩等待 ----
            if day_type in ('shrink_down', 'shrink_doji_down', 'shrink_doji_up') and above_ma20:
                pullback_mode = True
                # 检查是否出现企稳信号
                if self._check_pullback_confirm(row):
                    day_log['decision'] = '✅ 缩量企稳(十字星/小阳)+站上MA20，回踩买点确认！'
                    result['daily_log'].append(day_log)
                    status = 'BUY'
                    result['buy_quality'] = '回踩确认（最优）'
                    buy_signal_day = row['trade_date']
                    break
                else:
                    day_log['decision'] = '⏳ 缩量回踩中，等待企稳信号'
                    result['daily_log'].append(day_log)
                    continue

            # 其他情况
            day_log['decision'] = '⏳ 继续观察'
            result['daily_log'].append(day_log)

        # 追踪期结束仍未触发
        if status == 'TRACKING' or (status not in ('BUY', 'ABANDON')):
            if pullback_mode:
                status = 'PULLBACK_WAIT'
            else:
                status = 'EXPIRED'

        result['status'] = status
        if buy_signal_day:
            result['buy_signal_date'] = buy_signal_day

        # ============ 资金流交叉验证 ============
        if ENABLE_MONEYFLOW and status == 'BUY':
            mf = self.fetcher.get_moneyflow(ts_code, breakout_date, end_str)
            if mf is not None and not mf.empty:
                # 突破日及买入信号日的主力资金
                mf_breakout = mf[mf['trade_date'] == breakout_date]
                mf_buy = mf[mf['trade_date'] == buy_signal_day] if buy_signal_day else None

                fund_validation = {}
                if not mf_breakout.empty:
                    net = mf_breakout.iloc[0]['main_net_inflow']
                    fund_validation['breakout_day_main_net'] = round(net, 2)
                    fund_validation['breakout_day_fund_ok'] = net > 0

                if mf_buy is not None and not mf_buy.empty:
                    net = mf_buy.iloc[0]['main_net_inflow']
                    fund_validation['signal_day_main_net'] = round(net, 2)
                    fund_validation['signal_day_fund_ok'] = net > 0

                # 综合判定
                all_ok = all(v for k, v in fund_validation.items() if k.endswith('_ok'))
                fund_validation['fund_cross_validated'] = all_ok
                if not all_ok:
                    fund_validation['warning'] = '⚠️ 主力资金未确认，谨慎介入'
                else:
                    fund_validation['confirm'] = '✅ 主力资金确认，信号可靠'

                result['fund_validation'] = fund_validation

        return result


# ============================================================
# 输出格式化
# ============================================================
STATUS_EMOJI = {
    'BUY': '🟢',
    'PULLBACK_WAIT': '🟡',
    'TRACKING': '🔵',
    'WAITING': '🕐',
    'ABANDON': '🔴',
    'EXPIRED': '⚪',
    'ERROR': '❗',
}

STATUS_TEXT = {
    'BUY': '买入信号触发',
    'PULLBACK_WAIT': '回踩等待中',
    'TRACKING': '追踪中',
    'WAITING': '等待次日数据',
    'ABANDON': '信号失败，放弃',
    'EXPIRED': '追踪期满，未触发',
    'ERROR': '数据错误',
}


def format_result(r):
    """格式化单只股票结果为可读文本"""
    lines = []
    emoji = STATUS_EMOJI.get(r['status'], '❓')
    status_text = STATUS_TEXT.get(r['status'], r['status'])
    name_display = r.get('name', '') or r.get('code', '')
    code_display = r.get('code', '')

    lines.append(f"{emoji} {name_display} ({code_display})")
    lines.append(f"   状态: {status_text}")
    lines.append(f"   突破日: {r.get('breakout_date', 'N/A')} | "
                 f"突破价: {r.get('breakout_close', 'N/A')} | "
                 f"突破日量比: {r.get('breakout_vol_ratio', 'N/A')}x")

    if r.get('ma20_at_breakout'):
        lines.append(f"   MA20: {r['ma20_at_breakout']} | "
                     f"止损参考: {round(r['ma20_at_breakout'] * 0.99, 2)}")

    if r.get('buy_quality'):
        lines.append(f"   买点质量: {r['buy_quality']}")

    if r.get('buy_signal_date'):
        lines.append(f"   买入信号日: {r['buy_signal_date']}")

    # 逐日记录
    if r.get('daily_log'):
        lines.append(f"   --- 逐日追踪 ---")
        for d in r['daily_log']:
            vol_bar = '█' * min(int(d['vol_ratio'] * 3), 15)
            lines.append(
                f"   {d['date']} | 收:{d['close']} | "
                f"涨跌:{d['pct_chg']:+.2f}% | "
                f"量比:{d['vol_ratio']:.2f}x {vol_bar} | "
                f"{'✓MA20' if d['above_ma20'] else '✗MA20'}"
            )
            lines.append(f"      → {d['decision']}")

    # 资金流验证
    if r.get('fund_validation'):
        fv = r['fund_validation']
        lines.append(f"   --- 资金流验证 ---")
        if 'breakout_day_main_net' in fv:
            ok = '✅' if fv['breakout_day_fund_ok'] else '❌'
            lines.append(f"   突破日主力净流入: {fv['breakout_day_main_net']:.0f}万 {ok}")
        if 'signal_day_main_net' in fv:
            ok = '✅' if fv['signal_day_fund_ok'] else '❌'
            lines.append(f"   信号日主力净流入: {fv['signal_day_main_net']:.0f}万 {ok}")
        if 'warning' in fv:
            lines.append(f"   {fv['warning']}")
        if 'confirm' in fv:
            lines.append(f"   {fv['confirm']}")

    if r.get('abandon_reason'):
        lines.append(f"   放弃原因: {r['abandon_reason']}")

    return '\n'.join(lines)


def format_feishu_card(results):
    """生成飞书卡片格式的汇总（可直接用于webhook推送）"""
    buy_list = [r for r in results if r['status'] == 'BUY']
    wait_list = [r for r in results if r['status'] == 'PULLBACK_WAIT']
    abandon_list = [r for r in results if r['status'] == 'ABANDON']
    other_list = [r for r in results if r['status'] not in ('BUY', 'PULLBACK_WAIT', 'ABANDON')]

    sections = []

    if buy_list:
        section_text = "**🟢 买入信号触发**\n"
        for r in buy_list:
            name = r.get('name', r['code'])
            quality = r.get('buy_quality', '')
            fund_ok = ''
            if r.get('fund_validation', {}).get('fund_cross_validated'):
                fund_ok = ' | 资金✅'
            elif r.get('fund_validation'):
                fund_ok = ' | 资金⚠️'
            section_text += f"  • {name} - {quality}{fund_ok}\n"
        sections.append(section_text)

    if wait_list:
        section_text = "**🟡 回踩等待中**\n"
        for r in wait_list:
            name = r.get('name', r['code'])
            last_log = r['daily_log'][-1] if r.get('daily_log') else {}
            section_text += f"  • {name} - 收盘{last_log.get('close', 'N/A')} MA20:{last_log.get('ma20', 'N/A')}\n"
        sections.append(section_text)

    if abandon_list:
        section_text = "**🔴 信号失败**\n"
        for r in abandon_list:
            name = r.get('name', r['code'])
            reason = r.get('abandon_reason', '')
            section_text += f"  • {name} - {reason}\n"
        sections.append(section_text)

    if other_list:
        section_text = "**⚪ 其他**\n"
        for r in other_list:
            name = r.get('name', r['code'])
            status_text = STATUS_TEXT.get(r['status'], r['status'])
            section_text += f"  • {name} - {status_text}\n"
        sections.append(section_text)

    return '\n'.join(sections)


# ============================================================
# 飞书推送（可选）
# ============================================================
def push_to_feishu(webhook_url, results):
    """推送分析结果到飞书"""

    card_content = format_feishu_card(results)
    today = datetime.now().strftime('%Y-%m-%d')

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 突破信号追踪 - {today}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": card_content
                    }
                }
            ]
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        print(f"飞书推送: {resp.status_code}")
    except Exception as e:
        print(f"飞书推送失败: {e}")


# ============================================================
# 主函数
# ============================================================
def run_analysis(watchlist, feishu_webhook=None):
    """
    运行分析

    参数:
        watchlist: list of dict, 每个元素包含:
            - ts_code: 股票代码
            - breakout_date: 突破日期 (YYYYMMDD)
            - name: 股票名称（可选）
        feishu_webhook: 飞书webhook地址（可选）
    """
    fetcher = DataFetcher(TUSHARE_TOKEN)
    engine = BreakoutDecisionTree(fetcher)

    results = []
    print("=" * 60)
    print(f"  突破信号追踪分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    for item in watchlist:
        ts_code = item['ts_code']
        breakout_date = item['breakout_date']
        name = item.get('name', '')

        print(f"\n分析中: {name or ts_code} ...")
        r = engine.analyze_stock(ts_code, breakout_date, name)
        results.append(r)
        print(format_result(r))

    # 汇总统计
    print("\n" + "=" * 60)
    print("  汇总")
    print("=" * 60)
    status_counts = {}
    for r in results:
        s = r['status']
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, c in status_counts.items():
        emoji = STATUS_EMOJI.get(s, '')
        text = STATUS_TEXT.get(s, s)
        print(f"  {emoji} {text}: {c}只")

    # 飞书推送
    if feishu_webhook:
        push_to_feishu(feishu_webhook, results)

    return results


# ============================================================
# 使用示例
# ============================================================
if __name__ == '__main__':
    # ★ 在此填入你的突破筛选结果 ★
    # 每次你的MA20突破脚本筛出新信号后，把代码和日期添加到这里
    watchlist = [
        # 示例（请替换为实际数据）：
        # {'ts_code': '300246.SZ', 'breakout_date': '20260316', 'name': '宝莱特'},
        # {'ts_code': '688220.SH', 'breakout_date': '20260315', 'name': '翱捷科技'},
        # {'ts_code': '002076.SZ', 'breakout_date': '20260314', 'name': '*ST星光'},
    ]

    if not watchlist:
        print("⚠️ watchlist为空，请填入突破筛选结果后运行。")
        print("\n使用方法：")
        print("1. 在上方 TUSHARE_TOKEN 填入你的token")
        print("2. 在 watchlist 中添加突破信号：")
        print("   {'ts_code': '300246.SZ', 'breakout_date': '20260316', 'name': '宝莱特'}")
        print("3. 运行: python breakout_decision_tree.py")
        print("\n也可以从其他脚本调用：")
        print("   from breakout_decision_tree import run_analysis")
        print("   results = run_analysis(watchlist)")
    else:
        # 可选：飞书推送
        results = run_analysis(
            watchlist,
            feishu_webhook=FEISHU_WEBHOOK if FEISHU_WEBHOOK else None
        )
