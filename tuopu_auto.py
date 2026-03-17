"""
拓普集团（601689）全自动估值锚监控
====================================
数据源：
  - 股价/财务/估值: Tushare Pro
  - 客户销量: AKShare (盖世汽车/乘联会)
  - 一致预期: 东方财富网页爬取
  - 机构持仓: Tushare 十大流通股东

全部自动获取，无需手动输入。
用法: python tuopu_auto.py
建议cron: 每周五收盘后跑一次
"""

import tushare as ts
import akshare as ak
import pandas as pd
import numpy as np
import requests
import json
import re
import time
import sys
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 配置区 ==========
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"       # 填你的token
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"       # 填你的飞书webhook
TUOPU_CODE = "601689.SH"
TUOPU_CODE_EM = "601689"  # 东方财富用的代码格式
TOTAL_SHARES = 17.36      # 总股本（亿股），半年报后核对一次

# 估值参数
AUTO_PE_LOW = 20          # 纯汽车业务PE下限
AUTO_PE_MID = 25          # 中枢
AUTO_PE_HIGH = 30         # 上限
ROBOT_PE = 50             # 机器人业务PE

# Optimus 里程碑（手动维护，有新闻时更新）
OPTIMUS_MILESTONES = [
    {"event": "Gen2工厂部署测试", "expected": "2025Q3", "status": "已完成"},
    {"event": "Gen3发布", "expected": "2026Q1", "status": "待确认"},
    {"event": "Gen3批量定点", "expected": "2026Q1-Q2", "status": "待确认"},
    {"event": "Gen3小批量产(百台级)", "expected": "2026H2", "status": "未开始"},
    {"event": "拓普机器人收入确认", "expected": "2026Q3-Q4", "status": "未开始"},
]
# =============================


# ============================================================
#  第一部分：股价与基本估值（Tushare）
# ============================================================
def get_stock_data(pro):
    """获取拓普最新股价、PE、总市值"""
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")

        df = pro.daily(ts_code=TUOPU_CODE, start_date=start, end_date=end)
        basic = pro.daily_basic(ts_code=TUOPU_CODE, start_date=start, end_date=end)

        if df.empty:
            return None

        latest = df.iloc[0]
        result = {
            "date": latest["trade_date"],
            "close": latest["close"],
            "pct_chg": latest["pct_chg"],
        }
        if not basic.empty:
            result["pe_ttm"] = basic.iloc[0].get("pe_ttm")
            result["pb"] = basic.iloc[0].get("pb")
            result["total_mv"] = basic.iloc[0].get("total_mv")  # 万元

        return result
    except Exception as e:
        print(f"  [股价] 获取失败: {e}")
        return None


