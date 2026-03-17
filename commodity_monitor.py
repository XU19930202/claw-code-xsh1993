"""
商品周期股三层触发监控系统
=========================
第一层：商品价格 vs 行业成本线（偏离度报警）
第二层：商品价格技术面（周线不再创新低 + 期货曲线结构）
第三层：对应股票右侧信号（调用 macd_divergence.py）

数据源：
  - 期货价格：akshare（免费）
  - 现货价格：生意社爬取（免费）
  - 股票数据：tushare

用法：python commodity_monitor.py
建议cron：每个交易日17:00执行，推送飞书
"""

import akshare as ak
import pandas as pd
import numpy as np
import requests
import json
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 配置区 ==========
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"  # 填你的飞书webhook地址
TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"   # 填你的tushare token

@dataclass
class CommodityConfig:
    """单个商品品种配置"""
    name: str                    # 品种名
    futures_symbol: str          # akshare期货代码（主力合约）
    exchange: str                # 交易所: dce/shfe/czce/gfex/ine
    cost_floor: float            # 行业现金成本下限（低成本龙头）
    cost_70pct: float            # 70%分位产能现金成本（报警线）
    cost_90pct: float            # 90%分位产能现金成本（深度亏损线）
    unit: str                    # 单位
    related_stocks: Dict[str, str] = field(default_factory=dict)  # 关联股票 {名称: 代码}
    notes: str = ""              # 备注

# ========== 品种配置 ==========
# 成本数据需要你根据行业研报定期更新，这里给的是参考值
COMMODITIES = [
    CommodityConfig(
        name="碳酸锂",
        futures_symbol="LC0",      # 广期所碳酸锂主力
        exchange="gfex",
        cost_floor=3.5,            # 万元/吨，盐湖提锂
        cost_70pct=7.0,            # 万元/吨，云母提锂
        cost_90pct=9.0,
        unit="万元/吨",
        related_stocks={
            "天齐锂业": "002466.SZ",
            "赣锋锂业": "002460.SZ",
            "融捷股份": "002192.SZ",
        },
        notes="盐湖<4万, 锂辉石5-6万, 云母7-9万",
    ),
    CommodityConfig(
        name="纯碱",
        futures_symbol="SA0",      # 郑商所纯碱主力
        exchange="czce",
        cost_floor=1200,
        cost_70pct=1600,
        cost_90pct=1900,
        unit="元/吨",
        related_stocks={
            "远兴能源": "000683.SZ",
            "三友化工": "600409.SH",
        },
        notes="天然碱<1300, 氨碱法1400-1700, 联碱法1500-1800",
    ),
    CommodityConfig(
        name="铜",
        futures_symbol="CU0",      # 上期所铜主力
        exchange="shfe",
        cost_floor=35000,
        cost_70pct=50000,
        cost_90pct=60000,
        unit="元/吨",
        related_stocks={
            "紫金矿业": "601899.SH",
            "西部矿业": "601168.SH",
            "铜陵有色": "000630.SZ",
        },
    ),
    CommodityConfig(
        name="铝",
        futures_symbol="AL0",      # 上期所铝主力
        exchange="shfe",
        cost_floor=14000,          # 云南水电铝
        cost_70pct=17000,
        cost_90pct=18500,
        unit="元/吨",
        related_stocks={
            "中国铝业": "601600.SH",
            "云铝股份": "000807.SZ",
            "天山铝业": "002532.SZ",
        },
        notes="水电铝<15000, 火电铝16000-18000",
    ),
    CommodityConfig(
        name="螺纹钢",
        futures_symbol="RB0",      # 上期所螺纹主力
        exchange="shfe",
        cost_floor=3200,
        cost_70pct=3600,
        cost_90pct=3900,
        unit="元/吨",
        related_stocks={
            "华菱钢铁": "000932.SZ",
            "方大特钢": "600507.SH",
            "宝钢股份": "600019.SH",
        },
    ),
    CommodityConfig(
        name="PTA",
        futures_symbol="TA0",      # 郑商所PTA主力
        exchange="czce",
        cost_floor=4500,
        cost_70pct=5500,
        cost_90pct=6200,
        unit="元/吨",
        related_stocks={
            "恒力石化": "600346.SH",
            "荣盛石化": "002493.SZ",
            "桐昆股份": "601233.SH",
        },
    ),
    CommodityConfig(
        name="黄金",
        futures_symbol="AU0",      # 上期所黄金主力
        exchange="shfe",
        cost_floor=280,            # 黄金没有传统成本线逻辑
        cost_70pct=350,            # 这里用支撑位替代
        cost_90pct=400,
        unit="元/克",
        related_stocks={
            "山东黄金": "600547.SH",
            "中金黄金": "600489.SH",
            "赤峰黄金": "600988.SH",
        },
        notes="黄金不适用成本线逻辑，此处用关键支撑位替代",
    ),
    CommodityConfig(
        name="焦炭",
        futures_symbol="J0",       # 大商所焦炭主力
        exchange="dce",
        cost_floor=1600,
        cost_70pct=2000,
        cost_90pct=2300,
        unit="元/吨",
        related_stocks={
            "美锦能源": "000723.SZ",
            "山西焦煤": "000983.SZ",
        },
    ),
    CommodityConfig(
        name="尿素",
        futures_symbol="UR0",      # 郑商所尿素主力
        exchange="czce",
        cost_floor=1400,
        cost_70pct=1700,
        cost_90pct=1900,
        unit="元/吨",
        related_stocks={
            "华鲁恒升": "600426.SH",
        },
        notes="气头1400-1600, 煤头1500-1800",
    ),
]
# =============================


