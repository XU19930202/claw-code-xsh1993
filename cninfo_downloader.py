#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巨潮资讯网公告下载器
用法:
  python cninfo_downloader.py                        # 进入交互模式
  python cninfo_downloader.py -c 000063              # 按股票代码搜索
  python cninfo_downloader.py -c 000063 -k 年报      # 按代码+关键词搜索
  python cninfo_downloader.py -k 重大资产重组 -n 20   # 按关键词搜索，返回20条
  python cninfo_downloader.py -c 300246 -k 赎回       # 搜索宝莱特赎回相关公告
"""

import requests
import os
import sys
import argparse
import time
import re
from datetime import datetime

# ============== 配置 ==============
DOWNLOAD_DIR = "./公告下载"  # 默认下载目录，可修改
PAGE_SIZE = 30               # 每页条数

# ============== API 地址 ==============
SEARCH_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
FULL_TEXT_SEARCH_URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
}

# 公告分类映射
CATEGORY_MAP = {
    "全部": "",
    "年报": "category_ndbg_szsh",
    "半年报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
    "业绩预告": "category_yjygjxz_szsh",
    "权益分派": "category_qyfpxzcs_szsh",
    "董事会": "category_dshgg_szsh",
    "监事会": "category_jshgg_szsh",
    "股东大会": "category_gddh_szsh",
    "日常经营": "category_rcjy_szsh",
    "公司治理": "category_gszl_szsh",
    "中介报告": "category_zjbg_szsh",
    "首发": "category_sf_szsh",
    "增发": "category_zf_szsh",
    "股权激励": "category_gqjl_szsh",
    "配股": "category_pg_szsh",
    "解禁": "category_jj_szsh",
    "公司债": "category_gszq_szsh",
    "可转债": "category_kzzq_szsh",
    "其他融资": "category_qtrz_szsh",
    "股权变动": "category_gqbd_szsh",
    "补充更正": "category_bcgz_szsh",
    "澄清致歉": "category_cqdq_szsh",
    "风险提示": "category_fxts_szsh",
    "特别处理": "category_tbcl_szsh",
    "退市": "category_ts_szsh",
}


def ensure_download_dir(path=None):
    """确保下载目录存在"""
    d = path or DOWNLOAD_DIR
    os.makedirs(d, exist_ok=True)
    return d


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def should_download(title, filter_type="all"):
    """
    根据标题判断是否应该下载该文件
    :param title: 公告标题
    :param filter_type: 过滤类型
                       "all" - 下载所有文件
                       "report" - 只下载年报、半年报、三季报、一季报（排除摘要、募集说明书等）
                       "annual" - 只下载年度报告
                       "semi" - 只下载半年度报告
                       "quarterly" - 只下载三季度或一季度报告
    :return: 是否应该下载
    """
    # 需要排除的关键词
    EXCLUDE_KEYWORDS = ["摘要", "募集说明书", "转让说明书", "更正"]
    
    # 检查是否包含排除关键词
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in title:
            return False
    
    if filter_type == "all":
        # 下载所有不包含排除关键词的文件
        return True
    elif filter_type == "report":
        # 只下载各类报告（排除摘要版本）
        report_keywords = ["年度报告", "半年度报告", "第三季度报告", "第一季度报告"]
        return any(kw in title for kw in report_keywords)
    elif filter_type == "annual":
        # 只下载年度报告（不包括半年报或季报）
        # 使用更严格的匹配：确保是"年度报告"而不是"半年度报告"或"季度报告"
        return ("年度报告" in title and 
                "半年度报告" not in title and 
                "第一季度报告" not in title and 
                "第三季度报告" not in title)
    elif filter_type == "semi":
        # 只下载半年度报告（不包括年报或季报）
        return "半年度报告" in title
    elif filter_type == "quarterly":
        # 只下载季度报告（三季或一季），不包括年报或半年报
        return ("第三季度报告" in title or "第一季度报告" in title) and \
               "半年度报告" not in title
    
    return True


def search_announcements(stock_code="", keyword="", category="", page=1,
                         page_size=PAGE_SIZE, start_date="", end_date=""):
    """
    搜索公告
    :param stock_code: 股票代码，如 '000063' 或 '000063,300246' (多个用逗号分隔)
    :param keyword: 搜索关键词
    :param category: 公告分类，参考 CATEGORY_MAP
    :param page: 页码
    :param page_size: 每页条数
    :param start_date: 开始日期 YYYY-MM-DD
    :param end_date: 结束日期 YYYY-MM-DD
    :return: (公告列表, 总条数)
    """
    # 处理分类
    cat_code = CATEGORY_MAP.get(category, category)

    # 构建 stock 参数（需要带交易所前缀）
    stock_param = ""
    if stock_code:
        codes = [c.strip() for c in stock_code.split(",")]
        stock_param = ",".join(codes)

    data = {
        "stock": stock_param,
        "searchkey": keyword,
        "category": cat_code,
        "pageNum": page,
        "pageSize": page_size,
        "column": "szse",      # szse=深交所+上交所, szse 实际是全市场
        "tabName": "fulltext",
        "plate": "",
        "seDate": "",
        "sortName": "",
        "sortType": "",
        "isHLContent": "true",
    }

    # 日期范围
    if start_date and end_date:
        data["seDate"] = f"{start_date}~{end_date}"
    elif start_date:
        data["seDate"] = f"{start_date}~"
    elif end_date:
        data["seDate"] = f"~{end_date}"

    try:
        resp = requests.post(SEARCH_URL, data=data, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        result = resp.json()

        announcements = result.get("announcements", []) or []
        total = result.get("totalAnnouncement", 0)

        parsed = []
        for ann in announcements:
            # 清理 HTML 标签（搜索高亮）
            title = re.sub(r'<[^>]+>', '', ann.get("announcementTitle", ""))
            parsed.append({
                "title": title,
                "code": ann.get("secCode", ""),
                "name": ann.get("secName", ""),
                "date": datetime.fromtimestamp(
                    ann.get("announcementTime", 0) / 1000
                ).strftime("%Y-%m-%d") if ann.get("announcementTime") else "",
                "url": DOWNLOAD_BASE + ann.get("adjunctUrl", ""),
                "adjunct_url": ann.get("adjunctUrl", ""),
                "type": ann.get("announcementType", ""),
                "id": ann.get("announcementId", ""),
            })

        return parsed, total

    except requests.RequestException as e:
        print(f"[错误] 搜索请求失败: {e}")
        return [], 0
    except Exception as e:
        print(f"[错误] 解析结果失败: {e}")
        return [], 0


def download_announcement(ann, download_dir=None):
    """
    下载单个公告PDF
    :param ann: 公告字典（来自 search_announcements）
    :param download_dir: 下载目录
    :return: 保存的文件路径，失败返回 None
    """
    d = ensure_download_dir(download_dir)
    url = ann["url"]

    # 构建文件名: 代码_简称_日期_标题.pdf
    parts = [ann["code"], ann["name"], ann["date"], ann["title"]]
    filename = "_".join(p for p in parts if p) + ".pdf"
    filename = sanitize_filename(filename)
    filepath = os.path.join(d, filename)

    # 如果已存在则跳过
    if os.path.exists(filepath):
        print(f"  [跳过] 文件已存在: {filename}")
        return filepath

    try:
        resp = requests.get(url, headers={
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "http://www.cninfo.com.cn/",
        }, timeout=30, stream=True)
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  [完成] {filename} ({size_kb:.0f} KB)")
        return filepath

    except Exception as e:
        print(f"  [失败] {filename}: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return None


def display_results(announcements, total, page, page_size):
    """格式化打印搜索结果"""
    if not announcements:
        print("\n  未找到相关公告。\n")
        return

    total_pages = (total + page_size - 1) // page_size
    print(f"\n{'='*80}")
    print(f"  共 {total} 条结果，当前第 {page}/{total_pages} 页")
    print(f"{'='*80}")

    for i, ann in enumerate(announcements):
        idx = (page - 1) * page_size + i + 1
        print(f"\n  [{idx:3d}] {ann['code']} {ann['name']}")
        print(f"        {ann['title']}")
        print(f"        {ann['date']}")

    print(f"\n{'='*80}")


def interactive_mode():
    """交互式模式"""
    print("""
