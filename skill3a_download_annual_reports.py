#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill 3a：年度报告下载工具（替代原skill3的一部分）
数据来源：巨潮资讯网（cninfo.com.cn）
功能：下载指定股票代码上市以来的全部年度报告PDF

用法：
    python skill3a_download_annual_reports.py --code 002637         # 单只股票
    python skill3a_download_annual_reports.py --codes 002637,600110  # 多只股票
"""

import os
import sys
import json
import time
import random
import argparse
import requests
from datetime import datetime


# ============================================================
# 配置区
# ============================================================
# 下载保存目录
SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports")

# 巨潮资讯网 API
CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
}

# 请求间隔（秒），避免被封
REQUEST_DELAY_MIN = 1.5
REQUEST_DELAY_MAX = 3.0

# 年报分类编码
ANNUAL_REPORT_CATEGORY = "category_ndbg_szsh"


# ============================================================
# 核心函数
# ============================================================

def get_stock_org_id(stock_code: str) -> dict:
    """
    通过巨潮搜索接口获取股票的orgId和短代码
    返回: {"orgId": "xxx", "code": "002637", "name": "赞宇科技", "category": "sz"}
    """
    url = "http://www.cninfo.com.cn/new/information/topSearch/query"
    data = {"keyWord": stock_code, "maxNum": 5}
    
    try:
        resp = requests.post(url, data=data, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        
        if not result:
            print(f"  [错误] 未找到股票: {stock_code}")
            return None
        
        # 搜索结果可能有多个，匹配精确代码
        for item in result:
            if item.get("code") == stock_code:
                return {
                    "orgId": item.get("orgId"),
                    "code": item.get("code"),
                    "name": item.get("zwjc", ""),
                    "category": item.get("category", ""),
                }
        
        # 如果没有精确匹配，返回第一个
        first = result[0]
        return {
            "orgId": first.get("orgId"),
            "code": first.get("code"),
            "name": first.get("zwjc", ""),
            "category": first.get("category", ""),
        }
    
    except Exception as e:
        print(f"  [错误] 查询股票信息失败 {stock_code}: {e}")
        return None


def query_annual_reports(stock_code: str, org_id: str, plate: str = "") -> list:
    """
    查询指定股票的全部年度报告公告列表
    """
    all_announcements = []
    page = 1
    max_pages = 50  # 安全上限
    
    while page <= max_pages:
        data = {
            "stock": f"{stock_code},{org_id}",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": plate if plate else "szse",
            "category": ANNUAL_REPORT_CATEGORY,
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        
        try:
            resp = requests.post(
                CNINFO_QUERY_URL, data=data, headers=HEADERS, timeout=20
            )
            resp.raise_for_status()
            result = resp.json()
            
            announcements = result.get("announcements", [])
            if not announcements:
                break
            
            all_announcements.extend(announcements)
            
            total_pages = result.get("totalpages", 1)
            if page >= total_pages:
                break
            
            page += 1
            time.sleep(random.uniform(0.5, 1.0))
        
        except Exception as e:
            print(f"  [错误] 查询第{page}页失败: {e}")
            break
    
    return all_announcements


def filter_annual_reports(announcements: list) -> list:
    """
    从公告列表中筛选出正式年度报告（排除摘要、更正、修订稿等）
    """
    filtered = []
    
    for ann in announcements:
        title = ann.get("announcementTitle", "")
        
        # 必须包含"年度报告"或"年报"
        if "年度报告" not in title and "年报" not in title:
            continue
        
        # 排除摘要
        if "摘要" in title:
            continue
        
        # 排除更正/补充/修订说明类
        if any(kw in title for kw in ["更正", "补充", "致歉", "差错", "说明", "意见"]):
            continue
        
        # 排除英文版
        if "英文" in title or "English" in title.lower():
            continue
        
        # 排除已取消/已废止
        if any(kw in title for kw in ["取消", "废止"]):
            continue
        
        filtered.append(ann)
    
    # 去重：同一年度可能有修订版，优先保留最新的
    filtered.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
    
    # 按年度去重（从标题提取年份）
    seen_years = set()
    deduped = []
    
    for ann in filtered:
        title = ann.get("announcementTitle", "")
        year = extract_year_from_title(title)
        if year and year in seen_years:
            continue
        if year:
            seen_years.add(year)
        deduped.append(ann)
    
    # 按年份正序排列
    deduped.sort(key=lambda x: x.get("announcementTime", 0))
    
    return deduped


def extract_year_from_title(title: str) -> str:
    """从年报标题中提取报告年份"""
    import re
    match = re.search(r"(\d{4})\s*年?\s*年度报告", title)
    if match:
        return match.group(1)
    return ""


def download_pdf(url: str, save_path: str) -> bool:
    """下载PDF文件"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120, stream=True)
        resp.raise_for_status()
        
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(save_path)
        if file_size < 10240:  # 小于10KB可能是错误页面
            os.remove(save_path)
            print(f"  [警告] 文件太小({file_size}B)，可能下载失败，已删除")
            return False
        
        return True
    
    except Exception as e:
        print(f"  [错误] 下载失败: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def download_reports_for_stock(stock_code: str, annual_years: int = 3) -> dict:
    """
    下载单只股票的年度报告
    annual_years: 下载最近几年的年报（0=全部）
    返回: {"success": bool, "pdf_dir": str, "reports": list}
    """
    print(f"\n{'='*60}")
    print(f"开始处理: {stock_code}")
    print(f"{'='*60}")
    
    # 1. 查询股票信息
    print(f"  [1/4] 查询股票信息...")
    stock_info = get_stock_org_id(stock_code)
    if not stock_info:
        return {"success": False, "error": "未找到股票信息"}
    
    stock_name = stock_info["name"]
    org_id = stock_info["orgId"]
    category = stock_info.get("category", "")
    
    # 判断交易所
    if category == "sz" or stock_code.startswith(("0", "3")):
        plate = "szse"
    else:
        plate = "sse"
    
    print(f"  股票名称: {stock_name} ({stock_code})")
    print(f"  交易所: {'深交所' if plate == 'szse' else '上交所'}")
    
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    
    # 2. 查询年报公告列表
    print(f"  [2/4] 查询年度报告列表...")
    announcements = query_annual_reports(stock_code, org_id, plate)
    print(f"  找到 {len(announcements)} 条年报相关公告")
    
    if not announcements:
        return {"success": False, "error": "未找到年报公告"}
    
    # 3. 筛选正式年度报告
    print(f"  [3/4] 筛选正式年度报告...")
    reports = filter_annual_reports(announcements)
    print(f"  筛选出 {len(reports)} 份正式年度报告")
    
    if not reports:
        return {"success": False, "error": "筛选后无有效年报"}
    
    # 如果指定年份，只取最近N年
    if annual_years > 0:
        reports = reports[-annual_years:]
        print(f"  仅下载最近 {annual_years} 年的年报")
    
    # 4. 下载
    print(f"  [4/4] 开始下载...")
    
    stock_dir = os.path.join(SAVE_DIR, f"{stock_code}_{stock_name}")
    os.makedirs(stock_dir, exist_ok=True)
    
    downloaded = []
    success_count = 0
    fail_count = 0
    
    for i, report in enumerate(reports, 1):
        title = report.get("announcementTitle", "未知标题")
        title = title.replace("<em>", "").replace("</em>", "")
        
        adjunct_url = report.get("adjunctUrl", "")
        ann_time = report.get("announcementTime", 0)
        
        if not adjunct_url:
            continue
        
        # 生成文件名
        year = extract_year_from_title(title)
        if year:
            filename = f"{stock_code}_{stock_name}_{year}年年度报告.pdf"
        else:
            if ann_time:
                date_str = datetime.fromtimestamp(ann_time / 1000).strftime("%Y%m%d")
            else:
                date_str = "unknown"
            filename = f"{stock_code}_{stock_name}_{date_str}_年度报告.pdf"
        
        # 清理文件名中的非法字符
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            filename = filename.replace(char, '_')
        
        save_path = os.path.join(stock_dir, filename)
        
        # 如果已存在且文件有效，跳过
        if os.path.exists(save_path) and os.path.getsize(save_path) > 10240:
            print(f"  [{i}/{len(reports)}] 已存在，跳过: {filename}")
            success_count += 1
            downloaded.append(save_path)
            continue
        
        # 下载
        download_url = CNINFO_DOWNLOAD_BASE + adjunct_url
        print(f"  [{i}/{len(reports)}] 下载中: {filename}")
        
        if download_pdf(download_url, save_path):
            file_size = format_file_size(os.path.getsize(save_path))
            print(f"           [OK] 完成 ({file_size})")
            success_count += 1
            downloaded.append(save_path)
        else:
            fail_count += 1
        
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    
    print(f"\n  下载汇总 [{stock_code} {stock_name}]:")
    print(f"  - 成功下载: {success_count} 份")
    print(f"  - 下载失败: {fail_count} 份")
    
    return {
        "success": True,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "pdf_dir": stock_dir,
        "downloaded": downloaded,
        "success_count": success_count,
        "fail_count": fail_count
    }


def run(ts_code_or_keyword: str, annual_years: int = 3, verbose: bool = True) -> dict:
    """
    主入口：下载指定股票的年度报告
    ts_code_or_keyword: 股票代码或简称
    annual_years: 下载最近几年的年报（0=全部）
    """
    # 简化代码（去掉交易所后缀）
    stock_code = ts_code_or_keyword.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    
    if verbose:
        print(f"{'=' * 70}")
        print(f" 年度报告下载工具")
        print(f" 标的：{stock_code}")
        print(f" 年份范围：{'全部' if annual_years == 0 else f'最近{annual_years}年'}")
        print(f"{'=' * 70}")
    
    result = download_reports_for_stock(stock_code, annual_years)
    
    print(f"\n  [成功] 下载完成！")
    print(f"保存目录：{result['pdf_dir']}")
    
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="年度报告下载工具")
    parser.add_argument("stock", help="股票代码或简称")
    parser.add_argument("--years", type=int, default=3, help="下载最近几年年报（0=全部）")
    args = parser.parse_args()
    
    run(args.stock, annual_years=args.years)
