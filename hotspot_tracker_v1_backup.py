#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股热点关键词追踪系统 v3
每日从多源抓取新闻 → 分词统计 → 排名对比 → 识别升温/降温 → 飞书推送
"""

import requests, re, json, yaml, logging, time, sys, os
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

try:
    import jieba
    import jieba.analyse
except ImportError:
    print("请先安装依赖: pip install jieba")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
HISTORY_DIR = SCRIPT_DIR / "history"
RANK_DIR = SCRIPT_DIR / "hotspot_data"
HISTORY_DIR.mkdir(exist_ok=True)
RANK_DIR.mkdir(exist_ok=True)

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "hotspot.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ============================================================
#  自定义词典
# ============================================================
CUSTOM_WORDS = [
    "人工智能", "大模型", "算力", "液冷", "光模块", "存储芯片", "HBM",
    "人形机器人", "具身智能", "低空经济", "商业航天", "核聚变",
    "并购重组", "控制权转让", "新质生产力", "科创板", "创业板", "北交所",
    "半导体", "芯片", "国产替代", "信创", "AI算力", "AI应用",
    "新型储能", "固态电池", "钙钛矿", "光伏", "锂电",
    "中东局势", "油价", "黄金", "美联储", "降息", "加息",
    "北向资金", "港股通", "南向资金",
    "军工", "航天", "无人机", "卫星互联网",
    "创新药", "生物医药", "CXO", "多肽",
    "量子计算", "量子通信", "脑机接口",
    "DeepSeek", "大语言模型", "智能体", "OpenClaw",
    "互联互通", "十五五", "两会", "政府工作报告",
    "特朗普", "关税", "制裁", "霍尔木兹海峡",
    "机器人", "减速器", "伺服电机",
    "数据中心", "算力租赁", "智算中心",
    "可控核聚变", "核电", "氢能",
    "自动驾驶", "智能驾驶", "车路协同",
]

# ============================================================
#  停用词（完整版）
# ============================================================
STOP_WORDS = set([
    # 通用词
    "公司", "股份", "有限", "集团", "中国", "全国", "关于", "我国",
    "发展", "建设", "推动", "加强", "支持", "促进", "实现", "提升",
    "创新", "改革", "经济", "市场", "企业", "产业", "技术", "服务",
    "投资", "基金", "证券", "股票", "上市", "交易", "科技",
    "报告", "工作", "会议", "代表", "委员", "董事", "总裁", "董事长",
    "亿元", "万元", "同比", "环比", "增长", "下降", "下滑",
    "今日", "昨日", "本周", "上周", "近期", "目前", "当前", "预计",
    "全球", "国际", "国内", "行业", "领域", "方面", "方向",
    "公告", "披露", "信息", "数据", "情况", "问题",
    # 年份数字
    "2024", "2025", "2026", "2027", "年度", "季度", "月份",
    "第一", "第二", "第三", "第四", "第五",
    "第一次", "第二次", "第三次", "第四次", "第五次",
    "ST", "PDF",
    "10", "20", "30", "50", "100", "15", "12",
    # 公告类
    "系列", "日常", "有限公司", "股东", "提示性", "子公司",
    "控股", "部分", "质押", "担保", "转债", "联社",
    "赎回", "募集", "进展", "风险", "资金", "回购",
    "解除", "限售", "流通", "减持", "增持", "股权", "转让",
    "债券", "注销", "实施", "到期", "摘牌", "持股",
    "变更", "登记", "届满", "异常", "波动", "停牌", "复牌",
    "可能", "终止", "相关", "提示", "事项", "变动",
    "审议", "通过", "决议", "召开", "临时",
    "收到", "通知", "获得", "取得", "完成", "签署", "协议",
    "全资", "闲置", "现金", "管理", "使用", "现金管理",
    "配套", "补充", "流动", "注册", "资本",
    "营业", "执照", "工商", "专利", "证书", "高新", "认定",
    "自愿", "回复", "问询", "申报", "受理", "批准", "备案",
    "首次", "公开", "发行", "限制性", "激励", "计划",
    "期权", "授予", "行权", "解锁", "申请",
    "年报", "季报", "简报", "快报", "摘要",
    "销售", "触及", "提供", "整数", "权益", "整数倍",
    "股票交易", "公司股票", "科技股份", "股东权益", "权益变动",
    "人大代表", "政协委员",
    "转股", "付息", "兑付", "提前",
    # 地名
    "上海", "北京", "深圳", "广东", "江苏", "浙江", "天津", "重庆",
    # 动词形容词
    "办理", "业务", "开放", "期间", "持有", "份额",
    "申购", "定期", "混合", "指数", "开放式",
    "主动", "被动", "规模", "净值", "收益",
    "调整", "优化", "落实", "推进", "深化", "统筹",
    "保障", "加快", "积极", "稳步", "持续", "进一步",
    "重大", "重要", "主要", "有关", "以及", "其中",
    "根据", "按照", "为了", "对于", "日电",
    "食品", "新能", "三大", "电子",
])

def init_jieba():
    for w in CUSTOM_WORDS:
        jieba.add_word(w)
    logger.info(f"[jieba] {len(CUSTOM_WORDS)} 自定义词")

# ============================================================
#  新闻抓取
# ============================================================
def fetch_eastmoney_news():
    titles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("请先安装依赖: pip install beautifulsoup4")
        return []

    urls = [
        "https://stock.eastmoney.com/a/czqyw.html",
        "https://stock.eastmoney.com/a/cgnjj.html",
        "https://stock.eastmoney.com/a/cmgdd.html",
        "https://finance.eastmoney.com/a/ccjxw.html",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=20, headers=UA); r.encoding = "utf-8"
            for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
                t = a.get_text(strip=True)
                if t and len(t) > 8 and "eastmoney.com/a/" in a["href"]:
                    titles.append(t)
            time.sleep(0.3)
        except: pass
    logger.info(f"[东方财富] {len(titles)} 条")
    return titles

def fetch_stcn_titles(date_str):
    titles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    d = datetime.strptime(date_str, "%Y-%m-%d")
    url = f"https://epaper.stcn.com/col/{d.strftime('%Y%m/%d')}/node_A001.html"
    try:
        r = requests.get(url, timeout=20, headers=UA); r.encoding = "utf-8"
        if r.status_code == 200:
            for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
                if "content_" in a["href"]:
                    t = a.get_text(strip=True)
                    if t and len(t) > 4: titles.append(t)
    except: pass
    logger.info(f"[证券时报] {len(titles)} 条")
    return titles

def fetch_cls_telegraph():
    titles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    try:
        r = requests.get("https://www.cls.cn/telegraph", timeout=20, headers=UA)
        r.encoding = "utf-8"
        for el in BeautifulSoup(r.text, "html.parser").find_all(["span","div","p"], class_=re.compile("telegraph|content|title")):
            t = el.get_text(strip=True)
            if t and 10 < len(t) < 200: titles.append(t)
    except: pass
    logger.info(f"[财联社] {len(titles)} 条")
    return titles

# ============================================================
#  关键词提取
# ============================================================
def extract_keywords(titles):
    all_text = " ".join(titles)
    tfidf_words = jieba.analyse.extract_tags(all_text, topK=100, withWeight=True)

    words = jieba.lcut(all_text)
    words = [w for w in words if len(w) >= 2 and w not in STOP_WORDS]
    words = [w for w in words if not re.match(r'^[\d%\.\-\+]+$', w)]
    freq = Counter(words)

    scores = {}
    for word, weight in tfidf_words:
        if word in STOP_WORDS or len(word) < 2: continue
        if re.match(r'^[\d%\.\-\+]+$', word): continue
        count = freq.get(word, 0)
        scores[word] = round(weight * max(count, 1), 4)

    return sorted(scores.items(), key=lambda x: -x[1])[:50]

def load_history_ranks(days=7):
    history = {}
    for i in range(1, days+1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        path = RANK_DIR / f"{d}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                history[d] = json.load(f)
    return history

def save_today_rank(date_str, ranked):
    data = {word: {"rank": i+1, "score": score} for i, (word, score) in enumerate(ranked)}
    with open(RANK_DIR / f"{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def analyze_trends(today_ranked, history):
    results = []
    today_dict = {word: i+1 for i, (word, _) in enumerate(today_ranked)}
    for word, score in today_ranked:
        rank_today = today_dict[word]
        past_ranks = []
        for ds in sorted(history.keys()):
            if word in history[ds]: past_ranks.append(history[ds][word]["rank"])
            else: past_ranks.append(999)

        if not past_ranks:
            trend, desc = "NEW", "🆕 新晋"
        else:
            avg = sum(past_ranks) / len(past_ranks)
            if len(past_ranks) >= 2 and all(r > rank_today for r in past_ranks[-2:]) and rank_today <= 20:
                trend, desc = "SURGE", "🚀 连续升温"
            elif rank_today < avg - 5:
                trend, desc = "UP", "🔥 升温"
            elif rank_today > avg + 5:
                trend, desc = "DOWN", "⬇️ 降温"
            else:
                trend, desc = "STABLE", "➡️ 稳定"

        results.append({"word": word, "rank": rank_today, "score": score,
            "trend": trend, "trend_desc": desc, "past_ranks": past_ranks[-5:]})
    return results

def generate_report(trends):
    lines = ["**📊 今日热词Top15**\n"]
    for t in trends[:15]:
        past = "→".join([str(r) if r<100 else "-" for r in t["past_ranks"]]) if t["past_ranks"] else ""
        hist = f"（{past}）" if past else ""
        lines.append(f"{t['rank']}. {t['trend_desc']} **{t['word']}** {hist}")

    surging = [t for t in trends if t["trend"] in ("SURGE","UP") and t["rank"] <= 30]
    if surging:
        lines.append("\n\n**🔥 正在升温**\n")
        for t in surging:
            past = "→".join([str(r) if r<100 else "-" for r in t["past_ranks"]])
            lines.append(f"• **{t['word']}** 排名{t['rank']} ← {past}")

    new_w = [t for t in trends if t["trend"]=="NEW" and t["rank"]<=20]
    if new_w:
        lines.append("\n\n**🆕 新晋热词**\n")
        for t in new_w:
            lines.append(f"• **{t['word']}** 排名{t['rank']}")
    return "\n".join(lines)

# ============================================================
#  DeepSeek
# ============================================================
def call_llm(config, report, titles_sample):
    try:
        llm = config.get("llm", {})
        if not llm or "你的" in llm.get("api_key", ""):
            return None
    except:
        return None

    llm = config["llm"]
    sys_p = """你是A股市场热点分析师。根据今日热点关键词排名和趋势，给出简洁分析：
