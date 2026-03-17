"""
MACD周线底背离 + 金叉检测
用法：python macd_divergence.py
功能：
  1. 计算周线级别MACD（DIF, DEA）
  2. 检测底背离：价格创新低但DIF低点抬高
  3. 检测金叉：DIF上穿DEA
  4. 组合信号：底背离后出现金叉 = 右侧进场信号
"""

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ========== 配置区 ==========
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"  # 填你的token
WATCHLIST = {
    "长江电力": "600900.SH",
    "国电南瑞": "600406.SH",
    "中科曙光": "603019.SH",
    "中航沈飞": "600760.SH",
    "春立医疗": "688236.SH",
    "海力风电": "301155.SZ",
    "智明达": "688636.SH",
}
# 底背离回看周数（在多少根周K线内寻找两个低点）
LOOKBACK_WEEKS = 52
# =============================


def get_weekly_data(pro, ts_code, weeks=100):
    """获取周线数据"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y%m%d")
    df = pro.weekly(ts_code=ts_code, start_date=start, end_date=end,
                    fields="ts_code,trade_date,open,high,low,close,vol")
    if df.empty:
        return df
    df = df.sort_values("trade_date").reset_index(drop=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def calc_macd(df, fast=12, slow=26, signal=9):
    """计算MACD：DIF, DEA, MACD柱"""
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    df["dif"] = ema_fast - ema_slow
    df["dea"] = df["dif"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = 2 * (df["dif"] - df["dea"])  # 柱状图
    return df


def find_local_lows(series, order=3):
    """
    找局部低点
    order=3 表示一个低点的左右各3根K线都比它高才算
    """
    lows = []
    for i in range(order, len(series) - order):
        if all(series.iloc[i] <= series.iloc[i - j] for j in range(1, order + 1)) and \
           all(series.iloc[i] <= series.iloc[i + j] for j in range(1, order + 1)):
            lows.append(i)
    return lows


def detect_bottom_divergence(df, lookback=LOOKBACK_WEEKS):
    """
    检测底背离：
    在最近lookback根周K线内，找到至少两个价格低点
    如果后一个价格低点 < 前一个价格低点（价格创新低）
    但对应的DIF低点 > 前一个DIF低点（动能抬升）
    则判定为底背离
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback).copy()
    recent = recent.reset_index(drop=True)

    # 找价格局部低点
    price_low_indices = find_local_lows(recent["close"], order=2)
    # 找DIF局部低点
    dif_low_indices = find_local_lows(recent["dif"], order=2)

    if len(price_low_indices) < 2:
        return None

    # 从最近的两个价格低点开始检查
    for i in range(len(price_low_indices) - 1, 0, -1):
        idx_later = price_low_indices[i]      # 后一个低点（更近期）
        idx_earlier = price_low_indices[i - 1]  # 前一个低点（更早期）

        price_later = recent["close"].iloc[idx_later]
        price_earlier = recent["close"].iloc[idx_earlier]

        # 价格创新低（或接近新低，容差2%）
        if price_later > price_earlier * 1.02:
            continue

        # 找这两个价格低点附近对应的DIF值
        # 在价格低点前后2根K线内找最低DIF
        def get_nearby_dif_low(idx):
            start = max(0, idx - 2)
            end = min(len(recent) - 1, idx + 2)
            segment = recent["dif"].iloc[start:end + 1]
            return segment.min()

        dif_later = get_nearby_dif_low(idx_later)
        dif_earlier = get_nearby_dif_low(idx_earlier)

        # DIF低点抬高 = 底背离
        if dif_later > dif_earlier:
            return {
                "earlier_date": recent["trade_date"].iloc[idx_earlier],
                "earlier_price": price_earlier,
                "earlier_dif": dif_earlier,
                "later_date": recent["trade_date"].iloc[idx_later],
                "later_price": price_later,
                "later_dif": dif_later,
            }

    return None


def detect_golden_cross(df, within_weeks=8):
    """
    检测最近within_weeks周内是否出现金叉
    金叉定义：DIF从下方穿越DEA（前一根DIF<DEA，当前DIF>=DEA）
    """
    recent = df.tail(within_weeks).copy()
    recent = recent.reset_index(drop=True)

    crosses = []
    for i in range(1, len(recent)):
        prev_diff = recent["dif"].iloc[i - 1] - recent["dea"].iloc[i - 1]
        curr_diff = recent["dif"].iloc[i] - recent["dea"].iloc[i]
        if prev_diff < 0 and curr_diff >= 0:
            crosses.append({
                "date": recent["trade_date"].iloc[i],
                "dif": recent["dif"].iloc[i],
                "dea": recent["dea"].iloc[i],
            })

    return crosses[-1] if crosses else None


