"""
巨潮资讯网公告检索模块
──────────────────────
通过巨潮的公开POST接口检索上市公司并购/重组相关公告

接口地址：http://www.cninfo.com.cn/new/hisAnnouncement/query
无需注册，无需token，免费使用

注意事项：
  - 请控制请求频率（每次请求间隔>=2秒），避免触发反爬
  - 该接口返回公告标题和PDF链接，不返回公告正文
  - 如遇403或空结果，可能触发了滑块验证，稍后重试即可
"""

import time
import requests
import pandas as pd


# ============================================================
# 巨潮接口配置
# ============================================================

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_SEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_PDF_BASE = "http://static.cninfo.com.cn/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://www.cninfo.com.cn/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Host": "www.cninfo.com.cn",
    "Origin": "http://www.cninfo.com.cn",
}

# 并购重组相关搜索关键词
MA_KEYWORDS = [
    "重大资产重组",
    "重大资产购买",
    "重大资产出售",
    "收购报告书",
    "要约收购",
    "股权收购",
    "资产置换",
    "资产注入",
    "借壳上市",
    "控制权变更",
    "实际控制人变更",
    "控股股东变更",
    "定向增发",       # 并购常用支付方式
    "发行股份购买资产",
    "重组预案",
    "重组报告书",
]