1.【当前主线】2-3条核心投资主线
2.【升温方向】从边缘走向主流的方向
3.【降温信号】正在退潮的热点
4.【操作建议】1-2条具体建议
300字以内。"""
    usr = f"今日热点：\n{report}\n\n部分标题：\n" + "\n".join(titles_sample[:20])
    try:
        logger.info(f"[LLM] {llm['model']} ...")
        resp = requests.post(llm["api_url"], headers={
            "Content-Type":"application/json","Authorization":f"Bearer {llm['api_key']}"
        }, json={"model":llm['model'],"messages":[{"role":"system","content":sys_p},{"role":"user","content":usr}],
            "max_tokens":800,"temperature":0.3}, timeout=120)
        resp.raise_for_status(); data = resp.json()
        if "choices" in data: return data["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        logger.error(f"[LLM] {e}"); return None

# ============================================================
#  飞书
# ============================================================
def send_feishu(wh, title, content):
    if not wh or "你的" in wh: return
    try:
        requests.post(wh, json={"msg_type":"interactive","card":{
            "header":{"title":{"tag":"plain_text","content":title},"template":"orange"},
            "elements":[{"tag":"markdown","content":content[:4000]}]
        }}, timeout=10)
        logger.info("[飞书] OK")
    except Exception as e: logger.error(f"[飞书] {e}")

# ============================================================
#  主流程
# ============================================================
def run():
    try:
        config = load_config()
    except FileNotFoundError:
        logger.warning("未找到config.yaml，跳过飞书推送和AI功能")
        config = {"feishu_webhook": "", "llm": {}}

    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"{'='*20} 热点追踪 {today} {'='*20}")

    init_jieba()

    all_titles = fetch_eastmoney_news() + fetch_stcn_titles(today) + fetch_cls_telegraph()
    if len(all_titles) < 10:
        logger.warning(f"标题太少({len(all_titles)})"); return
    logger.info(f"共 {len(all_titles)} 条")

    ranked = extract_keywords(all_titles)
    save_today_rank(today, ranked)
    logger.info(f"Top5: {ranked[:5]}")

    history = load_history_ranks(7)
    trends = analyze_trends(ranked, history)
    report = generate_report(trends)

    ai = call_llm(config, report, all_titles)
    full = report + ("\n\n---\n\n**🤖 AI热点分析**\n\n" + ai if ai else "")

    title = f"🔥 {today} A股热点追踪"
    send_feishu(config.get("feishu_webhook", ""), title, full)

    with open(HISTORY_DIR / f"hotspot_{today}.md", "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{full}")
    logger.info("完成")

if __name__ == "__main__":
    run()
