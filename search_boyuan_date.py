#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from datetime import datetime
import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 查询2025年7月-8月的所有报告类公告
print("查询博源化工2025年7-8月的报告类公告（中期报告发布时间）:\n")

data = {
    "stock": "000683,gssz0000683",
    "tabName": "fulltext",
    "pageSize": 30,
    "pageNum": 1,
    "column": "szse",
    "category": "",
    "searchkey": "",
    "seDate": "2025-07-01~2025-08-31",
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
    
    if isinstance(result, dict):
        announcements = result.get("announcements", []) or []
    else:
        announcements = result or []
    
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
            # 尝试判断文件大小
            if len(adjunct_url) > 10:
                print(f"    [OK] 有附件")
        print()
            
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
