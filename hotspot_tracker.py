#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股热点追踪系统 V2
改进点：
1. 停用词过滤 — 去除"突传/重磅/迎来"等无实质含义的媒体高频词
2. 实体补全 — 短名映射到完整公司/概念名称
3. 排名展示优化 — ↑5 / ↓3 / 新入榜 / 持平，一眼看动量
4. AI分析prompt重构 — 聚焦增量信息、关联具体标的、对比昨日差异
5. 历史追踪 — 连续在榜天数标记，支持周度趋势
"""

import json
import os
import sys
import time
import yaml
import re
import requests
import logging
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

# Windows终端编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import jieba
    import jieba.analyse
except ImportError:
    print("请先安装依赖: pip install jieba")
    import sys
    sys.exit(1)

# ============================================================
# 配置区 — 根据你的实际环境修改
# ============================================================
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
HISTORY_DIR = SCRIPT_DIR / "history"
RANK_DIR = SCRIPT_DIR / "hotspot_data"
HISTORY_DIR.mkdir(exist_ok=True)
RANK_DIR.mkdir(exist_ok=True)

# V2使用的独立历史文件
HISTORY_FILE = SCRIPT_DIR / "hotspot_data" / "history_v2.json"

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"feishu_webhook": "", "llm": {}}

def load_config_yaml():
    """加载YAML配置"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

# 获取API配置
DEEPSEEK_API_KEY = None
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
FEISHU_WEBHOOK_URL = None

config = load_config()
if config:
    if "llm" in config and config["llm"]:
        DEEPSEEK_API_KEY = config["llm"].get("api_key")
        DEEPSEEK_BASE_URL = config["llm"].get("api_url", "https://api.deepseek.com/v1")
    FEISHU_WEBHOOK_URL = config.get("feishu_webhook", "")

# 最大展示热词数
TOP_N = 20

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "hotspot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ============================================================
# 1. 停用词表 — 过滤无实质投资含义的媒体高频词
# ============================================================
STOP_WORDS = {
    # 动词类（新闻标题常用）
    "突传", "迎来", "发起", "重磅", "曝光", "紧急", "突发",
    "刚刚", "官宣", "罕见", "暴雷", "实锤", "出手", "宣布",
    "惊现", "大动作", "放大招", "火速", "深夜", "最新",
    # 形容词/副词类
    "超预期", "史无前例", "首次", "再次", "持续", "加速",
    # 通用名词类（信息量极低）
    "概念股", "龙头股", "题材", "板块", "方向", "机会",
    "利好", "利空", "消息", "公告", "点评", "解读",
    # 媒体/平台词
    "说明书", "关联方",
    # V1中的通用停用词
    "公司", "股份", "有限", "集团", "中国", "全国", "关于", "我国",
    "发展", "建设", "推动", "加强", "支持", "促进", "实现", "提升",
    "创新", "改革", "经济", "市场", "企业", "产业", "技术", "服务",
    "投资", "基金", "证券", "股票", "上市", "交易", "科技",
    "报告", "工作", "会议", "代表", "委员", "董事", "总裁", "董事长",
    "亿元", "万元", "同比", "环比", "增长", "下降", "下滑",
    "今日", "昨日", "本周", "上周", "近期", "目前", "当前", "预计",
    "全球", "国际", "国内", "行业", "领域", "方面", "方向",
    "公告", "披露", "信息", "数据", "情况", "问题",
    "年度", "季度", "月份",
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
}

STOP_WORDS_PARTIAL = [
    "最新消息", "深度解析", "全面分析", "独家",
]


# ============================================================
# 2. 自定义词典 — jieba分词使用
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

def init_jieba():
    """初始化jieba分词器"""
    for w in CUSTOM_WORDS:
        jieba.add_word(w)
    logger.info(f"[jieba] {len(CUSTOM_WORDS)} 自定义词")


