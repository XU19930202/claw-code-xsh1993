#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查询博源化工最近一期的中期/半年度报告"""

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

# 查询所有公告看看有没有中期/半年报
url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

print("=" * 80)
print("查询博源化工（000683）的中期/半年度报告（用\"半年报\"关键字）")
print("=" * 80)

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "",
    "searchkey": "半年报",
    "seDate": "2024-01-01~2025-12-31",
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
    print(f"\n找到 {len(announcements)} 条相关公告\n")
    
    for i, ann in enumerate(announcements[:15], 1):
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

# 也试试用"一季"或"三季"查询
print("\n" + "=" * 80)
print("查询博源化工（000683）的季度报告（用\"一季\"关键字）")
print("=" * 80)

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "",
    "searchkey": "一季",
    "seDate": "2024-01-01~2025-12-31",
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
    print(f"\n找到 {len(announcements)} 条相关公告\n")
    
    for i, ann in enumerate(announcements[:5], 1):
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
