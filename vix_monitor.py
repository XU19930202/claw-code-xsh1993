#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIX恐慌指数定时监控
每隔4小时推送恐慌指数数据到飞书群
数据源: Alpha Vantage / Yahoo Finance / Investing.com
"""

import requests
import yaml
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
HISTORY_DIR = SCRIPT_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"feishu_webhook": "", "alpha_vantage_key": ""}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "vix_monitor.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# VIX预警阈值
VIX_THRESHOLD = 20

def fetch_vix_alpha_vantage(api_key):
    """从Alpha Vantage获取VIX数据"""
    if not api_key or "your" in api_key.lower():
        return None
    
    try:
        url = f"https://www.alphavantage.co/query?function=VIX&apikey={api_key}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if "data" in data and len(data["data"]) > 0:
            latest = data["data"][0]
            return {
                "value": float(latest["vix_close"]),
                "date": latest["date"],
                "open": float(latest["vix_open"]),
                "high": float(latest["vix_high"]),
                "low": float(latest["vix_low"])
            }
    except Exception as e:
        logger.error(f"[Alpha Vantage] 获取失败: {e}")
    
    return None

def fetch_vix_yahoo():
    """从Yahoo Finance获取VIX数据 (备用方案)"""
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="2d")
        
        if hist is not None and len(hist) > 0:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else None
            
            return {
                "value": float(latest["Close"]),
                "date": latest.name.strftime("%Y-%m-%d"),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "prev_close": float(prev["Close"]) if prev is not None else None
            }
    except Exception as e:
        logger.error(f"[Yahoo Finance] 获取失败: {e}")
    
    return None

def fetch_vix_investing():
    """从investing.com获取VIX数据 (备用方案)"""
    try:
        url = "https://www.investing.com/indices/volatility-s-p-500"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        
        # 简单的HTML解析查找VIX值
        import re
        match = re.search(r'id="last_last"[^>]*>(\d+\.?\d*)', resp.text)
        if match:
            value = float(match.group(1))
            return {
                "value": value,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "investing.com"
            }
    except Exception as e:
        logger.error(f"[Investing.com] 获取失败: {e}")
    
    return None

def get_vix_data(config):
    """获取VIX数据 (多数据源尝试)"""
    # 尝试Alpha Vantage
    alpha_key = config.get("alpha_vantage_key", "")
    vix_data = fetch_vix_alpha_vantage(alpha_key)
    
    if vix_data:
        vix_data["source"] = "Alpha Vantage"
        return vix_data
    
    # 尝试Yahoo Finance
    vix_data = fetch_vix_yahoo()
    if vix_data:
        vix_data["source"] = "Yahoo Finance"
        return vix_data
    
    # 尝试Investing.com
    vix_data = fetch_vix_investing()
    if vix_data:
        return vix_data
    
    return None

def analyze_vix_level(vix_value):
    """分析VIX水平"""
    if vix_value < 15:
        level = "极低恐慌"
        emoji = "😌"
        desc = "市场情绪平静,投资者信心充足,波动率偏低"
        alert = "info"
        suggestion = "适合逢低布局,市场风险较低"
    elif vix_value < 20:
        level = "低恐慌"
        emoji = "🙂"
        desc = "市场情绪稳定,波动性正常"
        alert = "info"
        suggestion = "正常操作,市场平稳运行"
    elif vix_value < 25:
        level = "中等恐慌"
        emoji = "😐"
        desc = "市场出现一定担忧,波动性上升"
        alert = "warning"
        suggestion = "谨慎操作,开始注意风险控制"
    elif vix_value < 30:
        level = "较高恐慌"
        emoji = "😟"
        desc = "市场恐慌情绪增加,注意风险控制"
        alert = "warning"
        suggestion = "减少高风险操作,适当控制仓位"
    elif vix_value < 40:
        level = "高恐慌"
        emoji = "😰"
        desc = "市场恐慌情绪显著,建议谨慎操作"
        alert = "danger"
        suggestion = "暂停高风险操作,保守观望"
    else:
        level = "极高恐慌"
        emoji = "😱"
        desc = "市场极度恐慌,可能出现重大事件"
        alert = "danger"
        suggestion = "强烈建议暂停交易,等待市场稳定"
    
    return level, emoji, desc, alert, suggestion

def send_feishu(wh, title, content, alert_level="warning"):
    """飞书推送"""
    if not wh or "your" in wh:
        logger.warning("飞书webhook未配置")
        return False
    
    # 根据VIX水平选择颜色
    color_map = {
        "info": "blue",
        "warning": "orange",
        "danger": "red"
    }
    color = color_map.get(alert_level, "orange")
    
    try:
        r = requests.post(wh, json={
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color
                },
                "elements": [
                    {"tag": "markdown", "content": content}
                ]
            }
        }, timeout=10)
        result = r.json()
        logger.info(f"[飞书] {result}")
        return result.get("StatusCode", -1) == 0
    except Exception as e:
        logger.error(f"[飞书] 推送失败: {e}")
        return False

def run():
    """主函数"""
    config = load_config()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"{'='*20} VIX监控 {now_str} {'='*20}")
    
    # 获取VIX数据
    vix_data = get_vix_data(config)
    
    if not vix_data:
        logger.error("无法获取VIX数据")
        return
    
    vix_value = vix_data["value"]
    logger.info(f"VIX当前值: {vix_value} (来源: {vix_data.get('source', 'unknown')})")
    
    # 分析VIX水平
    level, emoji, desc, alert, suggestion = analyze_vix_level(vix_value)
    
    # 不管VIX值多少,都需要推送(定时任务)
    logger.info(f"VIX={vix_value} (等级: {level})")
    
    # 生成报告内容
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = [
        f"**📊 VIX恐慌指数监控报告 ({current_time})**",
        f"",
        f"**当前值**: **{vix_value:.2f}**",
        f"**恐慌等级**: {emoji} {level}",
        f"",
        f"**市场解读**: {desc}",
        f"**操作建议**: {suggestion}",
        f""
    ]
    
    # 添加详细数据
    if "open" in vix_data:
        lines.append(f"**今日开盘**: {vix_data['open']:.2f}")
    if "high" in vix_data:
        lines.append(f"**今日最高**: {vix_data['high']:.2f}")
    if "low" in vix_data:
        lines.append(f"**今日最低**: {vix_data['low']:.2f}")
    if vix_data.get("prev_close"):
        change = vix_value - vix_data["prev_close"]
        pct = (change / vix_data["prev_close"]) * 100
        arrow = "📈" if change > 0 else "📉"
        lines.append(f"**前值**: {vix_data['prev_close']:.2f} ({arrow} {abs(change):.2f}, {pct:+.2f}%)")
    
    lines.append(f"")
    lines.append(f"**数据时间**: {vix_data.get('date', 'N/A')}")
    lines.append(f"**数据来源**: {vix_data.get('source', 'N/A')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*参考区间: <15极低恐慌, 15-20低恐慌, 20-25中等恐慌, 25-30较高恐慌, 30-40高恐慌, >40极高恐慌*")
    lines.append(f"*定时监控: 每隔4小时推送恐慌指数报告*")
    
    content = "\n".join(lines)
    
    # 推送标题
    title = f"📊 VIX恐慌指数报告: {vix_value:.2f} ({emoji})"
    
    # 发送飞书
    success = send_feishu(config.get("feishu_webhook", ""), title, content, alert)
    
    if success:
        # 保存历史记录
        history_file = HISTORY_DIR / f"vix_{now.strftime('%Y-%m-%d')}.log"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(f"{now_str} | VIX={vix_value:.2f} | {level} | 已推送\n")
        logger.info("完成")
    else:
        logger.error("推送失败")

if __name__ == "__main__":
    run()
