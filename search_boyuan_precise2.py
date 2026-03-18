#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 用精确关键词搜索中期报告
print("用关键词搜索博源化工2025年的中期/半年度报告:\n")

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "",
    "searchkey": "2025年上半年中期报告",
    "seDate": "",
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
    
    if result is None:
        print("API返回None")
    elif isinstance(result, dict):
        announcements = result.get("announcements", [])
        print(f"找到 {len(announcements)} 条公告\n")
        
        for i, ann in enumerate(announcements, 1):
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            ann_time = ann.get("announcementTime", 0)
            adjunct_url = ann.get("adjunctUrl", "")
            
            date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
            
            print(f"[{i}] {date_str}")
            print(f"    {title}")
            if adjunct_url:
                print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
            print()
    elif isinstance(result, list):
        print(f"找到 {len(result)} 条公告\n")
        
        for i, ann in enumerate(result, 1):
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            ann_time = ann.get("announcementTime", 0)
            adjunct_url = ann.get("adjunctUrl", "")
            
            date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
            
            print(f"[{i}] {date_str}")
            print(f"    {title}")
            if adjunct_url:
                print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
            print()
    else:
        print(f"API返回类型: {type(result)}, 内容: {result}")
            
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