def get_org_id(stock_code: str) -> tuple:
    """
    通过巨潮搜索接口获取公司的orgId（巨潮内部ID）
    stock_code: 纯数字代码如 "603197" 或简称如 "保隆科技"
    返回: (orgId, code, zwjc) 如 ("9900025935", "603197", "保隆科技")
    """
    try:
        resp = requests.post(
            CNINFO_SEARCH_URL,
            data={"keyWord": stock_code},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return None, None, None

        # 取第一个匹配结果
        item = results[0]
        return item.get("orgId"), item.get("code"), item.get("zwjc")

    except Exception as e:
        print(f"  ⚠️ 巨潮搜索接口异常: {e}")
        return None, None, None


def search_announcements(
    stock_code: str,
    org_id: str,
    keyword: str,
    se_date: str = "",
    max_pages: int = 5,
) -> list:
    """
    按关键词搜索某只股票的公告

    参数:
        stock_code: 股票代码（纯数字）
        org_id: 巨潮orgId
        keyword: 搜索关键词（公告标题包含）
        se_date: 日期范围，格式如 "2015-01-01~2025-12-31"
        max_pages: 最大翻页数

    返回:
        公告列表 [{ann_date, title, pdf_url, keyword}, ...]
    """
    all_items = []

    for page in range(1, max_pages + 1):
        data = {
            "pageNum": str(page),
            "pageSize": "30",
            "column": "szse",       # szse覆盖沪深两市
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{stock_code},{org_id}",
            "searchkey": keyword,
            "secid": "",
            "category": "",         # 不限分类，由关键词筛选
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }

        try:
            resp = requests.post(
                CNINFO_QUERY_URL,
                data=data,
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            print(f"  ⚠️ 请求异常 (keyword={keyword}, page={page}): {e}")
            break

        announcements = result.get("announcements", [])
        if not announcements:
            break

        for ann in announcements:
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            ann_date_ts = ann.get("announcementTime")  # 毫秒时间戳
            adj_url = ann.get("adjunctUrl", "")

            # 时间戳转日期
            if ann_date_ts:
                import datetime
                ann_date = datetime.datetime.fromtimestamp(
                    ann_date_ts / 1000
                ).strftime("%Y-%m-%d")
            else:
                ann_date = ""

            # PDF链接
            pdf_url = f"{CNINFO_PDF_BASE}{adj_url}" if adj_url else ""

            all_items.append({
                "ann_date": ann_date,
                "title": title,
                "pdf_url": pdf_url,
                "keyword": keyword,
            })

        # 检查是否还有更多页
        total_ann = result.get("totalAnnouncement", 0)
        if page * 30 >= total_ann:
            break

        time.sleep(1.5)  # 频率控制

    return all_items


def classify_ma_event(title: str) -> str:
    """
    根据公告标题分类事件类型
    """
    # 按优先级匹配
    rules = [
        (["借壳"], "借壳上市"),
        (["要约收购"], "要约收购"),
        (["控制权", "实际控制人变更", "控股股东变更"], "控制权变更"),
        (["发行股份购买资产", "发行股份及支付现金购买"], "发行股份购买资产"),
        (["重大资产重组", "重大资产购买", "重大资产出售"], "重大资产重组"),
        (["收购报告书", "股权收购", "收购"], "收购/并购"),
        (["资产置换"], "资产置换"),
        (["资产注入"], "资产注入"),
        (["定向增发", "非公开发行"], "定向增发"),
        (["重组预案", "重组报告书", "重组"], "重组相关"),
    ]
    for keywords, event_type in rules:
        if any(kw in title for kw in keywords):
            return event_type
    return "其他重组事项"


def filter_important(title: str) -> bool:
    """
    过滤掉不重要的公告（进展公告、回复函等）
    只保留实质性公告
    """
    # 排除的关键词
    noise_keywords = [
        "进展", "延期", "豁免", "补充", "更正", "修订",
        "回复", "反馈", "问询", "法律意见",
        "独立财务顾问", "验资报告",
        "股票交易异常波动", "风险提示",
        "摘要",
    ]
    # 如果标题包含核心关键词，即使包含噪音词也保留
    core_keywords = [
        "预案", "报告书", "草案", "方案",
        "收购", "重组", "完成", "实施",
        "控制权", "实际控制人",
    ]
    has_core = any(kw in title for kw in core_keywords)
    has_noise = any(kw in title for kw in noise_keywords)

    if has_core:
        return True
    if has_noise:
        return False
    return True  # 默认保留


def fetch_cninfo_ma_events(
    stock_code: str,
    se_date: str = "",
    verbose: bool = True,
) -> pd.DataFrame:
    """
    主入口：从巨潮资讯网获取并购/重组相关公告

    参数:
        stock_code: 股票代码（纯数字如 "603197"）或简称
        se_date: 日期范围（可选）
        verbose: 是否打印过程

    返回:
        DataFrame: [ann_date, event_type, title, pdf_url, keyword, source]
    """
    if verbose:
        print(f"\n  [巨潮资讯] 正在获取 {stock_code} 的并购/重组公告...")

    # 1. 获取orgId
    org_id, code, name = get_org_id(stock_code)
    if not org_id:
        if verbose:
            print(f"  ⚠️ 未在巨潮找到 {stock_code}，请检查代码或简称")
        return pd.DataFrame()

    if verbose:
        print(f"  公司: {name}（{code}）orgId={org_id}")

    # 2. 按每个关键词检索
    all_anns = []
    for i, kw in enumerate(MA_KEYWORDS):
        if verbose:
            print(f"  [{i+1}/{len(MA_KEYWORDS)}] 搜索: {kw}", end="", flush=True)

        results = search_announcements(code, org_id, kw, se_date)

        if verbose:
            print(f" → {len(results)} 条")

        all_anns.extend(results)
        time.sleep(2)  # 关键词之间间隔

    if not all_anns:
        if verbose:
            print(f"  ❌ 未找到任何并购/重组相关公告")
        return pd.DataFrame()

    # 3. 去重（同一公告可能匹配多个关键词）
    df = pd.DataFrame(all_anns)
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["ann_date", "title"], keep="first")
    if verbose:
        print(f"\n  原始 {before_dedup} 条，去重后 {len(df)} 条")

    # 4. 分类
    df["event_type"] = df["title"].apply(classify_ma_event)

    # 5. 过滤噪音
    df["is_important"] = df["title"].apply(filter_important)
    df_important = df[df["is_important"]].copy()
    if verbose:
        print(f"  过滤噪音后保留 {len(df_important)} 条重要公告")

    # 6. 排序
    df_important = df_important.sort_values("ann_date", ascending=True).reset_index(drop=True)
    df_important["source"] = "巨潮资讯网"
    df_important["year"] = df_important["ann_date"].str[:4]

    # 选择输出列
    output_cols = ["ann_date", "year", "event_type", "title", "pdf_url", "keyword", "source"]
    result = df_important[output_cols].copy()
    result.columns = ["event_date", "year", "event_type", "detail", "pdf_url", "keyword", "source"]

    return result


# ============================================================
# 独立运行测试
# ============================================================
if __name__ == "__main__":
    import sys
    import io

    # Windows GBK 终端兼容
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("用法：python cninfo_crawler.py <股票代码>")
        print("示例：python cninfo_crawler.py 603197")
        print("      python cninfo_crawler.py 保隆科技")
        sys.exit(1)

    stock = sys.argv[1]
    df = fetch_cninfo_ma_events(stock, verbose=True)

    if not df.empty:
        print(f"\n{'=' * 80}")
        print(f" 共找到 {len(df)} 条并购/重组公告")
        print(f"{'─' * 80}")

        # 按事件类型统计
        print("\n事件类型分布：")
        for evt_type, count in df["event_type"].value_counts().items():
            print(f"  {evt_type}: {count} 条")

        # 按年度统计
        print(f"\n年度分布：")
        for year, count in df["year"].value_counts().sort_index().items():
            print(f"  {year}年: {count} 条")

        # 打印所有公告
        print(f"\n{'=' * 80}")
        print(" 公告明细")
        print(f"{'─' * 80}")
        for _, row in df.iterrows():
            print(f"  [{row['event_date']}] 【{row['event_type']}】")
            print(f"    {row['detail']}")
            if row.get("pdf_url"):
                print(f"    📄 {row['pdf_url']}")
            print()

        # 保存
        output_file = f"{stock}_cninfo_ma_events.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n已保存至: {output_file}")
