#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import re
from datetime import datetime

url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/x-www-form-urlencoded',
}

# 按中文名搜索年报
keywords = ['年报', '半年报', '三季报']

for keyword in keywords:
    print(f"\n{'='*80}")
    print(f"搜索: 保隆科技 + {keyword}")
    print(f"{'='*80}\n")
    
    data = {
        'stock': '603197',
        'searchkey': keyword,
        'pageNum': 1,
        'pageSize': 30,
        'column': 'szse',
        'tabName': 'fulltext',
    }
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=15)
        result = resp.json()
        anns = result.get('announcements', [])
        total = result.get('totalAnnouncement', 0)
        
        print(f"共找到 {total} 条记录\n")
        
        for i, ann in enumerate(anns[:10]):
            title = re.sub(r'<[^>]+>', '', ann.get('announcementTitle', 'N/A'))
            date_ts = ann.get('announcementTime', 0)
            date_str = datetime.fromtimestamp(date_ts / 1000).strftime("%Y-%m-%d") if date_ts else "N/A"
            
            print(f"[{i+1}] {title}")
            print(f"    日期: {date_str}")
            print(f"    URL: http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}")
            print()
            
    except Exception as e:
        print(f"错误: {e}\n")
