"""
特斯拉机器人(Optimus)新闻追踪器
==================================
数据源：
  - 百度资讯搜索
  - 新浪财经搜索
  - 36kr搜索
  - 东方财富资讯搜索

功能：
  1. 多源抓取特斯拉机器人相关新闻
  2. 关键词权重打分，过滤噪声
  3. 自动判断新闻对拓普的影响等级
  4. 去重后推送飞书
  5. 本地记录已推送新闻，避免重复

用法: python optimus_tracker.py
建议cron: 每天9:00和18:00各跑一次
"""

import requests
import json
import re
import os
import sys
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup

# 修复Windows控制台编码（支持emoji和中文）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ========== 配置区 ==========
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"

# 已推送新闻记录文件（避免重复推送）
HISTORY_FILE = os.path.expanduser("~/optimus_news_history.json")

# 搜索关键词组合
SEARCH_QUERIES = [
    "特斯拉 Optimus 机器人",
    "特斯拉 人形机器人 量产",
    "Tesla Optimus 供应链",
    "特斯拉 机器人 执行器",
    "特斯拉 机器人 拓普",
    "Optimus Gen3",
]

# 新闻评分关键词：关键词 → 权重
# 高权重 = 对投资决策影响大
SCORE_KEYWORDS = {
    # 量产进度（最核心）
    "量产": 10, "mass production": 10,
    "批量生产": 10, "规模化": 8,
    "产线": 8, "产能": 8,
    "下线": 9, "交付": 9,
    "月产": 10, "年产": 10,

    # 定点/供应链（直接关联拓普）
    "拓普": 15, "601689": 15,
    "定点": 12, "供应商": 8,
    "执行器": 12, "减速器": 10,
    "灵巧手": 10, "电机": 6,
    "液冷": 6,

    # 产品迭代
    "Gen3": 10, "Gen 3": 10,
    "Gen4": 10, "第三代": 10,
    "新一代": 8, "升级": 5,
    "Optimus": 5,

    # 商业化信号
    "售价": 8, "价格": 5,
    "订单": 10, "采购": 8,
    "工厂部署": 10, "工厂应用": 9,
    "商业化": 8,

    # 高管表态
    "马斯克": 6, "Elon": 6, "Musk": 6,
    "GTC": 7, "AI Day": 8,

    # 竞品动态（间接影响）
    "Figure": 4, "波士顿动力": 4,
    "1X": 3, "Agility": 3,
    "优必选": 4, "宇树": 4,

    # 负面信号
    "推迟": -8, "延期": -8, "delay": -8,
    "取消": -10, "暂停": -8,
    "不及预期": -7, "低于预期": -7,
}

# 影响等级阈值
IMPACT_THRESHOLDS = {
    "🔴 重大": 25,      # 量产/定点等核心事件
    "🟡 关注": 15,      # 产品迭代/供应链变化
    "🟢 知悉": 5,       # 一般动态
}

# =============================


