#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查询博源化工2022-2024年的年报和最近一期中期报告"""

import requests
import time
import sys
import io
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 查询年报
print("=" * 80)
print("查询博源化工（000683）的年度报告")
print("=" * 80)

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "category_ndbg",
    "searchkey": "",
    "seDate": "2020-01-01~2024-12-31",
    "plate": "",
    "secid": "",
    "sortName": "",
    "sortType": "",
    "isHLtitle": "true",
}

url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

try:
    resp = requests.post(url, data=data, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    
    announcements = result.get("announcements", [])
    print(f"\n找到 {len(announcements)} 条年度报告相关公告\n")
    
    # 显示前面的公告（最新的）
    for i, ann in enumerate(announcements[:10], 1):
        title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
        ann_time = ann.get("announcementTime", 0)
        adjunct_url = ann.get("adjunctUrl", "")
        
        date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
        
        print(f"[{i}] {date_str}")
        print(f"    {title}")
        if adjunct_url:
            print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
        print()
            
except Exception as e:
    print(f"Error: {e}")

# 查询中期报告
print("\n" + "=" * 80)
print("查询博源化工（000683）的中期报告")
print("=" * 80)

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "category_bgjz_szsh",
    "searchkey": "",
    "seDate": "2023-01-01~2025-12-31",
    "plate": "",
    "secid": "",
    "sortName": "",
    "sortType": "",
    "isHLtitle": "true",
}

try:
    resp = requests.post(url, data=data, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    
    announcements = result.get("announcements", [])
    print(f"\n找到 {len(announcements)} 条中期报告相关公告\n")
    
    # 显示前面的公告（最新的）
    for i, ann in enumerate(announcements[:10], 1):
        title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
        ann_time = ann.get("announcementTime", 0)
        adjunct_url = ann.get("adjunctUrl", "")
        
        date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
        
        print(f"[{i}] {date_str}")
        print(f"    {title}")
        if adjunct_url:
            print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
        print()
            
except Exception as e:
    print(f"Error: {e}")
