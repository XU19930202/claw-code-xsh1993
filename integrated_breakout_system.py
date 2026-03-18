#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整突破交易系统集成脚本
==========================================
三层递进式完整流程：

1. 扫描阶段 (breakout_scanner.py)
   └─ 全市场 5244 只股票 → 发现放量突破信号

2. 追踪阶段 (breakout_decision_tree.py)
   └─ 对昨天的突破信号进行5日追踪 → 输出买入信号

3. 自动集成 (本脚本)
   └─ 自动连接上述两个流程，形成完整闭环

使用方法：
  python integrated_breakout_system.py             # 完整流程（扫描→追踪→推送）
  python integrated_breakout_system.py --scan-only # 仅扫描新信号
  python integrated_breakout_system.py --track-only # 仅追踪历史信号

定时任务建议：
  ✅ 收盘后 17:50 运行全流程
"""

import sys
import os
import argparse
import json
import csv
from datetime import datetime, timedelta
import pandas as pd

# 导入两个模块
from breakout_scanner import (
    get_all_stocks, calculate_signals, send_to_feishu as scanner_push_feishu
)
from breakout_decision_tree import (
    DataFetcher, BreakoutDecisionTree, format_result, 
    format_feishu_card, push_to_feishu, STATUS_TEXT, STATUS_EMOJI
)

# 配置
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"

# 信号历史保存文件
SIGNAL_HISTORY_FILE = "breakout_signals_history.csv"
TODAY = datetime.now().strftime('%Y%m%d')
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')


# ============================================================
# 核心整合逻辑
# ============================================================

def load_signal_history():
    """加载历史信号"""
    if os.path.exists(SIGNAL_HISTORY_FILE):
        return pd.read_csv(SIGNAL_HISTORY_FILE)
    return pd.DataFrame(columns=['ts_code', 'name', 'breakout_date', 'ma_type', 'signal_status'])


def save_signal_history(df):
    """保存信号历史"""
    df.to_csv(SIGNAL_HISTORY_FILE, index=False)


def get_yesterday_signals():
    """获取昨天的突破信号，用于今天追踪"""
    history = load_signal_history()
    if history.empty:
        return []
    
    yesterday_signals = history[
        (history['breakout_date'] == YESTERDAY) & 
        (history['signal_status'] == 'breakout')
    ]
    
    result = []
    for _, row in yesterday_signals.iterrows():
        result.append({
            'ts_code': row['ts_code'],
            'name': row['name'],
            'breakout_date': row['breakout_date']
        })
    return result


def run_scan_phase(ma_type=20):
    """
    阶段1：扫描新的突破信号
    
    返回: list of dict，每个元素包含 {ts_code, name, breakout_date}
    """
    print("\n" + "="*60)
    print(f"  【阶段1】全市场扫描 MA{ma_type} 突破")
    print("="*60)
    
    import tushare as ts
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    stocks = get_all_stocks(pro)
    print(f"✓ 获取 {len(stocks)} 只股票")
    
    signals = calculate_signals(pro, stocks, ma_type)
    print(f"✓ 发现 {len(signals)} 个放量突破信号")
    
    # 保存到历史
    history = load_signal_history()
    new_records = []
    for sig in signals:
        new_records.append({
            'ts_code': sig['ts_code'],
            'name': sig.get('name', ''),
            'breakout_date': TODAY,
            'ma_type': ma_type,
            'signal_status': 'breakout'
        })
    
    if new_records:
        history = pd.concat([history, pd.DataFrame(new_records)], ignore_index=True)
        save_signal_history(history)
    
    return signals


def run_track_phase():
    """
    阶段2：追踪昨天的突破信号
    
    返回: list of dict，每个元素的分析结果
    """
    print("\n" + "="*60)
    print(f"  【阶段2】追踪昨天突破信号的后续走势")
    print("="*60)
    
    watchlist = get_yesterday_signals()
    
    if not watchlist:
        print("⚠️ 没有找到需要追踪的信号")
        return []
    
    print(f"✓ 追踪 {len(watchlist)} 个信号")
    
    fetcher = DataFetcher(TUSHARE_TOKEN)
    engine = BreakoutDecisionTree(fetcher)
    
    results = []
    for item in watchlist:
        ts_code = item['ts_code']
        breakout_date = item['breakout_date']
        name = item.get('name', '')
        
        print(f"  分析: {name or ts_code} ...")
        r = engine.analyze_stock(ts_code, breakout_date, name)
        results.append(r)
    
    return results


def generate_integrated_report(scan_results=None, track_results=None):
    """
    生成整合报告
    """
    lines = []
    lines.append("\n" + "="*60)
    lines.append(f"  【集成报告】{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("="*60)
    
    # 扫描阶段结果
    if scan_results:
        lines.append(f"\n📊 【阶段1】扫描结果 ({len(scan_results)} 个信号)")
        lines.append("-" * 60)
        by_industry = {}
        for sig in scan_results:
            industry = sig.get('industry', '其他')
            if industry not in by_industry:
                by_industry[industry] = []
            by_industry[industry].append(sig)
        
        for industry, stocks in sorted(by_industry.items()):
            lines.append(f"\n  【{industry}】({len(stocks)}只)")
            for stock in stocks[:5]:  # 只显示前5个
                lines.append(f"    • {stock['name']}({stock['ts_code']}) "
                           f"{stock['close']}元 +{stock['pct_chg']:.1f}% "
                           f"量比{stock['vol_ratio']:.1f}x")
            if len(stocks) > 5:
                lines.append(f"    ... 还有 {len(stocks)-5} 只")
    
    # 追踪阶段结果
    if track_results:
        lines.append(f"\n🎯 【阶段2】追踪结果 ({len(track_results)} 个信号)")
        lines.append("-" * 60)
        
        status_counts = {}
        for r in track_results:
            s = r['status']
            status_counts[s] = status_counts.get(s, 0) + 1
        
        for status, count in status_counts.items():
            emoji = STATUS_EMOJI.get(status, '')
            text = STATUS_TEXT.get(status, status)
            lines.append(f"  {emoji} {text}: {count}只")
        
        # 显示买入信号
        buy_signals = [r for r in track_results if r['status'] == 'BUY']
        if buy_signals:
            lines.append(f"\n  🟢 买入信号详情:")
            for r in buy_signals:
                name = r.get('name', r['code'])
                quality = r.get('buy_quality', '')
                lines.append(f"    • {name} - {quality}")
    
    lines.append("\n" + "="*60)
    
    return '\n'.join(lines)


def push_integrated_report(scan_results=None, track_results=None):
    """推送整合报告到飞书"""
    import requests
    
    # 构建卡片内容
    sections = []
    
    if scan_results:
        section = f"**📊 扫描结果 ({len(scan_results)} 个信号)**\n"
        by_industry = {}
        for sig in scan_results:
            industry = sig.get('industry', '其他')
            if industry not in by_industry:
                by_industry[industry] = []
            by_industry[industry].append(sig)
        
        for industry, stocks in list(by_industry.items())[:5]:  # 只显示前5个行业
            section += f"{industry}({len(stocks)}只) "
        
        sections.append(section)
    
    if track_results:
        section = f"**🎯 追踪结果**\n"
        
        buy_list = [r for r in track_results if r['status'] == 'BUY']
        wait_list = [r for r in track_results if r['status'] == 'PULLBACK_WAIT']
        abandon_list = [r for r in track_results if r['status'] == 'ABANDON']
        
        if buy_list:
            section += f"🟢 买入信号: {len(buy_list)}只\n"
            for r in buy_list[:3]:
                section += f"  • {r.get('name', r['code'])} - {r.get('buy_quality', '')}\n"
        
        if wait_list:
            section += f"🟡 回踩等待: {len(wait_list)}只\n"
        
        if abandon_list:
            section += f"🔴 信号失败: {len(abandon_list)}只\n"
        
        sections.append(section)
    
    card_content = '\n'.join(sections)
    today = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚀 突破交易系统 - {today}"
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
        resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[OK] 整合报告已推送到飞书")
        else:
            print(f"[!] 飞书返回: {resp.status_code}")
    except Exception as e:
        print(f"[X] 推送失败: {e}")


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='突破交易系统集成')
    parser.add_argument('--scan-only', action='store_true', help='仅运行扫描阶段')
    parser.add_argument('--track-only', action='store_true', help='仅运行追踪阶段')
    parser.add_argument('--ma', type=int, default=20, help='均线周期 (默认20)')
    parser.add_argument('--no-push', action='store_true', help='不推送飞书')
    
    args = parser.parse_args()
    
    scan_results = None
    track_results = None
    
    try:
        # 阶段1：扫描
        if not args.track_only:
            scan_results = run_scan_phase(args.ma)
        
        # 阶段2：追踪
        if not args.scan_only:
            track_results = run_track_phase()
        
        # 输出报告
        report = generate_integrated_report(scan_results, track_results)
        print(report)
        
        # 推送飞书
        if not args.no_push:
            push_integrated_report(scan_results, track_results)
    
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
