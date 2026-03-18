#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日证券时报早报摘要 v5
火山云服务器 + DeepSeek API + 飞书推送
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
        return {"feishu_webhook": "", "llm": {}, "max_full_articles": 10}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "news_briefing.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ============================================================
#  标题过滤
# ============================================================
SKIP_PATTERNS = [r'\[\d{6}\]', r'\(\d{6}\)']
SKIP_KEYWORDS = [
    "日常公告", "年报+", "遗失声明", "拍卖公告", "送达公告",
    "今日公告导读", "报眼",
    "证券投资基金", "基金分红", "基金份额", "基金合同",
    "申购赎回", "大额申购", "恢复申购", "暂停申购",
    "定期定额", "转换转入", "费率优惠", "代销机构",
    "基金经理变更", "高级管理人员变更公告",
    "货币市场基金", "债券型", "混合型", "股票型",
    "基金销售", "流动性服务商", "持有人大会",
    "管理费", "托管费", "溢价风险提示",
    "年度报告摘要", "防范不法分子",
]

def should_skip(title):
    for pat in SKIP_PATTERNS:
        if re.search(pat, title): return True
    for kw in SKIP_KEYWORDS:
        if kw in title: return True
    return False

# ============================================================
#  证券时报抓取
# ============================================================
def fetch_stcn(date_str):
    articles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("请先安装依赖: pip install beautifulsoup4")
        return []

    d = datetime.strptime(date_str, "%Y-%m-%d")
    dp = d.strftime("%Y%m/%d")
    base = "https://epaper.stcn.com"
    url1 = f"{base}/col/{dp}/node_A001.html"
    logger.info(f"[证券时报] {url1}")
    try:
        r = requests.get(url1, timeout=30, headers=UA); r.encoding = "utf-8"
        if r.status_code != 200:
            logger.warning(f"[证券时报] HTTP {r.status_code}"); return articles
    except Exception as e:
        logger.error(f"[证券时报] {e}"); return articles

    soup = BeautifulSoup(r.text, "html.parser")
    pages = set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "node_A" in h and h.endswith(".html"):
            full = h if h.startswith("http") else base + (h if h.startswith("/") else f"/col/{dp}/{h}")
            pages.add(full)

    logger.info(f"[证券时报] {len(pages)} 个A版")
    all_pages = sorted(pages)[:12]
    if url1 not in all_pages:
        all_pages.insert(0, url1)

    for pu in all_pages:
        try:
            if pu != url1: time.sleep(0.3)
            r2 = requests.get(pu, timeout=20, headers=UA) if pu != url1 else r
            r2.encoding = "utf-8"
            for a in BeautifulSoup(r2.text, "html.parser").find_all("a", href=True):
                h = a["href"]
                if "content_" in h and h.endswith(".html"):
                    t = a.get_text(strip=True)
                    if t and len(t) > 3 and not should_skip(t):
                        articles.append({"source":"证券时报","title":t,
                            "url":h if h.startswith("http") else base+h})
        except: pass

    seen=set(); uniq=[]
    for a in articles:
        if a["title"] not in seen: seen.add(a["title"]); uniq.append(a)
    logger.info(f"[证券时报] {len(uniq)} 篇"); return uniq

def fetch_stcn_content(url):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    try:
        r=requests.get(url,timeout=20,headers=UA); r.encoding="utf-8"
        s=BeautifulSoup(r.text,"html.parser")
        for tag in s.find_all(["script","style","img"]): tag.decompose()
        div=s.find("div",class_="content") or s.find("div",id="ozoom") or s.find("article") or s.find("body")
        if div:
            lines=[l.strip() for l in div.get_text("\n",strip=True).split("\n") if l.strip()]
            return "\n".join(lines)[:2500]
        return ""
    except: return ""

# ============================================================
#  DeepSeek API（支持 Reasoner 模型）
# ============================================================
def call_llm(config, content):
    try:
        llm = config.get("llm", {})
        if not llm or "你的" in llm.get("api_key", ""):
            return None
    except:
        return None

    llm = config["llm"]
    api_url = llm.get("api_url", "")
    api_key = llm.get("api_key", "")
    model = llm.get("model", "")

    summary_config = config.get("summary_prompt", {})
    sys_p = summary_config.get("system", "总结报纸重点")
    usr_t = summary_config.get("user_template", "今日报纸：\n\n{content}\n\n请总结。")
    usr = usr_t.format(date=datetime.now().strftime("%Y年%m月%d日"), content=content)

    try:
        logger.info(f"[LLM] {model} ...")
        # Reasoner 模型需要更多 tokens 用于深度思考过程
        max_tok = 8000 if "reasoner" in model else 2000
        resp = requests.post(api_url, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }, json={
            "model": model,
            "messages": [{"role":"system","content":sys_p}, {"role":"user","content":usr}],
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
            "header":{"title":{"tag":"plain_text","content":title},"template":"blue"},
            "elements":[{"tag":"markdown","content":content[:4000]}]
        }}, timeout=10)
        logger.info(f"[飞书] {r.json()}")
    except Exception as e: logger.error(f"[飞书] {e}")

# ============================================================
#  主流程
# ============================================================
def run(date_str=None):
    config = load_config()
    if not date_str: date_str = datetime.now().strftime("%Y-%m-%d")
    d = datetime.strptime(date_str, "%Y-%m-%d")
    if d.weekday() >= 5: logger.info(f"{date_str} 周末"); return

    logger.info(f"{'='*20} {date_str} {'='*20}")
    articles = fetch_stcn(date_str)

    if not articles:
        logger.warning("无文章")
        return

    # 组装内容
    parts = ["=== 标题列表 ===\n"] + [f"• {a['title']}" for a in articles]
    max_n = config.get("max_full_articles", 10); fc = 0
    parts.append("\n\n=== 重点正文 ===\n")
    for a in articles:
        if fc >= max_n: break
        time.sleep(0.2)
        b = fetch_stcn_content(a["url"])
        if b and len(b) > 50:
            parts.append(f"\n--- {a['title']} ---\n{b[:1500]}")
            fc += 1

    full = "\n".join(parts)
    logger.info(f"共 {len(full)} 字")

    # AI总结
    summary = call_llm(config, full)
    if not summary:
        tl = "\n".join([f"• {a['title']}" for a in articles[:30]])
        summary = f"**AI总结失败，标题列表：**\n\n{tl}"

    # 推送飞书
    title = f"📰 {date_str} 证券早报"
    send_feishu(config.get("feishu_webhook", ""), title, summary)

    # 本地存档
    with open(HISTORY_DIR / f"{date_str}.md", "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{summary}\n\n---\n\n{full[:10000]}")
    logger.info("完成")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