# ============================================================
# 3. 实体补全映射表 — 截断简称→完整名称
# ============================================================
ENTITY_MAP = {
    # 公司简称补全
    "南威": "南威软件",
    "宏明": "宏明电子",
    "中复": "中复神鹰",
    "神鹰": "中复神鹰",
    "洪通": "亨通光电",
    "九鼎": "九鼎投资",
    "华泰": "华泰证券",
    "中证": "中证指数/中证系列产品",
    "清华": "清华系概念",
    # 概念补全
    "科创板": "科创板/科创50",
    "过户": "股权过户/控制权转让",
    # 根据你的持仓和关注列表持续补充
}


# ============================================================
# 4. 数据获取（使用V1的现有数据源）
# ============================================================
def fetch_eastmoney_news():
    """从东方财富获取新闻标题"""
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
            r = requests.get(url, timeout=20, headers=UA)
            r.encoding = "utf-8"
            for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
                t = a.get_text(strip=True)
                if t and len(t) > 8 and "eastmoney.com/a/" in a["href"]:
                    titles.append(t)
            time.sleep(0.3)
        except:
            pass
    logger.info(f"[东方财富] {len(titles)} 条")
    return titles


def fetch_stcn_titles(date_str):
    """从证券时报获取标题"""
    titles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    d = datetime.strptime(date_str, "%Y-%m-%d")
    url = f"https://epaper.stcn.com/col/{d.strftime('%Y%m/%d')}/node_A001.html"
    try:
        r = requests.get(url, timeout=20, headers=UA)
        r.encoding = "utf-8"
        if r.status_code == 200:
            for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
                if "content_" in a["href"]:
                    t = a.get_text(strip=True)
                    if t and len(t) > 4:
                        titles.append(t)
    except:
        pass
    logger.info(f"[证券时报] {len(titles)} 条")
    return titles


def fetch_cls_telegraph():
    """从财联社获取电报"""
    titles = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    try:
        r = requests.get("https://www.cls.cn/telegraph", timeout=20, headers=UA)
        r.encoding = "utf-8"
        for el in BeautifulSoup(r.text, "html.parser").find_all(["span", "div", "p"], class_=re.compile("telegraph|content|title")):
            t = el.get_text(strip=True)
            if t and 10 < len(t) < 200:
                titles.append(t)
    except:
        pass
    logger.info(f"[财联社] {len(titles)} 条")
    return titles


def fetch_raw_keywords():
    """
    从多数据源获取新闻，提取关键词
    返回格式: [{"keyword": "发行股票", "rank": 1, "heat": 850, "source": "eastmoney"}, ...]
    """
    # 获取所有新闻标题
    today = datetime.now().strftime("%Y-%m-%d")
    all_titles = fetch_eastmoney_news() + fetch_stcn_titles(today) + fetch_cls_telegraph()

    if len(all_titles) < 10:
        logger.warning(f"标题太少({len(all_titles)})")
        return []

    # 提取关键词
    all_text = " ".join(all_titles)
    tfidf_words = jieba.analyse.extract_tags(all_text, topK=100, withWeight=True)

    words = jieba.lcut(all_text)
    words = [w for w in words if len(w) >= 2 and w not in STOP_WORDS]
    words = [w for w in words if not re.match(r'^[\d%\.\-\+]+$', w)]
    freq = Counter(words)

    scores = {}
    for word, weight in tfidf_words:
        if word in STOP_WORDS or len(word) < 2:
            continue
        if re.match(r'^[\d%\.\-\+]+$', word):
            continue
        count = freq.get(word, 0)
        scores[word] = round(weight * max(count, 1), 4)

    # 排序并转换为V2格式
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:100]
    result = []
    for i, (keyword, score) in enumerate(ranked):
        # 计算热度指数（基于分数归一化）
        heat = min(1000, max(0, int(score * 1000)))
        result.append({
            "keyword": keyword,
            "rank": i + 1,
            "heat": heat
        })

    logger.info(f"共 {len(all_titles)} 条新闻，提取 {len(result)} 个关键词")
    return result


# ============================================================
# 5. 数据清洗与过滤
# ============================================================
def is_stop_word(keyword):
    """判断是否为停用词"""
    if keyword in STOP_WORDS:
        return True
    for partial in STOP_WORDS_PARTIAL:
        if partial in keyword:
            return True
    return False