def get_futures_daily(symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
    """
    获取期货主力合约日线数据
    返回 DataFrame: date, open, high, low, close, volume
    """
    try:
        df = ak.futures_main_sina(symbol=symbol, start_date="20230101")
        if df is None or df.empty:
            return None
        # 标准化列名
        df = df.rename(columns={
            "日期": "date", "开盘价": "open", "最高价": "high",
            "最低价": "low", "收盘价": "close", "成交量": "volume",
        })
        # 确保数值类型
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df.tail(days)
    except Exception as e:
        print(f"  获取 {symbol} 数据失败: {e}")
        return None


def get_futures_curve(symbol_prefix: str, exchange: str) -> Optional[Dict]:
    """
    获取期货各月合约价格，判断曲线结构
    返回: {
        "structure": "contango" / "backwardation" / "flat",
        "near_price": float,   # 近月价格
        "far_price": float,    # 远月价格
        "spread_pct": float,   # 远近月价差百分比
    }
    """
    try:
        # 尝试获取不同交易所的合约列表
        df = ak.futures_spot_price_daily(start_day=datetime.now().strftime("%Y%m%d"),
                                          end_day=datetime.now().strftime("%Y%m%d"))
        # 如果这个接口不可用，回退到简单判断
        return None
    except Exception:
        pass

    # 回退方案：用主力合约价格的近期趋势来间接判断
    # 如果近5日均价 > 近20日均价，市场预期回升（类contango）
    return None


def calc_weekly_from_daily(df: pd.DataFrame) -> pd.DataFrame:
    """从日线数据合成周线"""
    df = df.copy()
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["year"] = df["date"].dt.year
    weekly = df.groupby(["year", "week"]).agg(
        date=("date", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index(drop=True)
    weekly = weekly.sort_values("date").reset_index(drop=True)
    return weekly


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    """计算MACD"""
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    df["dif"] = ema_fast - ema_slow
    df["dea"] = df["dif"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = 2 * (df["dif"] - df["dea"])
    return df


def check_no_new_low(df: pd.DataFrame, weeks: int = 8) -> Dict:
    """
    检查商品价格周线是否已经不再创新低
    逻辑：最近weeks周的最低价 > 之前一段时间的最低价的位置在weeks之前
    """
    if len(df) < weeks + 10:
        return {"no_new_low": False, "detail": "数据不足"}

    recent = df.tail(weeks)
    earlier = df.iloc[-(weeks + 20):-weeks]

    recent_low = recent["low"].min()
    earlier_low = earlier["low"].min()

    if recent_low > earlier_low:
        return {
            "no_new_low": True,
            "recent_low": recent_low,
            "earlier_low": earlier_low,
            "detail": f"近{weeks}周最低{recent_low:.1f} > 前期低点{earlier_low:.1f}，底部抬升",
        }
    else:
        return {
            "no_new_low": False,
            "recent_low": recent_low,
            "earlier_low": earlier_low,
            "detail": f"近{weeks}周仍在创新低({recent_low:.1f})，尚未企稳",
        }


def check_commodity_macd(weekly_df: pd.DataFrame) -> Dict:
    """检查商品周线MACD金叉"""
    df = calc_macd(weekly_df.copy())
    if len(df) < 10:
        return {"golden_cross": False, "detail": "数据不足"}

    # 最近4周内是否出现金叉
    recent = df.tail(4)
    for i in range(1, len(recent)):
        prev_diff = recent["dif"].iloc[i - 1] - recent["dea"].iloc[i - 1]
        curr_diff = recent["dif"].iloc[i] - recent["dea"].iloc[i]
        if prev_diff < 0 and curr_diff >= 0:
            return {
                "golden_cross": True,
                "date": recent["date"].iloc[i],
                "detail": f"商品周线MACD金叉于{recent['date'].iloc[i].strftime('%Y-%m-%d')}",
            }

    # 当前DIF vs DEA状态
    latest = df.iloc[-1]
    if latest["dif"] > latest["dea"]:
        return {
            "golden_cross": False,
            "dif_above": True,
            "detail": "DIF在DEA上方，多头排列中",
        }
    else:
        return {
            "golden_cross": False,
            "dif_above": False,
            "detail": "DIF在DEA下方，等待金叉",
        }


def analyze_commodity(cfg: CommodityConfig) -> Dict:
    """
    综合分析单个品种，返回三层信号状态
    """
    result = {
        "name": cfg.name,
        "layer1": {},  # 成本线偏离度
        "layer2": {},  # 价格技术面
        "layer3": {},  # 股票信号（仅提示，详细调用macd_divergence）
        "signal_level": 0,  # 0=无信号, 1=关注, 2=跟踪, 3=待买, 4=可建仓
    }

    # ===== 获取数据 =====
    df = get_futures_daily(cfg.futures_symbol)
    if df is None or df.empty:
        result["error"] = "数据获取失败"
        return result

    latest_price = df["close"].iloc[-1]
    latest_date = df["date"].iloc[-1]

    # ===== 第一层：成本线偏离度 =====
    if latest_price <= cfg.cost_70pct:
        if latest_price <= cfg.cost_floor:
            cost_status = "🔴 低于龙头成本线（接近全行业亏损）"
            cost_zone = "极度低估"
            result["signal_level"] = max(result["signal_level"], 2)
        else:
            cost_status = "🟡 进入30%产能亏损区（低于70%分位成本）"
            cost_zone = "低估"
            result["signal_level"] = max(result["signal_level"], 1)
    elif latest_price <= cfg.cost_90pct:
        cost_status = "🟢 10%-30%产能亏损（70%-90%分位之间）"
        cost_zone = "中性偏低"
    else:
        cost_status = "⚪ 高于90%分位成本（行业普遍盈利）"
        cost_zone = "中性/偏高"

    # 计算偏离度
    deviation_70 = (latest_price - cfg.cost_70pct) / cfg.cost_70pct * 100
    deviation_floor = (latest_price - cfg.cost_floor) / cfg.cost_floor * 100

    result["layer1"] = {
        "price": latest_price,
        "date": latest_date.strftime("%Y-%m-%d"),
        "cost_floor": cfg.cost_floor,
        "cost_70pct": cfg.cost_70pct,
        "deviation_70": deviation_70,
        "deviation_floor": deviation_floor,
        "status": cost_status,
        "zone": cost_zone,
    }

    # ===== 第二层：商品价格技术面 =====
    weekly = calc_weekly_from_daily(df)

    # 周线是否不再创新低
    no_new_low = check_no_new_low(weekly)

    # 商品周线MACD
    macd_status = check_commodity_macd(weekly)

    # 近远月价差（简化版：用5日均价 vs 20日均价）
    if len(df) >= 20:
        ma5 = df["close"].tail(5).mean()
        ma20 = df["close"].tail(20).mean()
        momentum = "近强远弱(类升水)" if ma5 > ma20 else "近弱远强(类贴水)"
        momentum_pct = (ma5 - ma20) / ma20 * 100
    else:
        momentum = "数据不足"
        momentum_pct = 0

    # ===== 第二层信号：严格以第一层为前置条件 =====
    # 三道门串联：第一层没开，第二层不看
    layer1_triggered = result["signal_level"] >= 1  # 价格已进入成本区间
    layer2_signal = False
    layer2_note = ""

    if not layer1_triggered:
        # 第一层没过，第二层技术面再好也不算信号
        layer2_note = "第一层未触发，技术面仅作参考"
    else:
        # 第一层已触发，才看第二层
        if no_new_low.get("no_new_low") and (macd_status.get("golden_cross") or macd_status.get("dif_above")):
            layer2_signal = True
            result["signal_level"] = max(result["signal_level"], 3)  # 升级到待买
            layer2_note = "第一层+第二层均通过 → 待买"
        elif no_new_low.get("no_new_low"):
            result["signal_level"] = max(result["signal_level"], 2)  # 升级到跟踪
            layer2_note = "价格不再创新低，等待MACD确认"
        else:
            layer2_note = "价格仍在创新低，继续等待企稳"

    result["layer2"] = {
        "no_new_low": no_new_low,
        "macd": macd_status,
        "momentum": momentum,
        "momentum_pct": momentum_pct,
        "signal": layer2_signal,
        "layer1_prerequisite": layer1_triggered,
        "note": layer2_note,
    }

    # ===== 第三层：股票信号（严格以第二层为前置条件） =====
    if layer2_signal:
        result["layer3"] = {
            "stocks": cfg.related_stocks,
            "note": "第二层已通过，请运行 macd_divergence.py 检测股票右侧信号",
            "actionable": True,
        }
    else:
        result["layer3"] = {
            "stocks": cfg.related_stocks,
            "note": "第二层未通过，暂不检查股票信号",
            "actionable": False,
        }

    return result


def format_report(results: List[Dict]) -> str:
    """生成飞书推送文本"""
    lines = []
    lines.append(f"📊 商品周期股三层触发监控")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 按信号等级排序，高的在前
    results.sort(key=lambda x: x.get("signal_level", 0), reverse=True)

    # 信号等级说明（严格串联）
    level_map = {
        0: "⚪ 无信号（价格高于成本区间）",
        1: "🟢 关注（第一层：价格进入30%产能亏损区）",
        2: "🟡 跟踪（第一层+价格不再创新低）",
        3: "🟠 待买（第一层+第二层：商品价格企稳确认）",
        4: "🔴 可建仓（三层全部通过：股票右侧确认）",
    }

    # 先输出有信号的
    has_signal = [r for r in results if r.get("signal_level", 0) > 0]
    no_signal = [r for r in results if r.get("signal_level", 0) == 0]

    if has_signal:
        lines.append("═══ 有信号品种 ═══")
        lines.append("")

    for r in has_signal:
        lines.extend(format_single(r, level_map))
        lines.append("")

    if no_signal:
        lines.append("═══ 暂无信号 ═══")
        lines.append("")

    for r in no_signal:
        lines.extend(format_single(r, level_map, brief=True))
        lines.append("")

    # 底部说明
    lines.append("─────────────────")
    lines.append("三道门严格串联（前一道不开，后一道不看）：")
    lines.append("  第一道: 价格跌破70%分位成本线（30%产能亏损）")
    lines.append("  第二道: 商品周线不再创新低 + MACD多头确认")
    lines.append("  第三道: 对应股票周线右侧信号（macd_divergence.py）")
    lines.append("操作纪律: 缺一不动，三道全过才建仓")

    return "\n".join(lines)


def format_single(r: Dict, level_map: Dict, brief=False) -> List[str]:
    """格式化单个品种"""
    lines = []
    name = r["name"]
    level = r.get("signal_level", 0)

    if "error" in r:
        lines.append(f"【{name}】数据获取失败")
        return lines

    l1 = r["layer1"]
    l2 = r["layer2"]

    lines.append(f"【{name}】{level_map.get(level, '未知')}")
    lines.append(f"  现价: {l1['price']:.1f} {l1.get('unit', '')}  "
                 f"日期: {l1['date']}")
    lines.append(f"  {l1['status']}")
    lines.append(f"  vs 70%成本线: {l1['deviation_70']:+.1f}%  "
                 f"vs 龙头成本: {l1['deviation_floor']:+.1f}%")

    if not brief:
        lines.append(f"  ── 第二层：价格技术面 ──")
        # 显示串联前置条件状态
        if not l2.get("layer1_prerequisite", False):
            lines.append(f"  🚫 第一层未触发，以下技术面仅供参考（不产生信号）")
        lines.append(f"  {l2['no_new_low']['detail']}")
        lines.append(f"  {l2['macd']['detail']}")
        lines.append(f"  动量: {l2['momentum']} ({l2['momentum_pct']:+.1f}%)")
        if l2.get("note"):
            lines.append(f"  → {l2['note']}")

        # 第三层状态
        l3 = r.get("layer3", {})
        if l3.get("actionable"):
            stocks_str = ", ".join(l3.get("stocks", {}).keys())
            lines.append(f"  ── 第三层：股票右侧信号 ──")
            lines.append(f"  ✅ 前两层已通过，请检查股票右侧信号")
            lines.append(f"  关联股票: {stocks_str}")
        elif l2.get("layer1_prerequisite", False):
            lines.append(f"  ⏳ 第二层未完全通过，暂不检查股票")

    return lines


def push_to_feishu(content: str, webhook: str):
    """推送到飞书webhook"""
    if not webhook:
        print("未配置飞书webhook，仅打印到控制台")
        return

    payload = {
        "msg_type": "text",
        "content": {"text": content},
    }
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200:
            print("飞书推送成功")
        else:
            print(f"飞书推送失败: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"飞书推送异常: {e}")


def main():
    print("正在扫描商品品种...")
    print()

    results = []
    for cfg in COMMODITIES:
        print(f"  分析 {cfg.name} ({cfg.futures_symbol})...")
        try:
            r = analyze_commodity(cfg)
            # 把unit带上
            if "layer1" in r and r["layer1"]:
                r["layer1"]["unit"] = cfg.unit
            results.append(r)
        except Exception as e:
            print(f"  {cfg.name} 出错: {e}")
            results.append({"name": cfg.name, "error": str(e), "signal_level": 0})

    # 生成报告
    report = format_report(results)
    print()
    print(report)

    # 推送飞书
    push_to_feishu(report, FEISHU_WEBHOOK)


if __name__ == "__main__":
    main()
