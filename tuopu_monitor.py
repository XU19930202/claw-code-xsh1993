"""
拓普集团（601689.SH）估值锚监控系统
======================================
三层业务分拆跟踪：
  第一层：汽车主业 → 核心客户销量 + 单车ASP
  第二层：机器人业务 → Optimus量产节奏 + 定点进展
  第三层：液冷/AIDC → 在手订单 + 云厂商Capex

估值框架：基本盘估值 + 期权估值
  底部支撑 = 汽车业务利润 × 25倍PE
  当前市值 vs 底部支撑 = 安全边际
  溢价部分 = 机器人 + 液冷的期权价值

数据源：tushare(股票), 手动输入(客户销量/季报)
推送：飞书webhook
用法：python tuopu_monitor.py
"""

import tushare as ts
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List

# ========== 配置区 ==========
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"      # 填你的token
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"      # 填你的飞书webhook
TUOPU_CODE = "601689.SH"

# ========== 核心客户配置 ==========
# 每月手动更新（数据来源：乘联会月度批发销量）
# 格式：{月份: 销量（万辆）}
# 这里给的是示例数据，你需要每月更新

CUSTOMER_SALES = {
    "特斯拉中国": {
        "code": "TSLA_CN",
        "weight": 0.30,  # 占拓普汽车收入估算权重
        "monthly": {
            "2025-01": 7.17, "2025-02": 5.49, "2025-03": 8.94,
            "2025-04": 7.21, "2025-05": 7.76, "2025-06": 9.31,
            "2025-07": 7.45, "2025-08": 8.63, "2025-09": 9.25,
            "2025-10": 6.82, "2025-11": 7.31, "2025-12": 8.95,
            "2026-01": 7.85, "2026-02": 6.12,
        },
    },
    "赛力斯(问界)": {
        "code": "AITO",
        "weight": 0.20,
        "monthly": {
            "2025-01": 3.56, "2025-02": 2.18, "2025-03": 4.47,
            "2025-04": 4.56, "2025-05": 4.21, "2025-06": 4.78,
            "2025-07": 4.95, "2025-08": 5.12, "2025-09": 5.34,
            "2025-10": 5.08, "2025-11": 5.23, "2025-12": 5.87,
            "2026-01": 5.45, "2026-02": 3.92,
        },
    },
    "吉利新能源": {
        "code": "GEELY_NEV",
        "weight": 0.18,
        "monthly": {
            "2025-01": 7.82, "2025-02": 5.34, "2025-03": 9.12,
            "2025-04": 8.67, "2025-05": 8.93, "2025-06": 9.45,
            "2025-07": 9.01, "2025-08": 9.56, "2025-09": 10.12,
            "2025-10": 9.34, "2025-11": 9.78, "2025-12": 11.23,
            "2026-01": 9.87, "2026-02": 7.45,
        },
    },
    "比亚迪": {
        "code": "BYD",
        "weight": 0.15,
        "monthly": {
            "2025-01": 30.00, "2025-02": 23.45, "2025-03": 37.89,
            "2025-04": 33.12, "2025-05": 34.56, "2025-06": 38.23,
            "2025-07": 35.67, "2025-08": 37.89, "2025-09": 41.23,
            "2025-10": 50.27, "2025-11": 51.09, "2025-12": 59.48,
            "2026-01": 45.12, "2026-02": 33.78,
        },
    },
    "小米汽车": {
        "code": "XIAOMI",
        "weight": 0.10,
        "monthly": {
            "2025-01": 2.01, "2025-02": 1.58, "2025-03": 2.95,
            "2025-04": 2.87, "2025-05": 2.54, "2025-06": 2.68,
            "2025-07": 2.78, "2025-08": 2.93, "2025-09": 3.01,
            "2025-10": 2.95, "2025-11": 3.12, "2025-12": 3.56,
            "2026-01": 3.21, "2026-02": 2.45,
        },
    },
}