def enrich_keyword(keyword):
    """实体补全：短名→完整名"""
    return ENTITY_MAP.get(keyword, keyword)


def classify_keyword(keyword):
    """
    关键词分类，用于后续分析
    返回: "公司" | "概念" | "政策" | "事件" | "券商" | "其他"
    """
    company_hints = ["股份", "科技", "电子", "软件", "证券", "投资",
                     "能源", "矿业", "电力", "沈飞", "曙光"]
    concept_hints = ["AI", "科创板", "芯片", "半导体", "液冷", "光模块",
                     "军工", "碳纤维", "甲醇", "新能源", "算力",
                     "国产替代", "并购", "重组"]
    policy_hints = ["中证", "监管", "央行", "发改委", "两会", "政策"]
    event_hints = ["伊朗", "地缘", "关税", "制裁", "冲突"]
    broker_hints = ["华泰", "中信", "国泰", "海通", "招商"]

    enriched = enrich_keyword(keyword)
    for hint in company_hints:
        if hint in enriched:
            return "公司"
    for hint in concept_hints:
        if hint in enriched:
            return "概念"
    for hint in policy_hints:
        if hint in enriched:
            return "政策"
    for hint in event_hints:
        if hint in enriched:
            return "事件"
    for hint in broker_hints:
        if hint in enriched:
            return "券商"
    return "其他"


def process_keywords(raw_data):
    """主清洗流程：过滤→补全→分类→排名"""
    filtered = []
    removed = []

    for item in raw_data:
        kw = item["keyword"]
        if is_stop_word(kw):
            removed.append(kw)
            continue
        enriched = enrich_keyword(kw)
        category = classify_keyword(kw)
        filtered.append({
            "keyword": enriched,
            "original": kw,
            "rank": item["rank"],
            "heat": item.get("heat", 0),
            "category": category,
        })

    # 按原始排名排序，取TOP_N
    filtered.sort(key=lambda x: x["rank"])
    filtered = filtered[:TOP_N]

    return filtered, removed


# ============================================================
# 6. 历史对比与趋势标记
# ============================================================
def load_history():
    """加载历史数据"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history):
    """保存历史数据"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def compute_trends(today_keywords, history):
    """
    计算趋势标记：
    - 排名变化：↑N / ↓N / 持平 / 新入榜
    - 连续在榜天数
    - 热度变化趋势
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    yesterday_data = history.get(yesterday_str, {})
    yesterday_kw_map = {}
    if yesterday_data:
        for item in yesterday_data.get("keywords", []):
            yesterday_kw_map[item["keyword"]] = item

    results = []
    for item in today_keywords:
        kw = item["keyword"]
        trend_info = {**item}

        # 排名变化
        if kw in yesterday_kw_map:
            old_rank = yesterday_kw_map[kw]["rank"]
            new_rank = item["rank"]
            rank_change = old_rank - new_rank  # 正数=上升
            if rank_change > 0:
                trend_info["trend_label"] = f"↑{rank_change}"
                trend_info["trend_type"] = "up"
            elif rank_change < 0:
                trend_info["trend_label"] = f"↓{abs(rank_change)}"
                trend_info["trend_type"] = "down"
            else:
                trend_info["trend_label"] = "→持平"
                trend_info["trend_type"] = "stable"
        else:
            trend_info["trend_label"] = "🆕新入榜"
            trend_info["trend_type"] = "new"

        # 连续在榜天数
        consecutive_days = 1
        for i in range(1, 30):  # 最多回溯30天
            check_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            check_data = history.get(check_date, {})
            check_kws = [x["keyword"] for x in check_data.get("keywords", [])]
            if kw in check_kws:
                consecutive_days += 1
            else:
                break
        trend_info["consecutive_days"] = consecutive_days

        results.append(trend_info)

    # 计算昨日消失的关键词
    disappeared = []
    today_kw_set = {item["keyword"] for item in today_keywords}
    for kw, info in yesterday_kw_map.items():
        if kw not in today_kw_set and info["rank"] <= 15:
            disappeared.append({"keyword": kw, "yesterday_rank": info["rank"]})
    disappeared.sort(key=lambda x: x["yesterday_rank"])

    return results, disappeared


def update_history(history, today_keywords):
    """更新历史记录，保留最近30天"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    history[today_str] = {
        "keywords": today_keywords,
        "timestamp": datetime.now().isoformat(),
    }
    # 清理30天前的数据
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    old_keys = [k for k in history if k < cutoff]
    for k in old_keys:
        del history[k]
    return history


