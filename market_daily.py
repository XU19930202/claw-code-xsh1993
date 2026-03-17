#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日市场简报
功能：
  1. 上证指数、深证成指：收盘价、涨跌幅
  2. 全A市场：成交额、上涨家数、下跌家数
  3. 个股（翱捷科技、*ST星光、*ST天龙、中旗新材、宝莱特）：价格、涨跌幅、今日/昨日成交额比
  4. 华泰柏瑞沪深300ETF：价格、份额变动
数据源：Tushare
"""

import sys
import datetime
import time
import tushare as ts
import yaml
import logging
from pathlib import Path

# ========== 配置区 ==========
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
HISTORY_DIR = SCRIPT_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"feishu_webhook": "", "llm": {}}

TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"

# 监控个股列表：(名称, ts_code)
# ★ 请根据实际情况核实代码，ST股票代码可能因更名而变化
WATCH_STOCKS = [
    ("翱捷科技", "688220.SH"),
    ("*ST星光", "002076.SZ"),
    ("*ST天龙", "300029.SZ"),
    ("中旗新材", "001212.SZ"),
    ("宝莱特",   "300246.SZ"),
]

ETF_CODE = "510300.SH"  # 华泰柏瑞沪深300ETF
# ========== 配置区结束 ==========

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "market_daily.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def get_recent_trade_dates(n=5):
    """获取最近n个交易日（降序）"""
    today = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y%m%d")
    df = pro.trade_cal(exchange='SSE', start_date=start, end_date=today,
                       fields='cal_date,is_open')
    df = df[df['is_open'] == 1].sort_values('cal_date', ascending=False)
    return df['cal_date'].head(n).tolist()


def part1_index():
    """第一部分：上证指数、深证成指的价格和涨跌幅"""
    dates = get_recent_trade_dates(2)
    if not dates:
        return "【指数数据】获取交易日失败\n"
    trade_date = dates[0]

    indices = [
        ("上证指数", "000001.SH"),
        ("深证成指", "399001.SZ"),
    ]
    lines = []
    lines.append("━━━ 指数行情 ━━━")
    for name, code in indices:
        try:
            df = pro.index_daily(ts_code=code, trade_date=trade_date)
            if df.empty:
                lines.append(f"  {name}: 无数据")
                continue
            r = df.iloc[0]
            arrow = "🔴" if r['pct_chg'] < 0 else "🟢"
            lines.append(f"  {arrow} {name}  {r['close']:.2f}  ({r['pct_chg']:+.2f}%)")
        except Exception as e:
            lines.append(f"  {name}: 获取失败({e})")
    return "\n".join(lines), trade_date


def part2_market(trade_date):
    """第二部分：全A市场成交额、上涨家数、下跌家数"""
    lines = []
    lines.append("\n━━━ 全A市场概况 ━━━")
    try:
        # 拉取当日全部股票行情
        df = pro.daily(trade_date=trade_date)
        if df.empty:
            lines.append("  无数据")
            return "\n".join(lines)

        total_amount = df['amount'].sum() / 1e5  # amount单位千元 → 亿元
        up_count = len(df[df['pct_chg'] > 0])
        down_count = len(df[df['pct_chg'] < 0])
        flat_count = len(df[df['pct_chg'] == 0])

        lines.append(f"  成交额      {total_amount:,.0f} 亿元")
        lines.append(f"  上涨 {up_count} 家   下跌 {down_count} 家   平盘 {flat_count} 家")
    except Exception as e:
        lines.append(f"  获取失败: {e}")
    return "\n".join(lines)


def part3_stocks(trade_date, prev_date):
    """第三部分：个股价格、涨跌幅、今日/昨日成交额比"""
    lines = []
    lines.append("\n━━━ 重点个股 ━━━")
    lines.append(f"  {'名称':<10} {'价格':>8} {'涨跌幅':>8} {'额比(今/昨)':>12}")
    lines.append(f"  {'─'*46}")

    for name, code in WATCH_STOCKS:
        try:
            # 拉取近5个交易日数据以确保覆盖今天和昨天
            start_d = (datetime.datetime.strptime(prev_date, "%Y%m%d")
                       - datetime.timedelta(days=5)).strftime("%Y%m%d")
            df = pro.daily(ts_code=code, start_date=start_d, trade_date='')
            if df is None or df.empty:
                lines.append(f"  {name:<10} 无数据")
                continue

            df = df.sort_values('trade_date', ascending=False)

            # 找到当日和前一日数据
            today_row = df[df['trade_date'] == trade_date]
            prev_row = df[df['trade_date'] == prev_date]

            if today_row.empty:
                lines.append(f"  {name:<10} 当日无数据(可能停牌)")
                continue

            t = today_row.iloc[0]
            close = t['close']
            pct = t['pct_chg']
            amount_today = t['amount']  # 千元

            if not prev_row.empty:
                amount_prev = prev_row.iloc[0]['amount']
                if amount_prev > 0:
                    vol_ratio = amount_today / amount_prev
                    ratio_str = f"{vol_ratio:.2f}x"
                else:
                    ratio_str = "N/A"
            else:
                ratio_str = "N/A"

            arrow = "🔴" if pct < 0 else "🟢"
            lines.append(f"  {arrow} {name:<8} {close:>8.2f} {pct:>+7.2f}% {ratio_str:>10}")
        except Exception as e:
            lines.append(f"  {name:<10} 获取失败({e})")
        time.sleep(0.3)  # 控制频率，避免触发tushare限流

    return "\n".join(lines)


def part4_etf(trade_date, prev_date):
    """第四部分：华泰柏瑞沪深300ETF价格及份额变动"""
    lines = []
    lines.append("\n━━━ 沪深300ETF (510300) ━━━")
    try:
        # ETF行情（用fund_daily）
        df_price = pro.fund_daily(ts_code=ETF_CODE, trade_date=trade_date)
        if df_price.empty:
            lines.append("  行情数据: 无")
        else:
            r = df_price.iloc[0]
            arrow = "🔴" if r['pct_chg'] < 0 else "🟢"
            lines.append(f"  {arrow} 价格 {r['close']:.4f}  ({r['pct_chg']:+.2f}%)")
    except Exception as e:
        lines.append(f"  行情获取失败: {e}")

    try:
        # ETF份额变动（fund_share）
        start_d = (datetime.datetime.strptime(prev_date, "%Y%m%d")
                   - datetime.timedelta(days=5)).strftime("%Y%m%d")
        df_share = pro.fund_share(ts_code=ETF_CODE, start_date=start_d,
                                  end_date=trade_date)
        if df_share is not None and len(df_share) >= 2:
            df_share = df_share.sort_values('trade_date', ascending=False)
            today_share = df_share.iloc[0]['fd_share']   # 万份
            prev_share = df_share.iloc[1]['fd_share']
            delta = today_share - prev_share
            sign = "+" if delta >= 0 else ""
            lines.append(f"  份额 {today_share:,.2f} 万份  较上日 {sign}{delta:,.2f} 万份")
        elif df_share is not None and len(df_share) == 1:
            today_share = df_share.iloc[0]['fd_share']
            lines.append(f"  份额 {today_share:,.2f} 万份  (前日份额数据缺失)")
        else:
            lines.append("  份额数据: 暂无")
    except Exception as e:
        lines.append(f"  份额获取失败: {e}")

    return "\n".join(lines)


def send_feishu(wh, title, content):
    """飞书推送"""
    if not wh or "你的" in wh:
        logger.warning("飞书webhook未配置")
        return
    try:
        import requests
        r = requests.post(wh, json={"msg_type":"interactive","card":{
            "header":{"title":{"tag":"plain_text","content":title},"template":"blue"},
            "elements":[{"tag":"markdown","content":content[:4000]}]
        }}, timeout=10)
        logger.info(f"[飞书] {r.json()}")
    except Exception as e:
        logger.error(f"[飞书] {e}")


def main(target_date=None):
    """主函数"""
    config = load_config()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # 获取交易日
    dates = get_recent_trade_dates(3)
    if len(dates) < 2:
        print("无法获取足够的交易日数据")
        return

    if target_date:
        trade_date = target_date
        # 找target_date的前一个交易日
        all_dates = get_recent_trade_dates(20)
        try:
            idx = all_dates.index(target_date)
            prev_date = all_dates[idx + 1]
        except (ValueError, IndexError):
            prev_date = dates[1] if len(dates) > 1 else dates[0]
    else:
        trade_date = dates[0]
        prev_date = dates[1]

    # 检查是否是交易日，如果不是则跳过
    if trade_date != today.replace("-", ""):
        # 如果最新交易日不是今天，说明今天不是交易日，跳过推送
        logger.info(f"今日({today})非交易日，最新交易日为{trade_date}，跳过推送")
        return

    logger.info(f"📊 A股市场日报  {trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}")
    logger.info(f"   (对比前一交易日 {prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:]})")

    # 第一部分：指数
    result1, _ = part1_index()

    # 第二部分：全A概况
    result2 = part2_market(trade_date)

    # 第三部分：个股
    result3 = part3_stocks(trade_date, prev_date)

    # 第四部分：ETF
    result4 = part4_etf(trade_date, prev_date)

    # 组装完整文本
    full_text = "\n".join([
        f"📊 A股市场日报  {trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",
        f"   (对比前一交易日 {prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:]})",
        "", result1, result2, result3, result4,
        f"\n{'─'*50}",
        "数据来源: Tushare | 仅供参考"
    ])

    # 输出到控制台
    print(full_text)

    # 推送到飞书
    title = f"🇨🇳 {trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} A股市场日报"
    send_feishu(config.get("feishu_webhook", ""), title, full_text)

    # 存档
    try:
        with open(HISTORY_DIR / f"market_{trade_date}.md", "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{full_text}")
    except Exception as e:
        logger.error(f"存档失败: {e}")

    logger.info("完成")
    return full_text


if __name__ == "__main__":
    # 支持指定日期：python market_daily.py 20260310
    target = sys.argv[1] if len(sys.argv) > 1 else None

    # Windows控制台编码设置
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    main(target)