# ========== 季报数据（手动更新）==========
# 每个季报出来后更新一次
QUARTERLY_DATA = {
    "2024Q1": {
        "revenue": 6560,       # 营收（百万元）
        "net_profit": 720,     # 归母净利润（百万元）
        "gross_margin": 20.8,  # 毛利率(%)
        "segments": {
            "减震器": 1050,
            "内饰功能件": 2100,
            "底盘系统": 1850,
            "汽车电子": 480,
            "热管理": 510,
            "电驱系统": 30,
        },
        "overseas_revenue": 1620,   # 海外收入（百万元）
        "robot_revenue": 0,         # 机器人收入
        "liquid_cooling_order": 500, # 液冷在手订单（百万元）
    },
    "2024Q2": {
        "revenue": 7010,
        "net_profit": 810,
        "gross_margin": 21.1,
        "segments": {
            "减震器": 1080,
            "内饰功能件": 2250,
            "底盘系统": 1950,
            "汽车电子": 560,
            "热管理": 540,
            "电驱系统": 35,
        },
        "overseas_revenue": 1750,
        "robot_revenue": 0,
        "liquid_cooling_order": 680,
    },
    "2024Q3": {
        "revenue": 7280,
        "net_profit": 845,
        "gross_margin": 21.3,
        "segments": {
            "减震器": 1100,
            "内饰功能件": 2380,
            "底盘系统": 2010,
            "汽车电子": 620,
            "热管理": 580,
            "电驱系统": 40,
        },
        "overseas_revenue": 1680,
        "robot_revenue": 0,
        "liquid_cooling_order": 900,
    },
    "2024Q4": {
        "revenue": 5750,
        "net_profit": 570,
        "gross_margin": 19.8,
        "segments": {
            "减震器": 890,
            "内饰功能件": 1840,
            "底盘系统": 1590,
            "汽车电子": 520,
            "热管理": 480,
            "电驱系统": 35,
        },
        "overseas_revenue": 1320,
        "robot_revenue": 0,
        "liquid_cooling_order": 1100,
    },
    "2025Q1": {
        "revenue": 5768,
        "net_profit": 566,
        "gross_margin": 19.8,
        "segments": {
            "减震器": 980,
            "内饰功能件": 2050,
            "底盘系统": 1690,
            "汽车电子": 530,
            "热管理": 470,
            "电驱系统": 3,
        },
        "overseas_revenue": 1350,
        "robot_revenue": 0,
        "liquid_cooling_order": 1200,
    },
    "2025Q2": {
        "revenue": 7167,
        "net_profit": 729,
        "gross_margin": 19.28,
        "segments": {
            "减震器": 1060,
            "内饰功能件": 2316,
            "底盘系统": 2018,
            "汽车电子": 745,
            "热管理": 510,
            "电驱系统": 5,
        },
        "overseas_revenue": 1556,
        "robot_revenue": 0,
        "liquid_cooling_order": 1500,
    },
}

# ========== 估值参数 ==========
VALUATION_PARAMS = {
    # 汽车业务
    "auto_pe_low": 20,       # 汽车业务PE下限（纯制造）
    "auto_pe_mid": 25,       # 汽车业务PE中枢
    "auto_pe_high": 30,      # 汽车业务PE上限（含成长溢价）

    # 2026年利润预测（百万元），基于券商一致预期
    "auto_profit_2026": 3200,  # 汽车业务净利润预测
    "robot_profit_2026": 200,  # 机器人业务净利润预测（乐观）
    "robot_profit_2026_bear": 50,  # 机器人悲观
    "liqcool_profit_2026": 150,  # 液冷业务净利润预测

    # 机器人估值
    "robot_pe": 50,          # 机器人业务给的PE（高成长）

    # 总股本（亿股）
    "total_shares": 17.36,
}

