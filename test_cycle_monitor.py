#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期股买点监控脚本测试版 — 用实际数据测试
演员三人组：合盛硅业 / 海螺水泥 / 万华化学
"""

import sys
import io

# 强制使用UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import time
import tushare as ts
import numpy as np
from datetime import datetime, timedelta

# ============ 配置区 ============
# 这里填入你的 Tushare Token
# 获取地址：https://tushare.pro
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"

# 三个标的配置
STOCKS = [
    {
        "code": "603260.SH",
        "name": "合盛硅业",
        "sector": "有机硅",
        "strategy": "等Q1扣非转正+MA20突破",
        "wait_for": "扣非拐点+技术确认",
        "earnings_date": "2026-04-30",
        "earnings_desc": "2026Q1报(确认扣非是否转正)",
    },
    {
        "code": "600585.SH",
        "name": "海螺水泥",
        "sector": "水泥",
        "strategy": "扣非已确认,等MA20放量突破",
        "wait_for": "技术面突破",
        "earnings_date": "2026-03-25",
        "earnings_desc": "2025年报(全年扣非确认)",
    },
    {
        "code": "600309.SH",
        "name": "万华化学",
        "sector": "MDI",
        "strategy": "等回调企稳做底仓",
        "wait_for": "回调企稳",
        "earnings_date": "2026-03-28",
        "earnings_desc": "2025年报",
    },
]

# ============ 初始化 ============
print("="*50)
print("周期股买点监控 — 实际数据测试")
print("="*50)
print()

# 检查 Token
if TUSHARE_TOKEN == "替换为你的Tushare_Token":
    print("[ERROR] 请先配置 TUSHARE_TOKEN！")
    print("获取地址: https://tushare.pro")
    print()
    print("修改脚本第16行，将 TUSHARE_TOKEN 替换为你的真实Token")
    sys.exit(1)

try:
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    print("[OK] Tushare连接成功\n")
except Exception as e:
    print(f"[ERROR] Tushare初始化失败: {e}")
    print("请检查Token是否正确")
    sys.exit(1)


def get_stock_data(ts_code, days=250):
    """获取个股日线+估值数据"""
    try:
        print(f"  获取 {ts_code} 的历史数据...", end=" ", flush=True)
        
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

        # 日线
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=today)
        if df is None or df.empty:
            print("[无数据]")
            return None, None
        
        df = df.sort_values('trade_date', ascending=True).reset_index(drop=True)
        print(f"[{len(df)}条]", end=" ", flush=True)

        time.sleep(0.3)

        # 估值
        df_basic = pro.daily_basic(ts_code=ts_code, start_date=start, end_date=today)
        if df_basic is not None and not df_basic.empty:
            df_basic = df_basic.sort_values('trade_date', ascending=True).reset_index(drop=True)
            print(f"估值[{len(df_basic)}条]", end=" ", flush=True)

        print("[OK]")
        return df, df_basic
    except Exception as e:
        print(f"[ERROR] {e}")
        return None, None


def analyze_stock(stock_config, daily_df, basic_df):
    """分析单只股票，返回信号"""
    if daily_df is None or len(daily_df) < 60:
        return None

    close = daily_df['close'].values
    vol = daily_df['vol'].values
    price = close[-1]
    price_prev = close[-2] if len(close) >= 2 else price

    # ========== 均线计算 ==========
    ma5 = round(np.mean(close[-5:]), 2) if len(close) >= 5 else None
    ma10 = round(np.mean(close[-10:]), 2) if len(close) >= 10 else None
    ma20 = round(np.mean(close[-20:]), 2) if len(close) >= 20 else None
    ma60 = round(np.mean(close[-60:]), 2) if len(close) >= 60 else None
    ma120 = round(np.mean(close[-120:]), 2) if len(close) >= 120 else None

    # 昨日MA20/MA60
    ma20_prev = round(np.mean(close[-21:-1]), 2) if len(close) >= 21 else None
    ma60_prev = round(np.mean(close[-61:-1]), 2) if len(close) >= 61 else None

    # MA20方向
    ma20_5d_ago = round(np.mean(close[-25:-5]), 2) if len(close) >= 25 else None
    ma20_dir = "未知"
    if ma20 and ma20_5d_ago:
        if ma20 > ma20_5d_ago + 0.05:
            ma20_dir = "拐头向上"
        elif ma20 < ma20_5d_ago - 0.05:
            ma20_dir = "向下"
        else:
            ma20_dir = "走平"

    # ========== 成交量 ==========
    vol_5d = round(np.mean(vol[-5:]), 0) if len(vol) >= 5 else None
    vol_20d = round(np.mean(vol[-20:]), 0) if len(vol) >= 20 else None
    vol_ratio = round(vol[-1] / vol_5d, 2) if vol_5d and vol_5d > 0 else None

    # ========== 估值 ==========
    pe_ttm = None
    pb = None
    dv_ttm = None
    if basic_df is not None and not basic_df.empty:
        latest_basic = basic_df.iloc[-1]
        pe_ttm = round(latest_basic.get('pe_ttm', 0), 2) if latest_basic.get('pe_ttm') else None
        pb = round(latest_basic.get('pb', 0), 2) if latest_basic.get('pb') else None
        dv_ttm = round(latest_basic.get('dv_ttm', 0), 2) if latest_basic.get('dv_ttm') else None

    # PB历史分位
    pb_percentile = None
    if basic_df is not None and 'pb' in basic_df.columns:
        pb_series = basic_df['pb'].dropna()
        if len(pb_series) >= 20 and pb:
            pb_percentile = round((pb_series < pb).sum() / len(pb_series) * 100, 1)

    # ========== 信号判断 ==========
    signals = []
    alert_level = 0  # 0=无 1=关注 2=重要 3=立即行动

    # --- MA20突破判断 ---
    above_ma20_today = price > ma20 if ma20 else False
    above_ma20_prev = price_prev > ma20_prev if ma20_prev else False

    if above_ma20_today and not above_ma20_prev:
        signals.append("[火] 今日站上MA20!短期趋势转好")
        alert_level = max(alert_level, 2)
        # 放量突破
        if vol_ratio and vol_ratio >= 1.5:
            signals.append(f"[火火] 放量突破MA20!(量比{vol_ratio:.1f}x)")
            alert_level = max(alert_level, 3)
    elif above_ma20_today:
        signals.append("[OK] 站在MA20之上")
        alert_level = max(alert_level, 1)
    else:
        diff = round((price / ma20 - 1) * 100, 2) if ma20 else 0
        signals.append(f"[警] 在MA20之下 (偏离{diff:+.2f}%)")
        # 接近MA20（偏离<2%）
        if ma20 and abs(diff) < 2:
            signals.append("[看] 接近MA20,关注能否突破")
            alert_level = max(alert_level, 1)

    # --- MA60判断 ---
    if ma60:
        above_ma60_today = price > ma60
        above_ma60_prev = price_prev > ma60_prev if ma60_prev else False
        if above_ma60_today and not above_ma60_prev:
            signals.append("[火] 今日站上MA60!中期趋势转好")
            alert_level = max(alert_level, 2)
        elif not above_ma60_today and above_ma60_prev:
            signals.append("[警] 今日跌破MA60!注意风险")
        elif above_ma60_today:
            signals.append("[OK] 站在MA60之上")
        else:
            signals.append("[警] 在MA60之下")

    # --- 均线多头排列 ---
    if ma5 and ma10 and ma20 and ma60:
        if ma5 > ma10 > ma20 > ma60:
            signals.append("[OK] 均线多头排列")
            alert_level = max(alert_level, 1)
        elif ma5 < ma10 < ma20 < ma60:
            signals.append("[X] 均线空头排列")

    # --- 缩量企稳判断（万华化学用）---
    if vol_ratio and vol_ratio < 0.7:
        chg = daily_df.iloc[-1]['pct_chg']
        if abs(chg) < 1:
            signals.append("[图] 缩量窄幅震荡(企稳信号)")
            alert_level = max(alert_level, 1)

    # --- 连续下跌后反弹 ---
    if len(close) >= 5:
        recent_changes = [daily_df.iloc[i]['pct_chg'] for i in range(-5, 0)]
        down_days = sum(1 for c in recent_changes if c < 0)
        if down_days >= 4 and daily_df.iloc[-1]['pct_chg'] > 0:
            signals.append("[图] 连跌后首次收阳(可能企稳)")
            alert_level = max(alert_level, 1)

    # ========== 年报倒计时 ==========
    earnings_countdown = None
    try:
        ed = datetime.strptime(stock_config["earnings_date"], "%Y-%m-%d")
        days_left = (ed - datetime.now()).days
        if days_left > 0:
            earnings_countdown = days_left
    except:
        pass

    return {
        "price": price,
        "change_pct": round(daily_df.iloc[-1]['pct_chg'], 2),
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "ma20_dir": ma20_dir,
        "vol_ratio": vol_ratio,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "pb_percentile": pb_percentile,
        "dv_ttm": dv_ttm,
        "signals": signals,
        "alert_level": alert_level,
        "earnings_countdown": earnings_countdown,
    }


def print_report(results):
    """打印分析报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 判断最高警报级别
    max_alert = max(r.get("alert_level", 0) for r in results if r)

    print()
    print("="*60)
    if max_alert >= 3:
        print("[SOS] 周期股买点信号触发!")
    elif max_alert >= 2:
        print("[!] 周期股重要信号出现")
    else:
        print("[D] 周期股三标的日报")
    
    print(f"时间: {now}")
    print("="*60)

    for i, stock in enumerate(STOCKS):
        r = results[i]
        if r is None:
            print(f"\n[X] {stock['name']}({stock['code']}) 数据获取失败")
            continue

        print()
        # 标题带警报标记
        alert_mark = ""
        if r["alert_level"] >= 3:
            alert_mark = " [SOS买点]"
        elif r["alert_level"] >= 2:
            alert_mark = " [!关注]"

        print(f"{'─'*60}")
        print(f"[{stock['name']}] {stock['sector']}{alert_mark}")
        print(f"策略: {stock['strategy']}")

        # 价格和涨跌
        arrow = "[UP]" if r["change_pct"] > 0 else "[DN]" if r["change_pct"] < 0 else "[=]"
        print(f"股价: {r['price']:.2f} {arrow} {r['change_pct']:+.2f}%")

        # 均线
        if r["ma20"]:
            diff20 = round((r["price"] / r["ma20"] - 1) * 100, 2)
            print(f"MA20: {r['ma20']:.2f} (偏离{diff20:+.2f}%)")
        if r["ma60"]:
            diff60 = round((r["price"] / r["ma60"] - 1) * 100, 2)
            print(f"MA60: {r['ma60']:.2f} (偏离{diff60:+.2f}%)")
        if r["ma120"]:
            print(f"MA120: {r['ma120']:.2f}")
        print(f"MA20方向: {r['ma20_dir']}")

        # 量比
        if r["vol_ratio"]:
            print(f"量比: {r['vol_ratio']:.2f}x")

        # 估值
        val_parts = []
        if r["pe_ttm"]:
            val_parts.append(f"PE {r['pe_ttm']:.1f}")
        if r["pb"]:
            pb_str = f"PB {r['pb']:.2f}"
            if r["pb_percentile"] is not None:
                pb_str += f"({r['pb_percentile']:.0f}%分位)"
            val_parts.append(pb_str)
        if r["dv_ttm"]:
            val_parts.append(f"股息率{r['dv_ttm']:.2f}%")
        if val_parts:
            print(" | ".join(val_parts))

        # 信号
        print("信号:")
        for s in r["signals"]:
            print(f"  {s}")

        # 年报倒计时
        if r["earnings_countdown"]:
            print(f"[时] {stock['earnings_desc']}: 还有{r['earnings_countdown']}天")

    # ========== 综合评估 ==========
    print()
    print("="*60)
    print("[综合评估]")
    print()

    for i, stock in enumerate(STOCKS):
        r = results[i]
        if r is None:
            continue

        score = 0
        checks = []

        # MA20
        if r["ma20"] and r["price"] > r["ma20"]:
            checks.append("[OK]MA20之上")
            score += 1
        else:
            checks.append("[X]MA20之下")

        # MA20方向
        if "向上" in r["ma20_dir"]:
            checks.append("[OK]MA20向上")
            score += 1
        else:
            checks.append("[警]MA20未向上")

        # MA60
        if r["ma60"] and r["price"] > r["ma60"]:
            checks.append("[OK]MA60之上")
            score += 1
        else:
            checks.append("[X]MA60之下")

        # 量比
        if r["vol_ratio"] and r["vol_ratio"] >= 1.5:
            if r["change_pct"] > 0:
                checks.append("[OK]放量上涨")
                score += 1
            else:
                checks.append("[警]放量下跌")
        elif r["vol_ratio"] and r["vol_ratio"] < 0.7:
            checks.append("[图]缩量(观察)")

        status = "[绿]可操作" if score >= 3 else "[黄]等待中" if score >= 1 else "[红]未启动"
        print(f"  {stock['name']}: {' '.join(checks)} -> {status}({score}/4)")

    # 操作提醒
    print()
    print("="*60)
    print("[提醒] 操作纪律:")
    print("  合盛硅业: Q1扣非转正+MA20放量突破=买")
    print("  海螺水泥: MA20放量突破=买,跌破MA20=卖")
    print("  万华化学: 缩量企稳+重回MA20=建底仓")
    print("="*60)


def main():
    print(f"\n开始获取实际数据...\n")

    results = []
    for stock in STOCKS:
        print(f"[{stock['name']}({stock['code']})]")
        daily_df, basic_df = get_stock_data(stock["code"])
        time.sleep(0.5)

        r = analyze_stock(stock, daily_df, basic_df)
        results.append(r)

        if r:
            print(f"  ✓ 分析完成 | 股价:{r['price']:.2f} | 信号级别:{r['alert_level']}")
        else:
            print(f"  ✗ 分析失败")
        print()

    # 打印报告
    print_report(results)

    print("\n[完成] 测试报告已生成\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
