#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载鲁西化工2年一期的报告（2024年年报、2023年年报、2025年上半年报）
"""

import requests
import time
import os
from datetime import datetime
import sys
import io
import re

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports", "000830_鲁西化工")
os.makedirs(SAVE_DIR, exist_ok=True)

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
}

# 分类编码
CATEGORY_MAP = {
    "年报": "category_ndbg_szsh",
    "半年报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
}

def download_pdf(url, filename):
    """下载PDF文件"""
    try:
        print(f"  正在下载: {filename}")
        resp = requests.get(url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()
        
        save_path = os.path.join(SAVE_DIR, filename)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"    [OK] 完成 ({file_size:.1f}MB)")
        return True
    except Exception as e:
        print(f"    [失败] {e}")
        return False

def query_reports(stock_code, org_id, report_type, year):
    """查询指定类型、指定年份的报告"""
    category = CATEGORY_MAP.get(report_type, "")
    if not category:
        return []
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    se_date = f"{start_date}~{end_date}"
    
    data = {
        "stock": f"{stock_code},{org_id}",
        "tabName": "fulltext",
        "pageSize": 30,
        "pageNum": 1,
        "column": "szse",
        "category": category,
        "searchkey": report_type,
        "seDate": se_date,
        "plate": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    
    try:
        resp = requests.post(CNINFO_QUERY_URL, data=data, headers=headers, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        
        announcements = result.get("announcements", [])
        
        # 过滤：只要正式报告，排除摘要、审核意见等
        filtered = []
        for ann in announcements:
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            adjunct_url = ann.get("adjunctUrl", "")
            
            # 排除摘要和审核意见
            if "摘要" in title or "审核意见" in title:
                continue
            
            if adjunct_url:
                filtered.append({
                    "title": title,
                    "url": CNINFO_DOWNLOAD_BASE + adjunct_url,
                    "date": ann.get("announcementTime", 0)
                })
        
        return filtered
    
    except Exception as e:
        print(f"  查询失败: {e}")
        return []

# 主程序
print("=" * 70)
print(" 鲁西化工 财务报告下载器")
print(" 下载：2024年年报、2023年年报、2025年上半年报")
print("=" * 70)

stock_code = "000830"
org_id = "gssz0000830"

all_reports = []

# 下载计划
download_plan = [
    ("年报", 2024, "2024年年度报告"),
    ("年报", 2023, "2023年年度报告"),
    ("半年报", 2025, "2025年上半年度报告"),
]

print("\n[第1步] 查询报告列表...\n")

for report_type, year, display_name in download_plan:
    print(f"查询 {display_name}:")
    
    reports = query_reports(stock_code, stock_code, report_type, year)
    
    if reports:
        print(f"  找到 {len(reports)} 份正式报告")
        for report in reports:
            print(f"    - {report['title']}")
            all_reports.append({
                "name": display_name,
                "type": report_type,
                "year": year,
                "title": report['title'],
                "url": report['url'],
            })
    else:
        print(f"  未找到报告")
    
    time.sleep(1)

# 下载报告
print(f"\n[第2步] 开始下载 {len(all_reports)} 份报告...\n")

success_count = 0
for i, report in enumerate(all_reports, 1):
    print(f"[{i}/{len(all_reports)}] {report['name']}")
    
    # 生成文件名
    filename = f"{stock_code}_鲁西化工_{report['year']}年{report['type']}_{report['type']}.pdf"
    filename = filename.replace("年年报", "年年度报告").replace("年半年报", "年上半年度报告")
    
    if download_pdf(report['url'], filename):
        success_count += 1
    
    time.sleep(1)

print(f"\n" + "=" * 70)
print(f"下载完成!")
print(f"成功: {success_count}/{len(all_reports)}")
print(f"保存目录: {SAVE_DIR}")
print("=" * 70)