# ============================================================
#  第二部分：核心客户月销量（AKShare）
# ============================================================
def get_customer_sales():
    """
    通过AKShare获取盖世汽车月度厂商销量排行
    自动提取拓普5大客户的最新月度数据
    """
    # 拓普核心客户关键词 → 权重
    customers = {
        "特斯拉": {"weight": 0.30, "keywords": ["特斯拉"]},
        "比亚迪": {"weight": 0.15, "keywords": ["比亚迪"]},
        "吉利汽车": {"weight": 0.18, "keywords": ["吉利"]},
        "赛力斯": {"weight": 0.20, "keywords": ["赛力斯"]},
        "小米汽车": {"weight": 0.10, "keywords": ["小米"]},
    }

    results = {}

    # 尝试拉最近两个月的数据做环比
    now = datetime.now()
    months_to_try = []
    for i in range(1, 4):  # 往前找3个月
        dt = now - timedelta(days=30 * i)
        months_to_try.append(dt.strftime("%Y%m"))

    monthly_data = {}
    for month_str in months_to_try:
        try:
            df = ak.car_sale_rank_gasgoo(symbol="品牌榜", date=month_str)
            if df is not None and not df.empty:
                monthly_data[month_str] = df
                time.sleep(0.5)
        except Exception as e:
            print(f"  [销量] {month_str} 获取失败: {e}")
            continue

    if not monthly_data:
        # 回退：尝试乘联会厂商排名
        try:
            df = ak.car_market_man_rank_cpca(symbol="狭义乘用车-单月", indicator="零售")
            if df is not None and not df.empty:
                print("  [销量] 使用乘联会数据")
                # 乘联会数据格式不同，提取最近两列
                cols = [c for c in df.columns if c != "厂商"]
                if len(cols) >= 2:
                    latest_col = cols[-1]
                    prev_col = cols[-2]
                    for name, cfg in customers.items():
                        for _, row in df.iterrows():
                            manufacturer = str(row.get("厂商", ""))
                            if any(kw in manufacturer for kw in cfg["keywords"]):
                                latest_val = pd.to_numeric(row[latest_col], errors="coerce")
                                prev_val = pd.to_numeric(row[prev_col], errors="coerce")
                                if pd.notna(latest_val):
                                    mom = ((latest_val - prev_val) / prev_val * 100
                                           if pd.notna(prev_val) and prev_val > 0 else None)
                                    results[name] = {
                                        "month": latest_col,
                                        "sales": latest_val,
                                        "mom": mom,
                                        "weight": cfg["weight"],
                                        "source": "乘联会",
                                    }
                                break
                return results
        except Exception as e:
            print(f"  [销量] 乘联会数据也获取失败: {e}")
            return results

    # 处理盖世汽车数据
    sorted_months = sorted(monthly_data.keys(), reverse=True)
    latest_month = sorted_months[0]
    prev_month = sorted_months[1] if len(sorted_months) > 1 else None
    latest_df = monthly_data[latest_month]
    prev_df = monthly_data[prev_month] if prev_month else None

    for name, cfg in customers.items():
        for _, row in latest_df.iterrows():
            manufacturer = str(row.iloc[0]) if len(row) > 0 else ""
            if any(kw in manufacturer for kw in cfg["keywords"]):
                # 提取销量（取第二列，通常是当月销量）
                sales_col = latest_df.columns[1]
                latest_sales = pd.to_numeric(row[sales_col], errors="coerce")

                # 找上月同厂商数据
                mom = None
                if prev_df is not None:
                    for _, prev_row in prev_df.iterrows():
                        prev_mfr = str(prev_row.iloc[0]) if len(prev_row) > 0 else ""
                        if any(kw in prev_mfr for kw in cfg["keywords"]):
                            prev_sales_col = prev_df.columns[1]
                            prev_sales = pd.to_numeric(prev_row[prev_sales_col], errors="coerce")
                            if pd.notna(prev_sales) and prev_sales > 0:
                                mom = (latest_sales - prev_sales) / prev_sales * 100
                            break

                if pd.notna(latest_sales):
                    results[name] = {
                        "month": latest_month,
                        "sales": latest_sales,
                        "mom": mom,
                        "weight": cfg["weight"],
                        "source": "盖世汽车",
                    }
                break

    return results


# ============================================================
#  第三部分：季报财务数据（Tushare）
# ============================================================
def get_financial_data(pro):
    """获取拓普最近几个季度的财务数据"""
    try:
        # 利润表
        income = pro.income(ts_code=TUOPU_CODE, fields=(
            "ann_date,f_ann_date,end_date,revenue,n_income_attr_p,"
            "basic_eps,operate_profit"
        ))
        if income.empty:
            return None

        income = income.sort_values("end_date", ascending=False).head(8)
        income["revenue"] = income["revenue"] / 1e6       # 转百万
        income["net_profit"] = income["n_income_attr_p"] / 1e6

        # 主营构成（分业务）
        segments = {}
        try:
            mainbz = pro.fina_mainbz(ts_code=TUOPU_CODE, type="P")  # P=产品
            if not mainbz.empty:
                latest_period = mainbz["end_date"].max()
                latest_bz = mainbz[mainbz["end_date"] == latest_period]
                for _, row in latest_bz.iterrows():
                    bz_name = row.get("bz_item", "未知")
                    bz_revenue = row.get("bz_sales", 0) / 1e6
                    segments[bz_name] = bz_revenue
        except Exception:
            pass

        # 财务指标
        indicators = pro.fina_indicator(ts_code=TUOPU_CODE, fields=(
            "end_date,grossprofit_margin,netprofit_margin,roe,"
            "ocfps,extra_item"
        ))

        # 组装结果
        quarters = []
        for _, row in income.iterrows():
            q = {
                "end_date": row["end_date"],
                "revenue": row["revenue"],
                "net_profit": row["net_profit"],
            }
            # 匹配毛利率
            if not indicators.empty:
                match = indicators[indicators["end_date"] == row["end_date"]]
                if not match.empty:
                    q["gross_margin"] = match.iloc[0].get("grossprofit_margin")
                    q["roe"] = match.iloc[0].get("roe")
            quarters.append(q)

        return {
            "quarters": quarters,
            "segments": segments,
        }
    except Exception as e:
        print(f"  [财务] 获取失败: {e}")
        return None