def check_platform_breakout(df, lookback=20, confirm_days=2):
    """
    检测是否站上前期平台
    逻辑：找前期成交密集区（用价格分布的众数区间），
    判断最近价格是否突破该区间上沿
    """
    if len(df) < lookback + 10:
        return None

    # 取lookback之前的一段数据作为"前期"
    historical = df.iloc[-(lookback + 30):-lookback]
    recent = df.tail(confirm_days)

    if historical.empty or recent.empty:
        return None

    # 用价格分布找密集成交区
    prices = historical["close"]
    # 分10档，找最多出现的价格区间
    bins = np.linspace(prices.min(), prices.max(), 11)
    hist, edges = np.histogram(prices, bins=bins)
    peak_bin = np.argmax(hist)
    platform_low = edges[peak_bin]
    platform_high = edges[peak_bin + 1]

    # 最近价格是否站上平台上沿
    current_price = recent["close"].iloc[-1]
    if current_price > platform_high:
        return {
            "platform_range": f"{platform_low:.2f} - {platform_high:.2f}",
            "current_price": current_price,
            "breakout": True,
        }

    return None


def analyze_stock(pro, name, ts_code):
    """综合分析单只股票"""
    df = get_weekly_data(pro, ts_code, weeks=120)
    if df.empty or len(df) < 30:
        return f"  {name}({ts_code}): 数据不足，跳过"

    df = calc_macd(df)

    # 当前状态
    latest = df.iloc[-1]
    dif_above_dea = latest["dif"] > latest["dea"]

    # 检测底背离
    divergence = detect_bottom_divergence(df)

    # 检测金叉（最近8周内）
    golden_cross = detect_golden_cross(df, within_weeks=8)

    # 检测平台突破
    platform = check_platform_breakout(df)

    # ========== 输出结果 ==========
    lines = []
    lines.append(f"{'=' * 50}")
    lines.append(f"  {name} ({ts_code})")
    lines.append(f"  最新收盘: {latest['close']:.2f}  "
                 f"DIF: {latest['dif']:.4f}  DEA: {latest['dea']:.4f}  "
                 f"{'DIF在DEA上方' if dif_above_dea else 'DIF在DEA下方'}")

    # 底背离
    if divergence:
        lines.append(f"  ⚠️  周线底背离:")
        lines.append(f"      前低 {divergence['earlier_date'].strftime('%Y-%m-%d')} "
                     f"价格={divergence['earlier_price']:.2f} DIF={divergence['earlier_dif']:.4f}")
        lines.append(f"      后低 {divergence['later_date'].strftime('%Y-%m-%d')} "
                     f"价格={divergence['later_price']:.2f} DIF={divergence['later_dif']:.4f}")
        lines.append(f"      价格更低但DIF抬升 → 下跌动能衰竭")
    else:
        lines.append(f"  ── 未检测到周线底背离")

    # 金叉
    if golden_cross:
        lines.append(f"  ⚠️  周线金叉: {golden_cross['date'].strftime('%Y-%m-%d')} "
                     f"DIF={golden_cross['dif']:.4f} DEA={golden_cross['dea']:.4f}")
    else:
        lines.append(f"  ── 最近8周无金叉")

    # 平台突破
    if platform and platform["breakout"]:
        lines.append(f"  ⚠️  站上前期平台: 平台区间{platform['platform_range']} "
                     f"当前价{platform['current_price']:.2f}")
    else:
        lines.append(f"  ── 未突破前期平台")

    # 综合信号
    signals = []
    if divergence:
        signals.append("底背离")
    if golden_cross:
        signals.append("金叉")
    if platform and platform["breakout"]:
        signals.append("平台突破")

    if len(signals) >= 2:
        lines.append(f"  🔴 右侧进场信号: {' + '.join(signals)} → 可建标准仓位")
    elif len(signals) == 1:
        lines.append(f"  🟡 单信号: {signals[0]} → 可建底仓，等待更多确认")
    else:
        lines.append(f"  🟢 暂无信号，继续观察")

    return "\n".join(lines)


def main():
    if not TUSHARE_TOKEN:
        print("请先在脚本顶部填入TUSHARE_TOKEN")
        return

    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    print(f"MACD周线底背离+金叉扫描")
    print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"回看周期: {LOOKBACK_WEEKS}周")
    print()

    for name, code in WATCHLIST.items():
        try:
            result = analyze_stock(pro, name, code)
            print(result)
        except Exception as e:
            print(f"  {name}({code}): 出错 - {e}")

    print(f"\n{'=' * 50}")
    print("信号说明:")
    print("  🔴 双信号/三信号 = 右侧确认，可建标准仓位")
    print("  🟡 单信号 = 方向初步确认，可试探底仓")
    print("  🟢 无信号 = 等待，不操作")


if __name__ == "__main__":
    main()
