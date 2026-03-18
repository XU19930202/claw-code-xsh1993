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

# 按年份时间段查询 (2025年上半年对应2025-01-01到2025-06-30)
for year in [2025, 2024, 2023]:
    print(f"\n=== 查询 {year} 年度报告 ===")
    
    for page in range(1, 3):
        # 用年度范围查询
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        se_date = f"{start_date}~{end_date}"
        
        data = {
            "stock": "000807,gssz0000807",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": "szse",
            "category": "category_bgjz_szsh",  # 中期报告分类
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
            
            announcements = result.get("announcements", [])
            if not announcements:
                print(f"  第{page}页无数据")
                break
            
            print(f"  第{page}页找到 {len(announcements)} 条")
            
            for ann in announcements:
                title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
                ann_time = ann.get("announcementTime", 0)
                adjunct_url = ann.get("adjunctUrl", "")
                
                date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
                
                if adjunct_url:
                    print(f"    {date_str} - {title}")
                    
        except Exception as e:
            print(f"  查询失败: {e}")
            break
        
        time.sleep(1)
