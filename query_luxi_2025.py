#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
from datetime import datetime
import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

print("查询 2025 年中期报告:")

se_date = "2025-01-01~2025-12-31"

data = {
    "stock": "000830,gssz0000830",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "category_bgjz_szsh",
    "searchkey": "中期报告",
    "seDate": se_date,
    "plate": "",
    "secid": "",
    "sortName": "",
    "sortType": "",
    "isHLtitle": "true",
}

url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

try:
    resp = requests.post(url, data=data, headers=headers, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    
    if result and isinstance(result, list):
        announcements = result
    elif result and isinstance(result, dict):
        announcements = result.get("announcements", [])
    else:
        announcements = []
    
    print(f"找到 {len(announcements)} 条公告\n")
    
    for i, ann in enumerate(announcements[:10], 1):
        title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
        adjunct_url = ann.get("adjunctUrl", "")
        
        print(f"[{i}] {title}")
        if adjunct_url:
            print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
        print()
        
except Exception as e:
    print(f"查询失败: {e}")
    import traceback
    traceback.print_exc()
