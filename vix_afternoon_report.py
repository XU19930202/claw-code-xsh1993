#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
午后恐慌指数综合报告
获取VIX数据 + 国际主要指数 -> 生成分析报告 -> 推送飞书
"""

import requests
import yaml
import logging
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def fetch_vix():
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist is not None and len(hist) >= 1:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else None
            return {
                "value": float(latest["Close"]),
                "date": latest.name.strftime("%Y-%m-%d"),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "prev_close": float(prev["Close"]) if prev is not None else None,
                "source": "Yahoo Finance"
            }
    except Exception as e:
        logger.error(f"VIX获取失败: {e}")
    return None

def fetch_global_indices():
    """通过codebuddy金融API获取国际主要指数"""
    try:
        payload = {"api_name": "index_global", "params": {}, "fields": "ts_code,close,pre_close,change,pct_chg"}
        r = requests.post("https://www.codebuddy.cn/v2/tool/financedata", json=payload, timeout=15)
        data = r.json()
        if data.get("code") == 0 and data.get("data"):
            fields = data["data"]["fields"]
            items = data["data"]["items"]
            seen = set()
            result = {}
            for row in items:
                d = dict(zip(fields, row))
                code = d["ts_code"]
                if code not in seen:
                    seen.add(code)
                    result[code] = d
            return result
    except Exception as e:
        logger.error(f"国际指数获取失败: {e}")
    return {}

def analyze_vix(vix_value):
    if vix_value < 15:
        return "极低恐慌", "😌", "green", "市场高度乐观，投资者信心充足，波动率处于历史低位", "适合积极布局，市场风险较低"
    elif vix_value < 20:
        return "低恐慌", "🙂", "green", "市场情绪稳定，波动性正常，无明显恐慌信号", "正常仓位操作，市场平稳运行"
    elif vix_value < 25:
        return "中等恐慌", "😐", "blue", "市场出现一定担忧，波动性有所上升，需保持警惕", "谨慎操作，注意风险控制"
    elif vix_value < 30:
        return "较高恐慌", "😟", "orange", "市场恐慌情绪增加，投资者风险偏好下降", "减少高风险操作，控制仓位在45-55%"
    elif vix_value < 40:
        return "高恐慌", "😰", "red", "市场恐慌情绪显著，可能存在系统性风险", "暂停高风险操作，保守观望，仓位建议30-40%"
    else:
        return "极高恐慌", "😱", "red", "市场极度恐慌，可能出现重大系统性事件", "强烈建议暂停交易，等待市场稳定"

INDEX_NAME_MAP = {
    "SPX": "标普500",
    "IXIC": "纳斯达克",
    "DJI": "道琼斯",
    "RUT": "罗素2000",
    "N225": "日经225",
    "HSI": "恒生指数",
    "HKTECH": "恒生科技",
    "XIN9": "富时中国A50",
    "FTSE": "英国富时100",
    "GDAXI": "德国DAX",
    "FCHI": "法国CAC40",
    "KS11": "韩国综合",
    "TWII": "台湾加权",
    "SENSEX": "印度SENSEX",
    "CSX5P": "欧洲斯托克50",
}

def send_feishu(webhook, title, content, color="orange"):
    if not webhook:
        logger.warning("飞书webhook未配置")
        return False
    try:
        r = requests.post(webhook, json={
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color
                },
                "elements": [{"tag": "markdown", "content": content}]
            }
        }, timeout=10)
        result = r.json()
        logger.info(f"飞书推送结果: {result}")
        return result.get("StatusCode", -1) == 0
    except Exception as e:
        logger.error(f"飞书推送失败: {e}")
        return False

def run():
    config = load_config()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")

    logger.info(f"===== 午后恐慌指数报告 {now_str} =====")

    # 获取VIX
    vix_data = fetch_vix()
    if not vix_data:
        logger.error("无法获取VIX数据，任务终止")
        return

    vix_value = vix_data["value"]
    level, emoji, color, desc, suggestion = analyze_vix(vix_value)

    # 获取国际指数
    global_indices = fetch_global_indices()

    # 计算变化趋势
    change_info = ""
    if vix_data.get("prev_close"):
        change = vix_value - vix_data["prev_close"]
        pct = (change / vix_data["prev_close"]) * 100
        arrow = "📈" if change > 0 else "📉"
        change_info = f"  {arrow} 较前收盘 **{change:+.2f}** ({pct:+.2f}%)"

    # 构建报告内容
    lines = []
    lines.append(f"## 📊 VIX恐慌指数午后报告 — {now_str}")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| **当前VIX** | **{vix_value:.2f}** {emoji} |")
    lines.append(f"| **恐慌等级** | {level} |")
    lines.append(f"| 今日区间 | 高 {vix_data['high']:.2f} / 低 {vix_data['low']:.2f} |")
    if vix_data.get("prev_close"):
        change = vix_value - vix_data["prev_close"]
        pct = (change / vix_data["prev_close"]) * 100
        arrow = "📈" if change > 0 else "📉"
        lines.append(f"| 较前收盘 | {arrow} {change:+.2f} ({pct:+.2f}%) |")
    lines.append(f"| 数据来源 | {vix_data.get('source', 'N/A')} |")
    lines.append("")
    lines.append(f"**📝 市场解读**：{desc}")
    lines.append(f"**💡 操作建议**：{suggestion}")
    lines.append("")

    # 国际主要指数表
    if global_indices:
        key_indices = ["SPX", "IXIC", "DJI", "N225", "HSI", "HKTECH", "XIN9", "FTSE", "GDAXI"]
        lines.append("**🌍 国际主要指数（最新收盘）**")
        lines.append("")
        lines.append("| 指数 | 收盘 | 涨跌 | 涨跌幅 |")
        lines.append("|------|------|------|--------|")
        for code in key_indices:
            if code in global_indices:
                idx = global_indices[code]
                name = INDEX_NAME_MAP.get(code, code)
                close = idx.get("close", "N/A")
                change = idx.get("change", 0)
                pct = idx.get("pct_chg", 0)
                if pct is not None:
                    arrow = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
                    lines.append(f"| {name} | {close:,.2f} | {change:+.2f} | {arrow} {pct:+.2f}% |")
        lines.append("")

    # 全球市场情绪综合
    lines.append("---")
    lines.append(f"*VIX参考区间: <15极低 | 15-20低 | 20-25中等 | 25-30较高 | 30-40高 | >40极高恐慌*")
    lines.append(f"*本报告由自动化监控系统生成，仅供参考，不构成投资建议*")

    content = "\n".join(lines)
    title = f"📊 VIX恐慌指数午后报告 {vix_value:.2f} {emoji} [{level}]"

    success = send_feishu(config.get("feishu_webhook", ""), title, content, color)

    if success:
        logger.info(f"✅ 飞书推送成功 | VIX={vix_value:.2f} | {level}")
        # 保存历史
        history_dir = SCRIPT_DIR / "history"
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / f"vix_{now.strftime('%Y-%m-%d')}.log"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(f"{now.strftime('%Y-%m-%d %H:%M:%S')} | 午后 | VIX={vix_value:.2f} | {level} | 推送成功\n")
    else:
        logger.error("❌ 飞书推送失败")

if __name__ == "__main__":
    run()
