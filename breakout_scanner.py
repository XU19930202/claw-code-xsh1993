#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市场均线突破扫描器
默认扫描全部A股，找出当天首次放量站上均线的股票

规则一：今天首次站上均线（昨天在下方，今天在上方）
规则二：今天成交量 ≥ 5日均量 × 1.5

使用方法：
  python breakout_scanner.py                # 全市场扫描MA20突破
  python breakout_scanner.py --ma 60        # 全市场扫描MA60突破
  python breakout_scanner.py --ma 120       # 全市场扫描MA120突破
  python breakout_scanner.py --no-push      # 只打印不推送飞书

定时任务（每个交易日收盘后跑三次，分别扫三条均线）：
  30 17 * * 1-5 cd /path && python breakout_scanner.py --ma 20
  35 17 * * 1-5 cd /path && python breakout_scanner.py --ma 60
  40 17 * * 1-5 cd /path && python breakout_scanner.py --ma 120
"""

import sys
import time
import argparse
import requests
import tushare as ts
import numpy as np
from datetime import datetime, timedelta

# ============ 配置区 ============
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"

# ============ 初始化 ============
ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def get_all_stocks():
    """获取全部A股，排除ST、退市、北交所、次新股"""
    try:
        df = pro.stock_basic(
            exchange='', list_status='L',
            fields='ts_code,name,industry,market,list_date'
        )
        if df is None or df.empty:
            return []

        # 排除ST和退市
        df = df[~df['name'].str.contains('ST|退', na=False)]

        # 排除北交所（8开头）
        df = df[~df['ts_code'].str.startswith('8')]

        # 排除上市不满半年的次新股（波动太大）
        cutoff = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
        df = df[df['list_date'] <= cutoff]

        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "code": row['ts_code'],
                "name": row['name'],
                "industry": row['industry'] if row['industry'] else '未知',
            })
        return stocks

    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []


def get_daily_data(ts_code, days=150):
    """获取个股日线数据"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 50)).strftime("%Y%m%d")
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=today)
        if df is not None and not df.empty:
            df = df.sort_values('trade_date', ascending=True).reset_index(drop=True)
            return df
    except:
        pass
    return None


def check_breakout(daily_df, ma_period):
    """
    检查突破条件
    规则一：昨天收盘 < 昨日均线，今天收盘 > 今日均线
    规则二：今日成交量 ≥ 5日均量 × 1.5
    """
    if daily_df is None or len(daily_df) < ma_period + 6:
        return None

    close = daily_df['close'].values
    vol = daily_df['vol'].values

    price_today = close[-1]
    price_yesterday = close[-2]
    change_pct = daily_df.iloc[-1]['pct_chg']

    # 今日和昨日均线
    ma_today = np.mean(close[-ma_period:])
    ma_yesterday = np.mean(close[-(ma_period + 1):-1])

    # 规则一：首次站上均线
    if not (price_today > ma_today and price_yesterday <= ma_yesterday):
        return None

    # 5日均量（不含今天）
    vol_today = vol[-1]
    vol_5d_avg = np.mean(vol[-6:-1])
    vol_ratio = round(vol_today / vol_5d_avg, 2) if vol_5d_avg > 0 else 0

    # 规则二：是否放量
    is_vol_breakout = vol_ratio >= 1.5

    # 参考均线
    ma20 = round(np.mean(close[-20:]), 2) if len(close) >= 20 else None
    ma60 = round(np.mean(close[-60:]), 2) if len(close) >= 60 else None
    ma120 = round(np.mean(close[-120:]), 2) if len(close) >= 120 else None

    # 均线方向
    ma_dir = "未知"
    if len(close) >= ma_period + 5:
        ma_5d_ago = np.mean(close[-(ma_period + 5):-5])
        ma_dir = "向上" if ma_today > ma_5d_ago else "向下"

    # 评分（满分7分）
    score = 0
    tags = []

    # 放量（0-3分）
    if vol_ratio >= 2.0:
        score += 3; tags.append(f"强放量{vol_ratio:.1f}x")
    elif vol_ratio >= 1.5:
        score += 2; tags.append(f"放量{vol_ratio:.1f}x")
    else:
        tags.append(f"量{vol_ratio:.1f}x")

    # 涨幅（0-2分）
    if change_pct >= 3:
        score += 2; tags.append(f"涨{change_pct:.1f}%")
    elif change_pct >= 1:
        score += 1; tags.append(f"涨{change_pct:.1f}%")
    else:
        tags.append(f"{change_pct:+.1f}%")

    # 均线方向（0-1分）
    if ma_dir == "向上":
        score += 1; tags.append("MA上")
    else:
        tags.append("MA下")

    # 站在更长均线上方（0-1分）
    if ma_period == 20 and ma60 and price_today > ma60:
        score += 1; tags.append(">MA60")
    elif ma_period == 60 and ma120 and price_today > ma120:
        score += 1; tags.append(">MA120")

    return {
        "price": round(price_today, 2),
        "change_pct": round(change_pct, 2),
        "ma_period": ma_period,
        "ma_value": round(ma_today, 2),
        "vol_ratio": vol_ratio,
        "is_vol_breakout": is_vol_breakout,
        "score": score,
        "tags": tags,
        "ma_dir": ma_dir,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
    }