def analyze_financials(fin_data):
    """分析财务趋势"""
    if not fin_data or not fin_data["quarters"]:
        return None

    quarters = fin_data["quarters"]
    latest = quarters[0]

    result = {
        "latest_period": latest["end_date"],
        "revenue": latest["revenue"],
        "net_profit": latest["net_profit"],
        "gross_margin": latest.get("gross_margin"),
        "segments": fin_data.get("segments", {}),
    }

    # 计算单季度数据（累计值转单季）
    # end_date格式 20250630 → Q2
    period = latest["end_date"]
    month = period[4:6]
    if month == "03":
        result["quarter_label"] = f"{period[:4]}Q1"
        result["q_revenue"] = latest["revenue"]
        result["q_profit"] = latest["net_profit"]
    elif len(quarters) >= 2:
        result["q_revenue"] = latest["revenue"] - quarters[1]["revenue"] if quarters[1]["end_date"][:4] == period[:4] else latest["revenue"]
        result["q_profit"] = latest["net_profit"] - quarters[1]["net_profit"] if quarters[1]["end_date"][:4] == period[:4] else latest["net_profit"]
        q_map = {"06": "Q2", "09": "Q3", "12": "Q4"}
        result["quarter_label"] = f"{period[:4]}{q_map.get(month, '')}"

    # 毛利率趋势
    margins = [q.get("gross_margin") for q in quarters[:6] if q.get("gross_margin")]
    if len(margins) >= 3:
        decline_count = 0
        for i in range(len(margins) - 1):
            if margins[i] < margins[i + 1]:  # 注意quarters是倒序
                decline_count += 1
            else:
                break
        result["margin_decline_quarters"] = decline_count
    else:
        result["margin_decline_quarters"] = 0

    # 同比（找去年同期）
    for q in quarters[1:]:
        if q["end_date"][4:] == period[4:] and q["end_date"][:4] != period[:4]:
            if q["revenue"] > 0:
                result["revenue_yoy"] = (latest["revenue"] - q["revenue"]) / q["revenue"] * 100
            if q["net_profit"] > 0:
                result["profit_yoy"] = (latest["net_profit"] - q["net_profit"]) / q["net_profit"] * 100
            break

    return result


# ============================================================
#  第四部分：一致预期（东方财富网页爬取）
# ============================================================
def get_consensus_estimates():
    """
    爬取东方财富个股盈利预测页面
    获取券商一致预期净利润
    """
    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/ProfitForecast/ProfitForecastAjax?code=SH{TUOPU_CODE_EM}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://emweb.securities.eastmoney.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            # 备用URL格式
            url2 = f"https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_PROFIT_FORECAST&sty=ALL&filter=(SECURITY_CODE%3D%22{TUOPU_CODE_EM}%22)"
            resp = requests.get(url2, headers=headers, timeout=10)

        data = resp.json()

        # 尝试解析不同格式
        estimates = {}

        if isinstance(data, dict):
            # 格式1: ProfitForecastAjax
            if "Result" in data and "ProfitForecast" in data.get("Result", {}):
                forecasts = data["Result"]["ProfitForecast"]
                for item in forecasts:
                    year = item.get("ndate", "")[:4]
                    profit = item.get("jlr")  # 净利润（万元）
                    if year and profit:
                        estimates[year] = {
                            "net_profit": float(profit) / 10000,  # 万→亿
                            "eps": item.get("mgsy"),
                            "pe_forecast": item.get("sjl"),
                            "analyst_count": item.get("jg"),
                        }

            # 格式2: datacenter API
            elif "result" in data and "data" in data.get("result", {}):
                for item in data["result"]["data"]:
                    year = str(item.get("PREDICT_YEAR", ""))
                    profit = item.get("PREDICT_NET_PROFIT")
                    if year and profit:
                        estimates[year] = {
                            "net_profit": float(profit) / 1e8,  # 元→亿
                            "eps": item.get("PREDICT_EPS"),
                            "analyst_count": item.get("PREDICT_ORG_NUM"),
                        }

        return estimates if estimates else None

    except Exception as e:
        print(f"  [一致预期] 东方财富接口失败: {e}")
        # 备用方案：直接爬网页
        try:
            page_url = f"https://data.eastmoney.com/report/{TUOPU_CODE_EM}.html"
            resp2 = requests.get(page_url, headers=headers, timeout=10)
            # 简单提取页面中的预测数据
            # 如果这也失败，返回None
            return None
        except Exception:
            return None


