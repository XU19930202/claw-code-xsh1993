#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股隔夜新闻摘要
火山云 + DeepSeek + 飞书推送
数据源：东方财富美股导读
"""

import requests, re, json, yaml, logging, time, sys
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
        return {"feishu_webhook": "", "llm": {}}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "us_stock.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ============================================================
#  东方财富美股新闻抓取
# ============================================================

def fetch_eastmoney_us():
    """抓取东方财富美股导读 + 美股聚焦"""
    articles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("请先安装依赖: pip install beautifulsoup4")
        return []

    urls = [
        ("美股导读", "https://stock.eastmoney.com/a/cmgdd.html"),
        ("美股聚焦", "https://stock.eastmoney.com/a/cmgyw.html"),
    ]

    for section, url in urls:
        try:
            logger.info(f"[东方财富] 抓取{section}: {url}")
            r = requests.get(url, timeout=30, headers=UA); r.encoding = "utf-8"
            if r.status_code != 200:
                logger.warning(f"[东方财富] {section} HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                h = a["href"]
                t = a.get_text(strip=True)
                # 东方财富文章链接格式: finance.eastmoney.com/a/20260XXXXXXXXXX.html
                if t and len(t) > 8 and "eastmoney.com/a/" in h:
                    if h.startswith("//"): h = "https:" + h
                    elif not h.startswith("http"): h = "https://finance.eastmoney.com" + h
                    articles.append({"title": t, "url": h, "section": section})
        except Exception as e:
            logger.error(f"[东方财富] {section} 失败: {e}")

    # 去重
    seen = set(); uniq = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"]); uniq.append(a)

    logger.info(f"[东方财富] 共 {len(uniq)} 篇美股新闻")
    return uniq[:30]  # 最多30篇


def fetch_article_content(url):
    """抓取文章正文"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    try:
        r = requests.get(url, timeout=20, headers=UA); r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup.find_all(["script", "style", "img"]): tag.decompose()

        # 东方财富文章正文通常在 class="txtinfos" 或 id="ContentBody"
        div = (soup.find("div", class_="txtinfos") or
               soup.find("div", id="ContentBody") or
               soup.find("div", class_="content") or
               soup.find("article"))
        if div:
            lines = [l.strip() for l in div.get_text("\n", strip=True).split("\n") if l.strip()]
            return "\n".join(lines)[:2000]
        return ""
    except:
        return ""


# ============================================================
#  DeepSeek API
# ============================================================
def call_llm(config, content):
    try:
        llm = config.get("llm", {})
        if not llm or "你的" in llm.get("api_key", ""):
            return None
    except:
        return None

    llm = config["llm"]

    system_prompt = """你是一位服务于A股基金经理的海外市场分析师。
请阅读以下美股隔夜新闻，生成一份简洁的美股隔夜简报。

要求：
1. 分为【三大指数与市场概况】（2-3句话概括涨跌、成交、VIX等）
2. 【重要个股与板块】（3-5条，关注科技巨头、中概股、与A股联动的板块）
3. 【宏观与政策】（2-3条，美联储、经济数据、地缘政治等）
4. 【对今日A股的影响】（1-2条，直接给出操盘参考）
5. 如果有与AI算力、半导体、新能源相关的内容，加 🔥 标记
6. 语言简洁专业"""

    user_msg = f"以下是美股隔夜新闻（{datetime.now().strftime('%Y年%m月%d日')}）：\n\n{content}\n\n请生成美股隔夜简报。"

    try:
        logger.info(f"[LLM] {llm['model']} ...")
        # Reasoner模型需要更多tokens用于思考过程
        max_tok = 8000 if "reasoner" in llm["model"] else 1500
        resp = requests.post(llm["api_url"], headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm['api_key']}"
        }, json={
            "model": llm["model"],
            "messages": [{"role":"system","content":system_prompt}, {"role":"user","content":user_msg}],
            "max_tokens": max_tok, "temperature": 0.3
        }, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data:
            result = data["choices"][0]["message"]["content"]
            logger.info(f"[LLM] 完成 {len(result)} 字")
            return result
        return None
    except Exception as e:
        logger.error(f"[LLM] {e}"); return None


# ============================================================
#  飞书推送
# ============================================================
def send_feishu(wh, title, content):
    if not wh or "你的" in wh: return
    try:
        r = requests.post(wh, json={"msg_type":"interactive","card":{
            "header":{"title":{"tag":"plain_text","content":title},"template":"purple"},
            "elements":[{"tag":"markdown","content":content[:4000]}]
        }}, timeout=10)
        logger.info(f"[飞书] {r.json()}")
    except Exception as e: logger.error(f"[飞书] {e}")


# ============================================================
#  主流程
# ============================================================
def run():
    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")

    # 周末不跑（周六周日没有美股交易）
    # 但注意：周一早上需要看上周五的美股，所以周一要跑
    dow = datetime.now().weekday()
    if dow == 5 or dow == 6:  # 周六周日
        logger.info(f"{today} 周末，跳过"); return

    logger.info(f"{'='*20} 美股隔夜 {today} {'='*20}")

    # 1. 抓取
    articles = fetch_eastmoney_us()
    if not articles:
        logger.warning("无美股新闻"); return

    # 2. 组装
    parts = ["=== 美股隔夜新闻标题 ===\n"]
    parts += [f"• {a['title']}" for a in articles]

    # 抓前8篇正文
    fc = 0
    parts.append("\n\n=== 重点文章 ===\n")
    for a in articles:
        if fc >= 8: break
        time.sleep(0.2)
        body = fetch_article_content(a["url"])
        if body and len(body) > 50:
            parts.append(f"\n--- {a['title']} ---\n{body[:1500]}")
            fc += 1

    full = "\n".join(parts)
    logger.info(f"共 {len(full)} 字")

    # 3. AI总结
    summary = call_llm(config, full)
    if not summary:
        tl = "\n".join([f"• {a['title']}" for a in articles[:20]])
        summary = f"**AI总结失败，标题列表：**\n\n{tl}"

    # 4. 推送
    title = f"🇺🇸 {today} 美股隔夜简报"
    send_feishu(config.get("feishu_webhook", ""), title, summary)

    # 5. 存档
    with open(HISTORY_DIR / f"us_{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{summary}\n\n---\n\n{full[:10000]}")
    logger.info("完成")


if __name__ == "__main__":
    run()