def build_message(breakouts, ma_period, elapsed_min, total_scanned):
    """构建飞书推送消息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    strong = [b for b in breakouts if b["result"]["is_vol_breakout"]]
    weak = [b for b in breakouts if not b["result"]["is_vol_breakout"]]

    strong.sort(key=lambda x: x["result"]["score"], reverse=True)
    weak.sort(key=lambda x: x["result"]["score"], reverse=True)

    lines = []

    if strong:
        lines.append(f"[SOS] MA{ma_period}放量突破 | {now}")
    else:
        lines.append(f"[扫描] MA{ma_period}突破扫描 | {now}")

    lines.append(f"扫描{total_scanned}只A股 | 耗时{elapsed_min:.0f}分钟")
    lines.append(f"放量突破: {len(strong)}只 | 站上未放量: {len(weak)}只")
    lines.append("=" * 38)

    # 放量突破（按行业分组）
    if strong:
        lines.append("")
        lines.append(f"[火] 放量突破MA{ma_period}（共{len(strong)}只）")

        industry_groups = {}
        for b in strong:
            ind = b["industry"]
            if ind not in industry_groups:
                industry_groups[ind] = []
            industry_groups[ind].append(b)

        # 按行业内股票数量排序（多的排前面）
        for ind, stocks in sorted(industry_groups.items(), key=lambda x: -len(x[1])):
            lines.append(f"")
            lines.append(f"  【{ind}】({len(stocks)}只)")
            for b in sorted(stocks, key=lambda x: x["result"]["score"], reverse=True):
                r = b["result"]
                lines.append(
                    f"    {b['name']}({b['code']})"
                    f" {r['price']}元 {r['change_pct']:+.1f}%"
                    f" 量比{r['vol_ratio']:.1f}x"
                    f" 评分{r['score']}/7"
                    f" [{' '.join(r['tags'])}]"
                )
    else:
        lines.append("")
        lines.append(f"今日无MA{ma_period}放量突破")

    # 站上未放量（只显示评分最高的前15只）
    if weak:
        lines.append("")
        lines.append("=" * 38)
        show_n = min(15, len(weak))
        lines.append(f"[观察] 站上MA{ma_period}未放量（前{show_n}/{len(weak)}只）")
        for b in weak[:show_n]:
            r = b["result"]
            lines.append(
                f"  {b['name']}({b['code']}) [{b['industry']}]"
                f" {r['price']}元 {r['change_pct']:+.1f}%"
                f" 量比{r['vol_ratio']:.1f}x"
            )

    # 操作纪律
    lines.append("")
    lines.append("=" * 38)
    lines.append("[操作纪律]:")
    lines.append("  放量突破当天 -> 买入1/3")
    lines.append("  站稳3-5天不破 -> 加仓1/3")
    lines.append("  3天内跌回均线下 -> 止损")
    lines.append("  未放量 -> 只观察不操作")

    return "\n".join(lines)


def send_to_feishu(message):
    """发送到飞书（自动分段）"""
    MAX_LEN = 3500
    parts = []
    if len(message) > MAX_LEN:
        lines = message.split("\n")
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > MAX_LEN:
                parts.append(current)
                current = line
            else:
                current += "\n" + line if current else line
        if current:
            parts.append(current)
    else:
        parts = [message]

    for i, part in enumerate(parts):
        if i > 0:
            part = f"(续{i + 1})\n" + part
        payload = {"msg_type": "text", "content": {"text": part}}
        try:
            resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
            if resp.status_code == 200:
                r = resp.json()
                if r.get('code') == 0 or r.get('StatusCode') == 0:
                    print(f"[OK] 飞书推送成功 (第{i + 1}段)")
                else:
                    print(f"[!] 飞书返回: {r}")
            else:
                print(f"[X] HTTP {resp.status_code}")
        except Exception as e:
            print(f"[X] 推送失败: {e}")
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description='全市场均线突破扫描器')
    parser.add_argument('--ma', type=int, default=20, choices=[20, 60, 120],
                        help='均线周期: 20/60/120 (默认20)')
    parser.add_argument('--no-push', action='store_true', help='不推送飞书')
    args = parser.parse_args()

    ma_period = args.ma

    print(f"{'=' * 50}")
    print(f"  全市场 MA{ma_period} 突破扫描器")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  规则: 首次站上MA{ma_period} + 成交量>=1.5倍5日均量")
    print(f"{'=' * 50}")

    # 获取全部A股
    print("\n获取全部A股列表...")
    stocks = get_all_stocks()
    total = len(stocks)
    print(f"共 {total} 只股票\n")

    if not stocks:
        print("[X] 获取股票列表失败")
        return

    # 扫描
    breakouts = []
    failed = 0
    start_time = time.time()

    for idx, stock in enumerate(stocks):
        # 进度
        if (idx + 1) % 100 == 0:
            elapsed = time.time() - start_time
            speed = (idx + 1) / elapsed
            eta = (total - idx - 1) / speed / 60
            found = len(breakouts)
            strong_n = sum(1 for b in breakouts if b["result"]["is_vol_breakout"])
            print(f"  进度 {idx + 1}/{total}"
                  f" ({(idx + 1) / total * 100:.0f}%)"
                  f" | 发现{found}只(放量{strong_n})"
                  f" | 剩余约{eta:.1f}分钟")

        # 获取数据
        df = get_daily_data(stock["code"], days=max(ma_period + 30, 150))
        time.sleep(0.12)

        if df is None:
            failed += 1
            continue

        # 检查突破
        result = check_breakout(df, ma_period)
        if result:
            breakouts.append({
                "code": stock["code"],
                "name": stock["name"],
                "industry": stock["industry"],
                "result": result,
            })

            mark = "[火]放量" if result["is_vol_breakout"] else "[看]站上"
            print(f"  {mark} {stock['name']}({stock['code']})"
                  f" [{stock['industry']}]"
                  f" {result['price']}元 {result['change_pct']:+.1f}%"
                  f" 量比{result['vol_ratio']:.1f}x"
                  f" 评分{result['score']}/7")

    # 汇总
    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60
    strong = [b for b in breakouts if b["result"]["is_vol_breakout"]]
    weak = [b for b in breakouts if not b["result"]["is_vol_breakout"]]

    print(f"\n{'=' * 50}")
    print(f"  扫描完成!")
    print(f"  耗时: {elapsed_min:.1f}分钟 | 扫描{total}只 | 失败{failed}只")
    print(f"  [火] MA{ma_period}放量突破: {len(strong)}只")
    print(f"  [看] 站上未放量: {len(weak)}只")
    print(f"{'=' * 50}")

    # 构建消息
    message = build_message(breakouts, ma_period, elapsed_min, total)
    print(f"\n{message}")

    # 推送
    if not args.no_push:
        print("\n推送到飞书...")
        send_to_feishu(message)

        if strong:
            top = strong[:8]
            top.sort(key=lambda x: x["result"]["score"], reverse=True)
            names = "\n".join([
                f"  {b['name']}({b['code']}) [{b['industry']}]"
                f" {b['result']['price']}元"
                f" {b['result']['change_pct']:+.1f}%"
                f" 量比{b['result']['vol_ratio']:.1f}x"
                f" 评分{b['result']['score']}/7"
                for b in top
            ])
            alert = (
                f"[SOS] MA{ma_period}放量突破 TOP{len(top)}\n\n"
                f"{names}\n\n"
                f"共{len(strong)}只放量突破"
            )
            send_to_feishu(alert)

    print(f"\n完成! {datetime.now()}")


if __name__ == "__main__":
    main()