# ============================================================
#  第五部分：机构持仓变动（Tushare）
# ============================================================
def get_institutional_holdings(pro):
    """获取十大流通股东变动"""
    try:
        holders = pro.top10_floatholders(ts_code=TUOPU_CODE)
        if holders.empty:
            return None

        # 最近两期
        periods = holders["end_date"].unique()[:2]
        if len(periods) < 2:
            return {"latest_period": periods[0], "changes": []}

        latest = holders[holders["end_date"] == periods[0]]
        prev = holders[holders["end_date"] == periods[1]]

        # 找基金/机构持仓变化
        changes = []
        for _, row in latest.iterrows():
            name = row["holder_name"]
            hold_amount = row["hold_amount"]
            # 找上期
            prev_match = prev[prev["holder_name"] == name]
            if not prev_match.empty:
                prev_amount = prev_match.iloc[0]["hold_amount"]
                change = hold_amount - prev_amount
                if abs(change) > 0:
                    changes.append({
                        "name": name,
                        "amount": hold_amount,
                        "change": change,
                        "change_pct": change / prev_amount * 100 if prev_amount > 0 else 0,
                    })
            else:
                # 新进
                changes.append({
                    "name": name,
                    "amount": hold_amount,
                    "change": hold_amount,
                    "change_pct": 999,  # 新进标记
                })

        # 按变动量排序
        changes.sort(key=lambda x: abs(x["change"]), reverse=True)

        return {
            "latest_period": periods[0],
            "prev_period": periods[1],
            "changes": changes[:5],  # 前5大变动
        }
    except Exception as e:
        print(f"  [持仓] 获取失败: {e}")
        return None


# ============================================================
#  第六部分：估值计算
# ============================================================
def calculate_valuation(stock_data, estimates):
    """
    分部估值:
      底部 = 汽车利润 × 低PE
      中性 = 汽车利润 × 中PE + 机器人 + 液冷
      当前市值 vs 底部 = 安全边际
    """
    # 优先用一致预期，否则用默认值
    if estimates:
        # 找2026年或最近一年的预测
        for year in ["2026", "2027", "2025"]:
            if year in estimates:
                consensus_profit = estimates[year]["net_profit"]  # 亿元
                consensus_year = year
                break
        else:
            consensus_profit = 37  # 默认值（亿）
            consensus_year = "2026E"
    else:
        consensus_profit = 37
        consensus_year = "2026E(默认)"

    # 假设汽车业务占总利润的85-90%
    auto_profit = consensus_profit * 0.88
    robot_profit_bull = consensus_profit * 0.05   # 乐观：5%来自机器人
    robot_profit_bear = 0                          # 悲观：机器人还没贡献
    liqcool_profit = consensus_profit * 0.07       # 液冷：7%

    # 汽车业务估值区间
    floor_mv = auto_profit * AUTO_PE_LOW       # 纯汽车底部
    bear_mv = auto_profit * AUTO_PE_MID + liqcool_profit * 30
    base_mv = auto_profit * AUTO_PE_MID + robot_profit_bull * ROBOT_PE + liqcool_profit * 30
    bull_mv = auto_profit * AUTO_PE_HIGH + robot_profit_bull * ROBOT_PE + liqcool_profit * 35

    result = {
        "consensus_profit": consensus_profit,
        "consensus_year": consensus_year,
        "auto_profit": auto_profit,
        "floor_mv": floor_mv,
        "bear_mv": bear_mv,
        "base_mv": base_mv,
        "bull_mv": bull_mv,
        "floor_price": floor_mv / TOTAL_SHARES,
        "bear_price": bear_mv / TOTAL_SHARES,
        "base_price": base_mv / TOTAL_SHARES,
        "bull_price": bull_mv / TOTAL_SHARES,
    }

    if stock_data and stock_data.get("total_mv"):
        current_mv = stock_data["total_mv"] / 10000  # 万元→亿元
        result["current_mv"] = current_mv
        result["vs_floor"] = (current_mv - floor_mv) / floor_mv * 100
        result["vs_base"] = (current_mv - base_mv) / base_mv * 100
        result["robot_premium_pct"] = max(0, (current_mv - auto_profit * AUTO_PE_MID) / current_mv * 100)

    return result


