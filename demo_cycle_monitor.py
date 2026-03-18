#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期股买点监控脚本 — 模拟测试版
用模拟数据演示脚本功能，无需Tushare Token
"""

import sys
import io
import random
from datetime import datetime

# 强制使用UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np

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
        "base_price": 45.32,
    },
    {
        "code": "600585.SH",
        "name": "海螺水泥",
        "sector": "水泥",
        "strategy": "扣非已确认,等MA20放量突破",
        "wait_for": "技术面突破",
        "earnings_date": "2026-03-25",
        "earnings_desc": "2025年报(全年扣非确认)",
        "base_price": 28.15,
    },
    {
        "code": "600309.SH",
        "name": "万华化学",
        "sector": "MDI",
        "strategy": "等回调企稳做底仓",
        "wait_for": "回调企稳",
        "earnings_date": "2026-03-28",
        "earnings_desc": "2025年报",
        "base_price": 32.68,
    },
]


def generate_mock_data(stock_config):
    """生成模拟K线数据"""
    np.random.seed(hash(stock_config["code"]) % 2**32)
    
    base_price = stock_config["base_price"]
    days = 250
    
    # 生成随机走势
    returns = np.random.normal(0.0005, 0.015, days)
    prices = base_price * np.exp(np.cumsum(returns))
    
    close = prices
    vol = np.random.uniform(50000000, 150000000, days)
    
    # 计算涨跌幅
    prev_close = np.concatenate([[base_price], close[:-1]])
    pct_chg = (close - prev_close) / prev_close * 100
    
    # 构造DataFrame
    class MockDF:
        def __init__(self, close_data, vol_data, pct_data):
            self.data = {
                'close': close_data,
                'vol': vol_data,
                'pct_chg': pct_data,
            }
        
        def __getitem__(self, key):
            if isinstance(key, slice):
                return MockDF(
                    self.data['close'][key],
                    self.data['vol'][key],
                    self.data['pct_chg'][key]
                )
            return self.data[key]
        
        @property
        def iloc(self):
            return self
        
        def __call__(self, index):
            class Row:
                def __init__(self, data, idx):
                    self.data = data
                    self.idx = idx
                
                def __getitem__(self, key):
                    if key == 'pct_chg':
                        return self.data['pct_chg'][self.idx]
                    return self.data[key][self.idx]
                
                def get(self, key, default=None):
                    try:
                        return self[key]
                    except:
                        return default
            
            return Row(self.data, index)
    
    df = MockDF(close, vol, pct_chg)
    df.close = close
    df.vol = vol
    
    return df, None


def analyze_stock(stock_config, daily_df, basic_df):
    """分析单只股票，返回信号"""
    if daily_df is None:
        return None

    close = daily_df.close
    vol = daily_df.vol
    pct_chg = daily_df.data['pct_chg']
    
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
        chg = pct_chg[-1]
        if abs(chg) < 1:
            signals.append("[图] 缩量窄幅震荡(企稳信号)")
            alert_level = max(alert_level, 1)

    # --- 连续下跌后反弹 ---
    if len(pct_chg) >= 5:
        recent_changes = pct_chg[-5:]
        down_days = sum(1 for c in recent_changes if c < 0)
        if down_days >= 4 and pct_chg[-1] > 0:
            signals.append("[图] 连跌后首次收阳(可能企稳)")
            alert_level = max(alert_level, 1)

    # ========== 年报倒计时 ==========
    from datetime import datetime as dt
    earnings_countdown = None
    try:
        ed = dt.strptime(stock_config["earnings_date"], "%Y-%m-%d")
        days_left = (ed - dt.now()).days
        if days_left > 0:
            earnings_countdown = days_left
    except:
        pass

    return {
        "price": price,
        "change_pct": pct_chg[-1],
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "ma20_dir": ma20_dir,
        "vol_ratio": vol_ratio,
        "pe_ttm": round(np.random.uniform(12, 25), 1),
        "pb": round(np.random.uniform(1.5, 3.5), 2),
        "pb_percentile": round(np.random.uniform(20, 80), 1),
        "dv_ttm": round(np.random.uniform(1.5, 3.0), 2),
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
    print("\n" + "="*60)
    print("周期股买点监控脚本 — 模拟测试版")
    print("(用模拟数据演示,无需Tushare Token)")
    print("="*60)
    print(f"\n开始生成模拟数据...\n")

    results = []
    for stock in STOCKS:
        print(f"[{stock['name']}({stock['code']})]")
        daily_df, basic_df = generate_mock_data(stock)
        print(f"  ✓ 模拟数据生成完成")

        r = analyze_stock(stock, daily_df, basic_df)
        results.append(r)

        if r:
            print(f"  ✓ 分析完成 | 股价:{r['price']:.2f} | 信号级别:{r['alert_level']}")
        else:
            print(f"  ✗ 分析失败")
        print()

    # 打印报告
    print_report(results)

    print("\n[完成] 模拟测试报告已生成\n")
    print("提示: 这是模拟数据测试")
    print("如需真实数据,请运行 test_cycle_monitor.py (需要Tushare Token)")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