# ============================================================
# 7. 格式化输出
# ============================================================
def format_trend_icon(trend_type):
    """趋势图标"""
    icons = {
        "up": "🚀",
        "down": "📉",
        "stable": "➡️",
        "new": "🆕",
    }
    return icons.get(trend_type, "")


def format_category_tag(category):
    """分类标签"""
    tags = {
        "公司": "🏢",
        "概念": "💡",
        "政策": "📋",
        "事件": "🌍",
        "券商": "🏦",
        "其他": "📌",
    }
    return tags.get(category, "📌")


def format_consecutive_badge(days):
    """连续在榜标记"""
    if days >= 5:
        return f" 🔥连续{days}天"
    elif days >= 3:
        return f" ⏳连续{days}天"
    return ""


def build_feishu_message(trend_data, disappeared, removed_words, overall_heat):
    """
    构建飞书富文本消息
    返回: 飞书消息体字符串
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四",
                   4: "周五", 5: "周六", 6: "周日"}
    weekday = weekday_map[datetime.now().weekday()]

    lines = []
    lines.append(f"🔥 {today_str} ({weekday}) A股热点追踪 V2\n")

    # ---- 热度概览 ----
    lines.append(f"📊 整体热度指数: {overall_heat}")
    if overall_heat > 800:
        lines.append("  ▸ 市场情绪高涨，注意追高风险")
    elif overall_heat < 400:
        lines.append("  ▸ 市场整体清淡，缺乏明确主线")
    else:
        lines.append("  ▸ 市场情绪适中，关注结构性机会")
    lines.append("")

    # ---- 今日热词TOP榜 ----
    lines.append("📈 今日热词排行")
    lines.append("─" * 28)

    for i, item in enumerate(trend_data, 1):
        icon = format_trend_icon(item["trend_type"])
        cat = format_category_tag(item["category"])
        badge = format_consecutive_badge(item["consecutive_days"])
        heat_bar = "█" * max(1, item.get("heat", 0) // 100)

        line = (
            f"{i:>2}. {icon} {cat} {item['keyword']}"
            f"  ({item['trend_label']})"
            f"{badge}"
        )
        if item.get("heat", 0) > 0:
            line += f"  [{heat_bar} {item['heat']}]"
        lines.append(line)

    lines.append("")

    # ---- 今日新增/异动 ----
    new_entries = [x for x in trend_data if x["trend_type"] == "new"]
    big_movers = [x for x in trend_data
                  if x["trend_type"] == "up" and "↑" in x.get("trend_label", "")
                  and int(x["trend_label"].replace("↑", "")) >= 5]

    if new_entries or big_movers:
        lines.append("⚡ 今日增量信号")
        lines.append("─" * 28)
        for item in new_entries:
            lines.append(f"  🆕 {item['keyword']} — 首次入榜 (排名{item['rank']})")
        for item in big_movers:
            lines.append(f"  🚀 {item['keyword']} — {item['trend_label']} (排名{item['rank']})")
        lines.append("")

    # ---- 昨日消失的热词 ----
    if disappeared:
        lines.append("💨 昨日退榜（前15名中）")
        lines.append("─" * 28)
        for item in disappeared:
            lines.append(f"  ✖ {item['keyword']} (昨日排名{item['yesterday_rank']})")
        lines.append("")

    # ---- 持续主线标记 ----
    persistent = [x for x in trend_data if x["consecutive_days"] >= 3]
    if persistent:
        lines.append("🎯 持续主线（连续3天+在榜）")
        lines.append("─" * 28)
        for item in persistent:
            lines.append(
                f"  {item['keyword']} — 连续{item['consecutive_days']}天"
                f" | 今日排名{item['rank']}"
            )
        lines.append("")

    # ---- 过滤掉的噪声词 ----
    if removed_words:
        lines.append(f"🗑️ 已过滤噪声词: {', '.join(removed_words)}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 8. AI 分析 — 改进版 Prompt
# ============================================================
def build_analysis_prompt(trend_data, disappeared, overall_heat):
    """
    构建给DeepSeek的分析prompt
    核心改进：
    - 要求输出增量信息而非泛泛而谈
    - 要求关联具体标的代码
    - 要求对比昨日差异
    - 要求给出可操作的if-then建议
    """
    # 准备数据摘要
    keywords_summary = []
    for item in trend_data:
        keywords_summary.append({
            "排名": item["rank"],
            "关键词": item["keyword"],
            "分类": item["category"],
            "趋势": item["trend_label"],
            "连续在榜": item["consecutive_days"],
            "热度": item.get("heat", 0),
        })

    disappeared_summary = [f"{x['keyword']}(昨日第{x['yesterday_rank']})"
                           for x in disappeared]

    new_entries = [x["keyword"] for x in trend_data if x["trend_type"] == "new"]
    big_movers = [x["keyword"] for x in trend_data
                  if x["trend_type"] == "up" and "↑" in x.get("trend_label", "")
                  and int(x["trend_label"].replace("↑", "")) >= 5]

    persistent_keywords = [f"{x['keyword']}({x['consecutive_days']}天)"
                           for x in trend_data if x["consecutive_days"] >= 3]

    prompt = f"""你是一位专业的A股市场分析师，擅长从热搜关键词中提炼可交易的投资线索。

