#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股热点关键词追踪系统 v3 - 云函数版本
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
    """加载配置文件"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# 云函数环境简化日志配置
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

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
    "DeepSeek", "大语言模型", "智能体", "OpenAI",
]

for word in CUSTOM_WORDS:
    jieba.add_word(word, freq=1000, tag='nw')

logger.info(f"[jieba] {len(CUSTOM_WORDS)} 自定义词")

# ============================================================
#  新闻抓取
# ============================================================

def fetch_eastmoney():
    """抓取东方财富"""
    try:
        url = "https://finance.eastmoney.com/a/cjkjj.html"
        r = requests.get(url, headers=UA, timeout=10)
        items = re.findall(r'<li>.*?href="([^"]+)".*?title="([^"]+)"', r.text)
        count = len(items)
        logger.info(f"[东方财富] {count} 条")
        return [title for _, title in items[:50]]
    except Exception as e:
        logger.error(f"东方财富抓取失败: {e}")
        return []

def fetch_stcn():
    """抓取证券时报"""
    try:
        base = "https://epaper.stcn.com/col/"
        today = datetime.now().strftime("%Y%m/%d")
        url = base + today + "/node_A001.html"
        r = requests.get(url, headers=UA, timeout=10)
        links = re.findall(r'href="([^"]+\.html)"', r.text)
        count = len(links)
        logger.info(f"[证券时报] {count} 条")
        
        titles = []
        for link in links[:100]:
            try:
                full = url.rsplit("/", 1)[0] + "/" + link
                rr = requests.get(full, headers=UA, timeout=5)
                title_match = re.search(r'<h1[^>]*>(.+?)</h1>', rr.text)
                if title_match:
                    titles.append(title_match.group(1).strip())
                time.sleep(0.2)
            except:
                pass
        return titles
    except Exception as e:
        logger.error(f"证券时报抓取失败: {e}")
        return []

def fetch_cl():
    """抓取财联社"""
    try:
        url = "https://www.cls.cn/telegraph"
        r = requests.get(url, headers=UA, timeout=10)
        items = re.findall(r'<a[^>]+title="([^"]+)"', r.text)
        count = len(items)
        logger.info(f"[财联社] {count} 条")
        return items[:50]
    except Exception as e:
        logger.error(f"财联社抓取失败: {e}")
        return []

# ============================================================
#  统计与排序
# ============================================================

def analyze_titles(titles):
    """分词统计"""
    all_text = " ".join(titles)
    words = jieba.lcut(all_text)
    
    stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
                 '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
                 '你', '会', '着', '没有', '看', '好', '自己', '这'}
    
    filtered = [w for w in words if len(w) >= 2 and w not in stop_words]
    return Counter(filtered).most_common(50)

# ============================================================
#  飞书推送
# ============================================================

def send_feishu(msg):
    """发送消息到飞书"""
    config = load_config()
    webhook = config.get('feishu_webhook', '')
    if not webhook:
        logger.warning("未配置飞书webhook,跳过推送")
        return
    
    data = {
        "msg_type": "text",
        "content": {"text": msg}
    }
    
    try:
        r = requests.post(webhook, json=data, headers={"Content-Type": "application/json"}, timeout=5)
        if r.status_code == 200:
            logger.info("[飞书] OK")
        else:
            logger.error(f"[飞书] 失败: {r.text}")
    except Exception as e:
        logger.error(f"[飞书] 异常: {e}")

# ============================================================
#  LLM摘要
# ============================================================

def call_llm(prompt):
    """调用LLM生成摘要"""
    config = load_config()
    llm = config.get('llm', {})
    
    api_url = llm.get('api_url', 'https://api.deepseek.com/v1/chat/completions')
    api_key = llm.get('api_key', '')
    model = llm.get('model', 'deepseek-chat')
    
    if not api_key:
        logger.warning("未配置LLM API Key,跳过AI摘要")
        return None
    
    try:
        r = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是一位资深证券分析师,擅长提炼市场热点。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            },
            timeout=30
        )
        
        if r.status_code == 200:
            result = r.json()
            return result['choices'][0]['message']['content']
        else:
            logger.error(f"[LLM] 失败: {r.text}")
            return None
    except Exception as e:
        logger.error(f"[LLM] 异常: {e}")
        return None

# ============================================================
#  主流程
# ============================================================

def main():
    date = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"==================== {date} ====================")
    
    # 1. 抓取新闻
    titles = []
    titles.extend(fetch_eastmoney())
    titles.extend(fetch_stcn())
    titles.extend(fetch_cl())
    
    if not titles:
        logger.error("未获取到任何新闻")
        return
    
    total = len(titles)
    logger.info(f"共 {total} 条")
    
    # 2. 统计热词
    counter = analyze_titles(titles)
    top5 = counter[:5]
    logger.info(f"Top5: {[(k, round(v/total, 4)) for k, v in top5]}")
    
    # 3. 保存排名
    rank_file = RANK_DIR / f"{date}.json"
    with open(rank_file, 'w', encoding='utf-8') as f:
        json.dump(dict(counter), f, ensure_ascii=False, indent=2)
    
    # 4. 生成摘要
    hot_words = [f"{k}({v})" for k, v in top5]
    prompt = f"""
今日({date})A股市场热点追踪结果:

热词Top5: {', '.join(hot_words)}
新闻总数: {total}条

请基于以上信息,用简洁专业的语言分析今日市场热点(100字以内)。
"""
    
    summary = call_llm(prompt)
    
    # 5. 保存报告
    report = f"""# 🔥 A股热点追踪报告 {date}

## 热词排行 Top5

{chr(10).join([f'{i+1}. **{k}** - 出现{v}次 (占比{v/total:.2%})' for i, (k, v) in enumerate(top5)])}

## AI分析

{summary if summary else '暂无AI分析'}

## 数据来源

- 东方财富
- 证券时报  
- 财联社

---
*数据统计时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    report_file = HISTORY_DIR / f"hotspot_{date}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 6. 飞书推送
    msg = f"""🔥 A股热点追踪 {date}

热词Top5:
{chr(10).join([f'{i+1}. {k}' for i, (k, v) in enumerate(top5)])}

AI分析:
{summary if summary else '暂无'}
"""
    send_feishu(msg)
    
    logger.info("完成")
    return {
        "date": date,
        "total_news": total,
        "top5": hot_words,
        "summary": summary
    }

if __name__ == "__main__":
    main()
