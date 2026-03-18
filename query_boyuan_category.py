#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 直接查询中期报告分类
print("查询博源化工的中期报告（category_bgjz_szsh分类）:\n")

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "category_bgjz_szsh",
    "searchkey": "",
    "seDate": "2024-01-01~2025-12-31",
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
    
    announcements = result.get("announcements", [])
    print(f"找到 {len(announcements)} 条中期报告分类公告\n")
    
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