## 今日数据（{datetime.now().strftime('%Y-%m-%d')}）

### 热词排行
{json.dumps(keywords_summary, ensure_ascii=False, indent=2)}

### 整体热度指数: {overall_heat}

### 今日新入榜: {', '.join(new_entries) if new_entries else '无'}
### 今日大幅跳升(↑5以上): {', '.join(big_movers) if big_movers else '无'}
### 昨日退榜: {', '.join(disappeared_summary) if disappeared_summary else '无'}
### 持续主线(3天+): {', '.join(persistent_keywords) if persistent_keywords else '无'}

## 分析要求（严格遵守）

请按以下结构输出分析，每个部分务必简洁、具体、可操作：

### 1. 今日增量信号（最重要）
- 只分析今日新入榜和大幅跳升的关键词，解释背后的驱动事件
- 每个信号关联1-2个具体A股标的（需给出股票代码）
- 如果没有明显增量信号，直接说"今日无明显增量，维持存量博弈"

### 2. 持续主线研判
- 对连续3天以上在榜的关键词进行趋势判断：是加速、见顶、还是钝化？
- 给出每条主线的操作阶段判断：布局期/加速期/分歧期/退潮期
- 关联核心标的和仓位建议

### 3. 退潮预警
- 分析昨日退榜的关键词，判断是正常轮动还是题材终结
- 如有持仓相关，给出明确的止盈/止损建议

### 4. 操作指引（if-then格式）
给出2-3条具体的操作建议，格式为：
"如果[条件]，则[操作]，目标[预期]，止损[位置]"

### 5. 风险提示
- 当前市场情绪状态判断（基于整体热度指数）
- 需要警惕的风险因素

注意事项：
- 不要说"建议关注XX板块"这种废话，要具体到标的和操作条件
- 不要重复热词列表本身的内容
- 每个主线的分析不超过3句话
- 整体控制在800字以内"""

    return prompt


def call_deepseek_analysis(prompt):
    """调用DeepSeek API生成分析"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your-api-key":
        return "（AI分析功能需要配置DEEPSEEK_API_KEY）"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是专业A股市场分析师，输出简洁、具体、可操作的分析。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    try:
        logger.info(f"[LLM] deepseek-chat ...")
        # 构建正确的API URL
        api_url = DEEPSEEK_BASE_URL.rstrip('/chat/completions')
        if not api_url.endswith('chat/completions'):
            api_url = f"{api_url}/chat/completions"

        resp = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ AI分析生成失败: {str(e)}"