# ========== Optimus里程碑事件跟踪 ==========
OPTIMUS_MILESTONES = [
    {"event": "Gen2在特斯拉工厂部署测试", "expected": "2025Q3", "status": "已完成"},
    {"event": "Gen3发布", "expected": "2026Q1", "status": "待确认"},
    {"event": "Gen3批量定点（含拓普执行器）", "expected": "2026Q1-Q2", "status": "待确认"},
    {"event": "Gen3小批量产（月产百台级）", "expected": "2026H2", "status": "未开始"},
    {"event": "Gen3规模量产（月产千台级）", "expected": "2027H1", "status": "未开始"},
    {"event": "拓普机器人业务收入确认", "expected": "2026Q3-Q4", "status": "未开始"},
]


def get_stock_price(pro, ts_code=TUOPU_CODE):
    """获取拓普最新股价和基本估值数据"""
    try:
        # 最新日线
        df = pro.daily(ts_code=ts_code, start_date=(
            datetime.now() - timedelta(days=10)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"))
        if df.empty:
            return None
        latest = df.iloc[0]

        # 基本面数据
        basic = pro.daily_basic(ts_code=ts_code, start_date=(
            datetime.now() - timedelta(days=10)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"))

        result = {
            "date": latest["trade_date"],
            "close": latest["close"],
            "pct_chg": latest["pct_chg"],
        }

        if not basic.empty:
            result["pe_ttm"] = basic.iloc[0].get("pe_ttm", None)
            result["total_mv"] = basic.iloc[0].get("total_mv", None)  # 总市值（万元）

        return result
    except Exception as e:
        print(f"获取股价失败: {e}")
        return None


def analyze_customer_sales():
    """分析核心客户销量趋势"""
    results = {}

    for name, cfg in CUSTOMER_SALES.items():
        monthly = cfg["monthly"]
        if len(monthly) < 3:
            continue

        # 按月份排序
        sorted_months = sorted(monthly.keys())

        # 最近3个月 vs 去年同期
        recent_3 = sorted_months[-3:]
        recent_sum = sum(monthly[m] for m in recent_3)

        # 找去年同期
        yoy_months = []
        for m in recent_3:
            year, mon = m.split("-")
            last_year_m = f"{int(year)-1}-{mon}"
            if last_year_m in monthly:
                yoy_months.append(last_year_m)

        if yoy_months:
            yoy_sum = sum(monthly[m] for m in yoy_months)
            yoy_growth = (recent_sum - yoy_sum) / yoy_sum * 100
        else:
            yoy_growth = None

        # 环比趋势（最近月 vs 上月）
        if len(sorted_months) >= 2:
            mom = (monthly[sorted_months[-1]] - monthly[sorted_months[-2]]) / \
                  monthly[sorted_months[-2]] * 100
        else:
            mom = None

        results[name] = {
            "latest_month": sorted_months[-1],
            "latest_sales": monthly[sorted_months[-1]],
            "recent_3m_sum": recent_sum,
            "yoy_growth": yoy_growth,
            "mom_growth": mom,
            "weight": cfg["weight"],
        }

    # 加权综合增速
    weighted_yoy = 0
    total_weight = 0
    for name, r in results.items():
        if r["yoy_growth"] is not None:
            weighted_yoy += r["yoy_growth"] * r["weight"]
            total_weight += r["weight"]

    if total_weight > 0:
        weighted_yoy /= total_weight

    return results, weighted_yoy


def analyze_quarterly_trend():
    """分析季报趋势"""
    quarters = sorted(QUARTERLY_DATA.keys())
    if len(quarters) < 2:
        return None

    latest_q = quarters[-1]
    prev_q = quarters[-2]
    latest = QUARTERLY_DATA[latest_q]
    prev = QUARTERLY_DATA[prev_q]

    # 同比（找去年同季度）
    year = latest_q[:4]
    q_num = latest_q[5:]
    yoy_q = f"{int(year)-1}{q_num}"
    yoy_data = QUARTERLY_DATA.get(yoy_q)

    result = {
        "latest_quarter": latest_q,
        "revenue": latest["revenue"],
        "net_profit": latest["net_profit"],
        "gross_margin": latest["gross_margin"],
        "overseas_pct": latest["overseas_revenue"] / latest["revenue"] * 100,
        "robot_revenue": latest.get("robot_revenue", 0),
        "liqcool_order": latest.get("liquid_cooling_order", 0),
    }

    # 环比
    result["revenue_qoq"] = (latest["revenue"] - prev["revenue"]) / prev["revenue"] * 100
    result["profit_qoq"] = (latest["net_profit"] - prev["net_profit"]) / prev["net_profit"] * 100
    result["margin_qoq"] = latest["gross_margin"] - prev["gross_margin"]

    # 同比
    if yoy_data:
        result["revenue_yoy"] = (latest["revenue"] - yoy_data["revenue"]) / yoy_data["revenue"] * 100
        result["profit_yoy"] = (latest["net_profit"] - yoy_data["net_profit"]) / yoy_data["net_profit"] * 100
        result["margin_yoy"] = latest["gross_margin"] - yoy_data["gross_margin"]

    # 汽车电子增速（核心观察指标）
    if "汽车电子" in latest["segments"] and yoy_data and "汽车电子" in yoy_data["segments"]:
        auto_elec_now = latest["segments"]["汽车电子"]
        auto_elec_yoy = yoy_data["segments"]["汽车电子"]
        result["auto_elec_yoy"] = (auto_elec_now - auto_elec_yoy) / auto_elec_yoy * 100
    else:
        result["auto_elec_yoy"] = None

    # 毛利率连续下滑检测（预警信号）
    margin_trend = [QUARTERLY_DATA[q]["gross_margin"] for q in quarters[-4:]]
    consecutive_decline = 0
    for i in range(len(margin_trend) - 1, 0, -1):
        if margin_trend[i] < margin_trend[i - 1]:
            consecutive_decline += 1
        else:
            break
    result["margin_decline_quarters"] = consecutive_decline

    return result


def calculate_valuation(stock_data):
    """
    计算分部估值和安全边际
    核心逻辑：
      底部支撑 = 汽车业务利润 × 25倍PE
      合理估值 = 汽车 + 机器人(乐观) + 液冷
      当前市值 vs 底部/合理 = 安全边际
    """
    p = VALUATION_PARAMS

    # 汽车业务估值区间
    auto_low = p["auto_profit_2026"] * p["auto_pe_low"] / 100  # 亿元
    auto_mid = p["auto_profit_2026"] * p["auto_pe_mid"] / 100
    auto_high = p["auto_profit_2026"] * p["auto_pe_high"] / 100

    # 机器人业务估值
    robot_bull = p["robot_profit_2026"] * p["robot_pe"] / 100
    robot_bear = p["robot_profit_2026_bear"] * p["robot_pe"] / 100

    # 液冷业务（给30倍PE）
    liqcool = p["liqcool_profit_2026"] * 30 / 100

    # 总估值区间
    floor_mv = auto_low  # 纯汽车底部，亿元
    bear_mv = auto_mid + robot_bear + liqcool  # 保守
    base_mv = auto_mid + robot_bull + liqcool   # 中性
    bull_mv = auto_high + robot_bull + liqcool   # 乐观

    # 对应股价
    floor_price = floor_mv * 10000 / (p["total_shares"] * 10000)  # 元/股
    bear_price = bear_mv * 10000 / (p["total_shares"] * 10000)
    base_price = base_mv * 10000 / (p["total_shares"] * 10000)
    bull_price = bull_mv * 10000 / (p["total_shares"] * 10000)

    result = {
        "floor_mv": floor_mv,     # 底部市值（亿）
        "bear_mv": bear_mv,       # 保守市值
        "base_mv": base_mv,       # 中性市值
        "bull_mv": bull_mv,       # 乐观市值
        "floor_price": floor_price,
        "bear_price": bear_price,
        "base_price": base_price,
        "bull_price": bull_price,
    }

    if stock_data and stock_data.get("total_mv"):
        current_mv = stock_data["total_mv"] / 10000  # 万元→亿元
        result["current_mv"] = current_mv
        result["vs_floor"] = (current_mv - floor_mv) / floor_mv * 100
        result["vs_base"] = (current_mv - base_mv) / base_mv * 100
        result["robot_premium_pct"] = (current_mv - auto_mid) / current_mv * 100

    return result


def format_report(stock_data, customer_analysis, weighted_yoy,
                  quarterly, valuation):
    """生成飞书推送文本"""
    lines = []
    lines.append(f"📊 拓普集团（601689）估值锚监控")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ===== 股价和估值概览 =====
    if stock_data:
        lines.append("")
        lines.append(f"═══ 市场数据 ═══")
        lines.append(f"  股价: {stock_data['close']:.2f}元  "
                     f"涨跌: {stock_data['pct_chg']:+.2f}%")
        if stock_data.get("pe_ttm"):
            lines.append(f"  PE(TTM): {stock_data['pe_ttm']:.1f}x")
        if stock_data.get("total_mv"):
            lines.append(f"  总市值: {stock_data['total_mv']/10000:.0f}亿元")

    # ===== 估值安全边际 =====
    if valuation:
        lines.append("")
        lines.append(f"═══ 分部估值 (基于2026E) ═══")
        lines.append(f"  底部(纯汽车): {valuation['floor_mv']:.0f}亿 → "
                     f"{valuation['floor_price']:.1f}元/股")
        lines.append(f"  保守(汽车+机器人悲观+液冷): {valuation['bear_mv']:.0f}亿 → "
                     f"{valuation['bear_price']:.1f}元/股")
        lines.append(f"  中性(汽车+机器人乐观+液冷): {valuation['base_mv']:.0f}亿 → "
                     f"{valuation['base_price']:.1f}元/股")
        lines.append(f"  乐观: {valuation['bull_mv']:.0f}亿 → "
                     f"{valuation['bull_price']:.1f}元/股")

        if "current_mv" in valuation:
            lines.append(f"  ──")
            premium = valuation["vs_floor"]
            if premium < 10:
                signal = "🔴 接近纯汽车底部，安全边际充足"
            elif premium < 30:
                signal = "🟡 机器人溢价较低，可关注"
            elif premium < 60:
                signal = "🟢 估值中性，机器人预期部分兑现"
            else:
                signal = "⚪ 机器人溢价充分，注意风险"
            lines.append(f"  当前 vs 底部: +{premium:.0f}%  {signal}")
            if "robot_premium_pct" in valuation:
                lines.append(f"  机器人+液冷溢价占比: {valuation['robot_premium_pct']:.0f}%")

    # ===== 核心客户销量 =====
    lines.append("")
    lines.append(f"═══ 核心客户销量跟踪 ═══")
    for name, r in customer_analysis.items():
        yoy_str = f"同比{r['yoy_growth']:+.1f}%" if r["yoy_growth"] else "无同比"
        mom_str = f"环比{r['mom_growth']:+.1f}%" if r["mom_growth"] else ""
        lines.append(f"  {name}: {r['latest_month']}月 "
                     f"{r['latest_sales']:.2f}万辆 {yoy_str} {mom_str}")
    lines.append(f"  ── 加权综合同比: {weighted_yoy:+.1f}% "
                 f"{'↑' if weighted_yoy > 0 else '↓'}")

    # ===== 季报趋势 =====
    if quarterly:
        lines.append("")
        lines.append(f"═══ 最新季报: {quarterly['latest_quarter']} ═══")
        lines.append(f"  营收: {quarterly['revenue']:.0f}百万 "
                     f"环比{quarterly['revenue_qoq']:+.1f}%"
                     + (f" 同比{quarterly.get('revenue_yoy', 0):+.1f}%"
                        if "revenue_yoy" in quarterly else ""))
        lines.append(f"  净利润: {quarterly['net_profit']:.0f}百万 "
                     f"环比{quarterly['profit_qoq']:+.1f}%")
        lines.append(f"  毛利率: {quarterly['gross_margin']:.2f}%  "
                     f"环比{quarterly['margin_qoq']:+.2f}pct")
        lines.append(f"  海外收入占比: {quarterly['overseas_pct']:.1f}%")

        if quarterly.get("auto_elec_yoy") is not None:
            lines.append(f"  ⚡ 汽车电子同比: {quarterly['auto_elec_yoy']:+.1f}% "
                         f"{'🔥' if quarterly['auto_elec_yoy'] > 30 else ''}")

        # 毛利率预警
        if quarterly["margin_decline_quarters"] >= 3:
            lines.append(f"  ⚠️ 毛利率连续{quarterly['margin_decline_quarters']}个季度下滑!")
        elif quarterly["margin_decline_quarters"] >= 2:
            lines.append(f"  🟡 毛利率连续{quarterly['margin_decline_quarters']}个季度下滑，需关注")

        # 机器人收入
        if quarterly["robot_revenue"] > 0:
            lines.append(f"  🤖 机器人收入: {quarterly['robot_revenue']:.0f}百万 ← 关键拐点!")
        else:
            lines.append(f"  🤖 机器人收入: 尚未确认")

        lines.append(f"  🧊 液冷在手订单: {quarterly['liqcool_order']:.0f}百万")

    # ===== Optimus里程碑 =====
    lines.append("")
    lines.append(f"═══ Optimus量产里程碑 ═══")
    for ms in OPTIMUS_MILESTONES:
        icon = "✅" if ms["status"] == "已完成" else "⏳" if ms["status"] == "待确认" else "⬜"
        lines.append(f"  {icon} {ms['event']} ({ms['expected']}) - {ms['status']}")

    # ===== 操作建议 =====
    lines.append("")
    lines.append(f"═══ 操作框架 ═══")
    if valuation and "current_mv" in valuation:
        premium = valuation["vs_floor"]
        if premium < 10:
            lines.append(f"  🔴 股价接近纯汽车估值底部")
            lines.append(f"  → 机器人期权接近免费，安全边际高")
            lines.append(f"  → 可建标准仓位")
        elif premium < 30:
            lines.append(f"  🟡 机器人溢价偏低")
            lines.append(f"  → 若Optimus定点确认，有估值修复空间")
            lines.append(f"  → 可建底仓，等催化事件加仓")
        elif premium < 60:
            lines.append(f"  🟢 估值合理区间")
            lines.append(f"  → 持仓观察，季报交叉验证")
            lines.append(f"  → 不加仓不减仓")
        else:
            lines.append(f"  ⚪ 机器人预期充分定价")
            lines.append(f"  → 需要Optimus量产超预期才能继续上涨")
            lines.append(f"  → 考虑减仓锁定利润")

    lines.append("")
    lines.append(f"─────────────────")
    lines.append(f"核心跟踪: 客户月销量→季报ASP→Optimus节点→毛利率趋势")
    lines.append(f"买点: 股价跌至纯汽车估值附近（机器人溢价被杀光）")
    lines.append(f"卖点: 机器人量产不及预期 或 毛利率连续3季下滑")

    return "\n".join(lines)


def push_to_feishu(content: str, webhook: str):
    """推送到飞书"""
    if not webhook:
        return
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200:
            print("飞书推送成功")
        else:
            print(f"飞书推送失败: {resp.status_code}")
    except Exception as e:
        print(f"飞书推送异常: {e}")


def main():
    print("拓普集团估值锚监控系统")
    print("=" * 50)

    # 获取股价
    stock_data = None
    if TUSHARE_TOKEN:
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
        stock_data = get_stock_price(pro)
    else:
        print("未配置TUSHARE_TOKEN，跳过股价获取")

    # 分析客户销量
    customer_analysis, weighted_yoy = analyze_customer_sales()

    # 分析季报趋势
    quarterly = analyze_quarterly_trend()

    # 计算估值
    valuation = calculate_valuation(stock_data)

    # 生成报告
    report = format_report(stock_data, customer_analysis, weighted_yoy,
                           quarterly, valuation)
    print()
    print(report)

    # 推送飞书
    push_to_feishu(report, FEISHU_WEBHOOK)


if __name__ == "__main__":
    main()