# ============================================================
#  第七部分：报告生成与推送
# ============================================================
def format_report(stock, sales, financials, estimates, holdings, valuation):
    """生成飞书推送文本"""
    lines = []
    lines.append(f"📊 拓普集团(601689) 全自动估值监控")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ── 股价 ──
    if stock:
        lines.append("")
        lines.append(f"═══ 市场数据 ═══")
        lines.append(f"  股价: {stock['close']:.2f}  涨跌: {stock['pct_chg']:+.2f}%")
        if stock.get("pe_ttm"):
            lines.append(f"  PE(TTM): {stock['pe_ttm']:.1f}x  "
                         f"PB: {stock.get('pb', 0):.2f}x")
        if stock.get("total_mv"):
            lines.append(f"  总市值: {stock['total_mv']/10000:.0f}亿")

    # ── 估值 ──
    if valuation:
        lines.append("")
        lines.append(f"═══ 分部估值 ({valuation['consensus_year']}) ═══")
        lines.append(f"  一致预期净利润: {valuation['consensus_profit']:.1f}亿"
                     f" (汽车{valuation['auto_profit']:.1f}亿)")
        lines.append(f"  底部(纯汽车{AUTO_PE_LOW}x): "
                     f"{valuation['floor_mv']:.0f}亿 → {valuation['floor_price']:.1f}元")
        lines.append(f"  保守(汽车+液冷): "
                     f"{valuation['bear_mv']:.0f}亿 → {valuation['bear_price']:.1f}元")
        lines.append(f"  中性(+机器人): "
                     f"{valuation['base_mv']:.0f}亿 → {valuation['base_price']:.1f}元")
        lines.append(f"  乐观: "
                     f"{valuation['bull_mv']:.0f}亿 → {valuation['bull_price']:.1f}元")

        if "current_mv" in valuation:
            premium = valuation["vs_floor"]
            if premium < 10:
                signal = "🔴 接近纯汽车底部，机器人期权接近免费"
            elif premium < 30:
                signal = "🟡 机器人溢价偏低，可关注"
            elif premium < 60:
                signal = "🟢 估值中性"
            else:
                signal = "⚪ 机器人预期充分定价"
            lines.append(f"  当前vs底部: +{premium:.0f}%  {signal}")
            lines.append(f"  机器人+液冷溢价: {valuation.get('robot_premium_pct', 0):.0f}%")

    # ── 一致预期明细 ──
    if estimates:
        lines.append("")
        lines.append(f"═══ 券商一致预期 ═══")
        for year in sorted(estimates.keys()):
            e = estimates[year]
            profit_str = f"{e['net_profit']:.1f}亿" if e["net_profit"] else "N/A"
            eps_str = f"EPS={e.get('eps', 'N/A')}"
            org_str = f"{e.get('analyst_count', '?')}家机构"
            lines.append(f"  {year}E: 净利润{profit_str}  {eps_str}  ({org_str})")

    # ── 客户销量 ──
    if sales:
        lines.append("")
        lines.append(f"═══ 核心客户月销量 ═══")
        weighted_mom = 0
        total_w = 0
        for name, s in sales.items():
            mom_str = f"环比{s['mom']:+.1f}%" if s.get("mom") is not None else ""
            lines.append(f"  {name}: {s['sales']:.2f}万辆 {mom_str}"
                         f"  [{s.get('source', '')}]")
            if s.get("mom") is not None:
                weighted_mom += s["mom"] * s["weight"]
                total_w += s["weight"]
        if total_w > 0:
            lines.append(f"  加权环比: {weighted_mom/total_w:+.1f}%")

    # ── 财务趋势 ──
    if financials:
        lines.append("")
        lines.append(f"═══ 财务数据 ({financials.get('quarter_label', financials['latest_period'])}) ═══")
        lines.append(f"  累计营收: {financials['revenue']:.0f}百万  "
                     f"净利润: {financials['net_profit']:.0f}百万")
        if financials.get("revenue_yoy") is not None:
            lines.append(f"  营收同比: {financials['revenue_yoy']:+.1f}%  "
                         f"利润同比: {financials.get('profit_yoy', 0):+.1f}%")
        if financials.get("gross_margin"):
            lines.append(f"  毛利率: {financials['gross_margin']:.1f}%")

        if financials["margin_decline_quarters"] >= 3:
            lines.append(f"  ⚠️ 毛利率连续{financials['margin_decline_quarters']}季下滑!")
        elif financials["margin_decline_quarters"] >= 2:
            lines.append(f"  🟡 毛利率连续{financials['margin_decline_quarters']}季下滑")

        # 分业务
        if financials.get("segments"):
            lines.append(f"  ── 分业务(最新报告期) ──")
            segs = sorted(financials["segments"].items(), key=lambda x: x[1], reverse=True)
            for name, rev in segs[:6]:
                lines.append(f"    {name}: {rev:.0f}百万")

    # ── 机构持仓 ──
    if holdings and holdings.get("changes"):
        lines.append("")
        lines.append(f"═══ 十大流通股东变动 ({holdings['latest_period']}) ═══")
        for c in holdings["changes"][:5]:
            if c["change_pct"] > 900:
                tag = "🆕新进"
            elif c["change"] > 0:
                tag = f"↑加仓{c['change_pct']:+.0f}%"
            else:
                tag = f"↓减仓{c['change_pct']:.0f}%"
            # 截取机构名（太长的话截断）
            short_name = c["name"][:12] + "..." if len(c["name"]) > 12 else c["name"]
            lines.append(f"  {short_name}: {c['amount']/10000:.0f}万股 {tag}")

    # ── Optimus里程碑 ──
    lines.append("")
    lines.append(f"═══ Optimus里程碑 ═══")
    for ms in OPTIMUS_MILESTONES:
        icon = "✅" if ms["status"] == "已完成" else "⏳" if ms["status"] == "待确认" else "⬜"
        lines.append(f"  {icon} {ms['event']} ({ms['expected']})")

    # ── 操作建议 ──
    if valuation and "current_mv" in valuation:
        lines.append("")
        lines.append(f"═══ 操作框架 ═══")
        premium = valuation["vs_floor"]
        if premium < 10:
            lines.append(f"  → 股价接近纯汽车估值底部，安全边际充足")
            lines.append(f"  → 机器人期权≈免费，可建标准仓位")
        elif premium < 30:
            lines.append(f"  → 机器人溢价偏低，可建底仓等催化")
        elif premium < 60:
            lines.append(f"  → 估值合理，持仓观察")
        else:
            lines.append(f"  → 机器人预期充分定价，需量产超预期才可上涨")

    lines.append("")
    lines.append(f"买点: 跌至纯汽车估值附近 | 卖点: Optimus延期 或 毛利率连续3季↓")

    return "\n".join(lines)