# ============================================================
# 9. 飞书推送
# ============================================================
def push_to_feishu(content, ai_analysis):
    """推送到飞书群"""
    if not FEISHU_WEBHOOK_URL or FEISHU_WEBHOOK_URL == "your-webhook-url":
        logger.warning("未配置飞书webhook，跳过推送")
        return

    full_message = content + "\n" + "=" * 30 + "\n🤖 AI深度分析\n" + "=" * 30 + "\n" + ai_analysis

    # 卡片格式
    card_payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔥 {datetime.now().strftime('%Y-%m-%d')} A股热点追踪"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🤖 **AI深度分析**\n\n{ai_analysis}"
                    }
                }
            ]
        }
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=card_payload, timeout=30)
        if resp.status_code != 200 or resp.json().get("code") != 0:
            # fallback to plain text
            plain_payload = {
                "msg_type": "text",
                "content": {
                    "text": full_message
                }
            }
            resp = requests.post(FEISHU_WEBHOOK_URL, json=plain_payload, timeout=30)
        logger.info(f"[飞书] OK")
    except Exception as e:
        logger.error(f"[飞书] {e}")


# ============================================================
# 10. 主流程
# ============================================================
def main():
    print(f"{'=' * 50}")
    print(f"  A股热点追踪系统 V2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 50}\n")

    # Step 1: 初始化jieba
    init_jieba()

    # Step 2: 获取原始数据
    print("📥 Step 1: 获取热词数据...")
    raw_data = fetch_raw_keywords()
    print(f"  获取到 {len(raw_data)} 条原始热词\n")

    # Step 3: 清洗过滤
    print("🧹 Step 2: 数据清洗与过滤...")
    filtered_data, removed = process_keywords(raw_data)
    print(f"  有效热词: {len(filtered_data)} 条")
    print(f"  过滤噪声: {len(removed)} 条 ({', '.join(removed[:10])}...)\n")

    # Step 4: 加载历史 & 计算趋势
    print("📊 Step 3: 计算趋势与历史对比...")
    history = load_history()
    trend_data, disappeared = compute_trends(filtered_data, history)
    print(f"  昨日退榜: {len(disappeared)} 条")
    new_count = sum(1 for x in trend_data if x["trend_type"] == "new")
    print(f"  今日新增: {new_count} 条\n")

    # Step 5: 计算整体热度
    overall_heat = 0
    if trend_data:
        heats = [x.get("heat", 0) for x in trend_data if x.get("heat", 0) > 0]
        overall_heat = round(sum(heats) / len(heats)) if heats else 0
    print(f"📈 整体热度指数: {overall_heat}\n")

    # Step 6: 格式化消息
    print("📝 Step 4: 构建推送消息...")
    message_content = build_feishu_message(
        trend_data, disappeared, removed, overall_heat
    )
    print(message_content)
    print()

    # Step 7: AI分析
    print("🤖 Step 5: 生成AI分析...")
    analysis_prompt = build_analysis_prompt(trend_data, disappeared, overall_heat)
    ai_analysis = call_deepseek_analysis(analysis_prompt)
    print(f"  AI分析结果:\n{ai_analysis}\n")

    # Step 8: 推送
    print("📤 Step 6: 推送到飞书...")
    push_to_feishu(message_content, ai_analysis)

    # Step 9: 保存今日数据到历史
    history = update_history(history, filtered_data)
    save_history(history)
    print(f"💾 历史数据已保存 → {HISTORY_FILE}")

    # Step 10: 保存markdown记录
    today_str = datetime.now().strftime("%Y-%m-%d")
    with open(HISTORY_DIR / f"hotspot_{today_str}.md", "w", encoding="utf-8") as f:
        full = message_content + "\n" + "=" * 30 + "\n🤖 AI深度分析\n" + "=" * 30 + "\n" + ai_analysis
        f.write(f"# 🔥 {today_str} A股热点追踪 V2\n\n{full}")
    print(f"💾 记录已保存 → {HISTORY_DIR / f'hotspot_{today_str}.md'}")

    print(f"\n{'=' * 50}")
    print("  执行完毕")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