def load_history():
    """加载已推送新闻的哈希记录"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"hashes": [], "last_update": ""}
    return {"hashes": [], "last_update": ""}


def save_history(history):
    """保存已推送新闻记录"""
    # 只保留最近500条
    history["hashes"] = history["hashes"][-500:]
    history["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False)


def news_hash(title):
    """生成新闻标题的哈希，用于去重"""
    # 去掉空格和标点后哈希，避免标题微小差异导致重复
    clean = re.sub(r"[\s\u3000，。！？、：；\u201c\u201d\u2018\u2019（）【】\-—·…]", "", title)
    return hashlib.md5(clean.encode()).hexdigest()[:12]


def score_news(title, summary=""):
    """
    对新闻进行关键词打分
    返回: (score, matched_keywords)
    """
    text = (title + " " + summary).lower()
    total_score = 0
    matched = []

    for keyword, weight in SCORE_KEYWORDS.items():
        if keyword.lower() in text:
            total_score += weight
            matched.append(f"{keyword}({weight:+d})")

    return total_score, matched


def get_impact_level(score):
    """根据分数判断影响等级"""
    for level, threshold in IMPACT_THRESHOLDS.items():
        if score >= threshold:
            return level
    return "⚪ 噪声"


# ============================================================
#  数据源1：百度资讯搜索
# ============================================================
def fetch_baidu_news(query, max_results=10):
    """百度资讯搜索"""
    results = []
    url = f"https://www.baidu.com/s?tn=news&rtt=4&bsst=1&cl=2&wd={quote(query)}"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 百度资讯结果解析
        items = soup.select("div.result")
        if not items:
            items = soup.select("div.c-container")

        for item in items[:max_results]:
            title_tag = item.select_one("h3 a") or item.select_one("a.news-title-font_1xS-F")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "")

            # 摘要
            summary_tag = item.select_one("span.c-font-normal") or item.select_one("div.c-span-last")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            # 来源和时间
            source_tag = item.select_one("span.c-color-gray") or item.select_one("p.c-author")
            source_text = source_tag.get_text(strip=True) if source_tag else ""

            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "summary": summary[:200],
                    "link": link,
                    "source": f"百度-{source_text}",
                    "query": query,
                })

    except Exception as e:
        print(f"  [百度] {query[:10]}... 失败: {e}")

    return results


# ============================================================
#  数据源2：新浪财经搜索
# ============================================================
def fetch_sina_news(query, max_results=10):
    """新浪财经搜索"""
    results = []
    url = (f"https://search.sina.com.cn/news?"
           f"q={quote(query)}&c=news&from=&col=&range=all&source=&country="
           f"&size=10&stime=&etime=&time=&dpc=0&a=")
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36"),
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        items = soup.select("div.box-result")
        for item in items[:max_results]:
            title_tag = item.select_one("h2 a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "")

            summary_tag = item.select_one("p.content")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            source_tag = item.select_one("span.fgray_time")
            source_text = source_tag.get_text(strip=True) if source_tag else ""

            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "summary": summary[:200],
                    "link": link,
                    "source": f"新浪-{source_text}",
                    "query": query,
                })

    except Exception as e:
        print(f"  [新浪] {query[:10]}... 失败: {e}")

    return results


# ============================================================
#  数据源3：东方财富资讯搜索
# ============================================================
def fetch_eastmoney_news(query, max_results=10):
    """东方财富资讯搜索API"""
    results = []
    url = (f"https://search-api-web.eastmoney.com/search/jsonp?"
           f"cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22"
           f"{quote(query)}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D"
           f"%2C%22client%22%3A%22web%22%2C%22clientType%22%3A%22web%22"
           f"%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B"
           f"%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22"
           f"%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1"
           f"%2C%22pageSize%22%3A{max_results}%7D%7D%7D")
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36"),
        "Referer": "https://so.eastmoney.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        # 去掉jsonp包裹
        text = resp.text
        json_match = re.search(r'jQuery\((.*)\)', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            articles = (data.get("result", {})
                        .get("cmsArticleWebOld", {})
                        .get("list", []))
            for item in articles[:max_results]:
                title = item.get("title", "")
                # 去掉HTML标签
                title = re.sub(r"<[^>]+>", "", title)
                summary = item.get("content", "")[:200]
                summary = re.sub(r"<[^>]+>", "", summary)
                link = item.get("url", "")
                date = item.get("date", "")

                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": f"东财-{date}",
                        "query": query,
                    })

    except Exception as e:
        print(f"  [东财] {query[:10]}... 失败: {e}")

    return results


# ============================================================
#  数据源4：36kr搜索
# ============================================================
def fetch_36kr_news(query, max_results=10):
    """36kr搜索API"""
    results = []
    url = f"https://gateway.36kr.com/api/mis/nav/search/resultCount"
    payload = {
        "partner_id": "wap",
        "param": {
            "siteId": 1,
            "platformId": 2,
            "keyword": query,
        },
    }

    # 36kr的搜索API比较复杂，简化处理
    search_url = f"https://36kr.com/search/articles/{quote(query)}"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36"),
    }

    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        items = soup.select("div.search-article-item") or soup.select("a.article-item-link")
        for item in items[:max_results]:
            title_tag = item.select_one("h3") or item.select_one("p.title")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link_tag = item if item.name == "a" else item.select_one("a")
            link = link_tag.get("href", "") if link_tag else ""
            if link and not link.startswith("http"):
                link = f"https://36kr.com{link}"

            summary_tag = item.select_one("p.summary") or item.select_one("p.description")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "summary": summary[:200],
                    "link": link,
                    "source": "36kr",
                    "query": query,
                })

    except Exception as e:
        print(f"  [36kr] {query[:10]}... 失败: {e}")

    return results


# ============================================================
#  主逻辑：聚合、评分、去重、推送
# ============================================================
def fetch_all_news():
    """从所有数据源获取新闻"""
    all_news = []

    for query in SEARCH_QUERIES:
        print(f"  搜索: {query}")

        # 百度
        news = fetch_baidu_news(query, max_results=5)
        all_news.extend(news)
        time.sleep(1)

        # 东方财富
        news = fetch_eastmoney_news(query, max_results=5)
        all_news.extend(news)
        time.sleep(0.5)

        # 新浪（只对前两个query搜，避免太慢）
        if SEARCH_QUERIES.index(query) < 2:
            news = fetch_sina_news(query, max_results=5)
            all_news.extend(news)
            time.sleep(1)

        # 36kr（只对前两个query搜）
        if SEARCH_QUERIES.index(query) < 2:
            news = fetch_36kr_news(query, max_results=5)
            all_news.extend(news)
            time.sleep(0.5)

    print(f"  共获取 {len(all_news)} 条原始新闻")
    return all_news


def deduplicate_news(all_news, history):
    """去重：标题相似的只保留一条，已推送的跳过"""
    seen_hashes = set(history.get("hashes", []))
    unique = {}

    for item in all_news:
        h = news_hash(item["title"])
        if h in seen_hashes:
            continue
        if h in unique:
            # 保留分数更高的
            existing_score = score_news(unique[h]["title"], unique[h]["summary"])[0]
            new_score = score_news(item["title"], item["summary"])[0]
            if new_score > existing_score:
                unique[h] = item
        else:
            unique[h] = item

    return list(unique.values()), list(unique.keys())


def process_and_rank(news_list):
    """评分、排序"""
    scored = []
    for item in news_list:
        score, keywords = score_news(item["title"], item["summary"])
        if score < 3:
            continue  # 过滤纯噪声

        item["score"] = score
        item["keywords"] = keywords
        item["impact"] = get_impact_level(score)
        scored.append(item)

    # 按分数降序
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def format_news_report(scored_news):
    """生成推送报告"""
    lines = []
    lines.append(f"🤖 特斯拉机器人(Optimus)新闻追踪")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"📡 本次扫描到 {len(scored_news)} 条有效新闻")

    if not scored_news:
        lines.append("")
        lines.append("暂无新的相关新闻。")
        return "\n".join(lines)

    # 按影响等级分组
    critical = [n for n in scored_news if n["score"] >= 25]
    important = [n for n in scored_news if 15 <= n["score"] < 25]
    normal = [n for n in scored_news if 5 <= n["score"] < 15]
    minor = [n for n in scored_news if 3 <= n["score"] < 5]

    if critical:
        lines.append("")
        lines.append(f"🔴 重大信号 ({len(critical)}条)")
        for n in critical[:5]:
            lines.append(f"  [{n['score']}分] {n['title']}")
            if n["keywords"]:
                lines.append(f"    命中: {', '.join(n['keywords'][:5])}")
            if n["link"]:
                lines.append(f"    链接: {n['link']}")

    if important:
        lines.append("")
        lines.append(f"🟡 值得关注 ({len(important)}条)")
        for n in important[:5]:
            lines.append(f"  [{n['score']}分] {n['title']}")
            if n["keywords"]:
                lines.append(f"    命中: {', '.join(n['keywords'][:4])}")

    if normal:
        lines.append("")
        lines.append(f"🟢 一般动态 ({len(normal)}条)")
        for n in normal[:5]:
            lines.append(f"  [{n['score']}分] {n['title']}")

    if minor and not critical and not important:
        lines.append("")
        lines.append(f"⚪ 低相关 ({len(minor)}条)")
        for n in minor[:3]:
            lines.append(f"  [{n['score']}分] {n['title']}")

    # 投资提示
    if critical:
        lines.append("")
        lines.append(f"═══ 投资提示 ═══")
        has_positive = any(n["score"] > 0 for n in critical)
        has_negative = any(any("推迟" in k or "延期" in k or "取消" in k
                              for k in n["keywords"]) for n in critical)
        if has_negative:
            lines.append(f"  ⚠️ 检测到负面信号（推迟/延期），需立即评估对拓普估值的影响")
            lines.append(f"  → 检查拓普监控脚本中的Optimus里程碑是否需要更新")
        elif has_positive:
            lines.append(f"  ✅ 积极信号，可能触发拓普机器人业务估值重估")
            lines.append(f"  → 关注拓普股价对消息的反应，评估是否已price in")

    return "\n".join(lines)


def push_to_feishu(content, webhook):
    if not webhook:
        return
    # 飞书text消息限制4096字符
    if len(content) > 4000:
        content = content[:3950] + "\n\n...（内容截断，完整版请查看日志）"
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        print(f"飞书推送: {'成功' if resp.status_code == 200 else '失败'}")
    except Exception as e:
        print(f"飞书推送异常: {e}")


def main():
    print(f"特斯拉机器人新闻追踪器")
    print(f"{'=' * 50}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # 加载历史
    history = load_history()
    print(f"历史记录: {len(history.get('hashes', []))}条")

    # 抓取新闻
    print("\n正在从多个数据源抓取...")
    all_news = fetch_all_news()

    # 去重
    print("\n去重处理...")
    unique_news, new_hashes = deduplicate_news(all_news, history)
    print(f"去重后: {len(unique_news)}条新新闻")

    # 评分排序
    print("\n评分排序...")
    scored = process_and_rank(unique_news)
    print(f"有效新闻（评分≥3）: {len(scored)}条")

    # 生成报告
    report = format_news_report(scored)
    print()
    print(report)

    # 推送（只在有评分≥15的新闻时推送，避免噪声打扰）
    has_important = any(n["score"] >= 15 for n in scored)
    if has_important:
        push_to_feishu(report, FEISHU_WEBHOOK)
    elif scored:
        # 低分新闻也推送，但标注为日常
        push_to_feishu(report, FEISHU_WEBHOOK)
    else:
        print("\n无新闻，跳过推送")

    # 更新历史
    history["hashes"].extend(new_hashes)
    save_history(history)
    print(f"\n历史记录已更新: {len(history['hashes'])}条")


if __name__ == "__main__":
    main()