def push_to_feishu(content, webhook):
    if not webhook:
        return
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        print(f"飞书推送: {'成功' if resp.status_code == 200 else '失败'}")
    except Exception as e:
        print(f"飞书推送异常: {e}")


# ============================================================
#  主函数
# ============================================================
def main():
    print(f"拓普集团全自动估值监控")
    print(f"{'=' * 50}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    pro = None
    if TUSHARE_TOKEN:
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()

    # 1. 股价
    print("1/6 获取股价...")
    stock = get_stock_data(pro) if pro else None

    # 2. 客户销量
    print("2/6 获取客户销量...")
    sales = get_customer_sales()

    # 3. 财务数据
    print("3/6 获取财务数据...")
    fin_raw = get_financial_data(pro) if pro else None
    financials = analyze_financials(fin_raw) if fin_raw else None

    # 4. 一致预期
    print("4/6 获取一致预期...")
    estimates = get_consensus_estimates()

    # 5. 机构持仓
    print("5/6 获取机构持仓...")
    holdings = get_institutional_holdings(pro) if pro else None

    # 6. 估值计算
    print("6/6 计算估值...")
    valuation = calculate_valuation(stock, estimates)

    # 生成报告
    report = format_report(stock, sales, financials, estimates, holdings, valuation)
    print()
    print(report)

    # 推送
    push_to_feishu(report, FEISHU_WEBHOOK)


if __name__ == "__main__":
    main()