╔══════════════════════════════════════════════════╗
║         巨潮资讯网 · 公告下载器                  ║
╠══════════════════════════════════════════════════╣
║  命令说明:                                       ║
║    s / 搜索    - 搜索公告                        ║
║    d / 下载    - 下载公告 (输入序号)              ║
║    da / 全部下载 - 下载当前所有结果               ║
║    n / 下一页  - 下一页                          ║
║    p / 上一页  - 上一页                          ║
║    cat / 分类  - 显示可用分类                    ║
║    dir / 目录  - 设置下载目录                    ║
║    h / 帮助    - 显示帮助                        ║
║    q / 退出    - 退出程序                        ║
╚══════════════════════════════════════════════════╝
    """)

    current_results = []
    current_total = 0
    current_page = 1
    current_params = {}
    download_dir = DOWNLOAD_DIR

    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not cmd:
            continue

        # ---- 退出 ----
        if cmd.lower() in ("q", "quit", "exit", "退出"):
            print("再见！")
            break

        # ---- 帮助 ----
        elif cmd.lower() in ("h", "help", "帮助"):
            print("""
  搜索示例:
    > s 000063                    按股票代码搜索
    > s 000063 年报               按代码+关键词搜索
    > s 000063 年报 年报          按代码+关键词+分类搜索
    > s ,重大资产重组              只按关键词搜索（代码留空，前面加逗号）
    > s 000063 ,2024-01-01,2024-12-31   指定日期范围

  下载:
    > d 1                         下载序号1的公告
    > d 1 3 5                     下载序号1、3、5的公告
    > d 1-10                      下载序号1到10的公告
    > da                          下载当前页所有公告

  翻页:
    > n                           下一页
    > p                           上一页

  设置:
    > dir /path/to/folder         设置下载目录
    > cat                         查看公告分类列表
            """)

        # ---- 分类列表 ----
        elif cmd.lower() in ("cat", "分类"):
            print("\n  可用公告分类:")
            for k in CATEGORY_MAP:
                print(f"    {k}")

        # ---- 设置下载目录 ----
        elif cmd.lower().startswith(("dir ", "目录 ")):
            new_dir = cmd.split(None, 1)[1].strip()
            download_dir = new_dir
            ensure_download_dir(download_dir)
            print(f"  下载目录已设置为: {os.path.abspath(download_dir)}")

        # ---- 搜索 ----
        elif cmd.lower().startswith(("s ", "搜索 ", "search ")):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                print("  请输入搜索条件。输入 h 查看帮助。")
                continue

            query = parts[1].strip()
            # 解析搜索参数
            tokens = query.split()
            stock_code = ""
            keyword = ""
            category = ""
            start_date = ""
            end_date = ""

            if tokens:
                # 第一个token: 如果是数字则当作股票代码
                first = tokens[0]
                if first.startswith(","):
                    # 逗号开头表示没有代码，关键词紧跟
                    keyword = first[1:]
                elif re.match(r'^\d{6}$', first):
                    stock_code = first
                else:
                    keyword = first

            if len(tokens) >= 2 and not keyword:
                second = tokens[1]
                if second.startswith(","):
                    # 日期范围: ,2024-01-01,2024-12-31
                    date_parts = second.split(",")
                    if len(date_parts) >= 2:
                        start_date = date_parts[1]
                    if len(date_parts) >= 3:
                        end_date = date_parts[2]
                else:
                    keyword = second

            if len(tokens) >= 3:
                third = tokens[2]
                if third in CATEGORY_MAP:
                    category = third
                elif third.startswith(","):
                    date_parts = third.split(",")
                    if len(date_parts) >= 2:
                        start_date = date_parts[1]
                    if len(date_parts) >= 3:
                        end_date = date_parts[2]

            current_page = 1
            current_params = {
                "stock_code": stock_code,
                "keyword": keyword,
                "category": category,
                "start_date": start_date,
                "end_date": end_date,
            }

            print(f"\n  搜索中... 代码={stock_code or '全部'} "
                  f"关键词={keyword or '无'} "
                  f"分类={category or '全部'} "
                  f"日期={start_date}~{end_date}")

            current_results, current_total = search_announcements(
                stock_code=stock_code,
                keyword=keyword,
                category=category,
                page=current_page,
                start_date=start_date,
                end_date=end_date,
            )
            display_results(current_results, current_total, current_page, PAGE_SIZE)

        # ---- 下一页 ----
        elif cmd.lower() in ("n", "next", "下一页"):
            if not current_params:
                print("  请先搜索。")
                continue
            total_pages = (current_total + PAGE_SIZE - 1) // PAGE_SIZE
            if current_page >= total_pages:
                print("  已经是最后一页了。")
                continue
            current_page += 1
            current_results, current_total = search_announcements(
                page=current_page, **current_params
            )
            display_results(current_results, current_total, current_page, PAGE_SIZE)

        # ---- 上一页 ----
        elif cmd.lower() in ("p", "prev", "上一页"):
            if current_page <= 1:
                print("  已经是第一页了。")
                continue
            current_page -= 1
            current_results, current_total = search_announcements(
                page=current_page, **current_params
            )
            display_results(current_results, current_total, current_page, PAGE_SIZE)

        # ---- 下载全部 ----
        elif cmd.lower() in ("da", "all", "全部下载"):
            if not current_results:
                print("  当前没有搜索结果。")
                continue
            print(f"\n  开始下载当前页 {len(current_results)} 条公告...")
            ensure_download_dir(download_dir)
            success = 0
            for ann in current_results:
                result = download_announcement(ann, download_dir)
                if result:
                    success += 1
                time.sleep(0.3)  # 避免请求过快
            print(f"\n  下载完成: {success}/{len(current_results)} 成功")
            print(f"  保存目录: {os.path.abspath(download_dir)}")

        # ---- 下载指定序号 ----
        elif cmd.lower().startswith(("d ", "下载 ", "download ")):
            if not current_results:
                print("  当前没有搜索结果。请先搜索。")
                continue

            parts = cmd.split(None, 1)
            if len(parts) < 2:
                print("  请指定下载序号。例如: d 1 或 d 1-5")
                continue

            # 解析序号
            indices = set()
            for token in parts[1].split():
                if "-" in token:
                    try:
                        a, b = token.split("-", 1)
                        for i in range(int(a), int(b) + 1):
                            indices.add(i)
                    except ValueError:
                        print(f"  无效的范围: {token}")
                else:
                    try:
                        indices.add(int(token))
                    except ValueError:
                        print(f"  无效的序号: {token}")

            if not indices:
                continue

            ensure_download_dir(download_dir)
            offset = (current_page - 1) * PAGE_SIZE
            success = 0
            for idx in sorted(indices):
                list_idx = idx - offset - 1
                if 0 <= list_idx < len(current_results):
                    ann = current_results[list_idx]
                    print(f"\n  下载 [{idx}] {ann['code']} {ann['title']}...")
                    result = download_announcement(ann, download_dir)
                    if result:
                        success += 1
                    time.sleep(0.3)
                else:
                    print(f"  序号 {idx} 不在当前页范围内。")

            print(f"\n  下载完成: {success}/{len(indices)} 成功")
            print(f"  保存目录: {os.path.abspath(download_dir)}")

        # ---- 快捷搜索：直接输入6位数字 ----
        elif re.match(r'^\d{6}$', cmd):
            current_page = 1
            current_params = {
                "stock_code": cmd,
                "keyword": "",
                "category": "",
                "start_date": "",
                "end_date": "",
            }
            print(f"\n  搜索股票代码 {cmd} 的公告...")
            current_results, current_total = search_announcements(
                stock_code=cmd, page=current_page
            )
            display_results(current_results, current_total, current_page, PAGE_SIZE)

        else:
            print("  未知命令。输入 h 查看帮助。")


def batch_mode(args):
    """命令行批量模式"""
    results, total = search_announcements(
        stock_code=args.code or "",
        keyword=args.keyword or "",
        category=args.category or "",
        page=1,
        page_size=args.num,
        start_date=args.start or "",
        end_date=args.end or "",
    )

    display_results(results, total, 1, args.num)

    if not results:
        return

    if args.download:
        download_dir = args.output or DOWNLOAD_DIR
        ensure_download_dir(download_dir)
        
        # 应用过滤条件
        filtered_results = [ann for ann in results if should_download(ann["title"], args.filter_type)]
        
        print(f"\n  搜索结果: {len(results)} 条")
        if args.filter_type != "all":
            print(f"  过滤规则: {args.filter_type}")
            print(f"  过滤后: {len(filtered_results)} 条 (已排除摘要、募集说明书等)")
        
        if not filtered_results:
            print(f"  未找到符合条件的文件，无需下载。")
            return
        
        print(f"\n  开始下载 {len(filtered_results)} 条公告到 {os.path.abspath(download_dir)}...")
        success = 0
        for ann in filtered_results:
            result = download_announcement(ann, download_dir)
            if result:
                success += 1
            time.sleep(0.3)
        print(f"\n  下载完成: {success}/{len(filtered_results)} 成功")


def main():
    parser = argparse.ArgumentParser(
        description="巨潮资讯网公告下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                    交互模式
  %(prog)s -c 000063                          搜索中兴通讯公告
  %(prog)s -c 000063 -k 年报                  搜索中兴通讯年报
  %(prog)s -c 300246 -k 赎回 --download       搜索并下载宝莱特赎回公告
  %(prog)s -k 重大资产重组 -n 20              搜索关键词，返回20条
  %(prog)s -c 000063 --cat 年报 --download    按分类搜索并下载
  %(prog)s -c 000063 --start 2024-01-01 --end 2024-12-31  指定日期范围
        """,
    )
    parser.add_argument("-c", "--code", help="股票代码，如 000063")
    parser.add_argument("-k", "--keyword", help="搜索关键词")
    parser.add_argument("--cat", "--category", dest="category", help="公告分类（输入 --cat list 查看）")
    parser.add_argument("-n", "--num", type=int, default=30, help="返回条数（默认30）")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--download", action="store_true", help="搜索后直接下载")
    parser.add_argument("-o", "--output", help="下载目录（默认 ./公告下载）")
    parser.add_argument("--filter", dest="filter_type", default="all",
                        choices=["all", "report", "annual", "semi", "quarterly"],
                        help="下载过滤规则 (default: all)\n"
                             "  all - 下载所有文件\n"
                             "  report - 只下载年报、半年报、季报（排除摘要版本）\n"
                             "  annual - 只下载年度报告\n"
                             "  semi - 只下载半年度报告\n"
                             "  quarterly - 只下载季度报告")

    args = parser.parse_args()

    # 查看分类列表
    if args.category == "list":
        print("\n可用公告分类:")
        for k in CATEGORY_MAP:
            print(f"  {k}")
        return

    # 如果没有任何参数，进入交互模式
    if not args.code and not args.keyword and not args.category:
        interactive_mode()
    else:
        batch_mode(args)


if __name__ == "__main__":
    main()
